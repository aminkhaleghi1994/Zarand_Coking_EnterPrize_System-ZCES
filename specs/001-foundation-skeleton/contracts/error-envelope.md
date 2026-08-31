# Contract: Standard Error Envelope

**Scope**: Every backend error response in every phase · Owner: backend core

## Shape

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": { "field_errors": [ { "field": "page", "issue": "must be >= 1" } ] },
  "trace_id": "5f0c1b6a-..."
}
```

- `code` — machine-readable, from the standard set (table below).
- `message` — human-readable summary; frontend maps `code` → localized text (shared
  error-code dictionary in the frontend mirrors this set).
- `details` — optional structured object; never contains secrets or sensitive field values.
- `trace_id` — the request's correlation id (same value as the `X-Request-ID` response header).

## Standard error codes (fixed set)

| Code | HTTP | Raised by |
|---|---|---|
| `VALIDATION_ERROR` | 422 | request body/query/header validation |
| `AUTHENTICATION_REQUIRED` | 401 | (Phase 2+) missing/invalid credentials |
| `AUTHORIZATION_DENIED` | 403 | (Phase 2+) permission or scope failure |
| `RESOURCE_NOT_FOUND` | 404 | unknown route or missing resource |
| `DUPLICATE_RESOURCE` | 409 | uniqueness violations (Phase 3+) |
| `CONFLICT_CONCURRENT_UPDATE` | 409 | optimistic-lock conflicts |
| `INSUFFICIENT_STOCK` | 409 | (Phase 4+) stock decrements |
| `BUSINESS_RULE_VIOLATION` | 422 | domain rules not covered by a specific code |
| `RATE_LIMITED` | 429 | (Phase 10+) throttling |
| `INTERNAL_ERROR` | 500 | unhandled exceptions, BFF upstream failure |
| `STALE_VERSION` | 409 | client sent outdated `version` |
| `RESOURCE_LOCKED` | 423 | pessimistic lock contention |

## Mapping rules (Phase 1)

1. `AppError` → its own status/code.
2. Framework validation errors → 422 `VALIDATION_ERROR` with field-level `details`.
3. Unknown routes → 404 `RESOURCE_NOT_FOUND`; method-not-allowed → 405 mapped to
   `BUSINESS_RULE_VIOLATION` (422 semantics: operation not offered on that resource).
4. Unhandled exceptions → 500 `INTERNAL_ERROR`; full traceback goes to server logs with
   the trace id, never into the response body.
5. Every envelope carries the request's `trace_id`; every error is logged with it.

## Trace propagation

- Incoming non-empty `X-Request-ID` header is adopted verbatim; otherwise a UUID v4 is
  generated. Empty values are ignored (fresh id generated).
- The id is echoed on every response (`X-Request-ID`), stored in a request-scoped
  context, injected into all log records, and embedded in every error envelope.
- `X-Request-ID` is a correlation convenience, not an authentication or authorization
  control.
