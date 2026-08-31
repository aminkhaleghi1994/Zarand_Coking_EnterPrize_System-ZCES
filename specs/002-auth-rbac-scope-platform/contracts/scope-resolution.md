# Contract: Scope Resolution

**Scope**: Central authorization decision point (constitution II) · Pure logic + DB
loader, consumed by `require_permission` dependency and future module services.

## Model

- Operation string: `module:resource:operation` (e.g. `user:role:assign`).
- Scope assignment: `{ level: global|complex|workplace, module, resource, operation,
  complex_id?, workplace_id? }`.
- Target of an evaluation: `{ complex_id?, workplace_id? }` (none = org-agnostic op).

## Resolver semantics (requirements §13, verbatim)

```
can(user, "module:resource:operation", target) :=
       "module:resource:operation" ∈ user.permission_codes        # permission
   AND ∃ assignment ∈ user.scopes:                                # AND scope
          assignment.target == "module:resource:operation"
          AND covers(assignment, target)

covers(a, t):
   a.level == global                          → true
   a.level == complex                         → t.complex_id != null
                                                 AND a.complex_id == t.complex_id
   a.level == workplace                       → t.workplace_id != null
                                                 AND a.workplace_id == t.workplace_id
```

- Higher level covers lower units (Global ⊇ Complex ⊇ Workplace); a lower level
  never reaches upward.
- Multiple assignments UNION — allow if any covers.
- **Implicit deny**: no assignment, no permission, unknown operation, or unknown/
  null target unit for a non-Global level ⇒ deny.
- Deny is a normal result (`False`), never an exception; the dependency converts
  False → 403 `AUTHORIZATION_DENIED` (only AFTER 401 authentication checks).

## Resolution order per request

1. Authenticate (valid access JWT, user exists AND `is_active`) → else 401.
2. Load `ScopeContext` (permission codes + scope assignments) — DB joins.
3. `resolver.can(...)` for the route's required permission → else 403.
4. Repository calls receive the `ScopeContext` (mandatory scope filter from Phase 3).

## Testing surface (SC-002 gate)

Pure-function unit tests over constructed contexts: permission-only, scope-only,
both, neither, each level × target combination, cross-complex denial, cross-workplace
denial, union across levels, union across units, unknown operation, null targets,
deactivated user (loader-level), ≥ 15 cases green.
