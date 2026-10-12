"""Transaction-local provenance for database financial audit triggers."""
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


@event.listens_for(Session, "after_begin")
def _apply_audit_source(session, transaction, connection) -> None:
    source = session.info.get("financial_audit_source", "unknown")
    connection.execute(text("SELECT set_config('meridian.audit_source', :source, true)"), {"source": source})


async def set_audit_source(session: AsyncSession, source: str) -> None:
    # Test doubles need not emulate Postgres transaction-local settings.
    if not isinstance(session, AsyncSession):
        return
    session.info["financial_audit_source"] = source
    await session.execute(text("SELECT set_config('meridian.audit_source', :source, true)"), {"source": source})
