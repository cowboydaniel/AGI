"""
Continuous Predictive Loop — Stage 7.

Maintains an online predictive model of the sensory environment. On every
AudioEnergyEvent the predictor:

  1. Encodes the 5 acoustic features into a normalised feature vector.
  2. Computes prediction error: how wrong the previous prediction was.
  3. Updates the model via a gradient step (online linear regression).
  4. Makes a new prediction for the next observation.
  5. Publishes PredictionErrorEvent so arousal can modulate thresholds.

Model architecture
------------------
A single-layer linear predictor: x̂[t+1] = W·x[t] + b
Updated with stochastic gradient descent (no batches, no replay yet).
Input/output dimension = 5 (the AudioEnergyEvent feature vector).

This is the simplest possible instantiation of JEPA-style prediction —
predict the next latent state from the current one, learn from the error.
Stage 8 will add episodic memory; Stage 9 will upgrade the model.

Rhythm model
------------
Separately tracks the categorical sequence (SILENCE/NOISE/SPEECH) and
predicts the next category from a transition probability table updated
online. Rhythm prediction error adds to the overall surprise signal.

Threshold modulation
--------------------
High surprise (normalised error > SURPRISE_WAKE_BOOST_THRESHOLD) lowers
the effective arousal wake threshold, making the system easier to rouse.
Low sustained error (familiar environment) slightly raises the threshold.
The modulation is published as part of PredictionErrorEvent and read by
the arousal module.

No idle state from this stage onward — the predictor runs on every
AudioEnergyEvent regardless of arousal mode.
"""

import logging
import math
from dataclasses import dataclass, field
from collections import deque

import bus
import clock
import state_store
from events import (
    AudioEnergyEvent, PredictionErrorEvent, LearningProgressEvent,
    ArousalStateEvent, ArousalMode, SoundCategory,
)

logger = logging.getLogger(__name__)

# ── hyperparameters ────────────────────────────────────────────────────────────

FEATURE_DIM        = 5       # [rms, zcr, centroid_norm, flatness, band_ratio]
LEARNING_RATE      = 0.05    # SGD step size
EWA_ALPHA          = 0.1     # exponential weighting for error statistics

# Normalisation constants for spectral_centroid (Hz → [0,1])
CENTROID_MAX       = 16000.0

# Surprise modulation
SURPRISE_HIGH      = 0.6     # above this → lower wake threshold
SURPRISE_LOW       = 0.1     # below this (sustained) → raise wake threshold
SURPRISE_EFFECT    = 0.08    # max threshold shift per event

# Rhythm model
N_CATEGORIES       = 3       # SILENCE, NOISE, SPEECH
RHYTHM_WEIGHT      = 0.3     # weight of rhythm error in combined surprise

# Progress reporting cadence
PROGRESS_EVERY     = 100     # chunks

# ── model state ───────────────────────────────────────────────────────────────

# Linear predictor weights: W[5×5], b[5]
_W: list[list[float]] = [[1.0 if i == j else 0.0 for j in range(FEATURE_DIM)]
                          for i in range(FEATURE_DIM)]  # identity init
_b: list[float] = [0.0] * FEATURE_DIM

_prev_features: list[float] | None = None
_prev_prediction: list[float] | None = None

# Error statistics
_ewa_error:        float = 0.0
_error_history:    deque = deque(maxlen=200)
_chunks_trained:   int   = 0

# Rhythm model: transition counts [from_cat][to_cat]
_rhythm_counts: list[list[float]] = [[1.0] * N_CATEGORIES for _ in range(N_CATEGORIES)]
_prev_cat_idx:  int | None = None

# Current arousal mode (for logging context)
_current_mode: ArousalMode = ArousalMode.LIGHT_SLEEP


# ── feature encoding ───────────────────────────────────────────────────────────

def _encode(event: AudioEnergyEvent) -> list[float]:
    return [
        event.rms,
        event.zcr,
        min(event.spectral_centroid / CENTROID_MAX, 1.0),
        event.spectral_flatness,
        event.band_ratio,
    ]


def _cat_index(category) -> int:
    if category == SoundCategory.SPEECH:  return 2
    if category == SoundCategory.NOISE:   return 1
    return 0  # SILENCE and others


# ── linear predictor ──────────────────────────────────────────────────────────

