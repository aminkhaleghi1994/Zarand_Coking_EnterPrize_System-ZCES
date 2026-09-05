from app.common.masking import mask_snapshot
from app.core.tracing import get_trace_id, set_trace_id
from app.modules.audit.service import write_audit


def test_masking_of_snapshots_is_structural() -> None:
    masked = mask_snapshot(
        {
            "email": "ali@zarandsteel.ir",
            "password": "hunter2",
            "national_id": "0012345678",
            "refresh_token": "rt-value",
            "role_name": "SuperAdmin",
            "amount": "20000000.00",
        }
    )
    assert masked is not None
    assert masked["email"] == "a***@zarandsteel.ir"
    assert masked["password"] == "***"
    assert masked["national_id"] == "***5678"
    assert masked["refresh_token"] == "***"
    assert masked["role_name"] == "SuperAdmin"
    assert masked["amount"] == "***"


def test_deferred_audit_without_session_does_not_raise() -> None:
    write_audit(
        None,
        action="ROLE_ASSIGNED",
        entity_type="role",
        after={"name": "Ghost"},
    )


def test_critical_audit_without_session_is_logged_not_raised() -> None:
    write_audit(
        None,
        action="LOGIN_SUCCEEDED",
        entity_type="user",
        critical=True,
    )


def test_trace_id_roundtrip_in_context() -> None:
    set_trace_id("audit-trace-42")
    assert get_trace_id() == "audit-trace-42"
