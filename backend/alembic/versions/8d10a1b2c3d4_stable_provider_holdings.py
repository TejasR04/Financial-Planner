"""Preserve provider holding identity across refreshes.

Revision ID: 8d10a1b2c3d4
Revises: a0b1c2d3e4f5
"""
from alembic import op
import sqlalchemy as sa

revision = "8d10a1b2c3d4"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("holdings", sa.Column("provider_security_id", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_holdings_account_security", "holdings", ["account_id", "provider_security_id"])


def downgrade() -> None:
    op.drop_constraint("uq_holdings_account_security", "holdings", type_="unique")
    op.drop_column("holdings", "provider_security_id")
