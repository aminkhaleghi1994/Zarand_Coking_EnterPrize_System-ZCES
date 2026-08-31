# Contract: Browser Cookies & CSRF (BFF-owned boundary)

**Scope**: Next.js BFF ⇄ browser · The BFF is the ONLY writer of session cookies.

## Cookies

| Name | Content | HttpOnly | Lifetime | Purpose |
|---|---|---|---|---|
| `zces_at` | access JWT | yes | 15 min (env) | forwarded as `Authorization`/`Cookie` to backend via BFF |
| `zces_rt` | opaque refresh token | yes | 7 days (env) | sent ONLY to `/api/auth/refresh` + `/api/auth/logout` |
| `zces_csrf` | random 128-bit token | **no** | session | double-submit pair |

Common attributes: `Path=/`; `SameSite=Lax`; `Secure` when `COOKIE_SECURE=true`
(production); `Domain` unset (host-only).

## CSRF rules (browser mutations)

1. Browser mutations (`POST/DELETE` via BFF) MUST send header
   `X-CSRF-Token: <value of zces_csrf cookie>`.
2. BFF compares header ↔ cookie; mismatch/missing → HTTP 403 standard envelope
   `VALIDATION_ERROR` (validation-class per FR-005), request never reaches business
   processing.
3. `zces_csrf` is (re)issued on login and rotated on refresh; `GET` requests are
   exempt (no state change).
4. The refresh path itself (`GET /api/auth/refresh` triggered by serverSession) is
   cookie-only and exempt from CSRF header (it mutates nothing user-visible).

## BFF routes (browser-facing)

- `POST /api/auth/login` — body `{email, password}`; CSRF exempt (pre-auth; credential
  POST from our own origin; Lax already blocks cross-site). Calls backend `/auth/login`,
  sets `zces_at`/`zces_rt`/`zces_csrf`, returns `{user, roles}` (NO tokens).
- `POST /api/auth/logout` — CSRF required; calls backend `/auth/logout`, clears all
  three cookies, `{success: true}`.
- `GET /api/auth/me` — reads `zces_at`, calls backend `/auth/me` (with transparent
  single renewal via serverSession); 200 `{user, roles, permissions, scopes}` or
  401-shaped `{code: "AUTHENTICATION_REQUIRED", ...}` (cookies cleared when renewal
  also failed).
- `GET /api/auth/refresh` — internal helper endpoint used by serverSession; sets
  rotated cookies; never returns token material.

## serverSession helper rules (`lib/serverSession.ts`)

1. Wraps every backend call with the cookie jar; `X-Request-ID` per request.
2. On backend 401: ONE refresh attempt (`zces_rt`) → on success update cookies and
   retry the original call exactly once → on failure clear cookies and surface the
   standard envelope.
3. Tokens are never logged, never returned to client components, never stored outside
   the HttpOnly cookies.
