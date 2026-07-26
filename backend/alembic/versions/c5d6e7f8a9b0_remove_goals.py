"""remove goals

Revision ID: c5d6e7f8a9b0
Revises: b4d5e6f7a8b9
Create Date: 2026-07-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "b4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("goals")


def downgrade() -> None:
    pass
