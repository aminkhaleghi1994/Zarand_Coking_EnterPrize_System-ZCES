import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.masking import mask_identifier, mask_snapshot
from app.common.scope import ScopeContext, ScopeTarget, can
from app.core.errors import (
    AUTHORIZATION_DENIED,
    STALE_VERSION,
    AppError,
    duplicate_resource,
    not_found,
)
from app.core.security import hash_password
from app.modules.audit.contracts import write_audit
from app.modules.user import employee_repository, org_repository
from app.modules.user.models import Complex, Employee, User, Workplace
from app.modules.user.schemas import (
    EmployeeComplexOut,
    EmployeeCreateIn,
    EmployeeOut,
    EmployeeUpdateIn,
    EmployeeUserOut,
    EmployeeWorkplaceOut,
)

_EMPLOYEE_CREATE = "user:employee:create"
_EMPLOYEE_UPDATE = "user:employee:update"
_EMPLOYEE_DEACTIVATE = "user:employee:deactivate"
_PASSWORD_SET = "user:password:set"


def _require_target_scope(
    context: ScopeContext, operation: str, workplace: Workplace, complex_: Complex
) -> None:
    if not can(
        context,
        operation,
        ScopeTarget(complex_id=str(complex_.id), workplace_id=str(workplace.id)),
    ):
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)


def _load_workplace_in_scope(
    session: Session, context: ScopeContext, workplace_id: uuid.UUID, operation: str
) -> tuple[Workplace, Complex]:
    workplace = org_repository.get_workplace(session, workplace_id)
    if workplace is None:
        raise not_found("Workplace not found")
    complex_ = org_repository.get_complex(session, workplace.complex_id)
    if complex_ is None:
        raise not_found("Complex not found")
    _require_target_scope(context, operation, workplace, complex_)
    return workplace, complex_


def _mask_national_id(value: str, context: ScopeContext) -> str:
    if "user:employee:read_full" in context.permission_codes:
        return value
    return mask_identifier(value)


def to_employee_out(session: Session, employee: Employee, context: ScopeContext) -> EmployeeOut:
    workplace = session.get(Workplace, employee.workplace_id)
    complex_ = session.get(Complex, workplace.complex_id) if workplace is not None else None
    user = employee_repository.get_user_by_employee_id(session, employee.id)
    if workplace is None or complex_ is None or user is None:
        raise not_found("Employee is missing required related records")
    return EmployeeOut(
        id=employee.id,
        version=employee.version,
        national_id=_mask_national_id(employee.national_id, context),
        personnel_code=employee.personnel_code,
        first_name=employee.first_name,
        last_name=employee.last_name,
        first_name_fa=employee.first_name_fa,
        last_name_fa=employee.last_name_fa,
        birth_date=employee.birth_date,
        phone=employee.phone,
        is_active=employee.is_active and employee.deleted_at is None,
        workplace=EmployeeWorkplaceOut(
            id=workplace.id,
            code=workplace.code,
            name=workplace.name,
            name_fa=workplace.name_fa,
            complex_id=workplace.complex_id,
        ),
        complex=EmployeeComplexOut(
            id=complex_.id,
            code=complex_.code,
            name=complex_.name,
            name_fa=complex_.name_fa,
        ),
        user=EmployeeUserOut(
            id=user.id,
            email=user.email,
            username=user.username,
            is_active=user.is_active,
        ),
        created_at=employee.created_at,
    )


def _employee_snapshot(employee: Employee) -> dict[str, object]:
    return {
        "id": str(employee.id),
        "national_id": employee.national_id,
        "personnel_code": employee.personnel_code,
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "workplace_id": str(employee.workplace_id),
        "is_active": employee.is_active,
        "version": employee.version,
    }


