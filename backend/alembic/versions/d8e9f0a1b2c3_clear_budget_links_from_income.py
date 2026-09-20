"""clear legacy budget links from income

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""
from alembic import op

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Income is outside the expense budget. Older categorization flows could
    # leave an expense-category assignment behind after changing the type.
    op.execute("""
        UPDATE transactions
        SET budget_category_id = NULL, ignored_from_budget = false
        WHERE type = 'income' AND budget_category_id IS NOT NULL
    """)


def downgrade() -> None:
    # The old links were invalid under the current transaction rules and
    # cannot be reconstructed reliably.
    pass
