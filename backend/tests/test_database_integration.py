import os

import pytest
from sqlalchemy import create_engine

from app.core.database import check_database_health

_TEST_DATABASE_URL = os.environ.get("ZCES_TEST_DATABASE_URL")

requires_database = pytest.mark.skipif(
    not _TEST_DATABASE_URL, reason="ZCES_TEST_DATABASE_URL is not configured"
)


@requires_database
def test_select_1_against_real_database() -> None:
    engine = create_engine(_TEST_DATABASE_URL)  # type: ignore[arg-type]
    try:
        status = check_database_health(engine)
        assert status.status == "up"
        assert status.latency_ms is not None
    finally:
        engine.dispose()
