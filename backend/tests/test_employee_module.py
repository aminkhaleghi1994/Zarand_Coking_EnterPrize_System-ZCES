import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.main import create_app
from app.modules.user.models import Employee, Workplace
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="employee integration tests require a real database (PG service in CI)",
)

_RUN = uuid.uuid4().hex[:6]
_NI_BASE = uuid.uuid4().int % 100000
_EMPLOYEE_PASSWORD = "sara-password-1"

_counter = {"n": 0}


def _emp_email(tag: str) -> str:
    _counter["n"] += 1
    return f"emp-{_RUN}-{tag}-{_counter['n']}@zarandsteel.ir"


def _emp_national_id() -> str:
    _counter["n"] += 1
    return f"9{_NI_BASE:05d}{_counter['n']:04d}"


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
    from app.modules.user.models import User

    existing = session.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if existing:
        return existing
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password_static(password),
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def hash_password_static(password: str) -> str:
    from app.core.security import hash_password

    return hash_password(password)


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


def _workplace_id(factory, code: str) -> uuid.UUID:  # type: ignore[no-untyped-def]
    with factory() as session:
        workplace = session.scalar(select(Workplace).where(Workplace.code == code))
        assert workplace is not None
        return workplace.id


def _employee_payload(workplace_id: uuid.UUID, email: str) -> dict:
    national_id = _emp_national_id()
    return {
        "national_id": national_id,
        "personnel_code": f"PC-{national_id[-6:]}-{_RUN}",
        "first_name": "Sara",
        "last_name": "Ahmadi",
        "first_name_fa": "سارا",
        "last_name_fa": "احمدی",
        "workplace_id": str(workplace_id),
        "user": {
            "email": email,
            "username": email.split("@")[0][:100],
            "password": _EMPLOYEE_PASSWORD,
        },
    }


