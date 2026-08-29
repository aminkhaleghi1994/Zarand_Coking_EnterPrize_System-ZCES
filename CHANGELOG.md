# Changelog

All notable changes to this project are documented here. The format is based
on Keep a Changelog, and this project adheres to Semantic Versioning.

## [0.2.0] - 2026-08-29

### Added
- Authentication (Phase 2): login/logout/me with short-lived JWT access
  tokens (PyJWT) and rotating opaque refresh tokens (bcrypt hashing for
  passwords, SHA-256 hashing for refresh tokens) backed by DB refresh-token
  families — replay of a rotated/revoked token revokes the entire family and
  forces re-authentication; generic auth errors prevent user enumeration
- Authorization: RBAC entities (roles, permissions, role_permissions,
  user_roles) plus hierarchical scope assignments (Global > Complex >
  Workplace) and a central pure resolver — permission AND scope required,
  union across assignments, implicit deny; 18-case resolver unit suite;
  `require_permission` FastAPI dependency (401 before 403)
- Audit base: append-only `audit_logs` (actor, entity, action, masked
  before/after snapshots, trace_id) with critical-vs-deferred durability
  (auth events transactional, others tolerate failure); central masking
  helpers (email, identifiers, secrets) applied at write time
- Migration `0002_auth_rbac_scope`: 8 tables with UUID PKs, partial unique
  indexes on active rows, CHECK-constrained enums (reversible)
- Idempotent seeds: 7 base roles, base permission set, initial admin from
  environment (dev seed safe to re-run; prod seed refuses unsafe/default
  admin passwords)
- Admin endpoints (permission-guarded, audited): roles, permissions, users,
  role/scope assignment + revocation, paginated audit log with
  snapshot-visibility gating (`audit:log:read_full`)
- Frontend session plumbing (Phase 2): BFF-owned HttpOnly cookies
  (`zces_at`, `zces_rt`) + readable CSRF cookie with double-submit header
  validation on mutations; `/api/auth/{login,logout,refresh,me}` route
  handlers; transparent renewal via `GET /api/auth/refresh?next=…` with
  post-refresh identity validation; server-side layout guard redirecting
  unauthenticated visitors (destination preserved via middleware for cold
  navigation); login form wired to real authentication; identity (email +
  roles) and logout control in the app chrome; localized session-expired
  and auth error messages (EN/FA)
- Route-group restructure: `(app)` guarded shell vs `(auth)` login surface
- Smoke test extended with auth checks (login shape, generic rejection,
  401 enforcement) — 11 checks total
- CI: seed/admin env for backend job; auth + resolver + seed-idempotency
  tests run against PostgreSQL 16 service container

### Changed
- Backend deps: added PyJWT, bcrypt, email-validator; requirements floors
  updated
- README quick start: seed step + auth smoke checks; VERSION → 0.2.0

## [0.1.0] - 2026-08-29

### Added
- Backend platform skeleton (Phase 1): environment-driven config
  (pydantic-settings, fail-fast without leaking secrets), structured JSON
  logging with trace-id injection, request trace correlation
  (`X-Request-ID` middleware + contextvar), standard error envelope
  `{code, message, details, trace_id}` for all failure paths (validation,
  unknown routes, method-not-allowed, unhandled exceptions), `GET /healthz`
  (+ `/api/v1/healthz`) with liveness-vs-component semantics
- Database layer: SQLAlchemy 2.0 sync engine/session factory, `Base`
  declarative base, 2s DB health probe
- Shared entity conventions as mixins: ID (UUID), Timestamp,
  SoftDelete, Version (optimistic locking), CreatedBy/UpdatedBy, OrgScope
  (Company/Complex/Workplace columns)
- Alembic baseline `0001_baseline` (empty, reversible stamp point) wired to
  app metadata; verified upgrade → downgrade → upgrade against PostgreSQL 18
- Frontend scaffold (Phase 1): Next.js 16 App Router + TypeScript strict,
  Tailwind v4 with DESIGN.md token mapping (HP Electric Blue accent,
  two-tier radius 4px/16px, Soft Lift shadow), shadcn/ui primitives,
  next-intl bilingual routing (`/en`, `/fa`) with `lang`/`dir` switching,
  Kalameh standard + FaNum local fonts, reduced-motion support, page
  transitions and skeleton loaders
- Login visual shell (React Hook Form + Zod, i18n strings, no auth logic —
  Phase 2 delivers authentication)
- BFF layer: `/api/health` proxy with Zod validation, 5s timeout, and
  standard-error mapping (browser never calls FastAPI directly)
- Shared frontend error-code dictionary mirroring the backend standard set
- Dev bring-up scripts: `scripts/dev-backend.ps1`, `dev-frontend.ps1`,
  `smoke-test.ps1` (8-check phase gate)
- GitHub Actions CI: backend (ruff, mypy, pytest + PostgreSQL 16 service,
  migrations applied in CI) and frontend (eslint, tsc, next build)
- Spec Kit artifacts for Phase 1 (`specs/001-foundation-skeleton/`):
  spec, plan, research, data model, contracts (health, error envelope,
  BFF proxy), quickstart guide, 32-task list with full FR/SC coverage
- Monorepo structure: backend/, frontend/, infra/, docs/, scripts/, .github/
- Requirements source relocated to docs/requirements-prompt.txt
- Design system spec at frontend/DESIGN.md
- GitHub Spec Kit integration (opencode) with project constitution v1.0.0
- Agent skills installed: ui-ux-pro-max suite, frontend-design,
  react-best-practices, web-design-guidelines, shadcn, tdd, code-review,
  domain-modeling (project) and find-skills (global)
- Kalameh font family staged at frontend/src/fonts/kalameh (standard + FaNum
  webfont variants, 4 weights each, with FontLicense.txt)
- AGENTS.md guides at root, backend/, frontend/
- Bilingual implementation review documents (docs/reviews/en + fa):
  roadmap, 13-layer engineering review, skills & tooling, improvements
- Repository meta: README, CHANGELOG, VERSION, .gitignore, .gitattributes

### Changed
- None

### Fixed
- None

### Security
- Environment-driven configuration policy established; secrets excluded via
  .gitignore (.env ignored, .env.example only)
