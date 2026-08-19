"""
Unit tests for the audio motor / voice (src/audio_motor.py).

The central claim under test is that the system does not know what its own
voice does: the mapping from motor commands to perceived sound starts empty
and is learned only by babbling and listening. These tests never open the
speaker - vocalise() is exercised through its gates, and the forward model is
driven directly.

Runs under pytest or directly:  python tests/unit/test_audio_motor.py
"""

import asyncio
import random
import sys
import tempfile
from pathlib import Path

# Make src/ importable whether run via pytest or as a script.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import audio_motor
import bus
import sandbox
import state_store
from events import ArousalMode


_PUBLISHED: list = []


async def _collect(event) -> None:
    _PUBLISHED.append(event)


def _reset(stage: int = 5) -> None:
    _PUBLISHED.clear()
    state_store.init(Path(tempfile.mkdtemp()) / "state.db")
    bus.publish = _collect
    sandbox.init(stage=stage)
    audio_motor._M = [[0.0] * audio_motor.MOTOR_DIM
                      for _ in range(audio_motor.FEATURE_DIM)]
    audio_motor._c = [0.0] * audio_motor.FEATURE_DIM
    audio_motor._model_updates = 0
    audio_motor._pending_motor = None
    audio_motor._echo_frames = []
    audio_motor._utterances = 0
    audio_motor._last_utterance = -10_000
    audio_motor._enabled = False
    audio_motor._current_mode = ArousalMode.WAKEFUL


# A hidden "body" the tests use as ground truth. The module never sees this;
# it must discover the relationship by pairing commands with results.
def _true_body(motor):
    p, d, a, t = motor
    return [
        0.9 * a,                      # loudness follows amplitude
        0.2 + 0.5 * p,                # brightness follows pitch
        0.1 + 0.8 * p,                # centroid follows pitch
        0.6 - 0.3 * t,                # flatness falls as timbre rises
        0.3 + 0.4 * d,                # band ratio follows duration
    ]


# -- the model starts ignorant --------------------------------------------------

def test_forward_model_starts_empty():
    """It is born not knowing what its own voice does."""
    _reset()

    assert all(all(v == 0.0 for v in row) for row in audio_motor._M), \
        "the motor-to-perception mapping must start unlearned"
    assert audio_motor._model_updates == 0, "no experience at birth"


def test_prediction_is_bounded_even_when_untrained():
    _reset()

    for motor in ([0, 0, 0, 0], [1, 1, 1, 1], [0.5] * 4):
        pred = audio_motor.predict_perception(motor)
        assert len(pred) == audio_motor.FEATURE_DIM, "prediction must be well-shaped"
        assert all(0.0 <= v <= 1.0 for v in pred), "prediction must stay in range"


# -- learning by listening ------------------------------------------------------

def test_babbling_teaches_the_forward_model():
    """Pair random commands with what they produced; the mapping should emerge."""
    _reset()
    random.seed(7)

    def mean_err():
        total = 0.0
        for _ in range(60):
            m = [random.random() for _ in range(audio_motor.MOTOR_DIM)]
            pred = audio_motor.predict_perception(m)
            truth = _true_body(m)
            total += sum(abs(p - t) for p, t in zip(pred, truth)) / len(truth)
        return total / 60

    random.seed(1)
    before = mean_err()

    random.seed(2)
    for _ in range(3000):
        m = [random.random() for _ in range(audio_motor.MOTOR_DIM)]
        audio_motor._learn(m, _true_body(m))

    random.seed(1)
    after = mean_err()

    assert audio_motor._model_updates == 3000, "every pairing must be a learning step"
    assert after < before * 0.5, \
        f"babbling must substantially improve the model ({before:.4f} -> {after:.4f})"


def test_hearing_its_own_voice_updates_the_model():
    """The loop that closes motor and perception: emit, hear, learn."""
    _reset()
    audio_motor._pending_motor = [0.5, 0.5, 0.8, 0.2]

    async def run():
        from events import AudioEnergyEvent
        for _ in range(audio_motor.LISTEN_CHUNKS):
            await audio_motor.on_audio_energy(AudioEnergyEvent(
                source="mic", timestamp=0.0, rms=0.4, zcr=0.3,
                spectral_centroid=3200.0, spectral_flatness=0.5,
                band_ratio=0.5, chunk_ms=200))

    asyncio.run(run())

    assert audio_motor._model_updates == 1, "a heard utterance must train the model"
    assert audio_motor._pending_motor is None, "the utterance must be consumed"


