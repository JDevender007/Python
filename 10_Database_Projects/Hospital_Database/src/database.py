"""Database engine, schema and sample data for the Hospital Database project."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "hospital.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS doctors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    license_no  TEXT NOT NULL UNIQUE,
    full_name   TEXT NOT NULL,
    specialty   TEXT NOT NULL,
    phone       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mrn         TEXT NOT NULL UNIQUE,
    full_name   TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    gender      TEXT NOT NULL,
    phone       TEXT NOT NULL,
    blood_group TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER NOT NULL,
    doctor_id   INTEGER NOT NULL,
    scheduled_on TEXT NOT NULL,
    slot        TEXT NOT NULL,
    reason      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'scheduled'
                CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id)  REFERENCES doctors (id)  ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS bills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER,
    patient_id    INTEGER NOT NULL,
    amount        REAL NOT NULL CHECK (amount >= 0),
    paid          INTEGER NOT NULL DEFAULT 0,
    issued_on     TEXT NOT NULL,
    FOREIGN KEY (appointment_id) REFERENCES appointments (id) ON DELETE SET NULL,
    FOREIGN KEY (patient_id)     REFERENCES patients (id)     ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_appt_patient ON appointments (patient_id);
CREATE INDEX IF NOT EXISTS idx_appt_doctor ON appointments (doctor_id);
CREATE INDEX IF NOT EXISTS idx_bills_patient ON bills (patient_id);
"""

SEED_DOCTORS = [
    ("DOC101", "Dr. Kavita Rao", "Cardiology", "+91-900000001"),
    ("DOC102", "Dr. Arjun Menon", "Orthopedics", "+91-900000002"),
    ("DOC103", "Dr. Sunita Verma", "Pediatrics", "+91-900000003"),
]

SEED_PATIENTS = [
    ("MRN0001", "Ramesh Kumar", "1985-04-12", "Male", "+91-911111111", "O+"),
    ("MRN0002", "Lakshmi Devi", "1992-11-03", "Female", "+91-911111112", "A+"),
    ("MRN0003", "Amit Patel", "1978-07-25", "Male", "+91-911111113", "B+"),
    ("MRN0004", "Sara Joseph", "2010-01-19", "Female", "+91-911111114", "AB+"),
]

SEED_APPOINTMENTS = [
    (1, 1, "2026-01-05", "09:00", "Chest pain follow-up", "completed"),
    (2, 1, "2026-01-05", "10:30", "Hypertension review", "completed"),
    (3, 2, "2026-01-06", "11:00", "Knee pain", "scheduled"),
    (4, 3, "2026-01-06", "12:15", "Annual check-up", "scheduled"),
    (1, 2, "2026-01-07", "09:45", "Back pain", "scheduled"),
]

SEED_BILLS = [
    (1, 1, 2500.0, 1, "2026-01-05"),
    (2, 2, 1800.0, 1, "2026-01-05"),
    (3, 3, 3200.0, 0, "2026-01-06"),
    (None, 4, 750.0, 0, "2026-01-06"),
]


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection to the hospital database, creating it when missing."""
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
    for row in SEED_DOCTORS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO doctors (license_no, full_name, specialty, phone) VALUES (?, ?, ?, ?)",
            row,
        )
        created += cur.rowcount

    for row in SEED_PATIENTS:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO patients (mrn, full_name, date_of_birth, gender, phone, blood_group)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        created += cur.rowcount

    existing = conn.execute("SELECT COUNT(*) AS n FROM appointments").fetchone()["n"]
    if existing:
        # Seed data already applied: keep re-runs idempotent.
        conn.commit()
        return created

    for patient_id, doctor_id, day, slot, reason, status in SEED_APPOINTMENTS:
        cur = conn.execute(
            """
            INSERT INTO appointments (patient_id, doctor_id, scheduled_on, slot, reason, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (patient_id, doctor_id, day, slot, reason, status),
        )
        created += cur.rowcount

    for appointment_id, patient_id, amount, paid, issued in SEED_BILLS:
        cur = conn.execute(
            """
            INSERT INTO bills (appointment_id, patient_id, amount, paid, issued_on)
            VALUES (?, ?, ?, ?, ?)
            """,
            (appointment_id, patient_id, amount, paid, issued),
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
