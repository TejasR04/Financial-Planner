"""Store user-reported cash within investment accounts.

Revision ID: b0d1e2f3a4c5
Revises: a9c0d1e2f3b4
"""
from alembic import op
import sqlalchemy as sa

revision = "b0d1e2f3a4c5"
down_revision = "a9c0d1e2f3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("reported_cash_balance", sa.Numeric(18, 2), nullable=True))
    op.add_column("accounts", sa.Column("reported_cash_is_liquid", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("accounts", "reported_cash_is_liquid")
    op.drop_column("accounts", "reported_cash_balance")
