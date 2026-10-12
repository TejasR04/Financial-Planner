from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.domain.entities import User
from app.persistence.reporting_models import FinancialSyncRunModel
from app.providers.market_data_provider import TiingoMarketDataProvider
from app.providers.plaid_provider import PlaidProvider
from app.schemas.plaid import PlaidRefreshInstitutionResponse
from app.schemas.sync import FinancialDataRefreshResponse, MarketRefreshResponse
from app.services.market_price_sync_service import MarketPriceSyncService
from app.services.investment_contribution_service import InvestmentContributionService
from app.services.loan_balance_automation_service import LoanBalanceAutomationService

router = APIRouter(prefix="/sync", tags=["sync"])


async def _refresh_financial_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FinancialDataRefreshResponse:
    """Refresh linked institutions and automatically priced manual tickers."""
    settings = get_settings()
    plaid_results = []
    plaid_configured = bool(settings.plaid_client_id and settings.plaid_secret)
    if plaid_configured:
        plaid_results = await PlaidProvider(
            db, settings.plaid_client_id, settings.plaid_secret, settings.plaid_env
        ).refresh(current_user.id)
        await db.commit()

    # PlaidProvider.refresh applies loan automation after every linked Item
    # has synced; only run this separately when Plaid isn't configured.
    if not plaid_configured:
        await LoanBalanceAutomationService(db).apply(current_user.id)
    contributions_applied = await InvestmentContributionService(db).apply(current_user.id)
    market_result = await MarketPriceSyncService(
        db, TiingoMarketDataProvider(settings.tiingo_api_key)
    ).sync_user(current_user.id)
    await db.commit()
    return FinancialDataRefreshResponse(
        institutions=[
            PlaidRefreshInstitutionResponse(
                institution_id=result.institution_id,
                institution_name=result.institution_name,
                status=result.status,
                accounts_synced=result.accounts_synced,
                transactions_created=result.transactions_created,
                transactions_updated=result.transactions_updated,
                transactions_removed=result.transactions_removed,
                holdings_synced=result.holdings_synced,
                error=result.error,
            )
            for result in plaid_results
        ],
        market=MarketRefreshResponse(
            symbols_updated=market_result.symbols_updated,
            holdings_updated=market_result.holdings_updated,
            accounts_updated=market_result.accounts_updated,
            errors=market_result.errors,
        ),
        contributions_applied=contributions_applied,
    )


@router.post("", response_model=FinancialDataRefreshResponse)
async def refresh_financial_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FinancialDataRefreshResponse:
    run = FinancialSyncRunModel(user_id=current_user.id, source="manual", status="running")
    db.add(run)
    await db.commit()
    run_id = run.id
    try:
        result = await _refresh_financial_data(current_user, db)
    except Exception:
        await db.rollback()
        failed_run = await db.get(FinancialSyncRunModel, run_id)
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.finished_at = datetime.now(timezone.utc)
            failed_run.error_summary = {"failed_components": ["manual_sync"]}
            await db.commit()
        raise
    finished_run = await db.get(FinancialSyncRunModel, run_id)
    if finished_run is not None:
        errors = ["plaid"] if any(item.status == "error" for item in result.institutions) else []
        if result.market.errors:
            errors.append("market")
        finished_run.status = "partial" if errors else "succeeded"
        finished_run.finished_at = datetime.now(timezone.utc)
        finished_run.error_summary = {"failed_components": errors} if errors else None
        await db.commit()
    return result
