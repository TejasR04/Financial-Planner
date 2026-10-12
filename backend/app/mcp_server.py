"""The read-only Meridian reporting MCP server.

The public FastAPI application mounts ``asgi_app`` at ``/mcp`` and calls
``runtime.start()`` / ``runtime.stop()`` from its startup and shutdown hooks.
The wrapper authenticates every HTTP request, including initialize and tool
discovery, before it reaches the MCP protocol handler.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import date as Date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.reporting_deps import authenticate_bearer_for_reporting
from app.persistence.session import AsyncSessionLocal

_mcp_user_id: ContextVar[UUID | None] = ContextVar("meridian_mcp_user_id", default=None)


def _set_authenticated_user(user_id: UUID) -> Token[UUID | None]:
    return _mcp_user_id.set(user_id)


def _current_user_id() -> UUID:
    user_id = _mcp_user_id.get()
    if user_id is None:
        raise PermissionError("An authenticated Meridian reporting token is required")
    return user_id


class AgentTokenAuthASGI:
    """Require a valid reports:read token on every MCP HTTP request."""

    def __init__(self, app: ASGIApp, session_factory: Any = AsyncSessionLocal):
        self.app = app
        self.session_factory = session_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") not in {"/mcp", "/mcp/"}:
            await self.app(scope, receive, send)
            return

        authorization = _header(scope, b"authorization")
        async with self.session_factory() as db:
            principal = await authenticate_bearer_for_reporting(db, authorization)

        if principal is None:
            await _send_unauthorized(send)
            return

        context_token = _set_authenticated_user(principal.id)
        try:
            await self.app(scope, receive, send)
        finally:
            _mcp_user_id.reset(context_token)


def _header(scope: Scope, name: bytes) -> str | None:
    for header_name, value in scope.get("headers", []):
        if header_name.lower() == name:
            return value.decode("latin-1")
    return None


async def _send_unauthorized(send: Send) -> None:
    body = b'{"detail":"Invalid credentials"}'
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"www-authenticate", b"Bearer"),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class MCPServerRuntime:
    """Expose FastMCP's session-manager lifecycle to the existing FastAPI app."""

    def __init__(self, server: Any):
        self.server = server
        self._run_context: Any | None = None

    async def start(self) -> None:
        if self._run_context is not None:
            return
        self._run_context = self.server.session_manager.run()
        await self._run_context.__aenter__()

    async def stop(self) -> None:
        if self._run_context is None:
            return
        context = self._run_context
        self._run_context = None
        await context.__aexit__(None, None, None)


def create_mcp_server(session_factory: Any | None = None) -> tuple[ASGIApp, MCPServerRuntime]:
    """Build a stateless JSON Streamable HTTP server at the mounted root path."""
    # Keep the optional SDK import here so non-MCP API tests and tooling can
    # import the app modules even before backend dependencies are installed.
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations

    server = FastMCP(
        "Meridian",
        instructions="Read-only financial reports for the authenticated Meridian user.",
        host="0.0.0.0",
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )
    readonly = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    async def with_session(operation: Any) -> Any:
        user_id = _current_user_id()
        async with AsyncSessionLocal() as session:
            return await operation(session, user_id)

    @server.tool(
        name="get_current_financial_summary",
        description="Return the authenticated user's current read-only financial summary.",
        annotations=readonly,
    )
    async def get_current_financial_summary() -> dict[str, Any]:
        from app.services.daily_reports import get_current_summary

        return await with_session(get_current_summary)

    @server.tool(
        name="get_daily_report",
        description="Read a captured daily report. Waiting never starts a capture or financial sync.",
        annotations=readonly,
    )
    async def get_daily_report(date: str, wait_seconds: int = 0) -> dict[str, Any]:
        if not 0 <= wait_seconds <= 30:
            raise ValueError("wait_seconds must be between 0 and 30")
        parsed_date = _parse_date(date, "date")
        if parsed_date is None:
            raise ValueError("date is required")

        async def query(session: AsyncSession, user_id: UUID) -> dict[str, Any]:
            from app.services.daily_reports import get_daily_report as get_report

            return await get_report(session, user_id, parsed_date, wait_seconds=wait_seconds)

        return await with_session(query)

    @server.tool(
        name="list_daily_reports",
        description="List captured reports in a date range using an opaque pagination cursor.",
        annotations=readonly,
    )
    async def list_daily_reports(
        start_date: str | None = None,
        end_date: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        parsed_start = _parse_date(start_date, "start_date") if start_date else None
        parsed_end = _parse_date(end_date, "end_date") if end_date else None

        async def query(session: AsyncSession, user_id: UUID) -> dict[str, Any]:
            from app.services.daily_reports import list_reports

            return await list_reports(
                session,
                user_id,
                start_date=parsed_start,
                end_date=parsed_end,
                cursor=cursor,
                limit=limit,
            )

        return await with_session(query)

    @server.tool(
        name="get_report_changes",
        description="Read paginated financial change details belonging to one of the user's reports.",
        annotations=readonly,
    )
    async def get_report_changes(
        report_id: str,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        try:
            parsed_report_id = UUID(report_id)
        except ValueError as exc:
            raise ValueError("report_id must be a UUID") from exc

        async def query(session: AsyncSession, user_id: UUID) -> dict[str, Any]:
            from app.services.daily_reports import get_report_changes

            return await get_report_changes(
                session,
                user_id,
                parsed_report_id,
                cursor=cursor,
                limit=limit,
            )

        return await with_session(query)

    asgi_app = AgentTokenAuthASGI(server.streamable_http_app(), session_factory=session_factory or AsyncSessionLocal)
    return asgi_app, MCPServerRuntime(server)


def _parse_date(value: str | None, field_name: str) -> Date | None:
    if value is None:
        return None
    try:
        return Date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format") from exc
