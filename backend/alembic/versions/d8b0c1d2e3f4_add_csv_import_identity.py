"""add CSV import identity

Revision ID: d8b0c1d2e3f4
Revises: d7a9b0c1d2e3
"""
from alembic import op
import sqlalchemy as sa

revision = "d8b0c1d2e3f4"
down_revision = "d7a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("import_fingerprint", sa.String(length=64), nullable=True))
    op.create_index(
        "uq_transactions_active_import_fingerprint",
        "transactions",
        ["import_fingerprint"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND import_fingerprint IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_active_import_fingerprint", table_name="transactions")
    op.drop_column("transactions", "import_fingerprint")
