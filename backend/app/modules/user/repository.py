import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeAssignmentData, ScopeContext
from app.modules.user.models import (
    Permission,
    RefreshToken,
    RefreshTokenStatus,
    Role,
    RolePermission,
    ScopeAssignment,
    User,
    UserRole,
)
from app.modules.user.schemas import (
    PageParams,
    PermissionOut,
    RoleOut,
    ScopeAssignmentOut,
    UserOut,
)


def get_active_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(
        select(User).where(User.email == email.strip().lower(), User.deleted_at.is_(None))
    )


def get_active_user_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    return session.scalar(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )


def get_role_by_id(session: Session, role_id: uuid.UUID) -> Role | None:
    return session.scalar(select(Role).where(Role.id == role_id, Role.deleted_at.is_(None)))


def get_user_role(session: Session, user_id: uuid.UUID, role_id: uuid.UUID) -> UserRole | None:
    return session.scalar(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )


def get_scope_assignment(
    session: Session, user_id: uuid.UUID, assignment_id: uuid.UUID
) -> ScopeAssignment | None:
    return session.scalar(
        select(ScopeAssignment).where(
            ScopeAssignment.id == assignment_id, ScopeAssignment.user_id == user_id
        )
    )


def list_roles(session: Session, params: PageParams) -> Page[RoleOut]:
    total = (
        session.scalar(select(func.count()).select_from(Role).where(Role.deleted_at.is_(None)))
        or 0
    )
    rows = session.scalars(
        select(Role)
        .where(Role.deleted_at.is_(None))
        .order_by(Role.name)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return Page[RoleOut](items=[RoleOut.model_validate(r) for r in rows], total=total,
                         page=params.page, page_size=params.page_size)


def list_permissions(session: Session, params: PageParams) -> Page[PermissionOut]:
    total = session.scalar(select(func.count()).select_from(Permission)) or 0
    rows = session.scalars(
        select(Permission)
        .order_by(Permission.code)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return Page[PermissionOut](
        items=[PermissionOut.model_validate(r) for r in rows],
        total=total, page=params.page, page_size=params.page_size,
    )


def list_users(session: Session, params: PageParams) -> Page[UserOut]:
    total = (
        session.scalar(select(func.count()).select_from(User).where(User.deleted_at.is_(None)))
        or 0
    )
    rows = session.scalars(
        select(User)
        .where(User.deleted_at.is_(None))
        .order_by(User.email)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return Page[UserOut](items=[UserOut.model_validate(r) for r in rows], total=total,
                         page=params.page, page_size=params.page_size)


def get_user_role_names(session: Session, user_id: uuid.UUID) -> list[str]:
    return list(
        session.scalars(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, Role.deleted_at.is_(None))
        ).all()
    )


def load_scope_context(session: Session, user_id: str) -> ScopeContext | None:
    uid = uuid.UUID(user_id)
    user = get_active_user_by_id(session, uid)
    if user is None or not user.is_active:
        return None
    permission_codes = frozenset(
        session.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == uid)
        ).all()
    )
    assignments = tuple(
        ScopeAssignmentData(
            level=row.level.value,
            module=row.module,
            resource=row.resource,
            operation=row.operation,
            complex_id=str(row.complex_id) if row.complex_id else None,
            workplace_id=str(row.workplace_id) if row.workplace_id else None,
        )
        for row in session.scalars(
            select(ScopeAssignment).where(ScopeAssignment.user_id == uid)
        ).all()
    )
    return ScopeContext(user_id=user_id, is_active=True,
                        permission_codes=permission_codes, scopes=assignments)


def get_user_scopes(session: Session, user_id: uuid.UUID) -> list[ScopeAssignmentOut]:
    rows = session.scalars(
        select(ScopeAssignment).where(ScopeAssignment.user_id == user_id)
    ).all()
    return [ScopeAssignmentOut.model_validate(r) for r in rows]


def get_refresh_member_by_hash(session: Session, token_hash: str) -> RefreshToken | None:
    return session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))


def list_family_members(session: Session, family_id: uuid.UUID) -> list[RefreshToken]:
    return list(
        session.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id)).all()
    )


def list_active_families_for_user(session: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(RefreshToken.family_id)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.status != RefreshTokenStatus.REVOKED,
            )
            .distinct()
        ).all()
    )
