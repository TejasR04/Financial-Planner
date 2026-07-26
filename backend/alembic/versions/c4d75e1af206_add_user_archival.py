"""add user archival

Revision ID: c4d75e1af206
Revises: e3b1c7d8f2a4, f47c2e95b134
Create Date: 2026-07-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d75e1af206"
down_revision: Union[str, Sequence[str], None] = (
    "e3b1c7d8f2a4",
    "f47c2e95b134",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_users_archived_at"), "users", ["archived_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_archived_at"), table_name="users")
    op.drop_column("users", "archived_at")
