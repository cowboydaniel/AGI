"""
Salience Detection — GENOME.md P1 (Sensory Priors, "Newborn Biases").

A baby in a noisy room does not attend to the noise. It ignores a fan, hiss,
traffic and soft wind however loud they are, and turns its head for a voice.
That is not a learned skill and it is not a loudness threshold — it is innate
perceptual machinery present at birth.

This module is that machinery. It answers one question per chunk: *is this
worth attending to?* Nothing here knows what any sound means; it only knows
the difference between structure and noise.

Three innate detectors, combined
--------------------------------

1. ONSET (P1: "abrupt changes in volume/energy")
   Salience comes from *change*, not level. A step up in energy relative to
   the recent background is salient; a constant drone, at any volume, is not.
   This is why a fan running all day stops being interesting while a door
   closing does not.

2. PERIODICITY (the voice/noise distinction)
   A vibrating source — vocal folds, a string, a motor — produces energy that
   repeats. Static, hiss and wind are aperiodic: their autocorrelation is
   flat. This single measure separates "something made a sound" from "the room
   is noisy", and it is the reason soft static never wakes the system while a
   quiet word does.

3. SPEECH RHYTHM (P1: "caregiver-like speech rhythm — prosody and cadence,
   not vocabulary")
   Speech is amplitude-modulated at the syllable rate, roughly 2-8 Hz. Steady
   noise has no such modulation, and neither does a pure sustained tone. This
   detector measures modulation depth in that band. It responds to cadence
   only: it cannot tell one word from another and knows no vocabulary.

The three are combined into a salience score. Attention requires structure
(periodicity or rhythm), not merely energy — so loudness alone can never make
something salient, which is exactly the behaviour a fixed threshold got wrong.

Anti-hardcoding note: these are priors that make learning tractable, which
GENOME.md axiom 5 explicitly permits as "learnability infrastructure". No
detector here encodes what a sound is, which words exist, or what to do about
any of them.
"""

import logging
import math
from collections import deque
from dataclasses import dataclass

import bus
import state_store
from events import AudioEnergyEvent

logger = logging.getLogger(__name__)

# ── tuning (innate sensitivities, not knowledge) ───────────────────────────────

HISTORY = 60                 # chunks of energy history (~12 s at 200 ms)

# Onset: how far above the recent background an energy step must rise.
ONSET_RATIO = 2.5            # multiple of background energy
ONSET_ABS   = 0.004          # absolute floor so near-silence cannot "onset"

# Periodicity: below this a sound is treated as noise, however loud.
PERIODIC_MIN = 0.30
PERIODIC_STRONG = 0.55

# Speech rhythm: syllable-rate amplitude modulation.
RHYTHM_BAND_LO = 2.0         # Hz
RHYTHM_BAND_HI = 8.0         # Hz
RHYTHM_MIN_DEPTH = 0.25      # modulation depth counted as speech-like cadence

# Absolute threshold of hearing. Below this a chunk is silence as far as the
# system is concerned, whatever its measured periodicity: near-zero digital
# noise has arbitrary autocorrelation, and without this floor an empty room
# reads as full of structured sound.
AUDIBLE_MIN_RMS = 0.004

# Attention requires structure, not just energy.
SALIENT_SCORE = 0.40

# Weights of the three detectors in the combined score.
W_ONSET   = 0.30
W_PERIOD  = 0.45
W_RHYTHM  = 0.25


# ── events ─────────────────────────────────────────────────────────────────────

@dataclass
class SalienceEvent(bus.Event):
    """Per-chunk judgement of whether this is worth attending to."""
    salient:     bool
    score:       float
    onset:       float      # 0..1 how abrupt the energy change was
    periodicity: float      # 0..1 how strongly the sound repeats
    rhythm:      float      # 0..1 syllable-rate modulation depth
    background:  float      # current ambient energy estimate
    reason:      str


# ── state ──────────────────────────────────────────────────────────────────────

_energy: deque = deque(maxlen=HISTORY)     # recent rms values
_chunk_ms: int = 200
_salient_count: int = 0
_total_count: int = 0


# ── detectors ──────────────────────────────────────────────────────────────────

def background() -> float:
    """Ambient energy: a low percentile of recent history.

    A percentile, not a mean, so a burst of speech inside the window cannot
    drag the estimate up and deafen the system to the next word.
    """
    if len(_energy) < 8:
        return 0.0
    ordered = sorted(_energy)
    return ordered[int(len(ordered) * 0.25)]


def onset_strength(rms: float) -> float:
    """How abruptly energy rose above the recent background (P1)."""
    bg = background()
    if rms < ONSET_ABS:
        return 0.0
    if bg <= 1e-9:
        return 1.0 if rms > ONSET_ABS else 0.0
    ratio = rms / (bg + 1e-9)
    if ratio <= 1.0:
        return 0.0
    # Log-scaled so a 2.5x step already counts, and huge steps saturate.
    return max(0.0, min(1.0, math.log(ratio) / math.log(ONSET_RATIO * 4.0)))


