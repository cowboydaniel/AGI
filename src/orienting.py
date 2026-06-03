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
from dataclasses import dataclass

import bus
import clock
import state_store
from events import (
    ArousalMode, ArousalStateEvent,
    AudioEnergyEvent, SoundCategory, ArousalSignal,
    OrientingResponseEvent, SleepRecommendationEvent,
)

logger = logging.getLogger(__name__)


# ── classification thresholds ──────────────────────────────────────────────────

# Silence
SILENCE_RMS_MAX          = 0.02

# Alarm: loud AND either tonal (low flatness) or very high centroid
ALARM_RMS_MIN            = 0.85
ALARM_FLATNESS_MAX       = 0.25   # tonal
ALARM_CENTROID_MIN       = 3000.0 # Hz — high-pitched alarm

# Speech heuristics (all must pass for SPEECH category)
SPEECH_RMS_MIN           = 0.03
SPEECH_RMS_MAX           = 0.60   # very loud is more likely alarm/noise
SPEECH_BAND_RATIO_MIN    = 0.55   # majority of energy in voice band
SPEECH_ZCR_MIN           = 0.04   # speech has moderate ZCR
SPEECH_ZCR_MAX           = 0.35
SPEECH_FLATNESS_MAX      = 0.65   # speech is semi-tonal

# Arousal deltas per category — base values for a 200ms chunk.
# Scaled by chunk_ms/200 so a 500ms deep-sleep chunk carries proportional weight.
AROUSAL_DELTA: dict[SoundCategory, float] = {
    SoundCategory.SILENCE: -0.02,
    SoundCategory.NOISE:    0.00,
    SoundCategory.SPEECH:  +0.08,
    SoundCategory.ALARM:   +0.25,
}

# ArousalSignal rules
ALARM_CONF_MIN           = 0.70   # below this → LOUD_SOUND, not ALARM
ALARM_PATTERN_MS         = 500    # alarm must persist this long to be confirmed
LOUD_SOUND_RMS_MIN       = 0.35   # rms above this triggers LOUD_SOUND even without alarm conf

# Sustained silence → recommend re-sleep
SILENCE_SLEEP_TICKS      = 30     # consecutive silent chunks


# ── state ──────────────────────────────────────────────────────────────────────

_current_mode:        ArousalMode   = ArousalMode.LIGHT_SLEEP
_silence_streak:      int           = 0
_alarm_pattern_ms:    float         = 0.0   # accumulated ms of alarm-like chunks
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


def _compute_arousal_signal(
    category: SoundCategory,
    confidence: float,
    rms: float,
    chunk_ms: int,
) -> ArousalSignal:
    """
    Derive the actionable wake signal from classification results.

    Rules (in priority order):
    1. ALARM requires conf >= ALARM_CONF_MIN AND alarm pattern has persisted
       for >= ALARM_PATTERN_MS — prevents a single misclassified chunk from
       triggering a confirmed alarm wake.
    2. High rms with low alarm confidence → LOUD_SOUND (honest about cause).
    3. SPEECH → SPEECH.
    4. Everything else → NONE.
    """
    global _alarm_pattern_ms

    alarm_like = (category == SoundCategory.ALARM)

    if alarm_like:
        _alarm_pattern_ms += chunk_ms
    else:
        _alarm_pattern_ms = max(0.0, _alarm_pattern_ms - chunk_ms * 0.5)

    if alarm_like and confidence >= ALARM_CONF_MIN and _alarm_pattern_ms >= ALARM_PATTERN_MS:
        return ArousalSignal.ALARM

    if rms >= LOUD_SOUND_RMS_MIN:
        return ArousalSignal.LOUD_SOUND

    if category == SoundCategory.SPEECH:
        return ArousalSignal.SPEECH

    return ArousalSignal.NONE


async def on_audio_energy(event: AudioEnergyEvent) -> None:
    global _silence_streak, _last_category, _chunks_classified
    _chunks_classified += 1

    category, confidence = _classify(event)
    _last_category = category
    signal = _compute_arousal_signal(category, confidence, event.rms, event.chunk_ms)

    if category == SoundCategory.SILENCE:
        _silence_streak += 1
    else:
        _silence_streak = 0

    # Scale delta by chunk duration so longer chunks carry proportional weight
    delta = AROUSAL_DELTA[category] * (event.chunk_ms / 200.0)

    logger.info(
        "orienting: %-7s  conf=%.2f  rms=%.3f  centroid=%.0fHz  band=%.2f  zcr=%.2f  signal=%s",
        category.value, confidence, event.rms, event.spectral_centroid,
        event.band_ratio, event.zcr, signal.value,
    )

    await bus.publish(
        OrientingResponseEvent(
            source="orienting",
            timestamp=clock.elapsed(),
            category=category,
            confidence=confidence,
            arousal_delta=delta,
            arousal_signal=signal,
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
