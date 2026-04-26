"""Download versioned model artifacts from Weights & Biases."""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("wandb_model")


def download_production_models(model_dir: Path) -> bool:
    """Fetch ``signalguard-models:production`` into ``model_dir``.

    Returns True if a download happened, False if W&B is not configured
    (caller may fall back to local disk or training).
    """
    api_key = os.environ.get("WANDB_API_KEY", "").strip()
    if not api_key:
        log.info("WANDB_API_KEY not set — skipping W&B artifact download")
        return False

    entity = os.environ.get("WANDB_ENTITY", "").strip()
    project = os.environ.get("WANDB_PROJECT", "signalguard").strip()
    name = os.environ.get("WANDB_MODEL_ARTIFACT", "signalguard-models").strip()
    alias = os.environ.get("WANDB_MODEL_ALIAS", "production").strip()

    if not entity:
        # wandb can infer from API key; use Api().default_entity
        import wandb

        wandb.login(key=api_key, relogin=True)
        api = wandb.Api()
        entity = api.default_entity
        if not entity:
            log.warning("Could not determine W&B entity; set WANDB_ENTITY")
            return False
    else:
        import wandb

        wandb.login(key=api_key, relogin=True)
        api = wandb.Api()

    spec = f"{entity}/{project}/{name}:{alias}"
    log.info("downloading W&B artifact %s", spec)
    try:
        artifact = api.artifact(spec, type="model")
    except Exception as exc:  # pragma: no cover
        log.warning("W&B artifact fetch failed: %s", exc)
        return False

    model_dir.mkdir(parents=True, exist_ok=True)
    import shutil

    adir = Path(artifact.download())
    for fname in (
        "iforest.joblib",
        "lstm_ae.pt",
        "lstm_ae.json",
        "VERSION",
    ):
        p = adir / fname
        if p.is_file():
            shutil.copy2(p, model_dir / fname)
    log.info("W&B models copied to %s", model_dir)
    return True
