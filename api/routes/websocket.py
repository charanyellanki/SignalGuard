"""WebSocket fan-out for new anomalies.

Implementation:
* A single background task holds a dedicated asyncpg connection listening
  on the ``anomalies`` Postgres NOTIFY channel. The channel is populated by
  the ``anomalies_notify`` trigger installed by Alembic migration 0001.
* On each NOTIFY, the task re-reads the inserted row (payload carries only
  the id — Postgres caps NOTIFY payloads at 8 kB) and fans it out to every
  connected client via per-connection ``asyncio.Queue``.
* Clients can subscribe with an optional ``?device_id=`` filter.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import asyncpg
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from db import Anomaly, SessionLocal
from schemas import AnomalyRecord

log = logging.getLogger("ws")
router = APIRouter()

# asyncpg needs a libpq-style DSN. Strip the SQLAlchemy driver prefix.
_RAW_URL = os.environ["DATABASE_URL"]
ASYNCPG_DSN = _RAW_URL.replace("postgresql+asyncpg://", "postgresql://")


class _Hub:
    """Fan-out registry: one queue per connected WebSocket."""

    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subs.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subs.discard(q)

    async def publish(self, item: dict[str, Any]) -> None:
        async with self._lock:
            dead: list[asyncio.Queue[dict[str, Any]]] = []
            for q in self._subs:
                try:
                    q.put_nowait(item)
                except asyncio.QueueFull:
                    # Slow client — drop it rather than stalling the listener.
                    dead.append(q)
            for q in dead:
                self._subs.discard(q)


hub = _Hub()


async def _lookup(anomaly_id: int) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        row = (
            await session.execute(select(Anomaly).where(Anomaly.id == anomaly_id))
        ).scalar_one_or_none()
        if row is None:
            return None
        return AnomalyRecord.model_validate(row).model_dump(mode="json")


async def listen_forever() -> None:
    """Long-running task started in the FastAPI lifespan."""
    while True:
        try:
            conn: asyncpg.Connection = await asyncpg.connect(dsn=ASYNCPG_DSN)

            async def _on_notify(_c: asyncpg.Connection, _pid: int, _ch: str, payload: str) -> None:
                try:
                    anomaly_id = int(payload)
                except ValueError:
                    log.warning("bad NOTIFY payload: %r", payload)
                    return
                record = await _lookup(anomaly_id)
                if record is not None:
                    await hub.publish(record)

            await conn.add_listener("anomalies", _on_notify)
            log.info("LISTENing on channel=anomalies")
            # Keep the coroutine alive so notifications are delivered.
            while True:
                await asyncio.sleep(3600)
        except (asyncpg.PostgresError, OSError) as exc:
            log.warning("LISTEN connection dropped: %s — reconnecting in 2s", exc)
            await asyncio.sleep(2)


@router.websocket("/ws/anomalies")
async def ws_anomalies(ws: WebSocket, device_id: str | None = None) -> None:
    await ws.accept()
    q = await hub.subscribe()
    try:
        while True:
            item = await q.get()
            if device_id and item.get("device_id") != device_id:
                continue
            await ws.send_text(json.dumps(item))
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(q)
