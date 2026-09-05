"""Settings module tests (Phase 9, T003-T007): typed validation,
version-guarded audited updates, contract fallback, endpoint gates, seed
idempotency."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.core.errors import AppError
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.settings import contracts
from app.modules.settings.defaults import (
    ALERTING_LOW_STOCK_ENABLED,
    FLAGS_LOAN_MODULE_ENABLED,
    NOTIFICATIONS_DEFAULT_RECIPIENTS,
    REQUESTS_APPROVAL_REQUIRE_NOTE,
    SETTING_DEFAULTS,
    SETTING_KEYS,
)
from app.modules.settings.models import Setting
from app.modules.settings.schemas import validate_setting_value
from app.modules.user.models import User
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="settings tests require real PostgreSQL (JSONB values)",
)


# --- T003: typed validation ---


def test_validate_setting_value_all_types() -> None:
    assert validate_setting_value(ALERTING_LOW_STOCK_ENABLED, False) == (False, "boolean")
    assert validate_setting_value(REQUESTS_APPROVAL_REQUIRE_NOTE, True) == (True, "boolean")
    assert validate_setting_value(FLAGS_LOAN_MODULE_ENABLED, True) == (True, "boolean")
    assert validate_setting_value(NOTIFICATIONS_DEFAULT_RECIPIENTS, ["abc"]) == (
        ["abc"],
        "json",
    )


def test_validate_setting_value_unknown_key() -> None:
    with pytest.raises(AppError) as excinfo:
        validate_setting_value("not.a.key", True)
    assert excinfo.value.code == "VALIDATION_ERROR"
    assert excinfo.value.details["key"] == "not.a.key"


def test_validate_setting_value_wrong_types() -> None:
    with pytest.raises(AppError):
        validate_setting_value(ALERTING_LOW_STOCK_ENABLED, "yes")  # str, not bool
    with pytest.raises(AppError):
        validate_setting_value(NOTIFICATIONS_DEFAULT_RECIPIENTS, "abc")  # not json
    with pytest.raises(AppError):
        validate_setting_value(FLAGS_LOAN_MODULE_ENABLED, 1)  # int, not bool


def test_fixed_key_set_is_covered_by_defaults() -> None:
    assert len(SETTING_DEFAULTS) == 8
    assert len(SETTING_KEYS) == len(SETTING_DEFAULTS)


# --- T004/T006: service + contracts (real PG) ---

_CONTEXT_KWARGS = {"user_id": str(uuid.uuid4()), "is_active": True}


@requires_db
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
        json={
            "email": settings.INITIAL_ADMIN_EMAIL,
            "password": settings.INITIAL_ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(factory, tag: str) -> uuid.UUID:  # type: ignore[no-untyped-def]
    from app.core.security import hash_password

    with factory() as session:
        existing = session.scalar(
            select(User).where(User.email == f"settings-{tag}@zarandsteel.ir")
        )
        if existing is not None:
            return existing.id
        user = User(
            email=f"settings-{tag}@zarandsteel.ir",
            username=f"settings-{tag}",
            hashed_password=hash_password("settings-password-1"),
        )
        session.add(user)
        session.commit()
        return user.id


@requires_db
def test_update_setting_happy_path_with_audit(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)

    listed = client.get("/api/v1/settings", headers=_bearer(token))
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 8
    keys = {item["key"] for item in body["items"]}
    assert ALERTING_LOW_STOCK_ENABLED in keys
    target = next(item for item in body["items"] if item["key"] == REQUESTS_APPROVAL_REQUIRE_NOTE)
    assert target["value"] is True

    patched = client.patch(
        f"/api/v1/settings/{REQUESTS_APPROVAL_REQUIRE_NOTE}",
        json={"value": False, "version": target["version"]},
        headers=_bearer(token),
    )
    assert patched.status_code == 200, patched.text
    updated = patched.json()
    assert updated["value"] is False
    assert updated["version"] == target["version"] + 1

    with factory() as session:
        audit_row = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "SETTING_UPDATED",
                AuditLog.entity_type == "setting",
            )
        )
        assert audit_row is not None
        assert audit_row.after_snapshot is not None
        assert audit_row.after_snapshot["value"] is False
        assert audit_row.before_snapshot is not None
        assert audit_row.before_snapshot["value"] is True
        assert audit_row.actor_user_id is not None

    # restore for other tests
    restore = client.patch(
        f"/api/v1/settings/{REQUESTS_APPROVAL_REQUIRE_NOTE}",
        json={"value": True, "version": updated["version"]},
        headers=_bearer(token),
    )
    assert restore.status_code == 200


@requires_db
def test_update_setting_stale_version(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    listed = client.get("/api/v1/settings", headers=_bearer(token))
    target = next(
        item
        for item in listed.json()["items"]
        if item["key"] == ALERTING_LOW_STOCK_ENABLED
    )
    stale = client.patch(
        f"/api/v1/settings/{ALERTING_LOW_STOCK_ENABLED}",
        json={"value": False, "version": target["version"] + 5},
        headers=_bearer(token),
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_VERSION"


@requires_db
def test_update_setting_unknown_key_and_wrong_type(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    unknown = client.patch(
        "/api/v1/settings/not.a.key",
        json={"value": True, "version": 1},
        headers=_bearer(token),
    )
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "VALIDATION_ERROR"

    wrong = client.patch(
        f"/api/v1/settings/{ALERTING_LOW_STOCK_ENABLED}",
        json={"value": "yes", "version": 1},
        headers=_bearer(token),
    )
    assert wrong.status_code == 422
    assert wrong.json()["code"] == "VALIDATION_ERROR"


@requires_db
def test_settings_endpoints_require_permission(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    unauthenticated = client.get("/api/v1/settings")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "AUTHENTICATION_REQUIRED"

    # roleless user: has neither permission nor scope
    tag = uuid.uuid4().hex[:6]
    _make_user(factory, tag)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": f"settings-{tag}@zarandsteel.ir", "password": "settings-password-1"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    denied = client.get("/api/v1/settings", headers=_bearer(token))
    assert denied.status_code == 403
    assert denied.json()["code"] == "AUTHORIZATION_DENIED"


@requires_db
def test_contracts_fallback_and_read(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    with factory() as session:
        value = contracts.get_setting_bool(
            session, ALERTING_LOW_STOCK_ENABLED, default=True
        )
        assert value is True  # seeded row
        missing = contracts.get_setting(
            session, "not.a.key", default="fallback"
        )
        assert missing == "fallback"
        recipients = contracts.get_setting(
            session, NOTIFICATIONS_DEFAULT_RECIPIENTS, default=[]
        )
        assert recipients == []


@requires_db
def test_seed_settings_idempotent(pg):  # type: ignore[no-untyped-def]
    _client, factory = pg
    with factory() as session:
        result = run_seed(session, prod=False)
        assert result["settings_created"] == 0  # rows already exist
        rows = session.scalars(select(Setting)).all()
        assert {row.key for row in rows} == SETTING_KEYS
