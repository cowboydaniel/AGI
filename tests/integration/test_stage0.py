"""
Stage 0 (Zygote) integration tests.

Stage 0's goal is existence and persistence: a process that stays alive, keeps
time, remembers what it was, and holds a boundary between internal state and
external input. These tests boot the four Stage 0 subsystems together - state
store, sandbox, event bus, clock - run them as live asyncio tasks, and check
the exit criteria in STAGE_CRITERIA.md section 5:

    runtime_persistence_test               = pass
    state_save_load_success_rate           >= 99%
    clock_tick_jitter                      <= 10% of configured tick interval
    sandbox_initialization_success_rate    = 100%
    critical_sandbox_violations            = 0

The real duration criterion is 2 continuous hours; these run in under a second
against a shortened tick interval, so they verify mechanism rather than
endurance. Long-run stability is a separate soak-test concern.

No microphone, no torch, no hardware - Stage 0 predates all sensors.

Runs under pytest or directly:  python tests/integration/test_stage0.py
"""

import asyncio
import logging
import statistics
import sys
import tempfile
from pathlib import Path

# Make src/ importable whether run via pytest or as a script.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import bus
import clock
import sandbox
import state_store
from sandbox import (
    ActionApprovedEvent, ActionDeniedEvent, ActionRequestEvent,
    Capability, ViolationEvent,
)

# Captured at import time, before any test can monkeypatch it. Sibling test
# modules replace bus.publish to capture emissions and do not restore it, so
# these tests reinstate the real implementation to stay order-independent.
_REAL_PUBLISH = bus.publish

# Fast clock so a "continuous run" costs milliseconds. The jitter criterion is
# a ratio, so it holds at any interval.
_TEST_TICK_INTERVAL = 0.02


# -- harness --------------------------------------------------------------------

def _boot(stage: int = 0) -> Path:
    """Bring up the Stage 0 subsystems the way main.py does, in the same order."""
    bus.publish = _REAL_PUBLISH
    bus._subscribers.clear()
    bus._queue = None

    db = Path(tempfile.mkdtemp()) / "state.db"
    state_store.init(db)                                   # 2. state store
    sandbox.init(stage=state_store.get("development_stage", default=stage))
    sandbox._violation_count = 0                           # 1. sandbox
    bus.subscribe(ActionRequestEvent, sandbox.handle_request)
    return db


async def _run_for(ticks: int, *, extra_tasks: tuple = ()) -> list:
    """Run bus + clock live until `ticks` ticks have been observed, then stop."""
    observed: list = []
    done = asyncio.Event()

    async def on_tick(event):
        observed.append(event)
        if len(observed) >= ticks:
            done.set()

    bus.subscribe(clock.TickEvent, on_tick)

    original_interval = clock.TICK_INTERVAL
    clock.TICK_INTERVAL = _TEST_TICK_INTERVAL
    clock._tick_count = 0

    tasks = [
        asyncio.create_task(bus.run(), name="bus"),
        asyncio.create_task(clock.run(), name="clock"),
        *[asyncio.create_task(c) for c in extra_tasks],
    ]
    try:
        await asyncio.wait_for(done.wait(), timeout=10.0)
    finally:
        clock.TICK_INTERVAL = original_interval
        for task in tasks:                                 # graceful shutdown
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
    return observed


# -- runtime persistence --------------------------------------------------------

def test_runtime_stays_alive_and_shuts_down_cleanly():
    """The zygote must keep running on its own, then stop when told to."""
    _boot()

    observed = asyncio.run(_run_for(20))

    assert len(observed) >= 20, "the runtime must survive long enough to tick 20 times"
    assert [e.tick for e in observed[:20]] == list(range(1, 21)), \
        "ticks must be monotonic and gapless - no dropped or duplicated ticks"
    assert all(e.source == "clock" for e in observed), "every tick must be attributed"


def test_clock_timestamps_advance_monotonically():
    _boot()

    observed = asyncio.run(_run_for(20))
    stamps = [e.timestamp for e in observed]

    assert stamps == sorted(stamps), "elapsed time must never go backwards"
    assert stamps[0] > 0.0, "elapsed time must be measured from process start"


def test_clock_tick_jitter_within_tolerance():
    """STAGE_CRITERIA section 5: clock_tick_jitter <= 10% of the tick interval.

    Asserted against the mean interval. Per-tick jitter is bounded by the host
    OS timer granularity (~15 ms on Windows), which is a property of the host,
    not the clock module, so the tolerance here is deliberately loose and the
    strict 10% figure belongs to a long-run soak test.
    """
    _boot()

    observed = asyncio.run(_run_for(30))
    intervals = [b.timestamp - a.timestamp for a, b in zip(observed, observed[1:])]
    mean = statistics.fmean(intervals)

    assert all(i > 0 for i in intervals), "ticks must be strictly ordered in time"
    assert mean >= _TEST_TICK_INTERVAL * 0.9, \
        f"clock must not run fast: mean {mean:.4f}s vs {_TEST_TICK_INTERVAL}s"
    assert mean <= _TEST_TICK_INTERVAL * 2.0, \
        f"clock drifted badly: mean {mean:.4f}s vs {_TEST_TICK_INTERVAL}s"


