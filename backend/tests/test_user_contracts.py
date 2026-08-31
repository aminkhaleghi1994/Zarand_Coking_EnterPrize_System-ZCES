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
