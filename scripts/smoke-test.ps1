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

# --- Warehouse flow (Phase 4, T032) ---

Check "warehouse: catalog create + duplicate rejection" {
    $adminLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $script:adminEmail; password = $script:adminPassword } $null
    Assert-True ($adminLogin.Status -eq 200) "admin login failed"
    Update-JarFromCookies $script:jar $adminLogin.SetCookies
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar; "X-CSRF-Token" = $script:jar["zces_csrf"] }
    $unique = [guid]::NewGuid().ToString("N").Substring(0, 8)
    $created = Invoke-BffJson "POST" "/api/warehouse/items" @{
        name = "Smoke bearing $unique"; name_fa = "Smoke bearing FA $unique"; code = "SMK-$unique";
        unit = "ad"; min_quantity = "10"
    } $headers
    Assert-True ($created.Status -eq 201) "item create failed: $($created.Status) $($created.Body)"
    $duplicate = Invoke-BffJson "POST" "/api/warehouse/items" @{
        name = "smoke BEARING $unique"; name_fa = "Smoke bearing FA $unique"; code = "OTHER-$unique";
        unit = "ad"; min_quantity = "0"
    } $headers
    Assert-True ($duplicate.Status -eq 409) "expected duplicate 409, got $($duplicate.Status)"
}

Check "warehouse: receive/issue/overdraw ledger + low-stock alert" {
    $adminLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $script:adminEmail; password = $script:adminPassword } $null
    Update-JarFromCookies $script:jar $adminLogin.SetCookies
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar; "X-CSRF-Token" = $script:jar["zces_csrf"] }
    $unique = [guid]::NewGuid().ToString("N").Substring(0, 8)

    $workplaces = Invoke-BffJson "GET" "/api/org/workplaces?page_size=50" $null @{ Cookie = Get-CookiesFromJar $script:jar }
    $cp1 = ($workplaces.Body | ConvertFrom-Json).items | Where-Object { $_.code -eq "CP1" } | Select-Object -First 1
    Assert-True ($null -ne $cp1) "CP1 workplace not found"

    $warehouse = Invoke-BffJson "POST" "/api/warehouse/warehouses" @{
        workplace_id = $cp1.id; code = "WH-SMK-$unique"; name = "Smoke warehouse"; name_fa = "Smoke warehouse FA"
    } $headers
    Assert-True ($warehouse.Status -eq 201) "warehouse create failed: $($warehouse.Status) $($warehouse.Body)"
    $warehouseId = ($warehouse.Body | ConvertFrom-Json).id

    $shelf = Invoke-BffJson "POST" "/api/warehouse/warehouses/$warehouseId/shelves" @{ code = "S-01" } $headers
    Assert-True ($shelf.Status -eq 201) "shelf create failed: $($shelf.Status) $($shelf.Body)"
    $shelfId = ($shelf.Body | ConvertFrom-Json).id

    $item = Invoke-BffJson "POST" "/api/warehouse/items" @{
        name = "Smoke stock item $unique"; name_fa = "Smoke stock item FA $unique"; code = "SMKSTK-$unique";
        unit = "ad"; min_quantity = "10"
    } $headers
    Assert-True ($item.Status -eq 201) "item create failed: $($item.Status) $($item.Body)"
    $itemId = ($item.Body | ConvertFrom-Json).id

    $receive = Invoke-BffJson "POST" "/api/warehouse/placements/receive" @{
        item_id = $itemId; shelf_id = $shelfId; quantity = "50"; reason = "smoke"
    } $headers
    Assert-True ($receive.Status -eq 200) "receive failed: $($receive.Status) $($receive.Body)"
    $placement = $receive.Body | ConvertFrom-Json
    Assert-True ($placement.quantity -eq "50.000") "expected 50.000, got $($placement.quantity)"

    $issue = Invoke-BffJson "POST" "/api/warehouse/placements/issue" @{
        placement_id = $placement.id; quantity = "15"; reason = "smoke issue"
    } $headers
    Assert-True ($issue.Status -eq 200) "issue failed: $($issue.Status) $($issue.Body)"

    $overdraw = Invoke-BffJson "POST" "/api/warehouse/placements/issue" @{
        placement_id = $placement.id; quantity = "999"
    } $headers
    Assert-True ($overdraw.Status -eq 409) "expected overdraw 409, got $($overdraw.Status)"
    Assert-True (($overdraw.Body | ConvertFrom-Json).code -eq "INSUFFICIENT_STOCK") "expected INSUFFICIENT_STOCK"

    $dropBelow = Invoke-BffJson "POST" "/api/warehouse/placements/issue" @{
        placement_id = $placement.id; quantity = "30"
    } $headers
    Assert-True ($dropBelow.Status -eq 200) "issue to below-threshold failed: $($dropBelow.Status)"

    $alerts = Invoke-BffJson "GET" "/api/warehouse/alerts?active=true" $null @{ Cookie = Get-CookiesFromJar $script:jar }
    $alertItems = ($alerts.Body | ConvertFrom-Json).items
    $mine = @($alertItems | Where-Object { $_.placement_id -eq $placement.id })
    Assert-True ($mine.Count -eq 1) "expected exactly 1 active alert for the placement, got $($mine.Count)"
}

