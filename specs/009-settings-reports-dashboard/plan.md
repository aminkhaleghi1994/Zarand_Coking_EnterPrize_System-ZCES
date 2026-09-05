# Implementation Plan: Settings, Reports & Management Dashboard

**Branch**: `feature/009-settings-reports-dashboard` | **Date**: 2026-09-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-settings-reports-dashboard/spec.md`

## Summary

Phase 9 delivers the settings, reporting and dashboard surface over the
modules shipped in Phases 1–8. Technical approach: a new `settings` module
(global typed key/value store, version-guarded, audited updates) and a new
`reports` module (read-only, scope-filtered projections over existing
data via module contracts; openpyxl workbook export streamed through the
same scope+masking rules). The audit module gains a filtering contract
used by the reports module's sensitive-operations report. The frontend
gains a management dashboard page (scope-filtered counters + breakdowns),
report pages with export buttons, and a settings page — all bilingual
(en/fa, Jalali for fa, RTL) per constitution V.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript strict (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2,
openpyxl (NEW — Excel workbook generation, write-only mode); Next.js App
Router, TanStack Query, next-intl

**Storage**: PostgreSQL (settings table via migration `0009`; reports
add no storage — they project existing rows)

**Testing**: pytest (unit: settings validation, masking-on-export,
aggregation math; integration: endpoints, scope filters, export bytes,
audit of setting changes) + frontend `npm run lint` / `tsc` / `next build`

**Target Platform**: Windows dev → single Ubuntu VM (same as previous phases)

**Performance Goals**: report/dashboard p95 under 500ms (requirements §28);
export of one filtered page (≤ page_size bound) completes within request
timeout; dashboard uses count queries only (no row materialization)

**Constraints**: every report query applies the mandatory scope filter
(constitution II); masking identical on screen and in Excel (FR-002/
FR-013); settings updates optimistic-locked and audited in-transaction
(FR-009); no new runtime infra (constitution VIII)

**Scale/Scope**: 1 migration, 2 backend modules, ~5 BFF route groups,
3 frontend feature areas (dashboard upgrade, reports, settings)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How satisfied |
|---|---|---|
| I. Spec-driven sequential | Pass | This is one full Spec Kit cycle for Phase 9, after Phase 8 converged |
| II. Scoped access every query | Pass | Every report/dashboard query takes ScopeContext and applies unit filters; repository layer only |
| III. Auditability & integrity | Pass | Settings table: UUID key, no physical delete, version column; updates audited with before/after (masked) snapshots in-transaction |
| IV. Security & secrets | Pass | No secrets in settings values (validation rejects known secret-ish keys); export never writes unmasked values without `audit:log:read_full` |
| V. Bilingual RTL responsive animated | Pass | All three UI areas bilingual with Jalali/RTL; responsive breakpoints; skeletons + reduced motion |
| VI. Modular monolith boundaries | Pass | reports/settings talk to other modules ONLY through `contracts.py` interfaces |
| VII. Standard API contracts | Pass | List endpoints paginate `{items,page,page_size,total}`; errors use the envelope; trace ids flow |
| VIII. Simplicity over speculative infra | Pass | No Celery/Redis additions; synchronous exports bounded by pagination; global-only settings (user decision) |

No violations — no complexity-tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/009-settings-reports-dashboard/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── reports-settings-endpoints.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── 0009_settings.py                 # settings table (reversible)
├── app/
│   ├── modules/
│   │   ├── settings/
│   │   │   ├── models.py                # Setting model
│   │   │   ├── schemas.py               # SettingOut / SettingUpdate
│   │   │   ├── repository.py            # scope-checked (global op) queries
│   │   │   ├── service.py               # version guard + audit + emit
│   │   │   ├── router.py                # GET/PATCH /settings
│   │   │   ├── contracts.py             # get_setting contract for other modules
│   │   │   └── defaults.py              # fixed key set + typed defaults
│   │   └── reports/
│   │       ├── schemas.py               # report row DTOs + aggregate DTOs
│   │       ├── service.py               # scope-resolved aggregation + masking
│   │       ├── excel.py                 # openpyxl workbook builder (bilingual headers)
│   │       └── router.py                # /reports/* endpoints incl. export
│   ├── modules/audit/
│   │   └── contracts.py                 # NEW: filtered audit-page contract for reports
│   └── seeds/seed_dev.py                # + settings permissions + role maps + defaults
└── tests/
    ├── test_settings_module.py
    ├── test_settings_contracts.py
    ├── test_reports_dashboard.py
    ├── test_reports_inventory.py
    ├── test_reports_requests.py
    ├── test_reports_loans.py
    ├── test_reports_audit.py
    └── test_reports_export.py

frontend/
├── src/app/api/
│   ├── settings/route.ts                # GET list, PATCH {key}
│   ├── reports/dashboard/route.ts
│   ├── reports/inventory/route.ts
│   ├── reports/requests/route.ts
│   ├── reports/loans/route.ts
│   ├── reports/audit/route.ts
│   └── reports/export/route.ts          # file passthrough (Content-Disposition)
└── src/features/
    ├── dashboard/ (upgrade existing home) # counters + breakdown cards
    ├── reports/                         # ReportsConsole + report tables + export button
    └── settings/                        # SettingsConsole + typed setting forms
```

**Structure Decision**: matches the established modular monolith layout
(modules with models/schemas/repository/service/router/contracts; BFF
route per backend endpoint group; features/ per frontend area). The
reports module owns no repository — it consumes other modules'
contracts, keeping constitution VI intact; each source module's
repository keeps its scope filter and the reports service composes
filtered pages.

## Complexity Tracking

> None — no constitution violations to justify.
