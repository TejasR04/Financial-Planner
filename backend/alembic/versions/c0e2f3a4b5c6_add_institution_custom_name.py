"""add user-owned display names for institutions

Revision ID: c0e2f3a4b5c6
Revises: b9d1e2f3a4b5
Create Date: 2026-08-09 22:45:00
"""
from alembic import op
import sqlalchemy as sa


revision = "c0e2f3a4b5c6"
down_revision = "b9d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "institutions",
        sa.Column("custom_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("institutions", "custom_name")
