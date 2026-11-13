"""Tests for the Attendance Management project."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from database import open_initialised  # noqa: E402
from queries import (  # noqa: E402
    add_person,
    clear_day,
    csv_to_text,
    day_sheet,
    defaulters_report,
    export_csv,
    import_csv,
    list_people,
    mark_attendance,
    mark_by_code,
    monthly_report,
    search_people,
    status_summary,
)


def test_schema_and_seed(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert len(list_people(conn)) == 6
    assert status_summary(conn)["total"] == 18
    conn.close()


def test_mark_and_read_day_sheet(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    sheet = day_sheet(conn, "2026-01-05")
    assert len(sheet) == 6
    assert all("status" in r.keys() for r in sheet)
    # everyone is marked on the seeded day
    assert all(r["status"] != "unmarked" for r in sheet)
    conn.close()


def test_mark_by_code_and_validation(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert mark_by_code(conn, "STU001", "2026-01-08", "present") in {"inserted", "updated"}

    with pytest.raises(ValueError, match="invalid status"):
        mark_by_code(conn, "STU001", "2026-01-08", "napping")
    with pytest.raises(ValueError, match="unknown code"):
        mark_by_code(conn, "NOPE", "2026-01-08", "present")
    conn.close()


def test_upsert_does_not_duplicate(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    pid = conn.execute("SELECT id FROM people WHERE code = 'STU001'").fetchone()["id"]

    mark_attendance(conn, pid, "2026-01-05", "absent", "changed")
    sheet = day_sheet(conn, "2026-01-05")
    row = next(r for r in sheet if r["code"] == "STU001")
    assert row["status"] == "absent"
    assert row["note"] == "changed"
    assert status_summary(conn)["total"] == 18  # unchanged count
    conn.close()


def test_monthly_report_percentages(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    report = monthly_report(conn, "2026-01")
    assert len(report) == 6
    for row in report:
        assert row["days_marked"] == 3
        assert 0 <= row["attendance_pct"] <= 100
        assert row["present"] + row["late"] + row["absent"] + row["leave_days"] == 3
    conn.close()


def test_defaulters_threshold(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    # STU003: absent, present, present => 2/3 = 66.7% -> defaulter
    defaulters = defaulters_report(conn, "2026-01", 75.0)
    codes = {r["code"] for r in defaulters}
    assert "STU003" in codes
    for row in defaulters:
        assert row["attendance_pct"] < 75.0
    assert defaulters_report(conn, "2026-01", 0.0) == []
    conn.close()


def test_clear_day(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert clear_day(conn, "2026-01-05") == 6
    assert status_summary(conn, "2026-01-05")["total"] == 0
    assert clear_day(conn, "2026-01-05") == 0
    conn.close()


def test_search_people(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert len(search_people(conn, "batch a")) == 3
    assert len(search_people(conn, "STU006")) == 1
    assert search_people(conn, "zzz") == []
    conn.close()


def test_csv_export_roundtrip(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    target = tmp_path / "export.csv"
    export_csv(conn, target, month="2026-01")

    with target.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 18
    assert {"code", "full_name", "group_name", "day", "status", "note"} <= set(rows[0])

    # importing the same file must not duplicate anything
    assert import_csv(conn, target) == 18
    assert status_summary(conn)["total"] == 18
    conn.close()


def test_import_missing_file(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    with pytest.raises(FileNotFoundError):
        import_csv(conn, tmp_path / "nope.csv")
    conn.close()


def test_csv_to_text(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    text = csv_to_text(list_people(conn))
    assert text.splitlines()[0] == "id,code,full_name,group_name,days_marked"
    assert len(text.splitlines()) == 7
    conn.close()


def test_add_person(tmp_path):
    conn = open_initialised(tmp_path / "test.db", with_seed=False)
    pid = add_person(conn, "STU001", "Fresh Person", "Batch Z")
    assert pid == 1
    assert list_people(conn)[0]["group_name"] == "Batch Z"
    conn.close()
