"""FastAPI entrypoint: REST + WebSocket + health."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from db import SessionLocal
from routes import anomalies as anomalies_routes
from routes import devices as devices_routes
from routes import websocket as ws_routes
from schemas import HealthResponse

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s api %(message)s")
log = logging.getLogger("api")

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")]


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(ws_routes.listen_forever(), name="pg-listen")
    log.info("started pg-listen background task")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Sentinel API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices_routes.router)
app.include_router(anomalies_routes.router)
app.include_router(ws_routes.router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return HealthResponse(status="ok", db=True)
    except Exception as exc:  # pragma: no cover — probe, not logic
        log.warning("health check db failed: %s", exc)
        return HealthResponse(status="degraded", db=False)
