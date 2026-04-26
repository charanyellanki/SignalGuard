"""Admin / demo control — in-process simulation pause (no separate service)."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from simulation import state

router = APIRouter(prefix="/admin", tags=["admin"])

log = logging.getLogger("admin")


@router.get("/simulation")
async def get_simulation_state() -> dict:
    return {"running": not state.is_paused()}


@router.post("/simulation/pause")
async def pause_simulation() -> dict:
    state.paused.set()
    log.info("simulation PAUSED")
    return {"running": False}


@router.post("/simulation/resume")
async def resume_simulation() -> dict:
    state.paused.clear()
    log.info("simulation RESUMED")
    return {"running": True}
