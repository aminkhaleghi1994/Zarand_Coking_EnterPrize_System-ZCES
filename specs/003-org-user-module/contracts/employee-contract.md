# Contract: User Module Public Interface (internal)

**Owner**: `app/modules/user/contracts.py` — the ONLY surface other modules may
use (constitution VI). Signatures are stable from Phase 3 onward; Phase 4+
(warehouse, loans) consume these instead of touching repositories/models.

```python
def get_employee_by_id(session, employee_id: uuid.UUID) -> EmployeeOut | None:
    """Active employee by id, or None. No scope (internal system use)."""

def get_employee_workplace(session, employee_id: uuid.UUID) -> WorkplaceOut | None:
    """The employee's workplace (with complex id), or None."""

def search_employees(
    session,
    scope_ctx: ScopeContext,
    *,
    search: str | None = None,
    workplace_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> Page[EmployeeSummaryOut]:
    """Scope-filtered, paginated employee search for other modules' pickers."""

def is_employee_active(session, employee_id: uuid.UUID) -> bool:
    """True iff the employee exists and is active (not soft-deleted)."""

# Existing Phase-2 contract surface (unchanged):
def get_user_by_id(session, user_id: uuid.UUID) -> UserOut | None: ...
def is_user_active(session, user_id: uuid.UUID) -> bool: ...
def get_user_scopes(session, user_id: uuid.UUID) -> list[ScopeAssignmentOut]: ...
def revoke_all_for_user(session, user_id: uuid.UUID) -> None: ...
```

Rules:
- Consumers never see SQLAlchemy models — DTOs only.
- `search_employees` applies the caller's scope context; callers pass their own
  context, never a bare query.
- These functions are read-only; mutations stay inside the user module's
  services.
