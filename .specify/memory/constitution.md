<!--
Sync Impact Report
- Version change: (new) -> 1.0.0
- Modified principles: n/a (initial ratification from template scaffold)
- Added sections: Core Principles (I-VIII), Architecture & Technology Constraints,
  Development Workflow & Quality Gates, Governance
- Removed sections: none
- Follow-up TODOs: none
-->

# ZCES — Zarand Coking Enterprise System Constitution

## Core Principles

### I. Spec-Driven, Sequential Delivery

Every capability is delivered through the full Spec Kit cycle — specify, clarify,
plan, analyze, tasks, implement, converge — before the next capability begins.
Phases run strictly in sequence; a phase is done only when its gate passes:
the application boots, all tests are green, and the new capability has been
manually smoke-tested. Task lists favor granularity over brevity: detail is
never sacrificed for the big picture. Rationale: the owner must be able to run
and observe the web application personally after implementation and testing.

### II. Scoped Access on Every Query (NON-NEGOTIABLE)

Authorization requires BOTH a valid permission AND a valid scope
(`Scope:Module:Resource:Operation` at Global / Complex / Workplace level).
Deny is implicit; scopes union; higher levels cover lower ones. No repository
query may execute without applying the mandatory scope filter. Rationale:
access control is the primary risk of this system (see requirements Risk 1).

### III. Auditability & Data Integrity

All primary keys are UUIDs. Physical deletes are forbidden — soft delete with
partial unique indexes on active rows. Sensitive operations are 100% audited
with before/after snapshots, `actor_user_id`, and `trace_id`; sensitive fields
are masked. Employee and User are created in one transaction. Stock never
changes without a matching StockMovement in the same transaction, with row
locking (`SELECT ... FOR UPDATE`) on decrements; inventory may never go
negative. Editable entities use optimistic locking (`version`).

### IV. Security & Secrets Discipline

All configuration is environment-driven; hosts, URLs, and secrets are never
hardcoded (no `localhost`/`127.0.0.1` in code). Secrets never appear in code,
logs, audit snapshots, or exports. Validation always happens in the backend.
Production requires HTTPS, CSRF protection, and hardened cookies
(HttpOnly, SameSite). Authentication uses short-lived access tokens with
refresh token rotation behind the BFF pattern.

### V. Bilingual, RTL, Responsive, Animated UX (NON-NEGOTIABLE)

Every user-facing page MUST be fully bilingual (English + Persian), fully
responsive (breakpoints 480/768/1024/1280, touch targets >= 44px), RTL-correct
for the Persian locale (logical CSS properties, Kalameh FaNum font with Farsi
digits, Jalali calendar), and animated with smooth transitions
(150-300ms, skeletons, `prefers-reduced-motion` respected). These four are
acceptance criteria for every frontend task, not afterthoughts. The design
system in `frontend/DESIGN.md` is the single source of truth for visual work.

### VI. Modular Monolith Boundaries

The system is one deployable with independent internal modules (user,
warehouse, loan, notification, audit, settings). Modules never touch another
module's models or repositories directly — cross-module access goes through
published contracts only. Layering is strict: router -> service -> repository
-> database; business logic lives in services, queries in repositories.

### VII. Standard API Contracts

All errors use the envelope `{code, message, details, trace_id}` with the
standard error-code set. All list endpoints paginate with the
`{items, page, page_size, total}` response. Every request carries a trace id
correlated across frontend, backend, and workers. Notification failures never
break the main transaction unless explicitly Critical (Outbox pattern).

### VIII. Simplicity Over Speculative Infrastructure

Version 1 targets local Windows development and a single Ubuntu VM
(systemd + Nginx + PostgreSQL + Redis) — no Docker, cloud, CDN, load
balancers, or multi-node HA before the MVP is stable. Every layer added must
be justified by a current requirement, not a future one. Redis is used for
cache/Celery/SSE only when the phase that needs it arrives.

## Architecture & Technology Constraints

- Architecture: Modular Monolith (FastAPI backend, Next.js BFF + frontend).
- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2,
  Celery + Redis. Frontend: Next.js App Router, TypeScript strict, Tailwind
  CSS, shadcn/ui, React Hook Form + Zod, TanStack Query, next-intl.
- Data: PostgreSQL (primary store; running locally as a Windows service),
  Redis via WSL2 on dev machines. UUID keys, soft delete, partial unique
  indexes, optimized/constraint-driven schema.
- Organization hierarchy: Company -> Complex -> Workplace -> Employee.
  Each employee belongs to exactly one workplace.
- Fixed layer decisions (13-layer review): full implementation of Layers
  1,2,3,4,12; scoped implementation of 5,7,8,9,10,13; Layers 6 and 11 are
  explicitly out of scope for v1. See `docs/reviews/en/02-layers-review.md`.
- Version 1 exclusions per requirements section 3.2 (mobile apps, ERP
  integration, object storage, OCR, full multi-tenancy, SMS, push, complex
  BPM) are binding.

## Development Workflow & Quality Gates

- Workflow: one Spec Kit cycle per phase (`/speckit.specify` ->
  `/speckit.clarify` -> `/speckit.plan` -> `/speckit.analyze` ->
  `/speckit.tasks` -> `/speckit.implement` -> `/speckit.converge`, repeating
  implement/converge until Converged).
- Testing: unit tests for services, validators, scope resolution, and the
  loan validation cascade; integration tests for repositories, scope filters,
  constraints, and endpoints; E2E tests for the critical flows listed in
  requirements section 27.3. Tests are part of each task, not a follow-up.
- Git: Conventional Commits; branches `feature/*`, `fix/*`, `hotfix/*`,
  `release/*`; `main` stays deployable; Semantic Versioning; changelog kept
  per release.
- CI: GitHub Actions runs backend (ruff, mypy, pytest) and frontend (eslint,
  tsc, next build) checks from Phase 1 onward.
- Frontend quality gate: no task closes with hardcoded UI strings, a
  non-responsive page, a broken RTL layout, or missing reduced-motion
  handling.

## Governance

This constitution supersedes all other practice documents. Source requirement
truth: `docs/requirements-prompt.txt` (Persian). If code and requirements
disagree, work stops and the discrepancy is raised before proceeding.
Amendments require a documented rationale, a version bump (MAJOR for removals
or redefinitions, MINOR for additions, PATCH for clarifications), and a
migration note for affected in-flight specs. All specs, plans, and task lists
must be checked against this constitution during `/speckit.analyze`.

**Version**: 1.0.0 | **Ratified**: 2026-08-29 | **Last Amended**: 2026-08-29
