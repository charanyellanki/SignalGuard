"""Global pause control for the embedded simulator (admin routes toggle this)."""

from __future__ import annotations

import asyncio

# When the event is *set* the firehose is PAUSED.
paused: asyncio.Event = asyncio.Event()


def is_paused() -> bool:
    return paused.is_set()
