"""Tests for the CRM System project."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from database import open_initialised  # noqa: E402
from queries import (  # noqa: E402
    add_customer,
    add_deal,
    add_lead,
    convert_lead,
    follow_ups,
    get_customer,
    interaction_history,
    kpi_summary,
    lead_funnel,
    list_customers,
    list_leads,
    log_interaction,
    move_deal,
    pipeline_summary,
    search_customers,
    top_customers,
    update_lead_status,
)


def test_schema_and_seed(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert len(list_customers(conn)) == 3
    assert len(list_leads(conn)) == 4
    conn.close()


def test_add_customer_and_search(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    cid = add_customer(conn, name="Test User", email="t@example.com", phone="+91-1", company="TestCo")
    assert get_customer(conn, cid)["name"] == "Test User"
    assert len(search_customers(conn, "testco")) == 1
    assert search_customers(conn, "zzz") == []
    conn.close()


def test_duplicate_email_rejected(tmp_path):
    import sqlite3

    conn = open_initialised(tmp_path / "test.db")
    with pytest.raises(sqlite3.IntegrityError):
        add_customer(conn, name="Dup", email="neha@example.com", phone="1")
    conn.close()


def test_lead_status_validation(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert update_lead_status(conn, 1, "contacted") is True
    with pytest.raises(ValueError, match="invalid status"):
        update_lead_status(conn, 1, "bogus")
    conn.close()


def test_lead_conversion(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    # lead 3 is 'qualified'
    customer_id = convert_lead(conn, 3, phone="+91-999", company="Converted Co")
    assert customer_id is not None

    lead = next(r for r in list_leads(conn) if r["id"] == 3)
    assert lead["status"] == "converted"

    customer = get_customer(conn, customer_id)
    assert customer["email"] == "rahul@leads.example"
    assert convert_lead(conn, 9999, phone="1") is None
    conn.close()


def test_invalid_status_on_convert(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    lead_id = add_lead(conn, name="X", email="x@leads.example")
    update_lead_status(conn, lead_id, "lost")
    # converting a lost lead is still allowed mechanically, but statuses are validated
    with pytest.raises(ValueError):
        update_lead_status(conn, lead_id, "zombie")
    conn.close()


def test_interactions(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    log_interaction(conn, 1, "call", "Follow-up call", "2026-02-01")
    history = interaction_history(conn, 1)
    assert len(history) == 3
    assert history[0]["created_on"] == "2026-02-01"

    with pytest.raises(ValueError, match="invalid interaction kind"):
        log_interaction(conn, 1, "fax", "nope")
    conn.close()


def test_pipeline_summary(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    summary = pipeline_summary(conn)
    stages = {r["stage"] for r in summary}
    assert stages == {"proposal", "negotiation", "won"}
    assert sum(r["deals"] for r in summary) == 3

    assert move_deal(conn, 1, "won") is True
    with pytest.raises(ValueError):
        move_deal(conn, 1, "daydreaming")
    conn.close()


def test_follow_ups_horizon(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    # nothing closes within 7 days (seeded close dates are in 2026 but
    # relative to today's date they may be past -> use a huge horizon)
    far = follow_ups(conn, days=365 * 100)
    assert len(far) >= 2  # proposal + negotiation, not won/lost
    assert all(r["stage"] not in {"won", "lost"} for r in far)
    conn.close()


def test_lead_funnel_and_kpis(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    funnel = lead_funnel(conn)
    assert sum(r["leads"] for r in funnel) == 4

    kpis = kpi_summary(conn)
    assert kpis["customers"] == 3
    assert kpis["leads"] == 4
    assert kpis["won_value"] == 42000.0
    assert kpis["open_pipeline"] == 335000.0
    conn.close()


def test_top_customers(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    top = top_customers(conn)
    assert top[0]["name"] == "Neha Gupta"
    values = [r["total_value"] for r in top]
    assert values == sorted(values, reverse=True)
    conn.close()


def test_get_customer_pipeline(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    row = get_customer(conn, 1)
    assert row["open_pipeline"] == 240000.0
    assert row["won_value"] == 0
    conn.close()
