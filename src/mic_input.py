"""
Microphone Input Loop — Stage 6.

Reads raw audio from the system microphone via sounddevice, extracts the
five acoustic features AudioEnergyEvent requires, and publishes to the bus.

Only runs when the sensory gate has microphone enabled (i.e. arousal is at
least LIGHT_SLEEP with mic on, or WAKEFUL/FOCUSED). The gate publishes
SensoryGateControlEvent whenever mic state changes; this module starts and
stops its capture stream in response.

Feature extraction (no ML, pure signal processing):
  rms               — sqrt(mean(x^2))
  zcr               — zero-crossing rate, normalised to [0,1]
  spectral_centroid — energy-weighted mean frequency (Hz)
  spectral_flatness — geometric_mean(|X|) / arithmetic_mean(|X|)  (Wiener entropy)
  band_ratio        — energy in 300–3400 Hz / total energy

All extraction runs in a threadpool so the asyncio loop is never blocked by
numpy/FFT work.
"""

import asyncio
import logging
import math
from concurrent.futures import ThreadPoolExecutor

import bus
import clock
import state_store
from orienting import AudioEnergyEvent
from sensory_gate import SensoryGateControlEvent

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000   # Hz — matches torchaudio default for later stages

_executor   = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mic")
_stream     = None          # sounddevice.InputStream
_mic_active = False
_loop: asyncio.AbstractEventLoop | None = None


# ── feature extraction ─────────────────────────────────────────────────────────

def _extract_features(samples, chunk_ms: int) -> AudioEnergyEvent | None:
    """Pure numpy signal processing — runs in threadpool."""
    try:
        import numpy as np

        x = samples.flatten().astype(np.float32)
        if len(x) == 0:
            return None

        # RMS
        rms = float(np.sqrt(np.mean(x ** 2)))

        # Zero-crossing rate (normalised)
        signs  = np.sign(x)
        signs[signs == 0] = 1
        zcr = float(np.mean(np.abs(np.diff(signs)) > 0))

        # FFT magnitude spectrum
        window = np.hanning(len(x))
        X      = np.abs(np.fft.rfft(x * window))
        freqs  = np.fft.rfftfreq(len(x), d=1.0 / SAMPLE_RATE)
        eps    = 1e-10

        # Spectral centroid
        X_sum = np.sum(X) + eps
        spectral_centroid = float(np.sum(freqs * X) / X_sum)

        # Spectral flatness (Wiener entropy)
        log_mean = np.mean(np.log(X + eps))
        arith    = np.mean(X) + eps
        spectral_flatness = float(np.clip(np.exp(log_mean) / arith, 0.0, 1.0))

        # Band ratio: energy in 300–3400 Hz vs total
        band_mask  = (freqs >= 300) & (freqs <= 3400)
        band_ratio = float(np.sum(X[band_mask]) / X_sum)

        return AudioEnergyEvent(
            source="mic_input",
            timestamp=clock.elapsed(),
            rms=rms,
            zcr=zcr,
            spectral_centroid=spectral_centroid,
            spectral_flatness=spectral_flatness,
            band_ratio=band_ratio,
            chunk_ms=chunk_ms,
        )
    except Exception as e:
        logger.warning("mic_input: feature extraction failed (%s)", e)
        return None


# ── sounddevice stream ─────────────────────────────────────────────────────────

def _open_stream(chunk_ms: int) -> bool:
    global _stream
    try:
        import sounddevice as sd

        blocksize = int(SAMPLE_RATE * chunk_ms / 1000)

        def _callback(indata, frames, time_info, status):
            if status:
                logger.debug("mic_input: sd status %s", status)
            if _loop is None or _loop.is_closed():
                return
            # Copy so sounddevice can reuse the buffer
            samples = indata.copy()
            asyncio.run_coroutine_threadsafe(_on_audio(samples, chunk_ms), _loop)

        _stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
            callback=_callback,
        )
        _stream.start()
        logger.info("mic_input: stream opened  %d Hz  %d ms chunks", SAMPLE_RATE, chunk_ms)
        return True
    except Exception as e:
        logger.error("mic_input: failed to open stream (%s)", e)
        return False


def _close_stream() -> None:
    global _stream
    if _stream is not None:
        try:
            _stream.stop()
            _stream.close()
            logger.info("mic_input: stream closed")
        except Exception as e:
            logger.warning("mic_input: error closing stream (%s)", e)
        _stream = None


# ── async handlers ─────────────────────────────────────────────────────────────

async def _on_audio(samples, chunk_ms: int) -> None:
    """Called from the sd callback via run_coroutine_threadsafe."""
    loop = asyncio.get_running_loop()
    event = await loop.run_in_executor(_executor, _extract_features, samples, chunk_ms)
    if event is not None:
        await bus.publish(event)


async def on_gate_control(event: SensoryGateControlEvent) -> None:
    global _mic_active
    should_be_active = event.microphone_enabled and event.audio_chunk_ms > 0

    if should_be_active and not _mic_active:
        ok = _open_stream(event.audio_chunk_ms)
        _mic_active = ok
        state_store.set("mic_input.active", _mic_active)

    elif not should_be_active and _mic_active:
        _close_stream()
        _mic_active = False
        state_store.set("mic_input.active", False)


def init() -> None:
    global _loop
    _loop = asyncio.get_event_loop()
    bus.subscribe(SensoryGateControlEvent, on_gate_control)
    logger.info("mic_input initialized (waiting for gate open)")
