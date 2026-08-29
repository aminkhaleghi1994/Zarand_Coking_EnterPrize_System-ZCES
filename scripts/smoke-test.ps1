# ZCES phase-gate smoke test (Foundation Skeleton)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\smoke-test.ps1
# Exits 0 only when every check passes.
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http -ErrorAction SilentlyContinue

$repoRoot = Split-Path -Parent $PSScriptRoot

function Get-EnvValue([string]$filePath, [string]$key) {
    if (-not (Test-Path $filePath)) { return $null }
    $line = Get-Content $filePath | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split "=", 2)[1].Trim()
}

$backendUrl = Get-EnvValue (Join-Path $repoRoot "frontend\.env.local") "BACKEND_API_BASE_URL"
if (-not $backendUrl) { $backendUrl = "http://127.0.0.1:8000/api/v1" }
$frontendUrl = Get-EnvValue (Join-Path $repoRoot "frontend\.env.local") "NEXT_PUBLIC_FRONTEND_URL"
if (-not $frontendUrl) { $frontendUrl = "http://localhost:3000" }

$failures = @()

function Check([string]$name, [scriptblock]$block) {
    try {
        & $block
        Write-Host "PASS  $name" -ForegroundColor Green
    }
    catch {
        Write-Host "FAIL  $name :: $($_.Exception.Message)" -ForegroundColor Red
        $script:failures += $name
    }
}

function Assert-True($condition, [string]$message) {
    if (-not $condition) { throw $message }
}

Check "backend healthz responds 200 with standard shape" {
    $response = Invoke-WebRequest -Uri "$backendUrl/healthz" -UseBasicParsing -TimeoutSec 10
    Assert-True ($response.StatusCode -eq 200) "expected 200, got $($response.StatusCode)"
    $body = $response.Content | ConvertFrom-Json
    Assert-True ($body.status -eq "ok") "status is not ok"
    Assert-True ($null -ne $body.app -and $null -ne $body.env -and $null -ne $body.version) "missing app/env/version"
    Assert-True ($null -ne $body.components.database) "missing database component"
}

Check "database component reports up" {
    $body = (Invoke-WebRequest -Uri "$backendUrl/healthz" -UseBasicParsing -TimeoutSec 10).Content | ConvertFrom-Json
    Assert-True ($body.components.database.status -eq "up") "database component is not up (is the DB running and .env configured?)"
}

Check "BFF proxy /api/health forwards backend health" {
    $response = Invoke-WebRequest -Uri "$frontendUrl/api/health" -UseBasicParsing -TimeoutSec 15
    Assert-True ($response.StatusCode -eq 200) "expected 200, got $($response.StatusCode)"
    $body = $response.Content | ConvertFrom-Json
    Assert-True ($body.status -eq "ok") "BFF health body is not ok"
}

Check "frontend serves English locale" {
    $response = Invoke-WebRequest -Uri "$frontendUrl/en" -UseBasicParsing -TimeoutSec 15
    Assert-True ($response.StatusCode -eq 200) "expected 200, got $($response.StatusCode)"
    Assert-True ($response.Content -match 'lang="en"') "html lang is not en"
}

Check "frontend serves Persian locale (RTL)" {
    $response = Invoke-WebRequest -Uri "$frontendUrl/fa" -UseBasicParsing -TimeoutSec 15
    Assert-True ($response.StatusCode -eq 200) "expected 200, got $($response.StatusCode)"
    Assert-True ($response.Content -match 'lang="fa"') "html lang is not fa"
    Assert-True ($response.Content -match 'dir="rtl"') "html dir is not rtl"
}

Check "unknown backend route returns standard error envelope" {
    $client = New-Object System.Net.Http.HttpClient
    $client.Timeout = [TimeSpan]::FromSeconds(10)
    try {
        $response = $client.GetAsync("$backendUrl/definitely-not-a-route").GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        $bodyText = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    }
    finally {
        $client.Dispose()
    }
    Assert-True ($status -eq 404) "expected 404, got $status"
    Assert-True ($null -ne $bodyText -and $bodyText -ne "") "no response body captured"
    $body = $bodyText | ConvertFrom-Json
    Assert-True ($body.code -eq "RESOURCE_NOT_FOUND") "error code is not RESOURCE_NOT_FOUND"
    Assert-True ($null -ne $body.trace_id -and $body.trace_id -ne "") "trace_id missing"
}

