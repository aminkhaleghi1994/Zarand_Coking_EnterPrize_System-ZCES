# ZCES UI smoke test: guards against "page not hydrated" regressions
# (login leaking credentials into the URL, dead dark-mode toggle) using
# headless Chrome via puppeteer-core.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\smoke-ui.ps1
# Env:    SMOKE_FRONTEND_URL (default http://127.0.0.1:3000), CHROME_PATH
# Needs:  frontend dev server + backend running.
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
node (Join-Path $repoRoot "frontend\scripts\smoke-ui.mjs")
exit $LASTEXITCODE
