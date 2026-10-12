"""Add daily financial reports, agent credentials, and change audit events.

Revision ID: a10b2c3d4e5f
Revises: 8d10a1b2c3d4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a10b2c3d4e5f"
down_revision = "8d10a1b2c3d4"
branch_labels = None
depends_on = None


_AUDITED_TABLES = (
    "accounts",
    "holdings",
    "transactions",
    "liabilities",
    "budget_categories",
    "merchant_budget_rules",
    "income_sources",
    "investment_contribution_rules",
    "investment_contribution_adjustments",
    "loan_balance_rules",
    "loan_balance_adjustments",
)


def upgrade() -> None:
    op.create_table(
        "agent_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("token_prefix", sa.String(16), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[\"reports:read\"]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_tokens_user_id", "agent_tokens", ["user_id"])
    op.create_index("ix_agent_tokens_token_hash", "agent_tokens", ["token_hash"])
    op.create_index("ix_agent_tokens_expires_at", "agent_tokens", ["expires_at"])
    op.create_index("ix_agent_tokens_user_created", "agent_tokens", ["user_id", "created_at"])

    op.create_table(
        "reporting_enrollments",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "financial_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("previous_report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("financial_reports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_financial_reports_user_id", "financial_reports", ["user_id"])
    op.create_index("ix_financial_reports_scheduled_date", "financial_reports", ["scheduled_date"])
    op.create_index("ix_financial_reports_status", "financial_reports", ["status"])
    op.create_index(
        "uq_financial_reports_daily_user_date", "financial_reports", ["user_id", "scheduled_date"],
        unique=True, postgresql_where=sa.text("is_baseline = false"),
    )
    op.create_index(
        "uq_financial_reports_baseline_user", "financial_reports", ["user_id"],
        unique=True, postgresql_where=sa.text("is_baseline = true"),
    )
    op.create_index("ix_financial_reports_user_captured", "financial_reports", ["user_id", "captured_at"])

    op.create_table(
        "financial_change_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(12), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("before_values", postgresql.JSONB(), nullable=True),
        sa.Column("after_values", postgresql.JSONB(), nullable=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("financial_reports.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_financial_change_events_user_id", "financial_change_events", ["user_id"])
    op.create_index("ix_financial_change_events_observed_at", "financial_change_events", ["observed_at"])
    op.create_index("ix_financial_change_events_report_id", "financial_change_events", ["report_id"])
    op.create_index(
        "ix_financial_change_events_unassigned", "financial_change_events", ["user_id", "observed_at"],
        postgresql_where=sa.text("report_id IS NULL"),
    )
    op.create_index("ix_financial_change_events_report", "financial_change_events", ["report_id", "observed_at"])
    op.create_index("ix_financial_change_events_entity", "financial_change_events", ["entity_type", "entity_id", "observed_at"])

    op.create_table(
        "financial_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_financial_sync_runs_user_id", "financial_sync_runs", ["user_id"])
    op.create_index("ix_financial_sync_runs_status", "financial_sync_runs", ["status"])
    op.create_index("ix_financial_sync_runs_user_finished", "financial_sync_runs", ["user_id", "finished_at"])

    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION meridian_financial_audit_capture()
        RETURNS trigger AS $$
        DECLARE
            v_row jsonb;
            v_before jsonb := '{}'::jsonb;
            v_after jsonb := '{}'::jsonb;
            v_numeric_value jsonb;
            v_user_id uuid;
            v_account_id text;
            v_deleted_accounts jsonb;
            v_field text;
            v_source text;
            v_operation text;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                v_row := to_jsonb(OLD);
                v_operation := 'delete';
            ELSE
                v_row := to_jsonb(NEW);
                v_operation := lower(TG_OP);
            END IF;

            IF TG_TABLE_NAME = 'accounts' AND TG_OP = 'DELETE' THEN
                v_deleted_accounts := COALESCE(
                    NULLIF(current_setting('meridian.audit_deleted_accounts', true), '')::jsonb,
                    '{}'::jsonb
                );
                v_deleted_accounts := v_deleted_accounts || jsonb_build_object(OLD.id::text, OLD.user_id::text);
                PERFORM set_config('meridian.audit_deleted_accounts', v_deleted_accounts::text, true);
            END IF;

            IF TG_ARGV[0] <> '' THEN
                v_user_id := NULLIF(v_row ->> TG_ARGV[0], '')::uuid;
            ELSIF TG_ARGV[1] <> '' THEN
                v_account_id := v_row ->> TG_ARGV[1];
                IF v_account_id IS NOT NULL THEN
                    SELECT user_id INTO v_user_id FROM accounts WHERE id = v_account_id::uuid;
                END IF;
                IF v_user_id IS NULL AND v_account_id IS NOT NULL THEN
                    v_deleted_accounts := COALESCE(
                        NULLIF(current_setting('meridian.audit_deleted_accounts', true), '')::jsonb,
                        '{}'::jsonb
                    );
                    v_user_id := NULLIF(v_deleted_accounts ->> v_account_id, '')::uuid;
                END IF;
            END IF;

            -- User deletion is an explicit data erasure. Do not create rows
            -- which would block its cascading cleanup.
            IF v_user_id IS NULL OR NOT EXISTS (SELECT 1 FROM users WHERE id = v_user_id) THEN
                IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
            END IF;

            IF TG_OP <> 'INSERT' THEN
                FOREACH v_field IN ARRAY string_to_array(TG_ARGV[2], ',') LOOP
                    v_numeric_value := to_jsonb(OLD) -> v_field;
                    v_before := v_before || jsonb_build_object(
                        v_field,
                        CASE WHEN jsonb_typeof(v_numeric_value) = 'number'
                             THEN to_jsonb(v_numeric_value::text)
                             ELSE v_numeric_value END
                    );
                END LOOP;
            END IF;
            IF TG_OP <> 'DELETE' THEN
                FOREACH v_field IN ARRAY string_to_array(TG_ARGV[2], ',') LOOP
                    v_numeric_value := to_jsonb(NEW) -> v_field;
                    v_after := v_after || jsonb_build_object(
                        v_field,
                        CASE WHEN jsonb_typeof(v_numeric_value) = 'number'
                             THEN to_jsonb(v_numeric_value::text)
                             ELSE v_numeric_value END
                    );
                END LOOP;
            END IF;

            IF TG_OP = 'UPDATE' AND v_before = v_after THEN
                RETURN NEW;
            END IF;
            v_source := NULLIF(current_setting('meridian.audit_source', true), '');
            IF v_source IS NULL THEN v_source := 'unknown'; END IF;

            INSERT INTO financial_change_events
                (id, user_id, entity_type, entity_id, operation, observed_at, source, before_values, after_values)
            VALUES
                (gen_random_uuid(), v_user_id, TG_TABLE_NAME, v_row ->> 'id', v_operation,
                 clock_timestamp(), v_source,
                 CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE v_before END,
                 CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE v_after END);

            IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
        END;
        $$ LANGUAGE plpgsql
    """))

    triggers = {
        "accounts": ("user_id", "", "name,custom_name,type,currency,balance,reported_cash_balance,reported_cash_is_liquid,apy,status,archived_at,user_archived_at,provider_archived_at,institution_id"),
        "holdings": ("", "account_id", "symbol,quantity,cost_basis,market_value,asset_class,as_of,pricing_mode,last_price"),
        "transactions": ("", "account_id", "posted_at,merchant,category,amount,type,status,budget_category_id,ignored_from_budget,provider_category,provider_type,user_category_override,user_type_override,reviewed_at,deleted_at"),
        "liabilities": ("", "account_id", "principal,interest_rate,term_months,minimum_payment,origination_date,last_interest_accrual_date"),
        "budget_categories": ("user_id", "", "name,group_name,monthly_limit,sort_order,active"),
        "merchant_budget_rules": ("user_id", "", "budget_category_id,transaction_type,merchant_pattern"),
        "income_sources": ("user_id", "", "name,annual_amount,growth_rate,type,active"),
        "investment_contribution_rules": ("", "account_id", "amount,day_of_month,next_run_date,active,deleted_at"),
        "investment_contribution_adjustments": ("", "account_id", "scheduled_for,amount,applied_at,holdings_applied"),
        "loan_balance_rules": ("", "account_id", "mode,amount,frequency,next_run_date,merchant_pattern,active,deleted_at"),
        "loan_balance_adjustments": ("", "account_id", "event_key,amount_applied,source_amount,applied_at,reversed_at,reversal_reason,transaction_id"),
    }
    for table, (user_field, account_field, fields) in triggers.items():
        op.execute(sa.text(
            f"CREATE TRIGGER tr_{table}_financial_audit "
            f"BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW "
            f"EXECUTE FUNCTION meridian_financial_audit_capture('{user_field}', '{account_field}', '{fields}')"
        ))


def downgrade() -> None:
    for table in _AUDITED_TABLES:
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS tr_{table}_financial_audit ON {table}"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS meridian_financial_audit_capture()"))
    op.drop_table("financial_sync_runs")
    op.drop_table("financial_change_events")
    op.drop_table("financial_reports")
    op.drop_table("reporting_enrollments")
    op.drop_table("agent_tokens")