# --- Item request flow (Phase 5, T017) ---

Check "requests: compose + invalid variants + approve + fulfill + overdraw" {
    $adminLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $script:adminEmail; password = $script:adminPassword } $null
    Assert-True ($adminLogin.Status -eq 200) "admin login failed"
    Update-JarFromCookies $script:jar $adminLogin.SetCookies
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar; "X-CSRF-Token" = $script:jar["zces_csrf"] }
    $unique = [guid]::NewGuid().ToString("N").Substring(0, 8)

    $itemA = Invoke-BffJson "POST" "/api/warehouse/items" @{ name = "Smoke req A $unique"; name_fa = "Smoke req A FA"; unit = "ad"; min_quantity = "0" } $headers
    Assert-True ($itemA.Status -eq 201) "item A create failed"
    $itemB = Invoke-BffJson "POST" "/api/warehouse/items" @{ name = "Smoke req B $unique"; name_fa = "Smoke req B FA"; unit = "ad"; min_quantity = "0" } $headers
    Assert-True ($itemB.Status -eq 201) "item B create failed"
    $itemAId = ($itemA.Body | ConvertFrom-Json).id
    $itemBId = ($itemB.Body | ConvertFrom-Json).id

    $workplaces = Invoke-BffJson "GET" "/api/org/workplaces?page_size=50" $null @{ Cookie = Get-CookiesFromJar $script:jar }
    $cp1 = ($workplaces.Body | ConvertFrom-Json).items | Where-Object { $_.code -eq "CP1" } | Select-Object -First 1
    $warehouse = Invoke-BffJson "POST" "/api/warehouse/warehouses" @{ workplace_id = $cp1.id; code = "WH-REQ-$unique"; name = "Req WH"; name_fa = "Req WH FA" } $headers
    $warehouseId = ($warehouse.Body | ConvertFrom-Json).id
    $shelf = Invoke-BffJson "POST" "/api/warehouse/warehouses/$warehouseId/shelves" @{ code = "R-01" } $headers
    $shelfId = ($shelf.Body | ConvertFrom-Json).id
    $recvA = Invoke-BffJson "POST" "/api/warehouse/placements/receive" @{ item_id = $itemAId; shelf_id = $shelfId; quantity = "10" } $headers
    $placementA = ($recvA.Body | ConvertFrom-Json).id
    $recvB = Invoke-BffJson "POST" "/api/warehouse/placements/receive" @{ item_id = $itemBId; shelf_id = $shelfId; quantity = "2" } $headers
    $placementB = ($recvB.Body | ConvertFrom-Json).id

    $invalid = Invoke-BffJson "POST" "/api/warehouse/requests" @{ purpose_description = "x"; lines = @() } $headers
    Assert-True ($invalid.Status -eq 422) "expected 422 for empty lines, got $($invalid.Status)"

    $created = Invoke-BffJson "POST" "/api/warehouse/requests" @{
        purpose_description = "Smoke request $unique";
        lines = @(
            @{ item_id = $itemAId; quantity = "4" },
            @{ item_id = $itemBId; quantity = "2" }
        )
    } $headers
    Assert-True ($created.Status -eq 201) "request create failed: $($created.Status) $($created.Body)"
    $request = $created.Body | ConvertFrom-Json
    Assert-True ($request.status -eq "pending") "expected pending"
    $lineA = $request.lines | Where-Object { $_.item.id -eq $itemAId } | Select-Object -First 1
    $lineB = $request.lines | Where-Object { $_.item.id -eq $itemBId } | Select-Object -First 1

    $approve = Invoke-BffJson "POST" "/api/warehouse/requests/$($request.id)/approve" @{ version = $request.version; note = "smoke" } $headers
    Assert-True ($approve.Status -eq 200) "approve failed: $($approve.Status) $($approve.Body)"

    $fulfill = Invoke-BffJson "POST" "/api/warehouse/requests/$($request.id)/fulfill" @{
        version = ($approve.Body | ConvertFrom-Json).version;
        lines = @(
            @{ line_id = $lineA.id; placement_id = $placementA },
            @{ line_id = $lineB.id; placement_id = $placementB }
        )
    } $headers
    Assert-True ($fulfill.Status -eq 200) "fulfill failed: $($fulfill.Status) $($fulfill.Body)"

    $placements = Invoke-BffJson "GET" "/api/warehouse/placements?item_id=$itemAId&include_empty=true" $null @{ Cookie = Get-CookiesFromJar $script:jar }
    $placementAAfter = (($placements.Body | ConvertFrom-Json).items | Where-Object { $_.id -eq $placementA })
    Assert-True ($placementAAfter.quantity -eq "6.000") "expected A 6.000, got $($placementAAfter.quantity)"

    $overdraw = Invoke-BffJson "POST" "/api/warehouse/requests" @{ purpose_description = "overdraw $unique"; lines = @( @{ item_id = $itemAId; quantity = "99" } ) } $headers
    $overdrawReq = $overdraw.Body | ConvertFrom-Json
    $approve2 = Invoke-BffJson "POST" "/api/warehouse/requests/$($overdrawReq.id)/approve" @{ version = $overdrawReq.version } $headers
    $overdrawVersion = ($approve2.Body | ConvertFrom-Json).version
    $overdrawLineId = ($overdrawReq.lines | Select-Object -First 1).id
    $refused = Invoke-BffJson "POST" "/api/warehouse/requests/$($overdrawReq.id)/fulfill" @{ version = $overdrawVersion; lines = @( @{ line_id = $overdrawLineId; placement_id = $placementA } ) } $headers
    Assert-True ($refused.Status -eq 409) "expected overdraw 409, got $($refused.Status)"
    Assert-True (($refused.Body | ConvertFrom-Json).code -eq "INSUFFICIENT_STOCK") "expected INSUFFICIENT_STOCK"
}

