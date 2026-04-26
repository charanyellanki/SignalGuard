"""Telemetry scorer that runs IsolationForest + LSTM autoencoder per sample
and persists anomalies to Postgres.

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
import logging
import os
import signal
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update

import train as trainer
from db import Anomaly, SessionLocal, Telemetry
from models.isolation_forest import IForestDetector
from models.lstm_autoencoder import LSTMAutoencoderDetector, WINDOW_SIZE

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/app/models/trained"))
USE_IFOREST = os.environ.get("ENABLE_ISOLATION_FOREST", "true").lower() == "true"
USE_LSTM = os.environ.get("ENABLE_LSTM_AUTOENCODER", "true").lower() == "true"
COOLDOWN_SEC = int(os.environ.get("ANOMALY_COOLDOWN_SEC", "60"))
POLL_INTERVAL_SEC = float(os.environ.get("POLL_INTERVAL_SEC", "0.5"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "200"))

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
    """Cheap heuristic label for IForest flags, using Nokē playbook language.

    The model is feature-agnostic; these labels just give the dashboard a
    typed reason that maps to the operations playbook:

        lock_battery_critical    → schedule a battery swap (cheap, batchable)
        gateway_disconnect       → escalate to network ops / carrier
        tenant_access_anomaly    → review video, contact tenant, security
        telemetry_anomaly        → catch-all (analyst review)
    """
    if sample["battery_voltage"] < 2.85:
        return "lock_battery_critical"
    if sample["signal_strength_dbm"] <= -95.0:
        return "gateway_disconnect"
    if sample["lock_events_count"] >= 5:
        return "tenant_access_anomaly"
    return "telemetry_anomaly"


async def _persist(telemetry_row: Telemetry, anomalies: list[Anomaly]) -> None:
    async with SessionLocal() as session:
        session.add(telemetry_row)
        for a in anomalies:
            session.add(a)
        await session.commit()


def _identity_fields(sample: dict) -> dict:
    """The placement metadata we copy from the inbound message into both
    the Telemetry row and any flagged Anomaly row, so that the API can
    filter / group by customer and facility without joins."""
    return {
        "device_id":     sample["device_id"],
        "customer_id":   sample.get("customer_id"),
        "customer_name": sample.get("customer_name"),
        "site_id":       sample.get("site_id"),
        "site_name":     sample.get("site_name"),
        "gateway_id":    sample.get("gateway_id"),
        "building":      sample.get("building"),
        "unit_id":       sample.get("unit_id"),
    }


async def _process(
    telemetry_row: Telemetry,
    iforest: IForestDetector | None,
    lstm: LSTMAutoencoderDetector | None,
) -> None:
    # Convert the persisted row into the dict format the detectors expect.
    sample = {
        "device_id": telemetry_row.device_id,
        "customer_id": telemetry_row.customer_id,
        "customer_name": telemetry_row.customer_name,
        "site_id": telemetry_row.site_id,
        "site_name": telemetry_row.site_name,
        "gateway_id": telemetry_row.gateway_id,
        "building": telemetry_row.building,
        "unit_id": telemetry_row.unit_id,
        "timestamp": telemetry_row.timestamp.isoformat(),
        "battery_voltage": telemetry_row.battery_voltage,
        "lock_events_count": telemetry_row.lock_events_count,
        "signal_strength_dbm": telemetry_row.signal_strength_dbm,
        "temperature_c": telemetry_row.temperature_c,
    }

    device_id: str = telemetry_row.device_id
    ts = telemetry_row.timestamp
    ident = _identity_fields(sample)

    anomalies: list[Anomaly] = []

    if iforest is not None and not _in_cooldown(device_id, "isolation_forest", ts):
        is_anom, score = iforest.predict(sample)
        if is_anom:
            anomalies.append(
                Anomaly(
                    **ident,
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
                        **ident,
                        timestamp=ts,
                        anomaly_type="behavioral_drift",
                        detected_by_model="lstm_autoencoder",
                        severity=_severity(err, lstm.threshold),
                        raw_payload=sample,
                        reason=f"recon_err={err:.5f} (thr={lstm.threshold:.5f})",
                    )
                )
                _set_cooldown(device_id, "lstm_autoencoder", ts)

    # Persist anomalies (telemetry itself is already stored by the API).
    if anomalies:
        async with SessionLocal() as session:
            for a in anomalies:
                session.add(a)
            await session.commit()
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

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig_ in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig_, stop.set)

    try:
        while not stop.is_set():
            async with SessionLocal() as session:
                # Claim a batch of unprocessed rows using SKIP LOCKED so multiple
                # detector replicas can scale out safely.
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

                # Mark claimed rows processed up-front to avoid duplicate work if we crash
                # after releasing the row lock.
                now = datetime.now(timezone.utc)
                ids = [r.id for r in rows]
                await session.execute(
                    update(Telemetry)
                    .where(Telemetry.id.in_(ids))
                    .values(processed=True, processed_at=now)
                )
                await session.commit()

            # Process outside the transaction to keep DB locks short.
            await asyncio.gather(*(_process(r, iforest, lstm) for r in rows))
    finally:
        log.info("detector stopped")


# Suppress unused-import warning — datetime.timezone needed for type clarity in Anomaly
_ = timezone

if __name__ == "__main__":
    asyncio.run(main())
