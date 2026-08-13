import sys
import asyncio
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# The production dependency is declared in requirements.txt, but this focused
# unit test only imports app.main and does not exercise Gemini.
try:
    import google.genai  # noqa: F401
except ModuleNotFoundError:
    google_module = ModuleType("google")
    genai_module = ModuleType("google.genai")
    genai_module.types = ModuleType("google.genai.types")
    google_module.genai = genai_module
    sys.modules.setdefault("google", google_module)
    sys.modules["google.genai"] = genai_module
    sys.modules["google.genai.types"] = genai_module.types

from app import main


@pytest.mark.asyncio
async def test_auto_sync_lease_reports_when_another_worker_holds_it():
    session = SimpleNamespace(scalar=AsyncMock(return_value=False), execute=AsyncMock())

    assert await main._try_acquire_plaid_auto_sync_lease(session) is False
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_sync_lease_is_explicitly_released():
    session = SimpleNamespace(scalar=AsyncMock(return_value=True), execute=AsyncMock())

    assert await main._try_acquire_plaid_auto_sync_lease(session) is True
    await main._release_plaid_auto_sync_lease(session)
    assert "pg_advisory_unlock" in str(session.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_auto_sync_refreshes_immediately_after_acquiring_lease(monkeypatch):
    lease_connection = AsyncMock()
    raw_connection = AsyncMock()
    raw_connection.execution_options.return_value = lease_connection
    connection_context = AsyncMock()
    connection_context.__aenter__.return_value = raw_connection
    connection_context.__aexit__.return_value = None

    engine = SimpleNamespace(connect=lambda: connection_context)
    refreshed = asyncio.Event()

    async def sync_all():
        refreshed.set()

    async def stop_after_first_sleep(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "_try_acquire_plaid_auto_sync_lease", AsyncMock(return_value=True))
    monkeypatch.setattr(main, "_release_plaid_auto_sync_lease", AsyncMock())
    monkeypatch.setattr(main, "_sync_all_linked_institutions", sync_all)
    monkeypatch.setattr(main.asyncio, "sleep", stop_after_first_sleep)

    with pytest.raises(asyncio.CancelledError):
        await main._plaid_auto_sync_loop()

    assert refreshed.is_set()
    lease_connection.execute.assert_awaited_once()
