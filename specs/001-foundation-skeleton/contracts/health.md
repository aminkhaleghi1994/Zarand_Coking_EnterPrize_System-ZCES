# Contract: Health Endpoint

**Scope**: Phase 1 platform · Owner: backend core · Consumers: humans, BFF proxy, CI smoke tests

## `GET /healthz` (also mounted under `{API_V1_PREFIX}/healthz`)

### Request

- Method: `GET`
- Headers: none required; `X-Request-ID` honored (see [error-envelope.md](./error-envelope.md)
  propagation rules)

### Response `200 OK` (liveness success — always 200 while the app is up)

```json
{
  "status": "ok",
  "app": "ZCES",
  "env": "development",
  "version": "0.1.0",
  "components": {
    "database": { "status": "up", "latency_ms": 3 }
  }
}
```

### Rules

1. Liveness vs readiness: HTTP is `200` whenever the application process is alive,
   even if a component is down (FR-001). Component health is conveyed in the body.
2. `components.database.status` is `"up"` after a successful `SELECT 1` (with a
   2-second timeout) or `"down"` on any failure; `latency_ms` present only when `"up"`.
3. No secrets, connection strings, or host names appear in the response.
4. Response header `X-Request-ID` echoes/establishes the trace id.
5. Version is read from application configuration (`APP_VERSION`), not build-time magic.

### BFF projection

`GET {FRONTEND}/api/health` returns the same JSON on success. On backend failure it
returns HTTP 502 with the standard error envelope (code `INTERNAL_ERROR`) — the browser
never sees a raw network error.