def test_audio_without_a_pending_utterance_is_ignored():
    """Ambient sound is not evidence about the system's own voice."""
    _reset()

    async def run():
        from events import AudioEnergyEvent
        for _ in range(10):
            await audio_motor.on_audio_energy(AudioEnergyEvent(
                source="mic", timestamp=0.0, rms=0.4, zcr=0.3,
                spectral_centroid=3200.0, spectral_flatness=0.5,
                band_ratio=0.5, chunk_ms=200))

    asyncio.run(run())

    assert audio_motor._model_updates == 0, \
        "sound the system did not cause must not train its motor model"


# -- imitation ------------------------------------------------------------------

def test_imitation_planning_improves_once_the_body_is_known():
    """Criterion B in miniature: search motor space for a target sound."""
    _reset()
    random.seed(3)

    target = _true_body([0.8, 0.3, 0.7, 0.2])

    # Untrained: planning is guesswork against an empty model.
    motor_before, _ = audio_motor.plan_imitation(target)
    true_err_before = sum(
        abs(a - b) for a, b in zip(_true_body(motor_before), target)
    ) / len(target)

    for _ in range(4000):
        m = [random.random() for _ in range(audio_motor.MOTOR_DIM)]
        audio_motor._learn(m, _true_body(m))

    motor_after, _ = audio_motor.plan_imitation(target)
    true_err_after = sum(
        abs(a - b) for a, b in zip(_true_body(motor_after), target)
    ) / len(target)

    assert true_err_after < true_err_before, (
        "imitation must improve as the forward model improves "
        f"({true_err_before:.4f} -> {true_err_after:.4f})"
    )


def test_planned_motor_commands_stay_in_range():
    _reset()
    random.seed(5)

    motor, _ = audio_motor.plan_imitation([0.5] * audio_motor.FEATURE_DIM)

    assert len(motor) == audio_motor.MOTOR_DIM, "plan must fill the motor space"
    assert all(0.0 <= v <= 1.0 for v in motor), "motor commands must stay bounded"


# -- safety gates ---------------------------------------------------------------

def test_vocalisation_is_off_by_default():
    _reset()

    assert audio_motor._enabled is False, "the voice must not switch itself on"
    assert asyncio.run(audio_motor.vocalise([0.5] * 4)) is False, \
        "a disabled voice must stay silent"


def test_vocalisation_requires_the_audio_output_capability():
    """Containment: the sandbox gates the speaker, not the module itself."""
    _reset(stage=0)               # AUDIO_OUTPUT unlocks at stage 3
    audio_motor.enable(True)

    assert sandbox.is_allowed(sandbox.Capability.AUDIO_OUTPUT) is False, "precondition"
    assert asyncio.run(audio_motor.vocalise([0.5] * 4)) is False, \
        "the voice must not sound before the capability is unlocked"


def test_vocalisation_is_silent_while_asleep():
    _reset()
    audio_motor.enable(True)
    audio_motor._current_mode = ArousalMode.DEEP_SLEEP

    assert asyncio.run(audio_motor.vocalise([0.5] * 4)) is False, \
        "a sleeping system must not babble"


def test_babbling_respects_the_minimum_interval():
    _reset()
    audio_motor.enable(True)
    audio_motor._last_utterance = 0

    # Just below the interval: must stay quiet.
    import clock as _clock
    audio_motor._tick_count = audio_motor.MIN_INTERVAL_TICKS - 2
    asyncio.run(audio_motor.on_tick(_clock.TickEvent(
        source="clock", timestamp=0.0, tick=1)))

    assert audio_motor._utterances == 0, \
        "babbling must not exceed the minimum interval between utterances"


def test_enable_persists_the_choice():
    _reset()

    audio_motor.enable(True)
    assert state_store.get("audio_motor.enabled") is True, \
        "the caregiver's choice must survive a restart"

    audio_motor.enable(False)
    assert state_store.get("audio_motor.enabled") is False, "and be revocable"


# -- persistence ----------------------------------------------------------------

def test_forward_model_survives_a_save_load_cycle():
    _reset()
    random.seed(11)
    for _ in range(200):
        m = [random.random() for _ in range(audio_motor.MOTOR_DIM)]
        audio_motor._learn(m, _true_body(m))

    learned = [row[:] for row in audio_motor._M]
    audio_motor.save_state()

    audio_motor._M = [[0.0] * audio_motor.MOTOR_DIM
                      for _ in range(audio_motor.FEATURE_DIM)]
    assert audio_motor.load_state() is True, "a saved motor model must be found"
    assert audio_motor._M == learned, "what the body learned must persist"


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
