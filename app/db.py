"""SQLite connection management.

Raw `sqlite3`, no ORM (DECISIONS 001). The database file path comes from
`DATABASE_PATH` (default `data/console.db`), resolved relative to the repo root
so scripts run from any working directory.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent


def database_path() -> Path:
    """Resolve the configured SQLite file path (absolute)."""
    raw = os.getenv("DATABASE_PATH", "data/console.db")
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def connect() -> sqlite3.Connection:
    """Open a connection with row access by name and FK enforcement on."""
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Connection scope that commits on success and rolls back on error."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
