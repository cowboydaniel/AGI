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
from events import AudioEnergyEvent
from sensory_gate import SensoryGateControlEvent

logger = logging.getLogger(__name__)

# Probed at init — set to the first device with actual signal, falling back
# to the sounddevice default. Override via state_store key "mic_input.device_index".
SAMPLE_RATE    = 16000   # Hz target; resampled from device native rate if needed
_device_index: int | None = None   # None = sounddevice default
_device_rate:  int        = 16000  # actual hardware rate (may differ from SAMPLE_RATE)

_executor   = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mic")
_stream     = None          # sounddevice.InputStream
_mic_active = False


# ── device probe ──────────────────────────────────────────────────────────────

def _probe_best_device() -> tuple[int | None, int]:
    """
    Return (device_index, sample_rate) for the first input device that
    produces a non-zero signal. Falls back to (None, 44100) if none found.
    Records a short burst synchronously — called once at init.
    """
    try:
        import numpy as np
        import sounddevice as sd

        # Allow manual override via persisted state
        override = state_store.get("mic_input.device_index", None)
        if override is not None:
            rate = int(sd.query_devices(override)["default_samplerate"])
            logger.info("mic_input: using overridden device [%d] at %d Hz", override, rate)
            return int(override), rate

        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d["max_input_channels"] == 0:
                continue
            rate = int(d["default_samplerate"])
            try:
                frames = sd.rec(int(rate * 0.3), samplerate=rate, channels=1,
                                dtype="float32", device=i, blocking=True)
                rms = float(np.sqrt(np.mean(frames ** 2)))
                if rms > 0.0001:
                    logger.info(
                        "mic_input: selected device [%d] %r  rate=%d  probe_rms=%.4f",
                        i, d["name"], rate, rms,
                    )
                    state_store.set("mic_input.device_index", i)
                    return i, rate
            except Exception:
                continue

        logger.warning("mic_input: no live input device found — using system default")
        default_idx = sd.default.device[0]
        rate = int(sd.query_devices(default_idx)["default_samplerate"])
        return None, rate

    except Exception as e:
        logger.warning("mic_input: device probe failed (%s)", e)
        return None, 44100


# ── noise floor calibration ────────────────────────────────────────────────────

_noise_floor_rms: float = 0.0


def _calibrate_noise_floor(device_index: int | None, rate: int) -> float:
    """
    Record ~1.5 seconds of silence and measure the RMS noise floor.
    Updates orienting thresholds so they are relative to this mic's baseline.
    Called once at init, after device selection.
    """
    try:
        import numpy as np
        import sounddevice as sd
        from orienting import (
            SILENCE_RMS_MAX, SPEECH_RMS_MIN, SPEECH_RMS_MAX,
            ALARM_RMS_MIN,
        )
        import orienting

        frames = sd.rec(int(rate * 1.5), samplerate=rate, channels=1,
                        dtype="float32", device=device_index, blocking=True)
        floor = float(np.sqrt(np.mean(frames ** 2)))
        floor = max(floor, 0.001)   # never zero

        # Set thresholds relative to the measured floor
        orienting.SILENCE_RMS_MAX  = floor * 1.5
        orienting.SPEECH_RMS_MIN   = floor * 3.0
        orienting.SPEECH_RMS_MAX   = floor * 25.0
        orienting.ALARM_RMS_MIN    = floor * 15.0

        state_store.set("mic_input.noise_floor", floor)
        logger.info(
            "mic_input: noise floor=%.4f  thresholds → silence<%.4f  speech=%.4f–%.4f  alarm>%.4f",
            floor,
            orienting.SILENCE_RMS_MAX,
            orienting.SPEECH_RMS_MIN,
            orienting.SPEECH_RMS_MAX,
            orienting.ALARM_RMS_MIN,
        )
        return floor

    except Exception as e:
        logger.warning("mic_input: noise floor calibration failed (%s)", e)
        return 0.02


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

        # FFT magnitude spectrum — use actual device rate for correct Hz axis
        window = np.hanning(len(x))
        X      = np.abs(np.fft.rfft(x * window))
        freqs  = np.fft.rfftfreq(len(x), d=1.0 / _device_rate)
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

def _open_stream(chunk_ms: int, loop: asyncio.AbstractEventLoop) -> bool:
    global _stream
    try:
        import sounddevice as sd

        blocksize = int(_device_rate * chunk_ms / 1000)

        def _callback(indata, frames, time_info, status):
            if status:
                logger.debug("mic_input: sd status %s", status)
            if loop.is_closed():
                return
            samples = indata.copy()
            asyncio.run_coroutine_threadsafe(_on_audio(samples, chunk_ms), loop)

        _stream = sd.InputStream(
            samplerate=_device_rate,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
            device=_device_index,
            callback=_callback,
        )
        _stream.start()
        logger.info(
            "mic_input: stream opened  device=%s  %d Hz  %d ms chunks",
            _device_index, _device_rate, chunk_ms,
        )
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
        # Capture the running loop here — this handler runs inside asyncio.run()
        # so get_running_loop() returns the correct live loop for the sd callback.
        loop = asyncio.get_running_loop()
        ok = _open_stream(event.audio_chunk_ms, loop)
        _mic_active = ok
        state_store.set("mic_input.active", _mic_active)

    elif not should_be_active and _mic_active:
        _close_stream()
        _mic_active = False
        state_store.set("mic_input.active", False)


def init() -> None:
    global _device_index, _device_rate, _noise_floor_rms
    _device_index, _device_rate = _probe_best_device()
    if _device_index is not None or _device_rate > 0:
        _noise_floor_rms = _calibrate_noise_floor(_device_index, _device_rate)
    bus.subscribe(SensoryGateControlEvent, on_gate_control)
    logger.info("mic_input initialized (waiting for gate open)")
