"""Read-only financial reporting endpoints for configured external agents."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.reporting_deps import get_reporting_user_id
from app.services.daily_reports import (
    get_current_summary,
    get_daily_report,
    get_report_changes,
    list_reports,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/current")
async def current_financial_summary(
    user_id: UUID = Depends(get_reporting_user_id), db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_current_summary(db, user_id)


@router.get("/daily")
async def daily_financial_report(
    date_: date = Query(alias="date"),
    wait_seconds: int = Query(default=0, ge=0, le=30),
    user_id: UUID = Depends(get_reporting_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_daily_report(db, user_id, date_, wait_seconds)


@router.get("")
async def report_history(
    start_date: date | None = None,
    end_date: date | None = None,
    cursor: str | None = Query(default=None, max_length=256),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: UUID = Depends(get_reporting_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    try:
        return await list_reports(db, user_id, start_date, end_date, cursor, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{report_id}/changes")
async def report_change_history(
    report_id: UUID,
    cursor: str | None = Query(default=None, max_length=256),
    limit: int = Query(default=100, ge=1, le=200),
    user_id: UUID = Depends(get_reporting_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        response = await get_report_changes(db, user_id, report_id, cursor, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if response["status"] == "unavailable":
        raise HTTPException(status_code=404, detail="Report not found or not ready")
    return response

