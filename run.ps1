[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$VenvPath = if ($env:VENV_PATH) { $env:VENV_PATH } else { Join-Path $ProjectRoot "backend\.venv" }
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$AppHost = if ($env:APP_HOST) { $env:APP_HOST } else { "127.0.0.1" }
$AppPort = if ($env:APP_PORT) { $env:APP_PORT } else { "8000" }
$OpenBrowser = if ($env:OPEN_BROWSER) { $env:OPEN_BROWSER } else { "1" }
$FrontendDist = Join-Path $ProjectRoot "frontend\dist"

if (-not (Test-Path $VenvPython)) { throw "Python environment not found at $VenvPath. Run .\install.ps1 first." }
if (-not (Test-Path (Join-Path $FrontendDist "index.html"))) { throw "Frontend build not found. Run .\install.ps1 first." }

Write-Host "Applying database migrations..."
Push-Location (Join-Path $ProjectRoot "backend")
try {
    & $VenvPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }

    $env:SERVE_FRONTEND = "1"
    $env:FRONTEND_DIST_DIR = $FrontendDist
    $env:DB_MIGRATION_MODE = "check"

    $AppUrl = if ($AppHost -eq "0.0.0.0") { "http://localhost:$AppPort" } else { "http://${AppHost}:$AppPort" }
    Write-Host "Math Book Translator is available at $AppUrl"
    Write-Host "Press Ctrl+C to stop."
    if ($OpenBrowser -eq "1") { Start-Process $AppUrl }

    & $VenvPython -m uvicorn app.main:app --host $AppHost --port $AppPort
} finally {
    Pop-Location
}
