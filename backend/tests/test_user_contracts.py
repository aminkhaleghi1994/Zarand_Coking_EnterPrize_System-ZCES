import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.user import contracts
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="workplace contract tests require a real database (PG service in CI)",
)


@pytest.fixture()
def pg_session():
    engine = create_engine(_TEST_DATABASE_URL)  # type: ignore[arg-type]
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        run_seed(session, prod=False)
        yield session
    engine.dispose()


@requires_db
def test_get_workplace_with_parents_resolves_tree(pg_session):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.modules.user.models import Workplace

    workplace = pg_session.scalar(select(Workplace).where(Workplace.code == "CP1"))
    assert workplace is not None
    view = contracts.get_workplace_with_parents(pg_session, workplace.id)
    assert view is not None
    assert view.code == "CP1"
    assert view.complex_code == "CTR"
    assert view.is_active
    assert isinstance(view.company_id, uuid.UUID)


@requires_db
def test_get_workplace_with_parents_unknown_returns_none(pg_session):  # type: ignore[no-untyped-def]
    assert contracts.get_workplace_with_parents(pg_session, uuid.uuid4()) is None

@requires_db
def test_get_loan_requester_resolves_employee(pg_session):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.modules.user.models import Employee, User, Workplace

    workplace = pg_session.scalar(select(Workplace).where(Workplace.code == "CP1"))
    assert workplace is not None
    tag = uuid.uuid4().hex[:8]
    employee = Employee(
        national_id=f"8{uuid.uuid4().int % 10**9:09d}",
        personnel_code=f"LNC-{tag}",
        first_name="Ali",
        last_name="Loaner",
        workplace_id=workplace.id,
    )
    pg_session.add(employee)
    pg_session.flush()  # column defaults (uuid id) materialize at flush
    user = User(
        email=f"loaner-{tag}@zarandsteel.ir",
        username=f"loaner-{tag}",
        hashed_password=hash_password("loaner-password-1"),
        employee_id=employee.id,
        is_active=True,
    )
    pg_session.add(user)
    pg_session.commit()

    view = contracts.get_loan_requester(pg_session, user.id)
    assert view is not None
    assert view.employee_id == employee.id
    assert view.workplace_id == workplace.id
    assert view.display_name == "Ali Loaner"
    assert view.is_active
    assert view.company_id is not None and view.complex_id is not None

    employee.is_active = False
    pg_session.commit()
    deactivated = contracts.get_loan_requester(pg_session, user.id)
    assert deactivated is not None and deactivated.is_active is False


@requires_db
def test_get_loan_requester_without_employee_returns_none(pg_session):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.modules.user.models import User

    admin = pg_session.scalar(select(User).where(User.email.like("admin@%")))
    assert admin is not None
    assert contracts.get_loan_requester(pg_session, admin.id) is None


def _make_scoped_user(
    pg_session,  # type: ignore[no-untyped-def]
    *,
    tag: str,
    role_name: str | None,
    permission_code: str,
    level: str,
    workplace_id,  # type: ignore[no-untyped-def]
    complex_id,  # type: ignore[no-untyped-def]
    active: bool = True,
):
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.modules.user.models import (
        Employee,
        Role,
        ScopeAssignment,
        ScopeLevel,
        User,
        UserRole,
    )

    employee = Employee(
        national_id=f"8{uuid.uuid4().int % 10**9:09d}",
        personnel_code=f"RCP-{tag}",
        first_name="Scoped",
        last_name=f"User {tag}",
        workplace_id=workplace_id,
        is_active=True,
    )
    pg_session.add(employee)
    pg_session.flush()
    user = User(
        email=f"scoped-{tag}@zarandsteel.ir",
        username=f"scoped-{tag}",
        hashed_password=hash_password("scoped-password-1"),
        employee_id=employee.id,
        is_active=active,
    )
    pg_session.add(user)
    pg_session.flush()
    if role_name is not None:
        role = pg_session.scalar(select(Role).where(Role.name == role_name))
        assert role is not None
        pg_session.add(UserRole(user_id=user.id, role_id=role.id))
    module, resource, operation = permission_code.split(":", 2)
    pg_session.add(
        ScopeAssignment(
            user_id=user.id,
            level=ScopeLevel(level),
            module=module,
            resource=resource,
            operation=operation,
            complex_id=complex_id if level == "complex" else None,
            workplace_id=workplace_id if level == "workplace" else None,
        )
    )
    pg_session.commit()
    return user


@requires_db
def test_get_user_id_for_employee(pg_session):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.modules.user.models import Workplace

    workplace = pg_session.scalar(select(Workplace).where(Workplace.code == "CP1"))
    assert workplace is not None
    user = _make_scoped_user(
        pg_session,
        tag=uuid.uuid4().hex[:6],
        role_name=None,
        permission_code="warehouse:request:decide",
        level="workplace",
        workplace_id=workplace.id,
        complex_id=workplace.complex_id,
    )
    assert contracts.get_user_id_for_employee(pg_session, user.employee_id) == user.id
    assert contracts.get_user_id_for_employee(pg_session, uuid.uuid4()) is None


