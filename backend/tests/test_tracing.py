import uuid

from app.core.tracing import get_trace_id, new_trace_id, set_trace_id


def test_new_trace_id_is_uuid_v4() -> None:
    value = new_trace_id()
    assert len(value) == 36
    assert uuid.UUID(value).version == 4


def test_new_trace_ids_are_unique() -> None:
    assert new_trace_id() != new_trace_id()


def test_set_and_get_roundtrip() -> None:
    assert get_trace_id() is None
    set_trace_id("trace-1")
    assert get_trace_id() == "trace-1"
    set_trace_id("trace-2")
    assert get_trace_id() == "trace-2"
