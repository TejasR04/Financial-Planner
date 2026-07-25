"""plaid_transaction_identity

Revision ID: e3b1c7d8f2a4
Revises: 8d1776d4438a
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e3b1c7d8f2a4"
down_revision: Union[str, None] = "8d1776d4438a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_transactions_external_transaction_id",
        "transactions",
        ["external_transaction_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_transactions_external_transaction_id", "transactions", type_="unique")
