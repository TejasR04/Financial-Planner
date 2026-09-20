from decimal import Decimal

from app.ai.tools.recommendation_tools import (
    EstimateHomeAffordabilityInput,
    estimate_home_affordability,
)


def test_home_affordability_never_reports_negative_borrowing():
    result = estimate_home_affordability(EstimateHomeAffordabilityInput(
        gross_monthly_income=Decimal("2000"),
        existing_monthly_debt_payments=Decimal("650"),
        down_payment=Decimal("100000"),
    ))

    assert result["max_loan_amount"] == Decimal("0.00")
    assert result["unused_down_payment"] > 0
