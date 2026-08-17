#requires -Version 5.1
<#
.SYNOPSIS
    Importiert eine CSV mit Produkten in MarktPilot.

.DESCRIPTION
    Erwartet eine CSV im "Export-Format" mit Spalten:
    id,sku,barcode,name,category_id,unit,size_weight,cost_price,sell_price,
    currency,stock_quantity,min_stock_level,expiry_date,supplier,is_active,color_tag

    Das Skript transformiert die CSV in das vom Backend erwartete Format
    (siehe /api/products/bulk/upload) und schickt sie per HTTP-Upload.

    VOR dem eigentlichen Upload läuft ein Trockenlauf, der zeigt:
      - wie viele Zeilen importiert würden
      - welche Zeilen wegen fehlender Kategorie übersprungen werden
      - wie viele aktiv / inaktiv sind

.PARAMETER Backend
    Basis-URL des MarktPilot-Backends. Default: http://localhost:8000

.PARAMETER CsvPath
    Pfad zur CSV-Datei. Default: backend/products.csv (relativ zum Repo-Root)

.EXAMPLE
    .\import-products-csv.ps1
    .\import-products-csv.ps1 -Backend "http://192.168.2.30:8000"
    .\import-products-csv.ps1 -CsvPath "D:\meine-produkte.csv"
#>
[CmdletBinding()]
param(
    [string]$Backend = "http://localhost:8000",
    [string]$CsvPath = ""
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------
# Helfer: bunte Konsolenausgabe
# ------------------------------------------------------------------
function Write-Info    { param($msg) Write-Host $msg -ForegroundColor Cyan }
function Write-Ok      { param($msg) Write-Host $msg -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host $msg -ForegroundColor Yellow }
function Write-Err     { param($msg) Write-Host $msg -ForegroundColor Red }
function Write-Header  { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Magenta }

# ------------------------------------------------------------------
# Pfad zur CSV bestimmen
# ------------------------------------------------------------------
if (-not $CsvPath) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $CsvPath = Join-Path (Split-Path -Parent $scriptDir) "products.csv"
}
if (-not (Test-Path $CsvPath)) {
    Write-Err "CSV nicht gefunden: $CsvPath"
    exit 1
}
Write-Info "CSV-Datei: $CsvPath"

# ------------------------------------------------------------------
# Backend erreichbar?
# ------------------------------------------------------------------
try {
    $health = Invoke-RestMethod -Uri "$Backend/healthz" -TimeoutSec 5 -ErrorAction Stop
    Write-Ok "Backend erreichbar: $Backend ($($health.status))"
} catch {
    Write-Err "Backend nicht erreichbar unter $Backend"
    Write-Err "Starte zuerst den Server: cd C:\company\markt-pilot\backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
    exit 1
}

# ------------------------------------------------------------------
# CSV einlesen
# ------------------------------------------------------------------
try {
    $rows = Import-Csv -Path $CsvPath -Encoding UTF8
} catch {
    # PowerShell 5.1 kennt -Encoding UTF8 nicht immer
    $rows = Import-Csv -Path $CsvPath
}
if ($rows.Count -eq 0) {
    Write-Err "CSV ist leer."
    exit 1
}
Write-Info "Eingelesen: $($rows.Count) Zeilen"

# ------------------------------------------------------------------
# Statistik
# ------------------------------------------------------------------
Write-Header "Statistik"
$activeCount   = @($rows | Where-Object { $_.is_active -eq 'true' }).Count
$inactiveCount = @($rows | Where-Object { $_.is_active -ne 'true' }).Count
$noCategory    = @($rows | Where-Object { -not $_.category_id -or $_.category_id -eq '' })

Write-Host "  Aktiv:               $activeCount"
Write-Host "  Inaktiv:             $inactiveCount"
Write-Host "  Ohne Kategorie:      $($noCategory.Count)"

if ($noCategory.Count -gt 0) {
    Write-Warn "`nDiese Zeilen haben keine Kategorie und werden übersprungen:"
    $noCategory | Select-Object id, name, barcode, is_active | Format-Table | Out-String | Write-Host
}

# ------------------------------------------------------------------
# Interaktive Fragen
# ------------------------------------------------------------------
Write-Header "Optionen"

if ($inactiveCount -gt 0) {
    $ans = Read-Host "Aktuell sind $inactiveCount von $($rows.Count) auf 'is_active=false'. Sollen ALLE Produkte aktiviert werden? (j/N)"
    $forceActive = ($ans -eq 'j' -or $ans -eq 'J' -or $ans -eq 'y' -or $ans -eq 'Y')
} else {
    $forceActive = $false
}

if ($noCategory.Count -gt 0) {
    $ans = Read-Host "Sollen Zeilen ohne Kategorie ($(($noCategory | ForEach-Object { $_.name }) -join ', ')) uebersprungen werden? (J/n)"
    $skipNoCategory = -not ($ans -eq 'n' -or $ans -eq 'N')
} else {
    $skipNoCategory = $true
}

