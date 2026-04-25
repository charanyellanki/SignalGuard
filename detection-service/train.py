"""Train both detectors on synthetic *normal* telemetry whose distribution
mirrors the device-simulator output (no domain shift between train and
production).

Auto-runs from ``main.py`` on first boot and whenever ``MODEL_VERSION``
bumps. ``--force`` retrains unconditionally.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np

from models.isolation_forest import IForestDetector
from models.lstm_autoencoder import LSTMAutoencoderDetector, N_FEATURES, WINDOW_SIZE
from synthetic import generate_normal_traces

# Bump this whenever the feature schema, generator, or hyperparameters change
# so older saved models on the volume get replaced on next boot.
MODEL_VERSION = 2

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/app/models/trained"))
IFOREST_PATH = MODEL_DIR / "iforest.joblib"
LSTM_DIR = MODEL_DIR
VERSION_PATH = MODEL_DIR / "VERSION"

log = logging.getLogger("train")


def _windowize(traces: list[np.ndarray]) -> np.ndarray:
    windows: list[np.ndarray] = []
    for series in traces:
        for i in range(len(series) - WINDOW_SIZE + 1):
            windows.append(series[i : i + WINDOW_SIZE])
    if not windows:
        return np.empty((0, WINDOW_SIZE, N_FEATURES), dtype=np.float32)
    return np.stack(windows)


def _saved_version() -> int | None:
    if not VERSION_PATH.exists():
        return None
    try:
        return int(json.loads(VERSION_PATH.read_text())["version"])
    except (ValueError, KeyError):
        return None


def main(force: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    saved = _saved_version()
    has_artifacts = IFOREST_PATH.exists() and (LSTM_DIR / "lstm_ae.pt").exists()
    if has_artifacts and saved == MODEL_VERSION and not force:
        log.info(
            "models v%d already present at %s — skipping (use --force to retrain)",
            MODEL_VERSION, MODEL_DIR,
        )
        return

    if has_artifacts and saved != MODEL_VERSION:
        log.info("model version mismatch (saved=%s, expected=%d) — retraining",
                 saved, MODEL_VERSION)

    log.info("generating synthetic training data (matches simulator distribution)")
    # 12 hours per device covers a full diurnal cycle plus margin.
    traces = generate_normal_traces(n_devices=80, n_steps=720, seed=0)
    flat = np.concatenate(traces, axis=0)
    log.info("iforest training set: %s", flat.shape)
    iforest = IForestDetector.train(flat, contamination=0.005)
    iforest.save(IFOREST_PATH)
    log.info("saved iforest -> %s", IFOREST_PATH)

    windows = _windowize(traces)
    log.info("lstm-ae training set: %s", windows.shape)
    lstm = LSTMAutoencoderDetector.train(windows, epochs=20, threshold_pct=99.0)
    lstm.save(LSTM_DIR)
    log.info(
        "saved lstm-ae -> %s (threshold=%.5f @ p99)",
        LSTM_DIR / "lstm_ae.pt", lstm.threshold,
    )

    VERSION_PATH.write_text(json.dumps({"version": MODEL_VERSION}))
    log.info("wrote VERSION=%d", MODEL_VERSION)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="retrain even if models exist")
    args = ap.parse_args()
    main(force=args.force)
