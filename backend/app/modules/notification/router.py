"""Notification inbox endpoints (US3, contracts/notification-endpoints.md).
All endpoints are owner-scoped: authentication only (``load_context``), no
RBAC — a user's inbox is personal data. The stream is a per-user SSE feed
driven by the in-process bus; reconnects recover missed items through
``GET /notifications?unread_only=true``."""

import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.common.bus import bus, encode_sse
from app.common.pagination import Page
from app.common.scope import ScopeContext
from app.core.database import get_db
from app.modules.notification import service
from app.modules.notification.schemas import (
    MarkedOut,
    NotificationOut,
    UnreadCountOut,
)
from app.modules.user.dependencies import load_context
from app.modules.user.schemas import PageParams

router = APIRouter(tags=["notifications"])

KEEP_ALIVE_SECONDS = 15.0


@router.get("/notifications/stream")
async def stream_notifications(
    context: ScopeContext = Depends(load_context),
) -> StreamingResponse:
    """Live per-user SSE stream: ``event: notification`` frames for new
    deliveries and ``: keep-alive`` comments every 15s. Authentication runs
    in the dependency — unauthenticated callers get the standard 401
    envelope before any stream byte is written."""
    user_id = context.user_id

    async def event_stream() -> AsyncIterator[str]:
        queue = bus.subscribe(user_id)
        try:
            while True:
                message = await bus.wait_for_message(
                    queue, timeout=KEEP_ALIVE_SECONDS
                )
                if message is None:
                    yield ": keep-alive\n\n"
                    continue
                yield encode_sse("notification", message.payload)
        finally:
            bus.unsubscribe(user_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/notifications", response_model=Page[NotificationOut])
def get_notifications(
    params: PageParams = Depends(),
    unread_only: bool = Query(default=False),
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> Page[NotificationOut]:
    rows, total = service.list_inbox(
        session,
        uuid.UUID(context.user_id),
        page=params.page,
        page_size=params.page_size,
        unread_only=unread_only,
    )
    return Page(
        items=[
            NotificationOut.model_validate(row, from_attributes=True) for row in rows
        ],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.get("/notifications/unread-count", response_model=UnreadCountOut)
def get_unread_count(
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> UnreadCountOut:
    return UnreadCountOut(
        unread=service.unread_inbox_count(session, uuid.UUID(context.user_id))
    )


@router.post("/notifications/read-all", response_model=MarkedOut)
def post_read_all(
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> MarkedOut:
    return MarkedOut(
        marked=service.mark_inbox_all_read(session, uuid.UUID(context.user_id))
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def post_mark_read(
    notification_id: uuid.UUID,
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> NotificationOut:
    notification = service.mark_notification_read(
        session, uuid.UUID(context.user_id), notification_id
    )
    return NotificationOut.model_validate(notification, from_attributes=True)
