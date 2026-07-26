"""seed default budget categories

Revision ID: e95b3a7d10f6
Revises: d817f0c2a9e4
Create Date: 2026-07-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e95b3a7d10f6"
down_revision: Union[str, Sequence[str], None] = "d817f0c2a9e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing users receive the same zero-dollar starting categories as new
    # registrations. ON CONFLICT keeps custom categories or a rerun intact.
    op.execute(
        """
        INSERT INTO budget_categories
          (id, user_id, name, group_name, monthly_limit, sort_order, active, created_at, updated_at)
        SELECT md5(users.id::text || defaults.name)::uuid, users.id, defaults.name, defaults.group_name, 0, defaults.sort_order, true, now(), now()
        FROM users
        CROSS JOIN (
          VALUES
            ('Drinks & Dining', 'Wants', 0),
            ('Groceries', 'Needs', 1),
            ('Transportation', 'Needs', 2),
            ('Housing', 'Needs', 3),
            ('Entertainment', 'Wants', 4),
            ('Travel', 'Wants', 5),
            ('Health', 'Needs', 6),
            ('Shopping', 'Wants', 7)
        ) AS defaults(name, group_name, sort_order)
        ON CONFLICT (user_id, name) DO NOTHING
        """
    )


def downgrade() -> None:
    # Do not delete categories on downgrade: after users edit limits or add
    # rules, the rows are user data and should remain recoverable.
    pass
