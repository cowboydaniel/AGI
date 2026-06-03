"""
SQLite-backed persistent state store. Survives process restarts.
Key-value with optional JSON serialization for structured values.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DB_PATH = Path("data/state.db")
_conn: sqlite3.Connection | None = None


def init(db_path: Path = _DB_PATH) -> None:
    global _conn, _DB_PATH
    _DB_PATH = db_path
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    _conn.execute(
        "CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    _conn.execute(
        "CREATE TABLE IF NOT EXISTS meta "
        "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    _conn.commit()
    logger.info("state store initialized at %s", _DB_PATH)


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("state_store.init() must be called before use")
    return _conn


def set(key: str, value: Any) -> None:
    serialized = json.dumps(value)
    _get_conn().execute(
        "INSERT INTO state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, serialized),
    )
    _get_conn().commit()


def get(key: str, default: Any = None) -> Any:
    row = _get_conn().execute(
        "SELECT value FROM state WHERE key=?", (key,)
    ).fetchone()
    if row is None:
        return default
    return json.loads(row[0])


def delete(key: str) -> None:
    _get_conn().execute("DELETE FROM state WHERE key=?", (key,))
    _get_conn().commit()


def close() -> None:
    if _conn:
        _conn.close()
        logger.info("state store closed")
