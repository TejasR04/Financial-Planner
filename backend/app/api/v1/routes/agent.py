from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.ai.agent import AgentOrchestrator
from app.api.deps import get_current_user
from app.domain.entities import User

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict]
    structured_results: list[dict]


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, current_user: User = Depends(get_current_user)) -> ChatResponse:
    orchestrator = AgentOrchestrator()
    result = orchestrator.handle_message(body.message, body.history)
    return ChatResponse(
        reply=result.reply, tool_calls=result.tool_calls, structured_results=result.structured_results
    )
