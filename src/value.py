"""
Reinforcement / Value Signal — Stage 6.

This is the module STEPS.md places at Stage 6 ("Value Signal") and MODULES.md
calls the Reinforcement / Value module. STEPS orders it developmentally before
the predictive loop (Stage 7), but the MODULES.md initialisation order puts it
at slot #9 — *after* the prediction engine — because the value signal consumes
the predictor's error/progress events. Both are true: it is grown before the
loop conceptually, and initialised after it because it depends on the
predictor's output. It was skipped when "Stage 6" shipped as mic input; this
back-fills it.

What it does
------------
Maintains the six innate drives from GENOME.md as scalar satisfaction levels in
[0,1] (neutral baseline 0.5), updated continuously from observable signals:

  D1 Continuity  — persistence / stable runtime; unclean restarts are penalised
  D2 Stability   — coherence; runaway prediction error and arousal oscillation
                   (suppression) lower it
  D3 Energy      — compute metabolism; fatigue, sleep pressure, and tick jitter
                   (compute strain) lower it
  D4 Curiosity   — learning progress (error reduction *over time*, NOT raw
                   novelty — deliberately avoids novelty addiction)
  D5 Social      — caregiver bond; speech-like interaction satisfies it,
                   prolonged deprivation is aversive; explicit caregiver
                   feedback is the strong channel (arrives at Stage 9)
  D6 Integrity   — genome protection; sandbox violations are strongly aversive

Reward is not truth — reward is "what mattered" (GENOME L3). The module emits:
  RewardSignalEvent   on meaningful positive change (learning progress,
                      caregiver approval, a worthwhile wake)
  PenaltySignalEvent  on an aversive consequence (sandbox violation, caregiver
                      disapproval, a nuisance/false wake)
  DriveStateEvent     periodic broadcast of all six drives + dominant drive +
                      net value + the current wake-threshold policy bias

Policy adjustment (STEPS Stage 6: "behaviour begins adapting meaningfully")
---------------------------------------------------------------------------
The one behavioural degree of freedom that exists before higher cognition is
*whether to wake*. The module runs a small reinforcement loop over it: each
wake episode accrues a value (an intrinsic energy cost, offset by interaction
and learning gathered while awake). Worthwhile wakes reinforce a lower wake
threshold (easier to rouse); nuisance/false wakes reinforce a higher one. The
adjustment is published on DriveStateEvent as `wake_threshold_bias` and read by
the arousal module, mirroring how the predictor's surprise signal modulates the
threshold. The bias is hard-clamped to +/-MAX_WAKE_BIAS so value learning can
never destabilise arousal regulation (cf. STEPS Stage 10 stability criteria).

Anti-hardcoding note
--------------------
Every drive update is a domain-general regulatory / intrinsic-motivation
signal. Nothing here encodes task knowledge: speech-like input raises the
*social* drive because prosody is an innate salience prior (GENOME P1/P4), not
because the system understands speech. No labels, vocabulary, or answers — only
the mechanism that lets value emerge from experience.
"""

import logging
import math
from collections import deque

import bus
import clock
import state_store
from events import (
    ArousalMode, ArousalStateEvent, SleepModeChangeEvent,
    OrientingResponseEvent, SoundCategory,
    PredictionErrorEvent, LearningProgressEvent,
    RewardSignalEvent, PenaltySignalEvent, DriveStateEvent,
    CaregiverFeedbackEvent,
)
from homeostasis import HealthReportEvent
from sandbox import ViolationEvent

logger = logging.getLogger(__name__)


# ── drives ──────────────────────────────────────────────────────────────────────

DRIVES = ("continuity", "stability", "energy", "curiosity", "social", "integrity")
BASELINE = 0.5


# ── tuneable parameters (small and slow — consistent with the rest of the system) ─

# Homeostatic pull of every drive back toward baseline each tick, so transient
# pushes fade and the drives stay in tension (GENOME: always in tension).
DRIVE_DECAY              = 0.0010

# D1 Continuity
CONTINUITY_UPTIME_RATE   = 0.0004    # satisfaction earned per tick of uptime
CONTINUITY_UPTIME_CAP    = 0.85      # uptime alone won't push above this
UNCLEAN_RESTART_PENALTY  = 0.30      # continuity hit when the prior session crashed