@requires_db
def test_recipient_resolution_workplace_scope(pg_session):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.modules.user.models import Workplace

    cp1 = pg_session.scalar(select(Workplace).where(Workplace.code == "CP1"))
    cp2 = pg_session.scalar(select(Workplace).where(Workplace.code == "CP2"))
    sp = pg_session.scalar(select(Workplace).where(Workplace.code == "SP"))
    assert cp1 is not None and cp2 is not None and sp is not None

    holder = _make_scoped_user(
        pg_session,
        tag=uuid.uuid4().hex[:6],
        role_name="WarehouseApprover",
        permission_code="warehouse:request:decide",
        level="workplace",
        workplace_id=cp1.id,
        complex_id=cp1.complex_id,
    )
    recipients = contracts.get_recipient_user_ids(
        pg_session, "warehouse:request:decide", cp1.id
    )
    assert holder.id in recipients
    # Implicit deny: a different workplace's scoped holder does not cross over.
    recipients_cp2 = contracts.get_recipient_user_ids(
        pg_session, "warehouse:request:decide", cp2.id
    )
    assert holder.id not in recipients_cp2
    recipients_sp = contracts.get_recipient_user_ids(
        pg_session, "warehouse:request:decide", sp.id
    )
    assert holder.id not in recipients_sp


@requires_db
def test_recipient_resolution_complex_scope(pg_session):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.modules.user.models import Workplace

    cp1 = pg_session.scalar(select(Workplace).where(Workplace.code == "CP1"))
    cp2 = pg_session.scalar(select(Workplace).where(Workplace.code == "CP2"))
    sp = pg_session.scalar(select(Workplace).where(Workplace.code == "SP"))
    assert cp1 is not None and cp2 is not None and sp is not None

    complex_holder = _make_scoped_user(
        pg_session,
        tag=uuid.uuid4().hex[:6],
        role_name="WarehouseApprover",
        permission_code="warehouse:request:decide",
        level="complex",
        workplace_id=cp1.id,  # anchor employee; scope is complex-level
        complex_id=cp1.complex_id,
    )
    for workplace in (cp1, cp2):
        recipients = contracts.get_recipient_user_ids(
            pg_session, "warehouse:request:decide", workplace.id
        )
        assert complex_holder.id in recipients
    recipients_sp = contracts.get_recipient_user_ids(
        pg_session, "warehouse:request:decide", sp.id
    )
    assert complex_holder.id not in recipients_sp


@requires_db
def test_recipient_resolution_requires_role_permission(pg_session):  # type: ignore[no-untyped-def]
    """Implicit deny: scope alone (without a role granting the permission)
    never makes a user a recipient."""
    from sqlalchemy import select

    from app.modules.user.models import Workplace

    cp1 = pg_session.scalar(select(Workplace).where(Workplace.code == "CP1"))
    assert cp1 is not None
    scope_only = _make_scoped_user(
        pg_session,
        tag=uuid.uuid4().hex[:6],
        role_name=None,
        permission_code="warehouse:request:decide",
        level="workplace",
        workplace_id=cp1.id,
        complex_id=cp1.complex_id,
    )
    recipients = contracts.get_recipient_user_ids(
        pg_session, "warehouse:request:decide", cp1.id
    )
    assert scope_only.id not in recipients


@requires_db
def test_recipient_resolution_excludes_deactivated(pg_session):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.modules.user.models import Workplace

    cp1 = pg_session.scalar(select(Workplace).where(Workplace.code == "CP1"))
    assert cp1 is not None
    deactivated = _make_scoped_user(
        pg_session,
        tag=uuid.uuid4().hex[:6],
        role_name="WarehouseApprover",
        permission_code="warehouse:request:decide",
        level="workplace",
        workplace_id=cp1.id,
        complex_id=cp1.complex_id,
        active=False,
    )
    recipients = contracts.get_recipient_user_ids(
        pg_session, "warehouse:request:decide", cp1.id
    )
    assert deactivated.id not in recipients


@requires_db
def test_recipient_resolution_global_scope(pg_session):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.modules.user.models import User, Workplace

    admin = pg_session.scalar(select(User).where(User.email.like("admin@%")))
    sp = pg_session.scalar(select(Workplace).where(Workplace.code == "SP"))
    assert admin is not None and sp is not None
    recipients = contracts.get_recipient_user_ids(
        pg_session, "warehouse:request:decide", sp.id
    )
    assert admin.id in recipients
    # workplace_id=None → global-scope holders only (unanchored events).
    global_only = contracts.get_recipient_user_ids(
        pg_session, "warehouse:request:decide", None
    )
    assert admin.id in global_only


@requires_db
def test_recipient_resolution_unknown_workplace(pg_session):  # type: ignore[no-untyped-def]
    assert contracts.get_recipient_user_ids(
        pg_session, "warehouse:request:decide", uuid.uuid4()
    ) == []
