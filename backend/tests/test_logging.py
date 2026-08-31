import json
import logging

from app.core.logging import JsonFormatter, TraceIdFilter, setup_logging
from app.core.tracing import set_trace_id


class RecordingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.formatted: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.formatted.append(self.format(record))


def test_json_formatter_includes_trace_id() -> None:
    handler = RecordingHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TraceIdFilter())
    logger = logging.getLogger("test.logging.trace")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)

    set_trace_id("trace-42")
    logger.info("hello %s", "world")

    payload = json.loads(handler.formatted[0])
    assert payload["message"] == "hello world"
    assert payload["trace_id"] == "trace-42"
    assert payload["level"] == "INFO"
    assert "logger" in payload and "ts" in payload


def test_formatter_uses_dash_without_trace() -> None:
    handler = RecordingHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TraceIdFilter())
    logger = logging.getLogger("test.logging.notrace")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)

    logger.warning("no trace")
    payload = json.loads(handler.formatted[0])
    assert payload["trace_id"] == "-"


def test_setup_logging_sets_level() -> None:
    setup_logging("WARNING")
    assert logging.getLogger().level == logging.WARNING
    setup_logging("INFO")
    assert logging.getLogger().level == logging.INFO
