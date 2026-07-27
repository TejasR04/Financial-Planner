from datetime import datetime
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.ai.agent import AgentOrchestrator, GeminiConfigurationError
from app.ai.context import build_user_financial_context
from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.persistence.repositories.agent_message_repository import AgentMessageRepository
from app.persistence.snapshot_builder import build_financial_snapshot

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger("meridian.agent")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict]
    structured_results: list[dict]


class AgentMessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


@router.get("/history", response_model=list[AgentMessageResponse])
async def history(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[AgentMessageResponse]:
    rows = await AgentMessageRepository(db).list_for_user(current_user.id)
    return [
        AgentMessageResponse(
            id=str(row.id), role=row.role, content=row.content, created_at=row.created_at
        )
        for row in rows
    ]


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Response:
    await AgentMessageRepository(db).clear(current_user.id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    try:
        orchestrator = AgentOrchestrator()
    except GeminiConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    snapshot = await build_financial_snapshot(db, current_user.id)
    user_context = await build_user_financial_context(db, snapshot)
    message_repo = AgentMessageRepository(db)
    stored = await message_repo.list_for_user(current_user.id)
    conversation_history = (
        [{"role": row.role, "content": row.content} for row in stored]
        if stored
        else body.history[-30:]
    )

    try:
        result = await run_in_threadpool(
            orchestrator.handle_message,
            body.message.strip(),
            conversation_history,
            4,
            user_context,
        )
    except Exception as exc:
        logger.exception("gemini_request_failed", extra={"user_id": str(current_user.id)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini could not complete the analysis. Please try again.",
        ) from exc
    if not result.reply.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini returned an empty analysis. Please try again.",
        )

    await message_repo.append(current_user.id, "user", body.message.strip())
    await message_repo.append(current_user.id, "assistant", result.reply)
    await message_repo.prune(current_user.id)
    await db.commit()
    return ChatResponse(
        reply=result.reply, tool_calls=result.tool_calls, structured_results=result.structured_results
    )
