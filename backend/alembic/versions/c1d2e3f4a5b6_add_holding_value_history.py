"""add daily per holding observed value history

Revision ID: c1d2e3f4a5b6
Revises: b0d1e2f3a4c5
Create Date: 2026-09-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b0d1e2f3a4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "holding_value_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(18, 2), nullable=False),
        sa.UniqueConstraint("account_id", "symbol", "as_of", name="uq_holding_value_snapshots_account_symbol_date"),
    )
    op.create_index(op.f("ix_holding_value_snapshots_account_id"), "holding_value_snapshots", ["account_id"])
    op.create_index(op.f("ix_holding_value_snapshots_as_of"), "holding_value_snapshots", ["as_of"])
    # Start at the migration date. Existing account totals cannot be decomposed
    # into accurate historical position values, so no synthetic earlier points.
    op.execute("""
        INSERT INTO holding_value_snapshots (id, account_id, symbol, as_of, value)
        SELECT md5(accounts.id::text || upper(trim(holdings.symbol)) || CURRENT_DATE::text)::uuid,
               accounts.id, upper(trim(holdings.symbol)), CURRENT_DATE, sum(holdings.market_value)
        FROM holdings JOIN accounts ON accounts.id = holdings.account_id
        WHERE accounts.archived_at IS NULL
          AND accounts.type IN ('investment', 'retirement')
        GROUP BY accounts.id, upper(trim(holdings.symbol))
        ON CONFLICT (account_id, symbol, as_of) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index(op.f("ix_holding_value_snapshots_as_of"), table_name="holding_value_snapshots")
    op.drop_index(op.f("ix_holding_value_snapshots_account_id"), table_name="holding_value_snapshots")
    op.drop_table("holding_value_snapshots")
