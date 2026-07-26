"""seed investment value history

Revision ID: b4d5e6f7a8b9
Revises: a3c2d4e5f6a7
Create Date: 2026-07-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "a3c2d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Establish the honest first observation for accounts that existed before
    # history tracking. Later syncs overwrite the same day's value and add a
    # new point on subsequent days.
    op.execute(
        """
        INSERT INTO investment_value_snapshots (id, account_id, as_of, value)
        SELECT md5(accounts.id::text || CURRENT_DATE::text)::uuid, accounts.id, CURRENT_DATE, accounts.balance
        FROM accounts
        WHERE accounts.archived_at IS NULL
          AND accounts.type IN ('investment', 'retirement')
        ON CONFLICT (account_id, as_of) DO NOTHING
        """
    )


def downgrade() -> None:
    # Snapshots are financial history; retain the seeded baseline on downgrade.
    pass
