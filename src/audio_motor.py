"""
Audio Motor / Vocalisation — Stage 9 groundwork.

Gives the system a body part it can move: a speaker. Everything else in the
runtime is perception; this is the first action.

Motor space
-----------
A vocalisation is four continuous parameters, all in [0,1]:

    pitch      → fundamental frequency
    duration   → length of the utterance
    amplitude  → loudness
    timbre     → strength of the second harmonic

These are the muscles, not the sounds. Nothing maps a parameter to a phoneme,
a word, or a target: the system is born not knowing what its own voice does.

Forward model (learned, never computed)
---------------------------------------
The system discovers what its voice does the way an infant does — by babbling
and listening. Each utterance is emitted, heard back through the microphone as
ordinary AudioEnergyEvents, and the resulting acoustic features are paired
with the motor parameters that produced them. A linear forward model

    perceived_features ≈ M · motor + c

is fitted online by SGD from those pairs. The synthesiser's actual physics is
never handed to the model; if the speaker is quiet, or the room is muffled, or
the microphone colours the sound, the learned mapping absorbs all of it.

Imitation (success criterion B)
-------------------------------
To imitate a remembered sound, the system searches its motor space for the
parameters whose *predicted* perception is closest to the target summary,
using the model it learned by babbling. It then emits that guess, hears the
result, and updates the model from the discrepancy. Imitation therefore
improves only insofar as the forward model is good, which is exactly the
dependency the design wants.

Safety
------
Vocalisation is disabled by default and must be switched on explicitly
(`audio_motor.enable()` or state key "audio_motor.enabled"). It is further
gated by the sandbox AUDIO_OUTPUT capability, which only unlocks at stage 3,
by arousal (silent while asleep), and by a minimum interval between
utterances. A system that babbles nonstop is unusable to the caregiver.
"""

import asyncio
import logging
import math
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import bus
import clock
import sandbox
import state_store
from events import AudioEnergyEvent, ArousalMode, ArousalStateEvent

logger = logging.getLogger(__name__)

# ── motor space ────────────────────────────────────────────────────────────────

MOTOR_DIM     = 4        # pitch, duration, amplitude, timbre
FEATURE_DIM   = 5        # the perceptual features the mic produces

PITCH_MIN_HZ  = 110.0
PITCH_MAX_HZ  = 900.0
DUR_MIN_S     = 0.10
DUR_MAX_S     = 0.60
AMP_MAX       = 0.30     # never louder than this, whatever the motor says

SAMPLE_RATE   = 44100

LEARNING_RATE = 0.08     # forward-model SGD step
MIN_INTERVAL_TICKS = 30  # ≥3 s between utterances at the 10 Hz clock
LISTEN_CHUNKS = 4        # audio chunks after an utterance treated as its echo

# ── state ──────────────────────────────────────────────────────────────────────

# Forward model: features ≈ M·motor + c. Zero init — it knows nothing.
_M: list = [[0.0] * MOTOR_DIM for _ in range(FEATURE_DIM)]
_c: list = [0.0] * FEATURE_DIM

_enabled:        bool = False
_current_mode:   ArousalMode = ArousalMode.LIGHT_SLEEP
_tick_count:     int = 0
_last_utterance: int = -10_000

_pending_motor:  list | None = None   # motor params awaiting their echo
_echo_frames:    list = []
_utterances:     int = 0
_model_updates:  int = 0

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice")


# ── events ─────────────────────────────────────────────────────────────────────

@dataclass
class VocalisationEvent(bus.Event):
    """The system made a sound."""
    motor:      list
    pitch_hz:   float
    duration_s: float
    kind:       str      # "babble" or "imitation"


@dataclass
class ImitationAttemptEvent(bus.Event):
    """An attempt to reproduce a remembered sound, and how close it landed."""
    target:            list
    motor:             list
    predicted_error:   float
    perceived_error:   float | None = None


# ── forward model ──────────────────────────────────────────────────────────────