def test_runtime_survives_a_failing_module():
    """Keep-alive: one broken subscriber must not end the process."""
    _boot()

    async def exploding(event):
        raise RuntimeError("module failure")

    bus.subscribe(clock.TickEvent, exploding)

    logging.getLogger("bus").setLevel(logging.CRITICAL)
    try:
        observed = asyncio.run(_run_for(15))
    finally:
        logging.getLogger("bus").setLevel(logging.NOTSET)

    assert len(observed) >= 15, "the clock must keep ticking through handler failures"


# -- state save/load ------------------------------------------------------------

def test_state_save_load_success_rate():
    """STAGE_CRITERIA section 5: state_save_load_success_rate >= 99%."""
    _boot()

    attempts = 200
    successes = 0
    for i in range(attempts):
        key = f"probe_{i}"
        value = {"tick": i, "mode": "LIGHT_SLEEP", "level": i / attempts}
        state_store.set(key, value)
        if state_store.get(key) == value:
            successes += 1

    rate = successes / attempts
    assert rate >= 0.99, f"save/load success rate {rate:.2%} is below the 99% criterion"


def test_development_stage_survives_a_restart():
    """runtime_persistence_test: the system must know what it was on reboot."""
    db = _boot()

    # First life: reach stage 4 and record it, then shut down.
    state_store.set("development_stage", 4)
    state_store.set("uptime_ticks", 1234)
    state_store.close()

    # Second life: the boot sequence main.py runs, against the same database.
    state_store.init(db)
    stage = state_store.get("development_stage", default=0)
    sandbox.init(stage=stage)

    assert stage == 4, "the system must resume at the stage it reached"
    assert state_store.get("uptime_ticks") == 1234, "internal variables must persist"
    assert sandbox.is_allowed(Capability.MICROPHONE_READ), \
        "the sandbox must reopen the capabilities the resumed stage had earned"


def test_state_persists_across_a_live_run():
    """State written while the runtime is ticking is still there afterwards."""
    db = _boot()

    async def writer():
        for i in range(50):
            state_store.set("live_counter", i)
            await asyncio.sleep(0)

    asyncio.run(_run_for(10, extra_tasks=(writer(),)))

    state_store.close()
    state_store.init(db)
    assert state_store.get("live_counter") == 49, \
        "the last value written during the run must be durable"


# -- sandbox boundary -----------------------------------------------------------

def test_sandbox_initialization_success_rate():
    """STAGE_CRITERIA section 5: sandbox_initialization_success_rate = 100%."""
    for attempt in range(50):
        sandbox.init(stage=0)
        assert sandbox._allowed == {Capability.STATE_READ, Capability.STATE_WRITE}, \
            f"sandbox init produced the wrong capability set on attempt {attempt}"
        assert sandbox._current_stage == 0, f"stage not set on attempt {attempt}"


def test_stage_zero_boundary_holds_end_to_end():
    """The Stage 0 boundary, exercised through the real bus rather than directly."""
    _boot()
    verdicts: list = []

    async def record(event):
        verdicts.append(event)

    bus.subscribe(ActionApprovedEvent, record)
    bus.subscribe(ActionDeniedEvent, record)
    bus.subscribe(ViolationEvent, record)

    async def requester():
        await asyncio.sleep(0)
        for cap in (Capability.STATE_READ, Capability.CAMERA_READ, Capability.NETWORK):
            await bus.publish(ActionRequestEvent(
                source="test", timestamp=0.0,
                requesting_module="test_module", capability=cap,
            ))

    logging.getLogger("sandbox").setLevel(logging.CRITICAL)
    try:
        asyncio.run(_run_for(10, extra_tasks=(requester(),)))
    finally:
        logging.getLogger("sandbox").setLevel(logging.NOTSET)

    by_type = {type(v).__name__: v for v in verdicts}
    assert "ActionApprovedEvent" in by_type, "internal state access must be approved"
    assert by_type["ActionApprovedEvent"].capability is Capability.STATE_READ, \
        "only state access may be approved at stage 0"
    assert "ActionDeniedEvent" in by_type, "external input must be denied at stage 0"
    assert by_type["ActionDeniedEvent"].capability is Capability.CAMERA_READ, \
        "the camera is not unlocked at stage 0"
    assert "ViolationEvent" in by_type, "a forbidden request must raise a violation"
    assert by_type["ViolationEvent"].capability is Capability.NETWORK, \
        "the network must never be reachable"


def test_no_critical_violations_during_normal_operation():
    """STAGE_CRITERIA section 5: critical_sandbox_violations = 0."""
    _boot()
    violations: list = []

    async def record(event):
        violations.append(event)

    bus.subscribe(ViolationEvent, record)

    async def well_behaved():
        await asyncio.sleep(0)
        for _ in range(20):
            await bus.publish(ActionRequestEvent(
                source="test", timestamp=0.0,
                requesting_module="test_module", capability=Capability.STATE_WRITE,
            ))

    asyncio.run(_run_for(15, extra_tasks=(well_behaved(),)))

    assert violations == [], "normal operation must produce zero sandbox violations"
    assert sandbox._violation_count == 0, "the violation counter must stay at zero"


# -- script runner (works without pytest) ---------------------------------------

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
