from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError
from app.core.security import create_password_reset_token, hash_password_reset_token
from app.persistence.repositories.budget_repository import BudgetRepository
from app.persistence.repositories.password_reset_token_repository import (
    PasswordResetTokenRepository,
)


def _sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_password_reset_consume_is_one_conditional_update():
    consumed = object()
    result = SimpleNamespace(scalar_one_or_none=lambda: consumed)
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    token = create_password_reset_token(uuid4())

    returned = await PasswordResetTokenRepository(session).consume(token, uuid4())

    assert returned is consumed
    statement = session.execute.await_args.args[0]
    sql = _sql(statement)
    assert "password_reset_tokens.consumed_at IS NULL" in sql
    assert "password_reset_tokens.expires_at >" in sql
    assert "RETURNING password_reset_tokens" in sql


@pytest.mark.asyncio
async def test_password_reset_create_persists_only_a_digest():
    session = SimpleNamespace(add=Mock(), flush=AsyncMock())
    user_id = uuid4()
    token = create_password_reset_token(user_id)

    row = await PasswordResetTokenRepository(session).create(user_id, token, 30)

    assert row.token_hash == hash_password_reset_token(token)
    assert token not in row.token_hash
    session.add.assert_called_once_with(row)


@pytest.mark.asyncio
async def test_category_create_translates_unique_index_race_to_conflict():
    empty_categories = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [])
    )
    session = SimpleNamespace(
        execute=AsyncMock(return_value=empty_categories),
        scalar=AsyncMock(return_value=None),
        add=Mock(),
        flush=AsyncMock(
            side_effect=IntegrityError("INSERT", {}, Exception("unique violation"))
        ),
    )

    with pytest.raises(ConflictError):
        await BudgetRepository(session).create_category(
            uuid4(), "Travel", "Wants", Decimal("0")
        )