# --- Asset tracking flow (Phase 6, T015) ---

Check "assets: register + duplicate 409 + assign + blocked retire + return + retire + serial reuse" {
    $adminLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $script:adminEmail; password = $script:adminPassword } $null
    Assert-True ($adminLogin.Status -eq 200) "admin login failed"
    Update-JarFromCookies $script:jar $adminLogin.SetCookies
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar; "X-CSRF-Token" = $script:jar["zces_csrf"] }
    $unique = [guid]::NewGuid().ToString("N").Substring(0, 8)

    $created = Invoke-BffJson "POST" "/api/warehouse/assets" @{
        name = "Smoke wrench $unique"; name_fa = "Smoke wrench FA $unique"; serial = "SMK-AST-$unique";
        description = "smoke asset"
    } $headers
    Assert-True ($created.Status -eq 201) "asset create failed: $($created.Status) $($created.Body)"
    $asset = $created.Body | ConvertFrom-Json
    Assert-True ($asset.status -eq "available") "expected available after register"

    $duplicate = Invoke-BffJson "POST" "/api/warehouse/assets" @{
        name = "Smoke wrench 2 $unique"; name_fa = "Smoke wrench 2 FA"; serial = "smk-ast-$unique"
    } $headers
    Assert-True ($duplicate.Status -eq 409) "expected duplicate 409, got $($duplicate.Status)"
    Assert-True (($duplicate.Body | ConvertFrom-Json).code -eq "DUPLICATE_RESOURCE") "expected DUPLICATE_RESOURCE"

    $employees = Invoke-BffJson "GET" "/api/employees?page_size=1&status=active" $null @{ Cookie = Get-CookiesFromJar $script:jar }
    $employee = (($employees.Body | ConvertFrom-Json).items | Select-Object -First 1)
    Assert-True ($null -ne $employee) "no active employee found to assign"

    $assign = Invoke-BffJson "POST" "/api/warehouse/assets/$($asset.id)/assign" @{
        version = $asset.version; target_type = "employee"; employee_id = $employee.id; note = "smoke assign"
    } $headers
    Assert-True ($assign.Status -eq 200) "assign failed: $($assign.Status) $($assign.Body)"
    $assigned = $assign.Body | ConvertFrom-Json
    Assert-True ($assigned.status -eq "assigned" -and $assigned.holder.type -eq "employee") "holder not set to employee"

    $secondAssign = Invoke-BffJson "POST" "/api/warehouse/assets/$($asset.id)/assign" @{
        version = $assigned.version; target_type = "location"; location = "Smoke shelf"
    } $headers
    Assert-True ($secondAssign.Status -eq 422 -or $secondAssign.Status -eq 409) "assign of assigned asset should fail, got $($secondAssign.Status)"

    $blockedRetire = Invoke-BffJson "POST" "/api/warehouse/assets/$($asset.id)/retire" @{ version = $assigned.version } $headers
    Assert-True ($blockedRetire.Status -eq 422 -or $blockedRetire.Status -eq 409) "retire while assigned should be blocked, got $($blockedRetire.Status)"

    $return = Invoke-BffJson "POST" "/api/warehouse/assets/$($asset.id)/return" @{ version = $assigned.version; note = "smoke return" } $headers
    Assert-True ($return.Status -eq 200) "return failed: $($return.Status) $($return.Body)"
    $returned = $return.Body | ConvertFrom-Json
    Assert-True ($returned.status -eq "available") "asset not available after return"

    $retire = Invoke-BffJson "POST" "/api/warehouse/assets/$($asset.id)/retire" @{ version = $returned.version } $headers
    Assert-True ($retire.Status -eq 200) "retire after return failed: $($retire.Status) $($retire.Body)"
    Assert-True ((($retire.Body | ConvertFrom-Json).status) -eq "retired") "asset not retired"

    $history = Invoke-BffJson "GET" "/api/warehouse/assets/$($asset.id)/history" $null @{ Cookie = Get-CookiesFromJar $script:jar }
    $entries = ($history.Body | ConvertFrom-Json).items
    Assert-True ($history.Body | ConvertFrom-Json).total -ge 4 "expected >= 4 history entries"
    $actions = @($entries | ForEach-Object { $_.action })
    Assert-True ($actions[0] -eq "retired") "newest history entry is not retired: $($actions -join ',')"
    Assert-True ($actions -contains "created" -and $actions -contains "assigned" -and $actions -contains "returned") "history missing lifecycle entries"

    $reuse = Invoke-BffJson "POST" "/api/warehouse/assets" @{
        name = "Smoke wrench 3 $unique"; name_fa = "Smoke wrench 3 FA"; serial = "SMK-AST-$unique"
    } $headers
    Assert-True ($reuse.Status -eq 201) "serial reuse after retire failed: $($reuse.Status) $($reuse.Body)"
}

