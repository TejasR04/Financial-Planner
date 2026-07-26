"""Fixtures for API tests against a disposable Postgres database.

Run these through docker compose so TEST_DATABASE_URL points at the isolated
`meridian_test` database. The guard prevents an accidental test run against
the developer's normal data.
"""

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.main import app
from app.persistence import models  # noqa: F401 - registers all tables with Base
from app.persistence.session import Base


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if "meridian_test" not in TEST_DATABASE_URL:
    pytest.skip(
        "Set TEST_DATABASE_URL to the disposable meridian_test database to run integration tests.",
        allow_module_level=True,
    )


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncIterator[AsyncClient]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            await connection.execute(delete(table))

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def register_and_authorize(client: AsyncClient, email: str = "casey@example.com") -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery-staple", "full_name": "Casey Test"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
