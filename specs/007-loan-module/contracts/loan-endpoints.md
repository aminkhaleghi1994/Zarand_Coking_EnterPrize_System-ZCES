# API Contracts: Loan & Guarantee Management

**Feature branch**: `feature/007-loan-module` | **Date**: 2026-09-01
Base path `/api/v1` (BFF mirrors under `/api/loan/**`). Standard error
envelope `{code, message, details, trace_id}`; list responses
`{items, page, page_size, total}`.

---

## Loan policies

### `GET /loan/policies`

Query: `page`, `page_size` (bounded ≤ 100), `workplace_id?`, `year?`,
`include_retired` (default `false`).

Requires `loan:policy:read` + scope (`allowed_units` on workplace anchor).

Response item (`LoanPolicyOut`):

```json
{
  "id": "uuid",
  "version": 3,
  "workplace": {"id": "uuid", "code": "CP1", "name": "…", "name_fa": "…"},
  "year": 1405,
  "max_loan_amount": "100000000.00",
  "max_guarantee_amount": "50000000.00",
  "max_request_count_per_year": 3,
  "max_request_count_lifetime": 10,
  "is_active": true,
  "created_at": "2026-09-01T10:00:00Z"
}
```

### `POST /loan/policies` → 201

Requires `loan:policy:create` + in-scope workplace target.

```json
{
  "workplace_id": "uuid",
  "year": 1405,
  "max_loan_amount": "100000000.00",
  "max_guarantee_amount": "50000000.00",
  "max_request_count_per_year": 3,
  "max_request_count_lifetime": 10
}
```

Errors: `VALIDATION_ERROR` (year out of range, negative values),
`DUPLICATE_RESOURCE` (active policy exists for workplace+year),
`AUTHORIZATION_DENIED` (out-of-scope workplace).

### `PATCH /loan/policies/{id}` → 200

Requires `loan:policy:update` + in-scope target. Takes any subset of the
editable fields plus `version` (integer ≥ 1). Stale version →
`STALE_VERSION` 409. Retired policy → `RESOURCE_NOT_FOUND` (no leak).

### `POST /loan/policies/{id}/retire` → 200

Requires `loan:policy:retire` + in-scope target. Body: `{"version": n}`.
Idempotent-free semantics: retiring an already-retired policy →
`RESOURCE_NOT_FOUND`.

## Loan requests

### `GET /loan/requests`

Query: `page`, `page_size` (bounded ≤ 100), `type?` (loan|guarantee),
`status?` (pending|active|settled|cancelled|all), `year?`, `employee_id?`
(officers only), `search?` (requester name).

Visibility: authenticated users always see their **own** requests
(ownership filter); with `loan:request:read` + scope the response widens to
all covered-workplace requests (union, implicit deny).

Response item (`LoanRequestOut`):

```json
{
  "id": "uuid",
  "version": 2,
  "employee": {"id": "uuid", "name": "Ali Ahmadi", "name_fa": "علی احمدی"},
  "workplace": {"id": "uuid", "code": "CP1", "name": "…"},
  "type": "loan",
  "amount": "20000000.00",
  "year": 1405,
  "status": "pending",
  "settled_at": null,
  "created_by": "uuid",
  "created_at": "2026-09-01T10:00:00Z"
}
```

### `POST /loan/requests` → 201

Self-service: the signed-in user's employee record is the requester (no
`employee_id` in the payload). Requires authentication only (own request);
the employee record must exist and be active.

```json
{"type": "loan", "amount": "20000000.00"}
```

Validation cascade (exact §19 order, first failure wins,
`BUSINESS_RULE_VIOLATION` 422 with `details.rule` + numbers):

```json
{"code": "BUSINESS_RULE_VIOLATION",
 "details": {"rule": "yearly_count", "used": 3, "limit": 3}}
{"details": {"rule": "lifetime_count", "used": 10, "limit": 10}}
{"details": {"rule": "loan_cap", "current_active": "90000000.00", "limit": "100000000.00", "requested": "20000000.00"}}
{"details": {"rule": "guarantee_cap", …}}
{"rule": "no_policy", "workplace_id": "…", "year": 1405}
```

Other errors: `VALIDATION_ERROR` (bad type, non-positive amount, precision
> 2), `AUTHENTICATION_REQUIRED`, `RESOURCE_NOT_FOUND` (no employee record).

### `GET /loan/requests/{id}` → 200

Ownership (own request) or `loan:request:read` + scope. Out-of-scope →
`RESOURCE_NOT_FOUND` without leak.

### Transitions (all require the matching permission + in-scope target,
`version` guard → `STALE_VERSION` 409 on races)

- `POST /loan/requests/{id}/activate` — body `{"version": n}`. Pending only;
  employee must still be active. → status `active`.
  `BUSINESS_RULE_VIOLATION` otherwise.
- `POST /loan/requests/{id}/settle` — body `{"version": n}`. Active only;
  stamps `settled_at`; frees the amount commitment.
- `POST /loan/requests/{id}/cancel` — body `{"version": n}`. Pending or
  active; frees the amount commitment (if it was active); counts stay
  consumed.

## Cross-module contracts

- `user.contracts.get_loan_requester(session, user_id)` →
  `{employee_id, display_name, company_id, complex_id, workplace_id,
  is_active}` or `None` — resolves the signed-in user to an active employee
  with org anchors for policy lookup and request anchoring.
- Audit actions (masked `amount`): `LOAN_POLICY_CREATED` / `UPDATED` /
  `RETIRED`, `LOAN_REQUEST_CREATED` / `ACTIVATED` / `SETTLED` / `CANCELLED`.

## Frontend BFF routes

`/api/loan/policies` (+ `[id]`, `[id]/retire`), `/api/loan/requests`
(+ `[id]`, `[id]/activate|settle|cancel`) — pure passthrough via
`proxyToBackend`.
