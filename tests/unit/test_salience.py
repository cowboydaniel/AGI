"""
Unit tests for innate salience detection (src/salience.py, GENOME.md P1).

The behaviour under test is the one a newborn already has: ignore static,
hiss, fans and soft wind however loud they are, and attend to a voice. These
tests drive the detector with synthetic streams whose acoustic character is
known, and assert the biological outcome rather than any internal number.

Runs under pytest or directly:  python tests/unit/test_salience.py
"""

import asyncio
import math
import random
import sys
from pathlib import Path

# Make src/ importable whether run via pytest or as a script.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import salience
from events import AudioEnergyEvent


def _reset() -> None:
    salience._energy.clear()
    salience._salient_count = 0
    salience._total_count = 0
    salience._chunk_ms = 200
    salience._last_key = None


def _chunk(rms, periodicity=0.0, t=0.0):
    return AudioEnergyEvent(
        source="t", timestamp=t, rms=rms, zcr=0.2, spectral_centroid=1500.0,
        spectral_flatness=0.5, band_ratio=0.5, chunk_ms=200,
        periodicity=periodicity, f0_hz=0.0,
    )


def _feed(stream) -> list:
    """Run a stream of (rms, periodicity) through the detector."""
    verdicts = []
    for i, (rms, per) in enumerate(stream):
        salient, score, onset, p, r, why = salience.evaluate(_chunk(rms, per, t=i * 0.2))
        salience._energy.append(rms)
        verdicts.append((salient, why))
    return verdicts


def _salient_fraction(stream) -> float:
    v = _feed(stream)
    return sum(1 for s, _ in v if s) / len(v)


# -- streams ---------------------------------------------------------------------

def _static(n=60, level=0.05):
    """Broadband hiss: steady level, no periodicity."""
    return [(level * random.uniform(0.9, 1.1), random.uniform(0.0, 0.08))
            for _ in range(n)]


def _loud_static(n=60):
    """The key case: static far louder than any speech, still meaningless."""
    return _static(n, level=0.35)


def _soft_wind(n=60):
    """Slow-swelling aperiodic noise, as wind through a window."""
    out = []
    for i in range(n):
        swell = 0.04 * (1.0 + 0.5 * math.sin(i / 18.0))    # very slow, < 0.1 Hz
        out.append((swell, random.uniform(0.0, 0.10)))
    return out


def _fan(n=60):
    """A constant motor drone: periodic-ish but utterly unchanging."""
    return [(0.09, 0.35) for _ in range(n)]


def _speech(n=60):
    """Voice: strongly periodic, pulsed at a syllable rate near 4 Hz."""
    out = []
    for i in range(n):
        # 200 ms chunks -> 5 Hz sampling; a syllable every ~2 chunks.
        syll = 0.5 + 0.5 * math.sin(2 * math.pi * i / 2.5)
        rms = 0.02 + 0.13 * syll
        out.append((rms, 0.55 + 0.35 * syll))
    return out


def _quiet_speech(n=60):
    """A quiet voice must beat loud static - structure over volume."""
    out = []
    for i in range(n):
        syll = 0.5 + 0.5 * math.sin(2 * math.pi * i / 2.5)
        out.append((0.01 + 0.03 * syll, 0.55 + 0.35 * syll))
    return out


# -- the behaviour that matters --------------------------------------------------

def test_static_is_ignored():
    _reset(); random.seed(1)
    assert _salient_fraction(_static()) < 0.10, \
        "steady static must not hold attention"


def test_loud_static_is_still_ignored():
    """Volume must never be sufficient. This is the whole point of P1."""
    _reset(); random.seed(2)
    frac = _salient_fraction(_loud_static())
    assert frac < 0.10, \
        f"static at 7x speech level must still be ignored (was {frac:.0%})"


def test_soft_wind_is_ignored():
    _reset(); random.seed(3)
    assert _salient_fraction(_soft_wind()) < 0.10, \
        "slow aperiodic swell must not read as an event"


def test_constant_fan_is_ignored():
    """Unchanging drone: no onset, no rhythm. A baby tunes it out."""
    _reset(); random.seed(4)
    assert _salient_fraction(_fan()) < 0.15, \
        "a constant drone must not sustain attention"


