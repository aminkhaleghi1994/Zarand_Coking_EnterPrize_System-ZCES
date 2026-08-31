import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import (
    AUTHENTICATION_REQUIRED,
    AppError,
    duplicate_resource,
    not_found,
    validation_error,
)
from app.modules.audit.contracts import write_audit
from app.modules.user import auth_service, repository
from app.modules.user.dependencies import load_context, require_permission
from app.modules.user.models import Role, ScopeAssignment, ScopeLevel, UserRole
from app.modules.user.schemas import (
    AssignRoleIn,
    LoginIn,
    MeOut,
    PageParams,
    PermissionOut,
    RefreshTokenIn,
    RoleCreateIn,
    RoleOut,
    ScopeAssignmentOut,
    ScopeCreateIn,
    SuccessOut,
    TokenPairOut,
    UserOut,
)

require_role_read = require_permission("user:role:read")
require_role_create = require_permission("user:role:create")
require_role_assign = require_permission("user:role:assign")
require_permission_read = require_permission("user:permission:read")
require_user_list = require_permission("user:list:read")
require_scope_assign = require_permission("user:scope:assign")

router = APIRouter(tags=["auth"])
admin_router = APIRouter(tags=["admin"])


def _client_agent(request: Request) -> str | None:
    return request.headers.get("User-Agent")


@router.post("/auth/login", response_model=TokenPairOut)
def login(payload: LoginIn, request: Request, session: Session = Depends(get_db)) -> TokenPairOut:
    user, access_token, refresh_token = auth_service.authenticate(
        session, email=payload.email, password=payload.password, user_agent=_client_agent(request)
    )
    settings = get_settings()
    _ = settings
    pair = TokenPairOut(
        user=UserOut.model_validate(user),
        roles=repository.get_user_role_names(session, user.id),
        access_token=access_token,
        access_expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=refresh_token,
    )
    return pair


@router.post("/auth/refresh", response_model=TokenPairOut)
def refresh(
    payload: RefreshTokenIn, request: Request, session: Session = Depends(get_db)
) -> TokenPairOut:
    user, access_token, new_refresh = auth_service.rotate(
        session, refresh_token=payload.refresh_token, user_agent=_client_agent(request)
    )
    settings = get_settings()
    return TokenPairOut(
        user=UserOut.model_validate(user),
        roles=repository.get_user_role_names(session, user.id),
        access_token=access_token,
        access_expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=new_refresh,
    )


@router.post("/auth/logout", response_model=SuccessOut)
def logout(payload: RefreshTokenIn, session: Session = Depends(get_db)) -> SuccessOut:
    auth_service.logout(session, refresh_token=payload.refresh_token)
    return SuccessOut()


