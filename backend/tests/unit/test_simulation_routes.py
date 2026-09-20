from decimal import Decimal
from uuid import uuid4

from app.api.v1.routes.simulations import _debt_plan_paid_off
from app.domain.entities import Liability


def _liability(principal: Decimal) -> Liability:
    return Liability(
        id=uuid4(), account_id=uuid4(), principal=principal,
        interest_rate=Decimal("0.1"), term_months=12,
        minimum_payment=Decimal("25"), origination_date=None,
    )


def test_zero_balance_debt_is_already_paid_off():
    assert _debt_plan_paid_off([_liability(Decimal("0"))], []) is True


def test_positive_balance_still_requires_payoff_event():
    assert _debt_plan_paid_off([_liability(Decimal("100"))], []) is False
