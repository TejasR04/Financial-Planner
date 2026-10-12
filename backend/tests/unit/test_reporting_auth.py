import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.reporting_deps import authenticate_bearer_for_reporting
from app.mcp_server import AgentTokenAuthASGI, _current_user_id


@pytest.mark.asyncio
@pytest.mark.parametrize("authorization", [None, "Basic abc", "Bearer", "Bearer invalid"])
async def test_reporting_bearer_parser_rejects_missing_or_non_bearer_credentials(authorization: str | None) -> None:
    assert await authenticate_bearer_for_reporting(None, authorization) is None  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_mcp_auth_wraps_every_request_and_keeps_user_context_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    users_by_token = {"token-a": uuid4(), "token-b": uuid4()}

    async def authenticate(_session, authorization):
        if authorization is None:
            return None
        token = authorization.partition(" ")[2]
        user_id = users_by_token.get(token)
        return SimpleNamespace(id=user_id) if user_id is not None else None

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr("app.mcp_server.authenticate_bearer_for_reporting", authenticate)
    wrapper = AgentTokenAuthASGI(None, session_factory=lambda: FakeSession())  # type: ignore[arg-type]

    async def inner(scope, receive, send):
        await asyncio.sleep(0)
        body = json.dumps({"user_id": str(_current_user_id())}).encode()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": body})

    wrapper.app = inner

    async def call(token: str) -> bytes:
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        await wrapper(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
            },
            receive,
            send,
        )
        return next(message["body"] for message in messages if message["type"] == "http.response.body")

    result_a, result_b = await asyncio.gather(call("token-a"), call("token-b"))

    assert json.loads(result_a)["user_id"] == str(users_by_token["token-a"])
    assert json.loads(result_b)["user_id"] == str(users_by_token["token-b"])


@pytest.mark.asyncio
async def test_mcp_auth_rejects_before_request_reaches_protocol_app(monkeypatch: pytest.MonkeyPatch) -> None:
    async def authenticate(_session, _authorization):
        return None

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr("app.mcp_server.authenticate_bearer_for_reporting", authenticate)
    called = False

    async def should_not_reach_app(_scope, _receive, _send):
        nonlocal called
        called = True

    wrapper = AgentTokenAuthASGI(should_not_reach_app, session_factory=lambda: FakeSession())
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await wrapper(
        {"type": "http", "method": "POST", "path": "/mcp", "headers": []},
        receive,
        send,
    )

    assert called is False
    assert messages[0]["status"] == 401
    assert (b"www-authenticate", b"Bearer") in messages[0]["headers"]
