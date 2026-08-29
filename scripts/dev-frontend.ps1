# ZCES dev bring-up: frontend (npm install + next dev)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\dev-frontend.ps1
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"

if (-not (Test-Path (Join-Path $frontendDir ".env.local"))) {
    Write-Host "frontend\.env.local not found. Copy frontend\.env.example and edit values first." -ForegroundColor Yellow
    exit 1
}

Push-Location $frontendDir
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing npm dependencies..."
        npm install
    }

    Write-Host "Starting frontend dev server on port 3000..."
    npm run dev
}
finally {
    Pop-Location
}
