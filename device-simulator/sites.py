"""Realistic Noke-style self-storage facility list.

A "site" is one self-storage facility. Each Noke smart lock belongs to one
site, and every lock at the site uplinks through that site's cellular
gateway. Site names follow the pattern ``<Brand> <Metro> - <Submarket>``.

Scaling: ``assign_devices_to_sites`` distributes ``n_devices`` across the
sites with realistic per-site weights (some facilities are bigger than
others — small urban facilities run ~150 doors, big suburban ones run
500–1000+).
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    site_id: str
    name: str
    metro: str
    weight: float  # relative size — drives per-site device share


SITES: tuple[Site, ...] = (
    Site("site-atl-buckhead",   "StoragePoint Atlanta - Buckhead",     "Atlanta",   1.4),
    Site("site-atl-decatur",    "StoragePoint Atlanta - Decatur",      "Atlanta",   1.0),
    Site("site-atl-marietta",   "StoragePoint Atlanta - Marietta",     "Atlanta",   1.6),
    Site("site-clt-southend",   "StoragePoint Charlotte - South End",  "Charlotte", 0.9),
    Site("site-clt-ballantyne", "StoragePoint Charlotte - Ballantyne", "Charlotte", 1.2),
    Site("site-bna-brentwood",  "StoragePoint Nashville - Brentwood",  "Nashville", 1.0),
    Site("site-bna-franklin",   "StoragePoint Nashville - Franklin",   "Nashville", 0.8),
    Site("site-tpa-south",      "StoragePoint Tampa - South",          "Tampa",     1.3),
    Site("site-mco-winterpark", "StoragePoint Orlando - Winter Park",  "Orlando",   0.9),
    Site("site-dfw-plano",      "StoragePoint Dallas - Plano",         "Dallas",    1.5),
    Site("site-dfw-frisco",     "StoragePoint Dallas - Frisco",        "Dallas",    1.1),
    Site("site-hou-sugarland",  "StoragePoint Houston - Sugar Land",   "Houston",   1.0),
    Site("site-phx-scottsdale", "StoragePoint Phoenix - Scottsdale",   "Phoenix",   1.2),
    Site("site-phx-mesa",       "StoragePoint Phoenix - Mesa",         "Phoenix",   0.7),
    Site("site-las-summerlin",  "StoragePoint Las Vegas - Summerlin",  "Las Vegas", 0.9),
)


def assign_devices_to_sites(n_devices: int, seed: int = 7) -> list[Site]:
    """Return a list of length ``n_devices`` mapping device i → its Site."""
    weights = [s.weight for s in SITES]
    rng = random.Random(seed)
    return rng.choices(SITES, weights=weights, k=n_devices)
