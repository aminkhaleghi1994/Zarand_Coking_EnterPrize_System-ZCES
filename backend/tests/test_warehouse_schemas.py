from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.warehouse.schemas import (
    AdjustIn,
    ItemCreateIn,
    ReceiveIn,
    format_quantity,
    quantize_quantity,
)


def test_format_quantity_serializes_three_decimals() -> None:
    assert format_quantity(Decimal("10.5")) == "10.500"
    assert format_quantity(Decimal("0")) == "0.000"
    assert format_quantity(Decimal("12.3456")) == "12.346"


def test_quantize_quantity_rounds_to_three_decimals() -> None:
    assert quantize_quantity(Decimal("1.2349")) == Decimal("1.235")
    assert quantize_quantity(Decimal("1.2344")) == Decimal("1.234")


def test_item_create_in_strips_and_normalizes() -> None:
    payload = ItemCreateIn(
        name="  Ball bearing  ",
        name_fa=" بلبرینگ ",
        code=" bb-1 ",
        unit=" ad ",
        min_quantity=Decimal("10"),
    )
    assert payload.name == "Ball bearing"
    assert payload.name_fa == "بلبرینگ"
    assert payload.code == "bb-1"
    assert payload.unit == "ad"
    assert payload.min_quantity == Decimal("10")


def test_item_create_in_blank_name_rejected() -> None:
    with pytest.raises(ValidationError):
        ItemCreateIn(name="   ", name_fa="x", unit="ad")


def test_item_create_in_negative_min_quantity_rejected() -> None:
    with pytest.raises(ValidationError):
        ItemCreateIn(name="x", name_fa="y", unit="ad", min_quantity=Decimal("-1"))


def test_receive_in_quantity_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ReceiveIn(
            item_id="00000000-0000-0000-0000-000000000001",
            shelf_id="00000000-0000-0000-0000-000000000002",
            quantity=Decimal("0"),
        )
    with pytest.raises(ValidationError):
        ReceiveIn(
            item_id="00000000-0000-0000-0000-000000000001",
            shelf_id="00000000-0000-0000-0000-000000000002",
            quantity=Decimal("-5"),
        )


def test_adjust_in_allows_zero_target_but_not_negative() -> None:
    ok = AdjustIn(
        placement_id="00000000-0000-0000-0000-000000000001",
        quantity=Decimal("0"),
    )
    assert ok.quantity == Decimal("0")
    with pytest.raises(ValidationError):
        AdjustIn(
            placement_id="00000000-0000-0000-0000-000000000001",
            quantity=Decimal("-0.001"),
        )
