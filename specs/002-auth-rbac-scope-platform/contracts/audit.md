# Contract: Audit Base

**Scope**: `modules/audit` · All future modules write through the audit contract —
never the repository directly.

## Record shape (`audit_logs`, append-only)

`{ id, actor_user_id?, entity_type, entity_id?, action, before_snapshot?, after_snapshot?,
trace_id, created_at }` — actions seeded in Phase 2: LOGIN_SUCCEEDED, LOGIN_FAILED,
LOGOUT, TOKEN_RENEWED, TOKEN_REUSE_DETECTED, FAMILY_REVOKED, ROLE_ASSIGNED, ROLE_REVOKED,
SCOPE_ASSIGNED, SCOPE_REVOKED.

## Write contract (`write_audit`)

```python
write_audit(
    session,                      # request transaction
    *, action, entity_type,
    entity_id=None, actor_user_id=None,
    before=None, after=None,      # plain dicts; masking applied HERE
    critical=False,
)
```

- `critical=True` (auth events): written in the SAME transaction — failure rolls the
  operation back (audit must not be losable).
- `critical=False`: write attempted; on failure log-and-continue (notification
  tolerance rule, constitution VII).
- trace_id from request context automatically; snapshots masked at write time via
  `common/masking.py`.

## Masking helpers (central, reused by every future module)

| Helper | Rule | Example |
|---|---|---|
| `mask_secret(value)` | full mask, presence-preserving | `***` |
| `mask_email(value)` | local part → first char + `***`, domain kept | `a***@zarandsteel.ir` |
| `mask_identifier(value)` | keep last 4 chars only | `***1234` |
| `mask_user_agent(value)` | truncate 256 + strip version tokens | — |

Sensitive keys are masked structurally: any snapshot key in
`{password, hashed_password, token, refresh_token, access_token, secret, national_id,
personnel_code}` is masked by its kind automatically; `email` via `mask_email`.

## Read contract

- `GET /audit-logs` (paginated `{items, page, page_size, total}`, filters:
  `actor_user_id`, `action`, `entity_type`) — permission `audit:log:read` + Global
  scope; snapshots masked unless caller also holds `audit:log:read_full`.
- No update/delete endpoints exist (append-only by design).
