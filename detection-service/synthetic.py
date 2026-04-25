"""Synthetic *normal*-behavior generator for model training.

Mirrors the simulator (``device-simulator/simulator.py``) so the models
learn the same baseline distribution they'll see in production. If you
change the simulator's generation logic, change this too — the two are
intentionally kept in sync but live in separate containers.
"""

from __future__ import annotations

import math
import random

import numpy as np


def _diurnal_event_factor(hour: float) -> float:
    morning = math.exp(-((hour - 8.0) ** 2) / 4.0)
    evening = math.exp(-((hour - 18.0) ** 2) / 5.0)
    return 0.05 + 0.95 * (morning + 0.85 * evening) / 1.85


def _diurnal_temp_offset(hour: float) -> float:
    return math.sin((hour - 9.0) / 24.0 * 2.0 * math.pi)


def generate_normal_traces(
    n_devices: int,
    n_steps: int,
    interval_sec: float = 5.0,
    seed: int = 0,
) -> list[np.ndarray]:
    """Return one (n_steps, 4) array per device — feature order matches
    ``models.isolation_forest.FEATURE_ORDER``:
        battery_voltage, lock_events_count, signal_strength_dbm, temperature_c
    """
    rng = random.Random(seed)
    traces: list[np.ndarray] = []

    for _ in range(n_devices):
        # Per-device baseline (same ranges as device_profiles.generate_fleet).
        bat0 = rng.uniform(3.15, 3.30)
        bat_floor = rng.uniform(2.60, 2.75)
        life_h = rng.uniform(720, 1440)
        drain = (bat0 - bat_floor) / (life_h * 3600.0)

        sig_base = rng.uniform(-72, -48)
        sig_jit = rng.uniform(0.6, 1.4)
        sig_alpha = rng.uniform(0.82, 0.92)

        lam_peak = rng.uniform(0.15, 0.6)
        burst = rng.uniform(0.4, 0.8)

        t_base = rng.uniform(18, 23)
        t_amp = rng.uniform(0.8, 2.0)
        t_jit = rng.uniform(0.15, 0.35)

        # Mutable state.
        last_sig = sig_base
        last_temp: float | None = None
        last_events = 0
        # Random starting hour so all training devices don't share a phase.
        start_hour = rng.uniform(0, 24)

        rows = np.empty((n_steps, 4), dtype=np.float32)
        for step in range(n_steps):
            age = step * interval_sec
            hour = (start_hour + age / 3600.0) % 24.0

            battery = max(bat_floor, bat0 - drain * age) + rng.gauss(0, 0.003)

            sig = (
                sig_alpha * last_sig
                + (1.0 - sig_alpha) * sig_base
                + rng.gauss(0, sig_jit)
            )
            sig = max(-99.0, min(-30.0, sig))
            last_sig = sig

            target_temp = t_base + t_amp * _diurnal_temp_offset(hour)
            if last_temp is None:
                last_temp = target_temp
            temp = 0.7 * last_temp + 0.3 * target_temp + rng.gauss(0, t_jit)
            last_temp = temp

            lam = lam_peak * _diurnal_event_factor(hour)
            if last_events > 0:
                lam *= 1.0 + burst
            events = sum(1 for _ in range(8) if rng.random() < min(0.95, lam / 8.0))
            last_events = events

            rows[step, 0] = battery
            rows[step, 1] = events
            rows[step, 2] = sig
            rows[step, 3] = temp

        traces.append(rows)

    return traces
