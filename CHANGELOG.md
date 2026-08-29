# Changelog

All notable changes to this project are documented here. The format is based
on Keep a Changelog, and this project adheres to Semantic Versioning.

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
