import pytest
from sqlalchemy import Uuid

from app.common.mixins import (
    CreatedByMixin,
    IDMixin,
    OrgScopeMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UpdatedByMixin,
    VersionMixin,
)
from app.core.database import Base


class ScratchRow(  # noqa: N801
    IDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    VersionMixin,
    CreatedByMixin,
    UpdatedByMixin,
    OrgScopeMixin,
    Base,
):
    __tablename__ = "scratch_rows"


@pytest.fixture()
def scratch() -> ScratchRow:
    return ScratchRow()


def _column(model: type[ScratchRow], name: str):  # type: ignore[no-untyped-def]
    return model.__table__.columns[name]


def test_uuid_primary_key_with_default(scratch: ScratchRow) -> None:
    column = _column(ScratchRow, "id")
    assert column.primary_key
    assert isinstance(column.type, Uuid)
    assert column.default is not None and callable(column.default.arg)


def test_timestamp_columns_have_server_defaults(scratch: ScratchRow) -> None:
    assert _column(ScratchRow, "created_at").server_default is not None
    assert _column(ScratchRow, "updated_at").server_default is not None


def test_soft_delete_marker_is_nullable(scratch: ScratchRow) -> None:
    assert scratch.deleted_at is None
    assert _column(ScratchRow, "deleted_at").nullable


def test_version_defaults_to_one(scratch: ScratchRow) -> None:
    column = _column(ScratchRow, "version")
    assert not column.nullable
    assert column.default is not None and column.default.arg == 1


def test_actor_columns_nullable_uuids(scratch: ScratchRow) -> None:
    assert scratch.created_by is None
    assert scratch.updated_by is None
    for name in ("created_by", "updated_by"):
        column = _column(ScratchRow, name)
        assert column.nullable
        assert isinstance(column.type, Uuid)


def test_org_scope_columns_nullable_uuids(scratch: ScratchRow) -> None:
    for name in ("company_id", "complex_id", "workplace_id"):
        assert getattr(scratch, name) is None
        column = _column(ScratchRow, name)
        assert column.nullable
        assert isinstance(column.type, Uuid)
