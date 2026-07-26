"""add investment value snapshots

Revision ID: a3c2d4e5f6a7
Revises: e95b3a7d10f6
Create Date: 2026-07-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a3c2d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "e95b3a7d10f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investment_value_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.UniqueConstraint("account_id", "as_of", name="uq_investment_value_snapshots_account_date"),
    )
    op.create_index(op.f("ix_investment_value_snapshots_account_id"), "investment_value_snapshots", ["account_id"])
    op.create_index(op.f("ix_investment_value_snapshots_as_of"), "investment_value_snapshots", ["as_of"])


def downgrade() -> None:
    op.drop_index(op.f("ix_investment_value_snapshots_as_of"), table_name="investment_value_snapshots")
    op.drop_index(op.f("ix_investment_value_snapshots_account_id"), table_name="investment_value_snapshots")
    op.drop_table("investment_value_snapshots")
