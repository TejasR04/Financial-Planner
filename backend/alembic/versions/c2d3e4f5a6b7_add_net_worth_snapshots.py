"""add observed daily net worth snapshots

Revision ID: c2d3e4f5a6b7
Revises: c1d2e3f4a5b6
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c2d3e4f5a6b7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "net_worth_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("assets", sa.Numeric(18, 2), nullable=False),
        sa.Column("liabilities", sa.Numeric(18, 2), nullable=False),
        sa.UniqueConstraint("user_id", "as_of", name="uq_net_worth_snapshots_user_date"),
    )
    op.create_index(op.f("ix_net_worth_snapshots_user_id"), "net_worth_snapshots", ["user_id"])
    op.create_index(op.f("ix_net_worth_snapshots_as_of"), "net_worth_snapshots", ["as_of"])


def downgrade() -> None:
    op.drop_index(op.f("ix_net_worth_snapshots_as_of"), table_name="net_worth_snapshots")
    op.drop_index(op.f("ix_net_worth_snapshots_user_id"), table_name="net_worth_snapshots")
    op.drop_table("net_worth_snapshots")
