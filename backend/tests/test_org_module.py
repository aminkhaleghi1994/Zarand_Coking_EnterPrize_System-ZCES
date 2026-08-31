import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.core.security import hash_password
from app.main import create_app
from app.modules.user.models import Company, Complex, User, Workplace
from app.seeds.seed_dev import ORG_TREE, run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="org integration tests require a real database (PG service in CI)",
)

_RUN = uuid.uuid4().hex[:6]


def _get_or_create_role(session, name: str, description: str = ""):  # type: ignore[no-untyped-def]
    from app.modules.user.models import Role

    existing = session.scalar(select(Role).where(Role.name == name, Role.deleted_at.is_(None)))
    if existing:
        return existing
    role = Role(name=name, description=description)
    session.add(role)
    session.flush()
    return role


def _get_or_create_user(session, email: str, username: str, password: str):  # type: ignore[no-untyped-def]

    existing = session.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if existing:
        return existing
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


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


@requires_db
class TestOrganizationSeed:
    def test_seed_creates_exact_tree(self, pg) -> None:  # type: ignore[no-untyped-def]
        _client, factory = pg
        with factory() as session:
            company = session.scalar(select(Company))
            assert company is not None
            assert company.code == ORG_TREE["company"]["code"]

            complexes = session.scalars(select(Complex)).all()
            assert {c.code for c in complexes} == {"CTR", "SM"}

            workplaces = session.scalars(select(Workplace)).all()
            assert {w.code for w in workplaces} == {"KCM", "CP1", "CP2", "SP"}

            by_code = {w.code: w for w in workplaces}
            ctr = session.scalar(select(Complex).where(Complex.code == "CTR"))
            assert ctr is not None
            assert by_code["KCM"].complex_id == ctr.id
            assert by_code["CP1"].complex_id == ctr.id
            sm = session.scalar(select(Complex).where(Complex.code == "SM"))
            assert sm is not None
            assert by_code["SP"].complex_id == sm.id

    def test_seed_org_idempotent(self, pg) -> None:  # type: ignore[no-untyped-def]
        _client, factory = pg
        with factory() as session:
            second = run_seed(session, prod=False)
        assert second["org_created"] == 0
        with factory() as session:
            assert len(session.scalars(select(Complex)).all()) == 2
            assert len(session.scalars(select(Workplace)).all()) == 4


@requires_db
class TestOrgEndpoints:
    def test_admin_sees_full_tree(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, _factory = pg
        response = client.get(
            "/api/v1/org/complexes", params={"page_size": 50}, headers=_bearer(_admin_token(client))
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 2
        assert {item["code"] for item in body["items"]} == {"CTR", "SM"}

        response = client.get(
            "/api/v1/org/workplaces",
            params={"page_size": 50},
            headers=_bearer(_admin_token(client)),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 4

    def test_workplace_scope_narrows_results(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        from app.modules.user.models import (
            Permission,
            RolePermission,
            ScopeAssignment,
            ScopeLevel,
            UserRole,
        )

        email = f"org-viewer-{_RUN}@zarandsteel.ir"
        with factory() as session:
            workplace = session.scalar(select(Workplace).where(Workplace.code == "CP1"))
            permission = session.scalar(
                select(Permission).where(Permission.code == "user:org:read")
            )
            assert workplace is not None and permission is not None
            role = _get_or_create_role(session, f"OrgViewer-{_RUN}", "test viewer")
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            user = _get_or_create_user(session, email, f"org-viewer-{_RUN}", "viewer-password-1")
            session.add(UserRole(user_id=user.id, role_id=role.id))
            session.add(
                ScopeAssignment(
                    user_id=user.id,
                    level=ScopeLevel.WORKPLACE,
                    module="user",
                    resource="org",
                    operation="read",
                    workplace_id=workplace.id,
                )
            )
            session.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "viewer-password-1"},
        )
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]

        complexes = client.get(
            "/api/v1/org/complexes", params={"page_size": 50}, headers=_bearer(token)
        ).json()
        assert complexes["total"] == 1
        assert complexes["items"][0]["code"] == "CTR"

        workplaces = client.get(
            "/api/v1/org/workplaces", params={"page_size": 50}, headers=_bearer(token)
        ).json()
        assert workplaces["total"] == 1
        assert workplaces["items"][0]["code"] == "CP1"

    def test_roleless_user_denied(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        email = f"org-roleless-{_RUN}@zarandsteel.ir"
        with factory() as session:
            _get_or_create_user(session, email, f"org-roleless-{_RUN}", "roleless-password-1")
            session.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "roleless-password-1"},
        )
        token = response.json()["access_token"]
        response = client.get("/api/v1/org/complexes", headers=_bearer(token))
        assert response.status_code == 403
        assert response.json()["code"] == "AUTHORIZATION_DENIED"

    def test_user_without_org_scope_sees_empty(self, pg) -> None:  # type: ignore[no-untyped-def]
        """Permission without any unit coverage yields an empty page, not an error."""
        client, factory = pg
        from app.modules.user.models import (
            Permission,
            RolePermission,
            ScopeAssignment,
            ScopeLevel,
            UserRole,
        )

        email = f"org-noscope-{_RUN}@zarandsteel.ir"
        with factory() as session:
            permission = session.scalar(
                select(Permission).where(Permission.code == "user:org:read")
            )
            assert permission is not None
            role = _get_or_create_role(session, f"OrgNoScope-{_RUN}", "permission only")
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            user = _get_or_create_user(session, email, f"org-noscope-{_RUN}", "noscope-password-1")
            session.add(UserRole(user_id=user.id, role_id=role.id))
            session.add(
                ScopeAssignment(
                    user_id=user.id,
                    level=ScopeLevel.GLOBAL,
                    module="nothing",
                    resource="elsewhere",
                    operation="read",
                )
            )
            session.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "noscope-password-1"},
        )
        token = response.json()["access_token"]
        body = client.get(
            "/api/v1/org/complexes", params={"page_size": 50}, headers=_bearer(token)
        ).json()
        assert body["total"] == 0
        assert body["items"] == []
