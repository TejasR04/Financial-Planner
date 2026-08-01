import asyncio
import logging
import time
from uuid import uuid4
from contextlib import suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
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
configure_logging(settings.log_level)
logger = logging.getLogger("meridian.api")

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.middleware("http")
async def log_request(request: Request, call_next):
    """Emit one structured record per request; never include bodies or credentials."""
    request_id = request.headers.get("X-Request-ID", uuid4().hex)
    started_at = time.perf_counter()
    log_fields = {"request_id": request_id, "method": request.method, "path": request.url.path}
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed", extra=log_fields)
        raise

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed",
        extra={**log_fields, "status_code": response.status_code, "duration_ms": duration_ms},
    )
    return response


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
                logger.exception("plaid_auto_sync_user_failed", extra={"user_id": str(user_id)})


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


@app.get("/health/live")
async def liveness() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness() -> dict:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("readiness_database_failed")
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready"}


@app.get("/health", include_in_schema=False)
async def health() -> dict:
    return await liveness()
