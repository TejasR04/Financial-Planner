"""budget categories and merchant rules

Revision ID: d817f0c2a9e4
Revises: c4d75e1af206
Create Date: 2026-07-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d817f0c2a9e4"
down_revision: Union[str, Sequence[str], None] = "c4d75e1af206"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "budget_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("group_name", sa.String(length=100), nullable=False, server_default="Other"),
        sa.Column("monthly_limit", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_budget_categories_user_name"),
    )
    op.create_index(op.f("ix_budget_categories_user_id"), "budget_categories", ["user_id"], unique=False)
    op.create_table(
        "merchant_budget_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "budget_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("budget_categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("merchant_pattern", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "merchant_pattern", name="uq_merchant_budget_rules_user_pattern"),
    )
    op.create_index(op.f("ix_merchant_budget_rules_user_id"), "merchant_budget_rules", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_merchant_budget_rules_budget_category_id"),
        "merchant_budget_rules",
        ["budget_category_id"],
        unique=False,
    )
    op.add_column(
        "transactions",
        sa.Column("budget_category_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_transactions_budget_category_id_budget_categories",
        "transactions",
        "budget_categories",
        ["budget_category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_transactions_budget_category_id"), "transactions", ["budget_category_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_transactions_budget_category_id"), table_name="transactions")
    op.drop_constraint("fk_transactions_budget_category_id_budget_categories", "transactions", type_="foreignkey")
    op.drop_column("transactions", "budget_category_id")
    op.drop_index(op.f("ix_merchant_budget_rules_budget_category_id"), table_name="merchant_budget_rules")
    op.drop_index(op.f("ix_merchant_budget_rules_user_id"), table_name="merchant_budget_rules")
    op.drop_table("merchant_budget_rules")
    op.drop_index(op.f("ix_budget_categories_user_id"), table_name="budget_categories")
    op.drop_table("budget_categories")
