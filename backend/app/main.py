import asyncio
from contextlib import suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    ProviderError,
    UnauthorizedError,
    ValidationError,
)
from app.persistence.repositories.user_repository import UserRepository
from app.persistence.session import AsyncSessionLocal
from app.providers.plaid_provider import PlaidProvider

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
async def validate_plaid_config() -> None:
    """Fail fast and loud at boot if Plaid is configured but the token
    encryption key is missing/malformed, rather than letting the first
    user who tries to link an account hit a confusing 500.
    """
    if settings.plaid_client_id and settings.plaid_secret:
        from app.core.crypto import _fernet

        _fernet()
        if settings.plaid_auto_sync_enabled:
            app.state.plaid_auto_sync_task = asyncio.create_task(_plaid_auto_sync_loop())


async def _sync_all_linked_institutions() -> None:
    """Refresh every user's linked Plaid Items without a browser request.

    This is deliberately best-effort: `PlaidProvider.refresh` isolates one
    failed institution from the others, and one user's failure must never
    prevent the next user's data from being refreshed.
    """
    async with AsyncSessionLocal() as session:
        user_ids = await UserRepository(session).list_active_ids()
        for user_id in user_ids:
            try:
                provider = PlaidProvider(session, settings.plaid_client_id, settings.plaid_secret, settings.plaid_env)
                await provider.refresh(user_id)
                await session.commit()
            except Exception:
                await session.rollback()


async def _plaid_auto_sync_loop() -> None:
    interval_seconds = max(15, settings.plaid_auto_sync_interval_minutes * 60)
    while True:
        await asyncio.sleep(interval_seconds)
        await _sync_all_linked_institutions()


@app.on_event("shutdown")
async def stop_plaid_auto_sync() -> None:
    task = getattr(app.state, "plaid_auto_sync_task", None)
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


_STATUS_BY_ERROR = {
    NotFoundError: 404,
    ValidationError: 422,
    UnauthorizedError: 401,
    ConflictError: 409,
    ProviderError: 502,
}


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    status_code = _STATUS_BY_ERROR.get(type(exc), 400)
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