def test_speech_is_salient():
    _reset(); random.seed(5)
    frac = _salient_fraction(_speech())
    assert frac > 0.40, f"a voice must attract attention (was {frac:.0%})"


def test_quiet_speech_beats_loud_static():
    """The decisive comparison: structure wins over volume."""
    _reset(); random.seed(6)
    quiet_voice = _salient_fraction(_quiet_speech())
    _reset(); random.seed(6)
    loud_noise = _salient_fraction(_loud_static())

    assert quiet_voice > loud_noise, (
        f"a quiet voice ({quiet_voice:.0%}) must be more salient than "
        f"loud static ({loud_noise:.0%})"
    )


def test_voice_emerging_from_noisy_room_is_detected():
    """A room with a fan running, then someone speaks over it."""
    _reset(); random.seed(7)
    stream = _fan(30) + [(a + 0.09, p) for a, p in _speech(30)]
    verdicts = _feed(stream)

    fan_part = sum(1 for s, _ in verdicts[:30] if s) / 30
    voice_part = sum(1 for s, _ in verdicts[30:] if s) / 30

    assert voice_part > fan_part, \
        f"the voice ({voice_part:.0%}) must stand out against the fan ({fan_part:.0%})"


# -- mechanism checks ------------------------------------------------------------

def test_unstructured_sound_is_rejected_regardless_of_score():
    """The structure gate: no amount of energy substitutes for structure."""
    _reset()
    for _ in range(20):
        salience._energy.append(0.001)

    salient, score, onset, per, rhy, why = salience.evaluate(_chunk(0.9, periodicity=0.02))

    assert onset > 0.5, "a huge energy step must register as an onset"
    assert not salient, "but an aperiodic burst must not be salient"
    assert why == "unstructured (noise-like)", "and the reason must say so"


def test_periodic_sound_can_be_salient_without_being_loud():
    _reset()
    for _ in range(20):
        salience._energy.append(0.002)

    salient, score, *_ = salience.evaluate(_chunk(0.02, periodicity=0.9))

    assert salient, "a clearly periodic sound must be attended to even when quiet"


def test_background_tracks_the_room():
    _reset()
    assert salience.background() == 0.0, "no history means no estimate"

    for _ in range(40):
        salience._energy.append(0.08)

    assert salience.background() > 0.05, "a persistently loud room must raise the estimate"


def test_salience_event_is_published():
    _reset()
    published = []

    async def collect(e):
        published.append(e)

    import bus
    bus.publish = collect

    async def run():
        for i in range(5):
            await salience.on_audio_energy(_chunk(0.1, 0.8, t=i * 0.2))

    asyncio.run(run())

    assert len(published) == 5, "every chunk must be judged"
    assert all(isinstance(e, salience.SalienceEvent) for e in published), \
        "judgements must be published as SalienceEvent"
    assert all(e.reason for e in published), "every judgement must carry a reason"


def test_no_vocabulary_or_categories_are_encoded():
    """Anti-hardcoding: P1 is learnability infrastructure, not knowledge.

    Inspects executable code only. Comments and docstrings discuss voices and
    words as prose, which is documentation rather than encoded vocabulary.
    """
    import ast

    source = (Path(__file__).resolve().parents[2] / "src" / "salience.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)

    # Docstring nodes are the first statement of a module, function or class.
    # Identify them by identity, since ast.get_docstring() re-indents the text
    # and so never compares equal to the raw literal.
    docstring_nodes = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            body = getattr(n, "body", [])
            if body and isinstance(body[0], ast.Expr)                     and isinstance(body[0].value, ast.Constant)                     and isinstance(body[0].value.value, str):
                docstring_nodes.add(id(body[0].value))

    tokens = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstring_nodes:
                tokens.append(node.value.lower())
        elif isinstance(node, ast.Name):
            tokens.append(node.id.lower())
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            tokens.append(node.name.lower())

    haystack = " ".join(tokens)
    for forbidden in ("vowel", "consonant", "phoneme", "vocab", "yes", "hello",
                      "apple", "label"):
        assert forbidden not in haystack,             f"salience must not encode {forbidden!r} - it knows no vocabulary"

    # No lookup table of sound categories may live in module state either.
    tables = [k for k, v in vars(salience).items()
              if isinstance(v, dict) and len(v) > 2 and not k.startswith("__")]
    assert not tables, f"salience must hold no category table (found {tables})"


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
