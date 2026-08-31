# Tasks: Auth, RBAC & Scope Platform

**Input**: Design documents from `/specs/002-auth-rbac-scope-platform/`

**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED per task (constitution: tests are part of each task; write before
implementation where practical).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1–US5; FND = foundational; POL = polish
- FR/SC references map to spec.md

---

## Phase 1: Setup

- [x] T001 [FND] Add `pyjwt`, `bcrypt` (+ `types-*` stubs) to `backend/requirements-dev.txt`/`requirements.txt`; install & verify import in venv (FR-002)
- [x] T002 [P] [FND] `app/core/config.py`: add JWT_SECRET_KEY (required, min 16 chars — fail fast without echoing it), JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, COOKIE_* flags, INITIAL_ADMIN_* (password min 8); write `tests/test_config.py` additions (missing secret → error naming var, not value; defaults parsed) (FR-002, FR-020)

## Phase 2: Foundational (blocking)

- [x] T003 [FND] `app/core/security.py`: `hash_password`/`verify_password` (bcrypt cost 12), `create_access_token` (sub/jti/type/iat/exp), `decode_access_token` (returns payload or None; verifies type+exp), `new_opaque_token` + `hash_opaque_token` (sha256 hex); `tests/test_security.py`: hash/verify roundtrip + wrong-password False; tampered JWT → None; expired JWT → None; opaque tokens unique, hash stable (FR-002)
- [x] T004 [P] [FND] `app/common/masking.py`: `mask_secret`, `mask_email`, `mask_identifier`, `mask_user_agent`, `mask_snapshot(dict)` with structural sensitive-key mapping; `tests/test_masking.py`: national_id → `***1234`, email local part masked, password/token keys fully masked, non-sensitive keys untouched (FR-013, SC-005)
- [x] T005 [FND] `app/common/scope.py`: `ScopeAssignmentData`, `ScopeContext` (permission codes + assignments), pure `ScopeResolver.can(...)` per contracts/scope-resolution.md; `tests/test_scope_resolver.py`: **≥ 15 cases** — permission-only deny, scope-only deny, both allow, neither deny, Global→any, Complex→own workplace only, Workplace→self only, cross-complex deny, cross-workplace deny, union same level, union across levels, unknown operation deny, null target + non-global deny, org-agnostic op with Global allow, org-agnostic op with Complex deny, deactivated handled at loader (SC-002 gate)
- [x] T006 [FND] `app/modules/user/models.py` (users, roles, permissions, role_permissions, user_roles, scope_assignments, refresh_tokens) + `app/modules/audit/models.py` (audit_logs) per data-model.md; alembic revision `0002_auth_rbac_scope` (hand-review partial unique indexes + enums); verify `upgrade head → downgrade -1 → upgrade head` on local PG (FR-007, FR-012)

**Checkpoint**: models migrate cleanly; resolver + security + masking units green.

## Phase 3: US5 — Seeded bootstrap identity (P3)

- [x] T007 [US5] `app/seeds/seed_dev.py`: upsert 7 base roles, base permission set (user:list:read, user:role:read/create/assign, user:permission:read, user:scope:assign, audit:log:read, audit:log:read_full), SuperAdmin=ALL, admin user (env credentials, bcrypt), Global scope per permission; `app/seeds/seed_prod.py` refuses default/empty admin password; `app/seeds/__main__.py` entry; `tests/test_seed.py`: fresh seed exact state; re-run no-op (SC-007); prod refusal test (FR-020)

## Phase 4: US1 — Sign in / sign out / identity (P1) 🎯

- [x] T008 [US1] `app/modules/user/repository.py` (scope-context-aware): `get_active_user_by_email`, `get_user_by_id`, `load_scope_context(user_id)` (roles→permission codes + assignments), `list_users` (paginated Page[UserOut]), role/permission listers; `tests/test_user_repository.py` (integration, PG service URL or skip): unique email partial index blocks duplicate active (allows soft-deleted), loaders return expected shapes (FR-007, FR-009)
- [x] T009 [P] [US1] `app/modules/audit/` repository + `service.write_audit(..., critical)` + `contracts.py` (public `write_audit` façade) per contracts/audit.md; `tests/test_audit_service.py`: critical write in-session visible; deferred failure swallowed + logged; snapshots masked; trace id attached (FR-012, FR-013, FR-014)
- [x] T010 [US1] `app/modules/user/auth_service.py`: `authenticate(email, password)` → user or raise (generic `AUTHENTICATION_REQUIRED`; audits LOGIN_SUCCEEDED/LOGIN_FAILED critical, masked email in snapshot); `issue_family(user, user_agent)` → (access, refresh); `rotate(refresh_token)` → new pair + audit TOKEN_RENEWED; reuse (rotated/revoked member) → revoke family + audits TOKEN_REUSE_DETECTED + FAMILY_REVOKED + raise; `logout(refresh_token)` → revoke family + audit; `revoke_all_for_user(user_id)`; `tests/test_auth_service.py` (integration): full rotate chain, replay → family dead, logout kills family, deactivated user denied (FR-001, FR-003, FR-006, FR-014, SC-003)
- [x] T011 [US1] `app/modules/user/router.py`: POST /auth/login, /auth/refresh, /auth/logout, GET /auth/me (+ Session validate 204) per contracts/auth.md — Pydantic DTOs, no tokens in `me`, envelope errors; `tests/test_auth_endpoints.py`: login 200 shape; wrong password → 401 generic (same body as unknown email); deactivated → 401; me without token → 401; me with token → roles+permissions+scopes (FR-001, FR-004, FR-010)
- [x] T012 [US1] `app/common/scope.py::require_permission` FastAPI dependency (401 before 403; ScopeContext via repository) + admin routers: GET/POST /roles, GET /permissions, GET /users, POST/DELETE /users/{id}/roles, POST/DELETE /users/{id}/scopes, GET /audit-logs (paginated, filters, read_full gating); `tests/test_admin_endpoints.py`: roleless user → 403 on all; SuperAdmin → 200; assign/revoke audited with snapshots; audit list pagination envelope (FR-009, FR-010, FR-011, FR-015)

