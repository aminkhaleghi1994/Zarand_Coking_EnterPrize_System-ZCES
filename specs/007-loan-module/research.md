# Research: Loan & Guarantee Management

**Feature branch**: `feature/007-loan-module` | **Date**: 2026-09-01
**Inputs**: spec.md (clarified 2026-09-01), requirements §19 §21, roadmap,
platform patterns from Phases 2–6.

---

## R1 — Module ownership

**Decision**: Loans live in a new dedicated module `backend/app/modules/loan/`
(models, schemas, repository, service, router, contracts) — the first business
module outside warehouse.

**Rationale**: The platform module layout explicitly reserves `loan`; §19
defines loans as their own domain (policies + requests), unrelated to stock.
Keeping it separate honors constitution VI (modules talk through contracts
only) and prevents the warehouse module from accreting unrelated aggregates.

**Alternatives considered**: inside `modules/warehouse` (rejected — wrong
domain, warehouse is inventory-centric); inside `modules/user` (rejected —
employees are only the subject, not the owner).

## R2 — Validation cascade and race-proofing

**Decision**: Validation runs inside the submission transaction with a
`SELECT … FOR UPDATE` on the target policy row; the four rules evaluate in
the exact §19 order and the first failure raises `BUSINESS_RULE_VIOLATION`
with `details` naming the rule and current/limit values.

**Rationale**: Row-locking the policy serializes concurrent submissions per
workplace+year — the same proven pattern as stock decrements (constitution
golden rule 8) — so two submissions racing the last count slot or the last
rial of a cap resolve to exactly one winner (SC-003). Per-rule ordering is a
verbatim requirements mandate; a single combined "over policy" refusal would
violate FR-005.

**Alternatives considered**: optimistic re-check after insert (racy, rejects
late); advisory locks (less discoverable than a row lock tied to real data);
no lock (accepting rare over-cap races — violates SC-003).

## R3 — Counting and capping semantics (verbatim §19)

**Decision**:

- **Counts (lifetime / yearly)**: count every request row of the employee
  regardless of status **and regardless of `deleted_at`** — settled,
  cancelled, and soft-deleted all keep consuming counts. The yearly count
  filters on the request's `year` snapshot = the validated year.
- **Amount caps (loan / guarantee)**: sum `amount` of requests with
  `status = 'active'` **and `year = validated year`** (clarified Q3), type-
  matched to the rule being evaluated. Settling or cancelling frees the
  commitment. A soft-deleted active request still counts (its row remains
  with status active) — settling it later frees it.
- The new request itself does not count toward its own validation (it is
  not yet persisted when rules run).

**Rationale**: Direct transcription of §19's four calculation rules plus the
clarified cancelled semantics; year-scoped caps keep each policy year a
self-contained budget (Q3).

**Alternatives considered**: excluding soft-deleted from counts (contradicts
§19 "soft deleted do not free the count limits"); counting all-year active
commitments toward the current cap (rejected in Q3).

## R4 — Jalali year math without new dependencies

**Decision**: A small pure module `app/common/jalali.py` implementing the
standard Gregorian→Jalali conversion (the widely used jalaali algorithm:
JalaliCalculations breaks/g2j) plus `current_jalali_year(now)`; exhaustive
unit tests around Nowruz boundaries (e.g. 2026-03-20 → 1404, 2026-03-21 →
1405; Esfand 29/30 leap handling).

**Rationale**: Constitution VIII forbids speculative dependencies; the
conversion algorithm is ~40 lines, deterministic, and unit-testable. The
`year` stored on requests and policies is an integer Jalali year
(e.g. 1405); validation compares request year to policy year directly.

