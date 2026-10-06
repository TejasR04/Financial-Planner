"""Repair Bilt housing card legs that counted rent twice.

Revision ID: a0b1c2d3e4f5
Revises: f9c0d1e2f3a4
"""
from alembic import op

revision = "a0b1c2d3e4f5"
down_revision = "f9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve explicit type choices and all amounts, category assignments,
    # review state and bank withdrawals. Only fix the misclassified card leg.
    op.execute("""
        UPDATE transactions AS t
        SET type = 'credit_card_payment'
        FROM accounts AS a
        WHERE a.id = t.account_id AND a.type = 'credit'
          AND t.external_transaction_id IS NOT NULL
          AND t.user_type_override IS NULL
          AND t.deleted_at IS NULL
          AND upper(trim(t.merchant)) = 'BILT HOUSING PAYMENT'
          AND t.type IN ('expense', 'transfer', 'income')
    """)


def downgrade() -> None:
    # Provider classification repairs cannot reconstruct the old incorrect types.
    pass
