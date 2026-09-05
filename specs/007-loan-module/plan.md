# Implementation Plan: Loan & Guarantee Management

**Branch**: `feature/007-loan-module` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-loan-module/spec.md`

## Summary

Deliver the loan module as its own backend module (`modules/loan`, the first
business module outside warehouse): LoanPolicy per workplace + Jalali year
(loan/guarantee amount caps, yearly and lifetime request counts, active flag,
unique per workplace+year among active policies) and LoanRequest
(employee-owned, type loan|guarantee, positive amount, immutable Jalali year
snapshot, pending → active → settled/cancelled with version-guarded
transitions). Every submission validates against the requesting employee's
workplace policy in the exact §19 order — lifetime count → yearly count →
active loan cap → active guarantee cap — with settled/cancelled/soft-deleted
requests never freeing counts, only active same-year requests binding the
amount caps, and submissions serialized per policy row (`SELECT … FOR
UPDATE`) so cap races resolve to exactly one winner. Jalali year derivation
uses a dependency-free, well-tested conversion function (no new runtime
dependencies, constitution VIII). Loan amounts are masked in audit snapshots
per §21. A bilingual RTL loans console (policies + requests tabs) ships with
the endpoints; gate: all four validation rules proven in order including
settled/soft-deleted semantics, race one-winner, Nowruz boundary math, both
locales RTL-correct, all Phase 1–6 gates stay green.

## Technical Context

**Language/Version**: Python 3.12 (backend venv) · Node 24 / npm 11 (frontend)

**Primary Dependencies**: existing stack only — SQLAlchemy 2.0, Alembic,
Pydantic v2; frontend TanStack Query + Zod; **no new runtime dependencies**
(Jalali conversion is a local pure function, research R4)

**Storage**: PostgreSQL — 2 new tables (`loan_policies`, `loan_requests` +
unique (workplace, year) partial index for policies, type/status/amount
CHECKs, count/cap composite indexes); migration `0007_loan_module`
(reversible, `down_revision = 0006_asset_tracking`)

**Testing**: pytest (unit: Jalali conversion boundaries, validation cascade
order, masking; integration on PG: all four rules, settled/soft-deleted
semantics, submission race one-winner, scope purity, seed idempotency) ·
eslint/tsc/build · extended smoke test

**Target Platform**: Local Windows dev → single Ubuntu VM; GitHub Actions CI

**Performance Goals**: P95 < 200ms for list endpoints at clarified scale
(hundreds of policies/requests per year); indexed count/cap composite
columns; server-side pagination only; validation reads are two indexed
aggregate queries inside the locked transaction

**Constraints**: browser never touches FastAPI (BFF only); every query is
permission AND scope gated (constitution II) — except the deliberate
count/cap aggregates which read all rows including soft-deleted per §19
semantics (research R9); no physical deletes; every lifecycle action audited
with masked snapshots (constitution III); no new deps (constitution VIII)

**Scale/Scope**: 1 new module · 2 new tables · ~10 backend endpoints · 9 new
permission codes + LoanOfficer role mapping · 1 loans console (policies +
requests tabs, forms, filters, transitions) · ~20 tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence / Plan |
|---|---|---|
| I. Spec-driven sequential delivery | ✅ Pass | This cycle; gate = four-rule cascade proven in order + lifecycle + race + boundary tests, browser E2E, locales RTL-correct |
| II. Scoped access on every query | ✅ Enabled | Policy/request listings filter by workplace anchor via `allowed_units`; requester sees own rows (ownership pattern from Phase 5); the only unfiltered reads are the count/cap aggregates inside a locked transaction — a documented §19 semantic exception (research R9) |
| III. Auditability & data integrity | ✅ Pass | UUIDs; soft delete with retirement; version-guarded edits and transitions; every action audited (`LOAN_POLICY_*`, `LOAN_REQUEST_*`) with before/after snapshots; `amount` masked per §21 (research R7); CHECK constraints enforce type/status/amount/year bounds |
| IV. Security & secrets discipline | ✅ Pass | Env-only config; no secrets in code; masked loan amounts in audit |
| V. Bilingual RTL responsive UX | ✅ Pass | `loans.*` namespace in EN/FA; tables collapse to cards <768px; Jalali year display + Farsi digits in `fa`; skeletons; ≥44px targets; reduced motion |
| VI. Modular monolith boundaries | ✅ Pass | First standalone `modules/loan` (per the platform module layout); employee resolution via the user module's published contract (no direct model imports) |
| VII. Standard API contracts | ✅ Pass | Envelope + `BUSINESS_RULE_VIOLATION` (named rule + current/limit details), `STALE_VERSION`, `DUPLICATE_RESOURCE`, `VALIDATION_ERROR`, `AUTHORIZATION_DENIED`; lists `{items, page, page_size, total}` |
| VIII. Simplicity over speculation | ✅ Pass | No new dependencies; no payment integration; no multi-currency; policy-year self-containment per clarified Q3 |

**Post-design re-check**: ✅ Passes — see Complexity Tracking (empty).

## Project Structure

### Documentation (this feature)

```text
specs/007-loan-module/
├── plan.md / research.md / data-model.md / quickstart.md / tasks.md
└── contracts/ (loan-endpoints.md)
```

### Source Code (repository root)

```text
backend/app/
├── common/
│   ├── jalali.py            # NEW: dependency-free Gregorian→Jalali conversion + year helper
│   └── masking.py           # + "amount" sensitive key (§21 loan data)
├── modules/loan/            # NEW module (models, schemas, repository, service, router, contracts)
├── modules/user/contracts.py# + get_loan_requester (employee identity + anchor + is_active)
├── seeds/seed_dev.py        # + 9 loan permission codes, LoanOfficer mapping
└── alembic/versions/0007_loan_module.py

frontend/src/
├── app/api/loan/**          # BFF passthrough (policies, requests, transitions)
├── app/[locale]/(app)/loans/page.tsx
├── features/loans/          # LoansConsole (policies/requests tabs), PolicyForm, LoanForm, transitions
├── lib/client-api.ts        # + loanApi + types
└── messages/{en,fa}.json    # + loans.* namespace, nav href
```

**Structure Decision**: Loans become the first dedicated business module
(`modules/loan/`) per the platform module layout — loans are not warehouse
domain. The module talks to `user` only through its published contract;
validation aggregates run inside a policy-row-locked transaction; the
frontend reuses the requests-console UX pattern (tabs like the warehouse
console, forms like the requests feature).

## Complexity Tracking

> Empty — no constitution violations to justify.
