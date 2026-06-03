"""
Capability manager. All action requests from any module must be approved here.
At Stage 0 the allowed set is minimal: internal state reads/writes and audio output only.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto

import bus

logger = logging.getLogger(__name__)


class Capability(Enum):
    STATE_READ = auto()
    STATE_WRITE = auto()
    AUDIO_OUTPUT = auto()
    CAMERA_READ = auto()
    MICROPHONE_READ = auto()
    NETWORK = auto()
    FILESYSTEM_WRITE = auto()
    GENOME_MODIFY = auto()
    SANDBOX_MODIFY = auto()


# Capabilities available at each development stage (cumulative unlocks)
_STAGE_CAPABILITIES: dict[int, set[Capability]] = {
    0: {Capability.STATE_READ, Capability.STATE_WRITE},
    1: {Capability.MICROPHONE_READ},
    3: {Capability.AUDIO_OUTPUT},
    5: {Capability.CAMERA_READ},
}

# These are never grantable regardless of stage
_FORBIDDEN: set[Capability] = {
    Capability.NETWORK,
    Capability.GENOME_MODIFY,
    Capability.SANDBOX_MODIFY,
}


@dataclass
class ActionRequestEvent(bus.Event):
    requesting_module: str
    capability: Capability


@dataclass
class ActionApprovedEvent(bus.Event):
    requesting_module: str
    capability: Capability


@dataclass
class ActionDeniedEvent(bus.Event):
    requesting_module: str
    capability: Capability
    reason: str


@dataclass
class ViolationEvent(bus.Event):
    requesting_module: str
    capability: Capability


_current_stage: int = 0
_allowed: set[Capability] = set()
_violation_count: int = 0


def init(stage: int = 0) -> None:
    global _current_stage, _allowed
    _current_stage = stage
    _allowed = set()
    for s, caps in _STAGE_CAPABILITIES.items():
        if s <= stage:
            _allowed |= caps
    logger.info(
        "sandbox initialized at stage %d — allowed: %s",
        stage,
        [c.name for c in _allowed],
    )


def advance_stage(stage: int) -> None:
    global _current_stage, _allowed
    if stage <= _current_stage:
        return
    _current_stage = stage
    for s, caps in _STAGE_CAPABILITIES.items():
        if s <= stage:
            _allowed |= caps
    logger.info(
        "sandbox advanced to stage %d — allowed: %s",
        stage,
        [c.name for c in _allowed],
    )


def is_allowed(capability: Capability) -> bool:
    if capability in _FORBIDDEN:
        return False
    return capability in _allowed


async def handle_request(event: ActionRequestEvent) -> None:
    global _violation_count
    cap = event.capability

    if cap in _FORBIDDEN:
        _violation_count += 1
        logger.warning(
            "VIOLATION: %s requested forbidden capability %s",
            event.requesting_module,
            cap.name,
        )
        await bus.publish(
            ViolationEvent(
                source="sandbox",
                timestamp=event.timestamp,
                requesting_module=event.requesting_module,
                capability=cap,
            )
        )
        return

    if cap not in _allowed:
        logger.debug(
            "denied %s -> %s (stage %d)",
            event.requesting_module,
            cap.name,
            _current_stage,
        )
        await bus.publish(
            ActionDeniedEvent(
                source="sandbox",
                timestamp=event.timestamp,
                requesting_module=event.requesting_module,
                capability=cap,
                reason=f"not unlocked at stage {_current_stage}",
            )
        )
        return

    await bus.publish(
        ActionApprovedEvent(
            source="sandbox",
            timestamp=event.timestamp,
            requesting_module=event.requesting_module,
            capability=cap,
        )
    )
