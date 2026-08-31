# Implementation Plan: Organizational Structure & Employee/User Management

**Branch**: `feature/003-org-user-module` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-org-user-module/spec.md`

## Summary

Deliver the organizational backbone and the first business module: Company →
Complex → Workplace seeded per requirements §5; employees created together with
their mandatory 1:1 user account in a single transaction (bcrypt initial
password, masked audit); partial unique indexes making `national_id` and
`personnel_code` unique among active employees (soft-deleted rows never block
reuse); a scope-filtered, paginated employee directory with search and a
status filter (server-side pagination through the BFF); immutable identity
anchors with version-guarded edits and workplace moves within the editor's
scope; deactivation that cascades to the linked user and revokes their refresh
sessions (reactivation restores both); an audited administrator password reset
(clarify Q1); and the management UI for roles/permissions/scope assignment
surfacing the Phase-2 admin endpoints. Gate: employee CRUD verified in the
browser, duplicates blocked, deactivate→sign-out cascade observed, both
locales RTL-correct, all Phase 1–2 gates stay green.

## Technical Context

**Language/Version**: Python 3.12 (backend venv) · Node 24 / npm 11 (frontend)

**Primary Dependencies**: existing stack only — SQLAlchemy 2.0, Alembic,
Pydantic v2, bcrypt (already present); frontend: TanStack Query +
React Hook Form + Zod; no new runtime dependencies

**Storage**: PostgreSQL — 4 new tables (companies, complexes, workplaces,
employees) + 1 column on users (employee linkage) + partial unique indexes;
migration `0003_org_user_module` (reversible)

**Testing**: pytest (unit: validators, employee service transaction/cascade;
integration: scoped repositories, partial indexes, endpoints, seed idempotency)
· eslint/tsc/build · extended smoke test (employee create→sign-in→deactivate)

**Target Platform**: Local Windows dev → single Ubuntu VM; GitHub Actions CI

**Performance Goals**: P95 < 200ms for list/search endpoints at this scale
(thousands of employees); indexed search columns; server-side pagination only

**Constraints**: browser never touches FastAPI (BFF only); every repository
query carries the scope filter (constitution II); no physical deletes; audit
writes transactional for critical events; Redis still not needed; no Celery
yet (no async work in this phase)

**Scale/Scope**: 4 new tables · ~10 employee/org endpoints · 2 org-seeded
levels · 4 new UI surfaces (employees list/create/edit, user role/scope
management) · ~50 tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence / Plan |
|---|---|---|
| I. Spec-driven sequential delivery | ✅ Pass | This cycle; gate = browser-verified CRUD + duplicates blocked + deactivate cascade |
| II. Scoped access on every query | ✅ Enabled | Employee/org repositories take ScopeContext; every list/detail/mutation filters by Global>Complex>Workplace coverage; denial never leaks existence |
| III. Auditability & data integrity | ✅ Pass | UUIDs; soft delete everywhere; partial unique indexes on active rows; Employee+User one transaction; optimistic locking (`version`) on employee edits; audit with masked before/after on all mutations |
| IV. Security & secrets discipline | ✅ Pass | Passwords bcrypt-hashed, never logged/audited; masking helpers reused (national_id masked); env-only config; validation in backend |
| V. Bilingual RTL responsive UX | ✅ Pass | All strings via EN/FA dictionaries; forms and tables responsive (tables collapse to cards <768px); Jalali dates for `fa`; touch targets ≥44px; reduced-motion respected |
| VI. Modular monolith boundaries | ✅ Pass | New `modules/user` org/employee domain stays in the user module (owner per §9.1); other modules consume via `contracts.py` (`get_employee_by_id`, `get_employee_workplace`, `search_employees`, `is_employee_active`) |
| VII. Standard API contracts | ✅ Pass | Standard envelope + error codes (`DUPLICATE_RESOURCE`, `VALIDATION_ERROR`, `CONFLICT_CONCURRENT_UPDATE`, `AUTHORIZATION_DENIED`); list endpoints `{items, page, page_size, total}` |
| VIII. Simplicity over speculation | ✅ Pass | No Redis/Celery/queues; no email/invitation flows; password reset is a simple admin action; org editor for complexes/workplaces deferred (seed-provided) |

**Post-design re-check**: ✅ Passes — see Complexity Tracking (empty).

## Project Structure

### Documentation (this feature)

```text
specs/003-org-user-module/
├── plan.md / research.md / data-model.md / quickstart.md / tasks.md
└── contracts/ (employee-endpoints.md, employee-contract.md)
```

### Source Code (repository root)

```text
backend/app/
├── modules/user/
│   ├── models.py        # + Company, Complex, Workplace, Employee; users.employee_id
│   ├── schemas.py       # + OrgOut, EmployeeIn/Out, EmployeeUpdateIn, PasswordSetIn …
│   ├── org_repository.py    # company/complex/workplace scoped reads (+ cache-free)
│   ├── employee_repository.py  # scope-filtered employee queries (search/filter)
│   ├── employee_service.py  # create-with-user txn, edit/move, deactivate/reactivate,
│   │                       # password reset; audit writes; validation cascade
│   ├── router.py        # + /employees CRUD, /org/{complexes,workplaces}, /users/{id}/password
│   ├── contracts.py     # + get_employee_by_id, get_employee_workplace,
│   │                    # search_employees, is_employee_active
│   └── tests/           # unit + integration (PG)
├── seeds/
│   ├── seed_dev.py      # + org tree (company, 2 complexes, 4 workplaces) idempotent
│   └── seed_prod.py     # + same org tree (no demo employees)
└── alembic/versions/0003_org_user_module.py

frontend/src/
├── app/api/[...]        # BFF passthrough routes for new endpoints (cookie+CSRF)
├── features/employees/  # EmployeeTable, EmployeeForm (create/edit), status filter,
│                        # deactivate/reactivate confirm, workplace picker
├── features/admin/      # RolesView, PermissionsView, UserAccessManager (role/scope)
├── lib/api.ts           # + typed fetchers, Zod schemas mirroring backend DTOs
└── messages/{en,fa}.json  # employees.*, org.*, admin.* keys
```

**Structure Decision**: The user module owns org + employee data (requirements
§9.1); separate repository files keep org-tree reads apart from employee
queries but share one module. Frontend gets two new feature folders following
the established shell; BFF gains passthrough route handlers — no new deps.

## Complexity Tracking

> Empty — no constitution violations to justify.
