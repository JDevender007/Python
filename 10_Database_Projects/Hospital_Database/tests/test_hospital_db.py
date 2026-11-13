"""Tests for the Hospital Database project."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from database import open_initialised  # noqa: E402
from queries import (  # noqa: E402
    add_doctor,
    add_patient,
    book_appointment,
    create_bill,
    discharge_patient,
    get_patient,
    list_appointments,
    list_doctors,
    pay_bill,
    revenue_report,
    revenue_totals,
    schedule_view,
    search_patients,
    set_appointment_status,
    specialty_workload,
)


def test_schema_and_seed(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert len(list_doctors(conn)) == 3
    assert len(list_appointments(conn)) == 5
    conn.close()


def test_add_patient_and_fetch(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    pid = add_patient(
        conn,
        mrn="MRN7777",
        full_name="Test Person",
        date_of_birth="1995-05-05",
        gender="Female",
        phone="+91-900",
        blood_group="A-",
    )
    row = get_patient(conn, pid)
    assert row is not None
    assert row["full_name"] == "Test Person"
    assert row["balance_due"] == 0
    conn.close()


def test_duplicate_mrn_rejected(tmp_path):
    import sqlite3

    conn = open_initialised(tmp_path / "test.db")
    with pytest.raises(sqlite3.IntegrityError):
        add_patient(
            conn,
            mrn="MRN0001",
            full_name="Dup",
            date_of_birth="1990-01-01",
            gender="Male",
            phone="1",
        )
    conn.close()


def test_booking_and_discharge(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    appt = book_appointment(
        conn, patient_id=1, doctor_id=1, scheduled_on="2026-02-01", slot="08:00", reason="Demo"
    )
    assert discharge_patient(conn, appt) is True
    rows = list_appointments(conn, day="2026-02-01")
    assert rows[0]["status"] == "completed"
    conn.close()


def test_invalid_status_rejected(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    with pytest.raises(ValueError):
        set_appointment_status(conn, 1, "bogus")
    conn.close()


def test_billing_flow(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    bill = create_bill(conn, patient_id=1, amount=500.0, issued_on="2026-02-02")
    assert pay_bill(conn, bill) is True

    row = get_patient(conn, 1)
    assert row["balance_due"] == 0

    totals = revenue_totals(conn)
    assert totals["bills"] == 5
    assert totals["collected"] > 0
    conn.close()


def test_search_case_insensitive(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert len(search_patients(conn, "ramesh")) == 1
    assert len(search_patients(conn, "MRN0004")) == 1
    assert search_patients(conn, "nope") == []
    conn.close()


def test_schedule_and_workload(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert len(schedule_view(conn, "2026-01-06")) == 2
    workload = specialty_workload(conn)
    assert len(workload) == 3
    assert sum(r["appointments"] for r in workload) == 5
    conn.close()


def test_revenue_report_days(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    days = revenue_report(conn)
    assert {d["day"] for d in days} == {"2026-01-05", "2026-01-06"}
    conn.close()


def test_add_doctor(tmp_path):
    conn = open_initialised(tmp_path / "test.db", with_seed=False)
    doc_id = add_doctor(conn, "DOC999", "Dr. Test", "Dermatology", "+91-1")
    assert doc_id == 1
    assert list_doctors(conn)[0]["specialty"] == "Dermatology"
    conn.close()
