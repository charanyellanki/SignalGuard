"""Customer (operator) rollups — top-level grouping for the NOC dashboard.

Each row represents one Nokē-deployed storage operator (e.g. CubeSmart,
StorageMart, Extra Space) and aggregates health across all of that
operator's facilities. This is the primary slice for a Janus HQ
customer success engineer working a multi-tenant queue.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import Subquery, case, desc, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Anomaly, Telemetry, get_session
from schemas import CustomerSummary

router = APIRouter(tags=["customers"])

ONLINE_THRESHOLD_SEC = 30


def _online_cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=ONLINE_THRESHOLD_SEC)


def _twenty_four_hours_ago() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=24)


def _latest_per_device_subq() -> Subquery:
    return (
        select(Telemetry)
        .distinct(Telemetry.device_id)
        .order_by(Telemetry.device_id, desc(Telemetry.timestamp))
        .subquery()
    )


@router.get("/customers", response_model=list[CustomerSummary])
async def list_customers(session: AsyncSession = Depends(get_session)) -> list[CustomerSummary]:
    online_cutoff = _online_cutoff()
    since_24h = _twenty_four_hours_ago()
    latest = _latest_per_device_subq()

    cust_stmt = (
        select(
            latest.c.customer_id,
            latest.c.customer_name,
            func.count(distinct(latest.c.site_id)).label("facility_count"),
            func.count().label("device_count"),
            func.sum(
                case((latest.c.timestamp >= online_cutoff, 1), else_=0)
            ).label("devices_online"),
        )
        .where(latest.c.customer_id.is_not(None))
        .group_by(latest.c.customer_id, latest.c.customer_name)
    )
    rows = (await session.execute(cust_stmt)).all()

    anom_stmt = (
        select(Anomaly.customer_id, func.count(Anomaly.id))
        .where(Anomaly.timestamp >= since_24h, Anomaly.customer_id.is_not(None))
        .group_by(Anomaly.customer_id)
    )
    anom_counts: dict[str, int] = {
        cid: count for cid, count in await session.execute(anom_stmt)
    }

    open_stmt = (
        select(Anomaly.customer_id, func.count(Anomaly.id))
        .where(Anomaly.status == "open", Anomaly.customer_id.is_not(None))
        .group_by(Anomaly.customer_id)
    )
    open_counts: dict[str, int] = {
        cid: count for cid, count in await session.execute(open_stmt)
    }

    p0_stmt = (
        select(Anomaly.customer_id, func.count(Anomaly.id))
        .where(
            Anomaly.status == "open",
            Anomaly.severity == "high",
            Anomaly.customer_id.is_not(None),
        )
        .group_by(Anomaly.customer_id)
    )
    p0_counts: dict[str, int] = {
        cid: count for cid, count in await session.execute(p0_stmt)
    }

    out: list[CustomerSummary] = []
    for r in rows:
        device_count = int(r.device_count)
        devices_online = int(r.devices_online or 0)
        out.append(
            CustomerSummary(
                customer_id=r.customer_id,
                customer_name=r.customer_name or r.customer_id,
                facility_count=int(r.facility_count or 0),
                device_count=device_count,
                devices_online=devices_online,
                anomalies_24h=int(anom_counts.get(r.customer_id, 0)),
                open_incidents=int(open_counts.get(r.customer_id, 0)),
                p0_incidents=int(p0_counts.get(r.customer_id, 0)),
                tenants_impacted=max(0, device_count - devices_online),
            )
        )
    out.sort(key=lambda c: c.customer_name)
    return out
