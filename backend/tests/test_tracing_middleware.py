import uuid

from fastapi.testclient import TestClient


def test_echoes_supplied_trace_id(client: TestClient) -> None:
    response = client.get("/healthz", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"


def test_generates_trace_id_when_absent(client: TestClient) -> None:
    response = client.get("/healthz")
    trace_id = response.headers["X-Request-ID"]
    assert len(trace_id) == 36
    assert uuid.UUID(trace_id)


def test_empty_trace_id_generates_fresh_one(client: TestClient) -> None:
    response = client.get("/healthz", headers={"X-Request-ID": "   "})
    trace_id = response.headers["X-Request-ID"]
    assert trace_id.strip()
    assert uuid.UUID(trace_id)


def test_each_request_gets_independent_trace_id(client: TestClient) -> None:
    first = client.get("/healthz").headers["X-Request-ID"]
    second = client.get("/healthz").headers["X-Request-ID"]
    assert first != second
