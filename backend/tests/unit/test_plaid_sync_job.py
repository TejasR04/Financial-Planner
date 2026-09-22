from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.jobs import plaid_sync as job
from app.services import plaid_sync_service as service


@pytest.mark.asyncio
@pytest.mark.parametrize("acquired,failures,expected", [(True, 0, 0), (True, 2, 1), (False, 0, 0), (True, RuntimeError("failed"), None)])
async def test_job_lease_failure_status_and_cleanup(monkeypatch, acquired, failures, expected):
    connection = AsyncMock()
    raw = AsyncMock()
    raw.execution_options.return_value = connection
    context = AsyncMock()
    context.__aenter__.return_value = raw
    engine = SimpleNamespace(connect=Mock(return_value=context), dispose=AsyncMock())
    monkeypatch.setattr(job, "engine", engine)
    monkeypatch.setattr(job, "get_settings", lambda: SimpleNamespace(log_level="INFO", plaid_client_id="test", plaid_secret="test"))
    monkeypatch.setattr(job, "_fernet", Mock())
    monkeypatch.setattr(job, "try_acquire_sync_lease", AsyncMock(return_value=acquired))
    monkeypatch.setattr(job, "release_sync_lease", AsyncMock())
    monkeypatch.setattr(job, "sync_all_financial_data", AsyncMock(
        side_effect=failures if isinstance(failures, Exception) else None, return_value=failures))
    if isinstance(failures, Exception):
        with pytest.raises(RuntimeError, match="failed"):
            await job.run_once()
    else:
        assert await job.run_once() == expected
    engine.dispose.assert_awaited_once()
    if acquired:
        job.sync_all_financial_data.assert_awaited_once()
        job.release_sync_lease.assert_awaited_once_with(connection)
    else:
        job.sync_all_financial_data.assert_not_awaited()
        job.release_sync_lease.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_continues_after_user_failure_and_reports_institution_errors(monkeypatch):
    session = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = session
    monkeypatch.setattr(service, "AsyncSessionLocal", lambda: context)
    monkeypatch.setattr(service, "UserRepository", lambda _: SimpleNamespace(list_active_ids=AsyncMock(return_value=["first", "second", "third"])))
    refresh = AsyncMock(side_effect=[RuntimeError("failed"), [SimpleNamespace(status="healthy")], [SimpleNamespace(status="error")]])
    monkeypatch.setattr(service, "PlaidProvider", lambda *args: SimpleNamespace(refresh=refresh))
    assert await service.sync_all_linked_institutions() == 2
    assert refresh.await_count == 3
    assert session.commit.await_count == 2
    session.rollback.assert_awaited_once()
