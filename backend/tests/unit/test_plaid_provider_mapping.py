"""Unit tests for the pure mapping logic in PlaidProvider — no network
calls, no DB. Confirms Plaid's raw account shapes translate correctly
into this app's AccountType/balance-sign conventions.
"""
from decimal import Decimal

from app.domain.enums import AccountType
from app.providers.plaid_client import RawPlaidAccount
from app.providers.plaid_provider import _map_account_type, _map_balance


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
