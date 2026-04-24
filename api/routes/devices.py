"""Device-scoped endpoints: fleet summary + per-device detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Anomaly, Telemetry, get_session
from schemas import AnomalyRecord, DeviceDetail, DeviceSummary, TelemetryPoint

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceSummary])
async def list_devices(session: AsyncSession = Depends(get_session)) -> list[DeviceSummary]:
    # Latest telemetry per device via DISTINCT ON.
    latest_stmt = (
        select(Telemetry)
        .distinct(Telemetry.device_id)
        .order_by(Telemetry.device_id, desc(Telemetry.timestamp))
    )
    latest_rows = (await session.execute(latest_stmt)).scalars().all()

    # Anomaly counts + last timestamp per device.
    counts_stmt = select(
        Anomaly.device_id,
        func.count(Anomaly.id).label("n"),
        func.max(Anomaly.timestamp).label("last_at"),
    ).group_by(Anomaly.device_id)
    counts = {row.device_id: (row.n, row.last_at) for row in await session.execute(counts_stmt)}

    summaries: list[DeviceSummary] = []
    for row in latest_rows:
        n, last_at = counts.get(row.device_id, (0, None))
        summaries.append(
            DeviceSummary(
                device_id=row.device_id,
                latest=TelemetryPoint.model_validate(row),
                anomaly_count=n,
                last_anomaly_at=last_at,
            )
        )
    # Stable ordering for the UI.
    summaries.sort(key=lambda d: d.device_id)
    return summaries


@router.get("/{device_id}", response_model=DeviceDetail)
async def get_device(
    device_id: str, session: AsyncSession = Depends(get_session)
) -> DeviceDetail:
    telem_stmt = (
        select(Telemetry)
        .where(Telemetry.device_id == device_id)
        .order_by(desc(Telemetry.timestamp))
        .limit(100)
    )
    telem_rows = (await session.execute(telem_stmt)).scalars().all()
    if not telem_rows:
        raise HTTPException(status_code=404, detail="device not found")

    anom_stmt = (
        select(Anomaly)
        .where(Anomaly.device_id == device_id)
        .order_by(desc(Anomaly.timestamp))
        .limit(50)
    )
    anom_rows = (await session.execute(anom_stmt)).scalars().all()

    return DeviceDetail(
        device_id=device_id,
        # Chronological (oldest → newest) is friendlier for recharts.
        telemetry=[TelemetryPoint.model_validate(r) for r in reversed(telem_rows)],
        anomalies=[AnomalyRecord.model_validate(r) for r in anom_rows],
    )
