"""allow user-defined display names for linked accounts

Revision ID: a8c0e1f2a3b4
Revises: d9e0f1a2b3c4
Create Date: 2026-08-08 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8c0e1f2a3b4"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("custom_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "custom_name")
