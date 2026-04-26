"""ML telemetry scoring (IForest + LSTM AE) in-process with the API."""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update

import train as trainer
from db import Anomaly, SessionLocal, Telemetry
from detectors.isolation_forest import IForestDetector
from detectors.lstm_autoencoder import LSTMAutoencoderDetector, WINDOW_SIZE
from wandb_model import download_production_models

log = logging.getLogger("detector")

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/app/models/trained"))
USE_IFOREST = os.environ.get("ENABLE_ISOLATION_FOREST", "true").lower() == "true"
USE_LSTM = os.environ.get("ENABLE_LSTM_AUTOENCODER", "true").lower() == "true"
COOLDOWN_SEC = int(os.environ.get("ANOMALY_COOLDOWN_SEC", "60"))
POLL_INTERVAL_SEC = float(os.environ.get("POLL_INTERVAL_SEC", "0.5"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "200"))
REQUIRE_WANDB_MODEL = os.environ.get("REQUIRE_WANDB_MODEL", "false").lower() == "true"
ALLOW_BOOTSTRAP_TRAIN = os.environ.get("ALLOW_BOOTSTRAP_TRAIN", "true").lower() == "true"

_windows: dict[str, deque[dict]] = {}
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
    if sample["battery_voltage"] < 2.85:
        return "lock_battery_critical"
    if sample["signal_strength_dbm"] <= -95.0:
        return "gateway_disconnect"
    if sample["lock_events_count"] >= 5:
        return "tenant_access_anomaly"
    return "telemetry_anomaly"


def _identity_fields(sample: dict) -> dict:
    return {
        "device_id": sample["device_id"],
        "customer_id": sample.get("customer_id"),
        "customer_name": sample.get("customer_name"),
        "site_id": sample.get("site_id"),
        "site_name": sample.get("site_name"),
        "gateway_id": sample.get("gateway_id"),
        "building": sample.get("building"),
        "unit_id": sample.get("unit_id"),
    }


async def _process(
    telemetry_row: Telemetry,
    iforest: IForestDetector | None,
    lstm: LSTMAutoencoderDetector | None,
) -> None:
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
        if len(buf) == WINDOW_SIZE and not _in_cooldown(
            device_id, "lstm_autoencoder", ts
        ):
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


def _model_files_present() -> bool:
    if USE_IFOREST and not (MODEL_DIR / "iforest.joblib").is_file():
        return False
    if USE_LSTM and not (MODEL_DIR / "lstm_ae.pt").is_file():
        return False
    return True


def _ensure_models() -> tuple[IForestDetector | None, LSTMAutoencoderDetector | None]:
    iforest_path = MODEL_DIR / "iforest.joblib"
    lstm_pt = MODEL_DIR / "lstm_ae.pt"

    if not _model_files_present():
        download_production_models(MODEL_DIR)

    needs_train = (USE_IFOREST and not iforest_path.is_file()) or (
        USE_LSTM and not lstm_pt.is_file()
    )
    if not needs_train:
        saved = trainer._saved_version()
        if saved is not None and saved != trainer.MODEL_VERSION:
            log.info(
                "model version mismatch (saved=%s, expected=%d) — retraining",
                saved,
                trainer.MODEL_VERSION,
            )
            needs_train = True

    if needs_train:
        if REQUIRE_WANDB_MODEL:
            raise RuntimeError(
                "Trained model files are missing. Run the retrain GitHub Action "
                "or set WANDB_API_KEY and publish a model artifact, "
                "or set REQUIRE_WANDB_MODEL=false and ALLOW_BOOTSTRAP_TRAIN=true for local use."
            )
        if not ALLOW_BOOTSTRAP_TRAIN:
            raise RuntimeError(
                "Trained model files missing; set ALLOW_BOOTSTRAP_TRAIN=true for "
                "synthetic on-boot training, or provide W&B models."
            )
        log.info("no models on disk — running small synthetic training pass (bootstrap)")
        from synthetic import generate_normal_traces

        small = generate_normal_traces(n_devices=40, n_steps=400, seed=0)
        trainer.run_training(
            traces=small,
            force=True,
            skip_wandb=True,
            mark_production=False,
        )

    iforest = IForestDetector.load(iforest_path) if USE_IFOREST else None
    lstm = LSTMAutoencoderDetector.load(MODEL_DIR) if USE_LSTM else None
    log.info(
        "loaded detectors: iforest=%s lstm=%s cooldown=%ds",
        "on" if iforest else "off",
        "on" if lstm else "off",
        COOLDOWN_SEC,
    )
    return iforest, lstm


async def poll_forever() -> None:
    # Bootstrap (sklearn/torch) is CPU-heavy and synchronous — run off the
    # event loop so Uvicorn can answer /health and Render can bind PORT.
    iforest, lstm = await asyncio.to_thread(_ensure_models)
    log.info("detector loop started, poll=%.1fs", POLL_INTERVAL_SEC)
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

                now = datetime.now(timezone.utc)
                ids = [r.id for r in rows]
                await session.execute(
                    update(Telemetry)
                    .where(Telemetry.id.in_(ids))
                    .values(processed=True, processed_at=now)
                )
                await session.commit()

            await asyncio.gather(*(_process(r, iforest, lstm) for r in rows))

        except asyncio.CancelledError:
            log.info("detector loop cancelled")
            return
        except Exception as exc:  # pragma: no cover
            log.exception("detector error: %s", exc)
            await asyncio.sleep(5)


_ = timezone
