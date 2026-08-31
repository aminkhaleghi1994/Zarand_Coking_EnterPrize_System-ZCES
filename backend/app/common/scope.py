from dataclasses import dataclass, field
from typing import Literal

ScopeLevel = Literal["global", "complex", "workplace"]


@dataclass(frozen=True)
class ScopeAssignmentData:
    level: ScopeLevel
    module: str
    resource: str
    operation: str
    complex_id: str | None = None
    workplace_id: str | None = None

    @property
    def target(self) -> str:
        return f"{self.module}:{self.resource}:{self.operation}"


@dataclass(frozen=True)
class ScopeContext:
    user_id: str
    is_active: bool
    permission_codes: frozenset[str] = field(default=frozenset())
    scopes: tuple[ScopeAssignmentData, ...] = field(default=())


@dataclass(frozen=True)
class ScopeTarget:
    complex_id: str | None = None
    workplace_id: str | None = None


def _covers(assignment: ScopeAssignmentData, target: ScopeTarget) -> bool:
    if assignment.level == "global":
        return True
    if assignment.level == "complex":
        return target.complex_id is not None and assignment.complex_id == target.complex_id
    if assignment.level == "workplace":
        return target.workplace_id is not None and assignment.workplace_id == target.workplace_id
    return False


def can(
    context: ScopeContext,
    operation: str,
    target: ScopeTarget | None = None,
) -> bool:
    resolved_target = target or ScopeTarget()
    if not context.is_active:
        return False
    if operation not in context.permission_codes:
        return False
    return any(
        assignment.target == operation and _covers(assignment, resolved_target)
        for assignment in context.scopes
    )


@dataclass(frozen=True)
class ScopeUnits:
    """Resolved unit coverage for one operation: global flag + allowed unit ids."""

    global_access: bool
    complex_ids: frozenset[str] = field(default=frozenset())
    workplace_ids: frozenset[str] = field(default=frozenset())


def allowed_units(context: ScopeContext, operation: str) -> ScopeUnits:
    """Unit coverage of an operation per the same rules as `can` (union, both gates)."""
    if not context.is_active or operation not in context.permission_codes:
        return ScopeUnits(global_access=False)
    global_access = False
    complex_ids: set[str] = set()
    workplace_ids: set[str] = set()
    for assignment in context.scopes:
        if assignment.target != operation:
            continue
        if assignment.level == "global":
            global_access = True
        elif assignment.level == "complex" and assignment.complex_id:
            complex_ids.add(assignment.complex_id)
        elif assignment.level == "workplace" and assignment.workplace_id:
            workplace_ids.add(assignment.workplace_id)
    return ScopeUnits(
        global_access=global_access,
        complex_ids=frozenset(complex_ids),
        workplace_ids=frozenset(workplace_ids),
    )