def create_employee_with_user(
    session: Session, context: ScopeContext, payload: EmployeeCreateIn
) -> Employee:
    workplace, complex_ = _load_workplace_in_scope(
        session, context, payload.workplace_id, _EMPLOYEE_CREATE
    )

    if employee_repository.get_by_national_id(session, payload.national_id) is not None:
        raise duplicate_resource("An active employee with this national ID already exists")
    if employee_repository.get_by_personnel_code(session, payload.personnel_code) is not None:
        raise duplicate_resource("An active employee with this personnel code already exists")
    if employee_repository.get_user_by_email(session, payload.user.email) is not None:
        raise duplicate_resource("An active user with this email already exists")
    if employee_repository.get_user_by_username(session, payload.user.username) is not None:
        raise duplicate_resource("An active user with this username already exists")

    employee = Employee(
        workplace_id=workplace.id,
        national_id=payload.national_id,
        personnel_code=payload.personnel_code,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        first_name_fa=(payload.first_name_fa or None),
        last_name_fa=(payload.last_name_fa or None),
        birth_date=payload.birth_date,
        phone=(payload.phone or None),
        is_active=True,
        created_by=uuid.UUID(context.user_id),
        updated_by=uuid.UUID(context.user_id),
    )
    user = User(
        email=payload.user.email.strip().lower(),
        username=payload.user.username.strip(),
        hashed_password=hash_password(payload.user.password),
        is_active=True,
        employee_id=None,
        created_by=uuid.UUID(context.user_id),
        updated_by=uuid.UUID(context.user_id),
    )
    session.add(employee)
    session.flush()
    user.employee_id = employee.id
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise duplicate_resource(
            "A duplicate national ID, personnel code, email or username already exists"
        ) from exc

    write_audit(
        session,
        action="EMPLOYEE_CREATED",
        entity_type="employee",
        entity_id=employee.id,
        actor_user_id=uuid.UUID(context.user_id),
        after=mask_snapshot(
            {
                **_employee_snapshot(employee),
                "user_id": str(user.id),
                "user_email": user.email,
                "password": "***",
            }
        ),
        critical=True,
    )
    session.commit()
    return employee


def update_employee(
    session: Session,
    context: ScopeContext,
    employee_id: uuid.UUID,
    payload: EmployeeUpdateIn,
) -> Employee:
    employee = employee_repository.get_employee_in_scope(
        session, employee_id, context, _EMPLOYEE_UPDATE
    )
    if employee is None:
        raise not_found("Employee not found")
    workplace = session.get(Workplace, employee.workplace_id)
    complex_ = session.get(Complex, workplace.complex_id) if workplace else None
    if workplace is None or complex_ is None:
        raise not_found("Employee is missing required related records")
    _require_target_scope(context, _EMPLOYEE_UPDATE, workplace, complex_)

    if employee.version != payload.version:
        raise AppError(
            STALE_VERSION,
            "This record changed since you opened it — refresh and retry",
            status_code=409,
        )

    before = mask_snapshot(_employee_snapshot(employee))
    moved = False
    if payload.workplace_id is not None and payload.workplace_id != employee.workplace_id:
        new_workplace, _ = _load_workplace_in_scope(
            session, context, payload.workplace_id, _EMPLOYEE_UPDATE
        )
        employee.workplace_id = new_workplace.id
        moved = True

    updates = payload.model_dump(exclude={"version", "workplace_id"}, exclude_unset=True)
    if "first_name" in updates and updates["first_name"] is not None:
        employee.first_name = updates["first_name"].strip()
    if "last_name" in updates and updates["last_name"] is not None:
        employee.last_name = updates["last_name"].strip()
    if "first_name_fa" in updates:
        employee.first_name_fa = updates["first_name_fa"]
    if "last_name_fa" in updates:
        employee.last_name_fa = updates["last_name_fa"]
    if "birth_date" in updates:
        employee.birth_date = updates["birth_date"]
    if "phone" in updates:
        employee.phone = updates["phone"]
    employee.updated_by = uuid.UUID(context.user_id)
    employee.version += 1
    session.add(employee)
    session.flush()

    write_audit(
        session,
        action="EMPLOYEE_MOVED" if moved else "EMPLOYEE_UPDATED",
        entity_type="employee",
        entity_id=employee.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=mask_snapshot(_employee_snapshot(employee)),
        critical=True,
    )
    session.commit()
    return employee


