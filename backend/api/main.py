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
import detector
from routes import admin as admin_routes
from routes import anomalies as anomalies_routes
from routes import customers as customers_routes
from routes import devices as devices_routes
from routes import ingest as ingest_routes
from routes import sites as sites_routes
from routes import websocket as ws_routes
from schemas import HealthResponse

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s api %(message)s")
log = logging.getLogger("api")

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")]


@asynccontextmanager
async def lifespan(app: FastAPI):
    from simulation.worker import run_forever

    tasks: list[asyncio.Task[None]] = [
        asyncio.create_task(ws_routes.listen_forever(), name="pg-listen"),
        asyncio.create_task(detector.poll_forever(), name="detector"),
    ]
    if os.environ.get("SIMULATOR_ENABLED", "true").lower() == "true":
        tasks.append(asyncio.create_task(run_forever(), name="simulation"))
    log.info("started background tasks: %s", [t.get_name() for t in tasks])
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="Janus Nokē Smart Entry — Operations API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers_routes.router)
app.include_router(sites_routes.router)
app.include_router(devices_routes.router)
app.include_router(anomalies_routes.router)
app.include_router(ingest_routes.router)
app.include_router(admin_routes.router)
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
