"""add automatic holding pricing

Revision ID: f7a8b9c0d1e2
Revises: e1f2a3b4c5d6
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a8b9c0d1e2"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "holdings",
        sa.Column("pricing_mode", sa.String(length=20), server_default="manual", nullable=False),
    )
    op.add_column(
        "holdings",
        sa.Column("last_price", sa.Numeric(precision=18, scale=6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("holdings", "last_price")
    op.drop_column("holdings", "pricing_mode")