def _set_employee_active(
    session: Session,
    context: ScopeContext,
    employee_id: uuid.UUID,
    *,
    active: bool,
    version: int | None,
) -> Employee:
    employee = employee_repository.get_employee_in_scope(
        session, employee_id, context, _EMPLOYEE_DEACTIVATE
    )
    if employee is None:
        raise not_found("Employee not found")
    workplace = session.get(Workplace, employee.workplace_id)
    complex_ = session.get(Complex, workplace.complex_id) if workplace else None
    if workplace is None or complex_ is None:
        raise not_found("Employee is missing required related records")
    _require_target_scope(context, _EMPLOYEE_DEACTIVATE, workplace, complex_)

    currently_active = employee.deleted_at is None and employee.is_active
    if currently_active != active:
        if version is not None and employee.version != version:
            raise AppError(
                STALE_VERSION,
                "This record changed since you opened it — refresh and retry",
                status_code=409,
            )
        before = mask_snapshot(_employee_snapshot(employee))
        employee.is_active = active
        employee.deleted_at = None if active else datetime.now(UTC)
        employee.updated_by = uuid.UUID(context.user_id)
        employee.version += 1
        session.add(employee)

        user = employee_repository.get_user_by_employee_id(session, employee.id)
        if user is not None:
            user.is_active = active
            session.add(user)
            from app.modules.user import auth_service

            if not active:
                auth_service.revoke_all_for_user(session, user.id)

        write_audit(
            session,
            action="EMPLOYEE_REACTIVATED" if active else "EMPLOYEE_DEACTIVATED",
            entity_type="employee",
            entity_id=employee.id,
            actor_user_id=uuid.UUID(context.user_id),
            before=before,
            after=mask_snapshot(_employee_snapshot(employee)),
            critical=True,
        )
    else:
        write_audit(
            session,
            action="EMPLOYEE_REACTIVATED" if active else "EMPLOYEE_DEACTIVATED",
            entity_type="employee",
            entity_id=employee.id,
            actor_user_id=uuid.UUID(context.user_id),
            after=mask_snapshot(_employee_snapshot(employee)),
            critical=True,
        )
    session.commit()
    return employee


def deactivate_employee(
    session: Session, context: ScopeContext, employee_id: uuid.UUID, version: int | None = None
) -> Employee:
    return _set_employee_active(session, context, employee_id, active=False, version=version)


def reactivate_employee(
    session: Session, context: ScopeContext, employee_id: uuid.UUID, version: int | None = None
) -> Employee:
    return _set_employee_active(session, context, employee_id, active=True, version=version)


def set_user_password(
    session: Session, context: ScopeContext, user_id: uuid.UUID, password: str
) -> None:
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise not_found("User not found")
    if user.employee_id is not None:
        employee = employee_repository.get_employee_in_scope(
            session, user.employee_id, context, _PASSWORD_SET
        )
        if employee is None:
            raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    else:
        units_ok = can(context, _PASSWORD_SET, ScopeTarget())
        if not units_ok:
            raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)

    from app.modules.user import auth_service

    user.hashed_password = hash_password(password)
    user.updated_by = uuid.UUID(context.user_id)
    user.version += 1
    session.add(user)
    auth_service.revoke_all_for_user(session, user.id)
    write_audit(
        session,
        action="USER_PASSWORD_SET",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=uuid.UUID(context.user_id),
        after={"user_id": str(user.id), "password": "***"},
        critical=True,
    )
    session.commit()


__all__ = [
    "create_employee_with_user",
    "deactivate_employee",
    "reactivate_employee",
    "set_user_password",
    "to_employee_out",
    "update_employee",
]
