"""Settings module models: global typed key/value store (requirements §3.1
settings bullets, data-model.md, migration 0009).

Integrity invariants (constitution III):
- one row per key (plain unique — settings are never deleted, so no
  partial-unique is needed);
- value_type CHECK-guarded; the fixed key set is enforced by the service
  layer (unknown key -> VALIDATION_ERROR) keeping storage simple;
- optimistic locking via `version` on updates (requirements §25).
"""

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import IDMixin, TimestampMixin, VersionMixin
from app.core.database import Base

VALUE_TYPES: tuple[str, ...] = ("boolean", "integer", "string", "json")

_VALUE_TYPE_SQL = ", ".join(f"'{value}'" for value in VALUE_TYPES)


class Setting(IDMixin, TimestampMixin, VersionMixin, Base):
    """Global setting row from the fixed code-defined key set."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[object] = mapped_column(JSONB, nullable=False)
    value_type: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_fa: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            f"value_type IN ({_VALUE_TYPE_SQL})", name="ck_settings_value_type"
        ),
    )
