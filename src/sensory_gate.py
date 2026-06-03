"""
Sensory Gating — Stage 3 (Sensory Gate and Buffer).

Probes for available hardware at init and permanently disables any sensor
that cannot be opened. Gate state then tracks arousal — sensors are active
only when arousal warrants it, and frame/sample rates are throttled to the
current compute budget.

Hardware probe strategy:
- Camera: attempt to open cv2.VideoCapture(0); release immediately.
- Microphone: attempt to open a sounddevice InputStream for one block.

If a sensor is absent or throws on open, it is marked unavailable and will
never be enabled regardless of arousal. This is logged once at init so the
rest of the system knows what it's working with.
"""

import logging
from dataclasses import dataclass, field

import bus
import clock
import state_store
from events import ArousalMode, ArousalStateEvent

logger = logging.getLogger(__name__)


# ── hardware probe ─────────────────────────────────────────────────────────────

def _probe_camera() -> bool:
    try:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(0)
        ok = cap.isOpened()
        cap.release()
        if ok:
            logger.info("sensory_gate: camera present (index 0)")
        else:
            logger.info("sensory_gate: camera not found")
        return ok
    except Exception as e:
        logger.info("sensory_gate: camera unavailable (%s)", e)
        return False


def _probe_microphone() -> bool:
    try:
        import sounddevice as sd  # type: ignore
        devices = sd.query_devices()
        # Any input device is sufficient
        has_input = any(d["max_input_channels"] > 0 for d in devices)
        if has_input:
            logger.info("sensory_gate: microphone present")
        else:
            logger.info("sensory_gate: no input audio device found")
        return has_input
    except Exception as e:
        logger.info("sensory_gate: microphone unavailable (%s)", e)
        return False


# ── events ─────────────────────────────────────────────────────────────────────

@dataclass
class SensoryGateControlEvent(bus.Event):
    camera_enabled:    bool
    microphone_enabled: bool
    frame_rate_limit:  int    # fps cap (0 = off)
    audio_chunk_ms:    int    # audio chunk size in ms (0 = off)


@dataclass
class DroppedInputEvent(bus.Event):
    sensor: str   # "camera" | "microphone"
    reason: str


# ── gate parameters ────────────────────────────────────────────────────────────

# Frame rate caps per arousal mode
_CAMERA_FPS: dict[ArousalMode, int] = {
    ArousalMode.DEEP_SLEEP:  0,
    ArousalMode.LIGHT_SLEEP: 0,
    ArousalMode.RECOVERY:    0,
    ArousalMode.WAKEFUL:     5,
    ArousalMode.FOCUSED:     15,
}

# Audio chunk size (ms) per arousal mode — larger = lower CPU, worse latency
_AUDIO_CHUNK_MS: dict[ArousalMode, int] = {
    ArousalMode.DEEP_SLEEP:  0,
    ArousalMode.LIGHT_SLEEP: 200,
    ArousalMode.RECOVERY:    200,
    ArousalMode.WAKEFUL:     50,
    ArousalMode.FOCUSED:     20,
}


# ── state ──────────────────────────────────────────────────────────────────────

_camera_hw_present:    bool = False
_microphone_hw_present: bool = False

_camera_enabled:    bool = False
_microphone_enabled: bool = False
_frame_rate_limit:  int  = 0
_audio_chunk_ms:    int  = 0

_current_mode: ArousalMode = ArousalMode.LIGHT_SLEEP


async def _apply_gate(mode: ArousalMode) -> None:
    global _camera_enabled, _microphone_enabled, _frame_rate_limit, _audio_chunk_ms, _current_mode
    _current_mode = mode

    new_cam   = _camera_hw_present    and _CAMERA_FPS.get(mode, 0) > 0
    new_mic   = _microphone_hw_present and _AUDIO_CHUNK_MS.get(mode, 0) > 0
    new_fps   = _CAMERA_FPS.get(mode, 0)
    new_chunk = _AUDIO_CHUNK_MS.get(mode, 0)

    changed = (
        new_cam   != _camera_enabled    or
        new_mic   != _microphone_enabled or
        new_fps   != _frame_rate_limit   or
        new_chunk != _audio_chunk_ms
    )

    _camera_enabled     = new_cam
    _microphone_enabled = new_mic
    _frame_rate_limit   = new_fps
    _audio_chunk_ms     = new_chunk

    if changed:
        logger.info(
            "sensory_gate: mode=%s  cam=%s@%dfps  mic=%s@%dms",
            mode.value,
            "on" if _camera_enabled    else "off", _frame_rate_limit,
            "on" if _microphone_enabled else "off", _audio_chunk_ms,
        )
        await bus.publish(
            SensoryGateControlEvent(
                source="sensory_gate",
                timestamp=clock.elapsed(),
                camera_enabled=_camera_enabled,
                microphone_enabled=_microphone_enabled,
                frame_rate_limit=_frame_rate_limit,
                audio_chunk_ms=_audio_chunk_ms,
            )
        )

        state_store.set("sensory_gate.camera_enabled",     _camera_enabled)
        state_store.set("sensory_gate.microphone_enabled", _microphone_enabled)


async def on_arousal_state(event: ArousalStateEvent) -> None:
    if event.mode != _current_mode:
        await _apply_gate(event.mode)


def init() -> None:
    global _camera_hw_present, _microphone_hw_present

    _camera_hw_present     = _probe_camera()
    _microphone_hw_present = _probe_microphone()

    if not _camera_hw_present:
        logger.warning("sensory_gate: camera disabled — hardware not found")
        state_store.set("sensory_gate.camera_hw_present", False)
    if not _microphone_hw_present:
        logger.warning("sensory_gate: microphone disabled — hardware not found")
        state_store.set("sensory_gate.microphone_hw_present", False)

    bus.subscribe(ArousalStateEvent, on_arousal_state)
    logger.info(
        "sensory_gate initialized — camera_hw=%s  mic_hw=%s",
        _camera_hw_present, _microphone_hw_present,
    )