# D2 Stability
STABILITY_ERR_HIGH       = 0.35      # prediction error above this is destabilising
STABILITY_ERR_LOW        = 0.10      # below this is coherent
STABILITY_RATE           = 0.02
SUPPRESSION_PENALTY_RATE = 0.03      # arousal suppression (oscillation) lowers it

# D3 Energy
ENERGY_RATE              = 0.02
JITTER_STRAIN_MS         = 25.0      # tick jitter above this signals compute strain

# D4 Curiosity (learning progress, NOT novelty)
CURIOSITY_PROGRESS_GAIN  = 3.0       # maps error_trend -> drive nudge
CURIOSITY_NUDGE_CAP      = 0.05
CURIOSITY_REWARD_MIN     = 0.01      # nudge above which we emit a RewardSignal

# D5 Social
SOCIAL_DEPRIVATION_RATE  = 0.0006    # decay per tick toward the deprivation floor
SOCIAL_DEPRIVATION_FLOOR = 0.15
SOCIAL_SPEECH_GAIN       = 0.04      # per speech-like chunk while engaged

# D6 Integrity
INTEGRITY_VIOLATION_HIT  = 0.40      # strong, per GENOME D6

# Wake-episode value -> policy (wake threshold) learning
WAKE_BASE_COST           = 0.20      # being awake has an intrinsic energy cost
WAKE_SPEECH_VALUE        = 0.15      # worth of speech-like interaction per chunk
WAKE_PROGRESS_VALUE      = 1.50      # worth of learning progress while awake
WAKE_BIAS_LEARN_RATE     = 0.02
MAX_WAKE_BIAS            = 0.06      # hard clamp — cannot destabilise arousal

# Broadcast / persistence cadence
BROADCAST_EVERY_TICKS    = 20        # ~2 s at 10 Hz
REWARD_HISTORY_LEN       = 100


# ── state ──────────────────────────────────────────────────────────────────────

_drives: dict[str, float] = {d: BASELINE for d in DRIVES}
_wake_threshold_bias: float = 0.0
_reward_history: deque = deque(maxlen=REWARD_HISTORY_LEN)
_ewa_reward: float = 0.0

_mode: ArousalMode = ArousalMode.LIGHT_SLEEP
_awake: bool = False
_episode_value: float = 0.0   # accrued value of the current wake episode
_tick_count: int = 0
_uptime_credit: float = 0.0   # continuity earned from this session's uptime


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _nudge(drive: str, delta: float) -> None:
    _drives[drive] = _clamp(_drives[drive] + delta)


def _is_awake(mode: ArousalMode) -> bool:
    return mode in (ArousalMode.WAKEFUL, ArousalMode.FOCUSED)


def _accrue_episode(value: float) -> None:
    """Add to the current wake episode's value (only while awake)."""
    global _episode_value
    if _awake:
        _episode_value += value


# ── reward / penalty emission ───────────────────────────────────────────────────

async def _reward(magnitude: float, drive: str, reason: str) -> None:
    global _ewa_reward
    magnitude = _clamp(magnitude)
    if magnitude <= 0.0:
        return
    _reward_history.append(+magnitude)
    _ewa_reward = 0.1 * magnitude + 0.9 * _ewa_reward
    await bus.publish(RewardSignalEvent(
        source="value", timestamp=clock.elapsed(),
        magnitude=magnitude, drive=drive, reason=reason,
    ))


async def _penalty(magnitude: float, drive: str, reason: str) -> None:
    global _ewa_reward
    magnitude = _clamp(magnitude)
    if magnitude <= 0.0:
        return
    _reward_history.append(-magnitude)
    _ewa_reward = 0.1 * (-magnitude) + 0.9 * _ewa_reward
    await bus.publish(PenaltySignalEvent(
        source="value", timestamp=clock.elapsed(),
        magnitude=magnitude, drive=drive, reason=reason,
    ))


# ── input handlers ──────────────────────────────────────────────────────────────

async def on_prediction_error(event: PredictionErrorEvent) -> None:
    # D2 Stability: coherent prediction is stabilising; runaway error is not.
    if event.error >= STABILITY_ERR_HIGH:
        _nudge("stability", -STABILITY_RATE)
    elif event.error <= STABILITY_ERR_LOW:
        _nudge("stability", +STABILITY_RATE)


