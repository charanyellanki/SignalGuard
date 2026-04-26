"""Unit-scoped endpoints: units summary + per-unit detail.

In self-storage industry parlance, each Nokē smart lock corresponds to
one rentable storage unit. Internally we keep ``device_*`` field names
to stay generic in the schema, but the user-facing concept is "units".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Anomaly, Telemetry, get_session
from schemas import AnomalyRecord, DeviceDetail, DeviceSummary, TelemetryPoint

router = APIRouter(prefix="/devices", tags=["devices"])

# A lock is "online" if it sent telemetry in the last 30 seconds
# (devices emit every 5s; 6 missed ticks ≈ gateway problem).
ONLINE_THRESHOLD_SEC = 30


@router.get("", response_model=list[DeviceSummary])
async def list_devices(
    session: AsyncSession = Depends(get_session),
    customer_id: str | None = Query(None, description="Filter to a single operator"),
    site_id: str | None = Query(None, description="Filter to a single facility"),
) -> list[DeviceSummary]:
    # Latest telemetry per device via DISTINCT ON.
    latest_stmt = (
        select(Telemetry)
        .distinct(Telemetry.device_id)
        .order_by(Telemetry.device_id, desc(Telemetry.timestamp))
    )
    if customer_id is not None:
        latest_stmt = latest_stmt.where(Telemetry.customer_id == customer_id)
    if site_id is not None:
        latest_stmt = latest_stmt.where(Telemetry.site_id == site_id)
    latest_rows = (await session.execute(latest_stmt)).scalars().all()

    counts_stmt = select(
        Anomaly.device_id,
        func.count(Anomaly.id).label("n"),
        func.max(Anomaly.timestamp).label("last_at"),
    ).group_by(Anomaly.device_id)
    if customer_id is not None:
        counts_stmt = counts_stmt.where(Anomaly.customer_id == customer_id)
    if site_id is not None:
        counts_stmt = counts_stmt.where(Anomaly.site_id == site_id)
    counts = {row.device_id: (row.n, row.last_at) for row in await session.execute(counts_stmt)}

    online_cutoff = datetime.now(timezone.utc) - timedelta(seconds=ONLINE_THRESHOLD_SEC)
    summaries: list[DeviceSummary] = []
    for row in latest_rows:
        n, last_at = counts.get(row.device_id, (0, None))
        summaries.append(
            DeviceSummary(
                device_id=row.device_id,
                customer_id=row.customer_id,
                customer_name=row.customer_name,
                site_id=row.site_id,
                site_name=row.site_name,
                building=row.building,
                unit_id=row.unit_id,
                latest=TelemetryPoint.model_validate(row),
                anomaly_count=n,
                last_anomaly_at=last_at,
                online=row.timestamp >= online_cutoff,
            )
        )
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

    head = telem_rows[0]
    return DeviceDetail(
        device_id=device_id,
        customer_id=head.customer_id,
        customer_name=head.customer_name,
        site_id=head.site_id,
        site_name=head.site_name,
        building=head.building,
        unit_id=head.unit_id,
        telemetry=[TelemetryPoint.model_validate(r) for r in reversed(telem_rows)],
        anomalies=[AnomalyRecord.model_validate(r) for r in anom_rows],
    )
