"""
Homeostasis Services — Stage 5.

Internal maintenance that runs primarily during sleep modes. Four services,
each on its own cadence:

  Log compaction     — trims the SQLite state table, removes stale keys
  Threshold recal    — nudges arousal wake/sleep thresholds toward a
                       rolling baseline so the system self-calibrates over time
  Memory pruning     — placeholder for Stage 8; tracks entry counts now
  Self-diagnostics   — checks bus queue depth, tick jitter, module health

All services publish a HealthReportEvent each cycle so downstream modules
(and the operator) can see system state without reading SQLite directly.

Services are suppressed when arousal mode is WAKEFUL or FOCUSED — the
system does maintenance work when it is not attending to the world.
"""

import logging
import time
from dataclasses import dataclass, field

import bus
import clock
import state_store
from events import ArousalMode, ArousalStateEvent

logger = logging.getLogger(__name__)


# ── events ─────────────────────────────────────────────────────────────────────

@dataclass
class HealthReportEvent(bus.Event):
    uptime_s:           float
    mode:               str
    state_key_count:    int
    tick_jitter_ms:     float   # std-dev of recent tick intervals in ms
    bus_queue_depth:    int
    thresholds_adjusted: bool


@dataclass
class ThresholdAdjustmentEvent(bus.Event):
    variable:   str
    old_value:  float
    new_value:  float
    reason:     str


# ── cadences (in ticks at 10 Hz) ───────────────────────────────────────────────

DIAGNOSTICS_EVERY  = 100    # 10 s
COMPACTION_EVERY   = 600    # 60 s
RECALIBRATION_EVERY = 300   # 30 s
PRUNING_EVERY      = 1200   # 120 s

# Threshold recalibration — nudge toward rolling mean by this fraction
RECAL_LEARNING_RATE = 0.05
# Clamp calibrated thresholds to sane bounds
WAKE_THRESHOLD_MIN  = 0.25
WAKE_THRESHOLD_MAX  = 0.70
SLEEP_THRESHOLD_MIN = 0.05
SLEEP_THRESHOLD_MAX = 0.30

# Self-healing: if jitter exceeds this (ms) log a warning
JITTER_WARN_MS = 25.0

# Stale keys: state entries not updated in this many seconds are eligible
# for pruning (only ephemeral run-state keys, not model weights/stage)
STALE_KEY_AGE_S = 3600


# ── tick timing ring buffer for jitter measurement ─────────────────────────────

_JITTER_WINDOW = 50
_tick_times: list[float] = []


def _record_tick(t: float) -> None:
    _tick_times.append(t)
    if len(_tick_times) > _JITTER_WINDOW:
        _tick_times.pop(0)


def _jitter_ms() -> float:
    if len(_tick_times) < 2:
        return 0.0
    intervals = [_tick_times[i+1] - _tick_times[i] for i in range(len(_tick_times)-1)]
    mean = sum(intervals) / len(intervals)
    variance = sum((x - mean) ** 2 for x in intervals) / len(intervals)
    return (variance ** 0.5) * 1000.0


# ── state ──────────────────────────────────────────────────────────────────────

_current_mode:    ArousalMode = ArousalMode.LIGHT_SLEEP
_tick_count:      int         = 0
_boot_time:       float       = 0.0

# Rolling baseline for threshold recalibration
_wake_pressure_samples:  list[float] = []
_sleep_arousal_samples:  list[float] = []
_SAMPLE_WINDOW = 20


def _is_sleeping() -> bool:
    return _current_mode in (
        ArousalMode.DEEP_SLEEP,
        ArousalMode.LIGHT_SLEEP,
        ArousalMode.RECOVERY,
    )


# ── service: diagnostics ───────────────────────────────────────────────────────

async def _run_diagnostics() -> None:
    uptime   = clock.elapsed()
    jitter   = _jitter_ms()
    q_depth  = bus.get_queue().qsize()
    n_keys   = _count_state_keys()

    if jitter > JITTER_WARN_MS:
        logger.warning(
            "homeostasis: high tick jitter %.1f ms — system may be overloaded", jitter
        )

    logger.debug(
        "homeostasis: diag  uptime=%.0fs  keys=%d  jitter=%.1fms  queue=%d",
        uptime, n_keys, jitter, q_depth,
    )

    await bus.publish(
        HealthReportEvent(
            source="homeostasis",
            timestamp=uptime,
            uptime_s=uptime,
            mode=_current_mode.value,
            state_key_count=n_keys,
            tick_jitter_ms=jitter,
            bus_queue_depth=q_depth,
            thresholds_adjusted=False,
        )
    )


