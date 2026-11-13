"""CRUD operations and reporting queries for the Inventory Database."""

from __future__ import annotations

import sqlite3
from typing import Any


# --------------------------------------------------------------------------- #
# Suppliers
# --------------------------------------------------------------------------- #
def add_supplier(conn: sqlite3.Connection, name: str, contact: str, email: str, city: str) -> int:
    """Insert a supplier and return its id."""
    cur = conn.execute(
        "INSERT INTO suppliers (name, contact, email, city) VALUES (?, ?, ?, ?)",
        (name.strip(), contact.strip(), email.strip(), city.strip()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_suppliers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Suppliers with the number of products they provide."""
    return conn.execute(
        """
        SELECT s.id, s.name, s.contact, s.email, s.city,
               COUNT(p.id) AS products
        FROM suppliers s
        LEFT JOIN products p ON p.supplier_id = s.id
        GROUP BY s.id
        ORDER BY s.name
        """
    ).fetchall()


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #
def add_product(
    conn: sqlite3.Connection,
    *,
    sku: str,
    name: str,
    category: str,
    unit_price: float,
    supplier_id: int,
    reorder_level: int = 10,
) -> int:
    """Insert a product and return its id."""
    cur = conn.execute(
        """
        INSERT INTO products (sku, name, category, unit_price, reorder_level, supplier_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sku.strip(), name.strip(), category.strip(), float(unit_price),
         int(reorder_level), supplier_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_products(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Products with their current on-hand stock."""
    return stock_levels(conn)


def get_product(conn: sqlite3.Connection, product_id: int) -> sqlite3.Row | None:
    """Fetch one product with supplier details and stock."""
    return conn.execute(
        """
        SELECT p.*, s.name AS supplier_name,
               COALESCE(SUM(CASE WHEN m.movement = 'in' THEN m.quantity
                                 WHEN m.movement = 'out' THEN -m.quantity
                                 ELSE m.quantity END), 0) AS on_hand
        FROM products p
        JOIN suppliers s ON s.id = p.supplier_id
        LEFT JOIN stock_movements m ON m.product_id = p.id
        WHERE p.id = ?
        GROUP BY p.id
        """,
        (product_id,),
    ).fetchone()


def search_products(conn: sqlite3.Connection, term: str) -> list[sqlite3.Row]:
    """Case-insensitive search over sku, name, category and supplier."""
    like = f"%{term.strip()}%"
    return conn.execute(
        """
        SELECT p.id, p.sku, p.name, p.category, p.unit_price, s.name AS supplier_name
        FROM products p
        JOIN suppliers s ON s.id = p.supplier_id
        WHERE p.sku LIKE ? COLLATE NOCASE
           OR p.name LIKE ? COLLATE NOCASE
           OR p.category LIKE ? COLLATE NOCASE
           OR s.name LIKE ? COLLATE NOCASE
        ORDER BY p.name
        """,
        (like, like, like, like),
    ).fetchall()


def update_price(conn: sqlite3.Connection, product_id: int, unit_price: float) -> bool:
    """Update a product's unit price."""
    cur = conn.execute(
        "UPDATE products SET unit_price = ? WHERE id = ?",
        (float(unit_price), product_id),
    )
    conn.commit()
    return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# Stock movements
# --------------------------------------------------------------------------- #
def record_movement(
    conn: sqlite3.Connection,
    product_id: int,
    movement: str,
    quantity: int,
    *,
    note: str = "",
    created_on: str = "",
) -> int:
    """Record a stock movement ('in', 'out' or 'adjustment')."""
    if movement not in {"in", "out", "adjustment"}:
        raise ValueError(f"invalid movement: {movement}")
    if int(quantity) <= 0:
        raise ValueError("quantity must be positive")

    if movement == "out":
        on_hand = current_stock(conn, product_id)
        if on_hand < int(quantity):
            raise ValueError(f"insufficient stock: have {on_hand}, need {quantity}")

    cur = conn.execute(
        """
        INSERT INTO stock_movements (product_id, movement, quantity, note, created_on)
        VALUES (?, ?, ?, ?, ?)
        """,
        (product_id, movement, int(quantity), note.strip(), created_on),
    )
    conn.commit()
    return int(cur.lastrowid)


def stock_in(conn: sqlite3.Connection, product_id: int, quantity: int, **kw) -> int:
    """Record received stock."""
    return record_movement(conn, product_id, "in", quantity, **kw)


def stock_out(conn: sqlite3.Connection, product_id: int, quantity: int, **kw) -> int:
    """Record dispatched stock (validates available quantity)."""
    return record_movement(conn, product_id, "out", quantity, **kw)


def current_stock(conn: sqlite3.Connection, product_id: int) -> int:
    """Net on-hand quantity for a product."""
    row = conn.execute(
        """
        SELECT COALESCE(SUM(CASE WHEN movement = 'in' THEN quantity
                                 WHEN movement = 'out' THEN -quantity
                                 ELSE quantity END), 0) AS on_hand
        FROM stock_movements
        WHERE product_id = ?
        """,
        (product_id,),
    ).fetchone()
    return int(row["on_hand"])


def movement_history(conn: sqlite3.Connection, product_id: int) -> list[sqlite3.Row]:
    """Movement log for a single product."""
    return conn.execute(
        """
        SELECT movement, quantity, note, created_on
        FROM stock_movements
        WHERE product_id = ?
        ORDER BY created_on, id
        """,
        (product_id,),
    ).fetchall()


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def stock_levels(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every product with its on-hand quantity."""
    return conn.execute(
        """
        SELECT p.id, p.sku, p.name, p.category, p.unit_price, p.reorder_level,
               s.name AS supplier_name,
               COALESCE(SUM(CASE WHEN m.movement = 'in' THEN m.quantity
                                 WHEN m.movement = 'out' THEN -m.quantity
                                 ELSE m.quantity END), 0) AS on_hand
        FROM products p
        JOIN suppliers s ON s.id = p.supplier_id
        LEFT JOIN stock_movements m ON m.product_id = p.id
        GROUP BY p.id
        ORDER BY p.name
        """
    ).fetchall()


def low_stock_report(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Products at or below their reorder level."""
    return conn.execute(
        """
        SELECT p.id, p.sku, p.name, p.reorder_level,
               COALESCE(SUM(CASE WHEN m.movement = 'in' THEN m.quantity
                                 WHEN m.movement = 'out' THEN -m.quantity
                                 ELSE m.quantity END), 0) AS on_hand
        FROM products p
        LEFT JOIN stock_movements m ON m.product_id = p.id
        GROUP BY p.id
        HAVING on_hand <= p.reorder_level
        ORDER BY on_hand
        """
    ).fetchall()


def valuation_report(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Stock valuation per product (on_hand x unit_price)."""
    return conn.execute(
        """
        SELECT p.sku, p.name,
               COALESCE(SUM(CASE WHEN m.movement = 'in' THEN m.quantity
                                 WHEN m.movement = 'out' THEN -m.quantity
                                 ELSE m.quantity END), 0) AS on_hand,
               p.unit_price,
               COALESCE(SUM(CASE WHEN m.movement = 'in' THEN m.quantity
                                 WHEN m.movement = 'out' THEN -m.quantity
                                 ELSE m.quantity END), 0) * p.unit_price AS value
        FROM products p
        LEFT JOIN stock_movements m ON m.product_id = p.id
        GROUP BY p.id
        ORDER BY value DESC
        """
    ).fetchall()


def inventory_totals(conn: sqlite3.Connection) -> dict[str, Any]:
    """Aggregate valuation used by the demo report."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS products,
               COALESCE(SUM(value), 0) AS total_value,
               COALESCE(SUM(on_hand), 0) AS total_units
        FROM (
            SELECT p.id,
                   COALESCE(SUM(CASE WHEN m.movement = 'in' THEN m.quantity
                                     WHEN m.movement = 'out' THEN -m.quantity
                                     ELSE m.quantity END), 0) AS on_hand,
                   COALESCE(SUM(CASE WHEN m.movement = 'in' THEN m.quantity
                                     WHEN m.movement = 'out' THEN -m.quantity
                                     ELSE m.quantity END), 0) * p.unit_price AS value
            FROM products p
            LEFT JOIN stock_movements m ON m.product_id = p.id
            GROUP BY p.id
        ) AS totals
        """
    ).fetchone()
    return dict(row)


def category_summary(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Units and value grouped by category."""
    return conn.execute(
        """
        SELECT p.category,
               COUNT(DISTINCT p.id) AS products,
               COALESCE(SUM(CASE WHEN m.movement = 'in' THEN m.quantity
                                 WHEN m.movement = 'out' THEN -m.quantity
                                 ELSE m.quantity END), 0) AS units,
               COALESCE(SUM(CASE WHEN m.movement = 'in' THEN m.quantity
                                 WHEN m.movement = 'out' THEN -m.quantity
                                 ELSE m.quantity END) * p.unit_price, 0) AS value
        FROM products p
        LEFT JOIN stock_movements m ON m.product_id = p.id
        GROUP BY p.category
        ORDER BY value DESC
        """
    ).fetchall()
