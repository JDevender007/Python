"""Database engine, schema and sample data for the Employee Database project.

The module is deliberately free of any CLI concerns so it can be reused by the
queries layer, the demo runner and the test suite.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "employees.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS departments (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL DEFAULT 'Head Office'
);

CREATE TABLE IF NOT EXISTS employees (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL,
    department_id INTEGER NOT NULL,
    designation   TEXT NOT NULL,
    salary        REAL NOT NULL CHECK (salary >= 0),
    joined_on     TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_employees_department ON employees (department_id);
CREATE INDEX IF NOT EXISTS idx_employees_name ON employees (full_name);
"""

SEED_DEPARTMENTS: list[tuple[str, str]] = [
    ("Engineering", "Building A"),
    ("Finance", "Building B"),
    ("Human Resources", "Building B"),
    ("Sales", "Building C"),
]

SEED_EMPLOYEES: list[tuple[str, str, str, int, str, float, str]] = [
    ("EMP001", "Aarav Sharma", "aarav.sharma@example.com", 1, "Software Engineer", 720_000, "2021-06-14"),
    ("EMP002", "Priya Nair", "priya.nair@example.com", 1, "Senior Engineer", 1_150_000, "2018-02-05"),
    ("EMP003", "Rohan Das", "rohan.das@example.com", 1, "QA Engineer", 640_000, "2022-09-01"),
    ("EMP004", "Sneha Iyer", "sneha.iyer@example.com", 2, "Accountant", 580_000, "2020-03-17"),
    ("EMP005", "Vikram Rao", "vikram.rao@example.com", 2, "Finance Manager", 1_400_000, "2016-11-23"),
    ("EMP006", "Ananya Menon", "ananya.menon@example.com", 3, "HR Executive", 490_000, "2023-01-09"),
    ("EMP007", "Karan Malhotra", "karan.malhotra@example.com", 4, "Sales Executive", 450_000, "2022-05-30"),
    ("EMP008", "Meera Pillai", "meera.pillai@example.com", 4, "Regional Sales Head", 1_250_000, "2017-08-12"),
]


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection to the employee database, creating it when missing."""
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
    for name, location in SEED_DEPARTMENTS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO departments (name, location) VALUES (?, ?)",
            (name, location),
        )
        created += cur.rowcount

    for code, name, email, dept, designation, salary, joined in SEED_EMPLOYEES:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO employees
                (employee_code, full_name, email, department_id, designation, salary, joined_on)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (code, name, email, dept, designation, salary, joined),
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
