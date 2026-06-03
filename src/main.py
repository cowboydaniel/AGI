"""
ACD system entrypoint. Boots modules in the defined initialization order and runs
until SIGINT/SIGTERM. State persists across restarts via the state store.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import bus
import clock
import sandbox
import state_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

_shutdown = asyncio.Event()


def _handle_signal(sig: signal.Signals) -> None:
    logger.info("received %s — shutting down", sig.name)
    _shutdown.set()


async def _log_ticks(event: clock.TickEvent) -> None:
    if event.tick % 50 == 0:
        logger.info("tick %d  elapsed=%.1fs", event.tick, event.timestamp)


async def main() -> None:
    logger.info("ACD Stage 0 — Zygote — booting")

    # 2. State Store (must come before sandbox reads from it)
    state_store.init()

    # 1. Sandbox / Capability Manager
    stage = state_store.get("development_stage", default=0)
    sandbox.init(stage=stage)
    bus.subscribe(sandbox.ActionRequestEvent, sandbox.handle_request)

    # 3. Event Bus — already module-level; subscribe clock tick logger
    bus.subscribe(clock.TickEvent, _log_ticks)

    # Persist stage on each boot so we can inspect it externally
    state_store.set("development_stage", stage)
    state_store.set("last_boot", clock._start_time if hasattr(clock, "_start_time") else 0)

    logger.info("boot complete — stage=%d", stage)

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal, sig)

    # Launch long-lived tasks
    bus_task = asyncio.create_task(bus.run(), name="bus")
    clock_task = asyncio.create_task(clock.run(), name="clock")

    await _shutdown.wait()

    logger.info("shutting down tasks")
    for task in (clock_task, bus_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    state_store.close()
    logger.info("shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
