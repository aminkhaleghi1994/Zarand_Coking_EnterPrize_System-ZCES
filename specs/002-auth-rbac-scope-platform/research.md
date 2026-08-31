# Research: Auth, RBAC & Scope Platform

**Date**: 2026-08-29 · Resolves all technical unknowns for [plan.md](./plan.md)

## R1 — JWT library

**Decision**: `PyJWT` (+ `cryptography` for HS256/RS support) for access tokens.

**Rationale**: Actively maintained, minimal API, first-class `exp/iat/jti` handling.
`python-jose` (named in the requirements boilerplate install list) has a history of
CVEs and slower maintenance; PyJWT is the safer modern default while keeping the same
"JWT access token" contract.

**Alternatives considered**: python-jose (rejected — maintenance/CVE record);
`joserfc` (viable but unnecessary when PyJWT covers the need).

## R2 — Password hashing

**Decision**: `bcrypt` library used directly (cost factor 12). NOT passlib.

**Rationale**: The requirements' install list says `passlib[bcrypt]`, but passlib is
unmaintained and breaks with bcrypt ≥ 4.1 (the `__about__` removal). Calling bcrypt
directly provides the same adaptive-salted scheme with zero intermediary drift.
Verification is constant-time; hash format `$2b$12$...` self-describes cost.

**Alternatives considered**: argon2-cffi (stronger memory-hardness but diverges from
the documented scheme; revisit only if a phase requires it); passlib (rejected —
unmaintained, incompatible with current bcrypt).

## R3 — Token design & revocation strategy

**Decision**: Access token = JWT (HS256, `sub` = user id, `jti`, `type=access`, `exp`
15 min default, `iat`). Refresh token = **opaque** `secrets.token_urlsafe(32)`, stored
only as SHA-256 hash in `refresh_tokens` with `family_id`, `status`
(active/rotated/revoked), `expires_at` (7 days default), `rotated_to_id`. One family
per login session. Renewal: active member → mark rotated, insert new member (same
family), return new pair. Presenting a rotated/revoked member → revoke whole family +
`AUTHENTICATION_REQUIRED` + audit. No Redis blacklist: DB rows ARE the revocation
source of truth at this scale (constitution VIII).

**Rationale**: Opaque refresh + DB families give exact reuse detection and per-family
revocation with trivially auditable state; JWT-only revocation would need a blacklist.

**Alternatives considered**: JWT refresh with `jti` blacklist in DB (equivalent
complexity, worse ergonomics); in-memory/Redis revocation (rejected — adds Redis
dependency ahead of the phase that needs it).

## R4 — Cookie & CSRF boundary

**Decision**: Cookies are owned by the Next.js BFF: `zces_at` (access JWT), `zces_rt`
(refresh opaque), all `HttpOnly; SameSite=Lax; Path=/` (`Secure` when `COOKIE_SECURE`,
prod), lifetimes from env. `zces_csrf` (random, NOT HttpOnly) + required
`X-CSRF-Token` header on browser mutations (double-submit, compared for equality).
Backend auth endpoints are server-to-server for the BFF: login/refresh accept JSON
bodies (`email/password`, `refresh_token`) and return the token pair in the body —
the BFF immediately converts them to browser cookies and never renders them. Backend
additionally accepts `Authorization: Bearer <access>` for `me` and all protected
endpoints.

