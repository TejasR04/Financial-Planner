"""Shared background sync logic for the API loop and scheduled job."""
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.config import get_settings
from app.persistence.repositories.user_repository import UserRepository
from app.persistence.repositories.net_worth_snapshot_repository import NetWorthSnapshotRepository
from app.persistence.session import AsyncSessionLocal
from app.persistence.reporting_models import FinancialSyncRunModel
from app.providers.plaid_provider import PlaidProvider
from app.providers.market_data_provider import TiingoMarketDataProvider
from app.services.market_price_sync_service import MarketPriceSyncService
from app.services.investment_contribution_service import InvestmentContributionService
from app.services.loan_balance_automation_service import LoanBalanceAutomationService

logger = logging.getLogger("meridian.plaid_sync")
SYNC_LOCK_ID = 0x4D4552494449414E


async def try_acquire_sync_lease(connection) -> bool:
    return bool(await connection.scalar(
        text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": SYNC_LOCK_ID}))


async def release_sync_lease(connection) -> None:
    await connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": SYNC_LOCK_ID})


async def sync_all_linked_institutions() -> int:
    """Commit successful users independently; report failures to the job runner."""
    settings = get_settings()
    failures = 0
    async with AsyncSessionLocal() as session:
        user_ids = await UserRepository(session).list_active_ids()
        for user_id in user_ids:
            try:
                provider = PlaidProvider(session, settings.plaid_client_id, settings.plaid_secret, settings.plaid_env)
                results = await provider.refresh(user_id)
                await session.commit()
                failed = sum(result.status == "error" for result in results)
                failures += failed
                logger.info("plaid_sync_user_completed", extra={"user_id": str(user_id), "failed_institutions": failed})
            except Exception:
                await session.rollback()
                failures += 1
                logger.exception("plaid_sync_user_failed", extra={"user_id": str(user_id)})
    return failures


async def sync_all_financial_data() -> int:
    """Run both provider-linked and manual ticker refreshes for every user."""
    settings = get_settings()
    failures = 0
    market_provider = TiingoMarketDataProvider(settings.tiingo_api_key)
    async with AsyncSessionLocal() as session:
        user_ids = await UserRepository(session).list_active_ids()
        for user_id in user_ids:
            sync_run = FinancialSyncRunModel(user_id=user_id, source="scheduled", status="running")
            session.add(sync_run)
            await session.commit()
            sync_run_id = sync_run.id
            failures_before = failures
            failed_components = []
            if settings.plaid_client_id and settings.plaid_secret:
                try:
                    results = await PlaidProvider(
                        session, settings.plaid_client_id, settings.plaid_secret, settings.plaid_env
                    ).refresh(user_id)
                    await session.commit()
                    institution_failures = sum(result.status == "error" for result in results)
                    failures += institution_failures
                    if institution_failures:
                        failed_components.append("plaid")
                except Exception:
                    await session.rollback()
                    failures += 1
                    logger.exception("plaid_sync_user_failed", extra={"user_id": str(user_id)})
                    failed_components.append("plaid")

            try:
                loan_adjustments_applied = await LoanBalanceAutomationService(session).apply(user_id)
                await session.commit()
                logger.info(
                    "loan_balance_automation_user_completed",
                    extra={"user_id": str(user_id), "adjustments_applied": loan_adjustments_applied},
                )
            except Exception:
                await session.rollback()
                failures += 1
                logger.exception("loan_balance_automation_user_failed", extra={"user_id": str(user_id)})
                failed_components.append("loan_automation")

            try:
                contributions_applied = await InvestmentContributionService(session).apply(user_id)
                await session.commit()
                logger.info(
                    "investment_contributions_user_completed",
                    extra={"user_id": str(user_id), "contributions_applied": contributions_applied},
                )
            except Exception:
                await session.rollback()
                failures += 1
                logger.exception("investment_contributions_user_failed", extra={"user_id": str(user_id)})
                failed_components.append("investment_contributions")

            try:
                market = await MarketPriceSyncService(session, market_provider).sync_user(user_id)
                await session.commit()
                failures += len(market.errors)
                if market.errors:
                    failed_components.append("market")
                logger.info(
                    "market_sync_user_completed",
                    extra={
                        "user_id": str(user_id),
                        "holdings_updated": market.holdings_updated,
                        "ticker_errors": len(market.errors),
                    },
                )
            except Exception:
                await session.rollback()
                failures += 1
                logger.exception("market_sync_user_failed", extra={"user_id": str(user_id)})
                failed_components.append("market")
            try:
                await NetWorthSnapshotRepository(session).observe_current(user_id)
                await session.commit()
            except Exception:
                await session.rollback()
                failures += 1
                logger.exception("net_worth_snapshot_user_failed", extra={"user_id": str(user_id)})
                failed_components.append("net_worth_snapshot")
            finished_run = await session.get(FinancialSyncRunModel, sync_run_id)
            if finished_run is None:
                raise RuntimeError("Financial sync run disappeared")
            finished_run.status = "partial" if failures > failures_before else "succeeded"
            finished_run.finished_at = datetime.now(timezone.utc)
            finished_run.error_summary = {"failed_components": failed_components} if failed_components else None
            await session.commit()
    return failures
