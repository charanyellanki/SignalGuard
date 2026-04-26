"""Telemetry ingest endpoint (Kafka replacement).

The simulator POSTs raw telemetry samples here. We persist them to the
`telemetry` table with `processed=false`. The detection service polls rows
from Postgres, scores them, writes anomalies, and marks telemetry processed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db import Telemetry, get_session

router = APIRouter(prefix="/ingest", tags=["ingest"])


class TelemetryIn(BaseModel):
    device_id: str
    timestamp: datetime

    battery_voltage: float
    lock_events_count: int
    signal_strength_dbm: float
    temperature_c: float

    customer_id: str | None = None
    customer_name: str | None = None
    site_id: str | None = None
    site_name: str | None = None
    gateway_id: str | None = None
    building: str | None = None
    unit_id: str | None = None

    raw: dict[str, Any] | None = Field(
        default=None,
        description="Optional extra fields for debugging; not persisted.",
    )


class IngestResponse(BaseModel):
    status: str = "ok"


@router.post("/telemetry", response_model=IngestResponse)
async def ingest_telemetry(
    payload: TelemetryIn,
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    try:
        row = Telemetry(
            device_id=payload.device_id,
            timestamp=payload.timestamp,
            battery_voltage=payload.battery_voltage,
            lock_events_count=payload.lock_events_count,
            signal_strength_dbm=payload.signal_strength_dbm,
            temperature_c=payload.temperature_c,
            customer_id=payload.customer_id,
            customer_name=payload.customer_name,
            site_id=payload.site_id,
            site_name=payload.site_name,
            gateway_id=payload.gateway_id,
            building=payload.building,
            unit_id=payload.unit_id,
            processed=False,
            processed_at=None,
        )
        session.add(row)
        await session.commit()
        return IngestResponse()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"failed to ingest telemetry: {exc}") from exc

