from collections.abc import Generator
from time import perf_counter

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.common.schemas import ComponentStatus
from app.core.config import Settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

_DB_CONNECT_TIMEOUT_SECONDS = 2


class Base(DeclarativeBase):
    pass


def init_engine(settings: Settings) -> Engine:
    global _engine, _session_factory
    database_url = settings.DATABASE_URL
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    connect_args: dict[str, object] = {}
    if database_url.startswith("postgresql"):
        connect_args = {"connect_timeout": _DB_CONNECT_TIMEOUT_SECONDS}
    _engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_engine() -> Engine | None:
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        raise RuntimeError("Database engine is not initialized")
    return _session_factory


def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_db() -> Generator[Session, None, None]:
    if _session_factory is None:
        raise RuntimeError("Database engine is not initialized")
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def check_database_health(engine: Engine | None) -> ComponentStatus:
    if engine is None:
        return ComponentStatus(status="down")
    try:
        started = perf_counter()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        latency_ms = int((perf_counter() - started) * 1000)
    except Exception:
        return ComponentStatus(status="down")
    return ComponentStatus(status="up", latency_ms=latency_ms)
