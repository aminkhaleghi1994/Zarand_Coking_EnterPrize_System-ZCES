"""Item-request queries. Ownership-OR-scope visibility (research R5/R10):
a caller always sees requests they raised; holders of
`warehouse:request:read` additionally see requests anchored inside their
organizational scope (union, implicit deny)."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy import false as sa_false
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext, allowed_units
from app.modules.user.models import User
from app.modules.user.schemas import PageParams
from app.modules.warehouse.models import ItemCatalog, ItemRequest, ItemRequestLine
from app.modules.warehouse.schemas import ItemBriefOut, RequestLineOut, RequestOut, format_quantity

REQUEST_READ_OPERATION = "warehouse:request:read"


def _request_scope_filter(context: ScopeContext, operation: str) -> ColumnElement[bool]:
    units = allowed_units(context, operation)
    if units.global_access:
        return sa_true()
    conditions = []
    if units.complex_ids:
        conditions.append(ItemRequest.complex_id.in_(units.complex_ids))
    if units.workplace_ids:
        conditions.append(ItemRequest.workplace_id.in_(units.workplace_ids))
    if not conditions:
        return sa_false()
    return or_(*conditions)


def _visibility_filter(context: ScopeContext) -> ColumnElement[bool]:
    caller = UUID(context.user_id)
    return or_(
        ItemRequest.requested_by == caller,
        _request_scope_filter(context, REQUEST_READ_OPERATION),
    )


def to_request_out(
    session: Session,
    request: ItemRequest,
    lines: list[tuple[ItemRequestLine, ItemCatalog]],
    requester_email: str | None = None,
) -> RequestOut:
    return RequestOut(
        id=request.id,
        version=request.version,
        status=str(request.status.value),
        requested_by=request.requested_by,
        requested_by_email=requester_email,
        purpose_description=request.purpose_description,
        decision_note=request.decision_note,
        decided_by=request.decided_by,
        decided_at=request.decided_at,
        fulfilled_at=request.fulfilled_at,
        lines=[
            RequestLineOut(
                id=line.id,
                item=ItemBriefOut(
                    id=item.id,
                    name=item.name,
                    name_fa=item.name_fa,
                    code=item.code,
                    unit=item.unit,
                    min_quantity=format_quantity(item.min_quantity),
                ),
                quantity=format_quantity(line.quantity),
                note=line.note,
            )
            for line, item in lines
        ],
        created_at=request.created_at,
    )


def get_request(session: Session, request_id: UUID) -> ItemRequest | None:
    return session.scalar(select(ItemRequest).where(ItemRequest.id == request_id))


def get_request_lines(
    session: Session, request_id: UUID
) -> list[tuple[ItemRequestLine, ItemCatalog]]:
    rows = session.execute(
        select(ItemRequestLine, ItemCatalog)
        .join(ItemCatalog, ItemRequestLine.item_id == ItemCatalog.id)
        .where(ItemRequestLine.request_id == request_id)
        .order_by(ItemRequestLine.created_at, ItemRequestLine.id)
    ).all()
    return [(line, item) for line, item in rows]


def get_requester_email(session: Session, requester_id: UUID) -> str | None:
    return session.scalar(select(User.email).where(User.id == requester_id))


def list_requests(
    session: Session,
    context: ScopeContext,
    params: PageParams,
    *,
    status: str | None = None,
) -> Page[RequestOut]:
    base = select(ItemRequest).where(_visibility_filter(context))
    if status is not None and status != "all":
        base = base.where(ItemRequest.status == status)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    requests = session.scalars(
        base.order_by(ItemRequest.created_at.desc(), ItemRequest.id.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()

    request_ids = [request.id for request in requests]
    line_rows: dict[UUID, list[tuple[ItemRequestLine, ItemCatalog]]] = {}
    item_ids: set[UUID] = set()
    if request_ids:
        all_lines = session.execute(
            select(ItemRequestLine, ItemCatalog)
            .join(ItemCatalog, ItemRequestLine.item_id == ItemCatalog.id)
            .where(ItemRequestLine.request_id.in_(request_ids))
            .order_by(ItemRequestLine.created_at, ItemRequestLine.id)
        ).all()
        for line, item in all_lines:
            line_rows.setdefault(line.request_id, []).append((line, item))
            item_ids.add(item.id)
    requester_ids = {request.requested_by for request in requests}
    emails: dict[UUID, str] = {}
    if requester_ids:
        email_rows = session.execute(
            select(User.id, User.email).where(User.id.in_(requester_ids))
        ).all()
        emails = {}
        for row_id, row_email in email_rows:
            emails[row_id] = row_email

    items = [
        to_request_out(
            session, request, line_rows.get(request.id, []), emails.get(request.requested_by)
        )
        for request in requests
    ]
    return Page[RequestOut](items=items, total=total, page=params.page, page_size=params.page_size)


def create_request(
    session: Session,
    *,
    requested_by: UUID,
    purpose_description: str,
    company_id: UUID | None,
    complex_id: UUID | None,
    workplace_id: UUID | None,
    actor_user_id: UUID,
) -> ItemRequest:
    from app.modules.warehouse.models import RequestStatus

    request = ItemRequest(
        requested_by=requested_by,
        purpose_description=purpose_description,
        status=RequestStatus.PENDING,
        company_id=company_id,
        complex_id=complex_id,
        workplace_id=workplace_id,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    session.add(request)
    session.flush()
    return request


def create_request_line(
    session: Session,
    *,
    request_id: UUID,
    item_id: UUID,
    quantity: Decimal,
    note: str | None,
    actor_user_id: UUID,
) -> ItemRequestLine:
    line = ItemRequestLine(
        request_id=request_id,
        item_id=item_id,
        quantity=quantity,
        note=note,
        created_by=actor_user_id,
    )
    session.add(line)
    session.flush()
    return line