# ------------------------------------------------------------------
# CSV transformieren
# ------------------------------------------------------------------
Write-Header "Transformation"
$workRows = @()
$skippedRows = @()

foreach ($r in $rows) {
    # Kategorie prüfen
    if (-not $r.category_id -or $r.category_id -eq '') {
        if ($skipNoCategory) {
            $skippedRows += $r
            continue
        } else {
            Write-Err "Zeile '$($r.name)' hat keine Kategorie — Abbruch."
            exit 1
        }
    }

    # Mapping ins Ziel-Format
    $new = [ordered]@{
        barcode          = if ($r.barcode) { $r.barcode } else { '' }
        sku              = if ($r.sku)     { $r.sku }     else { '' }
        name             = $r.name
        category         = $r.category_id   # Backend akzeptiert ID
        unit             = $r.unit
        size_weight      = if ($r.size_weight) { $r.size_weight } else { '' }
        cost_price       = $r.cost_price
        sell_price       = $r.sell_price
        currency         = $r.currency
        stock_quantity   = $r.stock_quantity
        min_stock_level  = $r.min_stock_level
        expiry_date      = if ($r.expiry_date) { $r.expiry_date } else { '' }
        supplier         = if ($r.supplier) { $r.supplier } else { '' }
        notes            = ''
        color_tag        = $r.color_tag
        is_active        = if ($forceActive) { 'true' } else { $r.is_active }
    }
    $workRows += [PSCustomObject]$new
}

Write-Info "Zum Import vorbereitet: $($workRows.Count) Zeilen"
Write-Info "Uebersprungen: $($skippedRows.Count) Zeilen"

if ($workRows.Count -eq 0) {
    Write-Err "Keine Zeilen zum Importieren."
    exit 1
}

# ------------------------------------------------------------------
# Trockenlauf: zeige erste 10 Zeilen
# ------------------------------------------------------------------
Write-Header "Trockenlauf (erste 10 Zeilen)"
$workRows | Select-Object -First 10 name, category, sell_price, is_active | Format-Table | Out-String | Write-Host

# ------------------------------------------------------------------
# Bestätigung
# ------------------------------------------------------------------
Write-Header "Bereit zum Import"
Write-Host "  Backend:    $Backend/api/products/bulk/upload"
Write-Host "  Zeilen:     $($workRows.Count)"
Write-Host "  Aktiv:      $(@($workRows | Where-Object { $_.is_active -eq 'true' }).Count) von $($workRows.Count)"
if ($skippedRows.Count -gt 0) {
    Write-Host "  Uebersprungen: $($skippedRows.Count)  ( $($($skippedRows | ForEach-Object { $_.name }) -join ', ') )"
}

$confirm = Read-Host "`nWirklich importieren? (j/N)"
if ($confirm -ne 'j' -and $confirm -ne 'J' -and $confirm -ne 'y' -and $confirm -ne 'Y') {
    Write-Warn "Abgebrochen."
    exit 0
}

# ------------------------------------------------------------------
# CSV temporaer schreiben
# ------------------------------------------------------------------
$tempCsv = [System.IO.Path]::Combine(
    [System.IO.Path]::GetTempPath(),
    [System.IO.Path]::GetRandomFileName() + ".csv"
)
$workRows | Export-Csv -Path $tempCsv -NoTypeInformation -Encoding UTF8

# ------------------------------------------------------------------
# Upload
# ------------------------------------------------------------------
Write-Header "Import laeuft..."
try {
    $file = Get-Item $tempCsv
    $response = Invoke-RestMethod `
        -Uri "$Backend/api/products/bulk/upload" `
        -Method Post `
        -Form @{ file = $file } `
        -TimeoutSec 60

    Write-Ok "`nImport abgeschlossen!"
    Write-Host "  Erstellt:   $($response.created)"
    Write-Host "  Aktualisiert: $($response.updated)"
    Write-Host "  Uebersprungen: $($response.skipped)"
    if ($response.errors -and $response.errors.Count -gt 0) {
        Write-Warn "`n  Fehler ($($response.errors.Count)):"
        $response.errors | ForEach-Object { Write-Host "    - $_" -ForegroundColor Yellow }
    }
} catch {
    Write-Err "Import fehlgeschlagen: $_"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $body = $reader.ReadToEnd()
        Write-Err "Antwort: $body"
    }
    exit 1
} finally {
    Remove-Item $tempCsv -ErrorAction SilentlyContinue
}

# ------------------------------------------------------------------
# Verifizieren
# ------------------------------------------------------------------
Write-Header "Verifizierung"
$products = Invoke-RestMethod -Uri "$Backend/api/products?limit=500" -TimeoutSec 10
Write-Ok "In DB vorhanden: $($products.total) Produkte total"

if ($activeCount + $inactiveCount - $noCategory.Count -gt 0) {
    $active = ($products.items | Where-Object { $_.is_active -eq $true }).Count
    Write-Host "  Davon aktiv: $active"
}

Write-Ok "`nFertig. Öffne http://localhost:5173/ um die Produkte zu sehen."