def predict_perception(motor: list) -> list:
    """What the system expects to hear if it moves its voice this way."""
    out = []
    for i in range(FEATURE_DIM):
        v = _c[i]
        for j in range(MOTOR_DIM):
            v += _M[i][j] * motor[j]
        out.append(max(0.0, min(1.0, v)))
    return out


def _learn(motor: list, perceived: list) -> float:
    """One SGD step pairing an executed motor command with what it produced."""
    global _model_updates
    pred = predict_perception(motor)
    errs = [perceived[i] - pred[i] for i in range(FEATURE_DIM)]
    for i in range(FEATURE_DIM):
        _c[i] += LEARNING_RATE * errs[i]
        for j in range(MOTOR_DIM):
            _M[i][j] += LEARNING_RATE * errs[i] * motor[j]
    _model_updates += 1
    return sum(abs(e) for e in errs) / FEATURE_DIM


def plan_imitation(target: list, iterations: int = 240) -> tuple:
    """Search motor space for the utterance whose predicted perception is
    closest to `target`. Hill-climbing on the LEARNED model — no analytic
    inverse, because the system has no privileged access to its own physics.
    """
    best = [random.random() for _ in range(MOTOR_DIM)]
    best_d = _dist(predict_perception(best), target)

    step = 0.35
    for i in range(iterations):
        cand = [max(0.0, min(1.0, best[j] + random.gauss(0, step)))
                for j in range(MOTOR_DIM)]
        d = _dist(predict_perception(cand), target)
        if d < best_d:
            best, best_d = cand, d
        step *= 0.99   # anneal
    return best, best_d


def _dist(a: list, b: list) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return float("inf")
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(n)) / n)


# ── synthesis ──────────────────────────────────────────────────────────────────

def _motor_to_waveform(motor: list):
    """Turn motor parameters into samples. This is the body, not the brain:
    it is fixed physics, and the system must learn its behaviour by listening.
    """
    import numpy as np

    pitch, dur, amp, timbre = motor
    f0 = PITCH_MIN_HZ + pitch * (PITCH_MAX_HZ - PITCH_MIN_HZ)
    seconds = DUR_MIN_S + dur * (DUR_MAX_S - DUR_MIN_S)
    level = min(AMP_MAX, amp * AMP_MAX)

    t = np.linspace(0, seconds, int(SAMPLE_RATE * seconds), endpoint=False)
    env = np.minimum(1.0, np.minimum(t * 30, (seconds - t) * 30))
    wave = np.sin(2 * np.pi * f0 * t) + timbre * np.sin(2 * np.pi * 2 * f0 * t)
    wave = wave / (1.0 + timbre)
    return (level * env * wave).astype("float32"), f0, seconds


def _emit_blocking(motor: list) -> None:
    try:
        import sounddevice as sd
        wave, _, _ = _motor_to_waveform(motor)
        sd.play(wave, samplerate=SAMPLE_RATE, blocking=True)
    except Exception as e:
        logger.warning("audio_motor: emission failed (%s)", e)


async def vocalise(motor: list, kind: str = "babble") -> bool:
    """Emit one utterance, if permitted. Returns False if suppressed."""
    global _pending_motor, _echo_frames, _utterances, _last_utterance

    if not _enabled:
        return False
    if not sandbox.is_allowed(sandbox.Capability.AUDIO_OUTPUT):
        logger.debug("audio_motor: AUDIO_OUTPUT not unlocked at this stage")
        return False
    if _current_mode in (ArousalMode.DEEP_SLEEP, ArousalMode.LIGHT_SLEEP):
        return False

    motor = [max(0.0, min(1.0, v)) for v in motor]
    _pending_motor = motor
    _echo_frames = []
    _utterances += 1
    _last_utterance = _tick_count

    _, f0, seconds = _motor_to_waveform(motor)
    logger.info("audio_motor: %s — pitch=%.0fHz dur=%.2fs amp=%.2f timbre=%.2f",
                kind, f0, seconds, motor[2], motor[3])

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _emit_blocking, motor)

    await bus.publish(VocalisationEvent(
        source="audio_motor", timestamp=clock.elapsed(), motor=list(motor),
        pitch_hz=f0, duration_s=seconds, kind=kind,
    ))
    state_store.set("audio_motor.utterances", _utterances)
    return True


