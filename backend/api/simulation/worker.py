"""Asyncio Nokē telemetry simulator — writes directly into Postgres (ingest)."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import random
from datetime import datetime, timezone

from ingest_core import insert_telemetry_row
from simulation.device_profiles import DeviceProfile, generate_units
from simulation import state

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
DEVICE_COUNT = int(os.environ.get("DEVICE_COUNT", "50"))
INTERVAL_SEC = float(os.environ.get("EMIT_INTERVAL_SEC", "5"))
ANOMALY_P = float(os.environ.get("ANOMALY_PROBABILITY", "0.02"))

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s simulation %(message)s",
)
log = logging.getLogger("simulation")

ANOMALY_TYPES = (
    "lock_battery_critical",
    "gateway_disconnect",
    "tenant_access_anomaly",
)


def _diurnal_event_factor(hour: float) -> float:
    morning = math.exp(-((hour - 8.0) ** 2) / 4.0)
    evening = math.exp(-((hour - 18.0) ** 2) / 5.0)
    return 0.05 + 0.95 * (morning + 0.85 * evening) / 1.85


def _diurnal_temp_offset(hour: float) -> float:
    return math.sin((hour - 9.0) / 24.0 * 2.0 * math.pi)


def _sample_normal(p: DeviceProfile, rng: random.Random, hour: float) -> dict:
    drain = (p.battery_start_v - p.battery_floor_v) / (p.battery_life_hours * 3600.0)
    battery = max(p.battery_floor_v, p.battery_start_v - drain * p.age_seconds)
    battery += rng.gauss(0, 0.003)

    if p.last_signal_dbm is None:
        p.last_signal_dbm = p.signal_baseline_dbm
    sig = (
        p.signal_ar_alpha * p.last_signal_dbm
        + (1.0 - p.signal_ar_alpha) * p.signal_baseline_dbm
        + rng.gauss(0, p.signal_jitter_dbm)
    )
    sig = max(-99.0, min(-30.0, sig))
    p.last_signal_dbm = sig

    target_temp = p.temp_baseline_c + p.temp_amplitude_c * _diurnal_temp_offset(hour)
    if p.last_temp_c is None:
        p.last_temp_c = target_temp
    temp = 0.7 * p.last_temp_c + 0.3 * target_temp + rng.gauss(0, p.temp_jitter_c)
    p.last_temp_c = temp

    lam = p.events_lambda_peak * _diurnal_event_factor(hour)
    if p.last_events > 0:
        lam *= 1.0 + p.events_burstiness
    events = sum(1 for _ in range(8) if rng.random() < min(0.95, lam / 8.0))
    p.last_events = events

    return {
        "battery_voltage": round(battery, 4),
        "lock_events_count": events,
        "signal_strength_dbm": round(sig, 2),
        "temperature_c": round(temp, 2),
    }


def _maybe_inject_anomaly(
    p: DeviceProfile, payload: dict, rng: random.Random
) -> str | None:
    if p.flap_streak_remaining > 0:
        p.flap_streak_remaining -= 1
        payload["signal_strength_dbm"] = round(rng.uniform(-100.0, -97.0), 2)
        return "gateway_disconnect"
    if p.spike_streak_remaining > 0:
        p.spike_streak_remaining -= 1
        payload["lock_events_count"] = max(
            payload["lock_events_count"], int(p.events_lambda_peak * 6) + 4
        )
        return "tenant_access_anomaly"
    if p.battery_drop_remaining > 0:
        p.battery_drop_remaining -= 1
        payload["battery_voltage"] = round(
            max(p.battery_floor_v - 0.3, payload["battery_voltage"] - 0.5), 4
        )
        return "lock_battery_critical"

    if rng.random() >= ANOMALY_P:
        return None

    kind = rng.choice(ANOMALY_TYPES)
    if kind == "lock_battery_critical":
        p.battery_drop_remaining = rng.randint(4, 10)
    elif kind == "gateway_disconnect":
        p.flap_streak_remaining = rng.randint(3, 7)
    else:
        p.spike_streak_remaining = rng.randint(2, 4)
    return _maybe_inject_anomaly(p, payload, rng)


async def _run_device(profile: DeviceProfile, stop: asyncio.Event) -> None:
    rng = random.Random(hash(profile.device_id) & 0xFFFFFFFF)
    await asyncio.sleep(rng.uniform(0, INTERVAL_SEC))

    while not stop.is_set():
        if state.paused.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            continue

        profile.age_seconds += INTERVAL_SEC
        now = datetime.now(timezone.utc)
        hour = now.hour + now.minute / 60.0

        payload = _sample_normal(profile, rng, hour)
        _maybe_inject_anomaly(profile, payload, rng)

        try:
            await insert_telemetry_row(
                device_id=profile.device_id,
                timestamp=now,
                battery_voltage=payload["battery_voltage"],
                lock_events_count=payload["lock_events_count"],
                signal_strength_dbm=payload["signal_strength_dbm"],
                temperature_c=payload["temperature_c"],
                customer_id=profile.customer_id,
                customer_name=profile.customer_name,
                site_id=profile.site_id,
                site_name=profile.site_name,
                gateway_id=profile.gateway_id,
                building=profile.building,
                unit_id=profile.unit_id,
            )
        except Exception as exc:  # pragma: no cover
            log.warning("ingest failed for %s: %s", profile.device_id, exc)

        try:
            await asyncio.wait_for(stop.wait(), timeout=INTERVAL_SEC)
        except asyncio.TimeoutError:
            pass


async def run_forever() -> None:
    units = generate_units(DEVICE_COUNT)
    log.info(
        "simulation: %d units, interval=%.1fs, anomaly_p=%.3f (in-process ingest)",
        len(units),
        INTERVAL_SEC,
        ANOMALY_P,
    )
    stop = asyncio.Event()
    try:
        await asyncio.gather(*(_run_device(d, stop) for d in units))
    except asyncio.CancelledError:
        log.info("simulation worker cancelled")
        stop.set()
        return
