"""Realistic Janus Nokē Smart Entry deployments across customer operators."""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str


@dataclass(frozen=True)
class Site:
    site_id: str
    name: str
    metro: str
    customer_id: str
    customer_name: str
    gateway_id: str
    buildings: tuple[str, ...]
    weight: float


CUSTOMERS: tuple[Customer, ...] = (
    Customer("cust-10federal", "10 Federal Storage"),
    Customer("cust-storagemart", "StorageMart"),
    Customer("cust-cubesmart",  "CubeSmart"),
    Customer("cust-extraspace", "Extra Space Storage"),
    Customer("cust-uhaul",      "U-Haul Self Storage"),
    Customer("cust-stkingusa",  "Storage King USA"),
)

CUSTOMERS_BY_ID: dict[str, Customer] = {c.customer_id: c for c in CUSTOMERS}


def _site(
    site_id: str, name: str, metro: str, customer_id: str,
    buildings: tuple[str, ...], weight: float,
) -> Site:
    return Site(
        site_id=site_id,
        name=name,
        metro=metro,
        customer_id=customer_id,
        customer_name=CUSTOMERS_BY_ID[customer_id].name,
        gateway_id=f"gw-{site_id.removeprefix('site-')}",
        buildings=buildings,
        weight=weight,
    )


SITES: tuple[Site, ...] = (
    _site("site-10f-charlotte",  "10 Federal Storage - Charlotte Tryon",     "Charlotte",   "cust-10federal", ("A", "B"),       1.0),
    _site("site-10f-raleigh",    "10 Federal Storage - Raleigh Glenwood",    "Raleigh",     "cust-10federal", ("A", "B"),       0.9),
    _site("site-sm-kc",          "StorageMart - Kansas City Plaza",          "Kansas City", "cust-storagemart", ("A", "B", "C"), 1.4),
    _site("site-sm-stl",         "StorageMart - St. Louis Brentwood",        "St. Louis",   "cust-storagemart", ("A", "B"),       1.1),
    _site("site-sm-toronto",     "StorageMart - Toronto Dufferin",           "Toronto",     "cust-storagemart", ("A", "B"),       0.9),
    _site("site-cube-bk",        "CubeSmart - Brooklyn Gowanus",             "Brooklyn",    "cust-cubesmart",   ("A", "B", "C"), 1.6),
    _site("site-cube-bos",       "CubeSmart - Boston Allston",               "Boston",      "cust-cubesmart",   ("A", "B"),       1.2),
    _site("site-cube-atl",       "CubeSmart - Atlanta Buckhead",             "Atlanta",     "cust-cubesmart",   ("A", "B", "C"), 1.5),
    _site("site-exr-burbank",    "Extra Space Storage - Burbank",            "Los Angeles", "cust-extraspace",  ("A", "B", "C"), 1.7),
    _site("site-exr-scottsdale", "Extra Space Storage - Scottsdale",         "Phoenix",     "cust-extraspace",  ("A", "B"),       1.3),
    _site("site-uh-houston",     "U-Haul Self Storage - Houston Northwest",  "Houston",     "cust-uhaul",       ("A", "B", "C"), 1.4),
    _site("site-skusa-tampa",    "Storage King USA - Tampa Carrollwood",     "Tampa",       "cust-stkingusa",   ("A", "B"),       1.0),
)

SITES_BY_ID: dict[str, Site] = {s.site_id: s for s in SITES}


def assign_devices_to_sites(n_devices: int, seed: int = 7) -> list[Site]:
    weights = [s.weight for s in SITES]
    rng = random.Random(seed)
    return rng.choices(SITES, weights=weights, k=n_devices)


def assign_unit(site: Site, rng: random.Random) -> tuple[str, str]:
    building = rng.choice(site.buildings)
    unit_num = rng.randint(100, 599)
    return building, f"{building}-{unit_num:03d}"
