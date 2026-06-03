"""
Arousal Regulation — Stage 2 (Inhibitory Circuit).

Extends Stage 1 with:
- Refractory period: after any wake transition, sleep re-entry is blocked
  for REFRACTORY_TICKS ticks. Prevents rapid wake→sleep→wake oscillation.
- Adaptive sensitivity: a suppression variable decays after a false-wake
  event (waking with low sleep pressure), raising the effective wake threshold
  temporarily. Equivalent to biological post-excitation inhibition.
- Recovery mode: entered when fatigue is high and sleep pressure is low;
  a lower-arousal wakeful state that doesn't count as full sleep but allows
  partial recovery.
"""

import logging
from dataclasses import dataclass

import bus
import clock
import state_store
from events import (
    ArousalMode, ArousalStateEvent, SleepModeChangeEvent,
    OrientingResponseEvent, SoundCategory,
)

logger = logging.getLogger(__name__)


# ── tuneable parameters ────────────────────────────────────────────────────────

TICK_INTERVAL = clock.TICK_INTERVAL

SLEEP_PRESSURE_WAKE_RATE  =  0.0002
SLEEP_PRESSURE_SLEEP_RATE = -0.0005

AROUSAL_WAKE_RATE         =  0.0010
AROUSAL_SLEEP_DECAY       = -0.0008

FATIGUE_ACCUMULATE_RATE   =  0.0001
FATIGUE_CLEAR_RATE        = -0.0003

WAKE_THRESHOLD            = 0.4
SLEEP_THRESHOLD           = 0.15
DEEP_SLEEP_THRESHOLD      = 0.3
FOCUSED_AROUSAL_THRESHOLD = 0.75

# Stage 2 — inhibitory circuit
REFRACTORY_TICKS          = 30     # ticks (~3 s) during which sleep re-entry is blocked
SUPPRESSION_DECAY_RATE    = 0.002  # suppression decays per tick after a false wake
FALSE_WAKE_PRESSURE_MAX   = 0.1    # waking below this sleep_pressure is a "false wake"
SUPPRESSION_BOOST         = 0.4    # how much suppression a false wake adds

BROADCAST_EVERY_N_TICKS   = 10


# ── state ──────────────────────────────────────────────────────────────────────

_mode             = ArousalMode.LIGHT_SLEEP
_arousal          = 0.1
_sleep_pressure   = 0.0
_fatigue          = 0.0
_suppression      = 0.0   # Stage 2: inhibitory suppression [0, 1]
_refractory_ticks = 0     # ticks remaining in refractory period
_tick_count       = 0


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _save() -> None:
    state_store.set("arousal.mode",           _mode.value)
    state_store.set("arousal.arousal_level",  _arousal)
    state_store.set("arousal.sleep_pressure", _sleep_pressure)
    state_store.set("arousal.fatigue_level",  _fatigue)
    state_store.set("arousal.suppression",    _suppression)


def _load() -> None:
    global _mode, _arousal, _sleep_pressure, _fatigue, _suppression
    _mode           = ArousalMode(state_store.get("arousal.mode", ArousalMode.LIGHT_SLEEP.value))
    _arousal        = state_store.get("arousal.arousal_level",  0.1)
    _sleep_pressure = state_store.get("arousal.sleep_pressure", 0.0)
    _fatigue        = state_store.get("arousal.fatigue_level",  0.0)
    _suppression    = state_store.get("arousal.suppression",    0.0)
    # Refractory counter is not persisted — it resets on restart intentionally


async def _transition(new_mode: ArousalMode, reason: str) -> None:
    global _mode, _refractory_ticks, _suppression
    if new_mode == _mode:
        return
    prev  = _mode
    _mode = new_mode
    logger.info("arousal: %s → %s (%s)", prev.value, new_mode.value, reason)

    # Start refractory period on any wake transition
    if new_mode in (ArousalMode.WAKEFUL, ArousalMode.FOCUSED):
        _refractory_ticks = REFRACTORY_TICKS
        # Penalise false wakes with suppression
        if _sleep_pressure < FALSE_WAKE_PRESSURE_MAX:
            _suppression = _clamp(_suppression + SUPPRESSION_BOOST)
            logger.debug(
                "false wake detected (pressure=%.3f) — suppression → %.3f",
                _sleep_pressure, _suppression,
            )

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
    global _arousal, _sleep_pressure, _fatigue, _suppression, _refractory_ticks, _tick_count
    _tick_count += 1

    asleep = _mode in (ArousalMode.DEEP_SLEEP, ArousalMode.LIGHT_SLEEP, ArousalMode.RECOVERY)

    # Decay suppression each tick
    if _suppression > 0:
        _suppression = _clamp(_suppression - SUPPRESSION_DECAY_RATE)

    # Count down refractory period
    if _refractory_ticks > 0:
        _refractory_ticks -= 1

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

    # Effective wake threshold is raised by suppression
    effective_wake_threshold = _clamp(WAKE_THRESHOLD + _suppression)

    # ── transition logic ──────────────────────────────────────────────────────

    if asleep:
        if _sleep_pressure >= effective_wake_threshold:
            await _transition(ArousalMode.WAKEFUL, "sleep_pressure_threshold")

    else:  # awake
        if _arousal >= FOCUSED_AROUSAL_THRESHOLD:
            await _transition(ArousalMode.FOCUSED, "high_arousal")

        elif _arousal <= SLEEP_THRESHOLD and _refractory_ticks == 0:
            # High fatigue with low pressure → recovery instead of deep sleep
            if _fatigue > 0.5 and _sleep_pressure > DEEP_SLEEP_THRESHOLD:
                await _transition(ArousalMode.RECOVERY, "high_fatigue")
            elif _sleep_pressure <= DEEP_SLEEP_THRESHOLD:
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
                suppression=_suppression,
            )
        )
        _save()


async def on_orienting_response(event: OrientingResponseEvent) -> None:
    """Apply the arousal delta from the orienting reflex.

    This closes the sensory→arousal loop: a loud sound while sleeping will
    spike _arousal, which may cross the wake threshold and trigger a mode
    transition on the next tick — matching the startle/orient response in
    biological systems.
    """
    global _arousal
    if event.arousal_delta == 0.0:
        return
    prev     = _arousal
    _arousal = _clamp(_arousal + event.arousal_delta)
    if abs(_arousal - prev) > 0.01:
        logger.debug(
            "arousal: orienting delta %+.3f  (%s)  %.3f → %.3f",
            event.arousal_delta, event.category.value, prev, _arousal,
        )
    # Immediately check for wake transition so loud sounds wake the system
    # within one event rather than waiting for the next clock tick
    if _mode in (ArousalMode.DEEP_SLEEP, ArousalMode.LIGHT_SLEEP, ArousalMode.RECOVERY):
        effective_wake_threshold = _clamp(WAKE_THRESHOLD + _suppression)
        if _arousal >= effective_wake_threshold:
            await _transition(ArousalMode.WAKEFUL, f"sensory_arousal_{event.category.value.lower()}")


def init() -> None:
    _load()
    bus.subscribe(clock.TickEvent, on_tick)
    bus.subscribe(OrientingResponseEvent, on_orienting_response)
    logger.info(
        "arousal initialized — mode=%s arousal=%.3f sleep_pressure=%.3f "
        "fatigue=%.3f suppression=%.3f",
        _mode.value, _arousal, _sleep_pressure, _fatigue, _suppression,
    )
