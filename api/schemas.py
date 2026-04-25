"""Pydantic v2 schemas for API responses and WebSocket messages."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high"]
AnomalyStatus = Literal["open", "acknowledged", "dispatched", "snoozed", "resolved", "false_positive"]
AnomalyAction = Literal["acknowledge", "dispatch", "snooze", "resolve", "false_positive", "reopen"]


class TelemetryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: str
    customer_id: str | None = None
    customer_name: str | None = None
    site_id: str | None = None
    site_name: str | None = None
    gateway_id: str | None = None
    building: str | None = None
    unit_id: str | None = None
    timestamp: datetime
    battery_voltage: float
    lock_events_count: int
    signal_strength_dbm: float
    temperature_c: float


class AnomalyRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    customer_id: str | None = None
    customer_name: str | None = None
    site_id: str | None = None
    site_name: str | None = None
    gateway_id: str | None = None
    building: str | None = None
    unit_id: str | None = None
    timestamp: datetime
    anomaly_type: str
    detected_by_model: str
    severity: Severity
    raw_payload: dict[str, Any]
    reason: str | None = None

    # NOC workflow state
    status: AnomalyStatus = "open"
    assignee: str | None = None
    acted_at: datetime | None = None
    action_note: str | None = None


class DeviceSummary(BaseModel):
    device_id: str
    customer_id: str | None = None
    customer_name: str | None = None
    site_id: str | None = None
    site_name: str | None = None
    building: str | None = None
    unit_id: str | None = None
    latest: TelemetryPoint | None
    anomaly_count: int = 0
    last_anomaly_at: datetime | None = None
    online: bool = Field(description="Last telemetry within ONLINE_THRESHOLD_SEC")


class DeviceDetail(BaseModel):
    device_id: str
    customer_id: str | None = None
    customer_name: str | None = None
    site_id: str | None = None
    site_name: str | None = None
    building: str | None = None
    unit_id: str | None = None
    telemetry: list[TelemetryPoint]
    anomalies: list[AnomalyRecord]


class AnomalyPage(BaseModel):
    items: list[AnomalyRecord]
    total: int
    limit: int
    offset: int


class AnomalyActionRequest(BaseModel):
    """Body for ``POST /anomalies/{id}/action`` — NOC workflow transition."""
    action: AnomalyAction
    assignee: str | None = None
    note: str | None = None


class SiteSummary(BaseModel):
    site_id: str
    site_name: str
    customer_id: str | None = None
    customer_name: str | None = None
    gateway_id: str | None = None
    device_count: int
    devices_online: int
    anomalies_24h: int
    open_incidents: int = Field(0, description="Anomalies in 'open' status")
    low_battery_count: int = Field(description="Devices with last battery < 2.9 V")


class CustomerSummary(BaseModel):
    """Top-level operator rollup: one card per Nokē customer."""
    customer_id: str
    customer_name: str
    facility_count: int
    device_count: int
    devices_online: int
    anomalies_24h: int
    open_incidents: int
    p0_incidents: int = Field(0, description="High-severity open incidents")
    tenants_impacted: int = Field(0, description="Currently offline locks (1 unit ≈ 1 tenant)")


class UnitsStats(BaseModel):
    """Top-level KPI rollup for the dashboard header strip.

    A "unit" is a single rentable storage compartment (e.g. B-204); each
    unit has one Nokē smart lock.
    """

    customers_count: int = 0
    sites_count: int
    devices_total: int
    devices_online: int
    anomalies_24h: int
    open_incidents: int = 0
    p0_incidents: int = 0
    tenants_impacted: int = Field(0, description="Units currently offline — these tenants can't access their unit")
    low_battery_count: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: bool = Field(description="Database reachable")
