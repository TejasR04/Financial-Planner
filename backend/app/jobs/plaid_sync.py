"""Run with `python -m app.jobs.plaid_sync`; scheduling is owned by Cloud Scheduler."""
import asyncio
import logging

from app.core.config import get_settings
from app.core.crypto import _fernet
from app.core.logging import configure_logging
from app.persistence.session import engine
from app.services.plaid_sync_service import (
    release_sync_lease, sync_all_financial_data, try_acquire_sync_lease,
)

logger = logging.getLogger("meridian.plaid_sync_job")


async def run_once() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        if settings.plaid_client_id or settings.plaid_secret:
            if not settings.plaid_client_id or not settings.plaid_secret:
                raise RuntimeError("Both Plaid credentials are required when Plaid sync is configured")
            _fernet()
        async with engine.connect() as raw_connection:
            connection = await raw_connection.execution_options(isolation_level="AUTOCOMMIT")
            if not await try_acquire_sync_lease(connection):
                logger.info("plaid_sync_skipped_existing_runner")
                return 0
            try:
                failures = await sync_all_financial_data()
                logger.info("plaid_sync_job_completed", extra={"failures": failures})
                return 1 if failures else 0
            finally:
                await release_sync_lease(connection)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_once()))
