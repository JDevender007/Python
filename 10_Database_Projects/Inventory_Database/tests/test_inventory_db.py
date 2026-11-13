"""Tests for the Inventory Database project."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from database import open_initialised  # noqa: E402
from queries import (  # noqa: E402
    add_product,
    add_supplier,
    category_summary,
    current_stock,
    get_product,
    inventory_totals,
    list_products,
    list_suppliers,
    low_stock_report,
    movement_history,
    record_movement,
    search_products,
    stock_in,
    stock_out,
    update_price,
    valuation_report,
)


def test_schema_and_seed(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert len(list_suppliers(conn)) == 3
    assert len(list_products(conn)) == 6
    conn.close()


def test_stock_increases_and_decreases(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    # product 1: +60 in, -18 out => 42
    assert current_stock(conn, 1) == 42
    stock_in(conn, 1, 10, created_on="2026-02-01")
    assert current_stock(conn, 1) == 52
    stock_out(conn, 1, 2, created_on="2026-02-02")
    assert current_stock(conn, 1) == 50
    conn.close()


def test_insufficient_stock_blocked(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    with pytest.raises(ValueError, match="insufficient stock"):
        stock_out(conn, 6, 99999)
    conn.close()


def test_invalid_movement_rejected(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    with pytest.raises(ValueError):
        record_movement(conn, 1, "sideways", 5)
    with pytest.raises(ValueError):
        record_movement(conn, 1, "in", 0)
    conn.close()


def test_low_stock_report(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    # product 6: 12 in, 7 out => 5, reorder level 5 -> flagged
    flagged = low_stock_report(conn)
    ids = {row["id"] for row in flagged}
    assert 6 in ids
    for row in flagged:
        assert row["on_hand"] <= row["reorder_level"]
    conn.close()


def test_valuation_totals(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    report = valuation_report(conn)
    assert len(report) == 6
    totals = inventory_totals(conn)
    assert totals["products"] == 6
    assert totals["total_value"] > 0
    # value column must equal on_hand * unit_price per row
    for row in report:
        assert row["value"] == pytest.approx(row["on_hand"] * row["unit_price"])
    conn.close()


def test_add_product_and_supplier(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    sid = add_supplier(conn, "New Supplier", "+91-1", "n@e.example", "Kolkata")
    pid = add_product(
        conn, sku="SKU0001", name="Widget", category="Test",
        unit_price=10.0, supplier_id=sid, reorder_level=3,
    )
    row = get_product(conn, pid)
    assert row["supplier_name"] == "New Supplier"
    assert row["on_hand"] == 0
    conn.close()


def test_duplicate_sku_rejected(tmp_path):
    import sqlite3

    conn = open_initialised(tmp_path / "test.db")
    with pytest.raises(sqlite3.IntegrityError):
        add_product(
            conn, sku="SKU1001", name="Dup", category="X",
            unit_price=1.0, supplier_id=1,
        )
    conn.close()


def test_search_and_price_update(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert len(search_products(conn, "chair")) == 1
    assert len(search_products(conn, "acme")) == 2
    assert search_products(conn, "nothing-here") == []

    assert update_price(conn, 1, 599.0) is True
    assert get_product(conn, 1)["unit_price"] == 599.0
    conn.close()


def test_movement_history(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    stock_in(conn, 3, 5, note="top-up", created_on="2026-03-01")
    history = movement_history(conn, 3)
    # seeded with 1 'in' + 1 'out' movement, plus the new top-up
    assert len(history) == 3
    assert history[-1]["note"] == "top-up"
    conn.close()


def test_category_summary(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    summary = category_summary(conn)
    categories = {row["category"] for row in summary}
    assert categories == {"Electronics", "Accessories", "Stationery", "Furniture"}
    conn.close()