Check "supplied X-Request-ID is echoed" {
    $response = Invoke-WebRequest -Uri "$backendUrl/healthz" -Headers @{ "X-Request-ID" = "smoke-test-echo" } -UseBasicParsing -TimeoutSec 10
    Assert-True ($response.Headers["X-Request-ID"] -eq "smoke-test-echo") "X-Request-ID was not echoed"
}

Check "missing X-Request-ID gets generated" {
    $response = Invoke-WebRequest -Uri "$backendUrl/healthz" -UseBasicParsing -TimeoutSec 10
    $value = $response.Headers["X-Request-ID"]
    Assert-True ($null -ne $value -and $value -ne "") "X-Request-ID missing"
    Assert-True ($value -match "^[0-9a-fA-F-]{36}$") "generated X-Request-ID is not a UUID"
}

# --- Auth checks (Phase 2) ---

$script:adminEmail = Get-EnvValue (Join-Path $repoRoot "backend\.env") "INITIAL_ADMIN_EMAIL"
$script:adminPassword = Get-EnvValue (Join-Path $repoRoot "backend\.env") "INITIAL_ADMIN_PASSWORD"

Check "backend login returns token pair without leaking secrets" {
    Assert-True ($null -ne $script:adminEmail -and $null -ne $script:adminPassword) "INITIAL_ADMIN_* not configured in backend\.env"
    $payload = @{ email = $script:adminEmail; password = $script:adminPassword } | ConvertTo-Json
    $response = Invoke-WebRequest -Uri "$backendUrl/auth/login" -Method POST -Body $payload -ContentType "application/json" -UseBasicParsing -TimeoutSec 15
    Assert-True ($response.StatusCode -eq 200) "expected 200, got $($response.StatusCode)"
    $body = $response.Content | ConvertFrom-Json
    Assert-True ($null -ne $body.access_token -and $body.access_token -ne "") "access_token missing"
    Assert-True ($null -ne $body.refresh_token -and $body.refresh_token -ne "") "refresh_token missing"
    Assert-True ($body.roles -contains "SuperAdmin") "admin lacks SuperAdmin role"
    Assert-True ($response.Content -notmatch $script:adminPassword) "password leaked in login response"
}

Check "wrong password is rejected generically" {
    $payload = @{ email = $script:adminEmail; password = "definitely-wrong-1" } | ConvertTo-Json
    $client = New-Object System.Net.Http.HttpClient
    $client.Timeout = [TimeSpan]::FromSeconds(15)
    try {
        $content = New-Object System.Net.Http.StringContent($payload, [System.Text.Encoding]::UTF8, "application/json")
        $httpResponse = $client.PostAsync("$backendUrl/auth/login", $content).GetAwaiter().GetResult()
        $status = [int]$httpResponse.StatusCode
        $bodyText = $httpResponse.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    }
    finally {
        $client.Dispose()
    }
    Assert-True ($status -eq 401) "expected 401, got $status"
    $body = $bodyText | ConvertFrom-Json
    Assert-True ($body.code -eq "AUTHENTICATION_REQUIRED") "error code is not AUTHENTICATION_REQUIRED"
}

Check "admin endpoint denies unauthenticated request with 401" {
    $client = New-Object System.Net.Http.HttpClient
    $client.Timeout = [TimeSpan]::FromSeconds(10)
    try {
        $response = $client.GetAsync("$backendUrl/users").GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
    }
    finally {
        $client.Dispose()
    }
    Assert-True ($status -eq 401) "expected 401, got $status"
}

Write-Host ""
if ($failures.Count -gt 0) {
    Write-Host "SMOKE TEST FAILED: $($failures.Count) check(s) failed:" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "SMOKE TEST PASSED: all checks green." -ForegroundColor Green
exit 0
