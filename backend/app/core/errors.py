import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.tracing import get_trace_id, new_trace_id

logger = logging.getLogger(__name__)

VALIDATION_ERROR = "VALIDATION_ERROR"
AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"
CONFLICT_CONCURRENT_UPDATE = "CONFLICT_CONCURRENT_UPDATE"
INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
RATE_LIMITED = "RATE_LIMITED"
INTERNAL_ERROR = "INTERNAL_ERROR"
STALE_VERSION = "STALE_VERSION"
RESOURCE_LOCKED = "RESOURCE_LOCKED"

_HTTP_STATUS_TO_CODE: dict[int, tuple[str, str]] = {
    401: (AUTHENTICATION_REQUIRED, "Authentication required"),
    403: (AUTHORIZATION_DENIED, "Access denied"),
    404: (RESOURCE_NOT_FOUND, "Resource not found"),
    405: (BUSINESS_RULE_VIOLATION, "Method not allowed on this resource"),
    429: (RATE_LIMITED, "Too many requests"),
}


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def build_envelope(
    code: str,
    message: str,
    details: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details,
        "trace_id": get_trace_id() or new_trace_id(),
    }


def _envelope_response(
    code: str,
    message: str,
    details: dict[str, Any] | None,
    status_code: int,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=build_envelope(code, message, details),
        headers={"X-Request-ID": get_trace_id() or new_trace_id()},
    )


def _map_http_exception(exc: StarletteHTTPException) -> tuple[str, str]:
    mapped = _HTTP_STATUS_TO_CODE.get(exc.status_code)
    if mapped is None:
        return INTERNAL_ERROR, "Internal server error"
    code, default_message = mapped
    detail_text = str(exc.detail) if exc.detail else ""
    if detail_text and detail_text != exc.__class__.__name__:
        message = detail_text
    else:
        message = default_message
    return code, message


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _envelope_response(exc.code, exc.message, exc.details, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors = []
        for error in exc.errors():
            parts = [str(part) for part in error.get("loc", [])]
            if parts and parts[0] in {"body", "query", "path", "header", "cookie"}:
                parts = parts[1:]
            field_errors.append(
                {"field": ".".join(parts), "issue": error.get("msg", "invalid value")}
            )
        return _envelope_response(
            VALIDATION_ERROR,
            "Request validation failed",
            {"field_errors": field_errors},
            422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code, message = _map_http_exception(exc)
        status_code = exc.status_code if code != INTERNAL_ERROR else 500
        return _envelope_response(code, message, None, status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception while serving %s %s", request.method, request.url.path
        )
        return _envelope_response(INTERNAL_ERROR, "Internal server error", None, 500)
