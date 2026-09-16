"""Shared background sync logic for the API loop and scheduled job."""
import logging

from sqlalchemy import text

from app.core.config import get_settings
from app.persistence.repositories.user_repository import UserRepository
from app.persistence.session import AsyncSessionLocal
from app.providers.plaid_provider import PlaidProvider

logger = logging.getLogger("meridian.plaid_sync")
SYNC_LOCK_ID = 0x4D4552494449414E


async def try_acquire_sync_lease(connection) -> bool:
    return bool(await connection.scalar(
        text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": SYNC_LOCK_ID}))


async def release_sync_lease(connection) -> None:
    await connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": SYNC_LOCK_ID})


async def sync_all_linked_institutions() -> int:
    """Commit successful users independently; report failures to the job runner."""
    settings = get_settings()
    failures = 0
    async with AsyncSessionLocal() as session:
        user_ids = await UserRepository(session).list_active_ids()
        for user_id in user_ids:
            try:
                provider = PlaidProvider(session, settings.plaid_client_id, settings.plaid_secret, settings.plaid_env)
                results = await provider.refresh(user_id)
                await session.commit()
                failed = sum(result.status == "error" for result in results)
                failures += failed
                logger.info("plaid_sync_user_completed", extra={"user_id": str(user_id), "failed_institutions": failed})
            except Exception:
                await session.rollback()
                failures += 1
                logger.exception("plaid_sync_user_failed", extra={"user_id": str(user_id)})
    return failures
