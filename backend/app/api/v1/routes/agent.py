from datetime import datetime
import logging
import re
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.ai.agent import AgentOrchestrator, GeminiConfigurationError, GeminiTemporaryError
from app.ai.context import build_user_financial_context
from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.core.rate_limit import PerKeyConcurrencyLimiter, SlidingWindowRateLimiter
from app.persistence.repositories.agent_message_repository import (
    AgentConversationRepository,
    AgentMessageRepository,
)
from app.persistence.snapshot_builder import build_financial_snapshot

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger("meridian.agent")


class ChatHistoryEntry(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    history: list[ChatHistoryEntry] = Field(default_factory=list, max_length=30)


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    tool_calls: list[dict]
    structured_results: list[dict]


class AgentMessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class AgentConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


chat_rate_limiter = SlidingWindowRateLimiter(limit=10, window_seconds=60)
chat_concurrency_limiter = PerKeyConcurrencyLimiter(limit=1)


def _activity_selection_query(message: str, history: list[dict[str, str]]) -> str:
    """Carry the prior user topic into short comparison/follow-up requests."""
    follow_up = bool(
        re.search(
            r"\b(compare|comparison|previous|prior|other months?|what about|how about|same|that|those|instead)\b",
            message,
            re.IGNORECASE,
        )
    )
    if not follow_up:
        return message
    prior = next(
        (item["content"] for item in reversed(history) if item.get("role") == "user"),
        None,
    )
    return f"{message}\nPrior user request: {prior}" if prior else message


def _conversation_title(message: str) -> str:
    title = " ".join(message.split())
    if len(title) <= 80:
        return title
    return f"{title[:77].rstrip()}..."


def _message_response(row) -> AgentMessageResponse:
    return AgentMessageResponse(
        id=str(row.id), role=row.role, content=row.content, created_at=row.created_at
    )


@router.get("/conversations", response_model=list[AgentConversationResponse])
async def conversations(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[AgentConversationResponse]:
    rows = await AgentConversationRepository(db).list_for_user(current_user.id)
    return [
        AgentConversationResponse(
            id=str(conversation.id),
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=message_count,
        )
        for conversation, message_count in rows
    ]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[AgentMessageResponse],
)
async def conversation_messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentMessageResponse]:
    conversation = await AgentConversationRepository(db).get_for_user(
        current_user.id, conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    rows = await AgentMessageRepository(db).list_for_conversation(
        current_user.id, conversation_id, limit=100
    )
    return [_message_response(row) for row in rows]


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    repository = AgentConversationRepository(db)
    conversation = await repository.get_for_user(current_user.id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    await repository.delete(conversation)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/history", response_model=list[AgentMessageResponse])
async def history(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[AgentMessageResponse]:
    conversations = await AgentConversationRepository(db).list_for_user(current_user.id, limit=1)
    if not conversations:
        return []
    rows = await AgentMessageRepository(db).list_for_conversation(
        current_user.id, conversations[0][0].id
    )
    return [_message_response(row) for row in rows]


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Response:
    await AgentMessageRepository(db).clear_all(current_user.id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    user_key = str(current_user.id)
    if not chat_rate_limiter.allow(user_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many assistant requests.")
    if not chat_concurrency_limiter.acquire(user_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="An assistant request is already running.")
    try:
        try:
            orchestrator = AgentOrchestrator()
        except GeminiConfigurationError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        message = body.message.strip()
        message_repo = AgentMessageRepository(db)
        conversation_repo = AgentConversationRepository(db)
        if body.conversation_id is None:
            conversation = await conversation_repo.create(
                current_user.id, _conversation_title(message)
            )
        else:
            conversation = await conversation_repo.get_for_user(
                current_user.id, body.conversation_id
            )
            if conversation is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
                )
        stored = await message_repo.list_for_conversation(current_user.id, conversation.id)
        conversation_history = (
            [{"role": row.role, "content": row.content} for row in stored]
            if stored
            else [item.model_dump() for item in body.history]
        )
        snapshot = await build_financial_snapshot(db, current_user.id)
        selection_query = _activity_selection_query(message, conversation_history)
        user_context = await build_user_financial_context(db, snapshot, selection_query)

        try:
            result = await run_in_threadpool(
                orchestrator.handle_message, message, conversation_history, 4, user_context
            )
        except GeminiTemporaryError as exc:
            logger.warning("gemini_temporarily_unavailable", extra={"user_id": user_key}, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gemini is temporarily busy. Please try again in a moment.",
            ) from exc
        except Exception as exc:
            logger.exception("gemini_request_failed", extra={"user_id": user_key})
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini could not complete the analysis. Please try again.",
            ) from exc
        if not result.reply.strip():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini returned an empty analysis. Please try again.",
            )

        await message_repo.append(current_user.id, conversation.id, "user", message)
        await message_repo.append(current_user.id, conversation.id, "assistant", result.reply)
        await message_repo.prune(current_user.id, conversation.id)
        await conversation_repo.touch(conversation)
        await db.commit()
        return ChatResponse(
            conversation_id=str(conversation.id),
            reply=result.reply, tool_calls=result.tool_calls, structured_results=result.structured_results
        )
    finally:
        chat_concurrency_limiter.release(user_key)
