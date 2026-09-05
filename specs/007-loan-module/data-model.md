# Data Model: Loan & Guarantee Management

**Feature branch**: `feature/007-loan-module` | **Date**: 2026-09-01
**Source**: spec.md (clarified), requirements §19, research.md decisions.

---

## Entities

### LoanPolicy (`loan_policies`)

Master data defining one workplace's rules for one Jalali year.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID PK | | |
| workplace_id | UUID FK → workplaces.id | NOT NULL, RESTRICT delete | scope anchor; indexes |
| complex_id | UUID | NULLABLE | denormalized anchor (like assets/requests) for complex-scope filtering |
| company_id | UUID | NULLABLE | denormalized anchor |
| year | INTEGER | NOT NULL, CHECK 1300–1500 | Jalali year; part of the uniqueness pair |
| max_loan_amount | NUMERIC(18,2) | NOT NULL, CHECK >= 0 | |
| max_guarantee_amount | NUMERIC(18,2) | NOT NULL, CHECK >= 0 | |
| max_request_count_per_year | INTEGER | NOT NULL, CHECK >= 0 | |
| max_request_count_lifetime | INTEGER | NOT NULL, CHECK >= 0 | |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | officer can pause a policy without retiring it |
| version | INTEGER | NOT NULL, DEFAULT 1 | optimistic locking |
| created_by / updated_by | UUID | NULLABLE | |
| created_at / updated_at / deleted_at | TIMESTAMPTZ | | Timestamp + SoftDelete mixins |

**Indexes / constraints**

- `uq_loan_policies_workplace_year_active` — UNIQUE `(workplace_id, year)`
  WHERE `deleted_at IS NULL` (one policy per workplace+year among active
  rows; retired frees the pair for redefinition).
- `ix_loan_policies_workplace_id`, `ix_loan_policies_complex_id` — scope filter paths.
- CHECKs: year range; amounts >= 0; counts >= 0.

**Semantics**

- Soft-deletable (retirement); never physically deleted.
- Validation lookup: the active (`deleted_at IS NULL`) policy of the
  request's workplace for the request's year; `is_active = false` pauses
  validation with the same "no active policy" refusal as absence.
- Retiring does not block on outstanding requests (spec assumption).

### LoanRequest (`loan_requests`)

An employee's loan or guarantee demand; immutable flow history, versioned
for transitions.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID PK | | |
| employee_id | UUID FK → employees.id | NOT NULL, RESTRICT | requester |
| workplace_id | UUID | NOT NULL | snapshot of the requester's workplace at creation (scope anchor + policy lookup) |
| complex_id / company_id | UUID | NULLABLE | denormalized anchors |
| type | VARCHAR(20) | NOT NULL, CHECK IN ('loan','guarantee') | |
| amount | NUMERIC(18,2) | NOT NULL, CHECK > 0 | money; masked in audit |
| year | INTEGER | NOT NULL, CHECK 1300–1500 | Jalali year snapshot at submission (immutable) |
| status | VARCHAR(20) | NOT NULL, CHECK IN ('pending','active','settled','cancelled'), DEFAULT 'pending' | |
| settled_at | TIMESTAMPTZ | NULLABLE | set on settle; cleared never |
| version | INTEGER | NOT NULL, DEFAULT 1 | optimistic locking for transitions |
| created_by | UUID | NOT NULL | requester's user id |
| created_at / updated_at / deleted_at | TIMESTAMPTZ | | Timestamp + SoftDelete mixins |

**Indexes / constraints**

- `ix_loan_requests_employee_created` `(employee_id, created_at DESC)` — self-service list.
- `ix_loan_requests_workplace_status_year` `(workplace_id, year, status)` —
  serves both count aggregates (counts ignore status) and cap sums
  (status + year filters).
- `ix_loan_requests_complex_id` — complex-scope filtering.
- CHECKs: type, status, amount > 0, year range.

**Semantics (§19 + clarifications)**

- `year` is the Jalali year of submission — never rewritten.
- Transitions: `pending → active` (activate), `pending → cancelled`
  (cancel), `active → settled` (settle, stamps `settled_at`), `active →
  cancelled` (cancel). No edits to type/amount/employee after creation.
- Counting: every non-physically-deleted row counts toward the lifetime
  count; yearly count adds `year = validated year`; status and
  `deleted_at` are ignored for counts (research R3/R9).
- Capping: only `status = 'active'` rows with `year = validated year` and
  matching type sum toward the caps.
- Deactivated employee: activation refused (contract check at transition).

## Relationships

- `LoanPolicy.workplace_id → Workplace` (org anchor, RESTRICT)
- `LoanRequest.employee_id → Employee` (owner, RESTRICT)
- `LoanRequest.workplace_id → Workplace` (snapshot anchor, RESTRICT)

## Migration notes (`0007_loan_module`)

- Two tables with the constraint set above; partial unique index for
  policies; composite index for the count/cap aggregates.
- Reversible (`down_revision = 0006_asset_tracking`); drop tables on
  downgrade.
- Enum-like columns are plain `String(20)` + named CHECK constraints
  (`ck_loan_policies_year_range`, `ck_loan_requests_type`,
  `ck_loan_requests_status`, `ck_loan_requests_amount_positive`,
  `ck_loan_requests_year_range`) — matching the models'
  `create_constraint`-free Enum columns + explicit named CHECKs (the
  Phase-6 parity rule from the asset convergence).
- No data migrations; tables start empty (seed adds permissions only).
