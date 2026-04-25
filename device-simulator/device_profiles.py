"""Per-device baseline parameters + mutable per-device state.

Each virtual device has a stable personality (signal baseline, base event
rate, temperature baseline) **and** mutable state that drives temporal
realism (last RSSI for AR(1), last temp, last event count for burstiness).

Devices share generation logic with ``detection-service/synthetic.py`` —
keep them in sync if you change either.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from sites import Site, assign_devices_to_sites


@dataclass
class DeviceProfile:
    device_id: str
    site_id: str
    site_name: str

    # ── Battery ──────────────────────────────────────────────────────────
    # Linear drain from start → floor over the device's rated life.
    battery_start_v: float
    battery_floor_v: float
    battery_life_hours: float

    # ── Signal (RSSI) ────────────────────────────────────────────────────
    # AR(1) random walk: rssi_t = α * rssi_{t-1} + (1-α) * baseline + N(0, σ).
    # High α → smooth drift, low α → noisy. Real Wi-Fi/LoRa traces are smooth.
    signal_baseline_dbm: float
    signal_jitter_dbm: float
    signal_ar_alpha: float

    # ── Lock events ──────────────────────────────────────────────────────
    # Daytime peak λ per 5s tick; effective λ scales with the diurnal curve
    # in simulator._diurnal_event_factor (peaks 8am, 6pm; near-zero overnight).
    events_lambda_peak: float
    # Lift on next-tick λ if this tick had ≥1 event (clusters of activity).
    events_burstiness: float

    # ── Temperature ──────────────────────────────────────────────────────
    # Daily sine wave around baseline + AR(1) smoothing.
    temp_baseline_c: float
    temp_amplitude_c: float
    temp_jitter_c: float

    # ── Mutable state (driven by simulator loop) ─────────────────────────
    age_seconds: float = 0.0
    last_signal_dbm: float | None = None
    last_temp_c: float | None = None
    last_events: int = 0
    flap_streak_remaining: int = 0
    spike_streak_remaining: int = 0
    battery_drop_remaining: int = 0


def generate_fleet(count: int, seed: int = 42) -> list[DeviceProfile]:
    rng = random.Random(seed)
    site_assignment: list[Site] = assign_devices_to_sites(count, seed=seed + 1)
    fleet: list[DeviceProfile] = []
    for i in range(count):
        site = site_assignment[i]
        fleet.append(
            DeviceProfile(
                device_id=f"lock-{i:04d}",
                site_id=site.site_id,
                site_name=site.name,
                battery_start_v=rng.uniform(3.15, 3.30),
                battery_floor_v=rng.uniform(2.60, 2.75),
                battery_life_hours=rng.uniform(720, 1440),  # 30–60 days
                signal_baseline_dbm=rng.uniform(-72, -48),
                signal_jitter_dbm=rng.uniform(0.6, 1.4),
                signal_ar_alpha=rng.uniform(0.82, 0.92),
                events_lambda_peak=rng.uniform(0.15, 0.6),
                events_burstiness=rng.uniform(0.4, 0.8),
                temp_baseline_c=rng.uniform(18, 23),
                temp_amplitude_c=rng.uniform(0.8, 2.0),
                temp_jitter_c=rng.uniform(0.15, 0.35),
            )
        )
    return fleet
