# ZCES backend tests against a disposable scratch database.
#
# Creates a fresh `zces_test` database (dropping any previous one), runs the
# full pytest suite against it, and leaves `zces_dev` untouched. Integration
# tests build their schema via Base.metadata.create_all — no Alembic needed.
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts\test-backend.ps1 [extra pytest args...]
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"

function Get-EnvValue([string]$filePath, [string]$key) {
    if (-not (Test-Path $filePath)) { return $null }
    $line = Get-Content $filePath | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split "=", 2)[1].Trim().Trim('"')
}

$dbUrl = Get-EnvValue (Join-Path $backendDir ".env") "DATABASE_URL"
if (-not $dbUrl) {
    Write-Error "DATABASE_URL not found in backend\.env - cannot derive the scratch database."
    exit 1
}

$testDbName = "zces_test"
$testUrl = $dbUrl -replace "(postgresql\+psycopg://[^/]+/).*", "`$1$testDbName"
if ($testUrl -eq $dbUrl) {
    Write-Error "Could not derive scratch URL from DATABASE_URL."
    exit 1
}

# Recreate the scratch database with the server's maintenance connection.
$py = @"
import os
import psycopg
from sqlalchemy.engine import make_url

url = make_url(os.environ["ZCES_DB_URL"])
admin = psycopg.connect(
    host=url.host, port=url.port, user=url.username, password=url.password,
    dbname="postgres", autocommit=True,
)
admin.execute(f"DROP DATABASE IF EXISTS {os.environ['ZCES_TEST_DB']} WITH (FORCE)")
admin.execute(f"CREATE DATABASE {os.environ['ZCES_TEST_DB']}")
admin.close()
print(f"scratch database ready: {os.environ['ZCES_TEST_DB']}")
"@
$tmpPy = Join-Path $env:TEMP "zces-create-test-db.py"
Set-Content -Path $tmpPy -Value $py -Encoding ASCII

$env:ZCES_DB_URL = $dbUrl
$env:ZCES_TEST_DB = $testDbName
Push-Location $backendDir
try {
    & (Join-Path $backendDir ".venv\Scripts\python.exe") $tmpPy
    if ($LASTEXITCODE -ne 0) { exit 1 }

    $env:DATABASE_URL = $testUrl
    & (Join-Path $backendDir ".venv\Scripts\python.exe") -m pytest -p no:cacheprovider @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    Remove-Item "Env:ZCES_DB_URL", "Env:ZCES_TEST_DB" -ErrorAction SilentlyContinue
}