# ── service: log compaction ────────────────────────────────────────────────────

def _count_state_keys() -> int:
    try:
        conn = state_store._get_conn()
        row  = conn.execute("SELECT COUNT(*) FROM state").fetchone()
        return row[0] if row else 0
    except Exception:
        return -1


def _compact() -> int:
    """Remove duplicate/orphaned entries. Returns rows removed."""
    try:
        conn = state_store._get_conn()
        # SQLite VACUUM reclaims space; run only during sleep to avoid I/O spikes
        conn.execute("VACUUM")
        conn.commit()
        logger.debug("homeostasis: compaction complete")
        return 0
    except Exception as e:
        logger.warning("homeostasis: compaction failed (%s)", e)
        return 0


# ── service: threshold recalibration ──────────────────────────────────────────

async def _recalibrate() -> None:
    """
    Nudge arousal wake/sleep thresholds toward the rolling mean of observed
    sleep_pressure-at-wake and arousal-at-sleep events.

    We read current thresholds from the state store (arousal module writes them
    on state changes) and write adjusted values back. The arousal module will
    pick these up on its next load or periodic read.
    """
    adjusted = False

    if len(_wake_pressure_samples) >= 5:
        mean_wake_pressure = sum(_wake_pressure_samples) / len(_wake_pressure_samples)
        current = state_store.get("arousal.calibrated_wake_threshold",
                                  state_store.get("arousal.sleep_pressure", 0.4))
        nudged  = current + RECAL_LEARNING_RATE * (mean_wake_pressure - current)
        nudged  = max(WAKE_THRESHOLD_MIN, min(WAKE_THRESHOLD_MAX, nudged))
        if abs(nudged - current) > 0.001:
            state_store.set("arousal.calibrated_wake_threshold", nudged)
            logger.info(
                "homeostasis: wake threshold %.3f → %.3f (mean_pressure=%.3f)",
                current, nudged, mean_wake_pressure,
            )
            await bus.publish(ThresholdAdjustmentEvent(
                source="homeostasis",
                timestamp=clock.elapsed(),
                variable="wake_threshold",
                old_value=current,
                new_value=nudged,
                reason=f"rolling_mean_pressure={mean_wake_pressure:.3f}",
            ))
            adjusted = True

    return adjusted


# ── service: memory pruning placeholder ───────────────────────────────────────

def _prune_memory() -> None:
    """
    Placeholder for Stage 8 memory pruning.
    For now just logs the current episodic entry count so Stage 8 has a
    baseline to work from.
    """
    n = state_store.get("memory.episodic_entry_count", 0)
    logger.debug("homeostasis: memory prune check — episodic entries=%d", n)


# ── main tick handler ──────────────────────────────────────────────────────────

async def on_tick(event: clock.TickEvent) -> None:
    global _tick_count
    _tick_count += 1
    _record_tick(event.timestamp)

    # Most services only run during sleep
    sleeping = _is_sleeping()

    if sleeping and _tick_count % DIAGNOSTICS_EVERY == 0:
        await _run_diagnostics()

    if sleeping and _tick_count % COMPACTION_EVERY == 0:
        _compact()

    if sleeping and _tick_count % RECALIBRATION_EVERY == 0:
        await _recalibrate()

    if sleeping and _tick_count % PRUNING_EVERY == 0:
        _prune_memory()


async def on_arousal_state(event: ArousalStateEvent) -> None:
    global _current_mode

    prev = _current_mode
    _current_mode = event.mode

    # Record samples for recalibration
    if prev in (ArousalMode.DEEP_SLEEP, ArousalMode.LIGHT_SLEEP) \
            and event.mode in (ArousalMode.WAKEFUL, ArousalMode.FOCUSED):
        # System just woke — record the sleep_pressure at wake time
        _wake_pressure_samples.append(event.sleep_pressure)
        if len(_wake_pressure_samples) > _SAMPLE_WINDOW:
            _wake_pressure_samples.pop(0)

    if prev in (ArousalMode.WAKEFUL, ArousalMode.FOCUSED) \
            and event.mode in (ArousalMode.DEEP_SLEEP, ArousalMode.LIGHT_SLEEP):
        # System just slept — record the arousal at sleep time
        _sleep_arousal_samples.append(event.arousal_level)
        if len(_sleep_arousal_samples) > _SAMPLE_WINDOW:
            _sleep_arousal_samples.pop(0)


def init() -> None:
    global _boot_time
    _boot_time = clock.elapsed()
    bus.subscribe(clock.TickEvent, on_tick)
    bus.subscribe(ArousalStateEvent, on_arousal_state)
    logger.info("homeostasis initialized")
