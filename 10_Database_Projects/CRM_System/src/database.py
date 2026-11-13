"""Database engine, schema and sample data for the CRM System project."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "crm.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    phone      TEXT NOT NULL,
    company    TEXT NOT NULL DEFAULT '',
    created_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    source      TEXT NOT NULL DEFAULT 'inbound',
    status      TEXT NOT NULL DEFAULT 'new'
                CHECK (status IN ('new', 'contacted', 'qualified', 'converted', 'lost')),
    score       INTEGER NOT NULL DEFAULT 0,
    created_on  TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS interactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('call', 'email', 'meeting', 'note')),
    summary     TEXT NOT NULL,
    created_on  TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    title       TEXT NOT NULL,
    value       REAL NOT NULL CHECK (value >= 0),
    stage       TEXT NOT NULL DEFAULT 'prospecting'
                CHECK (stage IN ('prospecting', 'proposal', 'negotiation', 'won', 'lost')),
    close_on    TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads (status);
CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals (stage);
CREATE INDEX IF NOT EXISTS idx_interactions_customer ON interactions (customer_id);
"""

SEED_CUSTOMERS = [
    ("Neha Gupta", "neha@example.com", "+91-700000001", "Bright Labs", "2025-11-02"),
    ("Sanjay Rao", "sanjay@example.com", "+91-700000002", "Prime Retail", "2025-12-14"),
    ("Fatima Khan", "fatima@example.com", "+91-700000003", "City Foods", "2026-01-05"),
]

SEED_LEADS = [
    (None, "Omkar Patil", "omkar@leads.example", "website", "new", 40, "2026-01-10"),
    (None, "Divya Menon", "divya@leads.example", "referral", "contacted", 60, "2026-01-11"),
    (None, "Rahul Shah", "rahul@leads.example", "campaign", "qualified", 85, "2026-01-12"),
    (None, "Ishita Roy", "ishita@leads.example", "website", "lost", 20, "2026-01-13"),
]

SEED_INTERACTIONS = [
    (1, "call", "Introduced premium plan", "2026-01-08"),
    (1, "email", "Sent pricing deck", "2026-01-09"),
    (2, "meeting", "On-site product demo", "2026-01-10"),
    (3, "note", "Asked about bulk discount", "2026-01-11"),
]

SEED_DEALS = [
    (1, "Bright Labs annual license", 240000.0, "proposal", "2026-03-31"),
    (2, "Prime Retail pilot", 95000.0, "negotiation", "2026-02-28"),
    (3, "City Foods starter pack", 42000.0, "won", "2026-01-20"),
]


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection to the CRM database, creating it when missing."""
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
    for row in SEED_CUSTOMERS:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO customers (name, email, phone, company, created_on)
            VALUES (?, ?, ?, ?, ?)
            """,
            row,
        )
        created += cur.rowcount

    existing = conn.execute("SELECT COUNT(*) AS n FROM leads").fetchone()["n"]
    if existing:
        # Seed data already applied: keep re-runs idempotent.
        conn.commit()
        return created

    for customer_id, name, email, source, status, score, created_on in SEED_LEADS:
        cur = conn.execute(
            """
            INSERT INTO leads (customer_id, name, email, source, status, score, created_on)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (customer_id, name, email, source, status, score, created_on),
        )
        created += cur.rowcount

    for row in SEED_INTERACTIONS:
        cur = conn.execute(
            """
            INSERT INTO interactions (customer_id, kind, summary, created_on)
            VALUES (?, ?, ?, ?)
            """,
            row,
        )
        created += cur.rowcount

    for row in SEED_DEALS:
        cur = conn.execute(
            """
            INSERT INTO deals (customer_id, title, value, stage, close_on)
            VALUES (?, ?, ?, ?, ?)
            """,
            row,
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
