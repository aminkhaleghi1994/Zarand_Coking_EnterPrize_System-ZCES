import uuid
from contextvars import ContextVar

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def new_trace_id() -> str:
    return str(uuid.uuid4())


def get_trace_id() -> str | None:
    return _trace_id.get()


def set_trace_id(value: str) -> None:
    _trace_id.set(value)


def reset_trace_id() -> None:
    _trace_id.set(None)
