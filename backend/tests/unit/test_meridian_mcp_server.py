"""End-to-end protocol checks using the official Python MCP SDK."""

from importlib.util import find_spec
from uuid import UUID, uuid4

import pytest
import httpx
from fastapi import FastAPI

from app import mcp_server
from app.api.reporting_deps import ReportingUser

pytestmark = pytest.mark.skipif(find_spec("mcp") is None, reason="MCP SDK is not installed")


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class _FakeSessionFactory:
    def __call__(self):
        return _FakeSession()


@pytest.mark.asyncio
async def test_official_mcp_protocol_authenticates_and_calls_read_only_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import daily_reports

    expected_user_id = "6a14970e-227c-4374-acbd-58a89b969df2"
    current_calls: list[str] = []
    daily_calls: list[tuple[str, object, int]] = []

    async def authenticate(_session, authorization):
        if authorization == "Bearer valid-agent-token":
            return ReportingUser(UUID(expected_user_id), uuid4(), frozenset({"reports:read"}))
        return None

    async def current_summary(_db, user_id):
        current_calls.append(str(user_id))
        return {"assets": "1000.00", "net_worth": "1000.00"}

    async def daily_report(_db, user_id, report_date, wait_seconds=0):
        daily_calls.append((str(user_id), report_date, wait_seconds))
        return {"status": "ready", "report_id": "report-1", "captured_at": "2026-10-11T08:05:00-04:00"}

    monkeypatch.setattr(mcp_server, "AsyncSessionLocal", _FakeSessionFactory())
    monkeypatch.setattr(mcp_server, "authenticate_bearer_for_reporting", authenticate)
    monkeypatch.setattr(daily_reports, "get_current_summary", current_summary)
    monkeypatch.setattr(daily_reports, "get_daily_report", daily_report)

    protected_mcp, runtime = mcp_server.create_mcp_server(session_factory=_FakeSessionFactory())
    app = FastAPI()
    app.mount("/", protected_mcp)

    async def post(client: httpx.AsyncClient, payload: dict) -> httpx.Response:
        return await client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer valid-agent-token",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json=payload,
        )

    try:
        await runtime.start()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://meridian.example.test",
        ) as client:
            initialize = await post(
                client,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "meridian-test", "version": "1.0"},
                    },
                },
            )
            assert initialize.status_code == 200, initialize.text
            assert initialize.json()["result"]["serverInfo"]["name"] == "Meridian"

            listed = await post(
                client,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            assert listed.status_code == 200, listed.text
            tools = listed.json()["result"]["tools"]
            assert {tool["name"] for tool in tools} == {
                "get_current_financial_summary",
                "get_daily_report",
                "list_daily_reports",
                "get_report_changes",
            }
            assert all(tool.get("annotations", {}).get("readOnlyHint") is True for tool in tools)

            current = await post(
                client,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "get_current_financial_summary", "arguments": {}},
                },
            )
            assert current.status_code == 200, current.text
            assert current_calls == [expected_user_id]

            daily = await post(
                client,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "get_daily_report",
                        "arguments": {"date": "2026-10-11", "wait_seconds": 20},
                    },
                },
            )
            assert daily.status_code == 200, daily.text
            assert len(daily_calls) == 1
            user_id, report_date, wait_seconds = daily_calls[0]
            assert user_id == expected_user_id
            assert report_date.isoformat() == "2026-10-11"
            assert wait_seconds == 20
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_mcp_protocol_rejects_missing_and_invalid_tokens_before_initialize(monkeypatch: pytest.MonkeyPatch) -> None:
    async def reject(_session, _authorization):
        return None

    monkeypatch.setattr(mcp_server, "authenticate_bearer_for_reporting", reject)
    protected_mcp, runtime = mcp_server.create_mcp_server(session_factory=_FakeSessionFactory())
    app = FastAPI()
    app.mount("/", protected_mcp)
    try:
        await runtime.start()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://meridian.example.test"
        ) as client:
            response = await client.post(
                "/mcp",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid credentials"}
    finally:
        await runtime.stop()
