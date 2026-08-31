from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.user.models import (
    Permission,
    Role,
    RolePermission,
    ScopeAssignment,
    ScopeLevel,
    User,
    UserRole,
)

BASE_PERMISSIONS: list[tuple[str, str, str]] = [
    ("user:list:read", "List users", "مشاهده فهرست کاربران"),
    ("user:role:read", "Read roles", "مشاهده نقش‌ها"),
    ("user:role:create", "Create roles", "ایجاد نقش"),
    ("user:role:assign", "Assign roles", "تخصیص نقش"),
    ("user:permission:read", "Read permissions", "مشاهده مجوزها"),
    ("user:scope:assign", "Assign scopes", "تخصیص دامنه دسترسی"),
    ("audit:log:read", "Read audit logs", "مشاهده لاگ‌های ممیزی"),
    ("audit:log:read_full", "Read full audit snapshots", "مشاهده کامل اسنپ‌شات‌های ممیزی"),
]

BASE_ROLES: list[str] = [
    "SuperAdmin",
    "HRAdmin",
    "WarehouseKeeper",
    "WarehouseApprover",
    "LoanOfficer",
    "Auditor",
    "Manager",
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "SuperAdmin": [code for code, _, _ in BASE_PERMISSIONS],
    "Auditor": ["audit:log:read", "audit:log:read_full", "user:list:read"],
    "Manager": ["user:list:read"],
}

UNSAFE_PASSWORDS = {"change_me_now", "change_me", "admin", "password", "12345678"}


def _get_or_create_permission(
    session: Session, code: str, name_en: str, name_fa: str
) -> Permission:
    existing = session.scalar(select(Permission).where(Permission.code == code))
    if existing:
        return existing
    permission = Permission(code=code, name_en=name_en, name_fa=name_fa)
    session.add(permission)
    session.flush()
    return permission


def _get_or_create_role(session: Session, name: str, description: str) -> Role:
    existing = session.scalar(select(Role).where(Role.name == name, Role.deleted_at.is_(None)))
    if existing:
        return existing
    role = Role(name=name, description=description)
    session.add(role)
    session.flush()
    return role


def _ensure_role_permission(session: Session, role: Role, permission: Permission) -> None:
    existing = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == role.id, RolePermission.permission_id == permission.id
        )
    )
    if not existing:
        session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        session.flush()


def _ensure_user_role(session: Session, user: User, role: Role) -> None:
    existing = session.scalar(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )
    if not existing:
        session.add(UserRole(user_id=user.id, role_id=role.id))
        session.flush()


def _ensure_global_scope(session: Session, user: User, permission: Permission) -> None:
    module, resource, operation = permission.code.split(":", 2)
    existing = session.scalar(
        select(ScopeAssignment).where(
            ScopeAssignment.user_id == user.id,
            ScopeAssignment.level == ScopeLevel.GLOBAL,
            ScopeAssignment.module == module,
            ScopeAssignment.resource == resource,
            ScopeAssignment.operation == operation,
        )
    )
    if not existing:
        session.add(
            ScopeAssignment(
                user_id=user.id,
                level=ScopeLevel.GLOBAL,
                module=module,
                resource=resource,
                operation=operation,
            )
        )
        session.flush()


def _assert_safe_admin_password(password: str, username: str, email: str) -> None:
    normalized = (password or "").strip()
    if not normalized or len(normalized) < 8:
        raise SystemExit(
            "Refusing to seed production: INITIAL_ADMIN_PASSWORD is empty or too short"
        )
    if normalized.lower() in UNSAFE_PASSWORDS:
        raise SystemExit(
            "Refusing to seed production: INITIAL_ADMIN_PASSWORD is a known unsafe default"
        )
    if normalized in (username, email):
        raise SystemExit(
            "Refusing to seed production: INITIAL_ADMIN_PASSWORD must differ from username/email"
        )


def run_seed(session: Session, *, prod: bool = False) -> dict[str, int]:
    from app.core.config import get_settings

    settings = get_settings()
    email = (settings.INITIAL_ADMIN_EMAIL or "").strip().lower()
    username = (settings.INITIAL_ADMIN_USERNAME or "").strip()
    password = settings.INITIAL_ADMIN_PASSWORD or ""

    if not email or not username or not password:
        raise SystemExit(
            "INITIAL_ADMIN_EMAIL, INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD must be set"
        )
    if prod:
        _assert_safe_admin_password(password, username, email)

    created_permissions = 0
    permissions: dict[str, Permission] = {}
    for code, name_en, name_fa in BASE_PERMISSIONS:
        permission_existing = session.scalar(select(Permission).where(Permission.code == code))
        permissions[code] = _get_or_create_permission(session, code, name_en, name_fa)
        if permission_existing is None:
            created_permissions += 1

    created_roles = 0
    roles: dict[str, Role] = {}
    for name in BASE_ROLES:
        role_existing = session.scalar(
            select(Role).where(Role.name == name, Role.deleted_at.is_(None))
        )
        description = "Full administrative access" if name == "SuperAdmin" else ""
        roles[name] = _get_or_create_role(session, name, description)
        if role_existing is None:
            created_roles += 1

    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        for code in permission_codes:
            _ensure_role_permission(session, roles[role_name], permissions[code])

    admin = session.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    created_admin = admin is None
    if admin is None:
        admin = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            is_active=True,
        )
        session.add(admin)
        session.flush()

    _ensure_user_role(session, admin, roles["SuperAdmin"])
    for permission in permissions.values():
        _ensure_global_scope(session, admin, permission)

    session.commit()
    return {
        "permissions_created": created_permissions,
        "roles_created": created_roles,
        "admin_created": int(created_admin),
    }


def _run_with_engine(prod: bool, label: str) -> dict[str, int]:
    from app.core.config import get_settings
    from app.core.database import get_session_factory, init_engine
    from app.core.logging import setup_logging

    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    init_engine(settings)
    with get_session_factory()() as session:
        result = run_seed(session, prod=prod)
    print(f"{label} seed complete: {result}")
    return result


def seed_dev() -> dict[str, int]:
    return _run_with_engine(prod=False, label="Dev")


def seed_prod() -> dict[str, int]:
    return _run_with_engine(prod=True, label="Production")


if __name__ == "__main__":
    seed_dev()
