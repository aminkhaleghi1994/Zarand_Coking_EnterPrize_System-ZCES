"""Notification module DTOs: owner-facing inbox payloads."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class UnreadCountOut(BaseModel):
    unread: int = Field(ge=0)


class MarkedOut(BaseModel):
    marked: int = Field(ge=0)
