"""
Unit tests for the Stage 0 persistent state store (src/state_store.py).

Covers the SQLite key/value layer that gives the system Continuity — the
ability to survive a process restart with its development stage and internal
variables intact. Every test uses a throwaway database in a temp directory,
so nothing touches the real data/state.db.

Runs under pytest or directly:  python tests/unit/test_state.py
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

# Make src/ importable whether run via pytest or as a script.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import state_store


# ── harness ──────────────────────────────────────────────────────────────────────

def _fresh_db() -> Path:
    """A path to a not-yet-created database inside a fresh temp directory."""
    return Path(tempfile.mkdtemp()) / "state.db"


def _reset() -> Path:
    """Initialise the store against a brand-new database and return its path."""
    db = _fresh_db()
    state_store.init(db)
    return db


# ── tests ──────────────────────────────────────────────────────────────────────

def test_init_creates_database_and_tables():
    db = _fresh_db()
    assert not db.exists(), "precondition: database must not exist yet"

    state_store.init(db)

    assert db.exists(), "init must create the database file"
    tables = {
        row[0]
        for row in state_store._get_conn().execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "state" in tables, "init must create the state table"
    assert "meta" in tables, "init must create the meta table"


def test_init_creates_missing_parent_directories():
    db = Path(tempfile.mkdtemp()) / "nested" / "deeper" / "state.db"

    state_store.init(db)

    assert db.exists(), "init must create intermediate directories"


def test_set_get_roundtrip_preserves_json_types():
    _reset()

    cases = {
        "int_value":   7,
        "float_value": 0.25,
        "str_value":   "wakeful",
        "bool_value":  True,
        "none_value":  None,
        "list_value":  [1, 2, 3],
        "dict_value":  {"mode": "LIGHT_SLEEP", "pressure": 0.5},
    }
    for key, value in cases.items():
        state_store.set(key, value)

    for key, value in cases.items():
        got = state_store.get(key)
        assert got == value, f"{key}: expected {value!r}, got {got!r}"
        assert type(got) is type(value), f"{key}: type not preserved through JSON"


def test_get_returns_default_for_missing_key():
    _reset()

    assert state_store.get("never_written") is None, "default default must be None"
    assert state_store.get("never_written", default=3) == 3, "explicit default must be returned"
    # A stored None must be distinguishable from a missing key.
    state_store.set("explicit_none", None)
    assert state_store.get("explicit_none", default=3) is None, \
        "a stored null must win over the default"


def test_set_overwrites_existing_key():
    _reset()

    state_store.set("development_stage", 0)
    state_store.set("development_stage", 4)

    assert state_store.get("development_stage") == 4, "second write must win"
    rows = state_store._get_conn().execute(
        "SELECT COUNT(*) FROM state WHERE key='development_stage'"
    ).fetchone()[0]
    assert rows == 1, "upsert must not insert a duplicate row"


def test_delete_removes_key():
    _reset()

    state_store.set("scratch", "value")
    state_store.delete("scratch")

    assert state_store.get("scratch", default="gone") == "gone", "key must be removed"
    # Deleting a key that was never there must not raise.
    state_store.delete("never_existed")


def test_state_survives_close_and_reopen():
    """Continuity: the whole point of Stage 0 — state outlives the process."""
    db = _reset()

    state_store.set("development_stage", 6)
    state_store.set("drives", {"curiosity": 0.7, "energy": 0.4})
    state_store.close()

    # Simulate a restart: same path, fresh connection.
    state_store.init(db)

    assert state_store.get("development_stage") == 6, "stage must survive a restart"
    assert state_store.get("drives") == {"curiosity": 0.7, "energy": 0.4}, \
        "structured values must survive a restart"


def test_writes_are_committed_to_disk_immediately():
    """An unclean shutdown must not lose the last write — so no open transaction."""
    db = _reset()

    state_store.set("development_stage", 3)

    # Read through a completely independent connection, without closing ours.
    side = sqlite3.connect(str(db))
    try:
        row = side.execute(
            "SELECT value FROM state WHERE key='development_stage'"
        ).fetchone()
    finally:
        side.close()

    assert row is not None, "write must be committed, not left in a transaction"
    assert json.loads(row[0]) == 3, "committed value must match"


def test_use_before_init_raises():
    original = state_store._conn
    state_store._conn = None
    try:
        for name, call in (
            ("get",    lambda: state_store.get("k")),
            ("set",    lambda: state_store.set("k", 1)),
            ("delete", lambda: state_store.delete("k")),
        ):
            try:
                call()
            except RuntimeError:
                pass
            else:
                raise AssertionError(f"{name} must raise RuntimeError before init()")
    finally:
        state_store._conn = original


# ── script runner (works without pytest) ─────────────────────────────────────────

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
