"""
Shared event type definitions.

Thin module with no dependencies beyond bus, so any module can import from
here without creating circular dependencies.
"""

from dataclasses import dataclass
from enum import Enum

import bus


class ArousalMode(str, Enum):
    DEEP_SLEEP  = "DEEP_SLEEP"
    LIGHT_SLEEP = "LIGHT_SLEEP"
    WAKEFUL     = "WAKEFUL"
    FOCUSED     = "FOCUSED"
    RECOVERY    = "RECOVERY"


@dataclass
class ArousalStateEvent(bus.Event):
    mode:           ArousalMode
    arousal_level:  float
    sleep_pressure: float
    fatigue_level:  float
    suppression:    float


@dataclass
class SleepModeChangeEvent(bus.Event):
    previous_mode: ArousalMode
    new_mode:      ArousalMode
    reason:        str


class SoundCategory(str, Enum):
    SILENCE = "SILENCE"
    NOISE   = "NOISE"
    SPEECH  = "SPEECH"
    ALARM   = "ALARM"


class ArousalSignal(str, Enum):
    """
    Actionable wake signal derived from classification + confidence + pattern.
    Distinct from SoundCategory — a low-confidence ALARM classification
    produces LOUD_SOUND, not ALARM.
    """
    NONE       = "NONE"
    SPEECH     = "SPEECH"
    LOUD_SOUND = "LOUD_SOUND"   # high rms, low-confidence alarm
    ALARM      = "ALARM"        # high-confidence + pattern persistent


@dataclass
class OrientingResponseEvent(bus.Event):
    category:       SoundCategory
    confidence:     float
    arousal_delta:  float
    arousal_signal: ArousalSignal  # what arousal module should act on


@dataclass
class SleepRecommendationEvent(bus.Event):
    reason:                   str
    sustained_silence_chunks: int


@dataclass
class AudioEnergyEvent(bus.Event):
    rms:               float
    zcr:               float
    spectral_centroid: float
    spectral_flatness: float
    band_ratio:        float
    chunk_ms:          int


@dataclass
class PredictionErrorEvent(bus.Event):
    """Published by the predictor each time it processes a new observation."""
    error:          float   # raw mean-squared prediction error
    surprise:       float   # normalised [0,1] — how unexpected this was
    feature_errors: list    # per-feature errors [rms, zcr, centroid, flatness, band]


@dataclass
class LearningProgressEvent(bus.Event):
    """Periodic summary of how the predictor's model is improving."""
    mean_error:       float   # rolling mean prediction error
    error_trend:      float   # negative = improving, positive = getting worse
    model_age_chunks: int     # total chunks the model has trained on


# ── Stage 6: Value Signal (reinforcement) ───────────────────────────────────────

@dataclass
class RewardSignalEvent(bus.Event):
    """Positive reinforcement — something that mattered went well (GENOME L3)."""
    magnitude: float   # [0,1]
    drive:     str     # which drive the reward is attributed to
    reason:    str


@dataclass
class PenaltySignalEvent(bus.Event):
    """Negative reinforcement — an aversive consequence (GENOME L3)."""
    magnitude: float   # [0,1]
    drive:     str
    reason:    str


@dataclass
class DriveStateEvent(bus.Event):
    """Periodic broadcast of the six innate drives (GENOME D1-D6) plus the
    value system's current wake-threshold policy bias, which the arousal
    module reads to adapt behaviour."""
    continuity:          float
    stability:           float
    energy:              float
    curiosity:           float
    social:              float
    integrity:           float
    dominant_drive:      str
    net_value:           float
    wake_threshold_bias: float


@dataclass
class CaregiverFeedbackEvent(bus.Event):
    """Explicit caregiver reinforcement. Forward hook for the Stage 9
    communication loop / caregiver interface — no module publishes this yet.
    The value module already consumes it, so this becomes the strong social
    reinforcement channel the moment a caregiver module is added."""
    valence:   float   # [-1,1] — positive = approval, negative = disapproval
    kind:      str     # free-form marker, e.g. "approval" / "disapproval"
    intensity: float   # [0,1]
