#requires -Version 5.1
<#
.SYNOPSIS
    Baut das MarktPilot-Frontend und schiebt es auf die Kassen-Pi.

.BESCHREIBUNG
    Erwartet die Laptop-IP als Umgebungsvariable $env:LAPTOP_IP
    und die Pi-IP als Argument oder Umgebungsvariable $env:PI_IP.

    Was es macht:
      1. Frontend production-bauen (mit VITE_API_BASE = Laptop-IP:8000)
      2. dist/* per scp auf die Pi nach ~/markt-pilot-frontend/ kopieren
      3. nginx auf der Pi reloaden (falls vorhanden)

.BEISPIELE
    .\deploy-kasse.ps1 -PiIP 192.168.2.51
    $env:PI_IP = "192.168.2.51"; .\deploy-kasse.ps1
    .\deploy-kasse.ps1 -PiIP 192.168.2.51 -SkipBuild   # nur scp, kein Build

.NOTES
    Quelle: https://github.com/fakeochamp1357/markt-pilot
    Benutzung: pi  muss per SSH-Key vom Laptop aus erreichbar sein
                (sonst fragt scp jedes Mal nach Passwort).
#>
[CmdletBinding()]
param(
    [string]$PiIP = $env:PI_IP,
    [string]$LaptopIP = $env:LAPTOP_IP,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------
# Helfer
# ------------------------------------------------------------------
function Write-Step { param($m) Write-Host "`n===> $m" -ForegroundColor Cyan }
function Write-Ok    { param($m) Write-Host "  [ok] $m" -ForegroundColor Green }
function Write-Warn  { param($m) Write-Host "  [!] $m" -ForegroundColor Yellow }
function Write-Err   { param($m) Write-Host "  [X] $m" -ForegroundColor Red }

# ------------------------------------------------------------------
# Sanity-Checks
# ------------------------------------------------------------------
if (-not $PiIP) {
    Write-Err "Pi-IP fehlt. Entweder -PiIP Argument oder `$env:PI_IP setzen."
    Write-Host "  Beispiel: .\deploy-kasse.ps1 -PiIP 192.168.2.51" -ForegroundColor Yellow
    exit 1
}
if (-not $LaptopIP) {
    Write-Host "  Laptop-IP nicht explizit gesetzt --" versuche sie zu erkennen..." -ForegroundColor Yellow
    try {
        $LaptopIP = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet*","WLAN*" -ErrorAction Stop |
            Where-Object { $_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*" } |
            Select-Object -First 1).IPAddress
        if (-not $LaptopIP) { throw "nicht gefunden" }
        Write-Ok "Laptop-IP erkannt: $LaptopIP"
    } catch {
        Write-Err "Konnte Laptop-IP nicht erkennen. Setze `$env:LAPTOP_IP = '192.168.2.30' oder aehnlich."
        exit 1
    }
}

# ------------------------------------------------------------------
# Backend-Health (sanity check)
# ------------------------------------------------------------------
Write-Step "Backend-Health auf $LaptopIP"
try {
    $h = Invoke-RestMethod -Uri "http://${LaptopIP}:8000/healthz" -TimeoutSec 3
    Write-Ok "Backend antwortet: $($h.status)"
} catch {
    Write-Warn "Backend nicht erreichbar unter $LaptopIP --" der Kasse-Build geht trotzdem durch, aber die Pi wird Daten nicht laden."
}

# ------------------------------------------------------------------
# Frontend bauen
# ------------------------------------------------------------------
if (-not $SkipBuild) {
    Write-Step "Frontend production-bauen"
    Push-Location "$PSScriptRoot\..\frontend"
    try {
        $env:VITE_API_BASE = "http://${LaptopIP}:8000"
        Write-Host "  VITE_API_BASE = $env:VITE_API_BASE"
        cmd /c npm run build
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Frontend-Build fehlgeschlagen (Exit $LASTEXITCODE)"
            exit 1
        }
        Write-Ok "Build fertig (frontend/dist/)"
    } finally {
        Pop-Location
    }
} else {
    Write-Warn "Build uebersprungen (-SkipBuild)"
}

# ------------------------------------------------------------------
# scp auf die Pi
# ------------------------------------------------------------------
Write-Step "scp dist/* -> kasse@${PiIP}:~/markt-pilot-frontend/"
$distPath = Join-Path $PSScriptRoot "..\frontend\dist"
if (-not (Test-Path $distPath)) {
    Write-Err "dist/ nicht gefunden unter $distPath. Erst ohne -SkipBuild laufen lassen."
    exit 1
}

# rsync wuerde schneller sein, aber scp ist ueberall verfuegbar
$scpTarget = "kasse@${PiIP}:~/markt-pilot-frontend/"
Write-Host "  Ziel: $scpTarget"
scp -r "$distPath\*" $scpTarget
if ($LASTEXITCODE -ne 0) {
    Write-Err "scp fehlgeschlagen (Exit $LASTEXITCODE)"
    exit 1
}
Write-Ok "Frontend auf Pi deployed"

# ------------------------------------------------------------------
# nginx auf der Pi reloaden
# ------------------------------------------------------------------
Write-Step "nginx auf Pi reloaden (Frontend sofort sichtbar)"
$reloadCmd = 'sudo systemctl reload nginx 2>/dev/null && echo nginx-reloaded'
ssh "kasse@${PiIP}" $reloadCmd
if ($LASTEXITCODE -eq 0) {
    Write-Ok "nginx reload ausgeloest"
} else {
    Write-Warn "nginx-Reload fehlgeschlagen - manuell auf der Pi: sudo systemctl reload nginx"
}

# ------------------------------------------------------------------
# Kassen-Browser refresh (optional, geht nur wenn Display an Pi angeschlossen)
# ------------------------------------------------------------------
Write-Host ""
Write-Ok "Fertig. Auf der Kassen-Pi im Browser F5 druecken (oder Chromium-Kiosk neu laden)."
Write-Host "  URL auf der Pi: http://localhost:8080/" -ForegroundColor Cyan
