import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.main import create_app
from app.modules.user.models import RefreshToken, User
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="auth integration tests require a real database (PG service in CI)",
)


@pytest.fixture()
def pg_app():
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


def _login(client: TestClient, email: str, password: str) -> dict:  # type: ignore[type-arg]
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-return-value]


@requires_db
def test_login_success_returns_pair_without_leaking(pg_app):  # type: ignore[no-untyped-def]
    client, _ = pg_app
    settings = get_settings()
    body = _login(client, settings.INITIAL_ADMIN_EMAIL, settings.INITIAL_ADMIN_PASSWORD)
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["roles"] == ["SuperAdmin"]
    assert body["access_expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert "hashed_password" not in body["user"]
    assert "password" not in str(body)


@requires_db
def test_login_failure_is_generic_for_all_cases(pg_app):  # type: ignore[no-untyped-def]
    client, _ = pg_app
    settings = get_settings()
    bodies = [
        {"email": "ghost@nowhere.ir", "password": "whatever-pass-1"},
        {"email": settings.INITIAL_ADMIN_EMAIL, "password": "wrong-password-1"},
    ]
    responses = [client.post("/api/v1/auth/login", json=b) for b in bodies]
    for response in responses:
        assert response.status_code == 401
        assert response.json()["code"] == "AUTHENTICATION_REQUIRED"
        assert response.json()["message"] == "Invalid credentials"
    assert responses[0].json()["message"] == responses[1].json()["message"]


@requires_db
def test_refresh_rotation_and_reuse_detection(pg_app):  # type: ignore[no-untyped-def]
    client, factory = pg_app
    settings = get_settings()
    body = _login(client, settings.INITIAL_ADMIN_EMAIL, settings.INITIAL_ADMIN_PASSWORD)
    first_refresh = body["refresh_token"]

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert rotated.status_code == 200
    second_refresh = rotated.json()["refresh_token"]
    assert second_refresh != first_refresh

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert replay.status_code == 401

    family_killed = client.post("/api/v1/auth/refresh", json={"refresh_token": second_refresh})
    assert family_killed.status_code == 401

    with factory() as session:
        from sqlalchemy import select

        hashes = session.scalars(select(RefreshToken.token_hash)).all()
        assert all(len(h) == 64 for h in hashes)
        assert first_refresh not in hashes and second_refresh not in hashes


@requires_db
def test_logout_revokes_family(pg_app):  # type: ignore[no-untyped-def]
    client, _ = pg_app
    settings = get_settings()
    body = _login(client, settings.INITIAL_ADMIN_EMAIL, settings.INITIAL_ADMIN_PASSWORD)
    access = body["access_token"]
    out = client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]})
    assert out.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    again = client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]})
    assert again.status_code == 401


@requires_db
def test_me_requires_valid_token(pg_app):  # type: ignore[no-untyped-def]
    client, _ = pg_app
    no_token = client.get("/api/v1/auth/me")
    assert no_token.status_code == 401
    bad = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert bad.status_code == 401
    assert bad.json()["code"] == "AUTHENTICATION_REQUIRED"


@requires_db
def test_roleless_user_gets_403_on_admin_endpoints(pg_app):  # type: ignore[no-untyped-def]
    client, factory = pg_app
    from sqlalchemy import select

    from app.core.security import hash_password

    with factory() as session:
        existing = session.scalar(select(User).where(User.email == "roleless@zarandsteel.ir"))
        if existing is None:
            session.add(
                User(
                    email="roleless@zarandsteel.ir",
                    username="roleless",
                    hashed_password=hash_password("Roleless-2026!"),
                )
            )
            session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "roleless@zarandsteel.ir", "password": "Roleless-2026!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for path in ("/api/v1/users", "/api/v1/roles", "/api/v1/audit-logs"):
        response = client.get(path, headers=headers)
        assert response.status_code == 403, path
        assert response.json()["code"] == "AUTHORIZATION_DENIED"
