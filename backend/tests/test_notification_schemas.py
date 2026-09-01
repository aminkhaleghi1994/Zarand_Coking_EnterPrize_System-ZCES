import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.notification.schemas import MarkedOut, NotificationOut, UnreadCountOut


def test_notification_out_shape() -> None:
    out = NotificationOut(
        id=uuid.uuid4(),
        event_type="InventoryLowStock",
        payload={"entity_id": str(uuid.uuid4()), "title": "low_stock"},
        read_at=None,
        created_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    )
    dumped = out.model_dump()
    assert dumped["event_type"] == "InventoryLowStock"
    assert dumped["read_at"] is None
    assert dumped["payload"]["title"] == "low_stock"


def test_unread_count_bounds() -> None:
    assert UnreadCountOut(unread=0).unread == 0
    with pytest.raises(ValidationError):
        UnreadCountOut(unread=-1)


def test_marked_out_bounds() -> None:
    assert MarkedOut(marked=5).marked == 5
    with pytest.raises(ValidationError):
        MarkedOut(marked=-2)
