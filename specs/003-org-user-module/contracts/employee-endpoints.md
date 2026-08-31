# Contract: Employee & Organization Endpoints (HTTP)

**Base**: `/api/v1` behind the BFF (`/api/...` passthrough with cookies + CSRF
on mutations). All errors use the standard envelope
`{code, message, details, trace_id}`. All lists paginate
`{items, page, page_size, total}` (bounded page size, default 20).

Permission AND scope required on every endpoint (implicit deny). Scope filter
applies to the returned rows, never just the endpoint.

## Organization reads

### GET /org/complexes
- Permission: `user:org:read`
- Scope: Global → all; Complex → own only; Workplace → own complex (via workplace)
- Query: `page`, `page_size`
- 200: `{items: [{id, code, name, name_fa, company_id}], page, page_size, total}`
- Active rows only (pickers never show deactivated).

### GET /org/workplaces?complex_id={uuid}?
- Permission: `user:org:read`
- Scope: Global → all (optionally narrowed by `complex_id`); Complex → own
  complex's workplaces; Workplace → own workplace only
- 200: `{items: [{id, code, name, name_fa, complex_id}], page, page_size, total}`

## Employee lifecycle

### GET /employees
- Permission: `user:employee:read`
- Scope: union filter per assignments
- Query: `page`, `page_size`, `search` (name / national_id / personnel_code),
  `status` = `active` (default) | `deactivated` | `all`,
  `workplace_id`, `complex_id` (optional narrowing within scope)
- 200: `{items: [EmployeeOut], page, page_size, total}`

`EmployeeOut`:
```json
{
  "id": "uuid", "version": 7,
  "national_id": "*****6789",
  "personnel_code": "CP-1024",
  "first_name": "Sara", "last_name": "Ahmadi",
  "first_name_fa": "سارا", "last_name_fa": "احمدی",
  "birth_date": "1990-04-12", "phone": "+989120000000",
  "is_active": true,
  "workplace": {"id": "uuid", "code": "CP1", "name": "Coke Plant 1", "name_fa": "کوک‌سازی ۱"},
  "complex": {"id": "uuid", "code": "CTR", "name": "Coking and Tar Refining Complex"},
  "user": {"id": "uuid", "email": "sara@zarandsteel.ir", "is_active": true}
}
```
(`national_id` masked in list/detail responses for non-`read_full` holders;
full value only with `user:employee:read_full`.)

### POST /employees
- Permission: `user:employee:create`; scope must cover the target workplace
- Body:
```json
{
  "national_id": "1234567890",
  "personnel_code": "CP-1042",
  "first_name": "Sara", "last_name": "Ahmadi",
  "first_name_fa": null, "last_name_fa": null,
  "birth_date": null, "phone": null,
  "workplace_id": "uuid",
  "user": {"email": "sara@zarandsteel.ir", "password": "minimum-8-chars", "username": "sara.ahmadi"}
}
```
- 201: `EmployeeOut`
- Errors: `VALIDATION_ERROR` (field details: national_id format, password
  policy), `DUPLICATE_RESOURCE` (national_id / personnel_code / email /
  username — details name the field), `AUTHORIZATION_DENIED`
- Atomic: employee + user created together; `EMPLOYEE_CREATED` audited
  (masked after-snapshot).

### GET /employees/{id}
- Permission: `user:employee:read`; scope must cover the employee's workplace
- 200: `EmployeeOut` · 404-shaped `RESOURCE_NOT_FOUND` within scope ·
  `AUTHORIZATION_DENIED` outside scope (no existence leak)

### PATCH /employees/{id}
- Permission: `user:employee:update`; scope must cover both current AND target
  workplace (moves)
- Body: editable fields only (`first_name`, `last_name`, `first_name_fa`,
  `last_name_fa`, `birth_date`, `phone`, `workplace_id`) + `version` (required,
  optimistic lock)
- 200: `EmployeeOut` · `STALE_VERSION` on version mismatch ·
  `DUPLICATE_RESOURCE` impossible (identity anchors immutable — service
  rejects any attempt with `VALIDATION_ERROR`)
- Audited: `EMPLOYEE_UPDATED` (move additionally `EMPLOYEE_MOVED`)

### POST /employees/{id}/deactivate
- Permission: `user:employee:deactivate`; scope must cover the employee
- Body: `{"version": 7}`
- 200: `EmployeeOut` (deactivated)
- Effect: same-transaction cascade — user deactivated, refresh families
  revoked; audited `EMPLOYEE_DEACTIVATED`. Idempotent on already-deactivated.

### POST /employees/{id}/reactivate
- Permission: `user:employee:deactivate` (same capability governs the pair);
  scope must cover the employee
- 200: `EmployeeOut` (active) · audited `EMPLOYEE_REACTIVATED`

## User account management

### POST /users/{user_id}/password
- Permission: `user:password:set`; target user's employee (if any) must be in
  scope; bootstrap users without employee require Global
- Body: `{"password": "minimum-8-chars"}`
- 200: `{"success": true}`
- Effect: bcrypt rehash, all refresh families revoked, `USER_PASSWORD_SET`
  audited (no credential material anywhere)

## Role / scope management (existing Phase-2 endpoints, now surfaced in UI)

- `GET /roles`, `POST /roles` — `user:role:read` / `user:role:create`
- `GET /permissions` — `user:permission:read`
- `GET /users` — `user:list:read`
- `POST/DELETE /users/{id}/roles[/{role_id}]` — `user:role:assign`
- `POST/DELETE /users/{id}/scopes[/{assignment_id}]` — `user:scope:assign`;
  level→unit consistency per FR-019; assignments may not reference
  deactivated units (new service check)

## BFF passthrough pattern

Each endpoint above gets a route handler under `frontend/src/app/api/**` that:
forwards the `zces_at` cookie + `X-Request-ID`; enforces the CSRF header on
mutations; returns the backend body verbatim (envelope preserved) with the
backend status code; performs the single transparent-refresh-and-retry on 401
(existing session wrapper).
