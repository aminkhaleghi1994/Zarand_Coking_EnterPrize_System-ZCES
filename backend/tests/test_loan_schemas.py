from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.loan.models import LoanStatus, LoanType  # noqa: F401 (enum parity)
from app.modules.loan.schemas import (
    LoanPolicyCreateIn,
    LoanPolicyRetireIn,
    LoanPolicyUpdateIn,
    LoanRequestCreateIn,
    LoanRequestOut,
    LoanRequestTransitionIn,
    format_money,
    parse_money,
)


def test_money_formatting_roundtrip() -> None:
    assert format_money(parse_money("20000000")) == "20000000.00"
    assert format_money(parse_money("1500.5")) == "1500.50"
    assert parse_money("100000000.00") == 100000000.00  # type: ignore[comparison-overlap]


def test_money_rejects_more_than_two_decimals() -> None:
    with pytest.raises(ValidationError):
        LoanRequestCreateIn(type="loan", amount="100.999")


def test_money_rejects_negative_or_zero() -> None:
    with pytest.raises(ValidationError):
        LoanRequestCreateIn(type="loan", amount="0")
    with pytest.raises(ValidationError):
        LoanRequestCreateIn(type="loan", amount="-5")


def test_request_type_is_restricted() -> None:
    with pytest.raises(ValidationError):
        LoanRequestCreateIn(type="mortgage", amount="100")


def test_policy_year_bounds() -> None:
    base = {
        "workplace_id": uuid4(),
        "max_loan_amount": "100000000.00",
        "max_guarantee_amount": "50000000.00",
        "max_request_count_per_year": 3,
        "max_request_count_lifetime": 10,
    }
    with pytest.raises(ValidationError):
        LoanPolicyCreateIn(**base, year=1299)
    with pytest.raises(ValidationError):
        LoanPolicyCreateIn(**base, year=1501)
    ok = LoanPolicyCreateIn(**base, year=1405)
    assert ok.year == 1405


def test_policy_counts_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        LoanPolicyCreateIn(
            workplace_id=uuid4(),
            year=1405,
            max_loan_amount="1.00",
            max_guarantee_amount="1.00",
            max_request_count_per_year=-1,
            max_request_count_lifetime=5,
        )


def test_policy_update_requires_version() -> None:
    with pytest.raises(ValidationError):
        LoanPolicyUpdateIn(max_loan_amount="2.00")
    with pytest.raises(ValidationError):
        LoanPolicyUpdateIn(max_loan_amount="2.00", version=0)
    update = LoanPolicyUpdateIn(max_loan_amount="2.00", version=1, is_active=False)
    assert update.is_active is False


def test_retire_and_transition_require_version() -> None:
    with pytest.raises(ValidationError):
        LoanPolicyRetireIn()
    with pytest.raises(ValidationError):
        LoanRequestTransitionIn(version=0)
    assert LoanRequestTransitionIn(version=2).version == 2


def test_request_out_shape() -> None:
    out = LoanRequestOut(
        id=uuid4(),
        version=1,
        employee={"id": uuid4(), "name": "Ali Loaner", "name_fa": "علی وامخواه"},
        workplace={"id": uuid4(), "code": "CP1", "name": "Complex 1", "name_fa": "کمپلکس ۱"},
        type="loan",
        amount="20000000.00",
        year=1405,
        status="pending",
        settled_at=None,
        created_at="2026-09-01T10:00:00Z",
    )
    dumped = out.model_dump()
    assert dumped["type"] == "loan"
    assert dumped["amount"] == "20000000.00"
    assert dumped["status"] == "pending"
