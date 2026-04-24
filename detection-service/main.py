"""Kafka consumer that runs two anomaly detectors per message and persists
telemetry + anomalies to Postgres.

Design notes:
* Trains models on first boot if they are missing (MODEL_DIR volume empty).
* Per-device rolling window kept in-memory for LSTM sequence scoring.
* IForest runs on every sample (point detector). LSTM runs once a device has
  ``WINDOW_SIZE`` samples buffered.
* Either detector can be disabled via env (ENABLE_ISOLATION_FOREST,
  ENABLE_LSTM_AUTOENCODER).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from collections import deque
from datetime import datetime
from pathlib import Path

from aiokafka import AIOKafkaConsumer

import train as trainer
from db import Anomaly, SessionLocal, Telemetry
from models.isolation_forest import IForestDetector
from models.lstm_autoencoder import LSTMAutoencoderDetector, WINDOW_SIZE

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
BOOTSTRAP = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
TOPIC = os.environ.get("KAFKA_TOPIC", "device-telemetry")
GROUP_ID = os.environ.get("KAFKA_GROUP_ID", "detection-service")
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/app/models/trained"))
USE_IFOREST = os.environ.get("ENABLE_ISOLATION_FOREST", "true").lower() == "true"
USE_LSTM = os.environ.get("ENABLE_LSTM_AUTOENCODER", "true").lower() == "true"

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s detector %(message)s",
)
log = logging.getLogger("detector")

# Per-device sliding windows for the LSTM autoencoder.
_windows: dict[str, deque[dict]] = {}


def _severity(score: float, threshold: float) -> str:
    """Bucket anomaly score into low / medium / high."""
    if threshold <= 0:
        return "medium"
    ratio = score / threshold
    if ratio > 3:
        return "high"
    if ratio > 1.5:
        return "medium"
    return "low"


def _classify_point_anomaly(sample: dict) -> str:
    """Cheap heuristic label for IForest flags — the model itself is agnostic,
    but the dashboard is more useful with a typed anomaly."""
    if sample["battery_voltage"] < 2.8:
        return "battery_drop"
    if sample["signal_strength_dbm"] <= -95:
        return "connectivity_flap"
    if sample["lock_events_count"] >= 5:
        return "access_spike"
    return "point_anomaly"


async def _persist(
    session_factory, telemetry_row: Telemetry, anomalies: list[Anomaly]
) -> None:
    async with session_factory() as session:
        session.add(telemetry_row)
        for a in anomalies:
            session.add(a)
        await session.commit()


async def _process(
    raw: bytes,
    iforest: IForestDetector | None,
    lstm: LSTMAutoencoderDetector | None,
) -> None:
    try:
        sample = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("dropping malformed message")
        return

    device_id: str = sample["device_id"]
    ts = datetime.fromisoformat(sample["timestamp"])

    telem = Telemetry(
        device_id=device_id,
        timestamp=ts,
        battery_voltage=sample["battery_voltage"],
        lock_events_count=sample["lock_events_count"],
        signal_strength_dbm=sample["signal_strength_dbm"],
        temperature_c=sample["temperature_c"],
    )

    anomalies: list[Anomaly] = []

    if iforest is not None:
        is_anom, score = iforest.predict(sample)
        if is_anom:
            anomalies.append(
                Anomaly(
                    device_id=device_id,
                    timestamp=ts,
                    anomaly_type=_classify_point_anomaly(sample),
                    detected_by_model="isolation_forest",
                    severity=_severity(score, threshold=1.0),
                    raw_payload=sample,
                    reason=f"iforest score={score:.3f}",
                )
            )

    if lstm is not None:
        buf = _windows.setdefault(device_id, deque(maxlen=WINDOW_SIZE))
        buf.append(sample)
        if len(buf) == WINDOW_SIZE:
            is_anom, err = lstm.predict(list(buf))
            if is_anom:
                anomalies.append(
                    Anomaly(
                        device_id=device_id,
                        timestamp=ts,
                        anomaly_type="sequence_anomaly",
                        detected_by_model="lstm_autoencoder",
                        severity=_severity(err, lstm.threshold),
                        raw_payload=sample,
                        reason=f"recon_err={err:.5f} (thr={lstm.threshold:.5f})",
                    )
                )

    await _persist(SessionLocal, telem, anomalies)
    if anomalies:
        log.info(
            "device=%s flagged by=%s",
            device_id,
            ",".join(a.detected_by_model for a in anomalies),
        )


def _ensure_models() -> tuple[IForestDetector | None, LSTMAutoencoderDetector | None]:
    iforest_path = MODEL_DIR / "iforest.joblib"
    lstm_pt = MODEL_DIR / "lstm_ae.pt"
    if (USE_IFOREST and not iforest_path.exists()) or (USE_LSTM and not lstm_pt.exists()):
        log.info("models missing — running first-boot training ...")
        trainer.main(force=False)

    iforest = IForestDetector.load(iforest_path) if USE_IFOREST else None
    lstm = LSTMAutoencoderDetector.load(MODEL_DIR) if USE_LSTM else None
    log.info(
        "loaded detectors: iforest=%s lstm=%s",
        "on" if iforest else "off",
        "on" if lstm else "off",
    )
    return iforest, lstm


async def main() -> None:
    iforest, lstm = _ensure_models()

    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id=GROUP_ID,
        enable_auto_commit=True,
        auto_offset_reset="latest",
    )
    await consumer.start()
    log.info("subscribed topic=%s group=%s", TOPIC, GROUP_ID)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    try:
        while not stop.is_set():
            batch = await consumer.getmany(timeout_ms=1000, max_records=200)
            for _tp, msgs in batch.items():
                await asyncio.gather(*(_process(m.value, iforest, lstm) for m in msgs))
    finally:
        await consumer.stop()
        log.info("detector stopped")


if __name__ == "__main__":
    asyncio.run(main())