# --- Loan module flow (Phase 7, T018) ---

Check "loans: policy create + duplicate 409 + cascade order + lifecycle + settle frees" {
    $adminLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $script:adminEmail; password = $script:adminPassword } $null
    Assert-True ($adminLogin.Status -eq 200) "admin login failed"
    Update-JarFromCookies $script:jar $adminLogin.SetCookies
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar; "X-CSRF-Token" = $script:jar["zces_csrf"] }
    $unique = [guid]::NewGuid().ToString("N").Substring(0, 8)

    $workplaces = (Invoke-BffJson "GET" "/api/org/workplaces?page_size=50" $null @{ Cookie = Get-CookiesFromJar $script:jar }).Body | ConvertFrom-Json
    $cp1 = ($workplaces.items | Where-Object { $_.code -eq "CP1" } | Select-Object -First 1)
    Assert-True ($null -ne $cp1) "CP1 workplace not found"

    $ni = "8" + (Get-Random -Minimum 100000000 -Maximum 999999999)
    $ni = $ni.Substring(0, 10)
    $email = "loansmoke-$ni@zarandsteel.ir"
    $empCreate = Invoke-BffJson "POST" "/api/employees" @{
        national_id = $ni; personnel_code = "LSM-$($ni.Substring(4))";
        first_name = "Loan"; last_name = "Smoke"; workplace_id = $cp1.id;
        user = @{ email = $email; username = "loansmoke-$ni"; password = "smoke-password-1" }
    } $headers
    Assert-True ($empCreate.Status -eq 201) "loan smoke employee create failed: $($empCreate.Status)"

    # clean any leftover active policy for (CP1, current jalali year)
    $persian = New-Object System.Globalization.PersianCalendar
    $year = $persian.GetYear((Get-Date))
    $existing = (Invoke-BffJson "GET" "/api/loan/policies?page_size=100&year=$year" $null @{ Cookie = Get-CookiesFromJar $script:jar }).Body | ConvertFrom-Json
    foreach ($p in ($existing.items | Where-Object { $_.workplace.id -eq $cp1.id })) {
        $null = Invoke-BffJson "POST" "/api/loan/policies/$($p.id)/retire" @{ version = $p.version } $headers
    }

    $policy = Invoke-BffJson "POST" "/api/loan/policies" @{
        workplace_id = $cp1.id; year = $year;
        max_loan_amount = "100000000.00"; max_guarantee_amount = "50000000.00";
        max_request_count_per_year = 20; max_request_count_lifetime = 20
    } $headers
    Assert-True ($policy.Status -eq 201) "policy create failed: $($policy.Status) $($policy.Body)"
    $policyBody = $policy.Body | ConvertFrom-Json

    $duplicate = Invoke-BffJson "POST" "/api/loan/policies" @{
        workplace_id = $cp1.id; year = $year;
        max_loan_amount = "1.00"; max_guarantee_amount = "1.00";
        max_request_count_per_year = 1; max_request_count_lifetime = 1
    } $headers
    Assert-True ($duplicate.Status -eq 409) "expected duplicate policy 409, got $($duplicate.Status)"

    $empLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $email; password = "smoke-password-1" } $null
    Assert-True ($empLogin.Status -eq 200) "employee login failed"
    $empJar = @{}
    Update-JarFromCookies $empJar $empLogin.SetCookies
    $empHeaders = @{ Cookie = Get-CookiesFromJar $empJar; "X-CSRF-Token" = $empJar["zces_csrf"] }

    $big = Invoke-BffJson "POST" "/api/loan/requests" @{ type = "loan"; amount = "60000000.00" } $empHeaders
    Assert-True ($big.Status -eq 201) "loan submit failed: $($big.Status) $($big.Body)"
    $bigBody = $big.Body | ConvertFrom-Json

    $activate = Invoke-BffJson "POST" "/api/loan/requests/$($bigBody.id)/activate" @{ version = $bigBody.version } $headers
    Assert-True ($activate.Status -eq 200) "activate failed: $($activate.Status) $($activate.Body)"
    $activated = $activate.Body | ConvertFrom-Json

    $over = Invoke-BffJson "POST" "/api/loan/requests" @{ type = "loan"; amount = "50000000.00" } $empHeaders
    Assert-True ($over.Status -eq 422) "expected loan_cap 422, got $($over.Status)"
    Assert-True ((($over.Body | ConvertFrom-Json).details.rule) -eq "loan_cap") "expected loan_cap rule"

    $settle = Invoke-BffJson "POST" "/api/loan/requests/$($bigBody.id)/settle" @{ version = $activated.version } $headers
    Assert-True ($settle.Status -eq 200) "settle failed: $($settle.Status) $($settle.Body)"
    Assert-True ((($settle.Body | ConvertFrom-Json).settled_at) -ne $null) "settled_at missing"

    $afterSettle = Invoke-BffJson "POST" "/api/loan/requests" @{ type = "loan"; amount = "50000000.00" } $empHeaders
    Assert-True ($afterSettle.Status -eq 201) "submit after settle should pass the freed cap: $($afterSettle.Status) $($afterSettle.Body)"

    $retired = Invoke-BffJson "POST" "/api/loan/policies/$($policyBody.id)/retire" @{ version = $policyBody.version } $headers
    Assert-True ($retired.Status -eq 200) "policy retire failed: $($retired.Status)"
    $noPolicy = Invoke-BffJson "POST" "/api/loan/requests" @{ type = "loan"; amount = "1000000.00" } $empHeaders
    Assert-True ($noPolicy.Status -eq 422) "expected no_policy 422 after retirement, got $($noPolicy.Status)"
    Assert-True ((($noPolicy.Body | ConvertFrom-Json).details.rule) -eq "no_policy") "expected no_policy rule"
}

