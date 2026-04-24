"""Train Isolation Forest + LSTM autoencoder on synthetic normal telemetry.

Invoked automatically by ``main.py`` on first boot if the model directory is
empty. ``--force`` retrains unconditionally.

The synthetic-data generator mirrors the distribution produced by
``device-simulator`` when no anomaly is injected, so models learn the same
baseline operating envelope they'll see in production.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
from pathlib import Path

import numpy as np

from models.isolation_forest import FEATURE_ORDER, IForestDetector
from models.lstm_autoencoder import N_FEATURES, WINDOW_SIZE, LSTMAutoencoderDetector

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/app/models/trained"))
IFOREST_PATH = MODEL_DIR / "iforest.joblib"
LSTM_DIR = MODEL_DIR  # saves lstm_ae.pt + lstm_ae.json into the same dir

log = logging.getLogger("train")


def _synthetic_fleet(n_devices: int, n_steps: int, seed: int = 0) -> np.ndarray:
    """Generate (n_devices * n_steps, 4) normal samples."""
    rng = random.Random(seed)
    rows: list[list[float]] = []
    for _ in range(n_devices):
        bat = rng.uniform(3.15, 3.30)
        bat_floor = rng.uniform(2.60, 2.75)
        bat_drain = (bat - bat_floor) / (n_steps * 2)
        sig = rng.uniform(-70, -45)
        sig_j = rng.uniform(1.0, 3.0)
        lam = rng.uniform(0.05, 0.6)
        t = rng.uniform(17, 24)
        t_j = rng.uniform(0.3, 1.0)
        for step in range(n_steps):
            b = max(bat_floor, bat - bat_drain * step) + rng.gauss(0, 0.005)
            s = sig + rng.gauss(0, sig_j)
            e = sum(1 for _ in range(8) if rng.random() < lam / 8)
            c = t + rng.gauss(0, t_j)
            rows.append([b, e, s, c])
    return np.asarray(rows, dtype=np.float32)


def _windowize(samples_per_device: list[np.ndarray]) -> np.ndarray:
    """Slice each device's time series into sliding windows of WINDOW_SIZE."""
    windows: list[np.ndarray] = []
    for series in samples_per_device:
        for i in range(len(series) - WINDOW_SIZE + 1):
            windows.append(series[i : i + WINDOW_SIZE])
    return np.stack(windows) if windows else np.empty((0, WINDOW_SIZE, N_FEATURES))


def _synthetic_windows(n_devices: int, n_steps: int, seed: int = 1) -> np.ndarray:
    flat = _synthetic_fleet(n_devices, n_steps, seed=seed)
    per_device = np.split(flat, n_devices)
    return _windowize(per_device)


def main(force: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    already = IFOREST_PATH.exists() and (LSTM_DIR / "lstm_ae.pt").exists()
    if already and not force:
        log.info("models already present at %s — skipping (use --force to retrain)", MODEL_DIR)
        return

    log.info("feature order: %s", FEATURE_ORDER)

    log.info("generating synthetic training data ...")
    x_flat = _synthetic_fleet(n_devices=80, n_steps=300)
    log.info("iforest training set: %s", x_flat.shape)
    iforest = IForestDetector.train(x_flat, contamination=0.02)
    iforest.save(IFOREST_PATH)
    log.info("saved iforest -> %s", IFOREST_PATH)

    windows = _synthetic_windows(n_devices=80, n_steps=300)
    log.info("lstm-ae training set: %s", windows.shape)
    lstm = LSTMAutoencoderDetector.train(windows, epochs=15)
    lstm.save(LSTM_DIR)
    log.info(
        "saved lstm-ae -> %s (threshold=%.5f)",
        LSTM_DIR / "lstm_ae.pt", lstm.threshold,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="retrain even if models exist")
    args = ap.parse_args()
    main(force=args.force)
