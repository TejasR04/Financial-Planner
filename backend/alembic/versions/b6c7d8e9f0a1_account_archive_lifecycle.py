"""preserve account archive intent and Plaid relationships

Revision ID: b6c7d8e9f0a1
Revises: d8b0c1d2e3f4
Create Date: 2026-08-29 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, None] = "d8b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("user_archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accounts", sa.Column("provider_archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_accounts_user_archived_at"), "accounts", ["user_archived_at"], unique=False)
    op.create_index(op.f("ix_accounts_provider_archived_at"), "accounts", ["provider_archived_at"], unique=False)

    # Before this migration there was one archive timestamp. Existing rows
    # with an intact institution relationship were retired by Plaid; rows with
    # no relationship were either manual archives or already-disconnected
    # Plaid accounts. Preserve that distinction for safe restore behavior.
    op.execute(
        """
        UPDATE accounts
        SET provider_archived_at = archived_at
        WHERE archived_at IS NOT NULL
          AND external_account_id IS NOT NULL
          AND institution_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE accounts
        SET user_archived_at = archived_at
        WHERE archived_at IS NOT NULL
          AND (external_account_id IS NULL OR institution_id IS NULL)
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_accounts_provider_archived_at"), table_name="accounts")
    op.drop_index(op.f("ix_accounts_user_archived_at"), table_name="accounts")
    op.drop_column("accounts", "provider_archived_at")
    op.drop_column("accounts", "user_archived_at")
