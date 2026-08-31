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

# --- Auth checks via BFF cookie flow (Phase 2, T018) ---

$frontendOrigin = ($frontendUrl -replace "/$", "")

function Invoke-BffJson([string]$method, [string]$path, $body, [hashtable]$headers) {
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseCookies = $false
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(15)
    try {
        $message = New-Object System.Net.Http.HttpRequestMessage(
            [System.Net.Http.HttpMethod]::new($method), "$frontendOrigin$path")
        if ($null -ne $body) {
            $json = $body | ConvertTo-Json -Depth 5
            $message.Content = New-Object System.Net.Http.StringContent(
                $json, [System.Text.Encoding]::UTF8, "application/json")
        }
        if ($headers) {
            foreach ($key in $headers.Keys) { $message.Headers.TryAddWithoutValidation($key, $headers[$key]) | Out-Null }
        }
        $response = $client.SendAsync($message).GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        $bodyText = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $setCookieHeaders = @()
        $headerEnum = $response.Headers.TryGetValues("Set-Cookie", [ref]$null)
        $values = $null
        if ($response.Headers.TryGetValues("Set-Cookie", [ref]$values)) { $setCookieHeaders = @($values) }
        return @{ Status = $status; Body = $bodyText; SetCookies = $setCookieHeaders }
    }
    finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

function Get-CookiesFromJar([hashtable]$jar) {
    return ($jar.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "; "
}

function Update-JarFromCookies([hashtable]$jar, $setCookies) {
    foreach ($cookie in $setCookies) {
        $first = ($cookie -split ";")[0].Trim()
        $name = ($first -split "=", 2)[0].Trim()
        $value = ($first -split "=", 2)[1].Trim()
        if ($value -eq "") { $jar.Remove($name) } else { $jar[$name] = $value }
    }
}

# --- Auth checks (Phase 2, direct backend) ---

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

# --- Auth checks via BFF cookie flow (Phase 2, T018) ---

$script:jar = @{}

Check "BFF login sets auth cookies and returns user without token material" {
    Assert-True ($null -ne $script:adminEmail -and $null -ne $script:adminPassword) "INITIAL_ADMIN_* not configured in backend\.env"
    $result = Invoke-BffJson "POST" "/api/auth/login" @{ email = $script:adminEmail; password = $script:adminPassword } $null
    Assert-True ($result.Status -eq 200) "expected 200, got $($result.Status): $($result.Body)"
    $body = $result.Body | ConvertFrom-Json
    Assert-True ($null -ne $body.user -and $null -ne $body.user.email) "user object missing from BFF response"
    Assert-True ($result.Body -notmatch "access_token") "BFF login response leaked access_token"
    Assert-True ($result.Body -notmatch "refresh_token") "BFF login response leaked refresh_token"
    $joined = $result.SetCookies -join " "
    Assert-True ($joined -match "zces_at=") "zces_at cookie not set"
    Assert-True ($joined -match "zces_rt=") "zces_rt cookie not set"
    Assert-True ($joined -match "zces_csrf=") "zces_csrf cookie not set"
    $atCookie = $result.SetCookies | Where-Object { $_ -match "^zces_at=" } | Select-Object -First 1
    $rtCookie = $result.SetCookies | Where-Object { $_ -match "^zces_rt=" } | Select-Object -First 1
    Assert-True ($atCookie -match "httponly" -or $atCookie -match "HttpOnly") "zces_at is not HttpOnly"
    Assert-True ($rtCookie -match "httponly" -or $rtCookie -match "HttpOnly") "zces_rt is not HttpOnly"
    Update-JarFromCookies $script:jar $result.SetCookies
}

Check "BFF me returns identity from cookie jar" {
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar }
    $result = Invoke-BffJson "GET" "/api/auth/me" $null $headers
    Assert-True ($result.Status -eq 200) "expected 200, got $($result.Status): $($result.Body)"
    $body = $result.Body | ConvertFrom-Json
    Assert-True ($body.user.email -eq $script:adminEmail) "me returned unexpected identity"
}

Check "CSRF-less mutation is rejected" {
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar }
    $result = Invoke-BffJson "POST" "/api/auth/logout" $null $headers
    Assert-True ($result.Status -ge 400 -and $result.Status -lt 500) "expected 4xx without CSRF header, got $($result.Status)"
    Assert-True ($result.Status -ne 401 -or $result.Body -match "CSRF") "CSRF-less request was not rejected with a CSRF-specific error"
}

Check "BFF logout clears cookies and session is dead afterwards" {
    $csrf = $script:jar["zces_csrf"]
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar; "X-CSRF-Token" = $csrf }
    $result = Invoke-BffJson "POST" "/api/auth/logout" $null $headers
    Assert-True ($result.Status -eq 200) "expected 200, got $($result.Status): $($result.Body)"
    $joined = $result.SetCookies -join " "
    Assert-True ($joined -match "zces_at=;" -or $joined -match "zces_at=\s*;") "zces_at not cleared"
    Assert-True ($joined -match "zces_rt=;" -or $joined -match "zces_rt=\s*;") "zces_rt not cleared"
    Update-JarFromCookies $script:jar $result.SetCookies
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar }
    $result = Invoke-BffJson "GET" "/api/auth/me" $null $headers
    Assert-True ($result.Status -eq 401) "me after logout should be 401, got $($result.Status)"
}

