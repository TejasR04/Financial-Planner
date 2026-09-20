from pydantic import ValidationError
import pytest

from app.ai.tools.forecast_tools import EarliestRetirementAgeInput, ForecastRetirementInput
from app.ai.tools.scenario_tools import RunMonteCarloInput


@pytest.mark.parametrize(
    ("model", "values"),
    [
        (ForecastRetirementInput, {
            "current_age": 35, "retirement_age": 65,
            "current_retirement_balance": 1000, "annual_contribution": -1,
        }),
        (EarliestRetirementAgeInput, {
            "current_age": 35, "current_retirement_balance": 1000,
            "annual_contribution": -1, "annual_spending_target": 40000,
        }),
        (RunMonteCarloInput, {
            "starting_balance": 1000, "annual_contribution": -1,
            "years": 10, "current_age": 35, "target_balance": 10000,
        }),
    ],
)
def test_ai_projection_tools_reject_negative_contributions(model, values):
    with pytest.raises(ValidationError):
        model(**values)
