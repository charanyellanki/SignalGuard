"""Site-level rollups + global units KPI strip.

* ``GET /sites`` — one row per facility with unit count, online count,
  24-hour anomaly count, open-incident count, and low-battery count.
* ``GET /stats`` — single aggregate object for the dashboard KPI strip,
  including tenants-impacted (offline units ≈ tenants currently locked
  out of their unit).

Both queries are computed on demand against a DISTINCT ON (device_id) +
ORDER BY (device_id, timestamp DESC) subquery — i.e. "latest telemetry
per unit". For a Nokē-scale deployment you would materialize this
into a small per-site rollup table; fine for a 500-unit demo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import Subquery, case, desc, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Anomaly, Telemetry, get_session
from schemas import SiteSummary, UnitsStats

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
            latest.c.customer_id,
            latest.c.customer_name,
            latest.c.gateway_id,
            func.count().label("device_count"),
            func.sum(
                case((latest.c.timestamp >= online_cutoff, 1), else_=0)
            ).label("devices_online"),
            func.sum(
                case((latest.c.battery_voltage < LOW_BATTERY_V, 1), else_=0)
            ).label("low_battery_count"),
        )
        .where(latest.c.site_id.is_not(None))
        .group_by(
            latest.c.site_id,
            latest.c.site_name,
            latest.c.customer_id,
            latest.c.customer_name,
            latest.c.gateway_id,
        )
    )
    rows = (await session.execute(site_stmt)).all()

    anom_stmt = (
        select(Anomaly.site_id, func.count(Anomaly.id))
        .where(Anomaly.timestamp >= since_24h, Anomaly.site_id.is_not(None))
        .group_by(Anomaly.site_id)
    )
    anom_rows = (await session.execute(anom_stmt)).all()
    anom_counts: dict[str, int] = {site_id: count for site_id, count in anom_rows}

    open_stmt = (
        select(Anomaly.site_id, func.count(Anomaly.id))
        .where(Anomaly.status == "open", Anomaly.site_id.is_not(None))
        .group_by(Anomaly.site_id)
    )
    open_rows = (await session.execute(open_stmt)).all()
    open_counts: dict[str, int] = {site_id: count for site_id, count in open_rows}

    out: list[SiteSummary] = []
    for r in rows:
        out.append(
            SiteSummary(
                site_id=r.site_id,
                site_name=r.site_name or r.site_id,
                customer_id=r.customer_id,
                customer_name=r.customer_name,
                gateway_id=r.gateway_id,
                device_count=int(r.device_count),
                devices_online=int(r.devices_online or 0),
                anomalies_24h=int(anom_counts.get(r.site_id, 0)),
                open_incidents=int(open_counts.get(r.site_id, 0)),
                low_battery_count=int(r.low_battery_count or 0),
            )
        )
    out.sort(key=lambda s: (s.customer_name or "", s.site_name))
    return out


@router.get("/stats", response_model=UnitsStats)
async def units_stats(session: AsyncSession = Depends(get_session)) -> UnitsStats:
    online_cutoff = _online_cutoff()
    since_24h = _twenty_four_hours_ago()
    latest = _latest_per_device_subq()

    totals_stmt = select(
        func.count(distinct(latest.c.customer_id)).label("customers"),
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

    open_count = (
        await session.execute(
            select(func.count(Anomaly.id)).where(Anomaly.status == "open")
        )
    ).scalar_one()

    p0_count = (
        await session.execute(
            select(func.count(Anomaly.id)).where(
                Anomaly.status == "open", Anomaly.severity == "high"
            )
        )
    ).scalar_one()

    devices_total = int(t.devices_total or 0)
    devices_online = int(t.devices_online or 0)

    return UnitsStats(
        customers_count=int(t.customers or 0),
        sites_count=int(t.sites or 0),
        devices_total=devices_total,
        devices_online=devices_online,
        anomalies_24h=int(anom_count or 0),
        open_incidents=int(open_count or 0),
        p0_incidents=int(p0_count or 0),
        # An offline lock means a tenant likely cannot access their unit.
        # 1 lock ≈ 1 tenant in self-storage (each unit has its own lock).
        tenants_impacted=max(0, devices_total - devices_online),
        low_battery_count=int(t.low_battery or 0),
    )
