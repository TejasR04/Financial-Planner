"""preserve transaction overrides and loan adjustment history

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("transactions", "import_fingerprint", type_=sa.String(80), existing_type=sa.String(64))
    op.add_column("transactions", sa.Column("provider_category", sa.String(100), nullable=True))
    op.add_column("transactions", sa.Column("provider_type", sa.String(20), nullable=True))
    op.add_column("transactions", sa.Column("user_category_override", sa.String(100), nullable=True))
    op.add_column("transactions", sa.Column("user_type_override", sa.String(20), nullable=True))
    op.execute("UPDATE transactions SET provider_category = category, provider_type = type WHERE external_transaction_id IS NOT NULL")
    op.execute("""
        UPDATE transactions SET user_category_override = category, user_type_override = type
        WHERE external_transaction_id IS NOT NULL AND reviewed_at IS NOT NULL
    """)

    op.add_column("loan_balance_rules", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("loan_balance_adjustments", sa.Column("account_id", sa.UUID(), nullable=True))
    op.add_column("loan_balance_adjustments", sa.Column("source_amount", sa.Numeric(18, 2), nullable=True))
    op.add_column("loan_balance_adjustments", sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("loan_balance_adjustments", sa.Column("reversal_reason", sa.String(100), nullable=True))
    op.execute("""
        UPDATE loan_balance_adjustments a SET account_id = r.account_id
        FROM loan_balance_rules r WHERE r.id = a.rule_id
    """)
    op.execute("""
        UPDATE loan_balance_adjustments a SET source_amount = COALESCE(abs(t.amount), a.amount_applied)
        FROM transactions t WHERE t.id = a.transaction_id
    """)
    op.execute("UPDATE loan_balance_adjustments SET source_amount = amount_applied WHERE source_amount IS NULL")
    op.alter_column("loan_balance_adjustments", "account_id", nullable=False)
    op.alter_column("loan_balance_adjustments", "source_amount", nullable=False)
    op.create_foreign_key("fk_loan_adjustments_account", "loan_balance_adjustments", "accounts", ["account_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_loan_balance_adjustments_account_id", "loan_balance_adjustments", ["account_id"])
    op.drop_constraint("uq_loan_balance_adjustments_rule_event", "loan_balance_adjustments", type_="unique")
    # Keep the earliest application when old overlapping rules hit one loan/payment.
    op.execute("""
        WITH ranked AS (
          SELECT id, account_id, amount_applied,
                 row_number() OVER (PARTITION BY account_id, transaction_id ORDER BY applied_at, id) AS rn
          FROM loan_balance_adjustments WHERE transaction_id IS NOT NULL
        ), restored AS (
          SELECT account_id, sum(amount_applied) AS amount FROM ranked WHERE rn > 1 GROUP BY account_id
        )
        UPDATE accounts SET balance = accounts.balance - restored.amount FROM restored WHERE accounts.id = restored.account_id
    """)
    op.execute("""
        WITH ranked AS (
          SELECT id, row_number() OVER (PARTITION BY account_id, transaction_id ORDER BY applied_at, id) AS rn
          FROM loan_balance_adjustments WHERE transaction_id IS NOT NULL
        )
        UPDATE loan_balance_adjustments SET reversed_at = now(), reversal_reason = 'migrated_rule_overlap'
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
    """)
    op.create_index(
        "uq_loan_adjustments_active_account_transaction",
        "loan_balance_adjustments", ["account_id", "transaction_id"], unique=True,
        postgresql_where=sa.text("transaction_id IS NOT NULL AND reversed_at IS NULL"),
    )
    op.create_index(
        "uq_loan_adjustments_active_scheduled_event",
        "loan_balance_adjustments", ["rule_id", "event_key"], unique=True,
        postgresql_where=sa.text("transaction_id IS NULL AND reversed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_loan_adjustments_active_scheduled_event", table_name="loan_balance_adjustments")
    op.drop_index("uq_loan_adjustments_active_account_transaction", table_name="loan_balance_adjustments")
    op.execute("DELETE FROM loan_balance_adjustments WHERE reversed_at IS NOT NULL")
    op.create_unique_constraint("uq_loan_balance_adjustments_rule_event", "loan_balance_adjustments", ["rule_id", "event_key"])
    op.drop_index("ix_loan_balance_adjustments_account_id", table_name="loan_balance_adjustments")
    op.drop_constraint("fk_loan_adjustments_account", "loan_balance_adjustments", type_="foreignkey")
    op.drop_column("loan_balance_adjustments", "reversal_reason")
    op.drop_column("loan_balance_adjustments", "reversed_at")
    op.drop_column("loan_balance_adjustments", "account_id")
    op.drop_column("loan_balance_adjustments", "source_amount")
    op.drop_column("loan_balance_rules", "deleted_at")
    op.drop_column("transactions", "user_type_override")
    op.drop_column("transactions", "user_category_override")
    op.drop_column("transactions", "provider_type")
    op.drop_column("transactions", "provider_category")
    # The previous schema cannot represent occurrence identities. Preserve all
    # transaction rows and retain only legacy 64-character fingerprints.
    op.execute("UPDATE transactions SET import_fingerprint = NULL WHERE import_fingerprint LIKE '%:%'")
    op.alter_column("transactions", "import_fingerprint", type_=sa.String(64), existing_type=sa.String(80))
