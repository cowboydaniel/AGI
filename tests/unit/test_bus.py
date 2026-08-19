"""
Unit tests for the Stage 1 typed async event bus (src/bus.py).

The bus is the only sanctioned path for inter-module communication, so these
tests pin the guarantees every other module relies on: type-routed dispatch,
FIFO ordering, fan-out to multiple subscribers, and isolation of a handler
that raises. A real bus.run() task drains the queue — no mocking of dispatch.

Runs under pytest or directly:  python tests/unit/test_bus.py
"""

import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

# Make src/ importable whether run via pytest or as a script.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import bus

# Captured at import time, before any test can monkeypatch it. Other test
# modules replace bus.publish to capture emissions and do not restore it, so
# these tests reinstate the real implementation to stay order-independent.
_REAL_PUBLISH = bus.publish


# ── fixtures ─────────────────────────────────────────────────────────────────────

@dataclass
class AlphaEvent(bus.Event):
    payload: int


@dataclass
class BetaEvent(bus.Event):
    payload: int


def _alpha(payload: int = 0) -> AlphaEvent:
    return AlphaEvent(source="test", timestamp=0.0, payload=payload)


def _reset() -> None:
    """Clear all subscribers and force a fresh queue for the next event loop."""
    bus.publish = _REAL_PUBLISH
    bus._subscribers.clear()
    bus._queue = None


async def _drain() -> None:
    """Run the bus until every queued event has been dispatched, then stop it."""
    task = asyncio.create_task(bus.run(), name="bus")
    await bus.get_queue().join()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ── tests ──────────────────────────────────────────────────────────────────────

def test_publish_dispatches_to_subscriber():
    _reset()
    seen = []

    async def handler(event):
        seen.append(event)

    async def run():
        bus.subscribe(AlphaEvent, handler)
        await bus.publish(_alpha(1))
        await _drain()

    asyncio.run(run())

    assert len(seen) == 1, "handler must be called exactly once"
    assert seen[0].payload == 1, "handler must receive the published event"


def test_dispatch_is_routed_by_event_type():
    _reset()
    alphas, betas = [], []

    async def on_alpha(event):
        alphas.append(event)

    async def on_beta(event):
        betas.append(event)

    async def run():
        bus.subscribe(AlphaEvent, on_alpha)
        bus.subscribe(BetaEvent, on_beta)
        await bus.publish(_alpha(1))
        await _drain()

    asyncio.run(run())

    assert len(alphas) == 1, "the matching subscriber must fire"
    assert betas == [], "a subscriber to a different type must not fire"


def test_multiple_subscribers_all_receive_event():
    _reset()
    calls = []

    async def first(event):
        calls.append("first")

    async def second(event):
        calls.append("second")

    async def run():
        bus.subscribe(AlphaEvent, first)
        bus.subscribe(AlphaEvent, second)
        await bus.publish(_alpha())
        await _drain()

    asyncio.run(run())

    assert calls == ["first", "second"], "all subscribers must fire, in subscription order"


def test_events_dispatch_in_fifo_order():
    _reset()
    seen = []

    async def handler(event):
        seen.append(event.payload)

    async def run():
        bus.subscribe(AlphaEvent, handler)
        for i in range(10):
            await bus.publish(_alpha(i))
        await _drain()

    asyncio.run(run())

    assert seen == list(range(10)), "events must be delivered in publication order"


def test_handler_exception_does_not_stop_the_bus():
    """A module that raises must not take down inter-module communication."""
    _reset()
    survivors = []

    async def exploding(event):
        raise ValueError("handler failure")

    async def healthy(event):
        survivors.append(event.payload)

    async def run():
        bus.subscribe(AlphaEvent, exploding)
        bus.subscribe(AlphaEvent, healthy)
        await bus.publish(_alpha(1))
        await bus.publish(_alpha(2))
        await _drain()

    # The bus is expected to log the failure; keep it out of the test output.
    logging.getLogger("bus").setLevel(logging.CRITICAL)
    try:
        asyncio.run(run())
    finally:
        logging.getLogger("bus").setLevel(logging.NOTSET)

    assert survivors == [1, 2], \
        "later subscribers and later events must survive a raising handler"


def test_publish_with_no_subscribers_is_a_noop():
    _reset()

    async def run():
        await bus.publish(_alpha())
        await _drain()
        return bus.get_queue().qsize()

    assert asyncio.run(run()) == 0, "an unsubscribed event must still be drained"


def test_get_queue_is_idempotent():
    _reset()

    async def run():
        first = bus.get_queue()
        second = bus.get_queue()
        assert first is second, "get_queue must return the same queue instance"

    asyncio.run(run())


def test_subscribe_registers_against_the_event_type():
    _reset()

    async def handler(event):
        return None

    bus.subscribe(AlphaEvent, handler)

    assert bus._subscribers[AlphaEvent] == [handler], \
        "handler must be registered under its event type"
    assert bus._subscribers[BetaEvent] == [], \
        "unrelated event types must have no subscribers"


# ── script runner (works without pytest) ─────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
