import uuid

from app.common.scope import ScopeAssignmentData, ScopeContext, ScopeTarget, can

PERM = "warehouse:item:create"
COMPLEX_A = str(uuid.uuid4())
COMPLEX_B = str(uuid.uuid4())
WORKPLACE_A1 = str(uuid.uuid4())
WORKPLACE_A2 = str(uuid.uuid4())
WORKPLACE_B1 = str(uuid.uuid4())


def _context(
    *assignments: ScopeAssignmentData,
    permissions: frozenset[str] = frozenset({PERM}),
    active: bool = True,
) -> ScopeContext:
    return ScopeContext(
        user_id="u1",
        is_active=active,
        permission_codes=permissions,
        scopes=assignments,
    )


def _global() -> ScopeAssignmentData:
    return ScopeAssignmentData("global", "warehouse", "item", "create")


def _complex(complex_id: str) -> ScopeAssignmentData:
    return ScopeAssignmentData("complex", "warehouse", "item", "create", complex_id=complex_id)


def _workplace(workplace_id: str) -> ScopeAssignmentData:
    return ScopeAssignmentData(
        "workplace", "warehouse", "item", "create", workplace_id=workplace_id
    )


def test_01_permission_without_scope_denied() -> None:
    assert not can(_context(), PERM, ScopeTarget(complex_id=COMPLEX_A))


def test_02_scope_without_permission_denied() -> None:
    context = _context(_global(), permissions=frozenset())
    assert not can(context, PERM, ScopeTarget(complex_id=COMPLEX_A))


def test_03_permission_and_scope_allow() -> None:
    assert can(_context(_global()), PERM, ScopeTarget(complex_id=COMPLEX_A))


def test_04_neither_denied() -> None:
    assert not can(_context(permissions=frozenset()), PERM)


def test_05_global_covers_any_complex() -> None:
    context = _context(_global())
    assert can(context, PERM, ScopeTarget(complex_id=COMPLEX_A))
    assert can(context, PERM, ScopeTarget(complex_id=COMPLEX_B))


def test_06_global_covers_any_workplace() -> None:
    context = _context(_global())
    assert can(context, PERM, ScopeTarget(workplace_id=WORKPLACE_A1))
    assert can(context, PERM, ScopeTarget(workplace_id=WORKPLACE_B1))


def test_07_complex_covers_only_own_workplaces() -> None:
    context = _context(_complex(COMPLEX_A))
    assert can(context, PERM, ScopeTarget(complex_id=COMPLEX_A, workplace_id=WORKPLACE_A1))
    assert can(context, PERM, ScopeTarget(complex_id=COMPLEX_A, workplace_id=WORKPLACE_A2))
    assert not can(context, PERM, ScopeTarget(complex_id=COMPLEX_B, workplace_id=WORKPLACE_B1))


def test_08_complex_targets_the_complex_itself() -> None:
    context = _context(_complex(COMPLEX_A))
    assert can(context, PERM, ScopeTarget(complex_id=COMPLEX_A))
    assert not can(context, PERM, ScopeTarget(complex_id=COMPLEX_B))


def test_09_workplace_covers_only_itself() -> None:
    context = _context(_workplace(WORKPLACE_A1))
    assert can(context, PERM, ScopeTarget(complex_id=COMPLEX_A, workplace_id=WORKPLACE_A1))
    assert not can(context, PERM, ScopeTarget(complex_id=COMPLEX_A, workplace_id=WORKPLACE_A2))


def test_10_workplace_cannot_reach_upward() -> None:
    context = _context(_workplace(WORKPLACE_A1))
    assert not can(context, PERM, ScopeTarget(complex_id=COMPLEX_A))


def test_11_union_across_units_same_level() -> None:
    context = _context(_workplace(WORKPLACE_A1), _workplace(WORKPLACE_A2))
    assert can(context, PERM, ScopeTarget(workplace_id=WORKPLACE_A1))
    assert can(context, PERM, ScopeTarget(workplace_id=WORKPLACE_A2))
    assert not can(context, PERM, ScopeTarget(workplace_id=WORKPLACE_B1))


def test_12_union_across_levels() -> None:
    context = _context(_complex(COMPLEX_A), _workplace(WORKPLACE_B1))
    assert can(context, PERM, ScopeTarget(complex_id=COMPLEX_A, workplace_id=WORKPLACE_A1))
    assert can(context, PERM, ScopeTarget(workplace_id=WORKPLACE_B1))
    assert not can(context, PERM, ScopeTarget(complex_id=COMPLEX_B))


def test_13_union_across_operations() -> None:
    read = ScopeAssignmentData("global", "warehouse", "item", "read")
    context = _context(_global(), read, permissions=frozenset({PERM, "warehouse:item:read"}))
    assert can(context, PERM, ScopeTarget(complex_id=COMPLEX_A))
    assert can(context, "warehouse:item:read", ScopeTarget(complex_id=COMPLEX_B))


def test_14_unknown_operation_denied() -> None:
    context = _context(_global())
    assert not can(context, "loan:request:approve", ScopeTarget(complex_id=COMPLEX_A))


def test_15_null_target_with_non_global_denied() -> None:
    context = _context(_complex(COMPLEX_A), _workplace(WORKPLACE_A1))
    assert not can(context, PERM, None)
    assert not can(context, PERM, ScopeTarget())


def test_16_org_agnostic_operation_with_global_allowed() -> None:
    context = _context(_global())
    assert can(context, PERM, None)


def test_17_deactivated_user_denied() -> None:
    context = _context(_global(), active=False)
    assert not can(context, PERM, ScopeTarget(complex_id=COMPLEX_A))


def test_18_wrong_operation_string_denied() -> None:
    context = _context(_global())
    assert not can(context, "warehouse:item:delete", ScopeTarget(complex_id=COMPLEX_A))