**Rationale**: Matches the BFF pattern in requirements §12.1 and AGENTS.md ("browser
never sees raw tokens"); double-submit at the browser boundary is where the CSRF
threat actually lives. `Lax` blocks cross-site POSTs; double-submit covers the rest.

**Alternatives considered**: backend-issued CSRF with same-site cookies across two
origins (fragile port/domain juggling in dev); SameSite=Strict (breaks deep-link
return flows).

## R5 — Scope resolver semantics

**Decision**: `ScopeContext` loaded per request (user id → permission codes via
user→roles→permissions; scope assignments via `scope_assignments`). Resolver answers
`can(module, resource, operation, *, complex_id=None, workplace_id=None)`:
1. permission code `module:resource:operation` must be present — else deny;
2. covering scope: assignment target must equal `module:resource:operation` AND
   level coverage: `Global` always; `Complex` when `assignment.complex_id ==
   complex_id` (or the target unit IS that complex); `Workplace` when
   `assignment.workplace_id == workplace_id`;
3. union across all assignments; deny is implicit; unknown/None target with
   non-Global level → deny.
FastAPI dependency `require_permission("user:role:assign")` wraps this and raises
`AUTHORIZATION_DENIED` (403) / `AUTHENTICATION_REQUIRED` (401). Resolver is a pure
function over plain data → exhaustive unit tests without a DB.

**Rationale**: Requirements §13 exactly (union, implicit deny, hierarchy); purity
makes the 15+-case gate testable in milliseconds; one decision point per
constitution II.

**Alternatives considered**: wildcard `*` targets (rejected — requirements specify
exact codes; seed grants explicit Global scopes per operation instead); per-route
hardcoded checks (rejected — unenforceable).

## R6 — Audit base & masking

**Decision**: `audit_logs` append-only table (no version, no soft delete — rows are
never updated): `id, actor_user_id?, entity_type, entity_id?, action, before_snapshot
JSONB?, after_snapshot JSONB?, trace_id, created_at`. `audit/service.py::write_audit`
with `critical: bool` — critical (login success/failure, logout, renewal, reuse
detection, family revocation) commits in the request transaction; deferred failures
log-and-continue (constitution VII tolerance). Central masking helpers in
`common/masking.py`: `mask_email` (`u***@domain`), `mask_identifier` (last 4 digits),
`mask_secret` (`***`), applied to snapshots at write time. Audit read API is admin
(`audit:log:read` + Global scope); full snapshots only for privileged roles.

**Rationale**: §21 field list verbatim; transactional durability for the events whose
loss would be a security hole; masking at write time means leaks can't happen later.

**Alternatives considered**: async outbox for audit (arrives with the notification
phase; premature here); masking at read time (rejected — write-time is fail-safe).

## R7 — Admin endpoints & bootstrap

**Decision**: Minimal administration surface: `GET /roles`, `POST /roles`,
`GET /permissions`, `GET /users` (paginated), `POST /users/{id}/roles`,
`DELETE /users/{id}/roles/{role_id}`, `POST /users/{id}/scopes`,
`DELETE /users/{id}/scopes/{assignment_id}` — all behind `require_permission` with
`user:role:*` / `user:scope:*` / `user:list:read` codes, audited with before/after.
Bootstrap: seeded SuperAdmin holds every seeded permission + a Global scope per
seeded operation, so the system can administer itself. UI for role/scope administration
arrives in Phase 3 (org-user module) per the roadmap — this phase ships the endpoints
+ contracts only.

**Rationale**: Roadmap puts role/scope UI in Phase 3; endpoints here unblock it and
satisfy FR-011 with testable surface.

**Alternatives considered**: shipping admin UI now (rejected — roadmap order);
patch-based user editing (arrives with employee CRUD in Phase 3).

## R8 — Seed

**Decision**: `python -m app.seeds.seed_dev [--prod]` idempotent by natural keys
(role name, permission code, user email — all unique on active rows): 7 base roles,
base permission set (auth/rbac + placeholder operations for later modules NOT seeded —
only what exists), SuperAdmin role = all permissions, admin user (env credentials)
+ Global scope per permission. `--prod` refuses when the admin password matches the
template default (`change_me_now`) or is empty. Dev seed is safe to re-run anytime.

**Rationale**: Requirements §26 (idempotent, env password, unsafe default forbidden);
natural-key upserts make reruns no-ops without soft-deleting anything.

**Alternatives considered**: Alembic data migration (rejected — seeds are
environment-specific, not schema); per-phase ad-hoc scripts (rejected — §26 wants
seed designed from the start).

## R9 — Frontend session plumbing

**Decision**: `lib/serverSession.ts` — server helper wrapping backend calls with the
cookie jar (`cookies()` from `next/headers`): forwards `Cookie`, on 401 performs ONE
`POST ${BACKEND}/auth/refresh` with the `zces_rt` cookie value, updates both cookies
from the response, retries the original call once; on refresh failure clears cookies.
BFF routes: `POST /api/auth/login` (Zod-validated body, CSRF check, sets cookies),
`POST /api/auth/logout` (CSRF, revokes family, clears cookies), `GET /api/auth/refresh`
(called by the helper, sets cookies), `GET /api/auth/me` (session JSON or 401-shaped
body). `[locale]` layout: server-side `me()` → unauthenticated visitors to protected
pages redirect to `/{locale}/login?next=…`; identity (email, roles) rendered into
`AppChrome` with a `LogoutButton` (client, CSRF header, redirect on success). Login
page reads `?next` and session-expired flag for localized messaging. All strings via
`auth.*` keys in `en.json`/`fa.json`.

**Rationale**: Keeps every token decision in one server helper; single-retry renewal
matches FR-018; layout-level guard avoids per-page duplication now (per-page
permission guards arrive with business modules).

**Alternatives considered**: TanStack Query client-side session probing (rejected —
server components own the shell; hydration flash + token-in-JS risk); middleware-level
cookie sniffing (rejected — middleware can't validate JWTs server-side without shipping
the secret to edge runtime).

## R10 — CI

**Decision**: Unchanged workflow shape; backend job gains `INITIAL_ADMIN_*` +
`JWT_SECRET_KEY` env vars (non-secret CI values) so tests/seed exercise real paths;
migration step now applies `0002`; DB integration tests run against the PG16 service.

**Rationale**: Same gates as Phase 1 (constitution VII); auth tests need the env
surface that Phase 1 already templated.

**Alternatives considered**: secrets in CI (rejected — public repo; only dev-default
values, real secrets stay local).
