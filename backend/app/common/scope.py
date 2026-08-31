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