def rhythm_depth() -> float:
    """Modulation depth in the 2-8 Hz syllable band (P1: prosody and cadence).

    Speech pulses at syllable rate; steady noise and sustained tones do not.
    Computed as the normalised energy of the envelope's fluctuation within the
    band, using a coarse DFT over the recent energy history.
    """
    if len(_energy) < 16:
        return 0.0
    env = list(_energy)
    n = len(env)
    mean = sum(env) / n
    if mean <= 1e-9:
        return 0.0
    centred = [v - mean for v in env]

    fs = 1000.0 / max(1, _chunk_ms)          # envelope sample rate (Hz)
    if fs <= 2 * RHYTHM_BAND_LO:
        return 0.0

    band = 0.0
    total = 1e-12
    # Coarse DFT: only the handful of bins we care about.
    for k in range(1, n // 2):
        f = k * fs / n
        re = sum(centred[t] * math.cos(2 * math.pi * k * t / n) for t in range(n))
        im = sum(centred[t] * math.sin(2 * math.pi * k * t / n) for t in range(n))
        mag = math.sqrt(re * re + im * im)
        total += mag
        if RHYTHM_BAND_LO <= f <= RHYTHM_BAND_HI:
            band += mag
    return max(0.0, min(1.0, (band / total) * (1.0 + mean / (mean + 1e-9)) / 2.0))


def evaluate(event: AudioEnergyEvent) -> tuple:
    """Score one chunk. Returns (salient, score, onset, periodicity, rhythm, reason)."""
    if event.rms < AUDIBLE_MIN_RMS:
        # Below the absolute threshold of hearing: silence, regardless of what
        # the periodicity of near-zero noise happens to measure.
        return False, 0.0, 0.0, 0.0, 0.0, "inaudible"

    onset = onset_strength(event.rms)
    periodic = max(0.0, min(1.0, event.periodicity))
    rhythm = rhythm_depth()

    score = W_ONSET * onset + W_PERIOD * periodic + W_RHYTHM * rhythm

    # Structure gate: energy alone is never enough. A loud aperiodic drone with
    # no rhythm is exactly what a baby ignores, so it must not pass here.
    has_structure = periodic >= PERIODIC_MIN or rhythm >= RHYTHM_MIN_DEPTH
    salient = bool(score >= SALIENT_SCORE and has_structure)

    if not has_structure:
        reason = "unstructured (noise-like)"
    elif periodic >= PERIODIC_STRONG:
        reason = "periodic source"
    elif rhythm >= RHYTHM_MIN_DEPTH:
        reason = "speech-like rhythm"
    elif onset > 0.5:
        reason = "abrupt onset"
    else:
        reason = "weak"

    return salient, score, onset, periodic, rhythm, reason


# ── observation ────────────────────────────────────────────────────────────────

_last_key: object = None
_last_verdict: tuple = (False, 0.0, 0.0, 0.0, 0.0, "no observation")


def observe(event: AudioEnergyEvent) -> tuple:
    """Judge a chunk and fold it into the history. Idempotent per chunk.

    Both the bus handler and any module that needs the verdict synchronously
    (memory, for episode gating) call this. Repeat calls for the same chunk
    return the cached verdict instead of appending the chunk twice, so the
    background estimate cannot drift with the number of consumers and the
    result cannot depend on bus dispatch order.
    """
    global _chunk_ms, _salient_count, _total_count, _last_key, _last_verdict

    key = (id(event), event.timestamp, event.rms)
    if key == _last_key:
        return _last_verdict

    _chunk_ms = event.chunk_ms or _chunk_ms
    verdict = evaluate(event)

    # History is appended after evaluation so a chunk is judged against the
    # background *before* it, not including itself.
    _energy.append(event.rms)
    _total_count += 1
    if verdict[0]:
        _salient_count += 1

    _last_key, _last_verdict = key, verdict
    return verdict


# ── handler ────────────────────────────────────────────────────────────────────

async def on_audio_energy(event: AudioEnergyEvent) -> None:
    salient, score, onset, periodic, rhythm, reason = observe(event)

    await bus.publish(SalienceEvent(
        source="salience", timestamp=event.timestamp,
        salient=salient, score=score, onset=onset, periodicity=periodic,
        rhythm=rhythm, background=background(), reason=reason,
    ))


def stats() -> dict:
    return {
        "chunks": _total_count,
        "salient": _salient_count,
        "ratio": _salient_count / _total_count if _total_count else 0.0,
        "background": background(),
    }


def init() -> None:
    bus.subscribe(AudioEnergyEvent, on_audio_energy)
    _energy.clear()
    logger.info(
        "salience (GENOME P1) initialized — attention needs structure: "
        "periodicity>=%.2f or rhythm>=%.2f, score>=%.2f",
        PERIODIC_MIN, RHYTHM_MIN_DEPTH, SALIENT_SCORE,
    )
