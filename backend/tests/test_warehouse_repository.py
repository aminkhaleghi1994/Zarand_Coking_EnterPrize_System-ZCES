import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.common.scope import ScopeContext
from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.main import create_app
from app.modules.user import repository as user_repository
from app.modules.user.models import User
from app.modules.user.schemas import PageParams
from app.modules.warehouse import repository, service
from app.modules.warehouse.schemas import ItemCreateIn, ItemRetireIn
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="warehouse integration tests require a real database (PG service in CI)",
)

_RUN = uuid.uuid4().hex[:6]
_counter = {"n": 0}


def _unique_tag() -> str:
    _counter["n"] += 1
    return f"{_RUN}-{_counter['n']}"


@pytest.fixture()
def pg():
    engine = create_engine(_TEST_DATABASE_URL)  # type: ignore[arg-type]
    Base.metadata.create_all(engine)
    dispose_engine()
    init_engine(get_settings())

    factory = sessionmaker(bind=engine)
    with factory() as session:
        run_seed(session, prod=False)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client, factory

    dispose_engine()
    engine.dispose()


def _admin_token(client: TestClient) -> str:
    settings = get_settings()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": settings.INITIAL_ADMIN_EMAIL, "password": settings.INITIAL_ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin_context(factory) -> ScopeContext:  # type: ignore[no-untyped-def]
    with factory() as session:
        settings = get_settings()
        admin = session.scalar(
            select(User).where(User.email == (settings.INITIAL_ADMIN_EMAIL or "").lower())
        )
        assert admin is not None
        context = user_repository.load_scope_context(session, str(admin.id))
    assert context is not None
    return context


def _item_payload(tag: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": f"Ball bearing {tag}",
        "name_fa": f"بلبرینگ {tag}",
        "code": f"BB-{tag}",
        "unit": "ad",
        "min_quantity": "10.000",
        "description": None,
    }
    payload.update(overrides)
    return payload


@requires_db
def test_search_items_by_name_fa_and_code(pg):  # type: ignore[no-untyped-def]
    _client, factory = pg
    context = _admin_context(factory)
    tag = _unique_tag()
    with factory() as session:
        created = service.create_item(session, context, ItemCreateIn(**_item_payload(tag)))  # type: ignore[arg-type]

        by_name = repository.search_items(session, PageParams(), search=f"bearing {tag}")
        by_code = repository.search_items(session, PageParams(), search=f"bb-{tag.upper()}")
        by_fa = repository.search_items(session, PageParams(), search=f"بلبرینگ {tag}")
        empty = repository.search_items(session, PageParams(), search="no-such-item-xyz")

    assert [i.id for i in by_name.items] == [created.id]
    assert [i.id for i in by_code.items] == [created.id]
    assert [i.id for i in by_fa.items] == [created.id]
    assert empty.total == 0


@requires_db
def test_search_excludes_retired_items(pg):  # type: ignore[no-untyped-def]
    _client, factory = pg
    context = _admin_context(factory)
    tag = _unique_tag()
    with factory() as session:
        created = service.create_item(session, context, ItemCreateIn(**_item_payload(tag)))  # type: ignore[arg-type]
        service.retire_item(session, context, created.id, ItemRetireIn(version=created.version))
        page = repository.search_items(session, PageParams(), search=f"bearing {tag}")
    assert page.total == 0


@requires_db
def test_search_pagination_envelope(pg):  # type: ignore[no-untyped-def]
    _client, factory = pg
    context = _admin_context(factory)
    tag = _unique_tag()
    with factory() as session:
        for index in range(3):
            service.create_item(
                session,
                context,
                ItemCreateIn(**_item_payload(f"{tag}-{index}")),  # type: ignore[arg-type]
            )
        page = repository.search_items(session, PageParams(page=1, page_size=2), search=tag)
    assert page.total == 3
    assert len(page.items) == 2
    assert page.page == 1
    assert page.page_size == 2
