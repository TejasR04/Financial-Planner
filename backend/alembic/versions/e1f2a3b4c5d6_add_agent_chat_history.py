"""add agent chat history

Revision ID: e1f2a3b4c5d6
Revises: d8e9f0a1b2c3
"""
from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e1f2a3b4c5d6"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_conversations_user_id"), "agent_conversations", ["user_id"]
    )
    op.create_index(
        op.f("ix_agent_conversations_updated_at"), "agent_conversations", ["updated_at"]
    )
    op.add_column(
        "agent_messages",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    connection = op.get_bind()
    legacy_users = connection.execute(
        sa.text(
            """
            SELECT messages.user_id,
                   MIN(messages.created_at) AS created_at,
                   MAX(messages.created_at) AS updated_at,
                   (
                       SELECT first_message.content
                       FROM agent_messages AS first_message
                       WHERE first_message.user_id = messages.user_id
                         AND first_message.role = 'user'
                       ORDER BY first_message.created_at ASC
                       LIMIT 1
                   ) AS first_user_message
            FROM agent_messages AS messages
            GROUP BY messages.user_id
            """
        )
    ).mappings()
    for legacy in legacy_users:
        conversation_id = uuid.uuid4()
        created_at = legacy["created_at"] or datetime.now(timezone.utc)
        updated_at = legacy["updated_at"] or created_at
        connection.execute(
            sa.text(
                """
                INSERT INTO agent_conversations (id, user_id, title, created_at, updated_at)
                VALUES (:id, :user_id, :title, :created_at, :updated_at)
                """
            ),
            {
                "id": conversation_id,
                "user_id": legacy["user_id"],
                "title": (
                    " ".join((legacy["first_user_message"] or "Previous chat").split())[:120]
                ),
                "created_at": created_at,
                "updated_at": updated_at,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE agent_messages SET conversation_id = :conversation_id WHERE user_id = :user_id"
            ),
            {"conversation_id": conversation_id, "user_id": legacy["user_id"]},
        )

    op.alter_column("agent_messages", "conversation_id", nullable=False)
    op.create_foreign_key(
        "fk_agent_messages_conversation_id",
        "agent_messages",
        "agent_conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_agent_messages_conversation_id"),
        "agent_messages",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_messages_conversation_id"), table_name="agent_messages")
    op.drop_constraint(
        "fk_agent_messages_conversation_id", "agent_messages", type_="foreignkey"
    )
    op.drop_column("agent_messages", "conversation_id")
    op.drop_index(op.f("ix_agent_conversations_updated_at"), table_name="agent_conversations")
    op.drop_index(op.f("ix_agent_conversations_user_id"), table_name="agent_conversations")
    op.drop_table("agent_conversations")
