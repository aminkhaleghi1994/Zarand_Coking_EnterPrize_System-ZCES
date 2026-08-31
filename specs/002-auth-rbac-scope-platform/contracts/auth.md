# Contract: Auth Endpoints (backend, server-to-server for the BFF)

**Scope**: Phase 2 · Owner: `modules/user` · Consumers: Next.js BFF only (browser
never calls these directly)

## `POST {API_V1_PREFIX}/auth/login`

- Body: `{ "email": string, "password": string }` (Zod/Pydantic validated)
- 200 → `{ "user": { "id", "email", "username", "is_active" }, "roles": [name…],
  "access_token", "access_expires_in": seconds, "refresh_token" }`
- 401 → standard envelope `AUTHENTICATION_REQUIRED` (generic message — no user
  enumeration) for: unknown email, wrong password, deactivated user
- 422 → `VALIDATION_ERROR` (shape only)
- Side effects: refresh family created (first member), audit
  `LOGIN_SUCCEEDED` / `LOGIN_FAILED` (critical, same transaction)
- Rate limiting: Phase 10 (audit row provides the raw data)

## `POST {API_V1_PREFIX}/auth/refresh`

- Body: `{ "refresh_token": string }`
- 200 → same shape as login (new pair, new family member; old member `rotated`)
- 401 → `AUTHENTICATION_REQUIRED` when: unknown hash, expired, rotated/reused, or
  family/user revoked. Reuse (presenting a rotated/revoked member) additionally
  revokes the ENTIRE family and audits `TOKEN_REUSE_DETECTED` + `FAMILY_REVOKED`
- Side effects: audit `TOKEN_RENEWED` (critical)

## `POST {API_V1_PREFIX}/auth/logout`

- Body: `{ "refresh_token": string }`
- 200 → `{ "success": true }`; revokes the token's family (all devices of that
  session lineage), audits `LOGOUT` + `FAMILY_REVOKED` (critical)
- 401 → unknown/expired token (idempotent from the client's perspective)

## `GET {API_V1_PREFIX}/auth/me`

- Header: `Authorization: Bearer <access JWT>` (also accepted: `X-Request-ID` always)
- 200 → `{ "user": { "id", "email", "username", "is_active" }, "roles": [name…],
  "permissions": [code…], "scopes": [ { level, module, resource, operation,
  complex_id?, workplace_id? } ] }`
- 401 → missing/expired/invalid token (`AUTHENTICATION_REQUIRED`); deactivated user
  denied here as well

## `GET {API_V1_PREFIX}/auth/session/validate` (internal fast check)

- Header: Bearer; 204 when valid; 401 otherwise (used by BFF to decide retry)

## Admin surface (all `require_permission`-guarded, all audited, all paginated where lists)

- `GET  /roles` → Page[RoleOut] — permission `user:role:read`
- `POST /roles` → RoleOut — `user:role:create` (audited, after-snapshot)
- `GET  /permissions` → Page[PermissionOut] — `user:permission:read`
- `GET  /users` → Page[UserOut] (no password material) — `user:list:read`
- `POST /users/{id}/roles` `{role_id}` — `user:role:assign` (audited, after)
- `DELETE /users/{id}/roles/{role_id}` — `user:role:assign` (audited, before)
- `POST /users/{id}/scopes` `{level, module, resource, operation, complex_id?,
  workplace_id?}` — `user:scope:assign` (audited, after; level/unit consistency
  validated; unknown unit → `VALIDATION_ERROR`)
- `DELETE /users/{id}/scopes/{assignment_id}` — `user:scope:assign` (audited, before)
- `GET /audit-logs?page&page_size&actor_user_id&action` → Page[AuditOut masked] —
  `audit:log:read`; full snapshots restricted to `audit:log:read_full`

## Global rules

- Every response carries `X-Request-ID`; every error uses the standard envelope.
- Token material never appears in: responses after the login/refresh pair, logs,
  audit snapshots (hashes only), or `UserOut`.
- Password rules: min 8 chars; hashing cost 12; verification constant-time.
