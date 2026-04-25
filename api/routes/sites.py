"""Site-level rollups + global fleet KPI strip.

* ``GET /sites`` — one row per facility with device count, online count,
  24-hour anomaly count, and low-battery count.
* ``GET /stats`` — single aggregate object for the dashboard KPI strip.

Both queries are computed on demand against a DISTINCT ON (device_id) +
ORDER BY (device_id, timestamp DESC) subquery — i.e. "latest telemetry per
device". For a real Noke-scale fleet you would materialize this into a
small per-site rollup table; fine for a 500-device demo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import Subquery, case, desc, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Anomaly, Telemetry, get_session
from schemas import FleetStats, SiteSummary

router = APIRouter(tags=["sites"])

ONLINE_THRESHOLD_SEC = 30
LOW_BATTERY_V = 2.9


def _online_cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=ONLINE_THRESHOLD_SEC)


def _twenty_four_hours_ago() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=24)


def _latest_per_device_subq() -> Subquery:
    """Subquery: one row per device, the row being the most recent telemetry."""
    return (
        select(Telemetry)
        .distinct(Telemetry.device_id)
        .order_by(Telemetry.device_id, desc(Telemetry.timestamp))
        .subquery()
    )


@router.get("/sites", response_model=list[SiteSummary])
async def list_sites(session: AsyncSession = Depends(get_session)) -> list[SiteSummary]:
    online_cutoff = _online_cutoff()
    since_24h = _twenty_four_hours_ago()
    latest = _latest_per_device_subq()

    site_stmt = (
        select(
            latest.c.site_id,
            latest.c.site_name,
            func.count().label("device_count"),
            func.sum(
                case((latest.c.timestamp >= online_cutoff, 1), else_=0)
            ).label("devices_online"),
            func.sum(
                case((latest.c.battery_voltage < LOW_BATTERY_V, 1), else_=0)
            ).label("low_battery_count"),
        )
        .where(latest.c.site_id.is_not(None))
        .group_by(latest.c.site_id, latest.c.site_name)
    )
    rows = (await session.execute(site_stmt)).all()

    anom_stmt = (
        select(Anomaly.site_id, func.count(Anomaly.id))
        .where(Anomaly.timestamp >= since_24h, Anomaly.site_id.is_not(None))
        .group_by(Anomaly.site_id)
    )
    anom_rows = (await session.execute(anom_stmt)).all()
    anom_counts: dict[str, int] = {site_id: count for site_id, count in anom_rows}

    out: list[SiteSummary] = []
    for r in rows:
        out.append(
            SiteSummary(
                site_id=r.site_id,
                site_name=r.site_name or r.site_id,
                device_count=int(r.device_count),
                devices_online=int(r.devices_online or 0),
                anomalies_24h=int(anom_counts.get(r.site_id, 0)),
                low_battery_count=int(r.low_battery_count or 0),
            )
        )
    out.sort(key=lambda s: s.site_name)
    return out


@router.get("/stats", response_model=FleetStats)
async def fleet_stats(session: AsyncSession = Depends(get_session)) -> FleetStats:
    online_cutoff = _online_cutoff()
    since_24h = _twenty_four_hours_ago()
    latest = _latest_per_device_subq()

    totals_stmt = select(
        func.count(distinct(latest.c.site_id)).label("sites"),
        func.count().label("devices_total"),
        func.sum(
            case((latest.c.timestamp >= online_cutoff, 1), else_=0)
        ).label("devices_online"),
        func.sum(
            case((latest.c.battery_voltage < LOW_BATTERY_V, 1), else_=0)
        ).label("low_battery"),
    )
    t = (await session.execute(totals_stmt)).one()

    anom_count = (
        await session.execute(
            select(func.count(Anomaly.id)).where(Anomaly.timestamp >= since_24h)
        )
    ).scalar_one()

    return FleetStats(
        sites_count=int(t.sites or 0),
        devices_total=int(t.devices_total or 0),
        devices_online=int(t.devices_online or 0),
        anomalies_24h=int(anom_count or 0),
        low_battery_count=int(t.low_battery or 0),
    )
