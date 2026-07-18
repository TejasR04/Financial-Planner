from decimal import Decimal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import RecommendationEffort, RecommendationStatus


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    body: str
    category: str
    impact_value: Decimal
    effort: RecommendationEffort
    confidence: float
    status: RecommendationStatus
    generated_at: datetime | None


class RecommendationUpdateRequest(BaseModel):
    status: RecommendationStatus
