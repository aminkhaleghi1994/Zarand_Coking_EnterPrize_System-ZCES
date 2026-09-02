import os
import uuid
from threading import Thread

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.common.jalali import current_jalali_year
from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.loan.models import LoanRequest
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="loan integration tests require real PostgreSQL (row locking + CHECKs)",
)

_RUN = uuid.uuid4().hex[:6]


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


def _create_employee_via_api(
    client: TestClient, token: str, workplace_id: str, tag: str
) -> tuple[str, str, str]:
    """Create an employee + linked user; return (employee_id, user_id, email)."""
    email = f"loan-{tag}@zarandsteel.ir"
    created = client.post(
        "/api/v1/employees",
        json={
            "national_id": f"8{uuid.uuid4().int % 10**9:09d}",
            "personnel_code": f"LNM-{tag}",
            "first_name": "Loan",
            "last_name": f"Employee {tag}",
            "workplace_id": workplace_id,
            "user": {
                "email": email,
                "username": f"loan-{tag}",
                "password": "loan-password-1",
            },
        },
        headers=_bearer(token),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    return body["id"], body["user"]["id"], email


def _user_token(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "loan-password-1"}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _grant_loan_scope(
    client: TestClient, token: str, user_id: str, workplace_id: str, operations: list[str]
) -> None:
    roles = client.get("/api/v1/roles?page_size=100", headers=_bearer(token)).json()["items"]
    officer_role_id = next(role["id"] for role in roles if role["name"] == "LoanOfficer")
    assigned = client.post(
        f"/api/v1/users/{user_id}/roles",
        json={"role_id": officer_role_id},
        headers=_bearer(token),
    )
    assert assigned.status_code in (200, 409), assigned.text
    for operation in operations:
        module, resource, op = operation.split(":")
        response = client.post(
            f"/api/v1/users/{user_id}/scopes",
            json={
                "level": "workplace",
                "module": module,
                "resource": resource,
                "operation": op,
                "workplace_id": workplace_id,
            },
            headers=_bearer(token),
        )
        assert response.status_code == 201, response.text


def _policy_payload(workplace_id: str, year: int, **overrides: object) -> dict:
    payload: dict[str, object] = {
        "workplace_id": workplace_id,
        "year": year,
        "max_loan_amount": "100000000.00",
        "max_guarantee_amount": "50000000.00",
        "max_request_count_per_year": 3,
        "max_request_count_lifetime": 5,
    }
    payload.update(overrides)
    return payload


def _retire_existing(client: TestClient, token: str, workplace_id: str, year: int) -> None:
    """Retire any active policy for (workplace, year) so tests start clean
    against a shared dev database (the list endpoint returns active rows)."""
    listed = client.get(
        f"/api/v1/loan/policies?page_size=100&year={year}", headers=_bearer(token)
    ).json()
    for item in listed["items"]:
        if item["workplace"]["id"] == workplace_id:
            client.post(
                f"/api/v1/loan/policies/{item['id']}/retire",
                json={"version": item["version"]},
                headers=_bearer(token),
            )


def _reset_policy(
    client: TestClient, token: str, workplace_id: str, year: int, **limits: object
) -> dict:
    _retire_existing(client, token, workplace_id, year)
    created = client.post(
        "/api/v1/loan/policies",
        json=_policy_payload(workplace_id, year, **limits),
        headers=_bearer(token),
    )
    assert created.status_code == 201, created.text
    return created.json()


def _submit(client: TestClient, token: str, type: str, amount: str) -> object:
    return client.post(
        "/api/v1/loan/requests", json={"type": type, "amount": amount}, headers=_bearer(token)
    )


# --- US1: policies ---


@requires_db
def test_policy_crud_matrix(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces?page_size=50", headers=_bearer(token)).json()[
        "items"
    ][0]
    year = current_jalali_year()
    _retire_existing(client, token, workplace["id"], year)

    created = client.post(
        "/api/v1/loan/policies",
        json=_policy_payload(workplace["id"], year),
        headers=_bearer(token),
    )
    assert created.status_code == 201, created.text
    policy = created.json()
    assert policy["workplace"]["code"] == workplace["code"]
    assert policy["max_loan_amount"] == "100000000.00"
    assert policy["is_active"] is True

    duplicate = client.post(
        "/api/v1/loan/policies",
        json=_policy_payload(workplace["id"], year),
        headers=_bearer(token),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DUPLICATE_RESOURCE"

    stale = client.patch(
        f"/api/v1/loan/policies/{policy['id']}",
        json={"max_request_count_per_year": 9, "version": policy["version"] + 5},
        headers=_bearer(token),
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_VERSION"

    year_change = client.patch(
        f"/api/v1/loan/policies/{policy['id']}",
        json={"year": year - 1, "version": policy["version"]},
        headers=_bearer(token),
    )
    assert year_change.status_code == 200, year_change.text

    collide = client.post(
        "/api/v1/loan/policies",
        json=_policy_payload(workplace["id"], year),
        headers=_bearer(token),
    )
    assert collide.status_code == 201, collide.text
    moved_back = client.patch(
        f"/api/v1/loan/policies/{collide.json()['id']}",
        json={"year": year - 1, "version": collide.json()["version"]},
        headers=_bearer(token),
    )
    assert moved_back.status_code == 409
    assert moved_back.json()["code"] == "DUPLICATE_RESOURCE"

    retired = client.post(
        f"/api/v1/loan/policies/{policy['id']}/retire",
        json={"version": year_change.json()["version"]},
        headers=_bearer(token),
    )
    assert retired.status_code == 200, retired.text

    listed = client.get(
        f"/api/v1/loan/policies?page_size=100&workplace_id={workplace['id']}",
        headers=_bearer(token),
    ).json()
    assert all(item["id"] != policy["id"] for item in listed["items"])
    retired_listed = client.get(
        "/api/v1/loan/policies",
        params={
            "page_size": 100,
            "workplace_id": workplace["id"],
            "year": year - 1,
            "include_retired": "true",
        },
        headers=_bearer(token),
    ).json()
    assert any(item["id"] == policy["id"] for item in retired_listed["items"])

    gone = client.post(
        f"/api/v1/loan/policies/{policy['id']}/retire",
        json={"version": retired.json()["version"]},
        headers=_bearer(token),
    )
    assert gone.status_code == 404


@requires_db
def test_policy_scope_purity(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    workplaces = client.get("/api/v1/org/workplaces?page_size=50", headers=_bearer(token)).json()[
        "items"
    ]
    year = current_jalali_year()

    _employee_a, user_a, email_a = _create_employee_via_api(
        client, token, workplaces[0]["id"], f"{_RUN}a"
    )
    _employee_b, _user_b, _email_b = _create_employee_via_api(
        client, token, workplaces[1]["id"], f"{_RUN}b"
    )
    _grant_loan_scope(
        client, token, user_a, workplaces[0]["id"], ["loan:policy:read", "loan:request:read"]
    )

    for wp in (workplaces[0], workplaces[1]):
        _reset_policy(client, token, wp["id"], year)

    scoped = client.get(
        "/api/v1/loan/policies?page_size=100", headers=_bearer(_user_token(client, email_a))
    )
    assert scoped.status_code == 200, scoped.text
    seen = {item["workplace"]["id"] for item in scoped.json()["items"]}
    assert seen == {workplaces[0]["id"]}, f"scoped officer saw {seen}"

    # FR-003: explicit workplace filter narrows to that unit
    filtered = client.get(
        f"/api/v1/loan/policies?page_size=100&workplace_id={workplaces[0]['id']}",
        headers=_bearer(token),
    )
    assert filtered.status_code == 200, filtered.text
    filtered_seen = {item["workplace"]["id"] for item in filtered.json()["items"]}
    assert filtered_seen == {workplaces[0]["id"]}


# --- US2: validation cascade ---


@requires_db
def test_validation_cascade_in_exact_order(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces?page_size=50", headers=_bearer(token)).json()[
        "items"
    ][0]
    year = current_jalali_year()
    _employee, _user_id, email = _create_employee_via_api(
        client, token, workplace["id"], f"{_RUN}v"
    )
    employee_token = _user_token(client, email)

    # a leftover policy from another test must not mask the no-policy rule
    _retire_existing(client, token, workplace["id"], year)

    # rule 5 (no policy) fires before any counting
    refused = _submit(client, employee_token, "loan", "10000000.00")
    assert refused.status_code == 422, refused.text
    details = refused.json()["details"]
    assert details["rule"] == "no_policy"
    assert details["year"] == year

    _reset_policy(
        client, token, workplace["id"], year,
        max_request_count_per_year=2, max_request_count_lifetime=3,
    )

    first = _submit(client, employee_token, "loan", "10000000.00")
    assert first.status_code == 201, first.text
    second = _submit(client, employee_token, "loan", "10000000.00")
    assert second.status_code == 201, second.text

    third = _submit(client, employee_token, "loan", "10000000.00")
    assert third.status_code == 422, third.text
    assert third.json()["details"]["rule"] == "yearly_count"
    assert third.json()["details"]["used"] == 2
    assert third.json()["details"]["limit"] == 2

    # settle the first (settled keeps counting toward limits, per §19)
    activated = client.post(
        f"/api/v1/loan/requests/{first.json()['id']}/activate",
        json={"version": first.json()["version"]},
        headers=_bearer(token),
    )
    assert activated.status_code == 200, activated.text
    settled = client.post(
        f"/api/v1/loan/requests/{first.json()['id']}/settle",
        json={"version": activated.json()["version"]},
        headers=_bearer(token),
    )
    assert settled.status_code == 200, settled.text

    # widen the yearly limit, then keep submitting until the lifetime rule
    # (rule 1) fires first with the settled history still counted
    listed = client.get(
        f"/api/v1/loan/policies?page_size=100&year={year}", headers=_bearer(token)
    ).json()
    policy = next(item for item in listed["items"] if item["workplace"]["id"] == workplace["id"])
    widened = client.patch(
        f"/api/v1/loan/policies/{policy['id']}",
        json={"max_request_count_per_year": 10, "version": policy["version"]},
        headers=_bearer(token),
    )
    assert widened.status_code == 200, widened.text

    third_ok = _submit(client, employee_token, "guarantee", "5000000.00")
    assert third_ok.status_code == 201, third_ok.text

    fourth = _submit(client, employee_token, "loan", "1000000.00")
    assert fourth.status_code == 422, fourth.text
    assert fourth.json()["details"]["rule"] == "lifetime_count"
    assert fourth.json()["details"]["used"] == 3


@requires_db
def test_amount_caps_bind_and_free(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces?page_size=50", headers=_bearer(token)).json()[
        "items"
    ][0]
    year = current_jalali_year()
    _employee, _user_id, email = _create_employee_via_api(
        client, token, workplace["id"], f"{_RUN}c"
    )
    employee_token = _user_token(client, email)

    _reset_policy(
        client, token, workplace["id"], year,
        max_request_count_per_year=20, max_request_count_lifetime=20,
    )

    big = _submit(client, employee_token, "loan", "60000000.00")
    assert big.status_code == 201, big.text
    activated = client.post(
        f"/api/v1/loan/requests/{big.json()['id']}/activate",
        json={"version": big.json()["version"]},
        headers=_bearer(token),
    )
    assert activated.status_code == 200, activated.text

    over = _submit(client, employee_token, "loan", "50000000.00")
    assert over.status_code == 422, over.text
    details = over.json()["details"]
    assert details["rule"] == "loan_cap"
    assert details["current_active"] == "60000000.00"
    assert details["limit"] == "100000000.00"
    assert details["requested"] == "50000000.00"

    # guarantees evaluate the guarantee cap, not the loan cap
    guarantee = _submit(client, employee_token, "guarantee", "40000000.00")
    assert guarantee.status_code == 201, guarantee.text
    guarantee_activated = client.post(
        f"/api/v1/loan/requests/{guarantee.json()['id']}/activate",
        json={"version": guarantee.json()["version"]},
        headers=_bearer(token),
    )
    assert guarantee_activated.status_code == 200, guarantee_activated.text
    guarantee_over = _submit(client, employee_token, "guarantee", "20000000.00")
    assert guarantee_over.status_code == 422, guarantee_over.text
    assert guarantee_over.json()["details"]["rule"] == "guarantee_cap"

    # settling frees the commitment
    settled = client.post(
        f"/api/v1/loan/requests/{big.json()['id']}/settle",
        json={"version": activated.json()["version"]},
        headers=_bearer(token),
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["settled_at"] is not None

    after_settle = _submit(client, employee_token, "loan", "50000000.00")
    assert after_settle.status_code == 201, after_settle.text


@requires_db
def test_cancelled_keeps_counting(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces?page_size=50", headers=_bearer(token)).json()[
        "items"
    ][0]
    year = current_jalali_year()
    _employee, _user_id, email = _create_employee_via_api(
        client, token, workplace["id"], f"{_RUN}x"
    )
    employee_token = _user_token(client, email)

    _reset_policy(
        client, token, workplace["id"], year,
        max_request_count_per_year=2, max_request_count_lifetime=5,
    )
    first = _submit(client, employee_token, "loan", "1000000.00")
    assert first.status_code == 201, first.text
    cancelled = client.post(
        f"/api/v1/loan/requests/{first.json()['id']}/cancel",
        json={"version": first.json()["version"]},
        headers=_bearer(token),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    second = _submit(client, employee_token, "loan", "1000000.00")
    assert second.status_code == 201, second.text

    # cancelling freed nothing: 2 used, yearly limit 2 → third refused
    third = _submit(client, employee_token, "loan", "1000000.00")
    assert third.status_code == 422, third.text
    assert third.json()["details"]["rule"] == "yearly_count"


@requires_db
def test_submission_race_one_winner(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces?page_size=50", headers=_bearer(token)).json()[
        "items"
    ][0]
    year = current_jalali_year()
    _employee, _user_id, email = _create_employee_via_api(
        client, token, workplace["id"], f"{_RUN}r"
    )
    employee_token = _user_token(client, email)

    _reset_policy(
        client, token, workplace["id"], year,
        max_request_count_per_year=1, max_request_count_lifetime=5,
    )

    outcomes: list[str] = []

    def submit() -> None:
        response = _submit(client, employee_token, "loan", "1000000.00")
        if response.status_code == 201:
            outcomes.append("created")
        elif response.json().get("details", {}).get("rule") == "yearly_count":
            outcomes.append("yearly_count")
        else:
            outcomes.append(response.json().get("code", "unknown"))

    threads = [Thread(target=submit) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count("created") == 1, f"outcomes={outcomes}"
    assert outcomes.count("yearly_count") == 1, f"outcomes={outcomes}"


# --- US3: lifecycle ---


@requires_db
def test_lifecycle_audit_rows_are_critical_and_masked(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces?page_size=50", headers=_bearer(token)).json()[
        "items"
    ][0]
    year = current_jalali_year()
    _employee, _user_id, email = _create_employee_via_api(
        client, token, workplace["id"], f"{_RUN}a1"
    )
    employee_token = _user_token(client, email)

    _reset_policy(
        client, token, workplace["id"], year,
        max_request_count_per_year=10, max_request_count_lifetime=10,
    )
    created = _submit(client, employee_token, "loan", "20000000.00")
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    activated = client.post(
        f"/api/v1/loan/requests/{request_id}/activate",
        json={"version": created.json()["version"]},
        headers=_bearer(token),
    )
    assert activated.status_code == 200, activated.text
    settled = client.post(
        f"/api/v1/loan/requests/{request_id}/settle",
        json={"version": activated.json()["version"]},
        headers=_bearer(token),
    )
    assert settled.status_code == 200, settled.text

    with factory() as session:
        actions = session.scalars(
            select(AuditLog.action)
            .where(
                AuditLog.entity_type == "loan_request",
                AuditLog.entity_id == uuid.UUID(request_id),
            )
            .order_by(AuditLog.created_at)
        ).all()
        assert actions == ["LOAN_REQUEST_CREATED", "LOAN_REQUEST_ACTIVATED", "LOAN_REQUEST_SETTLED"]
        after_rows = session.scalars(
            select(AuditLog.after_snapshot).where(
                AuditLog.entity_type == "loan_request", AuditLog.entity_id == uuid.UUID(request_id)
            )
        ).all()
        for snapshot in after_rows:
            assert snapshot is not None
            assert snapshot["amount"] == "***"
            assert snapshot["status"] in ("pending", "active", "settled")


@requires_db
def test_transitions_matrix(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces?page_size=50", headers=_bearer(token)).json()[
        "items"
    ][0]
    year = current_jalali_year()
    _employee, _user_id, email = _create_employee_via_api(
        client, token, workplace["id"], f"{_RUN}t"
    )
    employee_token = _user_token(client, email)

    _reset_policy(
        client, token, workplace["id"], year,
        max_request_count_per_year=50, max_request_count_lifetime=50,
    )

    pending = _submit(client, employee_token, "loan", "5000000.00")
    assert pending.status_code == 201, pending.text
    request_id = pending.json()["id"]

    settle_pending = client.post(
        f"/api/v1/loan/requests/{request_id}/settle",
        json={"version": pending.json()["version"]},
        headers=_bearer(token),
    )
    assert settle_pending.status_code == 422

    activated = client.post(
        f"/api/v1/loan/requests/{request_id}/activate",
        json={"version": pending.json()["version"]},
        headers=_bearer(token),
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"

    double = client.post(
        f"/api/v1/loan/requests/{request_id}/activate",
        json={"version": pending.json()["version"]},
        headers=_bearer(token),
    )
    assert double.status_code == 409
    assert double.json()["code"] == "STALE_VERSION"

    settled = client.post(
        f"/api/v1/loan/requests/{request_id}/settle",
        json={"version": activated.json()["version"]},
        headers=_bearer(token),
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["status"] == "settled"
    assert settled.json()["settled_at"] is not None

    settle_again = client.post(
        f"/api/v1/loan/requests/{request_id}/settle",
        json={"version": settled.json()["version"]},
        headers=_bearer(token),
    )
    assert settle_again.status_code == 422
    cancel_settled = client.post(
        f"/api/v1/loan/requests/{request_id}/cancel",
        json={"version": settled.json()["version"]},
        headers=_bearer(token),
    )
    assert cancel_settled.status_code == 422

    cancellable = _submit(client, employee_token, "guarantee", "1000000.00")
    assert cancellable.status_code == 201, cancellable.text
    cancelled = client.post(
        f"/api/v1/loan/requests/{cancellable.json()['id']}/cancel",
        json={"version": cancellable.json()["version"]},
        headers=_bearer(token),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"


@requires_db
def test_activation_refused_for_deactivated_employee(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces?page_size=50", headers=_bearer(token)).json()[
        "items"
    ][0]
    year = current_jalali_year()
    employee_id, _user_id, email = _create_employee_via_api(
        client, token, workplace["id"], f"{_RUN}d"
    )
    employee_token = _user_token(client, email)

    _reset_policy(
        client, token, workplace["id"], year,
        max_request_count_per_year=50, max_request_count_lifetime=50,
    )
    created = _submit(client, employee_token, "loan", "1000000.00")
    assert created.status_code == 201, created.text

    deactivate = client.post(
        f"/api/v1/employees/{employee_id}/deactivate",
        json={"version": 1},
        headers=_bearer(token),
    )
    assert deactivate.status_code == 200, deactivate.text

    activated = client.post(
        f"/api/v1/loan/requests/{created.json()['id']}/activate",
        json={"version": created.json()["version"]},
        headers=_bearer(token),
    )
    assert activated.status_code == 422, activated.text
    assert activated.json()["code"] == "BUSINESS_RULE_VIOLATION"


# --- US4: visibility ---


@requires_db
def test_request_visibility_ownership_and_scope(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    workplaces = client.get("/api/v1/org/workplaces?page_size=50", headers=_bearer(token)).json()[
        "items"
    ]
    year = current_jalali_year()
    employee_a, user_a, email_a = _create_employee_via_api(
        client, token, workplaces[0]["id"], f"{_RUN}o1"
    )
    employee_b, _user_b, email_b = _create_employee_via_api(
        client, token, workplaces[1]["id"], f"{_RUN}o2"
    )
    employee_c, _user_c, email_c = _create_employee_via_api(
        client, token, workplaces[0]["id"], f"{_RUN}o3"
    )
    _grant_loan_scope(client, token, user_a, workplaces[0]["id"], ["loan:request:read"])

    _reset_policy(
        client, token, workplaces[0]["id"], year,
        max_request_count_per_year=50, max_request_count_lifetime=50,
    )
    _reset_policy(
        client, token, workplaces[1]["id"], year,
        max_request_count_per_year=50, max_request_count_lifetime=50,
    )

    a_request = _submit(client, _user_token(client, email_a), "loan", "1000000.00")
    b_request = _submit(client, _user_token(client, email_b), "loan", "1000000.00")
    c_request = _submit(client, _user_token(client, email_c), "loan", "1000000.00")
    assert a_request.status_code == 201 and b_request.status_code == 201
    assert c_request.status_code == 201, c_request.text

    # plain user (no loan permissions): strictly own requests
    own = client.get(
        "/api/v1/loan/requests?page_size=100", headers=_bearer(_user_token(client, email_c))
    )
    assert own.status_code == 200, own.text
    own_ids = {item["employee"]["id"] for item in own.json()["items"]}
    assert own_ids == {employee_c}, f"plain user saw {own_ids}"

    # scoped officer: whole covered workplace (union with ownership)
    officer = client.get(
        "/api/v1/loan/requests?page_size=100", headers=_bearer(_user_token(client, email_a))
    )
    assert officer.status_code == 200, officer.text
    officer_workplaces = {item["workplace"]["id"] for item in officer.json()["items"]}
    assert officer_workplaces == {workplaces[0]["id"]}, f"officer saw {officer_workplaces}"
    officer_employees = {item["employee"]["id"] for item in officer.json()["items"]}
    assert employee_a in officer_employees and employee_c in officer_employees

    leak = client.get(
        f"/api/v1/loan/requests/{b_request.json()['id']}",
        headers=_bearer(_user_token(client, email_a)),
    )
    assert leak.status_code == 404
    assert leak.json()["code"] == "RESOURCE_NOT_FOUND"

    admin_view = client.get("/api/v1/loan/requests?page_size=100", headers=_bearer(token))
    admin_ids = {item["employee"]["id"] for item in admin_view.json()["items"]}
    assert {employee_a, employee_b} <= admin_ids

    # FR-013: employee-name search narrows results
    searched = client.get(
        f"/api/v1/loan/requests?page_size=100&search=Employee {_RUN}o2",
        headers=_bearer(token),
    )
    assert searched.status_code == 200, searched.text
    searched_ids = {item["employee"]["id"] for item in searched.json()["items"]}
    assert searched_ids == {employee_b}, f"search matched {searched_ids}"

    with factory() as session:
        rows = session.scalars(
            select(LoanRequest).where(LoanRequest.employee_id.in_([uuid.UUID(employee_c)]))
        ).all()
        assert len(rows) == 1
        assert len(rows) == 1
