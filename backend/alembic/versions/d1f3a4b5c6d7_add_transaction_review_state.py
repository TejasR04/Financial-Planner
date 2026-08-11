"""add transaction review state

Revision ID: d1f3a4b5c6d7
Revises: c0e2f3a4b5c6
"""
from alembic import op
import sqlalchemy as sa

revision = "d1f3a4b5c6d7"
down_revision = "c0e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_transactions_reviewed_at", "transactions", ["reviewed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_transactions_reviewed_at", table_name="transactions")
    op.drop_column("transactions", "reviewed_at")
