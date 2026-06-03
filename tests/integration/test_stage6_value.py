"""
Stage 6 (Value Signal / Reinforcement) integration tests.

Exercises the value module's drive dynamics, reward/penalty emission, and the
wake-threshold policy loop, and confirms the arousal module consumes the
policy bias. Handlers are driven directly with constructed events and
bus.publish is captured, so the tests are deterministic and need no running
bus, pytest plugins, torch, or audio hardware.

Runs under pytest or directly:  python tests/integration/test_stage6_value.py
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Make src/ importable whether run via pytest or as a script.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import bus
import clock
import state_store
import value
import arousal
from events import (
    ArousalMode, ArousalStateEvent, SleepModeChangeEvent,
    OrientingResponseEvent, SoundCategory, ArousalSignal,
    PredictionErrorEvent, LearningProgressEvent,
    CaregiverFeedbackEvent, RewardSignalEvent, PenaltySignalEvent,
    DriveStateEvent,
)
from sandbox import ViolationEvent, Capability


# ── harness ──────────────────────────────────────────────────────────────────────

_PUBLISHED: list = []


async def _collect(event) -> None:
    _PUBLISHED.append(event)


def _reset() -> None:
    """Fresh state store + value module reset to neutral baseline."""
    _PUBLISHED.clear()
    db = Path(tempfile.mkdtemp()) / "state.db"
    state_store.init(db)
    bus.publish = _collect            # capture all emissions
    value._drives = {d: value.BASELINE for d in value.DRIVES}
    value._wake_threshold_bias = 0.0
    value._reward_history.clear()
    value._ewa_reward = 0.0
    value._mode = ArousalMode.LIGHT_SLEEP
    value._awake = False
    value._episode_value = 0.0
    value._tick_count = 0
    value._uptime_credit = 0.0


def _published(kind) -> list:
    return [e for e in _PUBLISHED if isinstance(e, kind)]


def _sleep(prev, new) -> SleepModeChangeEvent:
    return SleepModeChangeEvent(source="t", timestamp=0.0,
                                previous_mode=prev, new_mode=new, reason="test")


# ── tests ──────────────────────────────────────────────────────────────────────

def test_learning_progress_rewards_curiosity():
    _reset()

    async def run():
        before = value._drives["curiosity"]
        # error_trend < 0 means the model is improving -> curiosity reward.
        await value.on_learning_progress(LearningProgressEvent(
            source="t", timestamp=0.0,
            mean_error=0.2, error_trend=-0.04, model_age_chunks=100,
        ))
        assert value._drives["curiosity"] > before, "improving model should satisfy curiosity"
        assert _published(RewardSignalEvent), "learning progress should emit a reward"
        assert _published(RewardSignalEvent)[0].drive == "curiosity"

        # A worsening model must NOT be rewarded (no novelty addiction).
        _PUBLISHED.clear()
        peak = value._drives["curiosity"]
        await value.on_learning_progress(LearningProgressEvent(
            source="t", timestamp=0.0,
            mean_error=0.5, error_trend=+0.04, model_age_chunks=200,
        ))
        assert value._drives["curiosity"] < peak, "worsening model should lower curiosity"
        assert not _published(RewardSignalEvent), "regression must not be rewarded"

    asyncio.run(run())


def test_prediction_error_moves_stability():
    _reset()

    async def run():
        base = value._drives["stability"]
        await value.on_prediction_error(PredictionErrorEvent(
            source="t", timestamp=0.0, error=0.6, surprise=0.7, feature_errors=[],
        ))
        assert value._drives["stability"] < base, "runaway error should reduce stability"

        value._drives["stability"] = value.BASELINE
        await value.on_prediction_error(PredictionErrorEvent(
            source="t", timestamp=0.0, error=0.02, surprise=0.0, feature_errors=[],
        ))
        assert value._drives["stability"] > value.BASELINE, "coherent prediction should raise stability"

    asyncio.run(run())


def test_sandbox_violation_hits_integrity_hard():
    _reset()

    async def run():
        base = value._drives["integrity"]
        await value.on_violation(ViolationEvent(
            source="sandbox", timestamp=0.0,
            requesting_module="rogue", capability=Capability.NETWORK,
        ))
        assert value._drives["integrity"] <= base - 0.3, "violation must strongly hit integrity"
        pens = _published(PenaltySignalEvent)
        assert pens and pens[0].drive == "integrity"

    asyncio.run(run())


def test_nuisance_wake_raises_threshold_worthwhile_lowers():
    _reset()

    async def run():
        # A wake with no interaction = nuisance -> threshold bias should rise.
        await value.on_sleep_mode_change(_sleep(ArousalMode.LIGHT_SLEEP, ArousalMode.WAKEFUL))
        await value.on_sleep_mode_change(_sleep(ArousalMode.WAKEFUL, ArousalMode.LIGHT_SLEEP))
        assert value._wake_threshold_bias > 0, "nuisance wake should make waking harder"
        assert any(p.reason == "nuisance_wake" for p in _published(PenaltySignalEvent))

        # A wake full of speech-like interaction = worthwhile -> bias should fall.
        value._wake_threshold_bias = 0.0
        _PUBLISHED.clear()
        await value.on_sleep_mode_change(_sleep(ArousalMode.LIGHT_SLEEP, ArousalMode.WAKEFUL))
        for _ in range(3):
            await value.on_orienting_response(OrientingResponseEvent(
                source="t", timestamp=0.0, category=SoundCategory.SPEECH,
                confidence=0.9, arousal_delta=0.08, arousal_signal=ArousalSignal.SPEECH,
            ))
        await value.on_sleep_mode_change(_sleep(ArousalMode.WAKEFUL, ArousalMode.LIGHT_SLEEP))
        assert value._wake_threshold_bias < 0, "worthwhile wake should make waking easier"
        assert any(r.reason == "worthwhile_wake" for r in _published(RewardSignalEvent))

    asyncio.run(run())


def test_wake_bias_stays_bounded():
    _reset()

    async def run():
        # Many consecutive nuisance wakes must never exceed the clamp.
        for _ in range(200):
            await value.on_sleep_mode_change(_sleep(ArousalMode.LIGHT_SLEEP, ArousalMode.WAKEFUL))
            await value.on_sleep_mode_change(_sleep(ArousalMode.WAKEFUL, ArousalMode.LIGHT_SLEEP))
        assert value._wake_threshold_bias <= value.MAX_WAKE_BIAS + 1e-9
        assert value._wake_threshold_bias >= -value.MAX_WAKE_BIAS - 1e-9

    asyncio.run(run())


def test_caregiver_feedback_channel():
    _reset()

    async def run():
        base = value._drives["social"]
        await value.on_caregiver_feedback(CaregiverFeedbackEvent(
            source="caregiver", timestamp=0.0, valence=0.8, kind="approval", intensity=1.0,
        ))
        assert value._drives["social"] > base, "approval should satisfy the social drive"
        assert _published(RewardSignalEvent)

        _PUBLISHED.clear()
        peak = value._drives["social"]
        await value.on_caregiver_feedback(CaregiverFeedbackEvent(
            source="caregiver", timestamp=0.0, valence=-0.8, kind="disapproval", intensity=1.0,
        ))
        assert value._drives["social"] < peak, "disapproval should lower the social drive"
        assert _published(PenaltySignalEvent)

    asyncio.run(run())


def test_broadcast_and_arousal_consumes_bias():
    _reset()

    async def run():
        # Drive a broadcast, then feed it to the arousal module.
        value._wake_threshold_bias = -0.04
        value._tick_count = value.BROADCAST_EVERY_TICKS - 1
        await value.on_tick(clock.TickEvent(source="clock", timestamp=0.0, tick=1))
        states = _published(DriveStateEvent)
        assert states, "value should broadcast a DriveStateEvent on cadence"
        assert states[0].wake_threshold_bias == value._wake_threshold_bias
        assert states[0].dominant_drive in value.DRIVES

        arousal._value_bias = 0.0
        await arousal.on_drive_state(states[0])
        assert arousal._value_bias == value._wake_threshold_bias, "arousal must adopt the bias"

        # Out-of-range bias is clamped by the arousal consumer.
        await arousal.on_drive_state(DriveStateEvent(
            source="value", timestamp=0.0, continuity=0.5, stability=0.5, energy=0.5,
            curiosity=0.5, social=0.5, integrity=0.5, dominant_drive="energy",
            net_value=0.0, wake_threshold_bias=-99.0,
        ))
        assert arousal._value_bias == -arousal.VALUE_BIAS_MAX, "arousal must clamp the bias"

    asyncio.run(run())


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
