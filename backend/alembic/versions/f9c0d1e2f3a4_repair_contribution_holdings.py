"""Repair manual contributions that previously changed only account balances.

Revision ID: f9c0d1e2f3a4
Revises: e2f3a4b5c6d7
"""
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f9c0d1e2f3a4"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def repair(connection) -> None:
    # Use the recorded ledger, including removed rules, rather than replaying
    # schedules. A remaining value gap caps the repair if the user already
    # corrected some or all of the contributions by editing their holdings.
    accounts = connection.execute(sa.text("""
        SELECT a.id, a.balance,
               (SELECT SUM(c.amount) FROM investment_contribution_adjustments c
                WHERE c.account_id = a.id AND NOT c.holdings_applied) AS contributed
        FROM accounts a
        WHERE a.institution_id IS NULL AND a.external_account_id IS NULL
          AND a.type IN ('investment', 'retirement')
          AND EXISTS (SELECT 1 FROM investment_contribution_adjustments c
                      WHERE c.account_id = a.id AND NOT c.holdings_applied)
        ORDER BY a.id FOR UPDATE
    """)).mappings().all()
    today = connection.scalar(sa.text("SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date"))
    for account in accounts:
        holdings = [SimpleNamespace(**row) for row in connection.execute(sa.text("""
            SELECT id, account_id, symbol, quantity, cost_basis, market_value, asset_class, last_price, pricing_mode
            FROM holdings WHERE account_id = :account_id ORDER BY id FOR UPDATE
        """), {"account_id": account["id"]}).mappings()]
        amount = min(
            account["contributed"],
            max(Decimal("0"), account["balance"] - sum((h.market_value for h in holdings), Decimal("0"))),
        )
        if amount <= 0:
            continue
        positions = [h for h in holdings if h.market_value > 0 and (
            h.pricing_mode != "automatic" or h.quantity > 0 or (h.last_price is not None and h.last_price > 0)
        )]
        total = sum((h.market_value for h in positions), Decimal("0"))
        remaining = amount
        # Frozen allocation logic: future application changes must not change
        # the behavior of an already released data migration.
        for index, holding in enumerate(positions):
            added = remaining if index == len(positions) - 1 else (
                amount * holding.market_value / total
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            added = min(added, remaining)
            remaining -= added
            price = holding.last_price
            if price is None or price <= 0:
                price = holding.market_value / holding.quantity if holding.quantity > 0 else None
            if price is not None:
                holding.quantity += (added / price).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            if holding.cost_basis > 0 or holding.asset_class == "cash":
                holding.cost_basis += added
            holding.market_value += added
            connection.execute(sa.text("""
                UPDATE holdings SET quantity = :quantity, cost_basis = :cost_basis, market_value = :market_value
                WHERE id = :id
            """), vars(holding))
        if not positions:
            cash = next((h for h in holdings if h.symbol == "CUR:USD"), None)
            if cash:
                connection.execute(sa.text("""
                    UPDATE holdings SET quantity = quantity + :amount, cost_basis = cost_basis + :amount,
                        market_value = market_value + :amount, as_of = :today WHERE id = :id
                """), {"id": cash.id, "amount": amount, "today": today})
            else:
                connection.execute(sa.text("""
                    INSERT INTO holdings
                        (id, account_id, symbol, quantity, cost_basis, market_value, asset_class, as_of, pricing_mode)
                    VALUES (:id, :account_id, 'CUR:USD', :amount, :amount, :amount, 'cash', :today, 'manual')
                """), {"id": uuid4(), "account_id": account["id"], "amount": amount, "today": today})
        # Preserve observed past points; historical prices/allocation are unknown.
        connection.execute(sa.text("""
            INSERT INTO holding_value_snapshots (id, account_id, symbol, as_of, value)
            SELECT md5(account_id::text || upper(trim(symbol)) || CAST(:today AS text))::uuid,
                   account_id, upper(trim(symbol)), :today, SUM(market_value)
            FROM holdings WHERE account_id = :account_id
            GROUP BY account_id, upper(trim(symbol))
            ON CONFLICT (account_id, symbol, as_of) DO UPDATE SET value = EXCLUDED.value
        """), {"account_id": account["id"], "today": today})
    connection.execute(sa.text("UPDATE investment_contribution_adjustments SET holdings_applied = true"))


def upgrade() -> None:
    op.add_column("investment_contribution_adjustments", sa.Column(
        "holdings_applied", sa.Boolean(), nullable=False, server_default=sa.false()
    ))
    repair(op.get_bind())
    op.alter_column("investment_contribution_adjustments", "holdings_applied", server_default=sa.true())


def downgrade() -> None:
    # Preserve corrected user values; subsequent price updates/edits mean they
    # cannot safely be reversed when reverting the schema.
    op.drop_column("investment_contribution_adjustments", "holdings_applied")
