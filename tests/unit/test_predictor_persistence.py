"""
Unit tests for predictor model persistence (Stage 7 / design principle 4).

Without persistence every restart resets the model to the identity matrix and
discards the entire developmental history, so these tests pin the round trip
and the guards that stop a corrupt or mismatched model being adopted.

Runs under pytest or directly:  python tests/unit/test_predictor_persistence.py
"""

import sys
import tempfile
from pathlib import Path

# Make src/ importable whether run via pytest or as a script.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import predictor
import state_store


def _reset() -> Path:
    db = Path(tempfile.mkdtemp()) / "state.db"
    state_store.init(db)
    predictor._W = [[1.0 if i == j else 0.0 for j in range(predictor.FEATURE_DIM)]
                    for i in range(predictor.FEATURE_DIM)]
    predictor._b = [0.0] * predictor.FEATURE_DIM
    predictor._ewa_error = 0.0
    predictor._chunks_trained = 0
    predictor._error_history.clear()
    predictor._rhythm_counts = [[1.0] * predictor.N_CATEGORIES
                                for _ in range(predictor.N_CATEGORIES)]
    return db


def _identity():
    return [[1.0 if i == j else 0.0 for j in range(predictor.FEATURE_DIM)]
            for i in range(predictor.FEATURE_DIM)]


def test_load_returns_false_when_nothing_saved():
    _reset()
    assert predictor.load_state() is False, "a fresh store must yield no model"


def test_weights_survive_a_save_load_cycle():
    db = _reset()

    predictor._W[0][1] = 0.37
    predictor._b[2] = -0.11
    predictor._ewa_error = 0.0456
    predictor._chunks_trained = 812
    predictor._rhythm_counts[0][1] = 9.0
    predictor.save_state()

    # Wipe RAM the way a restart would.
    predictor._W = _identity()
    predictor._b = [0.0] * predictor.FEATURE_DIM
    predictor._ewa_error = 0.0
    predictor._chunks_trained = 0
    predictor._rhythm_counts = [[1.0] * predictor.N_CATEGORIES
                                for _ in range(predictor.N_CATEGORIES)]

    assert predictor.load_state() is True, "a saved model must be found"
    assert predictor._W[0][1] == 0.37, "weights must be restored"
    assert predictor._b[2] == -0.11, "biases must be restored"
    assert predictor._ewa_error == 0.0456, "error statistics must be restored"
    assert predictor._chunks_trained == 812, "model age must be restored"
    assert predictor._rhythm_counts[0][1] == 9.0, "rhythm model must be restored"


def test_model_age_accumulates_across_sessions():
    """The point of persistence: sessions add up into a developmental history."""
    db = _reset()

    predictor._chunks_trained = 500
    predictor.save_state()

    predictor._chunks_trained = 0
    predictor.load_state()
    predictor._chunks_trained += 300      # a second session of experience
    predictor.save_state()

    predictor._chunks_trained = 0
    predictor.load_state()
    assert predictor._chunks_trained == 800, \
        "experience must accumulate rather than restart each session"


def test_error_history_survives():
    _reset()
    for v in (0.1, 0.2, 0.3):
        predictor._error_history.append(v)
    predictor.save_state()

    predictor._error_history.clear()
    predictor.load_state()

    assert list(predictor._error_history) == [0.1, 0.2, 0.3], \
        "the rolling error window must be restored"


def test_model_with_wrong_shape_is_rejected():
    """A model saved under a different FEATURE_DIM must not corrupt the live one."""
    _reset()
    state_store.set("predictor.W", [[1.0, 0.0], [0.0, 1.0]])   # 2x2, not 5x5
    state_store.set("predictor.b", [0.0, 0.0])

    assert predictor.load_state() is False, "a mismatched model must be refused"
    assert predictor._W == _identity(), "the live model must be left untouched"


def test_corrupt_model_does_not_raise():
    _reset()
    state_store.set("predictor.W", "not-a-matrix")

    assert predictor.load_state() is False, "corrupt state must be refused, not fatal"
    assert predictor._W == _identity(), "the live model must be left untouched"


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