async def on_learning_progress(event: LearningProgressEvent) -> None:
    # D4 Curiosity: reward is *learning progress* — error_trend < 0 means the
    # model is improving. Raw novelty/surprise is deliberately NOT rewarded.
    nudge = _clamp(-event.error_trend * CURIOSITY_PROGRESS_GAIN,
                   -CURIOSITY_NUDGE_CAP, CURIOSITY_NUDGE_CAP)
    _nudge("curiosity", nudge)
    if nudge > 0:
        _accrue_episode(nudge * WAKE_PROGRESS_VALUE)
    if nudge >= CURIOSITY_REWARD_MIN:
        await _reward(nudge, "curiosity", "learning_progress")


async def on_arousal_state(event: ArousalStateEvent) -> None:
    global _mode
    _mode = event.mode
    # D3 Energy: fatigue and sleep pressure are the metabolic cost signals.
    energy_target = 1.0 - 0.5 * (event.fatigue_level + event.sleep_pressure)
    _nudge("energy", ENERGY_RATE * (energy_target - _drives["energy"]))
    # D2 Stability: suppression rises with oscillation / false wakes.
    if event.suppression > 0.0:
        _nudge("stability", -SUPPRESSION_PENALTY_RATE * event.suppression)


async def on_health_report(event: HealthReportEvent) -> None:
    # D3 Energy / D2 Stability: compute strain shows up as tick jitter.
    if event.tick_jitter_ms > JITTER_STRAIN_MS:
        _nudge("energy", -ENERGY_RATE)
        _nudge("stability", -STABILITY_RATE)


async def on_orienting_response(event: OrientingResponseEvent) -> None:
    # D5 Social: speech-like input is innate social salience (GENOME P1/P4),
    # not understood content. It satisfies the social drive and makes the
    # current wake episode worthwhile.
    if event.category == SoundCategory.SPEECH:
        _nudge("social", +SOCIAL_SPEECH_GAIN)
        _accrue_episode(WAKE_SPEECH_VALUE)


async def on_caregiver_feedback(event: CaregiverFeedbackEvent) -> None:
    # Forward hook for the Stage 9 caregiver interface. Nothing publishes this
    # yet; when the caregiver module exists this becomes the strong social
    # reinforcement channel (GENOME L3 / consequences system).
    mag = _clamp(abs(event.valence) * max(event.intensity, 0.0))
    if mag <= 0.0:
        return
    if event.valence >= 0:
        _nudge("social", +mag)
        _accrue_episode(+mag)
        await _reward(mag, "social", f"caregiver_{event.kind}")
    else:
        _nudge("social", -mag)
        _accrue_episode(-mag)
        await _penalty(mag, "social", f"caregiver_{event.kind}")


async def on_violation(event: ViolationEvent) -> None:
    # D6 Integrity: an attempt to use a forbidden capability is an axiom breach
    # — strongly aversive (GENOME D6).
    _nudge("integrity", -INTEGRITY_VIOLATION_HIT)
    await _penalty(INTEGRITY_VIOLATION_HIT, "integrity",
                   f"sandbox_violation:{event.capability.name}")


async def on_sleep_mode_change(event: SleepModeChangeEvent) -> None:
    # Wake-episode bookkeeping drives the wake-threshold policy reinforcement.
    global _awake, _episode_value
    was_awake = _is_awake(event.previous_mode)
    now_awake = _is_awake(event.new_mode)
    if now_awake and not was_awake:
        _awake = True
        _episode_value = -WAKE_BASE_COST     # a wake starts "in debt"
    elif was_awake and not now_awake:
        _awake = False
        await _settle_episode()


async def _settle_episode() -> None:
    """A wake episode just ended. Reinforce the wake threshold by its value."""
    global _wake_threshold_bias, _episode_value
    value = _episode_value
    _episode_value = 0.0
    # Worthwhile (value > 0) -> lower threshold (easier wake). Nuisance
    # (value < 0) -> raise threshold (harder wake). tanh keeps the step bounded.
    step = WAKE_BIAS_LEARN_RATE * math.tanh(value)
    _wake_threshold_bias = _clamp(_wake_threshold_bias - step,
                                  -MAX_WAKE_BIAS, MAX_WAKE_BIAS)
    if value >= 0:
        _nudge("continuity", +0.02)
        await _reward(min(value, 1.0), "continuity", "worthwhile_wake")
    else:
        # Repeated false / nuisance wakes are explicitly aversive (GENOME L3).
        await _penalty(min(-value, 1.0), "energy", "nuisance_wake")


