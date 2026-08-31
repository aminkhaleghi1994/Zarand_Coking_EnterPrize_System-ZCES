import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    before_snapshot: dict[str, Any] | None
    after_snapshot: dict[str, Any] | None
    trace_id: str | None
    created_at: datetime