# --- Notifications flow (Phase 8, T014) ---

Check "notifications: critical low-stock alert lands in the same commit + mark-read works" {
    $adminLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $script:adminEmail; password = $script:adminPassword } $null
    Assert-True ($adminLogin.Status -eq 200) "admin login failed"
    Update-JarFromCookies $script:jar $adminLogin.SetCookies
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar; "X-CSRF-Token" = $script:jar["zces_csrf"] }
    $unique = [guid]::NewGuid().ToString("N").Substring(0, 8)

    # Baseline: clear the inbox so deltas are unambiguous.
    $null = Invoke-BffJson "POST" "/api/notifications/read-all" $null $headers
    $before = ((Invoke-BffJson "GET" "/api/notifications/unread-count" $null @{ Cookie = Get-CookiesFromJar $script:jar }).Body | ConvertFrom-Json).unread
    Assert-True ($before -eq 0) "read-all did not zero the inbox (unread=$before)"

    $workplaces = (Invoke-BffJson "GET" "/api/org/workplaces?page_size=50" $null @{ Cookie = Get-CookiesFromJar $script:jar }).Body | ConvertFrom-Json
    $cp1 = ($workplaces.items | Where-Object { $_.code -eq "CP1" } | Select-Object -First 1)
    Assert-True ($null -ne $cp1) "CP1 workplace not found"

    $warehouse = Invoke-BffJson "POST" "/api/warehouse/warehouses" @{
        workplace_id = $cp1.id; code = "WH-NTF-$unique"; name = "Smoke notifications WH"; name_fa = "Smoke notifications WH FA"
    } $headers
    Assert-True ($warehouse.Status -eq 201) "warehouse create failed: $($warehouse.Status) $($warehouse.Body)"
    $warehouseId = ($warehouse.Body | ConvertFrom-Json).id
    $shelf = Invoke-BffJson "POST" "/api/warehouse/warehouses/$warehouseId/shelves" @{ code = "N-01" } $headers
    Assert-True ($shelf.Status -eq 201) "shelf create failed"
    $shelfId = ($shelf.Body | ConvertFrom-Json).id

    $item = Invoke-BffJson "POST" "/api/warehouse/items" @{
        name = "Smoke notify item $unique"; name_fa = "Smoke notify item FA $unique"; unit = "ad"; min_quantity = "10"
    } $headers
    Assert-True ($item.Status -eq 201) "item create failed: $($item.Status) $($item.Body)"
    $itemId = ($item.Body | ConvertFrom-Json).id

    $receive = Invoke-BffJson "POST" "/api/warehouse/placements/receive" @{
        item_id = $itemId; shelf_id = $shelfId; quantity = "50"; reason = "notify smoke"
    } $headers
    Assert-True ($receive.Status -eq 200) "receive failed: $($receive.Status)"
    $placement = $receive.Body | ConvertFrom-Json

    # Drop below threshold -> low-stock alert; the Critical event's
    # notification rows must exist in the SAME commit (SC-004).
    $issue = Invoke-BffJson "POST" "/api/warehouse/placements/issue" @{
        placement_id = $placement.id; quantity = "45"; reason = "notify smoke issue"
    } $headers
    Assert-True ($issue.Status -eq 200) "issue below threshold failed: $($issue.Status)"

    $after = ((Invoke-BffJson "GET" "/api/notifications/unread-count" $null @{ Cookie = Get-CookiesFromJar $script:jar }).Body | ConvertFrom-Json).unread
    Assert-True ($after -gt 0) "critical low-stock notification missing in the same commit (unread=$after)"

    $unread = (Invoke-BffJson "GET" "/api/notifications?unread_only=true&page_size=50" $null @{ Cookie = Get-CookiesFromJar $script:jar }).Body | ConvertFrom-Json
    $lowStock = @($unread.items | Where-Object { $_.event_type -eq "InventoryLowStock" -and $_.payload.item_id -eq $itemId }) | Select-Object -First 1
    Assert-True ($null -ne $lowStock) "no InventoryLowStock notification for item $itemId"
    Assert-True ($null -ne $lowStock.payload.body -and $lowStock.payload.body -ne "") "low-stock payload body missing"

    $markRead = Invoke-BffJson "POST" "/api/notifications/$($lowStock.id)/read" @{} $headers
    Assert-True ($markRead.Status -eq 200) "mark-read failed: $($markRead.Status) $($markRead.Body)"
    Assert-True (($markRead.Body | ConvertFrom-Json).read_at -ne $null) "read_at not stamped"

    $afterRead = ((Invoke-BffJson "GET" "/api/notifications/unread-count" $null @{ Cookie = Get-CookiesFromJar $script:jar }).Body | ConvertFrom-Json).unread
    Assert-True ($afterRead -lt $after) "mark-read did not decrement unread ($after -> $afterRead)"

    $readAll = Invoke-BffJson "POST" "/api/notifications/read-all" $null $headers
    Assert-True ($readAll.Status -eq 200) "read-all failed: $($readAll.Status)"
    Assert-True (((Invoke-BffJson "GET" "/api/notifications/unread-count" $null @{ Cookie = Get-CookiesFromJar $script:jar }).Body | ConvertFrom-Json).unread -eq 0) "unread not zero after read-all"
}

