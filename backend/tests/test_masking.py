from app.common.masking import (
    mask_email,
    mask_identifier,
    mask_secret,
    mask_snapshot,
    mask_user_agent,
)


def test_mask_secret() -> None:
    assert mask_secret("super-secret") == "***"
    assert mask_secret(None) == ""


def test_mask_email_keeps_domain() -> None:
    assert mask_email("ali.rezaei@zarandsteel.ir") == "a***@zarandsteel.ir"
    assert mask_email("@domain.test") == "***@domain.test"
    assert mask_email("not-an-email") == "***"
    assert mask_email(None) == ""


def test_mask_identifier_keeps_last_four() -> None:
    assert mask_identifier("1234567890") == "***7890"
    assert mask_identifier("1234") == "***"
    assert mask_identifier(None) == ""


def test_mask_user_agent_truncates() -> None:
    assert mask_user_agent("x" * 400) == "x" * 256
    assert mask_user_agent(None) == ""


def test_mask_snapshot_masks_sensitive_keys() -> None:
    snapshot = {
        "email": "ali@zarandsteel.ir",
        "password": "plain",
        "refresh_token": "rt-value",
        "national_id": "1234567890",
        "personnel_code": "998877",
        "role_name": "SuperAdmin",
        "attempts": 3,
        "nested": None,
    }
    masked = mask_snapshot(snapshot)
    assert masked["email"] == "a***@zarandsteel.ir"
    assert masked["password"] == "***"
    assert masked["refresh_token"] == "***"
    assert masked["national_id"] == "***7890"
    assert masked["personnel_code"] == "***8877"
    assert masked["role_name"] == "SuperAdmin"
    assert masked["attempts"] == 3
    assert masked["nested"] is None


def test_mask_snapshot_handles_none_and_empty() -> None:
    assert mask_snapshot(None) is None
    assert mask_snapshot({}) == {}
