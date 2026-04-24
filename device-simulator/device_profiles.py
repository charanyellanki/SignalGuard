"""Per-device baseline parameters.

Each virtual device carries a stable personality — different battery drain
rate, signal baseline, event cadence — so the detection service has to learn
structure rather than a single global mean.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class DeviceProfile:
    device_id: str
    # Battery decays linearly from `battery_start_v` toward `battery_floor_v`
    # over `battery_life_hours`. Noise is added per sample.
    battery_start_v: float
    battery_floor_v: float
    battery_life_hours: float
    # Signal strength baseline in dBm (typical Wi-Fi range -40 .. -80).
    signal_baseline_dbm: float
    signal_jitter_dbm: float
    # Expected lock events per emit interval (Poisson lambda).
    events_lambda: float
    # Temperature baseline in Celsius.
    temp_baseline_c: float
    temp_jitter_c: float
    # Device lifecycle state (mutable — driven by simulator loop).
    age_seconds: float = 0.0
    flap_streak_remaining: int = 0
    spike_streak_remaining: int = 0


def generate_fleet(count: int, seed: int = 42) -> list[DeviceProfile]:
    rng = random.Random(seed)
    fleet: list[DeviceProfile] = []
    for i in range(count):
        fleet.append(
            DeviceProfile(
                device_id=f"lock-{i:04d}",
                battery_start_v=rng.uniform(3.15, 3.30),
                battery_floor_v=rng.uniform(2.60, 2.75),
                battery_life_hours=rng.uniform(720, 1440),  # 30–60 days
                signal_baseline_dbm=rng.uniform(-70, -45),
                signal_jitter_dbm=rng.uniform(1.0, 3.0),
                events_lambda=rng.uniform(0.05, 0.6),
                temp_baseline_c=rng.uniform(17, 24),
                temp_jitter_c=rng.uniform(0.3, 1.0),
            )
        )
    return fleet
