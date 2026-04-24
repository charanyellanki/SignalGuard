"""Paginated, filterable anomaly listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Anomaly, get_session
from schemas import AnomalyPage, AnomalyRecord, Severity

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("", response_model=AnomalyPage)
async def list_anomalies(
    session: AsyncSession = Depends(get_session),
    device_id: str | None = None,
    anomaly_type: str | None = None,
    severity: Severity | None = None,
    detected_by_model: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AnomalyPage:
    stmt = select(Anomaly)
    count_stmt = select(func.count(Anomaly.id))

    for col, value in (
        (Anomaly.device_id, device_id),
        (Anomaly.anomaly_type, anomaly_type),
        (Anomaly.severity, severity),
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
