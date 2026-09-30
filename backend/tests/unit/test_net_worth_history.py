from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from fastapi import Response

from app.api.v1.routes import accounts as account_routes
from app.api.v1.routes import auth as auth_routes
from app.domain.entities import Account, User
from app.domain.enums import AccountType
from app.persistence.repositories import net_worth_snapshot_repository as module
from app.schemas.auth import RegisterRequest, TokenResponse


@pytest.mark.asyncio
async def test_observation_uses_active_user_accounts_and_updates_the_same_day(monkeypatch):
    user_id = uuid4()
    rows = [
        Account(uuid4(), user_id, "Bank", AccountType.DEPOSITORY, Decimal("1200")),
        Account(uuid4(), user_id, "Brokerage", AccountType.INVESTMENT, Decimal("300")),
        Account(uuid4(), user_id, "Card", AccountType.CREDIT, Decimal("-200")),
    ]
    list_for_user = AsyncMock(return_value=rows)
    monkeypatch.setattr(module, "AccountRepository", lambda _: SimpleNamespace(list_for_user=list_for_user))
    session = SimpleNamespace(execute=AsyncMock())

    await module.NetWorthSnapshotRepository(session).observe_current(user_id, date(2026, 9, 28))

    list_for_user.assert_awaited_once_with(user_id)
    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert "ON CONFLICT ON CONSTRAINT uq_net_worth_snapshots_user_date DO UPDATE" in str(compiled)
    assert Decimal("1500") in compiled.params.values()
    assert Decimal("200") in compiled.params.values()
    assert date(2026, 9, 28) in compiled.params.values()


@pytest.mark.asyncio
async def test_history_route_returns_dated_assets_liabilities_and_net_for_user(monkeypatch):
    user = User(uuid4(), "owner@example.com", "Owner")
    repo = SimpleNamespace(
        observe_current=AsyncMock(),
        history_for_user=AsyncMock(return_value=[
            (date(2026, 9, 27), Decimal("1000"), Decimal("300")),
            (date(2026, 9, 28), Decimal("1200"), Decimal("200")),
        ]),
    )
    monkeypatch.setattr(account_routes, "NetWorthSnapshotRepository", lambda _: repo)
    session = SimpleNamespace(commit=AsyncMock())

    result = await account_routes.observe_net_worth_history(user, session)

    repo.observe_current.assert_awaited_once_with(user.id)
    repo.history_for_user.assert_awaited_once_with(user.id)
    session.commit.assert_awaited_once()
    assert [(point.date, point.assets, point.liabilities, point.net) for point in result] == [
        (date(2026, 9, 27), Decimal("1000"), Decimal("300"), Decimal("700")),
        (date(2026, 9, 28), Decimal("1200"), Decimal("200"), Decimal("1000")),
    ]


@pytest.mark.asyncio
async def test_registration_starts_net_worth_history_on_account_creation(monkeypatch):
    user = User(uuid4(), "new@example.com", "New")
    observe = AsyncMock()
    monkeypatch.setattr(auth_routes, "get_settings", lambda: SimpleNamespace(registration_enabled=True))
    monkeypatch.setattr(auth_routes, "_client_key", lambda _: "unit-test")
    monkeypatch.setattr(auth_routes, "_enforce_rate_limit", lambda *_: None)
    monkeypatch.setattr(auth_routes, "hash_password", lambda _: "hashed")
    monkeypatch.setattr(auth_routes, "UserRepository", lambda _: SimpleNamespace(
        get_by_email=AsyncMock(return_value=None), create=AsyncMock(return_value=user)))
    monkeypatch.setattr(auth_routes, "NetWorthSnapshotRepository", lambda _: SimpleNamespace(observe_current=observe))
    monkeypatch.setattr(auth_routes, "_start_session", AsyncMock(return_value=TokenResponse(access_token="test-token")))
    session = SimpleNamespace(commit=AsyncMock())

    result = await auth_routes.register(
        RegisterRequest(email=user.email, full_name=user.full_name, password="correct-horse-battery-staple"),
        SimpleNamespace(), Response(), session,
    )

    observe.assert_awaited_once_with(user.id)
    session.commit.assert_awaited_once()
    assert result.access_token == "test-token"
