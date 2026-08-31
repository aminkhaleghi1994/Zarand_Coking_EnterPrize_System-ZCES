import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AUTHENTICATION_REQUIRED, AppError
from app.core.security import (
    create_access_token,
    hash_opaque_token,
    new_opaque_token,
    verify_password,
)
from app.modules.audit.contracts import write_audit
from app.modules.user import repository
from app.modules.user.models import RefreshToken, RefreshTokenStatus, User

_GENERIC_INVALID_CREDENTIALS = "Invalid credentials"


def _now() -> datetime:
    return datetime.now(UTC)


def authenticate(
    session: Session, *, email: str, password: str, user_agent: str | None = None
) -> tuple[User, str, str]:
    user = repository.get_active_user_by_email(session, email)
    base_snapshot: dict[str, str | None] = {"email": email, "user_agent": user_agent}

    if user is None:
        write_audit(
            session,
            action="LOGIN_FAILED",
            entity_type="user",
            after={**base_snapshot, "outcome": "unknown_email"},
            critical=True,
        )
        session.commit()
        raise AppError(AUTHENTICATION_REQUIRED, _GENERIC_INVALID_CREDENTIALS, status_code=401)

    if not verify_password(password, user.hashed_password):
        write_audit(
            session,
            action="LOGIN_FAILED",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            after={**base_snapshot, "outcome": "bad_password"},
            critical=True,
        )
        session.commit()
        raise AppError(AUTHENTICATION_REQUIRED, _GENERIC_INVALID_CREDENTIALS, status_code=401)

    if not user.is_active:
        write_audit(
            session,
            action="LOGIN_FAILED",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            after={**base_snapshot, "outcome": "inactive"},
            critical=True,
        )
        session.commit()
        raise AppError(AUTHENTICATION_REQUIRED, _GENERIC_INVALID_CREDENTIALS, status_code=401)

    access_token, refresh_token = issue_family(session, user, user_agent=user_agent)
    write_audit(
        session,
        action="LOGIN_SUCCEEDED",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        after={**base_snapshot, "outcome": "succeeded"},
        critical=True,
    )
    return user, access_token, refresh_token


def issue_family(session: Session, user: User, *, user_agent: str | None = None) -> tuple[str, str]:
    settings = get_settings()
    refresh_token = new_opaque_token()
    member = RefreshToken(
        user_id=user.id,
        family_id=uuid.uuid4(),
        token_hash=hash_opaque_token(refresh_token),
        status=RefreshTokenStatus.ACTIVE,
        expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=user_agent[:256] if user_agent else None,
    )
    session.add(member)
    session.flush()
    access_token, _ = create_access_token(str(user.id), settings)
    session.commit()
    return access_token, refresh_token


def rotate(
    session: Session, *, refresh_token: str, user_agent: str | None = None
) -> tuple[User, str, str]:
    settings = get_settings()
    member = repository.get_refresh_member_by_hash(session, hash_opaque_token(refresh_token))

    if member is None:
        raise AppError(AUTHENTICATION_REQUIRED, "Invalid session", status_code=401)

    if member.status != RefreshTokenStatus.ACTIVE:
        _revoke_family(session, member, reason="reuse_detected")
        raise AppError(AUTHENTICATION_REQUIRED, "Invalid session", status_code=401)

    if member.expires_at <= _now():
        raise AppError(AUTHENTICATION_REQUIRED, "Invalid session", status_code=401)

    user = repository.get_active_user_by_id(session, member.user_id)
    if user is None or not user.is_active:
        _revoke_family(session, member, reason="user_inactive")
        raise AppError(AUTHENTICATION_REQUIRED, "Invalid session", status_code=401)

    new_refresh = new_opaque_token()
    new_member = RefreshToken(
        user_id=member.user_id,
        family_id=member.family_id,
        token_hash=hash_opaque_token(new_refresh),
        status=RefreshTokenStatus.ACTIVE,
        expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=user_agent[:256] if user_agent else member.user_agent,
    )
    session.add(new_member)
    session.flush()
    member.status = RefreshTokenStatus.ROTATED
    member.rotated_to_id = new_member.id
    session.flush()

    access_token, _ = create_access_token(str(user.id), settings)
    write_audit(
        session,
        action="TOKEN_RENEWED",
        entity_type="session",
        entity_id=new_member.id,
        actor_user_id=user.id,
        after={"family_id": str(member.family_id), "user_agent": user_agent or member.user_agent},
        critical=True,
    )
    session.commit()
    return user, access_token, new_refresh


def logout(session: Session, *, refresh_token: str) -> None:
    member = repository.get_refresh_member_by_hash(session, hash_opaque_token(refresh_token))
    if member is None or member.status != RefreshTokenStatus.ACTIVE or member.expires_at <= _now():
        raise AppError(AUTHENTICATION_REQUIRED, "Invalid session", status_code=401)
    _revoke_family(session, member, reason="logout")


def revoke_all_for_user(session: Session, user_id: uuid.UUID) -> None:
    family_ids = repository.list_active_families_for_user(session, user_id)
    for family_id in family_ids:
        for member in repository.list_family_members(session, family_id):
            member.status = RefreshTokenStatus.REVOKED
    session.flush()
    write_audit(
        session,
        action="FAMILY_REVOKED",
        entity_type="user",
        entity_id=user_id,
        after={"reason": "user_deactivated", "families": len(family_ids)},
        critical=True,
    )
    session.commit()


def _revoke_family(session: Session, member: RefreshToken, *, reason: str) -> None:
    members = repository.list_family_members(session, member.family_id)
    for row in members:
        row.status = RefreshTokenStatus.REVOKED
    session.flush()
    if reason == "reuse_detected":
        write_audit(
            session,
            action="TOKEN_REUSE_DETECTED",
            entity_type="session",
            entity_id=member.id,
            actor_user_id=member.user_id,
            after={"family_id": str(member.family_id), "reason": reason},
            critical=True,
        )
    write_audit(
        session,
        action="FAMILY_REVOKED",
        entity_type="session",
        entity_id=member.id,
        actor_user_id=member.user_id,
        after={"family_id": str(member.family_id), "reason": reason},
        critical=True,
    )
    session.commit()
