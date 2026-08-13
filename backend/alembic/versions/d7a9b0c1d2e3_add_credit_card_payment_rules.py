"""allow credit card payment merchant rules

Revision ID: d7a9b0c1d2e3
Revises: d6f8a9b0c1d2
"""
from alembic import op

revision = "d7a9b0c1d2e3"
down_revision = "d6f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_merchant_rule_one_treatment", "merchant_budget_rules", type_="check")
    op.create_check_constraint(
        "ck_merchant_rule_one_treatment",
        "merchant_budget_rules",
        "(budget_category_id IS NOT NULL AND transaction_type IS NULL) OR "
        "(budget_category_id IS NULL AND transaction_type IN ('income', 'transfer', 'credit_card_payment'))",
    )
    # Existing Plaid credit-card payments were previously stored as generic
    # transfers. Promote only rows with the detailed provider category.
    op.execute(
        "UPDATE transactions SET type = 'credit_card_payment' "
        "WHERE type = 'transfer' AND upper(category) = 'LOAN_PAYMENTS_CREDIT_CARD_PAYMENT'"
    )


def downgrade() -> None:
    op.execute("UPDATE transactions SET type = 'transfer' WHERE type = 'credit_card_payment'")
    op.drop_constraint("ck_merchant_rule_one_treatment", "merchant_budget_rules", type_="check")
    op.create_check_constraint(
        "ck_merchant_rule_one_treatment",
        "merchant_budget_rules",
        "(budget_category_id IS NOT NULL AND transaction_type IS NULL) OR "
        "(budget_category_id IS NULL AND transaction_type IN ('income', 'transfer'))",
    )
