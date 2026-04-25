"""Pydantic v2 schemas for API responses and WebSocket messages."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high"]


class TelemetryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: str
    site_id: str | None = None
    site_name: str | None = None
    timestamp: datetime
    battery_voltage: float
    lock_events_count: int
    signal_strength_dbm: float
    temperature_c: float


class AnomalyRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    site_id: str | None = None
    site_name: str | None = None
    timestamp: datetime
    anomaly_type: str
    detected_by_model: str
    severity: Severity
    raw_payload: dict[str, Any]
    reason: str | None = None


class DeviceSummary(BaseModel):
    device_id: str
    site_id: str | None = None
    site_name: str | None = None
    latest: TelemetryPoint | None
    anomaly_count: int = 0
    last_anomaly_at: datetime | None = None
    online: bool = Field(description="Last telemetry within ONLINE_THRESHOLD_SEC")


class DeviceDetail(BaseModel):
    device_id: str
    site_id: str | None = None
    site_name: str | None = None
    telemetry: list[TelemetryPoint]
    anomalies: list[AnomalyRecord]


class AnomalyPage(BaseModel):
    items: list[AnomalyRecord]
    total: int
    limit: int
    offset: int


class SiteSummary(BaseModel):
    site_id: str
    site_name: str
    device_count: int
    devices_online: int
    anomalies_24h: int
    low_battery_count: int = Field(description="Devices with last battery < 2.9 V")


class FleetStats(BaseModel):
    """Top-level KPI rollup for the dashboard header strip."""

    sites_count: int
    devices_total: int
    devices_online: int
    anomalies_24h: int
    low_battery_count: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: bool = Field(description="Database reachable")
