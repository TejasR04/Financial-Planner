import pytest
from httpx import AsyncClient

from .conftest import register_and_authorize


@pytest.mark.asyncio
async def test_monte_carlo_contract_names_metric_and_discloses_model_limits(client: AsyncClient) -> None:
    headers = await register_and_authorize(client, "mc-contract@example.com")
    response = await client.post("/api/v1/simulations/monte-carlo", headers=headers, json={
        "current_age": 35, "starting_balance": "100000", "annual_contribution": "12000",
        "years": 30, "target_balance": "1000000", "trials": 100, "seed": 7,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success_metric"] == "target_attainment"
    assert body["model_version"] == "normal-iid-v2"
    assert body["percentile_method"] == "nearest-rank"
    assert "taxes" in body["exclusions"]


@pytest.mark.asyncio
async def test_monte_carlo_rejects_out_of_bounds_trials(client: AsyncClient) -> None:
    headers = await register_and_authorize(client, "mc-bounds@example.com")
    response = await client.post("/api/v1/simulations/monte-carlo", headers=headers, json={
        "current_age": 35, "starting_balance": "100000", "annual_contribution": "12000",
        "years": 30, "target_balance": "1000000", "trials": 99,
    })
    assert response.status_code == 422
