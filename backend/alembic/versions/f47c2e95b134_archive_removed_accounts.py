"""archive removed Plaid accounts

Revision ID: f47c2e95b134
Revises: 8d1776d4438a
Create Date: 2026-07-25 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f47c2e95b134"
down_revision: Union[str, None] = "8d1776d4438a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_accounts_archived_at"), "accounts", ["archived_at"], unique=False)
    # The UI has always rendered balances as USD and liabilities as negative
    # net-worth components. Normalize legacy metadata and manually-entered
    # positive debt balances to that single product convention.
    op.execute("UPDATE users SET base_currency = 'USD' WHERE base_currency <> 'USD'")
    op.execute("UPDATE accounts SET currency = 'USD' WHERE currency <> 'USD'")
    op.execute("UPDATE accounts SET balance = -balance WHERE type IN ('credit', 'loan') AND balance > 0")


def downgrade() -> None:
    op.drop_index(op.f("ix_accounts_archived_at"), table_name="accounts")
    op.drop_column("accounts", "archived_at")