def _predict(x: list[float]) -> list[float]:
    """x̂ = W·x + b"""
    result = []
    for i in range(FEATURE_DIM):
        val = _b[i]
        for j in range(FEATURE_DIM):
            val += _W[i][j] * x[j]
        result.append(max(0.0, min(1.0, val)))
    return result


def _update(x: list[float], target: list[float]) -> list[float]:
    """
    One SGD step: minimise MSE between prediction and target.
    Returns the per-feature errors before the update.
    """
    pred   = _predict(x)
    errors = [target[i] - pred[i] for i in range(FEATURE_DIM)]

    for i in range(FEATURE_DIM):
        _b[i] += LEARNING_RATE * errors[i]
        for j in range(FEATURE_DIM):
            _W[i][j] += LEARNING_RATE * errors[i] * x[j]

    return [abs(e) for e in errors]


# ── rhythm model ───────────────────────────────────────────────────────────────

def _rhythm_surprise(cat_idx: int) -> float:
    """
    How surprising is this category given the previous one?
    Returns 0.0 (expected) → 1.0 (completely unexpected).
    """
    if _prev_cat_idx is None:
        return 0.0
    row   = _rhythm_counts[_prev_cat_idx]
    total = sum(row) + 1e-10
    probs = [c / total for c in row]
    _rhythm_counts[_prev_cat_idx][cat_idx] += 1.0
    p = probs[cat_idx]
    # Shannon surprise: -log2(p), normalised to [0,1] over log2(N)
    return min(1.0, -math.log2(max(p, 1e-6)) / math.log2(N_CATEGORIES + 1))


# ── main handler ──────────────────────────────────────────────────────────────

async def on_audio_energy(event: AudioEnergyEvent) -> None:
    global _prev_features, _prev_prediction, _ewa_error
    global _chunks_trained, _prev_cat_idx

    features = _encode(event)

    # Determine category from rms/features for rhythm model
    import orienting as _ori
    if event.rms < _ori.SILENCE_RMS_MAX:
        cat_idx = 0
    elif event.rms < _ori.SPEECH_RMS_MIN:
        cat_idx = 1
    else:
        cat_idx = 2

    # Compute prediction error against the previous prediction
    feature_errors = [0.0] * FEATURE_DIM
    pred_error     = 0.0

    if _prev_features is not None:
        feature_errors = _update(_prev_features, features)
        pred_error     = math.sqrt(sum(e**2 for e in feature_errors) / FEATURE_DIM)

    r_surprise = _rhythm_surprise(cat_idx)
    _prev_cat_idx = cat_idx

    # Combined normalised surprise
    surprise = min(1.0, pred_error * (1.0 - RHYTHM_WEIGHT) + r_surprise * RHYTHM_WEIGHT)

    # Update error statistics
    _ewa_error = EWA_ALPHA * pred_error + (1.0 - EWA_ALPHA) * _ewa_error
    _error_history.append(pred_error)
    _chunks_trained += 1

    # Make next prediction
    _prev_features = features
    _prev_prediction = _predict(features)

    await bus.publish(
        PredictionErrorEvent(
            source="predictor",
            timestamp=clock.elapsed(),
            error=pred_error,
            surprise=surprise,
            feature_errors=feature_errors,
        )
    )

    # Periodic learning progress report
    if _chunks_trained % PROGRESS_EVERY == 0:
        hist = list(_error_history)
        half = len(hist) // 2
        if half > 0:
            trend = (sum(hist[half:]) / len(hist[half:])) - (sum(hist[:half]) / half)
        else:
            trend = 0.0
        logger.info(
            "predictor: chunks=%d  ewa_error=%.4f  trend=%+.4f  surprise=%.3f",
            _chunks_trained, _ewa_error, trend, surprise,
        )
        await bus.publish(
            LearningProgressEvent(
                source="predictor",
                timestamp=clock.elapsed(),
                mean_error=_ewa_error,
                error_trend=trend,
                model_age_chunks=_chunks_trained,
            )
        )


async def on_arousal_state(event: ArousalStateEvent) -> None:
    global _current_mode
    _current_mode = event.mode


def init() -> None:
    bus.subscribe(AudioEnergyEvent, on_audio_energy)
    bus.subscribe(ArousalStateEvent, on_arousal_state)
    logger.info("predictor initialized — online linear predictor  dim=%d  lr=%.3f",
                FEATURE_DIM, LEARNING_RATE)
