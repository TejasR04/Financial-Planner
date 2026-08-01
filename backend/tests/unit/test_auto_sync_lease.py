import sys
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
