from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import InsightKind


class InsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: InsightKind
    text: str
    meta: str
    generated_at: datetime | None
