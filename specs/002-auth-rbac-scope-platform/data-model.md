# Data Model: Auth, RBAC & Scope Platform

**Date**: 2026-08-29 · Companion to [plan.md](./plan.md) · 8 new tables, migration `0002_auth_rbac_scope`

All tables: UUID PK (`IDMixin`), timestamps (`TimestampMixin`), actor columns
(`CreatedByMixin`/`UpdatedByMixin`). Editable entities add `SoftDeleteMixin` +
`VersionMixin` (optimistic locking). Uniqueness on active rows uses partial unique
indexes (`WHERE deleted_at IS NULL`).

## Entity catalog

### users
| Column | Type | Rules |
|---|---|---|
| email | citext-like (text, lowercased by service) | NOT NULL; **partial unique** on active rows; format-validated in service |
| username | text | NOT NULL; partial unique on active rows |
| hashed_password | text | NOT NULL; bcrypt `$2b$12$…`; never in DTOs/logs/audit |
| is_active | bool | NOT NULL default true; deactivation revokes refresh families |
| mixins | — | ID, Timestamp, SoftDelete, Version, CreatedBy, UpdatedBy |

Employee 1:1 linkage is Phase 3 (column added there, single-transaction creation).

### roles
name (partial unique active) · description nullable. Mixins: full set incl. Version.

### permissions
code (text, unique — immutable natural key, e.g. `user:role:assign`) ·
name_en · name_fa. Mixins: ID/Timestamp/CreatedBy/UpdatedBy (no soft delete needed —
permissions are vocabulary; delete = never).

### role_permissions
role_id FK → roles · permission_id FK → permissions; **unique (role_id, permission_id)**.
No soft delete (grant rows are physically inserted/deleted; the grant itself is the
audit snapshot).

### user_roles
user_id FK → users · role_id FK → roles; **unique (user_id, role_id)**. No soft delete.

### scope_assignments
| Column | Type | Rules |
|---|---|---|
| user_id | FK users | NOT NULL |
| level | enum `global` / `complex` / `workplace` | NOT NULL |
| module, resource, operation | text | NOT NULL; target = `module:resource:operation` |
| complex_id | FK-like UUID null | required when level=complex |
| workplace_id | FK-like UUID null | required when level=workplace |
| — | — | level/unit consistency validated in service; no soft delete (assignments are grant rows, audited) |

FK constraints to complexes/workplaces land in Phase 3 when those tables exist;
until then plain UUID columns (resolver treats unknown ids as deny).

### refresh_tokens (family members)
| Column | Type | Rules |
|---|---|---|
| user_id | FK users | NOT NULL |
| family_id | UUID | NOT NULL (indexed); one family per login session |
| token_hash | text | NOT NULL; SHA-256 hex of the opaque token; **unique** (lookup key) |
| status | enum `active` / `rotated` / `revoked` | NOT NULL default active |
| rotated_to_id | UUID null | points to successor member |
| expires_at | timestamptz | NOT NULL |
| user_agent | text null | device hint (masked truncation 256 chars) |
| — | — | append-only lifecycle: insert on issue, status updated on rotate/revoke; no soft delete |

### audit_logs (append-only)
| Column | Type | Rules |
|---|---|---|
| actor_user_id | UUID null | null for failed login of unknown user |
| entity_type | text | e.g. `user`, `role`, `scope_assignment`, `session` |
| entity_id | UUID null | |
| action | text | `LOGIN_SUCCEEDED`, `LOGIN_FAILED`, `LOGOUT`, `TOKEN_RENEWED`, `TOKEN_REUSE_DETECTED`, `FAMILY_REVOKED`, `ROLE_ASSIGNED`, `ROLE_REVOKED`, `SCOPE_ASSIGNED`, `SCOPE_REVOKED` |
| before_snapshot | JSONB null | masked at write time |
| after_snapshot | JSONB null | masked at write time |
| trace_id | text | from request context |
| — | — | ID + created_at only (TimestampMixin without update? updated_at still present but unused) — no soft delete, no version |

## Relationships

- users 1—N user_roles N—1 roles; roles 1—N role_permissions N—1 permissions
- users 1—N scope_assignments
- users 1—N refresh_tokens (families: N members share family_id)
- audit_logs references users logically (actor_user_id, no FK to keep audit
  append-only even against future user soft-deletes)

## State transitions

- refresh_tokens: `active → rotated` (on renewal), `active → revoked` (logout),
  `rotated/active → revoked` (reuse detection / deactivation / family revocation).
- user lifecycle: active ⇄ deactivated; deactivation ⇒ all families revoked,
  authentication denied (checked at the boundary every time).

## Indexes (beyond PKs/uniques)

- `refresh_tokens(family_id)`, `refresh_tokens(user_id, status)`
- `audit_logs(created_at DESC)`, `audit_logs(actor_user_id, created_at DESC)`
- `scope_assignments(user_id)`
- partial unique: `users(email) WHERE deleted_at IS NULL`,
  `users(username) WHERE deleted_at IS NULL`, `roles(name) WHERE deleted_at IS NULL`
