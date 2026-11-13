"""Database engine, schema and sample data for the Attendance Management project."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "attendance.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS people (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    code      TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    group_name TEXT NOT NULL DEFAULT 'Default'
);

CREATE TABLE IF NOT EXISTS attendance (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id  INTEGER NOT NULL,
    day        TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late', 'leave')),
    note       TEXT NOT NULL DEFAULT '',
    UNIQUE (person_id, day),
    FOREIGN KEY (person_id) REFERENCES people (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_attendance_day ON attendance (day);
CREATE INDEX IF NOT EXISTS idx_attendance_person ON attendance (person_id);
"""

SEED_PEOPLE = [
    ("STU001", "Aarav Sharma", "Batch A"),
    ("STU002", "Priya Nair", "Batch A"),
    ("STU003", "Rohan Das", "Batch A"),
    ("STU004", "Sneha Iyer", "Batch B"),
    ("STU005", "Vikram Rao", "Batch B"),
    ("STU006", "Ananya Menon", "Batch B"),
]

# (code, day, status, note)
SEED_ATTENDANCE = [
    ("STU001", "2026-01-05", "present", ""),
    ("STU002", "2026-01-05", "present", ""),
    ("STU003", "2026-01-05", "absent", "not well"),
    ("STU004", "2026-01-05", "late", "traffic"),
    ("STU005", "2026-01-05", "present", ""),
    ("STU006", "2026-01-05", "present", ""),
    ("STU001", "2026-01-06", "present", ""),
    ("STU002", "2026-01-06", "late", "bus delay"),
    ("STU003", "2026-01-06", "present", ""),
    ("STU004", "2026-01-06", "present", ""),
    ("STU005", "2026-01-06", "absent", ""),
    ("STU006", "2026-01-06", "leave", "family event"),
    ("STU001", "2026-01-07", "present", ""),
    ("STU002", "2026-01-07", "present", ""),
    ("STU003", "2026-01-07", "present", ""),
    ("STU004", "2026-01-07", "absent", ""),
    ("STU005", "2026-01-07", "present", ""),
    ("STU006", "2026-01-07", "present", ""),
]


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection to the attendance database, creating it when missing."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the schema if it does not exist yet."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def seed(conn: sqlite3.Connection) -> int:
    """Insert the bundled sample data. Returns the number of rows created."""
    created = 0
    for row in SEED_PEOPLE:
        cur = conn.execute(
            "INSERT OR IGNORE INTO people (code, full_name, group_name) VALUES (?, ?, ?)",
            row,
        )
        created += cur.rowcount

    existing = conn.execute("SELECT COUNT(*) AS n FROM attendance").fetchone()["n"]
    if existing:
        # Seed data already applied: keep re-runs idempotent.
        conn.commit()
        return created

    for code, day, status, note in SEED_ATTENDANCE:
        person = conn.execute("SELECT id FROM people WHERE code = ?", (code,)).fetchone()
        if person is None:
            continue
        cur = conn.execute(
            """
            INSERT INTO attendance (person_id, day, status, note)
            VALUES (?, ?, ?, ?)
            """,
            (person["id"], day, status, note),
        )
        created += cur.rowcount

    conn.commit()
    return created


def open_initialised(db_path: str | Path | None = None, *, with_seed: bool = True) -> sqlite3.Connection:
    """Convenience helper used by the CLI and the tests."""
    conn = connect(db_path)
    init_db(conn)
    if with_seed:
        seed(conn)
    return conn
