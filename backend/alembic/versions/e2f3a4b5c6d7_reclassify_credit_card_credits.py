"""Reclassify existing credit-card refunds and statement credits as expenses.

Revision ID: e2f3a4b5c6d7
Revises: c2d3e4f5a6b7
"""

from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve explicit type overrides. Positive card credits were classified
    # as income solely from their sign, inflating historical cash-flow income.
    op.execute("""
        UPDATE transactions AS t
        SET type = 'expense'
        FROM accounts AS a
        WHERE t.account_id = a.id
          AND a.type = 'credit'
          AND t.type = 'income'
          AND t.amount > 0
          AND t.external_transaction_id IS NOT NULL
          AND t.user_type_override IS NULL
          AND UPPER(COALESCE(t.provider_category, t.category)) NOT LIKE 'TRANSFER%'
    """)


def downgrade() -> None:
    # Prior type values cannot be distinguished from later user edits.
    pass
