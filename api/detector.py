"""Lightweight rule-based telemetry detector.

Runs as an asyncio background task inside the API process, polling the
``telemetry`` table for unprocessed rows and writing ``Anomaly`` rows when
sensor readings cross the Nokē operations-playbook thresholds.

This replaces the standalone detection-service (which required scikit-learn +
PyTorch) so the whole backend fits in one free Render web service.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from db import Anomaly, SessionLocal, Telemetry

log = logging.getLogger("detector")

POLL_INTERVAL_SEC = float(os.environ.get("POLL_INTERVAL_SEC", "1.0"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100"))
COOLDOWN_SEC = int(os.environ.get("ANOMALY_COOLDOWN_SEC", "60"))

# ── Thresholds (Nokē operations playbook) ──────────────────────────────────
_BATTERY_CRITICAL_V = 2.9       # below this → schedule battery swap
_SIGNAL_FLOOR_DBM = -95.0       # below this → escalate to network ops
_ACCESS_BURST_COUNT = 5         # at or above this → review tenant access


# Per-device cooldown so one bad episode doesn't spam the incidents queue.
_cooldown_until: dict[str, datetime] = {}


def _in_cooldown(device_id: str, now: datetime) -> bool:
    until = _cooldown_until.get(device_id)
    return until is not None and now < until


def _set_cooldown(device_id: str, now: datetime) -> None:
    _cooldown_until[device_id] = now + timedelta(seconds=COOLDOWN_SEC)


def _classify(row: Telemetry) -> tuple[str, str, str] | None:
    """Return (anomaly_type, severity, reason) or None if the row is normal."""
    if row.battery_voltage < _BATTERY_CRITICAL_V:
        sev = "high" if row.battery_voltage < 2.7 else "medium"
        return (
            "lock_battery_critical",
            sev,
            f"battery={row.battery_voltage:.3f}V (thr={_BATTERY_CRITICAL_V}V)",
        )
    if row.signal_strength_dbm <= _SIGNAL_FLOOR_DBM:
        sev = "high" if row.signal_strength_dbm < -97.0 else "medium"
        return (
            "gateway_disconnect",
            sev,
            f"rssi={row.signal_strength_dbm:.1f}dBm (thr={_SIGNAL_FLOOR_DBM}dBm)",
        )
    if row.lock_events_count >= _ACCESS_BURST_COUNT:
        sev = "high" if row.lock_events_count >= 8 else "medium"
        return (
            "tenant_access_anomaly",
            sev,
            f"lock_events={row.lock_events_count} (thr={_ACCESS_BURST_COUNT})",
        )
    return None


async def _process_batch(rows: list[Telemetry]) -> None:
    now = datetime.now(timezone.utc)
    anomalies: list[Anomaly] = []

    for row in rows:
        if _in_cooldown(row.device_id, now):
            continue
        result = _classify(row)
        if result is None:
            continue
        anomaly_type, severity, reason = result
        anomalies.append(
            Anomaly(
                device_id=row.device_id,
                customer_id=row.customer_id,
                customer_name=row.customer_name,
                site_id=row.site_id,
                site_name=row.site_name,
                gateway_id=row.gateway_id,
                building=row.building,
                unit_id=row.unit_id,
                timestamp=row.timestamp,
                anomaly_type=anomaly_type,
                detected_by_model="rule_engine",
                severity=severity,
                raw_payload={
                    "battery_voltage": row.battery_voltage,
                    "signal_strength_dbm": row.signal_strength_dbm,
                    "lock_events_count": row.lock_events_count,
                    "temperature_c": row.temperature_c,
                },
                reason=reason,
            )
        )
        _set_cooldown(row.device_id, now)

    if not anomalies:
        return

    async with SessionLocal() as session:
        for a in anomalies:
            session.add(a)
        await session.commit()

    log.info(
        "flagged %d anomaly(ies): %s",
        len(anomalies),
        ", ".join(f"{a.device_id}/{a.anomaly_type}" for a in anomalies),
    )


async def poll_forever() -> None:
    """Long-running task started in the FastAPI lifespan."""
    log.info(
        "detector started — poll_interval=%.1fs batch=%d cooldown=%ds",
        POLL_INTERVAL_SEC,
        BATCH_SIZE,
        COOLDOWN_SEC,
    )
    while True:
        try:
            async with SessionLocal() as session:
                stmt = (
                    select(Telemetry)
                    .where(Telemetry.processed.is_(False))
                    .order_by(Telemetry.id)
                    .limit(BATCH_SIZE)
                    .with_for_update(skip_locked=True)
                )
                rows = (await session.execute(stmt)).scalars().all()

                if not rows:
                    await asyncio.sleep(POLL_INTERVAL_SEC)
                    continue

                ids = [r.id for r in rows]
                now = datetime.now(timezone.utc)
                await session.execute(
                    update(Telemetry)
                    .where(Telemetry.id.in_(ids))
                    .values(processed=True, processed_at=now)
                )
                await session.commit()

            await _process_batch(rows)

        except asyncio.CancelledError:
            log.info("detector stopped")
            return
        except Exception as exc:
            log.warning("detector error: %s — retrying in 5s", exc)
            await asyncio.sleep(5)
