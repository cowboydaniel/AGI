"""
Unit tests for the caregiver feedback channel (src/caregiver.py).

The caregiver structures experience but must never inject knowledge, so these
tests pin both halves: recognised tokens become reinforcement signals with the
right valence, and anything else is discarded rather than interpreted.

Runs under pytest or directly:  python tests/unit/test_caregiver.py
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Make src/ importable whether run via pytest or as a script.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import bus
import caregiver
import clock
import state_store
from events import CaregiverFeedbackEvent


_PUBLISHED: list = []


async def _collect(event) -> None:
    _PUBLISHED.append(event)


def _reset() -> Path:
    _PUBLISHED.clear()
    state_store.init(Path(tempfile.mkdtemp()) / "state.db")
    bus.publish = _collect
    caregiver._delivered = 0
    caregiver._unrecognised = 0
    path = Path(tempfile.mkdtemp()) / "caregiver_feedback"
    path.write_text("", encoding="utf-8")
    caregiver.FEEDBACK_PATH = path
    return path


def _feedback() -> list:
    return [e for e in _PUBLISHED if isinstance(e, CaregiverFeedbackEvent)]


# -- vocabulary -----------------------------------------------------------------

def test_approval_and_disapproval_have_opposite_valence():
    _reset()

    asyncio.run(caregiver.deliver("GOOD"))
    asyncio.run(caregiver.deliver("BAD"))

    events = _feedback()
    assert len(events) == 2, "both tokens must produce feedback"
    assert events[0].valence > 0, "GOOD must be positive reinforcement"
    assert events[1].valence < 0, "BAD must be negative reinforcement"


def test_every_documented_token_is_accepted():
    """CAREGIVER_INTERFACE.md section 4.2 lists the caregiver's buttons."""
    _reset()

    for token in ("GOOD", "BAD", "YES", "NO", "AGAIN", "STOP", "REST"):
        assert asyncio.run(caregiver.deliver(token)) is True, \
            f"{token} is a documented control and must be accepted"

    assert len(_feedback()) == 7, "each token must emit exactly one event"


def test_intensity_and_valence_are_bounded():
    _reset()

    for token in caregiver._VOCAB:
        asyncio.run(caregiver.deliver(token))

    for e in _feedback():
        assert -1.0 <= e.valence <= 1.0, f"{e.kind}: valence out of range"
        assert 0.0 <= e.intensity <= 1.0, f"{e.kind}: intensity out of range"


def test_rest_is_neutral_not_a_judgement():
    _reset()

    asyncio.run(caregiver.deliver("REST"))

    assert _feedback()[0].valence == 0.0, "REST must not reinforce in either direction"


def test_tokens_are_case_insensitive_and_trimmed():
    _reset()

    assert asyncio.run(caregiver.deliver("  good  ")) is True, \
        "caregiver input must tolerate whitespace and case"


# -- knowledge injection guard --------------------------------------------------

def test_unknown_tokens_are_discarded_not_interpreted():
    """Anti-hardcoding: the channel carries reinforcement, never vocabulary."""
    _reset()

    for junk in ("APPLE", "the ball is red", "42", "<script>", ""):
        assert asyncio.run(caregiver.deliver(junk)) is False, \
            f"{junk!r} must not be accepted as feedback"

    assert _feedback() == [], "no event may be emitted for unrecognised input"
    assert caregiver._unrecognised >= 4, "rejected input must be counted"


def test_feedback_carries_no_content_beyond_reinforcement():
    _reset()

    asyncio.run(caregiver.deliver("GOOD"))
    e = _feedback()[0]

    assert set(vars(e)) == {"source", "timestamp", "valence", "kind", "intensity"}, \
        "feedback must carry only reinforcement, never payload the system could decode"


# -- file transport -------------------------------------------------------------

def test_tokens_are_read_from_the_channel_file():
    path = _reset()
    path.write_text("GOOD\nNO\n", encoding="utf-8")

    async def run():
        await caregiver.on_tick(clock.TickEvent(
            source="clock", timestamp=1.0, tick=caregiver.POLL_EVERY_TICKS))

    asyncio.run(run())

    kinds = [e.kind for e in _feedback()]
    assert kinds == ["good", "no"], "each line must fire once, in order"


def test_channel_is_drained_so_tokens_fire_once():
    path = _reset()
    path.write_text("GOOD\n", encoding="utf-8")

    async def run():
        for i in range(1, 4):
            await caregiver.on_tick(clock.TickEvent(
                source="clock", timestamp=float(i),
                tick=i * caregiver.POLL_EVERY_TICKS))

    asyncio.run(run())

    assert len(_feedback()) == 1, "a token must not be redelivered on later polls"
    assert path.read_text(encoding="utf-8").strip() == "", "the channel must be drained"


def test_missing_channel_file_is_survivable():
    path = _reset()
    path.unlink()

    async def run():
        await caregiver.on_tick(clock.TickEvent(
            source="clock", timestamp=1.0, tick=caregiver.POLL_EVERY_TICKS))

    asyncio.run(run())          # must not raise
    assert _feedback() == [], "a missing channel simply yields no feedback"


# -- script runner (works without pytest) ---------------------------------------

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
