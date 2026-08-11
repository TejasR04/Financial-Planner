"""allow transactions to be excluded from budgets

Revision ID: b9d1e2f3a4b5
Revises: a8c0e1f2a3b4
Create Date: 2026-08-08 18:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = "b9d1e2f3a4b5"
down_revision = "a8c0e1f2a3b4"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("transactions", sa.Column("ignored_from_budget", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("transactions", "ignored_from_budget", server_default=None)

def downgrade() -> None:
    op.drop_column("transactions", "ignored_from_budget")
