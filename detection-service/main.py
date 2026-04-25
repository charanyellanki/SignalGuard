"""Kafka consumer that runs IsolationForest + LSTM autoencoder per message
and persists telemetry + anomalies to Postgres.

False-positive controls:
* IForest contamination is set in train.py (0.005) — point anomalies are rare.
* LSTM threshold is the 99th percentile of training reconstruction error.
* Per-(device, model) **cooldown** — once a device is flagged by a model,
  further flags from the same model are suppressed for ``COOLDOWN_SEC``.
  This prevents a device that is genuinely in trouble from spamming the
  feed every 5s for the duration of an episode.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from collections import deque
from datetime import datetime, timedelta, timezone
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
COOLDOWN_SEC = int(os.environ.get("ANOMALY_COOLDOWN_SEC", "60"))

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s detector %(message)s",
)
log = logging.getLogger("detector")

# Per-device sliding windows for the LSTM autoencoder.
_windows: dict[str, deque[dict]] = {}
# Per-(device, model) cooldown. Suppress duplicate flags during the same episode.
_cooldown_until: dict[tuple[str, str], datetime] = {}


def _in_cooldown(device_id: str, model_name: str, now: datetime) -> bool:
    until = _cooldown_until.get((device_id, model_name))
    return until is not None and now < until


def _set_cooldown(device_id: str, model_name: str, now: datetime) -> None:
    _cooldown_until[(device_id, model_name)] = now + timedelta(seconds=COOLDOWN_SEC)


def _severity(score: float, threshold: float) -> str:
    if threshold <= 0:
        return "medium"
    ratio = score / threshold
    if ratio > 3:
        return "high"
    if ratio > 1.5:
        return "medium"
    return "low"


def _classify_point_anomaly(sample: dict) -> str:
    """Cheap heuristic label for IForest flags, using Noke domain language.

    The model is feature-agnostic; these labels just give the dashboard a
    typed reason that maps to the operations playbook (battery dispatch,
    gateway escalation, after-hours access review)."""
    if sample["battery_voltage"] < 2.85:
        return "battery_critical"
    if sample["signal_strength_dbm"] <= -95.0:
        return "device_offline"
    if sample["lock_events_count"] >= 5:
        return "unusual_access_pattern"
    return "point_anomaly"


async def _persist(telemetry_row: Telemetry, anomalies: list[Anomaly]) -> None:
    async with SessionLocal() as session:
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
    site_id = sample.get("site_id")
    site_name = sample.get("site_name")
    ts = datetime.fromisoformat(sample["timestamp"])

    telem = Telemetry(
        device_id=device_id,
        site_id=site_id,
        site_name=site_name,
        timestamp=ts,
        battery_voltage=sample["battery_voltage"],
        lock_events_count=sample["lock_events_count"],
        signal_strength_dbm=sample["signal_strength_dbm"],
        temperature_c=sample["temperature_c"],
    )

    anomalies: list[Anomaly] = []

    if iforest is not None and not _in_cooldown(device_id, "isolation_forest", ts):
        is_anom, score = iforest.predict(sample)
        if is_anom:
            anomalies.append(
                Anomaly(
                    device_id=device_id,
                    site_id=site_id,
                    site_name=site_name,
                    timestamp=ts,
                    anomaly_type=_classify_point_anomaly(sample),
                    detected_by_model="isolation_forest",
                    severity=_severity(score, threshold=1.0),
                    raw_payload=sample,
                    reason=f"iforest score={score:.3f}",
                )
            )
            _set_cooldown(device_id, "isolation_forest", ts)

    if lstm is not None:
        buf = _windows.setdefault(device_id, deque(maxlen=WINDOW_SIZE))
        buf.append(sample)
        if len(buf) == WINDOW_SIZE and not _in_cooldown(device_id, "lstm_autoencoder", ts):
            is_anom, err = lstm.predict(list(buf))
            if is_anom:
                anomalies.append(
                    Anomaly(
                        device_id=device_id,
                        site_id=site_id,
                        site_name=site_name,
                        timestamp=ts,
                        anomaly_type="sequence_anomaly",
                        detected_by_model="lstm_autoencoder",
                        severity=_severity(err, lstm.threshold),
                        raw_payload=sample,
                        reason=f"recon_err={err:.5f} (thr={lstm.threshold:.5f})",
                    )
                )
                _set_cooldown(device_id, "lstm_autoencoder", ts)

    await _persist(telem, anomalies)
    if anomalies:
        log.info(
            "device=%s flagged by=%s",
            device_id,
            ",".join(a.detected_by_model for a in anomalies),
        )


def _ensure_models() -> tuple[IForestDetector | None, LSTMAutoencoderDetector | None]:
    """Train on first boot OR if MODEL_VERSION has been bumped since last save."""
    iforest_path = MODEL_DIR / "iforest.joblib"
    lstm_pt = MODEL_DIR / "lstm_ae.pt"

    needs_train = (USE_IFOREST and not iforest_path.exists()) or (
        USE_LSTM and not lstm_pt.exists()
    )
    saved = trainer._saved_version()
    if not needs_train and saved != trainer.MODEL_VERSION:
        log.info("model version mismatch (saved=%s, expected=%d) — retraining",
                 saved, trainer.MODEL_VERSION)
        needs_train = True

    if needs_train:
        log.info("running training pass ...")
        trainer.main(force=True)

    iforest = IForestDetector.load(iforest_path) if USE_IFOREST else None
    lstm = LSTMAutoencoderDetector.load(MODEL_DIR) if USE_LSTM else None
    log.info(
        "loaded detectors: iforest=%s lstm=%s cooldown=%ds",
        "on" if iforest else "off",
        "on" if lstm else "off",
        COOLDOWN_SEC,
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
    for sig_ in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig_, stop.set)

    try:
        while not stop.is_set():
            batch = await consumer.getmany(timeout_ms=1000, max_records=200)
            for _tp, msgs in batch.items():
                await asyncio.gather(*(_process(m.value, iforest, lstm) for m in msgs))
    finally:
        await consumer.stop()
        log.info("detector stopped")


# Suppress unused-import warning — datetime.timezone needed for type clarity in Anomaly
_ = timezone

if __name__ == "__main__":
    asyncio.run(main())
