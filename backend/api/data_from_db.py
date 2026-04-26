"""Build training traces from live Postgres telemetry (Supabase).

Each trace is a (T, 4) float32 array in FEATURE_ORDER. Devices with too few
rows are skipped. If the DB has almost no data, this raises so the caller
can fall back to synthetic generation.
"""

from __future__ import annotations

import os
from collections import defaultdict

import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor

from detectors.lstm_autoencoder import WINDOW_SIZE

# Minimum per-device length to contribute LSTM windows
_MIN_DEVICE_ROWS = WINDOW_SIZE * 2


def _psycopg2_url_from_env() -> str:
    raw = os.environ["DATABASE_URL"]
    if raw.startswith("postgresql+asyncpg://"):
        return "postgresql://" + raw.removeprefix("postgresql+asyncpg://")
    return raw


def load_traces_from_database(
    *,
    max_rows: int = 100_000,
    min_total_rows: int = 2_000,
) -> list[np.ndarray]:
    """Pull recent telemetry, grouped by device_id, as numpy arrays."""
    url = _psycopg2_url_from_env()
    conn = psycopg2.connect(url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT device_id, battery_voltage, lock_events_count,
                       signal_strength_dbm, temperature_c, timestamp
                FROM telemetry
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (max_rows,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if len(rows) < min_total_rows:
        raise RuntimeError(
            f"insufficient telemetry in DB: got {len(rows)} rows, need >= {min_total_rows}"
        )

    by_device: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_device[r["device_id"]].append(r)

    traces: list[np.ndarray] = []
    for did, rlist in by_device.items():
        rlist = sorted(rlist, key=lambda x: x["timestamp"])
        if len(rlist) < _MIN_DEVICE_ROWS:
            continue
        mat = np.empty((len(rlist), 4), dtype=np.float32)
        for i, r in enumerate(rlist):
            mat[i, 0] = float(r["battery_voltage"])
            mat[i, 1] = int(r["lock_events_count"])
            mat[i, 2] = float(r["signal_strength_dbm"])
            mat[i, 3] = float(r["temperature_c"])
        traces.append(mat)

    if not traces:
        raise RuntimeError("no device had enough rows for LSTM training")

    return traces