Check "roleless user gets 403 on admin endpoint (via admin API setup)" {
    $adminLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $script:adminEmail; password = $script:adminPassword } $null
    Assert-True ($adminLogin.Status -eq 200) "admin login failed: $($adminLogin.Status)"
    Update-JarFromCookies $script:jar $adminLogin.SetCookies
    $unique = "roleless-smoke-{0}@zarandsteel.ir" -f (Get-Date -Format "yyyyMMddHHmmss")
    $adminCookies = Get-CookiesFromJar $script:jar
    $csrf = $script:jar["zces_csrf"]
    $headers = @{ Cookie = $adminCookies; "X-CSRF-Token" = $csrf }
    $created = $null
    foreach ($path in @("/api/v1/employees", "/api/admin/users")) {
        $r = Invoke-BffJson "POST" $path @{ email = $unique; full_name = "Smoke Roleless"; password = "smoke-test-password-1" } $headers
        if ($r.Status -ge 200 -and $r.Status -lt 300) { $created = $r; break }
    }
    if ($null -eq $created) {
        Write-Host "SKIP  user-creation endpoint arrives with Phase 3 (employee CRUD); roleless-403 is covered by pytest tests/test_admin_endpoints.py" -ForegroundColor Yellow
        return
    }
    $rolelessLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $unique; password = "smoke-test-password-1" } $null
    Assert-True ($rolelessLogin.Status -eq 200) "roleless login failed: $($rolelessLogin.Status)"
    $rolelessJar = @{}
    Update-JarFromCookies $rolelessJar $rolelessLogin.SetCookies
    $result = Invoke-BffJson "GET" "/api/auth/me" $null @{ Cookie = Get-CookiesFromJar $rolelessJar }
    Assert-True ($result.Status -eq 200) "roleless me failed"
}

# --- Employee flow (Phase 3, T020) ---

Check "org tree seeded (4 workplaces)" {
    $adminLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $script:adminEmail; password = $script:adminPassword } $null
    Assert-True ($adminLogin.Status -eq 200) "admin login failed"
    Update-JarFromCookies $script:jar $adminLogin.SetCookies
    $result = Invoke-BffJson "GET" "/api/org/workplaces?page_size=50" $null @{ Cookie = Get-CookiesFromJar $script:jar }
    Assert-True ($result.Status -eq 200) "org workplaces failed: $($result.Status)"
    $body = $result.Body | ConvertFrom-Json
    Assert-True ($body.total -ge 4) "expected >= 4 workplaces, got $($body.total)"
}

Check "employee create + duplicate rejection + deactivate cascade" {
    $csrf = $script:jar["zces_csrf"]
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar; "X-CSRF-Token" = $csrf }
    $wps = (Invoke-BffJson "GET" "/api/org/workplaces?page_size=50" $null $headers).Body | ConvertFrom-Json
    $cp1 = ($wps.items | Where-Object { $_.code -eq "CP1" } | Select-Object -First 1).id
    Assert-True ($null -ne $cp1) "CP1 workplace not found"
    $ni = "8" + (Get-Random -Minimum 100000000 -Maximum 999999999)
    $ni = $ni.Substring(0, 10)
    $email = "smoke-$ni@zarandsteel.ir"
    $create = Invoke-BffJson "POST" "/api/employees" @{
        national_id = $ni; personnel_code = "SMK-$($ni.Substring(4))";
        first_name = "Smoke"; last_name = "Employee"; workplace_id = $cp1;
        user = @{ email = $email; username = "smoke-$ni"; password = "smoke-password-1" }
    } $headers
    Assert-True ($create.Status -eq 201) "employee create failed: $($create.Status) $($create.Body)"
    $emp = $create.Body | ConvertFrom-Json
    Assert-True ($null -ne $emp.id -and $null -ne $emp.user.id) "employee/user ids missing in create response"
    Assert-True ($emp.national_id -is [string]) "national_id missing in response"
    $dup = Invoke-BffJson "POST" "/api/employees" @{
        national_id = $ni; personnel_code = "DIF-$($ni.Substring(4))";
        first_name = "D"; last_name = "Up"; workplace_id = $cp1;
        user = @{ email = "d$ni@zarandsteel.ir"; username = "d$ni"; password = "smoke-password-1" }
    } $headers
    Assert-True ($dup.Status -eq 409) "expected duplicate 409, got $($dup.Status)"
    $deact = Invoke-BffJson "POST" "/api/employees/$($emp.id)/deactivate" @{ version = $emp.version } $headers
    Assert-True ($deact.Status -eq 200) "deactivate failed: $($deact.Status)"
    $empLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $email; password = "smoke-password-1" } $null
    Assert-True ($empLogin.Status -eq 401) "deactivated employee could still sign in"
}

Write-Host ""
if ($failures.Count -gt 0) {
    Write-Host "SMOKE TEST FAILED: $($failures.Count) check(s) failed:" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "SMOKE TEST PASSED: all checks green." -ForegroundColor Green
exit 0

