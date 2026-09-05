"""Settings module queries. Settings are a global resource: the scope
check is the operation-level permission gate (no org unit filtering —
constitution II is satisfied because reads/writes require both the
permission and a scope assignment, which for global resources means any
valid assignment covering the operation)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.settings.models import Setting


def get_by_key(session: Session, key: str) -> Setting | None:
    return session.scalar(select(Setting).where(Setting.key == key))


def list_all(session: Session) -> list[Setting]:
    return list(session.scalars(select(Setting).order_by(Setting.key)).all())
