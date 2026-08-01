import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.config import get_settings
from app.persistence.repositories.refresh_session_repository import RefreshSessionRepository
from app.persistence.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.email_service import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path=f"{settings.api_v1_prefix}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.refresh_cookie_name, path=f"{settings.api_v1_prefix}/auth")


async def _start_session(user_id: UUID, response: Response, db: AsyncSession) -> TokenResponse:
    settings = get_settings()
    refresh_token = create_refresh_token()
    await RefreshSessionRepository(db).create(
        user_id, refresh_token, settings.refresh_token_expire_days
    )
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=create_access_token(user_id))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    repo = UserRepository(db)
    if await repo.get_by_email(body.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = await repo.create(body.email, body.full_name, hash_password(body.password))
    tokens = await _start_session(user.id, response, db)
    await db.commit()
    return tokens


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    repo = UserRepository(db)
    result = await repo.get_hashed_password(body.email)
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    user, hashed = result
    if not verify_password(body.password, hashed):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    tokens = await _start_session(user.id, response, db)
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    refresh_token = request.cookies.get(get_settings().refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    repo = RefreshSessionRepository(db)
    consumed = await repo.consume(refresh_token)
    if consumed is None:
        await db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    replacement_token = create_refresh_token()
    replacement = await repo.create(
        consumed.user_id, replacement_token, get_settings().refresh_token_expire_days
    )
    await repo.set_replacement(consumed, replacement.id)
    await db.commit()
    _set_refresh_cookie(response, replacement_token)
    return TokenResponse(access_token=create_access_token(consumed.user_id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> None:
    refresh_token = request.cookies.get(get_settings().refresh_cookie_name)
    if refresh_token:
        await RefreshSessionRepository(db).revoke(refresh_token)
        await db.commit()
    _clear_refresh_cookie(response)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    body: PasswordResetRequest, db: AsyncSession = Depends(get_db)
) -> None:
    """Always return the same response to avoid revealing registered emails."""
    result = await UserRepository(db).get_hashed_password(body.email)
    if result is None:
        return
    user, _ = result
    try:
        token = create_password_reset_token(user.id)
        await asyncio.to_thread(send_password_reset_email, user.email, token)
    except Exception:
        # The client still gets the generic accepted response. Detailed
        # delivery errors are operational information, not authentication UI.
        logger.exception("Unable to send password reset email")


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    body: PasswordResetConfirmRequest, db: AsyncSession = Depends(get_db)
) -> None:
    try:
        payload = decode_token(body.token)
        if payload.get("type") != "password_reset":
            raise InvalidTokenError("wrong token type")
        user_id = UUID(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password-reset link is invalid or has expired.",
        ) from exc

    await UserRepository(db).update_password(user_id, hash_password(body.password))
    await RefreshSessionRepository(db).revoke_all(user_id)
    await db.commit()
