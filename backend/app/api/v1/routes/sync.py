from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.domain.entities import User
from app.providers.market_data_provider import TiingoMarketDataProvider
from app.providers.plaid_provider import PlaidProvider
from app.schemas.plaid import PlaidRefreshInstitutionResponse
from app.schemas.sync import FinancialDataRefreshResponse, MarketRefreshResponse
from app.services.market_price_sync_service import MarketPriceSyncService

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("", response_model=FinancialDataRefreshResponse)
async def refresh_financial_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FinancialDataRefreshResponse:
    """Refresh linked institutions and automatically priced manual tickers."""
    settings = get_settings()
    plaid_results = []
    if settings.plaid_client_id and settings.plaid_secret:
        plaid_results = await PlaidProvider(
            db, settings.plaid_client_id, settings.plaid_secret, settings.plaid_env
        ).refresh(current_user.id)
        await db.commit()

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
    )