async def imitate(target: list) -> bool:
    """Try to reproduce a remembered acoustic shape."""
    motor, predicted = plan_imitation(target)
    ok = await vocalise(motor, kind="imitation")
    if ok:
        await bus.publish(ImitationAttemptEvent(
            source="audio_motor", timestamp=clock.elapsed(),
            target=list(target), motor=list(motor), predicted_error=predicted,
        ))
    return ok


# ── handlers ───────────────────────────────────────────────────────────────────

async def on_audio_energy(event: AudioEnergyEvent) -> None:
    """Hear the consequence of an utterance and learn from it."""
    global _pending_motor, _echo_frames

    if _pending_motor is None:
        return

    _echo_frames.append([
        event.rms,
        event.zcr,
        min(event.spectral_centroid / 16000.0, 1.0),
        event.spectral_flatness,
        event.band_ratio,
    ])
    if len(_echo_frames) < LISTEN_CHUNKS:
        return

    perceived = [
        sum(f[d] for f in _echo_frames) / len(_echo_frames)
        for d in range(FEATURE_DIM)
    ]
    err = _learn(_pending_motor, perceived)
    logger.info("audio_motor: heard own voice — model error=%.4f (update %d)",
                err, _model_updates)
    _pending_motor = None
    _echo_frames = []


async def on_arousal_state(event: ArousalStateEvent) -> None:
    global _current_mode
    _current_mode = event.mode


async def on_tick(event: clock.TickEvent) -> None:
    """Spontaneous babbling: explore the motor space while awake.

    Random exploration is the mechanism by which the forward model gets its
    training data. It is deliberately sparse — a caregiver has to be able to
    stand being in the room.
    """
    global _tick_count
    _tick_count += 1

    if not _enabled or _pending_motor is not None:
        return
    if _current_mode not in (ArousalMode.WAKEFUL, ArousalMode.FOCUSED):
        return
    if _tick_count - _last_utterance < MIN_INTERVAL_TICKS:
        return

    await vocalise([random.random() for _ in range(MOTOR_DIM)], kind="babble")


# ── control and persistence ────────────────────────────────────────────────────

def enable(on: bool = True) -> None:
    global _enabled
    _enabled = bool(on)
    state_store.set("audio_motor.enabled", _enabled)
    logger.info("audio_motor: vocalisation %s", "ENABLED" if _enabled else "disabled")


def save_state() -> None:
    try:
        state_store.set("audio_motor.M", _M)
        state_store.set("audio_motor.c", _c)
        state_store.set("audio_motor.model_updates", _model_updates)
    except Exception as e:
        logger.warning("audio_motor: save failed (%s)", e)


def load_state() -> bool:
    global _M, _c, _model_updates
    M = state_store.get("audio_motor.M", None)
    if not M or len(M) != FEATURE_DIM:
        return False
    try:
        _M = [[float(v) for v in row] for row in M]
        _c = [float(v) for v in state_store.get("audio_motor.c", [0.0] * FEATURE_DIM)]
        _model_updates = int(state_store.get("audio_motor.model_updates", 0))
        return True
    except Exception as e:
        logger.warning("audio_motor: load failed (%s)", e)
        return False


def init() -> None:
    global _enabled
    bus.subscribe(AudioEnergyEvent, on_audio_energy)
    bus.subscribe(ArousalStateEvent, on_arousal_state)
    bus.subscribe(clock.TickEvent, on_tick)

    _enabled = bool(state_store.get("audio_motor.enabled", False))
    restored = load_state()
    logger.info(
        "audio_motor initialized — vocalisation %s  forward model %s",
        "enabled" if _enabled else "DISABLED (call enable() to switch on)",
        f"resumed after {_model_updates} updates" if restored else "unlearned",
    )