def _create_employee(client: TestClient, factory, workplace_code: str, tag: str) -> dict:  # type: ignore[no-untyped-def]
    wid = _workplace_id(factory, workplace_code)
    email = _emp_email(tag)
    response = client.post(
        "/api/v1/employees",
        json=_employee_payload(wid, email),
        headers=_bearer(_admin_token(client)),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    body["_email"] = email
    return body


def _active_employee_count(factory) -> int:  # type: ignore[no-untyped-def]
    with factory() as session:
        return (
            session.scalar(
                select(func.count()).select_from(Employee).where(Employee.deleted_at.is_(None))
            )
            or 0
        )


@requires_db
class TestEmployeeCreation:
    def test_create_returns_employee_and_user_signs_in(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        body = _create_employee(client, factory, "CP1", "create")
        assert body["is_active"] is True
        assert body["workplace"]["code"] == "CP1"
        assert body["complex"]["code"] == "CTR"

        login = client.post(
            "/api/v1/auth/login",
            json={"email": body["_email"], "password": _EMPLOYEE_PASSWORD},
        )
        assert login.status_code == 200, login.text

    def test_duplicate_national_id_rejected_with_field(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        wid = _workplace_id(factory, "CP1")
        headers = _bearer(_admin_token(client))
        payload = _employee_payload(wid, _emp_email("dupni1"))
        first = client.post("/api/v1/employees", json=payload, headers=headers)
        assert first.status_code == 201

        second_payload = _employee_payload(wid, _emp_email("dupni2"))
        second_payload["national_id"] = payload["national_id"]
        second = client.post("/api/v1/employees", json=second_payload, headers=headers)
        assert second.status_code == 409
        assert second.json()["code"] == "DUPLICATE_RESOURCE"
        assert "national" in second.json()["message"].lower()

    def test_duplicate_personnel_code_rejected(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        wid = _workplace_id(factory, "CP1")
        headers = _bearer(_admin_token(client))
        payload = _employee_payload(wid, _emp_email("duppc1"))
        first = client.post("/api/v1/employees", json=payload, headers=headers)
        assert first.status_code == 201

        second_payload = _employee_payload(wid, _emp_email("duppc2"))
        second_payload["personnel_code"] = payload["personnel_code"]
        second = client.post("/api/v1/employees", json=second_payload, headers=headers)
        assert second.status_code == 409
        assert "personnel" in second.json()["message"].lower()

    def test_duplicate_email_rolls_back_employee(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        wid = _workplace_id(factory, "CP1")
        headers = _bearer(_admin_token(client))
        payload = _employee_payload(wid, _emp_email("dupemail"))
        first = client.post("/api/v1/employees", json=payload, headers=headers)
        assert first.status_code == 201
        before = _active_employee_count(factory)

        repeat = _employee_payload(wid, payload["user"]["email"])
        second = client.post("/api/v1/employees", json=repeat, headers=headers)
        assert second.status_code == 409
        assert _active_employee_count(factory) == before

    def test_identity_reusable_after_deactivation(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        wid = _workplace_id(factory, "CP1")
        headers = _bearer(_admin_token(client))
        payload = _employee_payload(wid, _emp_email("reuse1"))
        first = client.post("/api/v1/employees", json=payload, headers=headers)
        assert first.status_code == 201

        deactivated = client.post(
            f"/api/v1/employees/{first.json()['id']}/deactivate",
            json={"version": first.json()["version"]},
            headers=headers,
        )
        assert deactivated.status_code == 200, deactivated.text

        recreated_payload = _employee_payload(wid, _emp_email("reuse2"))
        recreated_payload["national_id"] = payload["national_id"]
        recreated = client.post("/api/v1/employees", json=recreated_payload, headers=headers)
        assert recreated.status_code == 201, recreated.text

    def test_national_id_validation(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        wid = _workplace_id(factory, "CP1")
        payload = _employee_payload(wid, _emp_email("badni"))
        payload["national_id"] = "12345"
        response = client.post(
            "/api/v1/employees", json=payload, headers=_bearer(_admin_token(client))
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"


@requires_db
class TestDeactivationCascade:
    def test_deactivate_kills_user_session(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        created = _create_employee(client, factory, "CP1", "cascade")

        login = client.post(
            "/api/v1/auth/login",
            json={"email": created["_email"], "password": _EMPLOYEE_PASSWORD},
        )
        assert login.status_code == 200
        refresh_token = login.json()["refresh_token"]

        deactivated = client.post(
            f"/api/v1/employees/{created['id']}/deactivate",
            json={"version": created["version"]},
            headers=_bearer(_admin_token(client)),
        )
        assert deactivated.status_code == 200, deactivated.text
        assert deactivated.json()["is_active"] is False

        replay = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert replay.status_code == 401

        login_again = client.post(
            "/api/v1/auth/login",
            json={"email": created["_email"], "password": _EMPLOYEE_PASSWORD},
        )
        assert login_again.status_code == 401

    def test_reactivate_restores_sign_in(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        created = _create_employee(client, factory, "CP1", "reactivate")
        headers = _bearer(_admin_token(client))
        client.post(
            f"/api/v1/employees/{created['id']}/deactivate",
            json={"version": created["version"]},
            headers=headers,
        )
        reactivated = client.post(f"/api/v1/employees/{created['id']}/reactivate", headers=headers)
        assert reactivated.status_code == 200, reactivated.text
        assert reactivated.json()["is_active"] is True

        login = client.post(
            "/api/v1/auth/login",
            json={"email": created["_email"], "password": _EMPLOYEE_PASSWORD},
        )
        assert login.status_code == 200, login.text

    def test_idempotent_deactivate(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        created = _create_employee(client, factory, "CP1", "idem")
        headers = _bearer(_admin_token(client))
        first = client.post(
            f"/api/v1/employees/{created['id']}/deactivate",
            json={"version": created["version"]},
            headers=headers,
        )
        second = client.post(f"/api/v1/employees/{created['id']}/deactivate", headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200, second.text


@requires_db
class TestEmployeeListingAndScope:
    def _grant_viewer(
        self, factory, email: str, username: str, workplace_id, operations: list[str]
    ):  # type: ignore[no-untyped-def]
        from app.modules.user.models import (
            Permission,
            RolePermission,
            ScopeAssignment,
            ScopeLevel,
            UserRole,
        )

        with factory() as session:
            role = _get_or_create_role(session, f"EmpViewer-{_RUN}-{username[:8]}", "viewer")
            for operation in operations:
                permission = session.scalar(
                    select(Permission).where(Permission.code == f"user:employee:{operation}")
                )
                assert permission is not None
                session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            user = _get_or_create_user(session, email, username, "viewer-password-1")
            session.add(UserRole(user_id=user.id, role_id=role.id))
            for operation in operations:
                session.add(
                    ScopeAssignment(
                        user_id=user.id,
                        level=ScopeLevel.WORKPLACE,
                        module="user",
                        resource="employee",
                        operation=operation,
                        workplace_id=workplace_id,
                    )
                )
            session.commit()

    def test_list_masked_without_read_full(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        wid = _workplace_id(factory, "CP1")
        admin_headers = _bearer(_admin_token(client))
        created = _create_employee(client, factory, "CP1", "masked")

        email = f"emp-viewer-{_RUN}@zarandsteel.ir"
        self._grant_viewer(factory, email, f"emp-viewer-{_RUN}", wid, ["read"])

        viewer_login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "viewer-password-1"},
        )
        assert viewer_login.status_code == 200
        viewer_token = viewer_login.json()["access_token"]

        listed = client.get(
            "/api/v1/employees",
            params={"search": created["national_id"], "page_size": 50},
            headers=_bearer(viewer_token),
        )
        assert listed.status_code == 200
        items = listed.json()["items"]
        target = next(item for item in items if item["id"] == created["id"])
        assert target["national_id"] == f"***{created['national_id'][-4:]}"

        admin_list = client.get(
            "/api/v1/employees",
            params={"search": created["national_id"]},
            headers=admin_headers,
        )
        assert admin_list.status_code == 200
        assert admin_list.json()["items"][0]["national_id"] == created["national_id"]

    def test_scoped_viewer_cannot_reach_other_workplace(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        cp1 = _workplace_id(factory, "CP1")
        created = _create_employee(client, factory, "SP", "steel")

        email = f"cp1-editor-{_RUN}@zarandsteel.ir"
        self._grant_viewer(factory, email, f"cp1-editor-{_RUN}", cp1, ["read", "update"])

        editor_login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "viewer-password-1"},
        )
        assert editor_login.status_code == 200
        editor_token = editor_login.json()["access_token"]

        response = client.get(f"/api/v1/employees/{created['id']}", headers=_bearer(editor_token))
        assert response.status_code == 403
        assert response.json()["code"] == "AUTHORIZATION_DENIED"

        patch = client.patch(
            f"/api/v1/employees/{created['id']}",
            json={"phone": "+989120000001", "version": created["version"]},
            headers=_bearer(editor_token),
        )
        assert patch.status_code == 403

    def test_update_version_conflict(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        created = _create_employee(client, factory, "CP1", "conflict")
        headers = _bearer(_admin_token(client))
        stale = client.patch(
            f"/api/v1/employees/{created['id']}",
            json={"phone": "+989120000002", "version": created["version"] + 5},
            headers=headers,
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "STALE_VERSION"

        good = client.patch(
            f"/api/v1/employees/{created['id']}",
            json={"phone": "+989120000002", "version": created["version"]},
            headers=headers,
        )
        assert good.status_code == 200
        assert good.json()["phone"] == "+989120000002"


@requires_db
class TestPasswordReset:
    def test_admin_password_reset_and_audit(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        created = _create_employee(client, factory, "CP1", "reset")
        admin_headers = _bearer(_admin_token(client))
        user_id = created["user"]["id"]
        new_password = "brand-new-password-9"

        reset = client.post(
            f"/api/v1/users/{user_id}/password",
            json={"password": new_password},
            headers=admin_headers,
        )
        assert reset.status_code == 200, reset.text

        old_login = client.post(
            "/api/v1/auth/login",
            json={"email": created["_email"], "password": _EMPLOYEE_PASSWORD},
        )
        assert old_login.status_code == 401
        new_login = client.post(
            "/api/v1/auth/login",
            json={"email": created["_email"], "password": new_password},
        )
        assert new_login.status_code == 200

        with factory() as session:
            from app.modules.audit.models import AuditLog

            entries = session.scalars(
                select(AuditLog).where(AuditLog.action == "USER_PASSWORD_SET")
            ).all()
            assert len(entries) >= 1
            assert all(new_password not in str(entry.after_snapshot) for entry in entries)

    def test_weak_password_rejected(self, pg) -> None:  # type: ignore[no-untyped-def]
        client, factory = pg
        created = _create_employee(client, factory, "CP1", "weakpw")
        response = client.post(
            f"/api/v1/users/{created['user']['id']}/password",
            json={"password": "short"},
            headers=_bearer(_admin_token(client)),
        )
        assert response.status_code == 422