**Alternatives considered**: `jdatetime` library (new dependency — rejected);
storing Gregorian years (contradicts §19 "سال محاسباتی براساس سال جلالی
است"); deriving year in SQL (non-portable, harder to test).

## R5 — Permissions, roles, scope

**Decision**: 9 seeded permission codes, idempotent, following the
`module:resource:operation` convention:

- `loan:policy:create` `read` `update` `retire`
- `loan:request:create` `read` `activate` `settle` `cancel`

Role mappings: `LoanOfficer` += all nine; `SuperAdmin` += all (existing
pattern grants SuperAdmin every code); no other role changes.

**Rationale**: Mirrors the warehouse asset naming (Phase 6) and the existing
seeded `LoanOfficer` role description ("مدیریت سیاست‌ها و درخواست‌های وام").
Separate transition operations keep RBAC auditable and let an org grant
settle-only rights later without code changes.

**Alternatives considered**: one `loan:request:manage` operation (rejected —
coarser than needed); granting employees read of all requests (rejected —
FR-013 ownership scoping covers self-service visibility without a permission).

## R6 — Visibility and scope model

**Decision**: 

- **Policies**: visible with `loan:policy:read` + scope (`allowed_units` on
  the policy's workplace anchor); writes additionally require the matching
  operation and in-scope workplace target (assign-target style check).
- **Requests**: two-tier like Phase 5 item requests — any active signed-in
  user sees **their own** requests (ownership filter, no permission needed
  for self-view beyond authentication); users with `loan:request:read` +
  scope see their units' requests. Out-of-scope detail fetches return the
  standard not-found envelope without existence leak.

**Rationale**: Consistency with the established self-service pattern
(requests, Phase 5) and constitution II (permission AND scope for shared
data; ownership for personal data).

**Alternatives considered**: requiring `loan:request:create` to see own
requests (unnecessary gate on self-service); exposing policies to employees
(rejected — policies are officer tooling).

## R7 — Audit actions and masking

**Decision**: Audit actions `LOAN_POLICY_CREATED` / `LOAN_POLICY_UPDATED` /
`LOAN_POLICY_RETIRED` / `LOAN_REQUEST_CREATED` / `LOAN_REQUEST_ACTIVATED` /
`LOAN_REQUEST_SETTLED` / `LOAN_REQUEST_CANCELLED`, written with before/after
snapshots and `trace_id`. Extend `app/common/masking.py` with `"amount"` as
a sensitive key (full `***` mask) so loan amounts never appear in audit
snapshots (§21 lists loan data as sensitive; snapshots serialize amounts as
strings so the existing string-based masker applies).

**Rationale**: §21 explicitly requires masking of loan data in logs; the
existing masker is string-keyed, so snapshot amounts are rendered as strings
before masking. Entity data in the API remains permission-gated as usual —
only the audit trail is masked.

**Alternatives considered**: masking only partial digits (§21 says mask;
full mask is the safe reading); leaving amounts unmasked (violates §21).

## R8 — Money representation and formatting

**Decision**: `amount` columns are `Numeric(18, 2)`; API payloads carry
amounts as strings with exactly two decimals (mirrors the quantity
string discipline of Phase 4: `format_quantity` analog
`format_money`); UIs format with locale-appropriate thousand separators
(Latin digits in `en`, native Farsi digits in `fa` via the Kalameh FaNum
font) — no digit conversion in code for `fa`.

**Rationale**: Rial-scale amounts need 18 digits of headroom; string amounts
avoid float drift end-to-end and keep Zod/Pydantic validation symmetric.

**Alternatives considered**: integer Rials only (loses future support for
fractional amounts); float (float drift — rejected).

## R9 — Soft-delete query inversion (deliberate, documented)

**Decision**: The repository's count/cap aggregate queries deliberately DO
NOT filter `deleted_at` (§19: soft-deleted requests keep counting); every
other read (listings, detail, policy lookup for validation "active policy")
filters to active rows via the standard partial-index pattern. This
exception is confined to two named aggregate helpers with docstrings citing
§19, so the "every query is scoped/active" default stays intact elsewhere.

**Rationale**: §19's semantics make non-deleted-only aggregates the correct
behavior; documenting the two exceptions prevents future "cleanup" from
silently breaking the cascade.

**Alternatives considered**: a separate `is_counted` flag synced on delete
(extra state to keep consistent — rejected); physical delete of requests
(violates constitution II).

## R10 — API shapes

**Decision** (full I/O in `contracts/loan-endpoints.md`):

- `GET/POST /loan/policies`, `GET/PATCH /loan/policies/{id}`,
  `POST /loan/policies/{id}/retire`
- `GET/POST /loan/requests`, `GET /loan/requests/{id}`
- `POST /loan/requests/{id}/activate|settle|cancel`

All list endpoints return `{items, page, page_size, total}`; mutations take
`version` for optimistic locking (policies, transitions). Validation errors
carry `details.rule` ∈ {`lifetime_count`, `yearly_count`, `loan_cap`,
`guarantee_cap`, `no_policy`} plus current/limit values.

**Rationale**: Exact §19 rule naming in error details makes acceptance
tests (SC-001) mechanical; transition endpoints mirror the asset
assign/return pattern of Phase 6.

**Alternatives considered**: a single PATCH-based status field (loses
audit-friendly transitions and per-operation permissions); embedding
validation in GET (nonsensical).

## R11 — Frontend console pattern

**Decision**: `features/loans/LoansConsole.tsx` with two tabs (Policies,
Requests) reusing the warehouse console tab pattern; `PolicyForm` and
`LoanForm` mirror the requests/asset forms (React state + Zod schemas in
`lib/schemas.ts`, messages under `loans.*`); transitions inline per card
(activate/settle/cancel confirmations like asset retire); filter chips for
type/status/year; tables collapse to cards below 768px; Jalali year labels
in `fa` with native Farsi digits.

**Rationale**: Direct reuse of proven Phase 4–6 console components keeps
velocity and visual consistency; no new component primitives needed.

**Alternatives considered**: separate pages per entity (more nav noise);
modals for transitions (the inline confirm pattern is already established).
