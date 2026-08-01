"""add explicit planning input targets

Revision ID: b8c9d0e1f2a3
Revises: a7f8e9d0c1b2
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7f8e9d0c1b2"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("planning_profiles", sa.Column("target_savings_rate", sa.Numeric(5, 4), nullable=True))
    op.add_column("planning_profiles", sa.Column("cash_reserve_target", sa.Numeric(18, 2), nullable=True))

def downgrade() -> None:
    op.drop_column("planning_profiles", "cash_reserve_target")
    op.drop_column("planning_profiles", "target_savings_rate")
