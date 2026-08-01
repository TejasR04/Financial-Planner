import pytest
from httpx import AsyncClient

from tests.integration.conftest import register_and_authorize


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=201", "offset=-1"],
)
async def test_transaction_pagination_rejects_invalid_bounds(
    client: AsyncClient, query: str
) -> None:
    headers = await register_and_authorize(
        client, email=f"pagination-{query.replace('=', '-')}@example.com"
    )

    response = await client.get(f"/api/v1/transactions?{query}", headers=headers)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_budget_category_rename_is_case_insensitively_unique(
    client: AsyncClient,
) -> None:
    headers = await register_and_authorize(client, email="category-rename@example.com")
    first = await client.post(
        "/api/v1/budgets/categories",
        headers=headers,
        json={"name": "Alpha", "group_name": "Other", "monthly_limit": "0"},
    )
    second = await client.post(
        "/api/v1/budgets/categories",
        headers=headers,
        json={"name": "Beta", "group_name": "Other", "monthly_limit": "0"},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    renamed = await client.patch(
        f"/api/v1/budgets/categories/{second.json()['id']}",
        headers=headers,
        json={"name": "ALPHA"},
    )

    assert renamed.status_code == 409
