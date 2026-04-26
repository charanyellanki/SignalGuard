"""Train IsolationForest + LSTM autoencoder; log to W&B; register model Artifact.

* Synthetic data (default) — matches ``synthetic.py`` (no Supabase required).
* ``--from-db`` — pull recent rows from ``DATABASE_URL`` (set in CI / local).

Bump ``MODEL_VERSION`` when schema or training hyperparams change.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np

from detectors.isolation_forest import IForestDetector
from detectors.lstm_autoencoder import LSTMAutoencoderDetector, N_FEATURES, WINDOW_SIZE
from synthetic import generate_normal_traces

MODEL_VERSION = 4
# v4: W&B Artifacts + optional Supabase-sourced training rows

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/app/models/trained"))
IFOREST_PATH = MODEL_DIR / "iforest.joblib"
LSTM_DIR = MODEL_DIR
VERSION_PATH = MODEL_DIR / "VERSION"

log = logging.getLogger("train")

WANDB_MODEL_NAME = os.environ.get("WANDB_MODEL_ARTIFACT", "signalguard-models")


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
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def run_training(
    *,
    traces: list[np.ndarray],
    force: bool = False,
    skip_wandb: bool = False,
    mark_production: bool = True,
) -> None:
    """Train, save to disk, log to W&B, register artifact."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    saved = _saved_version()
    has_artifacts = IFOREST_PATH.exists() and (LSTM_DIR / "lstm_ae.pt").exists()
    if has_artifacts and saved == MODEL_VERSION and not force:
        log.info(
            "models v%d already present at %s — skipping (use force=True to retrain)",
            MODEL_VERSION,
            MODEL_DIR,
        )
        return

    run = None
    if not skip_wandb and os.environ.get("WANDB_API_KEY"):
        import wandb

        run = wandb.init(
            project=os.environ.get("WANDB_PROJECT") or "signalguard",
            entity=os.environ.get("WANDB_ENTITY") or None,
            name=f"train-v{MODEL_VERSION}",
            config={
                "model_version": MODEL_VERSION,
                "n_trace_arrays": len(traces),
                "iforest_contamination": 0.005,
                "lstm_epochs": 20,
            },
        )

    flat = np.concatenate(traces, axis=0)
    log.info("iforest training set: %s", flat.shape)
    if run is not None:
        run.log({"iforest/flat_rows": flat.shape[0]})

    iforest = IForestDetector.train(flat, contamination=0.005)
    iforest.save(IFOREST_PATH)
    log.info("saved iforest -> %s", IFOREST_PATH)
    if run is not None:
        run.log({"iforest/saved": 1})

    windows = _windowize(traces)
    log.info("lstm-ae training set: %s", windows.shape)
    if run is not None:
        run.log({"lstm/window_count": int(windows.shape[0])})

    lstm = LSTMAutoencoderDetector.train(
        windows, epochs=20, threshold_pct=99.0, wandb_run=run
    )
    lstm.save(LSTM_DIR)
    log.info(
        "saved lstm-ae -> %s (threshold=%.5f @ p99)",
        LSTM_DIR / "lstm_ae.pt",
        lstm.threshold,
    )

    VERSION_PATH.write_text(json.dumps({"version": MODEL_VERSION}))
    log.info("wrote VERSION=%d", MODEL_VERSION)
    if run is not None:
        run.log({"model_version": MODEL_VERSION, "lstm/threshold": lstm.threshold})

    if run is not None:
        import wandb

        art = wandb.Artifact(
            WANDB_MODEL_NAME,
            type="model",
            metadata={"version": MODEL_VERSION, "iforest": str(IFOREST_PATH.name)},
        )
        art.add_file(str(IFOREST_PATH))
        art.add_file(str(LSTM_DIR / "lstm_ae.pt"))
        art.add_file(str(LSTM_DIR / "lstm_ae.json"))
        art.add_file(str(VERSION_PATH))
        aliases = ["latest"]
        if mark_production:
            aliases.append("production")
        run.log_artifact(art, aliases=aliases)
        log.info("logged W&B artifact %r aliases=%s", WANDB_MODEL_NAME, aliases)
        run.finish()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="retrain even if models exist")
    ap.add_argument(
        "--from-db",
        action="store_true",
        help="load training rows from DATABASE_URL (Postgres) instead of synthetic",
    )
    ap.add_argument(
        "--no-wandb",
        action="store_true",
        help="local dev: skip W&B (no WANDB_API_KEY required)",
    )
    ap.add_argument(
        "--no-production-alias",
        action="store_true",
        help="log artifact as latest only (do not move production tag)",
    )
    args = ap.parse_args()

    if args.from_db:
        from data_from_db import load_traces_from_database

        try:
            traces = load_traces_from_database()
            log.info("loaded %d device traces from database", len(traces))
        except Exception as exc:
            log.warning("DB load failed (%s) — falling back to synthetic", exc)
            traces = generate_normal_traces(n_devices=80, n_steps=720, seed=0)
    else:
        log.info("generating synthetic training data")
        traces = generate_normal_traces(n_devices=80, n_steps=720, seed=0)

    run_training(
        traces=traces,
        force=args.force,
        skip_wandb=args.no_wandb,
        mark_production=not args.no_production_alias,
    )


if __name__ == "__main__":
    main()
