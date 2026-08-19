"""
Caregiver Feedback Channel — Stage 9 groundwork.

The caregiver structures experience; the caregiver does not supply knowledge
(CLAUDE.md, Caregiver Rule). This module is the input half of that
relationship: it turns a caregiver's real-time reinforcement into
CaregiverFeedbackEvent on the bus, which value.py already consumes as its
strongest social signal and memory.py binds to the open episode.

Feedback vocabulary (CAREGIVER_INTERFACE.md section 4.2):

    GOOD  BAD  YES  NO  AGAIN  STOP  REST

These are NOT words the system understands, and nothing here teaches their
meaning. Each maps only to a valence and an intensity — a push toward or away
from whatever the system was just doing. The tokens are for the human's
convenience; the system receives numbers. This distinction is the whole
difference between reinforcement and knowledge injection, so it must survive
any future extension of this module.

Transport
---------
A plain text file, one token per line, polled on the clock. Writing to it is
the entire caregiver interface until the Stage 9 UI exists:

    echo GOOD >> sandbox/tmp/caregiver_feedback

The file is truncated after each read, so each token fires exactly once.
Nothing is executed from the file — unrecognised lines are counted and
discarded, never interpreted.
"""

import logging
from pathlib import Path

import bus
import clock
import state_store
from events import CaregiverFeedbackEvent

logger = logging.getLogger(__name__)

# Poll cadence — 10 Hz clock, so every 5 ticks is twice a second: fast enough
# that feedback lands inside the episode it refers to.
POLL_EVERY_TICKS = 5

FEEDBACK_PATH = Path("sandbox/tmp/caregiver_feedback")

# Token → (valence, intensity). Valence sign is the only "meaning" present,
# and it is reinforcement, not semantics.
_VOCAB: dict = {
    "GOOD":  (+1.0, 0.8),
    "YES":   (+1.0, 0.5),
    "BAD":   (-1.0, 0.8),
    "NO":    (-1.0, 0.5),
    "AGAIN": (+0.3, 0.4),   # mild encouragement to repeat
    "STOP":  (-0.6, 0.7),
    "REST":  (0.0, 0.3),    # neutral: a cue to settle, not a judgement
}

_delivered:      int = 0
_unrecognised:   int = 0


def _read_tokens() -> list:
    """Drain the feedback file. Returns the raw token strings found."""
    try:
        if not FEEDBACK_PATH.exists():
            return []
        text = FEEDBACK_PATH.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return []
        FEEDBACK_PATH.write_text("", encoding="utf-8")   # consume
        return [line.strip().upper() for line in text.splitlines() if line.strip()]
    except Exception as e:
        logger.warning("caregiver: could not read feedback channel (%s)", e)
        return []


async def deliver(token: str, timestamp: float | None = None) -> bool:
    """Publish one feedback token. Returns False if the token is unknown.

    Exposed directly so a UI, a test, or a teaching script can call it without
    going through the file.
    """
    global _delivered, _unrecognised

    token = token.strip().upper()
    if token not in _VOCAB:
        _unrecognised += 1
        logger.debug("caregiver: ignoring unrecognised token %r", token)
        return False

    valence, intensity = _VOCAB[token]
    _delivered += 1
    state_store.set("caregiver.feedback_count", _delivered)

    logger.info("caregiver: %s  (valence=%+.2f intensity=%.2f)",
                token, valence, intensity)

    await bus.publish(CaregiverFeedbackEvent(
        source="caregiver",
        timestamp=clock.elapsed() if timestamp is None else timestamp,
        valence=valence,
        kind=token.lower(),
        intensity=intensity,
    ))
    return True


async def on_tick(event: clock.TickEvent) -> None:
    # The clock's tick is the time reference, not a private counter, so poll
    # cadence stays aligned across restarts and is testable directly.
    if event.tick % POLL_EVERY_TICKS:
        return
    for token in _read_tokens():
        await deliver(token, timestamp=event.timestamp)


def init() -> None:
    try:
        FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        FEEDBACK_PATH.write_text("", encoding="utf-8")
    except Exception as e:
        logger.warning("caregiver: could not open feedback channel at %s (%s)",
                       FEEDBACK_PATH, e)

    bus.subscribe(clock.TickEvent, on_tick)
    logger.info("caregiver initialized — feedback channel at %s  vocabulary=%s",
                FEEDBACK_PATH, ",".join(sorted(_VOCAB)))
