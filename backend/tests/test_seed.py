import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base
from app.modules.user.models import Permission, Role, RolePermission, User
from app.seeds.seed_dev import UNSAFE_PASSWORDS, run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_database = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="a real DATABASE_URL is not configured",
)

TOTAL_PERMISSIONS = 8

WAREHOUSE_PERMISSION_CODES = {
    "warehouse:item:create",
    "warehouse:item:read",
    "warehouse:item:update",
    "warehouse:item:retire",
    "warehouse:warehouse:create",
    "warehouse:warehouse:read",
    "warehouse:warehouse:update",
    "warehouse:warehouse:retire",
    "warehouse:shelf:create",
    "warehouse:shelf:read",
    "warehouse:shelf:update",
    "warehouse:shelf:retire",
    "warehouse:stock:receive",
    "warehouse:stock:issue",
    "warehouse:stock:adjust",
    "warehouse:stock:read",
    "warehouse:alert:read",
}

WAREHOUSE_ROLE_EXPECTATIONS = {
    "WarehouseKeeper": {
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
    },
    "WarehouseApprover": {
        "warehouse:item:read",
        "warehouse:warehouse:read",
        "warehouse:shelf:read",
        "warehouse:stock:read",
        "warehouse:alert:read",
    },
}


@pytest.fixture()
def pg_session():
    engine = create_engine(_TEST_DATABASE_URL)  # type: ignore[arg-type]
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
    engine.dispose()


def _count(model, session):  # type: ignore[no-untyped-def]
    return len(session.scalars(select(model)).all())


@requires_database
def test_seed_creates_exact_state(pg_session):  # type: ignore[no-untyped-def]
    settings = get_settings()
    admin_email = (settings.INITIAL_ADMIN_EMAIL or "").strip().lower()

    result = run_seed(pg_session, prod=False)
    assert result["permissions_created"] + _count(Permission, pg_session) >= TOTAL_PERMISSIONS
    assert _count(Role, pg_session) >= 7
    assert result["admin_created"] in (0, 1)

    admin = pg_session.scalar(select(User).where(User.email == admin_email))
    assert admin is not None
    assert admin.is_active
    roles = {role.name for role in pg_session.scalars(select(Role)).all()}
    assert {
        "SuperAdmin",
        "HRAdmin",
        "WarehouseKeeper",
        "WarehouseApprover",
        "LoanOfficer",
        "Auditor",
        "Manager",
    } <= roles


@requires_database
def test_seed_is_idempotent(pg_session):  # type: ignore[no-untyped-def]
    run_seed(pg_session, prod=False)
    users_before = _count(User, pg_session)
    roles_before = _count(Role, pg_session)
    permissions_before = _count(Permission, pg_session)

    second = run_seed(pg_session, prod=False)
    assert second["admin_created"] == 0
    assert second["roles_created"] == 0
    assert second["permissions_created"] == 0
    assert _count(User, pg_session) == users_before
    assert _count(Role, pg_session) == roles_before
    assert _count(Permission, pg_session) == permissions_before


@requires_database
def test_seed_creates_warehouse_permissions(pg_session):  # type: ignore[no-untyped-def]
    run_seed(pg_session, prod=False)
    codes = set(pg_session.scalars(select(Permission.code)).all())
    assert codes >= WAREHOUSE_PERMISSION_CODES


@requires_database
def test_seed_maps_warehouse_roles(pg_session):  # type: ignore[no-untyped-def]
    run_seed(pg_session, prod=False)
    for role_name, expected_codes in WAREHOUSE_ROLE_EXPECTATIONS.items():
        role = pg_session.scalar(select(Role).where(Role.name == role_name))
        assert role is not None, role_name
        granted = set(
            pg_session.scalars(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            ).all()
        )
        assert expected_codes <= granted, role_name
    keeper_has_adjust = pg_session.scalar(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .where(Role.name == "WarehouseKeeper", Permission.code == "warehouse:stock:adjust")
    )
    assert keeper_has_adjust is None, "adjust must stay outside the keeper role (clarify Q1)"


@requires_database
def test_seed_prod_refuses_unsafe_password(pg_session):  # type: ignore[no-untyped-def]
    settings = get_settings()
    original = settings.INITIAL_ADMIN_PASSWORD
    try:
        for unsafe in UNSAFE_PASSWORDS:
            settings.INITIAL_ADMIN_PASSWORD = unsafe
            with pytest.raises(SystemExit, match="Refusing to seed production"):
                run_seed(pg_session, prod=True)
        settings.INITIAL_ADMIN_PASSWORD = ""
        with pytest.raises(SystemExit, match="must be set"):
            run_seed(pg_session, prod=True)
    finally:
        settings.INITIAL_ADMIN_PASSWORD = original
        run_seed(pg_session, prod=False)
