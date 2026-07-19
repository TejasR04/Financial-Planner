from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.account import AccountResponse


class PlaidLinkTokenResponse(BaseModel):
    link_token: str
    expiration: datetime


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
