"""Shared background sync logic for the API loop and scheduled job."""
import logging

from sqlalchemy import text

from app.core.config import get_settings
from app.persistence.repositories.user_repository import UserRepository
from app.persistence.session import AsyncSessionLocal
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
            if settings.plaid_client_id and settings.plaid_secret:
                try:
                    results = await PlaidProvider(
                        session, settings.plaid_client_id, settings.plaid_secret, settings.plaid_env
                    ).refresh(user_id)
                    await session.commit()
                    failures += sum(result.status == "error" for result in results)
                except Exception:
                    await session.rollback()
                    failures += 1
                    logger.exception("plaid_sync_user_failed", extra={"user_id": str(user_id)})

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

            try:
                market = await MarketPriceSyncService(session, market_provider).sync_user(user_id)
                await session.commit()
                failures += len(market.errors)
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
    return failures
