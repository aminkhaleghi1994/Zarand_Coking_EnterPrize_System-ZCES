import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_NAME", "ZCES")
os.environ.setdefault("APP_VERSION", "0.1.0")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.tracing import reset_trace_id  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_trace_context() -> None:
    reset_trace_id()


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
