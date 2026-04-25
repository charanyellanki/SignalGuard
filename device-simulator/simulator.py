"""Realistic IoT smart-lock simulator → Kafka producer.

Per-tick generation is **not** independent samples — it carries state so that
traces look like real telemetry rather than random pulses:

* **Signal (RSSI)** — AR(1) random walk around the device baseline. RSSI in
  the field drifts; it doesn't jump.
* **Temperature** — diurnal sine wave (cool at 6am, warm at 6pm) blended
  with AR(1) noise.
* **Lock events** — Poisson-like with a diurnal multiplier (~zero overnight,
  peaks at 8am and 6pm) plus next-tick burstiness when the prior tick had
  events.
* **Battery** — slow linear drain over the device's rated life.

Three anomaly patterns inject with probability ``ANOMALY_PROBABILITY``,
and once started they persist for several ticks (battery cliffs and RSSI
floors don't last one sample in real life).
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import signal
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer

from device_profiles import DeviceProfile, generate_fleet

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC = os.environ.get("KAFKA_TOPIC", "device-telemetry")
DEVICE_COUNT = int(os.environ.get("DEVICE_COUNT", "500"))
INTERVAL_SEC = float(os.environ.get("EMIT_INTERVAL_SEC", "5"))
ANOMALY_P = float(os.environ.get("ANOMALY_PROBABILITY", "0.02"))

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s simulator %(message)s",
)
log = logging.getLogger("simulator")

ANOMALY_TYPES = ("battery_drop", "connectivity_flap", "access_spike")


# ─── Diurnal helpers ────────────────────────────────────────────────────────

def _diurnal_event_factor(hour: float) -> float:
    """Smart-lock activity profile. Two Gaussian peaks (morning + evening)
    on a small overnight floor. Returns a multiplier in roughly [0.05, 1.05]."""
    morning = math.exp(-((hour - 8.0) ** 2) / 4.0)   # commute / school run
    evening = math.exp(-((hour - 18.0) ** 2) / 5.0)  # home from work
    return 0.05 + 0.95 * (morning + 0.85 * evening) / 1.85


def _diurnal_temp_offset(hour: float) -> float:
    """Sinusoid: peaks ~3pm, troughs ~3am. Returns value in [-1, 1]."""
    return math.sin((hour - 9.0) / 24.0 * 2.0 * math.pi)


# ─── Per-tick sample ────────────────────────────────────────────────────────

def _sample_normal(p: DeviceProfile, rng: random.Random, hour: float) -> dict:
    # Battery: deterministic drain + tiny noise.
    drain = (p.battery_start_v - p.battery_floor_v) / (p.battery_life_hours * 3600.0)
    battery = max(p.battery_floor_v, p.battery_start_v - drain * p.age_seconds)
    battery += rng.gauss(0, 0.003)

    # Signal: AR(1) — high autocorrelation around baseline.
    if p.last_signal_dbm is None:
        p.last_signal_dbm = p.signal_baseline_dbm
    sig = (
        p.signal_ar_alpha * p.last_signal_dbm
        + (1.0 - p.signal_ar_alpha) * p.signal_baseline_dbm
        + rng.gauss(0, p.signal_jitter_dbm)
    )
    # Clip to physically plausible range.
    sig = max(-99.0, min(-30.0, sig))
    p.last_signal_dbm = sig

    # Temperature: diurnal sine wave + AR(1) smoothing.
    target_temp = p.temp_baseline_c + p.temp_amplitude_c * _diurnal_temp_offset(hour)
    if p.last_temp_c is None:
        p.last_temp_c = target_temp
    temp = 0.7 * p.last_temp_c + 0.3 * target_temp + rng.gauss(0, p.temp_jitter_c)
    p.last_temp_c = temp

    # Lock events: diurnal Poisson + burstiness.
    lam = p.events_lambda_peak * _diurnal_event_factor(hour)
    if p.last_events > 0:
        lam *= 1.0 + p.events_burstiness
    # 8 Bernoulli trials approximates Poisson without numpy.
    events = sum(1 for _ in range(8) if rng.random() < min(0.95, lam / 8.0))
    p.last_events = events

    return {
        "battery_voltage": round(battery, 4),
        "lock_events_count": events,
        "signal_strength_dbm": round(sig, 2),
        "temperature_c": round(temp, 2),
    }


# ─── Anomaly injection ──────────────────────────────────────────────────────

def _maybe_inject_anomaly(
    p: DeviceProfile, payload: dict, rng: random.Random
) -> str | None:
    """Mutates ``payload`` if an anomaly is in progress or fires this tick."""
    # Multi-tick anomalies in progress take priority.
    if p.flap_streak_remaining > 0:
        p.flap_streak_remaining -= 1
        payload["signal_strength_dbm"] = round(rng.uniform(-100.0, -97.0), 2)
        return "connectivity_flap"
    if p.spike_streak_remaining > 0:
        p.spike_streak_remaining -= 1
        payload["lock_events_count"] = max(
            payload["lock_events_count"], int(p.events_lambda_peak * 6) + 4
        )
        return "access_spike"
    if p.battery_drop_remaining > 0:
        p.battery_drop_remaining -= 1
        payload["battery_voltage"] = round(
            max(p.battery_floor_v - 0.3, payload["battery_voltage"] - 0.5), 4
        )
        return "battery_drop"

    if rng.random() >= ANOMALY_P:
        return None

    kind = rng.choice(ANOMALY_TYPES)
    if kind == "battery_drop":
        # Real cliffs persist — battery doesn't recover on its own.
        p.battery_drop_remaining = rng.randint(4, 10)
    elif kind == "connectivity_flap":
        p.flap_streak_remaining = rng.randint(3, 7)
    else:  # access_spike
        p.spike_streak_remaining = rng.randint(2, 4)
    # Recurse once to apply the freshly-set streak this same tick.
    return _maybe_inject_anomaly(p, payload, rng)


# ─── Per-device task ────────────────────────────────────────────────────────

async def _run_device(
    producer: AIOKafkaProducer,
    profile: DeviceProfile,
    stop: asyncio.Event,
) -> None:
    rng = random.Random(hash(profile.device_id) & 0xFFFFFFFF)
    # Stagger so the whole fleet doesn't burst on a single tick.
    await asyncio.sleep(rng.uniform(0, INTERVAL_SEC))

    while not stop.is_set():
        profile.age_seconds += INTERVAL_SEC
        now = datetime.now(timezone.utc)
        hour = now.hour + now.minute / 60.0

        payload = _sample_normal(profile, rng, hour)
        label = _maybe_inject_anomaly(profile, payload, rng)

        msg = {
            "device_id": profile.device_id,
            "site_id": profile.site_id,
            "site_name": profile.site_name,
            "timestamp": now.isoformat(),
            **payload,
        }
        if label is not None:
            msg["_injected_anomaly"] = label  # ground-truth hint; ignored by detector

        try:
            await producer.send_and_wait(
                TOPIC, json.dumps(msg).encode(), key=profile.device_id.encode()
            )
        except Exception as exc:  # pragma: no cover — broker hiccup
            log.warning("send failed for %s: %s", profile.device_id, exc)

        try:
            await asyncio.wait_for(stop.wait(), timeout=INTERVAL_SEC)
        except asyncio.TimeoutError:
            pass


# ─── Entrypoint ─────────────────────────────────────────────────────────────

async def main() -> None:
    fleet = generate_fleet(DEVICE_COUNT)
    log.info(
        "starting %d devices, interval=%.1fs, anomaly_p=%.3f, topic=%s",
        len(fleet), INTERVAL_SEC, ANOMALY_P, TOPIC,
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        acks="all",
        linger_ms=50,
        max_batch_size=64 * 1024,
    )
    await producer.start()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig_ in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig_, stop.set)

    try:
        await asyncio.gather(*(_run_device(producer, d, stop) for d in fleet))
    finally:
        await producer.stop()
        log.info("simulator stopped")


if __name__ == "__main__":
    asyncio.run(main())
