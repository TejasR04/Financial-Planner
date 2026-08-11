"""remove generated flow categories and reset imported labels

Revision ID: d6f8a9b0c1d2
Revises: d5e7f8a9b0c1
"""
from alembic import op

revision = "d6f8a9b0c1d2"
down_revision = "d5e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE transactions
        SET budget_category_id = NULL
        WHERE budget_category_id IN (
          SELECT id FROM budget_categories
          WHERE lower(name) IN ('withdrawal', 'deposit', 'transfer')
        )
        """
    )
    op.execute("DELETE FROM budget_categories WHERE lower(name) IN ('withdrawal', 'deposit', 'transfer')")
    op.execute(
        """
        UPDATE transactions
        SET category = 'uncategorized'
        WHERE external_transaction_id IS NULL
          AND lower(category) IN ('withdrawal', 'deposit', 'transfer', 'money in', 'interest payment')
        """
    )


def downgrade() -> None:
    # The original provider labels and unintended generated categories cannot
    # be reconstructed reliably, so downgrade preserves the cleanup.
    pass
