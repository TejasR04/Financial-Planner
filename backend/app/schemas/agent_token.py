from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentTokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class AgentTokenResponse(BaseModel):
    id: UUID
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    scope: str = "reports:read"


class AgentTokenCreatedResponse(AgentTokenResponse):
    token: str


class AgentTokenListResponse(BaseModel):
    data: list[AgentTokenResponse]
