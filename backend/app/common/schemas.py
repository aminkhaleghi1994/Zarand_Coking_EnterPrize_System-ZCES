from typing import Any, Literal

from pydantic import BaseModel

ComponentState = Literal["up", "down"]


class ComponentStatus(BaseModel):
    status: ComponentState
    latency_ms: int | None = None


class HealthStatus(BaseModel):
    status: Literal["ok"] = "ok"
    app: str
    env: str
    version: str
    components: dict[str, ComponentStatus]


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    trace_id: str
