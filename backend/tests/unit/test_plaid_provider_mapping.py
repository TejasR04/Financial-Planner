"""Unit tests for the pure mapping logic in PlaidProvider — no network
calls, no DB. Confirms Plaid's raw account shapes translate correctly
into this app's AccountType/balance-sign conventions.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import ProviderError
from app.domain.enums import AccountType, AssetClass, TransactionStatus, TransactionType
from app.providers.plaid_client import (
    RawPlaidAccount,
    RawPlaidHolding,
    RawPlaidTransaction,
    _to_raw_transaction,
)
from app.providers.plaid_provider import (
    _map_account_type,
    _map_asset_class,
    _map_balance,
    _to_account_entity,
    _to_holding_entity,
    _to_transaction_entity,
)


def _raw(plaid_type: str, plaid_subtype: str | None, current_balance: Decimal | None) -> RawPlaidAccount:
    return RawPlaidAccount(
        external_account_id="acc-1",
        name="Test Account",
        official_name=None,
        plaid_type=plaid_type,
        plaid_subtype=plaid_subtype,
        mask="1234",
        currency="USD",
        current_balance=current_balance,
        available_balance=None,
    )


def test_depository_maps_to_depository():
    raw = _raw("depository", "checking", Decimal("1500.00"))
    assert _map_account_type(raw) == AccountType.DEPOSITORY


def test_401k_subtype_maps_to_retirement_even_though_investment_type():
    raw = _raw("investment", "401k", Decimal("50000.00"))
    assert _map_account_type(raw) == AccountType.RETIREMENT


def test_plain_investment_maps_to_investment():
    raw = _raw("investment", "brokerage", Decimal("20000.00"))
    assert _map_account_type(raw) == AccountType.INVESTMENT


def test_credit_balance_is_flipped_negative():
    raw = _raw("credit", "credit card", Decimal("2500.00"))
    account_type = _map_account_type(raw)
    assert account_type == AccountType.CREDIT
    assert _map_balance(raw, account_type) == Decimal("-2500.00")


def test_mortgage_subtype_maps_to_loan_and_flips_sign():
    raw = _raw("loan", "mortgage", Decimal("310000.00"))
    account_type = _map_account_type(raw)
    assert account_type == AccountType.LOAN
    assert _map_balance(raw, account_type) == Decimal("-310000.00")


def test_asset_balance_is_not_flipped():
    raw = _raw("depository", "savings", Decimal("8000.00"))
    account_type = _map_account_type(raw)
    assert _map_balance(raw, account_type) == Decimal("8000.00")


def test_missing_balance_defaults_to_zero():
    raw = _raw("depository", "checking", None)
    account_type = _map_account_type(raw)
    assert _map_balance(raw, account_type) == Decimal("0")


def test_non_usd_account_is_rejected():
    raw = _raw("depository", "checking", Decimal("1500.00"))
    raw.currency = "CAD"

    with pytest.raises(ProviderError, match="U.S. dollar"):
        _to_account_entity(uuid4(), uuid4(), raw)


def test_plaid_outflow_amount_is_inverted_for_normalized_cash_flow():
    raw = _to_raw_transaction(
        SimpleNamespace(
            transaction_id="transaction-1",
            account_id="account-1",
            date=date(2026, 7, 25),
            merchant_name=None,
            name="Payroll",
            personal_finance_category=SimpleNamespace(primary="INCOME_WAGES"),
            amount=-2500.00,
            pending=False,
        )
    )
    assert raw.amount == Decimal("2500.0")


def test_positive_normalized_amount_is_income():
    transaction = _to_transaction_entity(
        RawPlaidTransaction(
            external_transaction_id="transaction-1",
            external_account_id="account-1",
            posted_at=date(2026, 7, 25),
            merchant="Payroll",
            category="INCOME_WAGES",
            amount=Decimal("2500.00"),
            pending=False,
        ),
        uuid4(),
    )
    assert transaction.amount == Decimal("2500.00")
    assert transaction.type == TransactionType.INCOME
    assert transaction.status == TransactionStatus.CLEARED


def test_transfer_category_is_not_misclassified_as_income():
    transaction = _to_transaction_entity(
        RawPlaidTransaction(
            external_transaction_id="transaction-2",
            external_account_id="account-1",
            posted_at=date(2026, 7, 25),
            merchant="Brokerage transfer",
            category="TRANSFER_IN_ACCOUNT_TRANSFER",
            amount=Decimal("100.00"),
            pending=True,
        ),
        uuid4(),
    )
    assert transaction.type == TransactionType.TRANSFER
    assert transaction.status == TransactionStatus.PENDING


def test_etf_holding_maps_to_equity():
    raw = RawPlaidHolding(
        external_account_id="account-1",
        symbol="VTI",
        quantity=Decimal("10"),
        cost_basis=Decimal("2000"),
        market_value=Decimal("2500"),
        security_type="etf",
        is_cash_equivalent=False,
        as_of=date(2026, 7, 25),
    )
    holding = _to_holding_entity(raw, uuid4())
    assert _map_asset_class(raw) == AssetClass.EQUITY
    assert holding.asset_class == AssetClass.EQUITY
