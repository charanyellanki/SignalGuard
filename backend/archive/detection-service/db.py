"""Async SQLAlchemy plumbing for the detection service.

The canonical schema is owned by the ``api`` service via Alembic; these ORM
models mirror it so the detector can INSERT without depending on api code.
If the schema changes, update both sides.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def _normalize_async_database_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return "postgresql+asyncpg://" + raw.removeprefix("postgresql://")
    return raw


DATABASE_URL = _normalize_async_database_url(os.environ["DATABASE_URL"])

engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=10, future=True)
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    site_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gateway_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    building: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    battery_voltage: Mapped[float] = mapped_column(Float)
    lock_events_count: Mapped[int] = mapped_column(Integer)
    signal_strength_dbm: Mapped[float] = mapped_column(Float)
    temperature_c: Mapped[float] = mapped_column(Float)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    site_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gateway_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    building: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    anomaly_type: Mapped[str] = mapped_column(String(64))
    detected_by_model: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    assignee: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action_note: Mapped[str | None] = mapped_column(Text, nullable=True)
