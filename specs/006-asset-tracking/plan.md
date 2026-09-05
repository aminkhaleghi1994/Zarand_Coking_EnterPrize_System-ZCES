# Implementation Plan: Asset Tracking

**Branch**: `feature/006-asset-tracking` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-asset-tracking/spec.md`

## Summary

Deliver asset tracking inside the warehouse module (requirements §9.2 owns
AssetInstance/AssetHistory): asset registration with bilingual names and
required serial numbers (normalized partial-unique among active assets,
reusable after retirement, retirement blocked while assigned), assignment to
active in-scope employees or free-text locations (current holder recorded,
target-typed), returns clearing the holder, and an immutable per-asset
history timeline (created / assigned / returned / retired, newest first).
Assignment and return are version-guarded (§25 concurrency-sensitive: races
resolve to exactly one winner) and audited with the §18 events
(`ASSET_ASSIGNED` / `ASSET_RETURNED`). Scope-filtered visibility follows the
established workplace-anchored pattern; a bilingual RTL assets console
provides register/edit/retire/assign/return actions with an employee picker
and a history drawer. Gate: browser E2E register → assign → history →
return, duplicate serial refused, retirement blocked while assigned, both
locales RTL-correct, all Phase 1–5 gates stay green.

## Technical Context

**Language/Version**: Python 3.12 (backend venv) · Node 24 / npm 11 (frontend)

**Primary Dependencies**: existing stack only — SQLAlchemy 2.0, Alembic,
Pydantic v2; frontend TanStack Query + Zod; **no new runtime dependencies**

**Storage**: PostgreSQL — 2 new tables (`asset_instances`,
`asset_histories` + holder-state CHECK, serial partial unique, history
indexes); migration `0006_asset_tracking` (reversible,
`down_revision = 0005_item_requests_flow`)

**Testing**: pytest (unit: holder-state validation, serial normalization;
integration on PG: duplicate serials, retirement blocking, assignment/return
races via version guard, scope-filtered visibility, seed idempotency) ·
eslint/tsc/build · extended smoke test

**Target Platform**: Local Windows dev → single Ubuntu VM; GitHub Actions CI

**Performance Goals**: P95 < 200ms for list/detail endpoints at clarified
scale (hundreds of assets); indexed serial/search columns; server-side
pagination only

**Constraints**: browser never touches FastAPI (BFF only); assign/return
require permission AND scope (constitution II); no physical deletes; every
lifecycle action audited with snapshots (constitution III); no new deps
(constitution VIII)

**Scale/Scope**: 2 new tables · ~8 backend endpoints · 6 new permission
codes + role mappings · 1 assets console (list + register/assign/return +
history drawer) · ~16 tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence / Plan |
|---|---|---|
| I. Spec-driven sequential delivery | ✅ Pass | This cycle; gate = browser E2E register→assign→history→return, duplicate refusal, blocked retirement, locales RTL-correct |
| II. Scoped access on every query | ✅ Enabled | Asset list/detail/mutations filter by the asset's workplace anchor via `allowed_units`; anchorless rows visible only to global + their creator — mirrors the Phase-5 request pattern (research R6) |
| III. Auditability & data integrity | ✅ Pass | UUIDs; soft delete with reuse; version-guarded assign/return/update/retire; immutable append-only history table; holder-state CHECK constraint; every action audited with snapshots |
| IV. Security & secrets discipline | ✅ Pass | No secrets; env-only config; backend validation; no sensitive fields in snapshots |
| V. Bilingual RTL responsive UX | ✅ Pass | `assets.*` namespace in EN/FA; history drawer; tables collapse to cards <768px; Jalali timestamps in `fa`; skeletons; ≥44px targets |
| VI. Modular monolith boundaries | ✅ Pass | Assets live in `modules/warehouse` (§9.2 owner); employee targets resolved through the user module's published contract |
| VII. Standard API contracts | ✅ Pass | Envelope + `BUSINESS_RULE_VIOLATION`, `STALE_VERSION`, `DUPLICATE_RESOURCE`, `VALIDATION_ERROR`, `AUTHORIZATION_DENIED`; lists `{items, page, page_size, total}` |
| VIII. Simplicity over speculation | ✅ Pass | Single-holder model; free-text locations (no registry); no maintenance scheduling; no new deps |

**Post-design re-check**: ✅ Passes — see Complexity Tracking (empty).

## Project Structure

### Documentation (this feature)

```text
specs/006-asset-tracking/
├── plan.md / research.md / data-model.md / quickstart.md / tasks.md
└── contracts/ (asset-endpoints.md)
```

### Source Code (repository root)

```text
backend/app/
├── modules/warehouse/
│   ├── models.py           # + AssetInstance, AssetHistory, HolderType, AssetAction
│   ├── schemas.py          # + AssetCreateIn/UpdateIn/Out, AssignIn, ReturnIn, HistoryOut
│   ├── asset_repository.py # scope-filtered asset queries + history writes/reads
│   ├── asset_service.py    # create/update/retire/assign/return with version guards
│   ├── router.py           # + /warehouse/assets endpoints
│   └── tests/              # backend/tests/test_asset_*.py
├── seeds/seed_dev.py       # + 6 asset permission codes, role mappings
└── alembic/versions/0006_asset_tracking.py

frontend/src/
├── app/api/warehouse/assets/**   # BFF passthrough
├── app/[locale]/(app)/assets/page.tsx
├── features/assets/        # AssetsView, AssetForm, AssignDialog, HistoryDrawer
├── lib/client-api.ts       # + assetApi + types
└── messages/{en,fa}.json   # + assets.* namespace, nav href
```

**Structure Decision**: Same-module ownership per §9.2 with dedicated
repository/service files (the Phase-4/5 file-per-aggregate pattern); the
frontend reuses the requests-console UX pattern and the Phase-3 employees
API for the assignment picker.

## Complexity Tracking

> Empty — no constitution violations to justify.
