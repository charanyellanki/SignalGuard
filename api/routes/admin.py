"""Admin / demo control endpoints — proxy to the simulator's control plane.

The simulator runs a tiny HTTP server on its CONTROL_PORT (default 9100,
docker-network-internal) where it accepts pause/resume commands. The
frontend calls these API routes; the API forwards to the simulator. We
deliberately do not expose the simulator port to the host.
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])

SIMULATOR_URL = os.environ.get(
    "SIMULATOR_CONTROL_URL", "http://device-simulator:9100"
).rstrip("/")
TIMEOUT_SEC = 2.0

log = logging.getLogger("admin")


async def _proxy(method: str, path: str) -> dict:
    url = f"{SIMULATOR_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEC) as client:
            r = await client.request(method, url)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as exc:
        log.warning("simulator control unreachable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"simulator control unreachable at {url}",
        ) from exc


@router.get("/simulation")
async def get_simulation_state() -> dict:
    """Return ``{"running": bool}``. 503 if the simulator is unreachable."""
    return await _proxy("GET", "/state")


@router.post("/simulation/pause")
async def pause_simulation() -> dict:
    return await _proxy("POST", "/pause")


@router.post("/simulation/resume")
async def resume_simulation() -> dict:
    return await _proxy("POST", "/resume")
