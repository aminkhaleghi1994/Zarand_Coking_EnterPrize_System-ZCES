# ZCES dev bring-up: backend (venv + deps + migrations + uvicorn)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\dev-backend.ps1
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"

if (-not (Test-Path (Join-Path $backendDir ".env"))) {
    Write-Host "backend\.env not found. Copy backend\.env.example and edit values first." -ForegroundColor Yellow
    exit 1
}

Push-Location $backendDir
try {
    if (-not (Test-Path ".venv")) {
        Write-Host "Creating virtual environment..."
        python -m venv .venv
    }

    $venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Error "Virtual environment python not found at $venvPython"
        exit 1
    }

    Write-Host "Installing dependencies..."
    & $venvPython -m pip install -r requirements-dev.txt --quiet

    Write-Host "Applying migrations..."
    & $venvPython -m alembic upgrade head

    $port = "8000"
    $envFile = Get-Content (Join-Path $backendDir ".env")
    $urlLine = $envFile | Where-Object { $_ -match "^DATABASE_URL=" }

    Write-Host "Starting backend on port $port (from backend\.env defaults)..."
    Write-Host "Health endpoint: http://<backend-host>:$port/healthz"
    & $venvPython -m uvicorn app.main:app --reload --host 0.0.0.0 --port $port
}
finally {
    Pop-Location
}
