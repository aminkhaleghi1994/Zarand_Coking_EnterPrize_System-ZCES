from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.audit.contracts import write_audit
from app.modules.user.models import (
    Company,
    Complex,
    Permission,
    Role,
    RolePermission,
    ScopeAssignment,
    ScopeLevel,
    User,
    UserRole,
    Workplace,
)


class _UnitSpec(TypedDict):
    code: str
    name: str
    name_fa: str


class _ComplexSpec(TypedDict):
    code: str
    name: str
    name_fa: str
    workplaces: list[_UnitSpec]


class _OrgTree(TypedDict):
    company: _UnitSpec
    complexes: list[_ComplexSpec]


BASE_PERMISSIONS: list[tuple[str, str, str]] = [
    ("user:list:read", "List users", "مشاهده فهرست کاربران"),
    ("user:role:read", "Read roles", "مشاهده نقش‌ها"),
    ("user:role:create", "Create roles", "ایجاد نقش"),
    ("user:role:assign", "Assign roles", "تخصیص نقش"),
    ("user:permission:read", "Read permissions", "مشاهده مجوزها"),
    ("user:scope:assign", "Assign scopes", "تخصیص دامنه دسترسی"),
    ("user:employee:read", "View employees", "مشاهده کارکنان"),
    ("user:employee:read_full", "View full employee identifiers", "مشاهده کامل شناسه‌های کارکنان"),
    ("user:employee:create", "Create employees", "ایجاد کارمند"),
    ("user:employee:update", "Update employees", "ویرایش کارکنان"),
    ("user:employee:deactivate", "Deactivate employees", "غیرفعال‌سازی کارکنان"),
    ("user:password:set", "Set user passwords", "تنظیم گذرواژه کاربران"),
    ("user:org:read", "View organization structure", "مشاهده ساختار سازمانی"),
    ("audit:log:read", "Read audit logs", "مشاهده لاگ‌های ممیزی"),
    ("audit:log:read_full", "Read full audit snapshots", "مشاهده کامل اسنپ‌شات‌های ممیزی"),
    ("warehouse:item:create", "Create catalog items", "ایجاد کالا در کاتالوگ"),
    ("warehouse:item:read", "View catalog items", "مشاهده کالاهای کاتالوگ"),
    ("warehouse:item:update", "Update catalog items", "ویرایش کالاهای کاتالوگ"),
    ("warehouse:item:retire", "Retire catalog items", "بازنشسته‌کردن کالاهای کاتالوگ"),
    ("warehouse:warehouse:create", "Create warehouses", "ایجاد انبار"),
    ("warehouse:warehouse:read", "View warehouses", "مشاهده انبارها"),
    ("warehouse:warehouse:update", "Update warehouses", "ویرایش انبارها"),
    ("warehouse:warehouse:retire", "Retire warehouses", "بازنشسته‌کردن انبارها"),
    ("warehouse:shelf:create", "Create shelves", "ایجاد قفسه"),
    ("warehouse:shelf:read", "View shelves", "مشاهده قفسه‌ها"),
    ("warehouse:shelf:update", "Update shelves", "ویرایش قفسه‌ها"),
    ("warehouse:shelf:retire", "Retire shelves", "بازنشسته‌کردن قفسه‌ها"),
    ("warehouse:stock:receive", "Receive stock", "ثبت ورودی کالا"),
    ("warehouse:stock:issue", "Issue stock", "ثبت خروجی کالا"),
    ("warehouse:stock:adjust", "Adjust stock", "اصلاح موجودی کالا"),
    ("warehouse:stock:read", "View stock", "مشاهده موجودی کالا"),
    ("warehouse:alert:read", "View low-stock alerts", "مشاهده هشدارهای کمبود موجودی"),
    ("warehouse:request:read", "View item requests", "مشاهده درخواست‌های کالا"),
    ("warehouse:request:decide", "Approve or reject item requests", "تأیید یا رد درخواست‌های کالا"),
    ("warehouse:request:fulfill", "Fulfill item requests", "انجام درخواست‌های کالا"),
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
    "WarehouseKeeper": [
        "warehouse:item:create",
        "warehouse:item:read",
        "warehouse:item:update",
        "warehouse:item:retire",
        "warehouse:warehouse:read",
        "warehouse:shelf:create",
        "warehouse:shelf:read",
        "warehouse:shelf:update",
        "warehouse:shelf:retire",
        "warehouse:stock:receive",
        "warehouse:stock:issue",
        "warehouse:stock:read",
        "warehouse:alert:read",
        "warehouse:request:read",
        "warehouse:request:fulfill",
    ],
    "WarehouseApprover": [
        "warehouse:item:read",
        "warehouse:warehouse:read",
        "warehouse:shelf:read",
        "warehouse:stock:read",
        "warehouse:alert:read",
        "warehouse:request:read",
        "warehouse:request:decide",
    ],
}

UNSAFE_PASSWORDS = {"change_me_now", "change_me", "admin", "password", "12345678"}

ORG_TREE: _OrgTree = {
    "company": {"code": "ZCS", "name": "Zarand Coking & Steel", "name_fa": "کک و فولاد زرند"},
    "complexes": [
        {
            "code": "CTR",
            "name": "Coking and Tar Refining Complex",
            "name_fa": "مجتمع کک‌سازی و پالایش قطران",
            "workplaces": [
                {"code": "KCM", "name": "Khamroud Coal Mine", "name_fa": "معدن زغال خامرود"},
                {"code": "CP1", "name": "Coke Plant 1", "name_fa": "کوک‌سازی ۱"},
                {"code": "CP2", "name": "Coke Plant 2", "name_fa": "کوک‌سازی ۲"},
            ],
        },
        {
            "code": "SM",
            "name": "Steelmaking Complex",
            "name_fa": "مجتمع فولادسازی",
            "workplaces": [
                {"code": "SP", "name": "Steel Plant", "name_fa": "واحد فولادسازی"},
            ],
        },
    ],
}


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


def _seed_organization(session: Session) -> int:
    """Idempotent org tree upsert keyed by natural codes. Returns created count."""
    created = 0
    company_spec = ORG_TREE["company"]
    company = session.scalar(select(Company).where(Company.code == company_spec["code"]))
    if company is None:
        company = Company(
            code=company_spec["code"],
            name=company_spec["name"],
            name_fa=company_spec["name_fa"],
        )
        session.add(company)
        session.flush()
        created += 1

    for complex_spec in ORG_TREE["complexes"]:
        complex_ = session.scalar(select(Complex).where(Complex.code == complex_spec["code"]))
        if complex_ is None:
            complex_ = Complex(
                company_id=company.id,
                code=complex_spec["code"],
                name=complex_spec["name"],
                name_fa=complex_spec["name_fa"],
            )
            session.add(complex_)
            session.flush()
            created += 1
        for workplace_spec in complex_spec["workplaces"]:
            workplace = session.scalar(
                select(Workplace).where(Workplace.code == workplace_spec["code"])
            )
            if workplace is None:
                session.add(
                    Workplace(
                        complex_id=complex_.id,
                        code=workplace_spec["code"],
                        name=workplace_spec["name"],
                        name_fa=workplace_spec["name_fa"],
                    )
                )
                session.flush()
                created += 1
    return created


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

    org_created = _seed_organization(session)
    if org_created > 0:
        write_audit(
            session,
            action="ORG_SEEDED",
            entity_type="organization",
            actor_user_id=None,
            after={"records_created": org_created},
            critical=True,
        )

    session.commit()
    return {
        "permissions_created": created_permissions,
        "roles_created": created_roles,
        "admin_created": int(created_admin),
        "org_created": org_created,
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
