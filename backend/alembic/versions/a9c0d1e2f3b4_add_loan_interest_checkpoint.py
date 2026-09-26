"""Track the last day interest was added to a manual loan balance.

Revision ID: a9c0d1e2f3b4
Revises: f8b9c0d1e2f3
"""
from alembic import op
import sqlalchemy as sa

revision = "a9c0d1e2f3b4"
down_revision = "f8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("liabilities", sa.Column("last_interest_accrual_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("liabilities", "last_interest_accrual_date")
