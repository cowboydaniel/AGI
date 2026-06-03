"""
Internal clock. Publishes TickEvent on the bus at a fixed interval.
All modules use this as their time reference — never wall-clock directly.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

import bus

logger = logging.getLogger(__name__)

TICK_INTERVAL = 0.1  # seconds — 10 Hz base clock


@dataclass
class TickEvent(bus.Event):
    tick: int  # monotonically increasing since process start


_tick_count = 0
_start_time: float = 0.0


def elapsed() -> float:
    return time.monotonic() - _start_time


async def run() -> None:
    global _tick_count, _start_time
    _start_time = time.monotonic()
    logger.info("clock started (%.1f Hz)", 1.0 / TICK_INTERVAL)
    while True:
        await asyncio.sleep(TICK_INTERVAL)
        _tick_count += 1
        await bus.publish(
            TickEvent(
                source="clock",
                timestamp=elapsed(),
                tick=_tick_count,
            )
        )
