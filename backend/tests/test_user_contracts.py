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
