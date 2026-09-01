"""Asset services (Phase 6): registration, assignment, return, retirement.

Authorization model (research R5/R6): all operations require the matching
`warehouse:asset:*` permission (router) AND scope coverage over the asset's
workplace anchor; anchorless assets require global coverage. Assignment and
return are version-guarded (§25) and write history entries in the same
transaction as the state change.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.scope import ScopeContext, ScopeTarget, allowed_units, can
from app.core.errors import (
    AUTHORIZATION_DENIED,
    BUSINESS_RULE_VIOLATION,
    STALE_VERSION,
    AppError,
    duplicate_resource,
    not_found,
    validation_error,
)
from app.modules.audit.contracts import write_audit
from app.modules.user import contracts as user_contracts
from app.modules.warehouse import asset_repository
from app.modules.warehouse.models import AssetInstance, HolderType
from app.modules.warehouse.schemas import (
    AssetAssignIn,
    AssetCreateIn,
    AssetRetireIn,
    AssetReturnIn,
    AssetUpdateIn,
)

_ASSET_CREATE = "warehouse:asset:create"
_ASSET_UPDATE = "warehouse:asset:update"
_ASSET_RETIRE = "warehouse:asset:retire"
_ASSET_ASSIGN = "warehouse:asset:assign"
_ASSET_RETURN = "warehouse:asset:return"


def _require_anchor_scope(
    context: ScopeContext,
    operation: str,
    *,
    complex_id: uuid.UUID | None,
    workplace_id: uuid.UUID | None,
) -> None:
    if workplace_id is None:
        target = ScopeTarget()
    else:
        target = ScopeTarget(
            complex_id=str(complex_id) if complex_id else None,
            workplace_id=str(workplace_id),
        )
    if not can(context, operation, target):
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)


def _load_asset(
    session: Session, context: ScopeContext, asset_id: uuid.UUID, operation: str
) -> AssetInstance:
    asset = asset_repository.get_asset(session, asset_id)
    units = allowed_units(context, operation)
    if units.global_access:
        if asset is None:
            raise not_found("Asset not found")
        return asset
    if asset is None:
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    if (
        asset.workplace_id is not None
        and str(asset.workplace_id) in units.workplace_ids
        or (asset.complex_id is not None and str(asset.complex_id) in units.complex_ids)
    ):
        return asset
    raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)


def _asset_snapshot(asset: AssetInstance, holder_name: str | None) -> dict[str, object]:
    return {
        "id": str(asset.id),
        "name": asset.name,
        "serial": asset.serial,
        "status": (
            "retired"
            if asset.deleted_at is not None
            else ("assigned" if asset.holder_type is not None else "available")
        ),
        "holder_type": asset.holder_type.value if asset.holder_type else None,
        "holder_employee_id": (str(asset.holder_employee_id) if asset.holder_employee_id else None),
        "holder_location": asset.holder_location,
        "version": asset.version,
        "holder_name": holder_name,
    }


def _holder_parts(asset: AssetInstance) -> tuple[str | None, uuid.UUID | None, str | None]:
    return (
        asset.holder_type.value if asset.holder_type else None,
        asset.holder_employee_id,
        asset.holder_location,
    )


def create_asset(session: Session, context: ScopeContext, payload: AssetCreateIn) -> AssetInstance:
    serial_norm = payload.serial.strip().lower()
    if asset_repository.get_asset_by_serial_norm(session, serial_norm) is not None:
        raise duplicate_resource("An active asset with this serial already exists")

    anchor = user_contracts.get_user_workplace_anchor(session, uuid.UUID(context.user_id))
    asset = AssetInstance(
        name=payload.name.strip(),
        name_fa=payload.name_fa.strip(),
        serial=payload.serial.strip(),
        serial_norm=serial_norm,
        description=payload.description,
        company_id=anchor.company_id if anchor else None,
        complex_id=anchor.complex_id if anchor else None,
        workplace_id=anchor.workplace_id if anchor else None,
        created_by=uuid.UUID(context.user_id),
        updated_by=uuid.UUID(context.user_id),
    )
    session.add(asset)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise duplicate_resource("An active asset with this serial already exists") from exc

    asset_repository.write_history(
        session,
        asset_id=asset.id,
        action="created",
        from_type=None,
        from_employee_id=None,
        from_location=None,
        to_type=None,
        to_employee_id=None,
        to_location=None,
        note=None,
        actor_user_id=uuid.UUID(context.user_id),
    )
    write_audit(
        session,
        action="ASSET_CREATED",
        entity_type="asset",
        entity_id=asset.id,
        actor_user_id=uuid.UUID(context.user_id),
        after=_asset_snapshot(asset, None),
        critical=True,
    )
    session.commit()
    return asset


def update_asset(
    session: Session, context: ScopeContext, asset_id: uuid.UUID, payload: AssetUpdateIn
) -> AssetInstance:
    asset = _load_asset(session, context, asset_id, _ASSET_UPDATE)
    if asset.version != payload.version:
        raise AppError(
            STALE_VERSION,
            "This record changed since you opened it — refresh and retry",
            status_code=409,
        )
    holder_name = (
        asset_repository.get_holder_name(session, asset.holder_employee_id)
        if asset.holder_employee_id
        else None
    )
    before = _asset_snapshot(asset, holder_name)
    updates = payload.model_dump(exclude={"version"}, exclude_unset=True)
    if (
        "serial" in updates
        and updates["serial"] is not None
        and updates["serial"].strip().lower() != asset.serial_norm
    ):
        raise validation_error("Serial numbers are immutable after creation")
    if "name" in updates and updates["name"] is not None:
        asset.name = updates["name"].strip()
    if "name_fa" in updates and updates["name_fa"] is not None:
        asset.name_fa = updates["name_fa"].strip()
    if "description" in updates:
        asset.description = updates["description"]
    asset.updated_by = uuid.UUID(context.user_id)
    asset.version += 1
    session.add(asset)

    asset_repository.write_history(
        session,
        asset_id=asset.id,
        action="updated",
        from_type=None,
        from_employee_id=None,
        from_location=None,
        to_type=None,
        to_employee_id=None,
        to_location=None,
        note=None,
        actor_user_id=uuid.UUID(context.user_id),
    )
    write_audit(
        session,
        action="ASSET_UPDATED",
        entity_type="asset",
        entity_id=asset.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_asset_snapshot(asset, holder_name),
        critical=True,
    )
    session.commit()
    return asset


def retire_asset(
    session: Session, context: ScopeContext, asset_id: uuid.UUID, payload: AssetRetireIn
) -> AssetInstance:
    asset = _load_asset(session, context, asset_id, _ASSET_RETIRE)
    if asset.deleted_at is None:
        if asset.holder_type is not None:
            raise AppError(
                BUSINESS_RULE_VIOLATION,
                "Retirement is blocked while the asset is assigned — return it first",
                status_code=422,
            )
        if asset.version != payload.version:
            raise AppError(
                STALE_VERSION,
                "This record changed since you opened it — refresh and retry",
                status_code=409,
            )
        holder_name = (
            asset_repository.get_holder_name(session, asset.holder_employee_id)
            if asset.holder_employee_id
            else None
        )
        before = _asset_snapshot(asset, holder_name)
        asset.deleted_at = datetime.now(UTC)
        asset.updated_by = uuid.UUID(context.user_id)
        asset.version += 1
        session.add(asset)
        asset_repository.write_history(
            session,
            asset_id=asset.id,
            action="retired",
            from_type=None,
            from_employee_id=None,
            from_location=None,
            to_type=None,
            to_employee_id=None,
            to_location=None,
            note=payload_note(payload),
            actor_user_id=uuid.UUID(context.user_id),
        )
        write_audit(
            session,
            action="ASSET_RETIRED",
            entity_type="asset",
            entity_id=asset.id,
            actor_user_id=uuid.UUID(context.user_id),
            before=before,
            after=_asset_snapshot(asset, holder_name),
            critical=True,
        )
    else:
        write_audit(
            session,
            action="ASSET_RETIRED",
            entity_type="asset",
            entity_id=asset.id,
            actor_user_id=uuid.UUID(context.user_id),
            after=_asset_snapshot(asset, None),
            critical=True,
        )
    session.commit()
    return asset


def payload_note(payload: AssetRetireIn | AssetReturnIn) -> str | None:
    return getattr(payload, "note", None)


def assign_asset(
    session: Session, context: ScopeContext, asset_id: uuid.UUID, payload: AssetAssignIn
) -> AssetInstance:
    asset = _load_asset(session, context, asset_id, _ASSET_ASSIGN)
    if asset.version != payload.version:
        raise AppError(
            STALE_VERSION,
            "This record changed since you opened it — refresh and retry",
            status_code=409,
        )
    if asset.holder_type is not None:
        raise AppError(
            BUSINESS_RULE_VIOLATION,
            "The asset is already assigned — return it first",
            status_code=422,
        )

    holder_name: str | None = None
    if payload.target_type == "employee":
        if payload.employee_id is None:
            raise validation_error("employee_id is required for an employee target")
        holder = user_contracts.get_employee_holder(session, payload.employee_id)
        if holder is None:
            raise validation_error("Unknown employee")
        if not holder.is_active:
            raise validation_error("The employee is deactivated")
        _require_anchor_scope(
            context, _ASSET_ASSIGN, complex_id=holder.complex_id, workplace_id=holder.workplace_id
        )
        holder_name = holder.display_name
        to_type, to_employee_id, to_location = (
            HolderType.EMPLOYEE.value,
            holder.id,
            None,
        )
        asset.holder_type = HolderType.EMPLOYEE
        asset.holder_employee_id = holder.id
        asset.holder_location = None
    else:
        if not payload.location:
            raise validation_error("location is required for a location target")
        to_type, to_employee_id, to_location = (
            HolderType.LOCATION.value,
            None,
            payload.location,
        )
        asset.holder_type = HolderType.LOCATION
        asset.holder_employee_id = None
        asset.holder_location = payload.location

    asset.updated_by = uuid.UUID(context.user_id)
    asset.version += 1
    session.add(asset)
    asset_repository.write_history(
        session,
        asset_id=asset.id,
        action="assigned",
        from_type=None,
        from_employee_id=None,
        from_location=None,
        to_type=to_type,
        to_employee_id=to_employee_id,
        to_location=to_location,
        note=payload.note,
        actor_user_id=uuid.UUID(context.user_id),
    )
    write_audit(
        session,
        action="ASSET_ASSIGNED",
        entity_type="asset",
        entity_id=asset.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=_asset_snapshot(asset, None),
        after=_asset_snapshot(asset, holder_name),
        critical=True,
    )
    session.commit()
    return asset


def return_asset(
    session: Session, context: ScopeContext, asset_id: uuid.UUID, payload: AssetReturnIn
) -> AssetInstance:
    asset = _load_asset(session, context, asset_id, _ASSET_RETURN)
    if asset.version != payload.version:
        raise AppError(
            STALE_VERSION,
            "This record changed since you opened it — refresh and retry",
            status_code=409,
        )
    if asset.holder_type is None:
        raise AppError(
            BUSINESS_RULE_VIOLATION,
            "The asset is not assigned — nothing to return",
            status_code=422,
        )

    holder_name = (
        asset_repository.get_holder_name(session, asset.holder_employee_id)
        if asset.holder_employee_id
        else None
    )
    before = _asset_snapshot(asset, holder_name)
    from_type, from_employee_id, from_location = _holder_parts(asset)
    asset.holder_type = None
    asset.holder_employee_id = None
    asset.holder_location = None
    asset.updated_by = uuid.UUID(context.user_id)
    asset.version += 1
    session.add(asset)
    asset_repository.write_history(
        session,
        asset_id=asset.id,
        action="returned",
        from_type=from_type,
        from_employee_id=from_employee_id,
        from_location=from_location,
        to_type=None,
        to_employee_id=None,
        to_location=None,
        note=payload.note,
        actor_user_id=uuid.UUID(context.user_id),
    )
    write_audit(
        session,
        action="ASSET_RETURNED",
        entity_type="asset",
        entity_id=asset.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_asset_snapshot(asset, holder_name),
        critical=True,
    )
    session.commit()
    return asset


__all__ = [
    "assign_asset",
    "create_asset",
    "retire_asset",
    "return_asset",
    "update_asset",
]
