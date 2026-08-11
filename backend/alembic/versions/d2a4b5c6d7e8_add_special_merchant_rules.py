"""allow merchant rules for income and transfers

Revision ID: d2a4b5c6d7e8
Revises: d1f3a4b5c6d7
"""
from alembic import op
import sqlalchemy as sa

revision = "d2a4b5c6d7e8"
down_revision = "d1f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("merchant_budget_rules", "budget_category_id", existing_type=sa.UUID(), nullable=True)
    op.add_column("merchant_budget_rules", sa.Column("transaction_type", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_merchant_rule_one_treatment",
        "merchant_budget_rules",
        "(budget_category_id IS NOT NULL AND transaction_type IS NULL) OR "
        "(budget_category_id IS NULL AND transaction_type IN ('income', 'transfer'))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_merchant_rule_one_treatment", "merchant_budget_rules", type_="check")
    op.drop_column("merchant_budget_rules", "transaction_type")
    op.alter_column("merchant_budget_rules", "budget_category_id", existing_type=sa.UUID(), nullable=False)
