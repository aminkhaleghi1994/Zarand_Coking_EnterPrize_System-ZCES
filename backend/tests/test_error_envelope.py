import logging

import pytest
from fastapi import Query
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client_with_routes() -> TestClient:
    app = create_app()

    def boom() -> dict[str, str]:
        raise RuntimeError("boom-secret-internals")

    def echo(page: int = Query(ge=1)) -> dict[str, int]:
        return {"page": page}

    app.add_api_route("/boom", boom, methods=["GET"])
    app.add_api_route("/echo", echo, methods=["GET"])

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_unknown_route_uses_standard_envelope(client: TestClient) -> None:
    response = client.get("/definitely-not-a-route")
    assert response.status_code == 404
    body = response.json()
    assert set(body.keys()) == {"code", "message", "details", "trace_id"}
    assert body["code"] == "RESOURCE_NOT_FOUND"
    assert body["details"] is None
    assert body["trace_id"] == response.headers["X-Request-ID"]


def test_validation_error_envelope(client_with_routes: TestClient) -> None:
    response = client_with_routes.get("/echo?page=0")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    field_errors = body["details"]["field_errors"]
    assert field_errors[0]["field"] == "page"
    assert body["trace_id"] == response.headers["X-Request-ID"]


def test_unhandled_exception_maps_to_internal_error_without_leaking(
    client_with_routes: TestClient,
) -> None:
    response = client_with_routes.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert body["message"] == "Internal server error"
    assert body["details"] is None
    assert "boom-secret-internals" not in response.text
    assert "RuntimeError" not in response.text
    assert body["trace_id"] == response.headers["X-Request-ID"]


def test_unhandled_exception_is_logged_with_traceback(
    client_with_routes: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        client_with_routes.get("/boom")
    error_records = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert error_records
    assert any(record.exc_info for record in error_records)
    assert "boom-secret-internals" in error_records[0].getMessage() + str(
        error_records[0].exc_info
    )


def test_method_not_allowed_maps_to_business_rule(client: TestClient) -> None:
    response = client.post("/healthz")
    assert response.status_code == 405
    body = response.json()
    assert body["code"] == "BUSINESS_RULE_VIOLATION"
