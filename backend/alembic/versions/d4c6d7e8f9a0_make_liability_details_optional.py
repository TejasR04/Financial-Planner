"""make liability details optional

Revision ID: d4c6d7e8f9a0
Revises: d3b5c6d7e8f9
"""
from alembic import op

revision = "d4c6d7e8f9a0"
down_revision = "d3b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("principal", "interest_rate", "term_months", "minimum_payment", "origination_date"):
        op.alter_column("liabilities", column, nullable=True)


def downgrade() -> None:
    # Rows with omitted details cannot safely be made non-null again without
    # inventing financial assumptions, so downgrade intentionally preserves
    # their optionality.
    pass
