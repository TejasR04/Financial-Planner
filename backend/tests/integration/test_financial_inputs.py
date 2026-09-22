from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient

from .conftest import register_and_authorize
from app.services.activity_history import shift_month


@pytest.mark.asyncio
async def test_income_sources_are_owned_and_do_not_change_account_balances(client: AsyncClient) -> None:
    owner = await register_and_authorize(client, "inputs-owner@example.com")
    other = await register_and_authorize(client, "inputs-other@example.com")
    account = await client.post("/api/v1/accounts", headers=owner, json={"name": "Checking", "type": "depository", "balance": "1000"})
    source = await client.post("/api/v1/income-sources", headers=owner, json={"name": "Salary", "annual_amount": "100000"})
    assert source.status_code == 201
    assert (await client.patch(f"/api/v1/income-sources/{source.json()['id']}", headers=other, json={"annual_amount": "1"})).status_code == 404
    accounts = await client.get("/api/v1/accounts", headers=owner)
    assert Decimal(accounts.json()["data"][0]["balance"]) == Decimal(account.json()["balance"])


@pytest.mark.asyncio
async def test_liability_terms_and_manual_holdings_follow_source_rules(client: AsyncClient) -> None:
    headers = await register_and_authorize(client, "source-rules@example.com")
    loan = await client.post("/api/v1/accounts", headers=headers, json={"name": "Loan", "type": "loan", "balance": "10000"})
    details = await client.put(f"/api/v1/accounts/{loan.json()['id']}/liability", headers=headers, json={"principal": "12000", "interest_rate": "0.07", "term_months": 60, "minimum_payment": "250", "origination_date": date.today().isoformat()})
    assert details.status_code == 200
    investment = await client.post("/api/v1/accounts", headers=headers, json={"name": "Brokerage", "type": "investment", "balance": "5000"})
    holding = await client.post(f"/api/v1/accounts/{investment.json()['id']}/holdings", headers=headers, json={"symbol": "VTI", "quantity": "10", "cost_basis": "4000", "market_value": "5000", "asset_class": "equity", "as_of": date.today().isoformat()})
    assert holding.status_code == 201
    accounts = await client.get("/api/v1/accounts", headers=headers)
    brokerage = next(row for row in accounts.json()["data"] if row["id"] == investment.json()["id"])
    assert brokerage["balance"] == "5000.00"

    payoff = await client.post("/api/v1/simulations/debt-optimization", headers=headers, json={"account_ids": [loan.json()["id"]], "extra_monthly_payment": "100", "strategy": "avalanche"})
    assert payoff.status_code == 200, payoff.text
    assert payoff.json()["payoff_order"] == ["Loan"]


@pytest.mark.asyncio
async def test_cash_flow_outlook_uses_saved_income_and_completed_month_expenses(client: AsyncClient) -> None:
    headers = await register_and_authorize(client, "outlook@example.com")
    account = await client.post("/api/v1/accounts", headers=headers, json={"name": "Checking", "type": "depository", "balance": "1000"})
    await client.post("/api/v1/income-sources", headers=headers, json={"name": "Take-home pay", "annual_amount": "60000", "growth_rate": "0"})
    await client.post("/api/v1/transactions", headers=headers, json={"account_id": account.json()["id"], "posted_at": date.today().isoformat(), "merchant": "Rent", "category": "housing", "amount": "-3000", "type": "expense"})
    partial = await client.post("/api/v1/simulations/cash-flow", headers=headers, json={"months": 12})
    assert partial.status_code == 422
    # Three completed months, including an observed zero-activity month.
    for offset, amount in [(-3, "-3000"), (-1, "-6000")]:
        await client.post("/api/v1/transactions", headers=headers, json={"account_id": account.json()["id"], "posted_at": shift_month(date.today(), offset).isoformat(), "merchant": "Rent", "category": "housing", "amount": amount, "type": "expense"})
    outlook = await client.post("/api/v1/simulations/cash-flow", headers=headers, json={"months": 12})
    assert outlook.status_code == 200, outlook.text
    assert outlook.json()["series"][0]["income"] == "5000.00"
    assert outlook.json()["series"][0]["expenses"] == "3000.00"
    assert "3 completed months" in outlook.json()["expense_source"]
    summary = await client.get(f"/api/v1/budgets/summary?month={date.today().replace(day=1).isoformat()}", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["average_month_count"] == 3
    assert summary.json()["average_daily_spending"][-1] == "3000.00"


@pytest.mark.asyncio
async def test_manual_transaction_fields_can_be_corrected(client: AsyncClient) -> None:
    headers = await register_and_authorize(client, "transaction-edit@example.com")
    account = await client.post("/api/v1/accounts", headers=headers, json={"name": "Manual", "type": "depository", "balance": "0"})
    row = await client.post("/api/v1/transactions", headers=headers, json={"account_id": account.json()["id"], "posted_at": date.today().isoformat(), "merchant": "Typo", "category": "other", "amount": "-10", "type": "expense"})
    edited = await client.patch(f"/api/v1/transactions/{row.json()['id']}", headers=headers, json={"merchant": "Corrected", "amount": "-12", "type": "expense"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["merchant"] == "Corrected"
    assert Decimal(edited.json()["amount"]) == Decimal("-12.00")
