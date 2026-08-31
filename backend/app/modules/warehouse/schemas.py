import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

QUANT = Decimal("0.001")


def quantize_quantity(value: Decimal) -> Decimal:
    """Normalize any quantity to exactly 3 decimal places (research R1)."""
    return value.quantize(QUANT)


def format_quantity(value: Decimal) -> str:
    """Serialize a quantity with exactly 3 decimals (contract decision)."""
    return f"{quantize_quantity(value):.3f}"


class ItemCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    name_fa: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    unit: str = Field(min_length=1, max_length=30)
    min_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name", "name_fa", "unit")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("code", "description")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ItemUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    name_fa: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    min_quantity: Decimal | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=1000)
    version: int = Field(ge=1)

    @field_validator("name", "name_fa", "unit")
    @classmethod
    def _strip_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("code", "description")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ItemRetireIn(BaseModel):
    version: int = Field(ge=1)


class WarehouseRetireIn(BaseModel):
    version: int = Field(ge=1)


class ShelfRetireIn(BaseModel):
    version: int = Field(ge=1)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    name: str
    name_fa: str
    code: str | None = None
    unit: str
    min_quantity: str
    description: str | None = None
    is_active: bool
    created_at: datetime


class ItemBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    name_fa: str
    code: str | None = None
    unit: str
    min_quantity: str


class WarehouseCreateIn(BaseModel):
    workplace_id: uuid.UUID
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    name_fa: str = Field(min_length=1, max_length=200)

    @field_validator("code", "name", "name_fa")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class WarehouseUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    name_fa: str | None = Field(default=None, min_length=1, max_length=200)
    version: int = Field(ge=1)

    @field_validator("code", "name", "name_fa")
    @classmethod
    def _strip_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class WarehouseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    workplace_id: uuid.UUID
    code: str
    name: str
    name_fa: str
    is_active: bool
    created_at: datetime


class ShelfCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str | None = Field(default=None, max_length=200)
    name_fa: str | None = Field(default=None, max_length=200)

    @field_validator("code")
    @classmethod
    def _strip_code(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("name", "name_fa")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ShelfUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, max_length=200)
    name_fa: str | None = Field(default=None, max_length=200)
    version: int = Field(ge=1)

    @field_validator("code")
    @classmethod
    def _strip_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ShelfOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    warehouse_id: uuid.UUID
    code: str
    name: str | None = None
    name_fa: str | None = None
    is_active: bool
    created_at: datetime


class ShelfBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str | None = None


class WarehouseBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str


class ReceiveIn(BaseModel):
    item_id: uuid.UUID
    shelf_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class IssueIn(BaseModel):
    placement_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AdjustIn(BaseModel):
    placement_id: uuid.UUID
    quantity: Decimal = Field(ge=0)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PlacementOut(BaseModel):
    id: uuid.UUID
    item: ItemBriefOut
    shelf: ShelfBriefOut
    warehouse: WarehouseBriefOut
    quantity: str
    below_min_threshold: bool


class MovementOut(BaseModel):
    id: uuid.UUID
    movement_type: str
    quantity_delta: str
    resulting_quantity: str
    reason: str | None = None
    actor_user_id: uuid.UUID | None = None
    created_at: datetime


class AlertOut(BaseModel):
    id: uuid.UUID
    placement_id: uuid.UUID
    item: ItemBriefOut
    shelf: ShelfBriefOut
    warehouse: WarehouseBriefOut
    quantity_at_alert: str
    threshold_at_alert: str
    current_quantity: str
    raised_at: datetime
    resolved_at: datetime | None = None


# --- Item requests (Phase 5) ---


class RequestLineIn(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def _strip_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class RequestCreateIn(BaseModel):
    purpose_description: str = Field(min_length=1, max_length=2000)
    lines: list[RequestLineIn] = Field(min_length=1)

    @field_validator("purpose_description")
    @classmethod
    def _strip_purpose(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class RequestLineOut(BaseModel):
    id: uuid.UUID
    item: ItemBriefOut
    quantity: str
    note: str | None = None


class RequestOut(BaseModel):
    id: uuid.UUID
    version: int
    status: str
    requested_by: uuid.UUID
    requested_by_email: str | None = None
    purpose_description: str
    decision_note: str | None = None
    decided_by: uuid.UUID | None = None
    decided_at: datetime | None = None
    fulfilled_at: datetime | None = None
    lines: list[RequestLineOut] = []
    created_at: datetime


class DecisionIn(BaseModel):
    version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note")
    @classmethod
    def _strip_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class FulfillLineIn(BaseModel):
    line_id: uuid.UUID
    placement_id: uuid.UUID


class FulfillIn(BaseModel):
    version: int = Field(ge=1)
    lines: list[FulfillLineIn] = Field(min_length=1)
