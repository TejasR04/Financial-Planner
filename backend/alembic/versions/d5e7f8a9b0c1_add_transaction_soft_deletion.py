"""add persistent transaction soft deletion

Revision ID: d5e7f8a9b0c1
Revises: d4c6d7e8f9a0
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e7f8a9b0c1"
down_revision = "d4c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_transactions_deleted_at", "transactions", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_transactions_deleted_at", table_name="transactions")
    op.drop_column("transactions", "deleted_at")
