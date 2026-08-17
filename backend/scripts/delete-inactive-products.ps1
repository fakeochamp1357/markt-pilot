#requires -Version 5.1
<#
.SYNOPSIS
    Loescht inaktive Produkte hart aus der MarktPilot-Datenbank.

.DESCRIPTION
    Einfacher Wrapper fuer delete_inactive_hard.py. Das Python-Skript macht
    selbst alle Checks (Backup, Vorschau, Confirm-Prompt, Hard-Delete + VACUUM).

    Foreign Keys: ReceiptLine.product_id hat ON DELETE SET NULL - alte Bons
    bleiben durch name_snapshot lesbar.

.EXAMPLE
    .\delete-inactive-products.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------
# Python-Helper finden
# ------------------------------------------------------------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "delete_inactive_hard.py"

if (-not (Test-Path $pyScript)) {
    Write-Host "[fehler] Python-Skript fehlt: $pyScript" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------
# Python-Interpreter bestimmen
# ------------------------------------------------------------------
$python = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
} else {
    Write-Host "[fehler] Weder 'python' noch 'py' im PATH gefunden." -ForegroundColor Red
    Write-Host "Tipp: Python 3.11+ installieren (https://www.python.org/downloads/)" -ForegroundColor Yellow
    exit 1
}

# ------------------------------------------------------------------
# Los geht's
# ------------------------------------------------------------------
Write-Host ""
Write-Host "MarktPilot: Inaktive Produkte hart loeschen" -ForegroundColor Magenta
Write-Host "Python: $python" -ForegroundColor Cyan
Write-Host "Skript: $pyScript" -ForegroundColor Cyan
Write-Host ""

# In das Skript-Verzeichnis wechseln, damit relative Pfade stimmen
Push-Location $scriptDir
try {
    & $python $pyScript
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
