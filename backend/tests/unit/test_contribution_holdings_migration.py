import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest


MIGRATION = Path(__file__).resolve().parents[2] / "alembic/versions/f9c0d1e2f3a4_repair_contribution_holdings.py"
spec = importlib.util.spec_from_file_location("repair_contributions", MIGRATION)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class RepairConnection:
    def __init__(self, balance, value, contributed="250"):
        self.account_id = uuid4()
        self.balance = Decimal(balance)
        self.contributed = Decimal(contributed)
        self.applied = False
        self.rows = [] if value is None else [{
            "id": uuid4(), "account_id": self.account_id, "symbol": "VTI",
            "quantity": Decimal(value) / 100, "market_value": Decimal(value),
            "cost_basis": Decimal(value) - 200, "asset_class": "equity", "last_price": Decimal("100"),
            "pricing_mode": "automatic",
        }]
        self.snapshots = []
        self.queries = []

    def scalar(self, statement):
        return date(2026, 10, 5)

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.queries.append(sql)
        if "FROM accounts a" in sql:
            accounts = [] if self.applied else [{
                "id": self.account_id, "balance": self.balance, "contributed": self.contributed,
            }]
            return Mock(mappings=Mock(return_value=Mock(all=Mock(return_value=accounts))))
        if "FROM holdings WHERE account_id" in sql and "SELECT id" in sql:
            return Mock(mappings=Mock(return_value=self.rows))
        if "UPDATE holdings SET quantity = :quantity" in sql:
            self.rows[0].update(parameters)
        elif "INSERT INTO holdings" in sql:
            self.rows.append({"symbol": "CUR:USD", "market_value": parameters["amount"],
                              "quantity": parameters["amount"], "cost_basis": parameters["amount"]})
        elif "INSERT INTO holding_value_snapshots" in sql:
            assert set(statement.compile().params) == {"today", "account_id"}
            self.snapshots.append(sum(h["market_value"] for h in self.rows))
        elif "UPDATE investment_contribution_adjustments" in sql:
            self.applied = True
        else:
            raise AssertionError(sql)


@pytest.mark.parametrize("balance,value,expected", [
    ("1250", "1000", "1250"),
    ("1250", "1100", "1250"),  # A partial manual correction is not counted twice.
    ("1250", "1250", "1250"),
    ("1000", "1250", "1250"),  # Never shrink holdings to reconcile a negative gap.
    ("2000", "1000", "1250"),  # Unrelated unallocated balances are preserved.
    ("250", None, "250"),
])
def test_backfill_preserves_balances_and_repairs_each_ledger_only_once(balance, value, expected):
    connection = RepairConnection(balance, value)
    migration.repair(connection)
    assert sum(h["market_value"] for h in connection.rows) == Decimal(expected)
    assert connection.balance == Decimal(balance)
    after = [dict(h) for h in connection.rows]
    migration.repair(connection)
    assert connection.rows == after
    assert not any("UPDATE accounts" in query for query in connection.queries)
    query = connection.queries[0]
    assert "a.institution_id IS NULL" in query
    assert "a.external_account_id IS NULL" in query
    assert "NOT c.holdings_applied" in query


def test_backfill_increases_share_quantity_and_preserves_existing_gain():
    connection = RepairConnection("1250", "1000")
    migration.repair(connection)
    holding = connection.rows[0]
    assert holding["quantity"] == Decimal("12.5")
    assert holding["cost_basis"] == Decimal("1050")
    assert holding["market_value"] - holding["cost_basis"] == 200
    assert connection.snapshots == [Decimal("1250")]
