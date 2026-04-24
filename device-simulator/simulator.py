"""Kafka producer that emits telemetry for a fleet of virtual smart locks.

Each device runs as its own asyncio task. On every tick a device emits a
normal sample; with probability ``ANOMALY_PROBABILITY`` one of three
anomaly patterns is injected instead:

* ``battery_drop`` — battery voltage cliff (drops ~0.5V for this sample).
* ``connectivity_flap`` — RSSI floors at -100 dBm for several intervals.
* ``access_spike``    — lock_events_count jumps to ~5x the device lambda
                         for several intervals.
"""

from __future__ import annotations

import asyncio
import json
import logging
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


def _sample_normal(profile: DeviceProfile, rng: random.Random) -> dict:
    drain = (profile.battery_start_v - profile.battery_floor_v) / (
        profile.battery_life_hours * 3600.0
    )
    battery = profile.battery_start_v - drain * profile.age_seconds
    battery = max(profile.battery_floor_v, battery) + rng.gauss(0, 0.005)

    signal_dbm = profile.signal_baseline_dbm + rng.gauss(0, profile.signal_jitter_dbm)

    # Poisson-like event count via sum of Bernoulli trials (no numpy dep).
    events = sum(1 for _ in range(8) if rng.random() < profile.events_lambda / 8)

    temp = profile.temp_baseline_c + rng.gauss(0, profile.temp_jitter_c)

    return {
        "battery_voltage": round(battery, 4),
        "lock_events_count": events,
        "signal_strength_dbm": round(signal_dbm, 2),
        "temperature_c": round(temp, 2),
    }


def _maybe_inject_anomaly(
    profile: DeviceProfile, payload: dict, rng: random.Random
) -> str | None:
    """Mutates ``payload`` in place if an anomaly fires. Returns the label or None."""
    # Multi-tick anomalies in progress take priority.
    if profile.flap_streak_remaining > 0:
        profile.flap_streak_remaining -= 1
        payload["signal_strength_dbm"] = -100.0
        return "connectivity_flap"
    if profile.spike_streak_remaining > 0:
        profile.spike_streak_remaining -= 1
        payload["lock_events_count"] = max(
            payload["lock_events_count"], int(profile.events_lambda * 5) + 3
        )
        return "access_spike"

    if rng.random() >= ANOMALY_P:
        return None

    kind = rng.choice(ANOMALY_TYPES)
    if kind == "battery_drop":
        payload["battery_voltage"] = round(
            max(profile.battery_floor_v - 0.3, payload["battery_voltage"] - 0.5), 4
        )
        return "battery_drop"
    if kind == "connectivity_flap":
        profile.flap_streak_remaining = rng.randint(2, 5)
        payload["signal_strength_dbm"] = -100.0
        return "connectivity_flap"
    # access_spike
    profile.spike_streak_remaining = rng.randint(1, 3)
    payload["lock_events_count"] = max(
        payload["lock_events_count"], int(profile.events_lambda * 5) + 3
    )
    return "access_spike"


async def _run_device(
    producer: AIOKafkaProducer,
    profile: DeviceProfile,
    stop: asyncio.Event,
) -> None:
    rng = random.Random(hash(profile.device_id) & 0xFFFFFFFF)
    # Stagger devices so the whole fleet doesn't publish on the same tick.
    await asyncio.sleep(rng.uniform(0, INTERVAL_SEC))
    while not stop.is_set():
        profile.age_seconds += INTERVAL_SEC
        payload = _sample_normal(profile, rng)
        label = _maybe_inject_anomaly(profile, payload, rng)
        msg = {
            "device_id": profile.device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        if label is not None:
            msg["_injected_anomaly"] = label  # ground-truth hint; ignored by detector
        try:
            await producer.send_and_wait(
                TOPIC, json.dumps(msg).encode(), key=profile.device_id.encode()
            )
        except Exception as exc:  # pragma: no cover — network/broker issues
            log.warning("send failed for %s: %s", profile.device_id, exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=INTERVAL_SEC)
        except asyncio.TimeoutError:
            pass


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
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    try:
        await asyncio.gather(*(_run_device(producer, d, stop) for d in fleet))
    finally:
        await producer.stop()
        log.info("simulator stopped")


if __name__ == "__main__":
    asyncio.run(main())
