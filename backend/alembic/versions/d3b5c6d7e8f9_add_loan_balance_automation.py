"""add manual loan balance automation

Revision ID: d3b5c6d7e8f9
Revises: d2a4b5c6d7e8
"""
from alembic import op
import sqlalchemy as sa

revision = "d3b5c6d7e8f9"
down_revision = "d2a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loan_balance_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("frequency", sa.String(length=20), nullable=True),
        sa.Column("next_run_date", sa.Date(), nullable=True),
        sa.Column("merchant_pattern", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(mode = 'scheduled' AND amount > 0 AND frequency IN ('once', 'monthly') AND next_run_date IS NOT NULL AND merchant_pattern IS NULL) OR "
            "(mode = 'merchant' AND amount IS NULL AND frequency IS NULL AND next_run_date IS NULL AND merchant_pattern IS NOT NULL)",
            name="ck_loan_balance_rule_configuration",
        ),
    )
    op.create_index("ix_loan_balance_rules_account_id", "loan_balance_rules", ["account_id"])
    op.create_index("ix_loan_balance_rules_next_run_date", "loan_balance_rules", ["next_run_date"])
    op.create_table(
        "loan_balance_adjustments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=True),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("amount_applied", sa.Numeric(18, 2), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["loan_balance_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "event_key", name="uq_loan_balance_adjustments_rule_event"),
    )
    op.create_index("ix_loan_balance_adjustments_rule_id", "loan_balance_adjustments", ["rule_id"])


def downgrade() -> None:
    op.drop_table("loan_balance_adjustments")
    op.drop_table("loan_balance_rules")
