"""Shared telemetry row insert (HTTP ingest + in-process simulator)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from db import Telemetry, SessionLocal


async def insert_telemetry_row(
    *,
    device_id: str,
    timestamp: datetime,
    battery_voltage: float,
    lock_events_count: int,
    signal_strength_dbm: float,
    temperature_c: float,
    customer_id: str | None = None,
    customer_name: str | None = None,
    site_id: str | None = None,
    site_name: str | None = None,
    gateway_id: str | None = None,
    building: str | None = None,
    unit_id: str | None = None,
) -> None:
    async with SessionLocal() as session:
        await _insert_with_session(
            session,
            device_id=device_id,
            timestamp=timestamp,
            battery_voltage=battery_voltage,
            lock_events_count=lock_events_count,
            signal_strength_dbm=signal_strength_dbm,
            temperature_c=temperature_c,
            customer_id=customer_id,
            customer_name=customer_name,
            site_id=site_id,
            site_name=site_name,
            gateway_id=gateway_id,
            building=building,
            unit_id=unit_id,
        )
        await session.commit()


async def _insert_with_session(
    session: AsyncSession,
    *,
    device_id: str,
    timestamp: datetime,
    battery_voltage: float,
    lock_events_count: int,
    signal_strength_dbm: float,
    temperature_c: float,
    customer_id: str | None = None,
    customer_name: str | None = None,
    site_id: str | None = None,
    site_name: str | None = None,
    gateway_id: str | None = None,
    building: str | None = None,
    unit_id: str | None = None,
) -> None:
    row = Telemetry(
        device_id=device_id,
        timestamp=timestamp,
        battery_voltage=battery_voltage,
        lock_events_count=lock_events_count,
        signal_strength_dbm=signal_strength_dbm,
        temperature_c=temperature_c,
        customer_id=customer_id,
        customer_name=customer_name,
        site_id=site_id,
        site_name=site_name,
        gateway_id=gateway_id,
        building=building,
        unit_id=unit_id,
        processed=False,
        processed_at=None,
    )
    session.add(row)
