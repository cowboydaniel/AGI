"""
Orienting Reflex — Stage 4.

Rapid sound categorization from acoustic features. No ML — heuristics only.
Classifies each audio chunk into one of four categories and issues an
immediate arousal response.

Categories
----------
SILENCE   — RMS below noise floor; promote re-sleep if sustained
NOISE     — broadband energy, no rhythmic structure; ignore
SPEECH    — energy concentrated in voice band (300-3400 Hz), amplitude
             modulation at syllabic rate (2-8 Hz), ZCR in speech range
ALARM     — high energy spike or narrow-band sustained tone above speech

AudioEnergyEvent is defined here because this module owns the feature
contract that Stage 6 (mic input loop) must produce. Stage 6 extracts
the features from raw waveform and publishes; this module classifies.

Decision rules
--------------
SILENCE   → if sustained for SILENCE_SLEEP_TICKS consecutive chunks and
             arousal is wakeful, issue SleepRecommendationEvent
NOISE     → no action (ignore)
SPEECH    → boost arousal; publish OrientingResponseEvent(category=SPEECH)
ALARM     → strong arousal boost; publish OrientingResponseEvent(category=ALARM)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

import bus
import clock
import state_store
from arousal import ArousalMode, ArousalStateEvent

logger = logging.getLogger(__name__)


# ── shared event: produced by Stage 6, consumed here ──────────────────────────

@dataclass
class AudioEnergyEvent(bus.Event):
    """Acoustic features extracted from one audio chunk by the mic input loop."""
    rms:              float   # root-mean-square amplitude [0, 1]
    zcr:              float   # zero-crossing rate [0, 1] normalised to chunk length
    spectral_centroid: float  # Hz — centre of mass of the spectrum
    spectral_flatness: float  # [0, 1] — 0=tonal, 1=white noise
    band_ratio:       float   # energy in 300-3400 Hz / total energy
    chunk_ms:         int     # chunk duration in ms


# ── output events ──────────────────────────────────────────────────────────────

class SoundCategory(str, Enum):
    SILENCE = "SILENCE"
    NOISE   = "NOISE"
    SPEECH  = "SPEECH"
    ALARM   = "ALARM"


@dataclass
class OrientingResponseEvent(bus.Event):
    category:      SoundCategory
    confidence:    float          # [0, 1] heuristic confidence
    arousal_delta: float          # suggested arousal change


@dataclass
class SleepRecommendationEvent(bus.Event):
    reason: str
    sustained_silence_chunks: int


# ── classification thresholds ──────────────────────────────────────────────────

# Silence
SILENCE_RMS_MAX          = 0.02

# Alarm: loud AND either tonal (low flatness) or very high centroid
ALARM_RMS_MIN            = 0.35
ALARM_FLATNESS_MAX       = 0.25   # tonal
ALARM_CENTROID_MIN       = 3000.0 # Hz — high-pitched alarm

# Speech heuristics (all must pass for SPEECH category)
SPEECH_RMS_MIN           = 0.03
SPEECH_RMS_MAX           = 0.60   # very loud is more likely alarm/noise
SPEECH_BAND_RATIO_MIN    = 0.55   # majority of energy in voice band
SPEECH_ZCR_MIN           = 0.04   # speech has moderate ZCR
SPEECH_ZCR_MAX           = 0.35
SPEECH_FLATNESS_MAX      = 0.65   # speech is semi-tonal

# Arousal deltas per category
AROUSAL_DELTA: dict[SoundCategory, float] = {
    SoundCategory.SILENCE: -0.02,
    SoundCategory.NOISE:    0.00,
    SoundCategory.SPEECH:  +0.08,
    SoundCategory.ALARM:   +0.20,
}

# Sustained silence → recommend re-sleep
SILENCE_SLEEP_TICKS      = 30     # consecutive silent chunks


# ── state ──────────────────────────────────────────────────────────────────────

_current_mode:        ArousalMode = ArousalMode.LIGHT_SLEEP
_silence_streak:      int         = 0
_last_category:       SoundCategory = SoundCategory.SILENCE
_chunks_classified:   int         = 0


def _classify(ev: AudioEnergyEvent) -> tuple[SoundCategory, float]:
    """Return (category, confidence) from audio features."""

    # Silence check first — cheapest
    if ev.rms < SILENCE_RMS_MAX:
        return SoundCategory.SILENCE, 1.0 - (ev.rms / SILENCE_RMS_MAX)

    # Alarm: high amplitude with tonal character or high centroid
    if ev.rms >= ALARM_RMS_MIN:
        tonal_alarm    = ev.spectral_flatness <= ALARM_FLATNESS_MAX
        highpitch_alarm = ev.spectral_centroid >= ALARM_CENTROID_MIN
        if tonal_alarm or highpitch_alarm:
            conf = min(1.0, ev.rms / 0.8) * (0.6 + 0.4 * (1.0 - ev.spectral_flatness))
            return SoundCategory.ALARM, conf

    # Speech: energy in voice band, moderate ZCR, semi-tonal
    speech_score = 0.0
    checks = [
        ev.rms              >= SPEECH_RMS_MIN,
        ev.rms              <= SPEECH_RMS_MAX,
        ev.band_ratio       >= SPEECH_BAND_RATIO_MIN,
        ev.zcr              >= SPEECH_ZCR_MIN,
        ev.zcr              <= SPEECH_ZCR_MAX,
        ev.spectral_flatness <= SPEECH_FLATNESS_MAX,
    ]
    speech_score = sum(checks) / len(checks)
    if speech_score >= 0.67:   # at least 4/6 criteria
        return SoundCategory.SPEECH, speech_score

    # Default: broadband noise, no action warranted
    noise_conf = min(1.0, ev.spectral_flatness + 0.2)
    return SoundCategory.NOISE, noise_conf


async def on_audio_energy(event: AudioEnergyEvent) -> None:
    global _silence_streak, _last_category, _chunks_classified
    _chunks_classified += 1

    category, confidence = _classify(event)
    _last_category = category

    if category == SoundCategory.SILENCE:
        _silence_streak += 1
    else:
        _silence_streak = 0

    delta = AROUSAL_DELTA[category]

    if category in (SoundCategory.SPEECH, SoundCategory.ALARM):
        logger.info(
            "orienting: %-7s  conf=%.2f  rms=%.3f  centroid=%.0fHz  band=%.2f",
            category.value, confidence, event.rms, event.spectral_centroid, event.band_ratio,
        )

    await bus.publish(
        OrientingResponseEvent(
            source="orienting",
            timestamp=clock.elapsed(),
            category=category,
            confidence=confidence,
            arousal_delta=delta,
        )
    )

    # Recommend re-sleep after sustained silence while awake
    awake = _current_mode in (ArousalMode.WAKEFUL, ArousalMode.FOCUSED)
    if awake and _silence_streak >= SILENCE_SLEEP_TICKS:
        logger.info(
            "orienting: sustained silence (%d chunks) — recommending re-sleep",
            _silence_streak,
        )
        await bus.publish(
            SleepRecommendationEvent(
                source="orienting",
                timestamp=clock.elapsed(),
                reason="sustained_silence",
                sustained_silence_chunks=_silence_streak,
            )
        )
        _silence_streak = 0   # reset so we don't spam recommendations


async def on_arousal_state(event: ArousalStateEvent) -> None:
    global _current_mode
    _current_mode = event.mode


def init() -> None:
    bus.subscribe(AudioEnergyEvent, on_audio_energy)
    bus.subscribe(ArousalStateEvent, on_arousal_state)
    logger.info("orienting reflex initialized")