async def on_tick(event: clock.TickEvent) -> None:
    global _tick_count, _uptime_credit
    _tick_count += 1

    # Homeostatic decay of every drive back toward baseline.
    for d in DRIVES:
        cur = _drives[d]
        _drives[d] = cur + DRIVE_DECAY * (BASELINE - cur)

    # D1 Continuity: sustained uptime is rewarded (persistence).
    if _uptime_credit < CONTINUITY_UPTIME_CAP:
        _uptime_credit = min(CONTINUITY_UPTIME_CAP,
                             _uptime_credit + CONTINUITY_UPTIME_RATE)
        _nudge("continuity", +CONTINUITY_UPTIME_RATE)

    # D5 Social: drift toward deprivation when no interaction arrives.
    if _drives["social"] > SOCIAL_DEPRIVATION_FLOOR:
        _nudge("social", -SOCIAL_DEPRIVATION_RATE)

    if _tick_count % BROADCAST_EVERY_TICKS == 0:
        await _broadcast()
        _save()


# ── broadcast & persistence ──────────────────────────────────────────────────────

def _dominant_drive() -> str:
    # The most pressing drive is the one furthest *below* baseline (least satisfied).
    return min(DRIVES, key=lambda d: _drives[d])


def _net_value() -> float:
    return sum(_drives[d] - BASELINE for d in DRIVES) / len(DRIVES)


async def _broadcast() -> None:
    await bus.publish(DriveStateEvent(
        source="value", timestamp=clock.elapsed(),
        continuity=_drives["continuity"], stability=_drives["stability"],
        energy=_drives["energy"], curiosity=_drives["curiosity"],
        social=_drives["social"], integrity=_drives["integrity"],
        dominant_drive=_dominant_drive(), net_value=_net_value(),
        wake_threshold_bias=_wake_threshold_bias,
    ))


def _save() -> None:
    for d in DRIVES:
        state_store.set(f"value.drive.{d}", _drives[d])
    state_store.set("value.wake_threshold_bias", _wake_threshold_bias)
    state_store.set("value.ewa_reward", _ewa_reward)


def _load() -> None:
    global _wake_threshold_bias, _ewa_reward
    for d in DRIVES:
        _drives[d] = state_store.get(f"value.drive.{d}", BASELINE)
    _wake_threshold_bias = state_store.get("value.wake_threshold_bias", 0.0)
    _ewa_reward = state_store.get("value.ewa_reward", 0.0)


def mark_clean_shutdown() -> None:
    """Called by main on graceful shutdown so the next boot can tell a clean
    stop from a crash (D1 Continuity)."""
    _save()
    state_store.set("value.clean_shutdown", True)


def init() -> None:
    _load()
    # D1 Continuity: detect an unclean restart (the prior session never marked a
    # clean shutdown) and register it as a self-preservation penalty. Applied
    # directly to the drive — the bus is not running yet, so it surfaces on the
    # first DriveStateEvent broadcast rather than as an immediate event.
    prior_clean = state_store.get("value.clean_shutdown", True)
    if not prior_clean:
        _drives["continuity"] = _clamp(_drives["continuity"] - UNCLEAN_RESTART_PENALTY)
        logger.warning("value: unclean restart detected — continuity penalty applied")
    state_store.set("value.clean_shutdown", False)   # mark this session as running

    bus.subscribe(clock.TickEvent, on_tick)
    bus.subscribe(PredictionErrorEvent, on_prediction_error)
    bus.subscribe(LearningProgressEvent, on_learning_progress)
    bus.subscribe(ArousalStateEvent, on_arousal_state)
    bus.subscribe(HealthReportEvent, on_health_report)
    bus.subscribe(OrientingResponseEvent, on_orienting_response)
    bus.subscribe(SleepModeChangeEvent, on_sleep_mode_change)
    bus.subscribe(CaregiverFeedbackEvent, on_caregiver_feedback)
    bus.subscribe(ViolationEvent, on_violation)
    logger.info(
        "value (Stage 6 reinforcement) initialized — drives=%s wake_bias=%+.3f",
        {d: round(_drives[d], 2) for d in DRIVES}, _wake_threshold_bias,
    )
