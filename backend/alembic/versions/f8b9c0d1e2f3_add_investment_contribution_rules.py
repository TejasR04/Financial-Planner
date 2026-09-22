"""add recurring manual investment contributions

Revision ID: f8b9c0d1e2f3
Revises: f7a8b9c0d1e2
"""
from alembic import op
import sqlalchemy as sa

revision = "f8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investment_contribution_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=False),
        sa.Column("next_run_date", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_investment_contribution_amount_positive"),
        sa.CheckConstraint("day_of_month BETWEEN 1 AND 31", name="ck_investment_contribution_day"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investment_contribution_rules_account_id", "investment_contribution_rules", ["account_id"]
    )
    op.create_index(
        "ix_investment_contribution_rules_next_run_date", "investment_contribution_rules", ["next_run_date"]
    )
    op.create_table(
        "investment_contribution_adjustments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["investment_contribution_rules.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "scheduled_for", name="uq_investment_contribution_rule_date"),
    )
    op.create_index(
        "ix_investment_contribution_adjustments_rule_id",
        "investment_contribution_adjustments",
        ["rule_id"],
    )
    op.create_index(
        "ix_investment_contribution_adjustments_account_id",
        "investment_contribution_adjustments",
        ["account_id"],
    )
    op.create_index(
        "ix_investment_contribution_adjustments_scheduled_for",
        "investment_contribution_adjustments",
        ["scheduled_for"],
    )


def downgrade() -> None:
    op.drop_table("investment_contribution_adjustments")
    op.drop_table("investment_contribution_rules")
