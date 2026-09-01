from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.warehouse.schemas import (
    AssetAssignIn,
    AssetCreateIn,
    AssetHistoryOut,
    AssetOut,
    AssetReturnIn,
    AssetUpdateIn,
    EmployeeBriefOut,
    HistoryHolderOut,
    HolderOut,
)

# --- AssetCreateIn (T002 fixtures) ---


def test_asset_create_valid_and_optional_description() -> None:
    payload = AssetCreateIn(
        name="Torque wrench",
        name_fa="آچار گشتاور",
        serial="  TW-001  ",
        description="   ",
    )
    assert payload.serial == "TW-001"
    assert payload.description is None


@pytest.mark.parametrize(
    "field", ["name", "name_fa", "serial"]
)
def test_asset_create_required_fields_reject_blank(field: str) -> None:
    base = {
        "name": "Torque wrench",
        "name_fa": "آچار گشتاور",
        "serial": "TW-001",
    }
    base[field] = "   "
    with pytest.raises(ValidationError):
        AssetCreateIn(**base)


def test_asset_create_rejects_oversized_fields() -> None:
    with pytest.raises(ValidationError):
        AssetCreateIn(name="x" * 201, name_fa="نام", serial="S")
    with pytest.raises(ValidationError):
        AssetCreateIn(name="n", name_fa="نام", serial="s" * 101)
    with pytest.raises(ValidationError):
        AssetCreateIn(name="n", name_fa="نام", serial="s", description="d" * 1001)


# --- AssetUpdateIn ---


def test_asset_update_requires_version() -> None:
    with pytest.raises(ValidationError):
        AssetUpdateIn(name="Renamed")
    with pytest.raises(ValidationError):
        AssetUpdateIn(name="Renamed", version=0)
    update = AssetUpdateIn(name="Renamed", version=3)
    assert update.description is None


def test_asset_update_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        AssetUpdateIn(name="   ", version=1)


# --- AssetAssignIn ---


def test_asset_assign_target_type_is_restricted() -> None:
    with pytest.raises(ValidationError):
        AssetAssignIn(version=1, target_type="shelf")
    assign = AssetAssignIn(version=1, target_type="employee")
    assert assign.employee_id is None and assign.location is None


def test_asset_assign_version_and_note_bounds() -> None:
    with pytest.raises(ValidationError):
        AssetAssignIn(version=0, target_type="location", location="Rack B2")
    with pytest.raises(ValidationError):
        AssetAssignIn(version=1, target_type="location", location="Rack", note="n" * 501)
    assign = AssetAssignIn(version=1, target_type="location", location="  ", note=" ok ")
    assert assign.location is None
    assert assign.note == "ok"


# --- AssetReturnIn ---


def test_asset_return_requires_version_and_strips_note() -> None:
    with pytest.raises(ValidationError):
        AssetReturnIn(note="gone")
    returned = AssetReturnIn(version=2, note="  kept  ")
    assert returned.version == 2
    assert returned.note == "kept"


# --- Output shapes ---


def test_holder_out_shapes() -> None:
    available = HolderOut(type="available")
    assert available.employee is None and available.location is None
    HolderOut(
        type="employee",
        employee=EmployeeBriefOut(id=uuid4(), name="Ali Ahmadi"),
    )
    location = HolderOut(type="location", location="Rack B2")
    assert location.employee is None


def test_asset_history_out_shape() -> None:
    now = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    entry = AssetHistoryOut(
        id=uuid4(),
        action="assigned",
        from_holder=HistoryHolderOut(type="available"),
        to_holder=HistoryHolderOut(
            type="employee", employee=EmployeeBriefOut(id=uuid4(), name="Holder")
        ),
        note="handover",
        actor_user_id=uuid4(),
        created_at=now,
    )
    dumped = entry.model_dump()
    assert dumped["action"] == "assigned"
    assert dumped["from_holder"]["type"] == "available"
    assert dumped["to_holder"]["employee"]["name"] == "Holder"


def test_asset_out_requires_holder() -> None:
    with pytest.raises(ValidationError):
        AssetOut(
            id=uuid4(),
            version=1,
            name="Asset",
            name_fa="مال",
            serial="S-1",
            status="available",
            created_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        )
