"""
Arousal Regulation — Stage 1 (Excitable Cell).

Maintains sleep/wake state machine driven by internal pressure variables.
No sensors yet — arousal evolves purely from sleep pressure accumulation
and decay. Stage 2 will add inhibitory suppression; Stage 3 adds sensory gating.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum, auto

import bus
import clock
import state_store

logger = logging.getLogger(__name__)


class ArousalMode(str, Enum):
    DEEP_SLEEP = "DEEP_SLEEP"
    LIGHT_SLEEP = "LIGHT_SLEEP"
    WAKEFUL = "WAKEFUL"
    FOCUSED = "FOCUSED"
    RECOVERY = "RECOVERY"


@dataclass
class ArousalStateEvent(bus.Event):
    mode: ArousalMode
    arousal_level: float
    sleep_pressure: float
    fatigue_level: float


@dataclass
class SleepModeChangeEvent(bus.Event):
    previous_mode: ArousalMode
    new_mode: ArousalMode
    reason: str


# ── tuneable parameters ────────────────────────────────────────────────────────

TICK_INTERVAL = clock.TICK_INTERVAL          # seconds

# Sleep pressure accumulates while awake, dissipates while asleep
SLEEP_PRESSURE_WAKE_RATE   = 0.0002          # per tick while wakeful/focused
SLEEP_PRESSURE_SLEEP_RATE  = -0.0005         # per tick while sleeping (dissipates)

# Arousal decays toward 0 while asleep, rises while awake
AROUSAL_WAKE_RATE          = 0.0010
AROUSAL_SLEEP_DECAY        = -0.0008

# Fatigue accumulates with arousal, clears slowly during deep sleep
FATIGUE_ACCUMULATE_RATE    = 0.0001
FATIGUE_CLEAR_RATE         = -0.0003

# Thresholds driving mode transitions
WAKE_THRESHOLD             = 0.4             # sleep_pressure must exceed to auto-wake
SLEEP_THRESHOLD            = 0.15            # arousal must drop below to re-enter sleep
DEEP_SLEEP_THRESHOLD       = 0.3             # sleep_pressure below → eligible for deep sleep
FOCUSED_AROUSAL_THRESHOLD  = 0.75            # arousal above → FOCUSED

# Broadcast arousal state every N ticks regardless of change
BROADCAST_EVERY_N_TICKS    = 10


# ── state ──────────────────────────────────────────────────────────────────────

_mode          = ArousalMode.LIGHT_SLEEP
_arousal       = 0.1
_sleep_pressure= 0.0
_fatigue       = 0.0
_tick_count    = 0


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _save() -> None:
    state_store.set("arousal.mode", _mode.value)
    state_store.set("arousal.arousal_level", _arousal)
    state_store.set("arousal.sleep_pressure", _sleep_pressure)
    state_store.set("arousal.fatigue_level", _fatigue)


def _load() -> None:
    global _mode, _arousal, _sleep_pressure, _fatigue
    _mode           = ArousalMode(state_store.get("arousal.mode", ArousalMode.LIGHT_SLEEP.value))
    _arousal        = state_store.get("arousal.arousal_level", 0.1)
    _sleep_pressure = state_store.get("arousal.sleep_pressure", 0.0)
    _fatigue        = state_store.get("arousal.fatigue_level", 0.0)


async def _transition(new_mode: ArousalMode, reason: str) -> None:
    global _mode
    if new_mode == _mode:
        return
    logger.info("arousal: %s → %s (%s)", _mode.value, new_mode.value, reason)
    prev = _mode
    _mode = new_mode
    await bus.publish(
        SleepModeChangeEvent(
            source="arousal",
            timestamp=clock.elapsed(),
            previous_mode=prev,
            new_mode=new_mode,
            reason=reason,
        )
    )


async def on_tick(event: clock.TickEvent) -> None:
    global _arousal, _sleep_pressure, _fatigue, _tick_count
    _tick_count += 1

    asleep = _mode in (ArousalMode.DEEP_SLEEP, ArousalMode.LIGHT_SLEEP, ArousalMode.RECOVERY)

    # Update pressure variables
    if asleep:
        _sleep_pressure = _clamp(_sleep_pressure + SLEEP_PRESSURE_SLEEP_RATE)
        _arousal        = _clamp(_arousal + AROUSAL_SLEEP_DECAY)
        if _mode == ArousalMode.DEEP_SLEEP:
            _fatigue    = _clamp(_fatigue + FATIGUE_CLEAR_RATE)
    else:
        _sleep_pressure = _clamp(_sleep_pressure + SLEEP_PRESSURE_WAKE_RATE)
        _arousal        = _clamp(_arousal + AROUSAL_WAKE_RATE)
        _fatigue        = _clamp(_fatigue + FATIGUE_ACCUMULATE_RATE)

    # Mode transition logic
    if asleep and _sleep_pressure >= WAKE_THRESHOLD:
        await _transition(ArousalMode.WAKEFUL, "sleep_pressure_threshold")
    elif not asleep and _arousal >= FOCUSED_AROUSAL_THRESHOLD:
        await _transition(ArousalMode.FOCUSED, "high_arousal")
    elif not asleep and _arousal <= SLEEP_THRESHOLD:
        if _sleep_pressure <= DEEP_SLEEP_THRESHOLD:
            await _transition(ArousalMode.DEEP_SLEEP, "low_arousal_low_pressure")
        else:
            await _transition(ArousalMode.LIGHT_SLEEP, "low_arousal")

    # Periodic broadcast
    if _tick_count % BROADCAST_EVERY_N_TICKS == 0:
        await bus.publish(
            ArousalStateEvent(
                source="arousal",
                timestamp=event.timestamp,
                mode=_mode,
                arousal_level=_arousal,
                sleep_pressure=_sleep_pressure,
                fatigue_level=_fatigue,
            )
        )
        _save()


def init() -> None:
    _load()
    bus.subscribe(clock.TickEvent, on_tick)
    logger.info(
        "arousal initialized — mode=%s arousal=%.3f sleep_pressure=%.3f fatigue=%.3f",
        _mode.value, _arousal, _sleep_pressure, _fatigue,
    )
