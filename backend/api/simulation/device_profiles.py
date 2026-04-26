"""Per-Nokē-lock baseline parameters + mutable per-device state."""

from __future__ import annotations

import random
from dataclasses import dataclass

from simulation.sites import Site, assign_devices_to_sites, assign_unit


@dataclass
class DeviceProfile:
    device_id: str
    site_id: str
    site_name: str
    customer_id: str
    customer_name: str
    gateway_id: str
    building: str
    unit_id: str
    battery_start_v: float
    battery_floor_v: float
    battery_life_hours: float
    signal_baseline_dbm: float
    signal_jitter_dbm: float
    signal_ar_alpha: float
    events_lambda_peak: float
    events_burstiness: float
    temp_baseline_c: float
    temp_amplitude_c: float
    temp_jitter_c: float
    age_seconds: float = 0.0
    last_signal_dbm: float | None = None
    last_temp_c: float | None = None
    last_events: int = 0
    flap_streak_remaining: int = 0
    spike_streak_remaining: int = 0
    battery_drop_remaining: int = 0


def generate_units(count: int, seed: int = 42) -> list[DeviceProfile]:
    rng = random.Random(seed)
    site_assignment: list[Site] = assign_devices_to_sites(count, seed=seed + 1)
    units: list[DeviceProfile] = []
    for i in range(count):
        site = site_assignment[i]
        building, unit_id = assign_unit(site, rng)
        units.append(
            DeviceProfile(
                device_id=f"noke-{i:05d}",
                site_id=site.site_id,
                site_name=site.name,
                customer_id=site.customer_id,
                customer_name=site.customer_name,
                gateway_id=site.gateway_id,
                building=building,
                unit_id=unit_id,
                battery_start_v=rng.uniform(3.15, 3.30),
                battery_floor_v=rng.uniform(2.60, 2.75),
                battery_life_hours=rng.uniform(720, 1440),
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
    return units