**Checkpoint**: backend auth fully usable via HTTP (curl-able end-to-end).

## Phase 5: US2 — Session plumbing at the BFF (P1)

- [x] T013 [US2] `frontend/src/lib/csrf.ts` (issue/compare double-submit) + `src/app/api/auth/login/route.ts`: Zod body, CSRF-exempt (pre-auth), backend call, Set-Cookie `zces_at`/`zces_rt` (HttpOnly+SameSite Lax+Secure-if-env) + `zces_csrf` (readable), returns `{user, roles}` only; never logs tokens (FR-002, FR-016)
- [x] T014 [P] [US2] `src/app/api/auth/logout/route.ts` (CSRF required → backend logout → clear cookies), `src/app/api/auth/refresh/route.ts` (cookie-only rotation, sets new cookies), `src/app/api/auth/me/route.ts` (via serverSession; 401-shaped body on failure) (FR-004, FR-018)
- [x] T015 [US2] `frontend/src/lib/serverSession.ts`: cookie-jar fetch wrapper — forwards cookies, on 401 ONE refresh + retry, clears cookies when renewal fails; X-Request-ID per call; tokens never returned to client components (FR-018, SC-005)

## Phase 6: US1/US3/US4 — Authenticated shell & protection (P1/P2)

- [x] T016 [US1] `src/features/auth/LoginForm.tsx` real submit → `/api/auth/login` (no CSRF header pre-auth), generic error display via error-code dictionary, `?next` redirect, session-expired flag surface; `?expired=1` localized message (FR-016, FR-017, FR-019)
- [x] T017 [US3/US4] `[locale]/layout.tsx` server guard: `me()` via serverSession → redirect `/{locale}/login?next=…` when unauthenticated; pass identity into `AppChrome` (email, roles) + `LogoutButton` (client, CSRF header, redirect on success); `messages/{en,fa}.json` `auth.*` keys (identity, logout, sessionExpired, login errors) (FR-017, FR-019, V)

## Phase 7: Polish & Convergence

- [x] T018 [P] [POL] `scripts/smoke-test.ps1`: add checks — login via BFF returns user w/o token material; `zces_at`/`zces_rt` HttpOnly + `zces_csrf` present; me with cookie jar; logout clears; admin endpoint 403 for roleless (script creates one via admin API then verifies); CSRF-less mutation rejected (FR-005, SC-001)
- [x] T019 [POL] README auth section + CHANGELOG 0.2.0 entry; VERSION → 0.2.0 (FR-020 lifecycle)
- [x] T020 [POL] Full gate: backend ruff/mypy/pytest; frontend lint/tsc/build; seed twice idempotent; manual browser gate per quickstart.md (login/FA-RTL/expiry/reuse/403/audit); commit + push; CI green

---

## Dependencies & Execution Order

- T001–T002 → T003–T005 ([P] pairs) → T006 → T007 → T008–T012 (T009 parallel with
  T008; T010 needs T003+T008+T009; T011 needs T010; T012 needs T005+T008) →
  T013–T015 (need live backend from checkpoint) → T016–T017 → T018–T020.
- The Phase 1 gate (SC-002) is T005 — resolver unit tests can go green before any
  endpoint exists.

## Notes

- No physical deletes anywhere; grant tables (role_permissions, user_roles,
  scope_assignments) insert/delete rows by design with audit snapshots.
- All credentials/tokens masked or absent in logs, audit, responses (SC-005 asserted
  by tests, not just policy).
- User *deactivation endpoint/UI* is Phase 3 (employee CRUD); Phase 2 ships the
  machinery it will call — `revoke_all_for_user` + active-check at the authentication
  boundary (FR-006 verified by tests, not by an endpoint).
- Commit after each phase checkpoint (Conventional Commits).

## Convergence record (2026-08-31)

- Backend gate: `ruff check .` + `ruff format --check .` clean (alembic excluded in
  `pyproject.toml`, matching CI scope; app/tests reformatted), `mypy app` strict clean,
  `pytest` 79/79 green including DB integration (roleless-403 in `test_admin_endpoints.py`).
- Frontend gate: eslint, `tsc --noEmit`, `next build` all clean.
- Smoke test: `scripts/smoke-test.ps1` extended with Phase 2 BFF checks (T018) —
  cookie flags, me, CSRF rejection, logout family kill; roleless-403 via API deferred
  to Phase 3 (no user-creation endpoint exists yet).
- Implementation note: T013/T015 shipped as `frontend/src/lib/session.ts` +
  `session-cookies.ts` (names differ from the task text; behavior per contract).
