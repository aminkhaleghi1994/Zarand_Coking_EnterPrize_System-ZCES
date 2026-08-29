import pytest
from fastapi.testclient import TestClient

from app.common.schemas import ComponentStatus


def test_healthz_returns_200_with_full_shape(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"status", "app", "env", "version", "components"}
    assert body["status"] == "ok"
    assert body["app"] == "ZCES"
    assert body["env"] == "development"
    assert body["version"] == "0.1.0"
    assert set(body["components"].keys()) == {"database"}
    assert body["components"]["database"]["status"] in {"up", "down"}


def test_healthz_available_under_api_prefix(client: TestClient) -> None:
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_healthz_stays_200_when_database_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module,
        "check_database_health",
        lambda engine: ComponentStatus(status="down"),
    )
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["components"]["database"]["status"] == "down"


def test_healthz_includes_request_id_header(client: TestClient) -> None:
    response = client.get("/healthz")
    assert "X-Request-ID" in response.headers