@router.get("/auth/me", response_model=MeOut)
def me(
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> MeOut:
    user = repository.get_active_user_by_id(session, uuid.UUID(context.user_id))
    if user is None:
        raise AppError(AUTHENTICATION_REQUIRED, "Authentication required", status_code=401)
    return MeOut(
        user=UserOut.model_validate(user),
        roles=repository.get_user_role_names(session, user.id),
        permissions=sorted(context.permission_codes),
        scopes=repository.get_user_scopes(session, user.id),
    )


@router.get("/auth/session/validate", status_code=204)
def validate_session(context=Depends(load_context)) -> None:  # type: ignore[no-untyped-def]
    _ = context


@admin_router.get("/roles", response_model=Page[RoleOut])
def list_roles(
    params: PageParams = Depends(),
    context: ScopeContext = Depends(require_role_read),
    session: Session = Depends(get_db),
) -> Page[RoleOut]:
    _ = context
    return repository.list_roles(session, params)


@admin_router.post("/roles", response_model=RoleOut, status_code=201)
def create_role(
    payload: RoleCreateIn,
    context: ScopeContext = Depends(require_role_create),
    session: Session = Depends(get_db),
) -> RoleOut:
    existing = (
        session.query(Role).filter(Role.name == payload.name, Role.deleted_at.is_(None)).first()
    )
    if existing:
        raise duplicate_resource("A role with this name already exists")
    role = Role(name=payload.name, description=payload.description)
    session.add(role)
    session.flush()
    write_audit(
        session,
        action="ROLE_CREATED",
        entity_type="role",
        entity_id=role.id,
        actor_user_id=uuid.UUID(context.user_id),
        after={"name": role.name},
    )
    return RoleOut.model_validate(role)


@admin_router.get("/permissions", response_model=Page[PermissionOut])
def list_permissions(
    params: PageParams = Depends(),
    context: ScopeContext = Depends(require_permission_read),
    session: Session = Depends(get_db),
) -> Page[PermissionOut]:
    _ = context
    return repository.list_permissions(session, params)


@admin_router.get("/users", response_model=Page[UserOut])
def list_users(
    params: PageParams = Depends(),
    context: ScopeContext = Depends(require_user_list),
    session: Session = Depends(get_db),
) -> Page[UserOut]:
    _ = context
    return repository.list_users(session, params)


@admin_router.post("/users/{user_id}/roles", response_model=SuccessOut)
def assign_role(
    user_id: uuid.UUID,
    payload: AssignRoleIn,
    context: ScopeContext = Depends(require_role_assign),
    session: Session = Depends(get_db),
) -> SuccessOut:
    user = repository.get_active_user_by_id(session, user_id)
    if user is None:
        raise not_found("User not found")
    role = repository.get_role_by_id(session, payload.role_id)
    if role is None:
        raise not_found("Role not found")
    if repository.get_user_role(session, user_id, payload.role_id):
        raise duplicate_resource("Role already assigned to user")
    session.add(UserRole(user_id=user_id, role_id=payload.role_id))
    session.flush()
    write_audit(
        session,
        action="ROLE_ASSIGNED",
        entity_type="user",
        entity_id=user_id,
        actor_user_id=uuid.UUID(context.user_id),
        after={"role_id": str(payload.role_id), "role_name": role.name},
    )
    return SuccessOut()


@admin_router.delete("/users/{user_id}/roles/{role_id}", response_model=SuccessOut)
def revoke_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    context: ScopeContext = Depends(require_role_assign),
    session: Session = Depends(get_db),
) -> SuccessOut:
    user_role = repository.get_user_role(session, user_id, role_id)
    if user_role is None:
        raise not_found("Role assignment not found")
    role = repository.get_role_by_id(session, role_id)
    session.delete(user_role)
    session.flush()
    write_audit(
        session,
        action="ROLE_REVOKED",
        entity_type="user",
        entity_id=user_id,
        actor_user_id=uuid.UUID(context.user_id),
        before={"role_id": str(role_id), "role_name": role.name if role else None},
    )
    return SuccessOut()


@admin_router.post("/users/{user_id}/scopes", response_model=ScopeAssignmentOut, status_code=201)
def assign_scope(
    user_id: uuid.UUID,
    payload: ScopeCreateIn,
    context: ScopeContext = Depends(require_scope_assign),
    session: Session = Depends(get_db),
) -> ScopeAssignmentOut:
    user = repository.get_active_user_by_id(session, user_id)
    if user is None:
        raise not_found("User not found")
    if payload.level == "complex" and payload.complex_id is None:
        raise validation_error("complex_id is required for complex-level scope")
    if payload.level == "workplace" and payload.workplace_id is None:
        raise validation_error("workplace_id is required for workplace-level scope")
    if payload.level == "global" and (payload.complex_id or payload.workplace_id):
        raise validation_error("global-level scope must not carry unit ids")

    assignment = ScopeAssignment(
        user_id=user_id,
        level=ScopeLevel(payload.level),
        module=payload.module,
        resource=payload.resource,
        operation=payload.operation,
        complex_id=payload.complex_id,
        workplace_id=payload.workplace_id,
    )
    session.add(assignment)
    session.flush()
    write_audit(
        session,
        action="SCOPE_ASSIGNED",
        entity_type="scope_assignment",
        entity_id=assignment.id,
        actor_user_id=uuid.UUID(context.user_id),
        after={
            "user_id": str(user_id),
            "level": str(payload.level),
            "target": f"{payload.module}:{payload.resource}:{payload.operation}",
            "complex_id": str(payload.complex_id) if payload.complex_id else None,
            "workplace_id": str(payload.workplace_id) if payload.workplace_id else None,
        },
    )
    return ScopeAssignmentOut.model_validate(assignment)


@admin_router.delete("/users/{user_id}/scopes/{assignment_id}", response_model=SuccessOut)
def revoke_scope(
    user_id: uuid.UUID,
    assignment_id: uuid.UUID,
    context: ScopeContext = Depends(require_scope_assign),
    session: Session = Depends(get_db),
) -> SuccessOut:
    assignment = repository.get_scope_assignment(session, user_id, assignment_id)
    if assignment is None:
        raise not_found("Scope assignment not found")
    before = {
        "user_id": str(user_id),
        "level": assignment.level.value,
        "target": f"{assignment.module}:{assignment.resource}:{assignment.operation}",
    }
    session.delete(assignment)
    session.flush()
    write_audit(
        session,
        action="SCOPE_REVOKED",
        entity_type="scope_assignment",
        entity_id=assignment_id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
    )
    return SuccessOut()
