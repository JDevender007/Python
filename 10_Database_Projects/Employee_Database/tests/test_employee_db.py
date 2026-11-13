"""Tests for the Employee Database project."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from database import open_initialised  # noqa: E402
from queries import (  # noqa: E402
    add_department,
    add_employee,
    deactivate_employee,
    department_salary_summary,
    delete_employee,
    get_employee,
    list_departments,
    list_employees,
    payroll_cost,
    search_employees,
    top_earners,
    update_salary,
)


def test_schema_and_seed(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert len(list_departments(conn)) == 4
    assert len(list_employees(conn)) == 8
    conn.close()


def test_add_and_fetch_employee(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    new_id = add_employee(
        conn,
        employee_code="EMP777",
        full_name="Test Person",
        email="test@example.com",
        department_id=1,
        designation="Engineer",
        salary=500_000,
        joined_on="2026-02-02",
    )
    row = get_employee(conn, new_id)
    assert row is not None
    assert row["full_name"] == "Test Person"
    assert row["department_name"] == "Engineering"
    conn.close()


def test_duplicate_code_rejected(tmp_path):
    import sqlite3

    conn = open_initialised(tmp_path / "test.db")
    with pytest.raises(sqlite3.IntegrityError):
        add_employee(
            conn,
            employee_code="EMP001",  # already seeded
            full_name="Dup",
            email="dup@example.com",
            department_id=1,
            designation="X",
            salary=1,
            joined_on="2026-01-01",
        )
    conn.close()


def test_search_is_case_insensitive(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert len(search_employees(conn, "PRIYA")) == 1
    assert len(search_employees(conn, "emp003")) == 1
    assert search_employees(conn, "zzz-nothing") == []
    conn.close()


def test_salary_update_and_deactivate(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    assert update_salary(conn, 1, 999_999) is True
    assert get_employee(conn, 1)["salary"] == 999_999

    assert deactivate_employee(conn, 1) is True
    active = list_employees(conn, active_only=True)
    assert all(row["id"] != 1 for row in active)
    conn.close()


def test_reporting_queries(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    summary = department_salary_summary(conn)
    assert len(summary) == 4
    assert sum(row["head_count"] for row in summary) == 8

    earners = top_earners(conn, 3)
    assert len(earners) == 3
    assert earners[0]["salary"] >= earners[-1]["salary"]

    cost = payroll_cost(conn)
    assert cost["head_count"] == 8
    assert cost["total"] > 0
    conn.close()


def test_hard_delete(tmp_path):
    conn = open_initialised(tmp_path / "test.db")
    new_id = add_employee(
        conn,
        employee_code="EMP888",
        full_name="Temp",
        email="temp@example.com",
        department_id=2,
        designation="Temp",
        salary=1,
        joined_on="2026-01-01",
    )
    assert delete_employee(conn, new_id) is True
    assert get_employee(conn, new_id) is None
    assert delete_employee(conn, new_id) is False
    conn.close()


def test_add_department(tmp_path):
    conn = open_initialised(tmp_path / "test.db", with_seed=False)
    dept_id = add_department(conn, "Marketing", "Tower 1")
    assert dept_id == 1
    assert list_departments(conn)[0]["name"] == "Marketing"
    conn.close()
