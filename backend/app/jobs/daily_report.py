"""Scheduled immutable report capture; invoke as `python -m app.jobs.daily_report`."""
from __future__ import annotations

import asyncio
import logging
import time

from app.core.config import get_settings
from app.core.financial_date import financial_today
from app.core.logging import configure_logging
from app.persistence.session import AsyncSessionLocal, engine
from app.services.daily_reports import (
    capture_daily_report,
    enabled_reporting_users,
    mark_daily_report_failed,
)
from app.services.plaid_sync_service import release_sync_lease, try_acquire_sync_lease

logger = logging.getLogger("meridian.daily_report_job")
LEASE_WAIT_SECONDS = 15 * 60
LEASE_POLL_SECONDS = 30


async def _users_to_report() -> list:
    async with AsyncSessionLocal() as db:
        return await enabled_reporting_users(db)


async def _mark_all_failed(user_ids: list, report_date, message: str) -> None:
    for user_id in user_ids:
        try:
            await mark_daily_report_failed(user_id, report_date, message)
        except Exception:
            logger.exception("daily_report_failure_persist_failed", extra={"user_id": str(user_id)})


async def run_once() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    report_date = financial_today()
    locked = False
    try:
        user_ids = await _users_to_report()
        if not user_ids:
            logger.info("daily_report_no_enrolled_users", extra={"date": report_date.isoformat()})
            return 0

        async with engine.connect() as raw_connection:
            connection = await raw_connection.execution_options(isolation_level="AUTOCOMMIT")
            try:
                deadline = time.monotonic() + LEASE_WAIT_SECONDS
                while time.monotonic() < deadline:
                    if await try_acquire_sync_lease(connection):
                        locked = True
                        break
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    await asyncio.sleep(min(LEASE_POLL_SECONDS, remaining))

                if not locked:
                    message = "The scheduled financial sync lease remained busy for 15 minutes; no report snapshot was captured."
                    await _mark_all_failed(user_ids, report_date, message)
                    logger.error("daily_report_sync_lease_timeout", extra={"date": report_date.isoformat(), "users": len(user_ids)})
                    return 1

                failures = 0
                for user_id in user_ids:
                    try:
                        report = await capture_daily_report(user_id, report_date)
                        if report.get("status") != "ready":
                            failures += 1
                        logger.info(
                            "daily_report_user_capture_finished",
                            extra={"user_id": str(user_id), "report_id": report.get("report_id"), "status": report.get("status")},
                        )
                    except Exception:
                        failures += 1
                        logger.exception("daily_report_user_capture_failed", extra={"user_id": str(user_id)})
                        await mark_daily_report_failed(user_id, report_date, "The scheduled report capture failed unexpectedly.")
                return 1 if failures else 0
            finally:
                if locked:
                    await release_sync_lease(connection)
                    locked = False
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_once()))