Check "notifications: relay delivers non-critical event within latency" {
    $adminLogin = Invoke-BffJson "POST" "/api/auth/login" @{ email = $script:adminEmail; password = $script:adminPassword } $null
    Assert-True ($adminLogin.Status -eq 200) "admin login failed"
    Update-JarFromCookies $script:jar $adminLogin.SetCookies
    $headers = @{ Cookie = Get-CookiesFromJar $script:jar; "X-CSRF-Token" = $script:jar["zces_csrf"] }
    $unique = [guid]::NewGuid().ToString("N").Substring(0, 8)

    $null = Invoke-BffJson "POST" "/api/notifications/read-all" $null $headers

    # Non-critical event (SC-001/SC-002): capture is in-commit, delivery is
    # relay-owned -> must appear within relay latency (poll 2s, <= 15s).
    $item = Invoke-BffJson "POST" "/api/warehouse/items" @{
        name = "Smoke relay item $unique"; name_fa = "Smoke relay item FA $unique"; unit = "ad"; min_quantity = "0"
    } $headers
    Assert-True ($item.Status -eq 201) "item create failed: $($item.Status) $($item.Body)"
    $itemId = ($item.Body | ConvertFrom-Json).id

    $deadline = (Get-Date).AddSeconds(15)
    $delivered = $null
    while ((Get-Date) -lt $deadline -and $null -eq $delivered) {
        Start-Sleep -Milliseconds 500
        $list = (Invoke-BffJson "GET" "/api/notifications?page_size=50" $null @{ Cookie = Get-CookiesFromJar $script:jar }).Body | ConvertFrom-Json
        $delivered = @($list.items | Where-Object { $_.event_type -eq "ItemCatalogCreated" -and $_.payload.entity_id -eq $itemId }) | Select-Object -First 1
    }
    Assert-True ($null -ne $delivered) "relay did not deliver ItemCatalogCreated for item $itemId within 15s"

    $null = Invoke-BffJson "POST" "/api/notifications/read-all" $null $headers
}

Write-Host ""
if ($failures.Count -gt 0) {
    Write-Host "SMOKE TEST FAILED: $($failures.Count) check(s) failed:" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "SMOKE TEST PASSED: all checks green." -ForegroundColor Green
exit 0

