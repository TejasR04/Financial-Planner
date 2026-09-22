from pydantic import BaseModel, Field

from app.schemas.plaid import PlaidRefreshInstitutionResponse


class MarketRefreshResponse(BaseModel):
    symbols_updated: int = 0
    holdings_updated: int = 0
    accounts_updated: int = 0
    errors: dict[str, str] = Field(default_factory=dict)


class FinancialDataRefreshResponse(BaseModel):
    institutions: list[PlaidRefreshInstitutionResponse] = Field(default_factory=list)
    market: MarketRefreshResponse
