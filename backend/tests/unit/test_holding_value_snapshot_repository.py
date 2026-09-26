from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.persistence.repositories.investment_value_snapshot_repository import InvestmentValueSnapshotRepository


@pytest.mark.asyncio
async def test_closed_positions_are_not_repeated_after_latest_zero_observation():
    statements = []
    calls = 0

    class Session:
        def __init__(self):
            self.added = []
            self.flush = AsyncMock()

        async def execute(self, statement):
            nonlocal calls
            calls += 1
            statements.append(statement)
            # No row exists for this date, and prior latest-nonzero query
            # returns no positions because the symbol was already closed.
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []), all=lambda: [])

        def add(self, row):
            self.added.append(row)

    session = Session()
    repo = InvestmentValueSnapshotRepository(session)

    await repo.record_holding_values([uuid4()], [], date(2026, 9, 26))

    assert calls == 2
    sql = str(statements[1])
    assert "max(holding_value_snapshots.as_of)" in sql
    assert "holding_value_snapshots.value !=" in sql
    assert session.added == []
