"""Database engine, schema and sample data for the Inventory Database project."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "inventory.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS suppliers (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    contact  TEXT NOT NULL,
    email    TEXT NOT NULL,
    city     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sku           TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    unit_price    REAL NOT NULL CHECK (unit_price >= 0),
    reorder_level INTEGER NOT NULL DEFAULT 10,
    supplier_id   INTEGER NOT NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    movement   TEXT NOT NULL CHECK (movement IN ('in', 'out', 'adjustment')),
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    note       TEXT NOT NULL DEFAULT '',
    created_on TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stock_product ON stock_movements (product_id);
"""

SEED_SUPPLIERS = [
    ("Acme Traders", "+91-800000001", "sales@acme.example", "Mumbai"),
    ("Global Wholesale", "+91-800000002", "hello@global.example", "Delhi"),
    ("Coastal Distributors", "+91-800000003", "info@coastal.example", "Chennai"),
]

SEED_PRODUCTS = [
    ("SKU1001", "Wireless Mouse", "Electronics", 499.0, 20, 1),
    ("SKU1002", "Mechanical Keyboard", "Electronics", 2499.0, 10, 1),
    ("SKU1003", "USB-C Cable 1m", "Accessories", 199.0, 50, 2),
    ("SKU1004", "Notebook A5", "Stationery", 79.0, 100, 3),
    ("SKU1005", "Desk Lamp LED", "Furniture", 899.0, 15, 3),
    ("SKU1006", "Office Chair", "Furniture", 6499.0, 5, 2),
]

# (product_id, movement, quantity, note, created_on)
SEED_MOVEMENTS = [
    (1, "in", 60, "Opening stock", "2026-01-02"),
    (2, "in", 25, "Opening stock", "2026-01-02"),
    (3, "in", 200, "Opening stock", "2026-01-02"),
    (4, "in", 300, "Opening stock", "2026-01-02"),
    (5, "in", 40, "Opening stock", "2026-01-02"),
    (6, "in", 12, "Opening stock", "2026-01-02"),
    (1, "out", 18, "Order #4501", "2026-01-08"),
    (3, "out", 75, "Order #4502", "2026-01-09"),
    (4, "out", 120, "Order #4503", "2026-01-10"),
    (2, "out", 16, "Order #4504", "2026-01-11"),
    (6, "out", 7, "Order #4505", "2026-01-12"),
]


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection to the inventory database, creating it when missing."""
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
    for row in SEED_SUPPLIERS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO suppliers (name, contact, email, city) VALUES (?, ?, ?, ?)",
            row,
        )
        created += cur.rowcount

    for row in SEED_PRODUCTS:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO products
                (sku, name, category, unit_price, reorder_level, supplier_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        created += cur.rowcount

    existing = conn.execute("SELECT COUNT(*) AS n FROM stock_movements").fetchone()["n"]
    if existing:
        # Seed data already applied: keep re-runs idempotent.
        conn.commit()
        return created

    for product_id, movement, qty, note, day in SEED_MOVEMENTS:
        cur = conn.execute(
            """
            INSERT INTO stock_movements (product_id, movement, quantity, note, created_on)
            VALUES (?, ?, ?, ?, ?)
            """,
            (product_id, movement, qty, note, day),
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
