# Implementation Plan: Item Request Flow

**Branch**: `feature/005-item-requests-flow` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-item-requests-flow/spec.md`

## Summary

Deliver the item-request flow inside the warehouse module (requirements §9.2
owns ItemRequest/ItemRequestLine there): employees self-service submit
requests (≥1 line from the live catalog picker + purpose description) that
start pending; WarehouseApprover decides approve/reject (version-guarded,
only from pending, audited); keepers fulfill approved requests by selecting
a stock placement per line — every line decremented through the Phase-4
contract `apply_fulfillment_issue` (FOR UPDATE, fulfillment movements,
alert evaluation) in one all-or-nothing transaction, refused atomically with
per-line detail when stock is short. Requests are visible to their requester
always and to warehouse actors within their organizational scope; every
transition is audited (created/approved/rejected/fulfilled mirror the
§20 domain events). Bilingual RTL requests console with a line editor,
status filters, and permission-gated actions. Gate: E2E request →
approve → fulfill in the browser with stock verified to move, overdraw
refused atomically, both locales RTL-correct, all Phase 1–4 gates stay green.

## Technical Context

**Language/Version**: Python 3.12 (backend venv) · Node 24 / npm 11 (frontend)

**Primary Dependencies**: existing stack only — SQLAlchemy 2.0, Alembic,
Pydantic v2; frontend TanStack Query + React Hook Form + Zod; **no new
runtime dependencies** (fulfillment reuses the Phase-4 contract and ledger)

**Storage**: PostgreSQL — 2 new tables (`item_requests`,
`item_request_lines` + status CHECK + quantity CHECK + request FK indexes);
migration `0005_item_requests_flow` (reversible,
`down_revision = 0004_warehouse_catalog_inventory`)

**Testing**: pytest (unit: status transition guards, line validation;
integration on PG: creation validation, decision races via version guard,
fulfillment atomicity + overdraw + concurrency across requests, scope-filtered
visibility, seed idempotency) · eslint/tsc/build · extended smoke test

**Target Platform**: Local Windows dev → single Ubuntu VM; GitHub Actions CI

**Performance Goals**: P95 < 200ms for request list/detail endpoints at the
clarified scale (hundreds of requests); indexed list columns; server-side
pagination only

**Constraints**: browser never touches FastAPI (BFF only); decision and
fulfillment require permission AND scope (constitution II); fulfillment is
one transaction per request — atomic, row-locked, no negative stock
(constitution III); requests are immutable flow history (no delete); no new
infrastructure (constitution VIII)

**Scale/Scope**: 2 new tables · ~8 backend endpoints · 3 new permission codes
+ role-mapping updates · 1 requests console (compose + list + decide +
fulfill) reusing the Phase-4 item combobox · ~45 tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence / Plan |
|---|---|---|
| I. Spec-driven sequential delivery | ✅ Pass | This cycle; gate = browser E2E request→approve→fulfill, atomic overdraw refusal, locales RTL-correct |
| II. Scoped access on every query | ✅ Enabled | Decide/fulfill/scope-list: permission + scope via the request's workplace anchor (allowed_units); requester-own access is ownership-scoped (requested_by = caller, the /auth/me precedent) — documented decision R5 |
| III. Auditability & data integrity | ✅ Pass | UUIDs; requests immutable (no delete paths); version-guarded decisions; fulfillment atomically decrements via the Phase-4 contract (FOR UPDATE + ledger + alert evaluation) and audits every transition with snapshots |
| IV. Security & secrets discipline | ✅ Pass | No secrets; env-only config; backend-side validation; standard masking (no sensitive fields in request snapshots) |
| V. Bilingual RTL responsive UX | ✅ Pass | `requests.*` namespace in EN/FA; line editor + tables collapse to cards <768px; Jalali timestamps in `fa`; skeletons; ≥44px targets; reduced-motion |
| VI. Modular monolith boundaries | ✅ Pass | Requests live in `modules/warehouse` (§9.2 owner) and consume the module's own published contract for stock decrements; user module supplies requester workplace anchoring via its existing contract |
| VII. Standard API contracts | ✅ Pass | Envelope + `INSUFFICIENT_STOCK`, `BUSINESS_RULE_VIOLATION`, `STALE_VERSION`, `VALIDATION_ERROR`, `AUTHORIZATION_DENIED`; lists `{items, page, page_size, total}` |
| VIII. Simplicity over speculation | ✅ Pass | Whole-request fulfillment; no per-line states; no cancel flow; no notifications (Phase 8 reads the audited transitions); no new deps |

**Post-design re-check**: ✅ Passes — see Complexity Tracking (empty).

## Project Structure

### Documentation (this feature)

```text
specs/005-item-requests-flow/
├── plan.md / research.md / data-model.md / quickstart.md / tasks.md
└── contracts/ (item-request-endpoints.md)
```

### Source Code (repository root)

```text
backend/app/
├── modules/warehouse/
│   ├── models.py           # + ItemRequest, ItemRequestLine, RequestStatus
│   ├── schemas.py          # + RequestCreateIn (lines), RequestOut, RequestLineOut,
│   │                       #   DecisionIn, FulfillIn (per-line placement picks)
│   ├── request_repository.py  # scope/ownership-filtered request queries
│   ├── request_service.py  # create / decide / fulfill (calls contracts.apply_fulfillment_issue)
│   ├── router.py           # + /warehouse/requests endpoints
│   └── tests/              # backend/tests/test_item_requests_*.py
├── seeds/seed_dev.py       # + 3 request permissions, role mappings
└── alembic/versions/0005_item_requests_flow.py

frontend/src/
├── app/api/warehouse/requests/**   # BFF passthrough
├── app/[locale]/(app)/requests/page.tsx
├── features/requests/      # RequestsView (list + filters), RequestForm (line editor
│                           # with ItemSearchCombobox), DecisionButtons, FulfillDialog
├── lib/client-api.ts       # + requestApi + types
└── messages/{en,fa}.json   # + requests.* namespace, nav entry
```

**Structure Decision**: Requests belong to the warehouse module per
requirements §9.2 — one module owns the whole stock domain, and fulfillment
reuses the module's own published contract. Frontend gets one route with a
compose dialog and a filterable list; the Phase-4 `ItemSearchCombobox` is
reused per line.

## Complexity Tracking

> Empty — no constitution violations to justify.
