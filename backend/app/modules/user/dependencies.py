from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.common.scope import ScopeContext, ScopeTarget, can
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AUTHENTICATION_REQUIRED, AUTHORIZATION_DENIED, AppError
from app.core.security import decode_access_token
from app.modules.user import repository


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    raise AppError(AUTHENTICATION_REQUIRED, "Authentication required", status_code=401)


def load_context(request: Request, session: Session = Depends(get_db)) -> ScopeContext:
    token = _bearer_token(request)
    payload = decode_access_token(token, get_settings())
    if payload is None or not payload.get("sub"):
        raise AppError(AUTHENTICATION_REQUIRED, "Authentication required", status_code=401)
    context = repository.load_scope_context(session, str(payload["sub"]))
    if context is None:
        raise AppError(AUTHENTICATION_REQUIRED, "Authentication required", status_code=401)
    return context


def require_permission(operation: str) -> Callable[..., ScopeContext]:
    def dependency(context: ScopeContext = Depends(load_context)) -> ScopeContext:
        if not can(context, operation, ScopeTarget()):
            raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
        return context

    return dependency
