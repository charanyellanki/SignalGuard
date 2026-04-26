"""Paginated, filterable anomaly listing + NOC workflow actions."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import Anomaly, get_session
from schemas import (
    AnomalyAction,
    AnomalyActionRequest,
    AnomalyPage,
    AnomalyRecord,
    AnomalyStatus,
    Severity,
)

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


# Mapping from action verb → terminal status. Defines the NOC workflow.
_ACTION_TO_STATUS: dict[AnomalyAction, AnomalyStatus] = {
    "acknowledge":    "acknowledged",
    "dispatch":       "dispatched",
    "snooze":         "snoozed",
    "resolve":        "resolved",
    "false_positive": "false_positive",
    "reopen":         "open",
}


@router.get("", response_model=AnomalyPage)
async def list_anomalies(
    session: AsyncSession = Depends(get_session),
    device_id: str | None = None,
    customer_id: str | None = None,
    site_id: str | None = None,
    anomaly_type: str | None = None,
    severity: Severity | None = None,
    status: AnomalyStatus | None = None,
    detected_by_model: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AnomalyPage:
    stmt = select(Anomaly)
    count_stmt = select(func.count(Anomaly.id))

    for col, value in (
        (Anomaly.device_id,         device_id),
        (Anomaly.customer_id,       customer_id),
        (Anomaly.site_id,           site_id),
        (Anomaly.anomaly_type,      anomaly_type),
        (Anomaly.severity,          severity),
        (Anomaly.status,            status),
        (Anomaly.detected_by_model, detected_by_model),
    ):
        if value is not None:
            stmt = stmt.where(col == value)
            count_stmt = count_stmt.where(col == value)

    stmt = stmt.order_by(desc(Anomaly.timestamp)).limit(limit).offset(offset)

    rows = (await session.execute(stmt)).scalars().all()
    total = int((await session.execute(count_stmt)).scalar() or 0)

    return AnomalyPage(
        items=[AnomalyRecord.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{anomaly_id}/action", response_model=AnomalyRecord)
async def act_on_anomaly(
    anomaly_id: int,
    body: AnomalyActionRequest = Body(...),
    session: AsyncSession = Depends(get_session),
) -> AnomalyRecord:
    """Transition an anomaly through the NOC workflow.

    The body's ``action`` selects the next status. ``assignee`` and
    ``note`` are optional metadata captured at the moment of action.
    """
    new_status = _ACTION_TO_STATUS[body.action]
    now = datetime.now(timezone.utc)

    result = await session.execute(
        update(Anomaly)
        .where(Anomaly.id == anomaly_id)
        .values(
            status=new_status,
            assignee=body.assignee,
            acted_at=now,
            action_note=body.note,
        )
        .returning(Anomaly)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="anomaly not found")
    await session.commit()
    return AnomalyRecord.model_validate(row)
