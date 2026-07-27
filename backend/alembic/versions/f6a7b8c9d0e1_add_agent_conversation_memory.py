"""add agent conversation memory

Revision ID: f6a7b8c9d0e1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-27 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_messages_user_id"), "agent_messages", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_agent_messages_created_at"), "agent_messages", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_messages_created_at"), table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_user_id"), table_name="agent_messages")
    op.drop_table("agent_messages")
