from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.account import AccountResponse


class PlaidLinkTokenResponse(BaseModel):
    link_token: str
    expiration: datetime


class PlaidLinkTokenRequest(BaseModel):
    """Pass an existing institution ID to enter Plaid Link update mode.
    The backend resolves its encrypted access token after verifying the
    institution belongs to the authenticated user.
    """

    institution_id: UUID | None = None


class PlaidExchangePublicTokenRequest(BaseModel):
    """`public_token` is short-lived (expires in ~30 minutes) and single-use
    by design on Plaid's side — it can't be replayed to link an item twice.
    Nothing else about which user it belongs to is taken from the client;
    the institution/accounts created from it are always attributed to
    `current_user` from the JWT, never a client-supplied user id.
    """

    public_token: str


class PlaidInstitutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str


class PlaidExchangePublicTokenResponse(BaseModel):
    institution: PlaidInstitutionResponse
    accounts: list[AccountResponse]


class PlaidRefreshInstitutionResponse(BaseModel):
    institution_id: UUID
    institution_name: str
    status: str
    accounts_synced: int = 0
    transactions_created: int = 0
    transactions_updated: int = 0
    transactions_removed: int = 0
    holdings_synced: int = 0
    error: str | None = None


class PlaidRefreshResponse(BaseModel):
    data: list[PlaidRefreshInstitutionResponse]
