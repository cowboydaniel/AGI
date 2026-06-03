"""
ACD system entrypoint. Boots modules in the defined initialization order and runs
until SIGINT/SIGTERM. State persists across restarts via the state store.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import arousal
import bus
import clock
import homeostasis
import mic_input
import orienting
import predictor
import sandbox
import sensory_gate
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
    logger.info("ACD Stage 7 — Continuous Predictive Loop — booting")

    # 2. State Store (must come before sandbox reads from it)
    state_store.init()

    # 1. Sandbox / Capability Manager
    stage = state_store.get("development_stage", default=0)
    sandbox.init(stage=stage)
    bus.subscribe(sandbox.ActionRequestEvent, sandbox.handle_request)

    # 3. Event Bus — already module-level; subscribe clock tick logger
    bus.subscribe(clock.TickEvent, _log_ticks)

    # 4. Arousal Regulation
    arousal.init()

    # 5. Sensory Gating
    sensory_gate.init()

    # 6. Orienting Reflex
    orienting.init()

    # Homeostasis (no fixed slot in init order — runs alongside everything)
    homeostasis.init()

    # 7. Continuous Predictive Loop
    predictor.init()

    # 6. Sensor Input — mic
    mic_input.init()

    # Persist stage on each boot so we can inspect it externally
    state_store.set("development_stage", stage)

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal, sig)

    # Launch long-lived tasks
    bus_task   = asyncio.create_task(bus.run(),   name="bus")
    clock_task = asyncio.create_task(clock.run(), name="clock")

    # All modules are subscribed — apply startup gate so sensors open immediately
    await sensory_gate.apply_startup_gate()

    logger.info("boot complete — stage=%d", stage)

    await _shutdown.wait()

    logger.info("shutting down tasks")
    mic_input._close_stream()
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
