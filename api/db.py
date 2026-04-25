"""Async SQLAlchemy engine + ORM models.

These models are the source of truth for the schema — Alembic autogenerate
reads them. The detection service mirrors this schema in its own ``db.py``.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, AsyncIterator

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = os.environ["DATABASE_URL"]

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
    site_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    site_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    battery_voltage: Mapped[float] = mapped_column(Float)
    lock_events_count: Mapped[int] = mapped_column(Integer)
    signal_strength_dbm: Mapped[float] = mapped_column(Float)
    temperature_c: Mapped[float] = mapped_column(Float)


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    site_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    site_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    anomaly_type: Mapped[str] = mapped_column(String(64))
    detected_by_model: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
