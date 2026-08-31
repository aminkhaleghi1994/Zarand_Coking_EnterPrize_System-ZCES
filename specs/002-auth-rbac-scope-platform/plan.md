# Implementation Plan: Auth, RBAC & Scope Platform

**Branch**: `feature/002-auth-rbac-scope-platform` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-auth-rbac-scope-platform/spec.md`

## Summary

Deliver the security platform: backend authentication (JWT access + rotating DB-backed
opaque refresh tokens with family reuse detection, bcrypt password hashing, HttpOnly
cookies owned by the BFF, double-submit CSRF at the browser boundary), the RBAC +
hierarchical scope model with a single central resolver (permission AND scope, union,
implicit deny, Global > Complex > Workplace coverage), an append-only audit base with
central masking helpers, idempotent dev/prod seeding (initial admin from env, 7 base
roles), and the BFF/UI integration (login form → BFF routes → authenticated shell with
identity + logout, transparent renewal, session-expired handling). Gate: end-to-end
login in the browser; scope resolver unit tests green; all Phase 1 gates stay green.

## Technical Context

**Language/Version**: Python 3.12 (backend venv) · Node 24 / npm 11 (frontend)

**Primary Dependencies**: existing Phase 1 stack + PyJWT (access tokens), bcrypt
(password hashing); no new frontend runtime deps

**Storage**: PostgreSQL (8 new tables, all UUID-keyed, partial unique indexes on
active rows)

**Testing**: pytest (unit: resolver, masking, token service; integration: endpoints,
rotation, seed idempotency) · eslint/tsc/build (frontend) · extended smoke test

**Target Platform**: Local Windows dev → single Ubuntu VM; GitHub Actions CI

**Performance Goals**: identity/scope resolution per request is DB-backed (join
queries); P95 < 200ms applies from business-module phases onward

**Constraints**: browser never touches FastAPI (BFF only); secrets env-only; no Redis
(DB-backed revocation is sufficient at this scale); audit-critical events share the
request transaction; no rate limiting yet (Phase 10)

**Scale/Scope**: 8 new tables · 4 auth endpoints + 6 admin endpoints · 4 BFF routes ·
login UI wiring · ~45 tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence / Plan |
|---|---|---|
| I. Spec-driven sequential delivery | ✅ Pass | This cycle; gate = e2e login + resolver tests + smoke |
| II. Scoped access on every query | ✅ Enabled | Central resolver + `require_permission` dependency delivered; admin repositories take a scope context; business-module repositories inherit the pattern in Phase 3 |
| III. Auditability & data integrity | ✅ Pass | AuditLog append-only (no soft delete needed — never updated); UUIDs; optimistic locking on editable entities; auth-critical audit writes transactional (FR-014) |
| IV. Security & secrets discipline | ✅ Pass | Tokens HttpOnly at the BFF; no token in browser scripts; hashes only server-side; env-only config; generic auth errors prevent enumeration; logs/audit masked centrally |
| V. Bilingual RTL responsive UX | ✅ Pass | All new strings via EN/FA dictionaries; login/logout/session-expired flows localized; existing responsive shell unchanged |
| VI. Modular monolith boundaries | ✅ Pass | New `modules/user` (auth, rbac, scope) + `modules/audit` with `contracts.py`; audit written via contract, not cross-module repository access |
| VII. Standard API contracts | ✅ Pass | 401/403 map to `AUTHENTICATION_REQUIRED`/`AUTHORIZATION_DENIED`; all errors via existing envelope + trace id; audit list endpoints paginated |
| VIII. Simplicity over speculation | ✅ Pass | No Redis blacklist, no OAuth/SSO, no MFA, no rate limiting — DB-backed families + env config only |

**Post-design re-check**: ✅ Passes — no violations; Complexity Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-auth-rbac-scope-platform/
├── plan.md / research.md / data-model.md / quickstart.md / tasks.md
└── contracts/ (auth.md, cookies-csrf.md, scope-resolution.md, audit.md)
```

### Source Code (repository root)

```text
backend/app/
├── core/
│   ├── config.py            # + JWT_*, COOKIE_*, INITIAL_ADMIN_* settings
│   ├── security.py          # NEW: bcrypt hash/verify, JWT encode/decode, token secrets
│   ├── errors.py            # + 401/403 mapping already present
│   └── database.py          # unchanged
├── common/
│   ├── mixins.py            # unchanged
│   ├── masking.py           # NEW: mask_identifier / mask_secret / mask_email
│   ├── pagination.py        # unchanged
│   └── scope.py             # NEW: ScopeContext, ScopeResolver, require_permission dep
├── modules/
│   ├── user/
│   │   ├── models.py        # User, Role, Permission, RolePermission, UserRole,
│   │   │                    # ScopeAssignment, RefreshToken
│   │   ├── schemas.py       # DTOs (LoginIn, TokenPairOut, MeOut, RoleOut, ...)
│   │   ├── repository.py    # scope-context-aware queries
│   │   ├── auth_service.py  # login/refresh/logout/reuse-detection/audit-critical
│   │   ├── rbac_service.py  # role/scope administration
│   │   ├── router.py        # /api/v1/auth/*, /api/v1/roles|permissions|users/*
│   │   ├── contracts.py     # get_user_by_id, is_user_active, get_user_scopes ...
│   │   └── tests/
│   └── audit/
│       ├── models.py        # AuditLog
│       ├── schemas.py       # AuditOut (masked)
│       ├── repository.py    # paginated read
│       ├── service.py       # write_audit (critical/deferred modes)
│       ├── router.py        # GET /api/v1/audit-logs (admin)
│       └── tests/
└── seeds/
    ├── seed_dev.py          # idempotent: admin + roles + permissions + scopes
    └── seed_prod.py         # refuses unsafe admin password

frontend/src/
├── app/api/auth/{login,logout,refresh,me}/route.ts   # BFF, cookie owner
├── app/[locale]/layout.tsx  # + server-side session guard, identity into chrome
├── app/[locale]/login/page.tsx  # form → BFF, CSRF, session-expired surface
├── components/layout/AppChrome.tsx  # + identity block + logout control
├── features/auth/           # LoginForm (real submit), LogoutButton, session types
├── lib/                     # serverSession.ts (cookie jar + transparent retry), csrf.ts
└── messages/                # en/fa: auth.* keys

backend/alembic/versions/0002_auth_rbac_scope.py   # 8 tables, partial unique indexes
```

**Structure Decision**: Two new modules (`user`, `audit`) inside the existing modular
monolith layout, per backend/AGENTS.md module template (models/schemas/repository/
service/router/contracts/tests). Frontend gains BFF auth routes + session plumbing
without new runtime dependencies.

## Complexity Tracking

> Empty — no constitution violations to justify.
