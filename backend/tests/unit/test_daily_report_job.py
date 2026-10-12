from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.jobs import daily_report as job


def configure_job(monkeypatch):
    connection = AsyncMock()
    connection.execution_options.return_value = connection
    context = AsyncMock()
    context.__aenter__.return_value = connection
    engine = SimpleNamespace(connect=lambda: context, dispose=AsyncMock())
    monkeypatch.setattr(job, "engine", engine)
    monkeypatch.setattr(job, "get_settings", lambda: SimpleNamespace(log_level="WARNING"))
    monkeypatch.setattr(job, "configure_logging", lambda *_: None)
    monkeypatch.setattr(job, "_users_to_report", AsyncMock(return_value=["user"]))
    monkeypatch.setattr(job, "release_sync_lease", AsyncMock())
    return connection, engine


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", [("ready", 0), ("failed", 1)])
async def test_capture_runs_only_after_sync_lease_and_cleans_up(monkeypatch, status, expected):
    connection, engine = configure_job(monkeypatch)
    acquire = AsyncMock(return_value=True)
    capture = AsyncMock(return_value={"status": status, "report_id": "report"})
    monkeypatch.setattr(job, "try_acquire_sync_lease", acquire)
    monkeypatch.setattr(job, "capture_daily_report", capture)
    assert await job.run_once() == expected
    acquire.assert_awaited_once_with(connection)
    capture.assert_awaited_once_with("user", job.financial_today())
    job.release_sync_lease.assert_awaited_once_with(connection)
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_busy_sync_timeout_records_failure_without_capturing(monkeypatch):
    _, engine = configure_job(monkeypatch)
    monkeypatch.setattr(job, "LEASE_WAIT_SECONDS", 0)
    capture = AsyncMock()
    failure = AsyncMock()
    monkeypatch.setattr(job, "capture_daily_report", capture)
    monkeypatch.setattr(job, "mark_daily_report_failed", failure)
    assert await job.run_once() == 1
    capture.assert_not_awaited()
    assert failure.await_args.args[:2] == ("user", job.financial_today())
    job.release_sync_lease.assert_not_awaited()
    engine.dispose.assert_awaited_once()
