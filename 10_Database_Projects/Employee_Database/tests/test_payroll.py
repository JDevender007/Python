"""Tests for the payroll lab: aggregate semantics and integer-paise money."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import main as cli  # noqa: E402
import payroll  # noqa: E402
from payroll import (  # noqa: E402
    Employee,
    PayrollError,
    audit,
    average_of_averages_paise,
    build_database,
    department_head_counts,
    department_summary,
    divide_half_up,
    format_money,
    is_iso_date,
    legacy_count_star,
    legacy_inner_filter,
    load_departments,
    load_employees,
    measure,
    overall_average_paise,
    parse_money,
    payroll as payroll_figures,
    report,
    require_iso_date,
    run_demo,
)


# --------------------------------------------------------------------------- #
# money
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,paise",
    [
        ("720000.00", 72_000_000),
        ("1150000.00", 115_000_000),
        ("0.05", 5),
        ("8.20", 820),
        ("7", 700),
        ("7.5", 750),
        ("+1.00", 100),
        ("-1.05", -105),
        (" 12.30 ", 1230),
    ],
)
def test_parse_money_is_exact(text, paise):
    assert parse_money(text) == paise


@pytest.mark.parametrize("bad", ["", "  ", "1.2.3", "1.234", "abc", "1.a5", ".", "1,"])
def test_parse_money_refuses_malformed(bad):
    with pytest.raises(PayrollError):
        parse_money(bad)


def test_parse_money_refuses_non_text():
    with pytest.raises(PayrollError, match="must be text"):
        parse_money(720000)


def test_parse_money_names_the_decimal_places():
    with pytest.raises(PayrollError, match="2 decimal places"):
        parse_money("1.234")


@pytest.mark.parametrize(
    "paise,text",
    [(0, "0.00"), (5, "0.05"), (99, "0.99"), (100, "1.00"), (-105, "-1.05"), (83_666_667, "836666.67")],
)
def test_format_money(paise, text):
    assert format_money(paise) == text


@pytest.mark.parametrize("bad", [True, 1.5, "10"])
def test_format_money_refuses_non_integers(bad):
    with pytest.raises(PayrollError, match="must be an integer"):
        format_money(bad)


@pytest.mark.parametrize(
    "top,bottom,expected",
    [(251_000_000, 3, 83_666_667), (198_000_000, 2, 99_000_000), (5, 2, 3), (1, 3, 0), (-5, 2, -3)],
)
def test_divide_half_up(top, bottom, expected):
    assert divide_half_up(top, bottom) == expected


@pytest.mark.parametrize("bottom", [0, -1])
def test_divide_half_up_refuses_bad_denominators(bottom):
    with pytest.raises(PayrollError, match="denominator must be positive"):
        divide_half_up(1, bottom)


# --------------------------------------------------------------------------- #
# dates
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", ["2021-06-14", "2018-02-05", "2026-01-01", "1999-12-31"])
def test_iso_dates_are_accepted(text):
    assert is_iso_date(text) is True


@pytest.mark.parametrize("text", ["2021-6-14", "2021-06-32", "2021-13-01", "14/06/2021", "", "2021-06-1x"])
def test_iso_dates_are_refused(text):
    assert is_iso_date(text) is False


def test_require_iso_date_names_the_offender():
    with pytest.raises(PayrollError, match="joined_on must be YYYY-MM-DD"):
        require_iso_date("14/06/2021")


# --------------------------------------------------------------------------- #
# loaders
# --------------------------------------------------------------------------- #
def test_load_departments_from_bundled_seed():
    departments = load_departments()
    assert [d.name for d in departments] == [
        "Engineering",
        "Finance",
        "Human Resources",
        "Sales",
        "Research",
    ]
    assert departments[0].location == "Building A"


def test_load_employees_from_bundled_seed():
    employees = load_employees()
    assert len(employees) == 8
    assert employees[0].code == "EMP001"
    assert employees[0].paise == 72_000_000
    assert employees[6].active == 0


def test_loader_reports_a_missing_file(tmp_path):
    with pytest.raises(PayrollError, match="file not found"):
        load_employees(tmp_path / "nope.csv")


def test_loader_reports_a_missing_column(tmp_path):
    path = tmp_path / "departments.csv"
    path.write_text("id,name\n1,Engineering\n", encoding="utf-8")
    with pytest.raises(PayrollError, match="missing column"):
        load_departments(path)


def test_loader_refuses_duplicate_department_names(tmp_path):
    path = tmp_path / "departments.csv"
    path.write_text("id,name,location\n1,A,X\n2,A,Y\n", encoding="utf-8")
    with pytest.raises(PayrollError, match="department names must be unique"):
        load_departments(path)


EMPLOYEE_HEADER = (
    "id,employee_code,full_name,email,department_id,designation,salary,joined_on,is_active\n"
)


def test_loader_refuses_duplicate_employee_codes(tmp_path):
    path = tmp_path / "employees.csv"
    path.write_text(
        EMPLOYEE_HEADER
        + "1,EMP001,A,a@x,1,Dev,1.00,2026-01-01,1\n"
        + "2,EMP001,B,b@x,1,Dev,1.00,2026-01-02,1\n",
        encoding="utf-8",
    )
    with pytest.raises(PayrollError, match="employee codes must be unique"):
        load_employees(path)


def test_loader_refuses_a_bad_active_flag(tmp_path):
    path = tmp_path / "employees.csv"
    path.write_text(
        EMPLOYEE_HEADER + "1,EMP001,A,a@x,1,Dev,1.00,2026-01-01,yes\n", encoding="utf-8"
    )
    with pytest.raises(PayrollError, match="must be 0 or 1"):
        load_employees(path)


def test_loader_refuses_a_bad_joined_on(tmp_path):
    path = tmp_path / "employees.csv"
    path.write_text(
        EMPLOYEE_HEADER + "1,EMP001,A,a@x,1,Dev,1.00,01/01/2026,1\n", encoding="utf-8"
    )
    with pytest.raises(PayrollError, match="YYYY-MM-DD"):
        load_employees(path)


# --------------------------------------------------------------------------- #
# database and reports
# --------------------------------------------------------------------------- #
@pytest.fixture()
def seeded():
    departments = load_departments()
    employees = load_employees()
    conn = build_database(departments, employees)
    yield conn, departments, employees
    conn.close()


def test_build_database_rows(seeded):
    conn, _, _ = seeded
    assert conn.execute("SELECT COUNT(*) AS n FROM departments").fetchone()["n"] == 5
    assert conn.execute("SELECT COUNT(*) AS n FROM employees").fetchone()["n"] == 8


def test_build_database_refuses_unknown_department():
    departments = load_departments()
    employees = [Employee(1, "EMP999", "Ghost", "g@x", 99, "Dev", 100, "2026-01-01", 1)]
    with pytest.raises(PayrollError, match="unknown department 99"):
        build_database(departments, employees)


def test_correct_head_counts(seeded):
    conn, _, _ = seeded
    assert department_head_counts(conn) == {
        "Engineering": 3,
        "Finance": 2,
        "Human Resources": 1,
        "Research": 0,
        "Sales": 0,
    }


def test_legacy_count_star_counts_phantom_rows(seeded):
    conn, _, _ = seeded
    heads = legacy_count_star(conn)
    assert heads == {
        "Engineering": 3,
        "Finance": 2,
        "Human Resources": 1,
        "Research": 1,
        "Sales": 1,
    }
    assert sum(heads.values()) == 8


def test_legacy_inner_filter_drops_empty_departments(seeded):
    conn, _, _ = seeded
    assert legacy_inner_filter(conn) == {
        "Engineering": 3,
        "Finance": 2,
        "Human Resources": 1,
    }


def test_department_summary_values(seeded):
    conn, _, _ = seeded
    summary = {row[0]: row for row in department_summary(conn)}
    assert summary["Engineering"] == ("Engineering", 3, 251_000_000, 83_666_667)
    assert summary["Finance"] == ("Finance", 2, 198_000_000, 99_000_000)
    assert summary["Human Resources"] == ("Human Resources", 1, 49_000_000, 49_000_000)
    assert summary["Research"] == ("Research", 0, 0, 0)
    assert summary["Sales"] == ("Sales", 0, 0, 0)


def test_department_summary_is_sorted_by_name(seeded):
    conn, _, _ = seeded
    names = [row[0] for row in department_summary(conn)]
    assert names == sorted(names)


def test_overall_average_divides_total_by_head(seeded):
    conn, _, _ = seeded
    assert overall_average_paise(department_summary(conn)) == 83_000_000


def test_average_of_averages_is_different(seeded):
    conn, _, _ = seeded
    summary = department_summary(conn)
    assert average_of_averages_paise(summary) == 77_222_222
    assert overall_average_paise(summary) - average_of_averages_paise(summary) == 5_777_778


def test_overall_average_refuses_an_empty_summary():
    with pytest.raises(PayrollError, match="summary must not be empty"):
        overall_average_paise([])


def test_overall_average_is_zero_when_nobody_is_active():
    assert overall_average_paise([("Empty", 0, 0, 0)]) == 0


def test_payroll_figures(seeded):
    conn, _, _ = seeded
    figures = payroll_figures(conn)
    assert figures["head"] == 6
    assert figures["total"] == 498_000_000
    assert figures["average"] == 83_000_000
    assert figures["lowest"] == 49_000_000
    assert figures["highest"] == 140_000_000


def test_inactive_staff_are_excluded_from_payroll(seeded):
    conn, _, employees = seeded
    active_total = sum(e.paise for e in employees if e.active == 1)
    assert payroll_figures(conn)["total"] == active_total


# --------------------------------------------------------------------------- #
# measure and report
# --------------------------------------------------------------------------- #
def test_measure_pins_the_gap():
    measured = measure()
    assert measured["overall"] == 83_000_000
    assert measured["average_of_averages"] == 77_222_222
    assert measured["payroll"]["total"] == 498_000_000


def test_measure_keeps_the_three_head_counts():
    measured = measure()
    assert sum(measured["correct_heads"].values()) == 6
    assert sum(measured["legacy_heads"].values()) == 8
    assert len(measured["inner_heads"]) == 3


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "conn" not in text
    assert payload["overall_average_paise"] == 83_000_000
    assert payload["gap_paise"] == 5_777_778
    assert payload["rows"][0]["department"] == "Engineering"


def test_measure_reads_siblings_from_the_employees_folder(tmp_path):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "departments.csv").write_text("id,name,location\n1,Only,X\n", encoding="utf-8")
    (folder / "employees.csv").write_text(
        EMPLOYEE_HEADER + "1,EMP001,A,a@x,1,Dev,10.00,2026-01-01,1\n", encoding="utf-8"
    )
    measured = measure(folder / "employees.csv")
    assert len(measured["departments"]) == 1
    assert measured["payroll"]["total"] == 1000


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_audit_passes_every_check():
    results = audit(measure())
    assert len(results) >= 12
    assert all(ok for _, ok in results)


def test_audit_names_are_unique():
    names = [name for name, _ in audit(measure())]
    assert len(names) == len(set(names))


def test_audit_negative_control_legacy_reader_flips_the_head_total():
    results = dict(audit(measure(), read_heads=legacy_count_star))
    assert results["correct_head_total_is_active_count"] is False
    assert results["phantom_rows_are_the_empty_departments"] is False


def test_audit_negative_control_reader_returning_zero():
    def broken(conn):
        return {}

    results = dict(audit(measure(), read_heads=broken))
    assert results["correct_head_total_is_active_count"] is False


def test_audit_detects_a_tampered_average():
    measured = measure()
    measured["overall"] = 1
    results = dict(audit(measured))
    assert results["overall_average_is_total_over_head"] is False


# --------------------------------------------------------------------------- #
# demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_returns_zero_and_ends_with_the_contract(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    second = capsys.readouterr().out
    assert first == second


def test_demo_reports_the_pinned_numbers(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "830000.00" in out
    assert "772222.22" in out
    assert "57777.78" in out
    assert "836666.67" in out


def test_cli_demo_exits_zero():
    assert cli.main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_json_writes_a_report(tmp_path):
    target = tmp_path / "report.json"
    assert cli.main(["--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["overall_average_paise"] == 83_000_000


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such.csv"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_bad_money_exits_two(tmp_path, capsys):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "departments.csv").write_text("id,name,location\n1,Only,X\n", encoding="utf-8")
    (folder / "employees.csv").write_text(
        EMPLOYEE_HEADER + "1,EMP001,A,a@x,1,Dev,1.234,2026-01-01,1\n", encoding="utf-8"
    )
    assert cli.main(["--file", str(folder / "employees.csv")]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_quiet_json_still_writes(tmp_path):
    target = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(target)]) == 0
    assert target.is_file()


def test_module_demo_entry_point():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        assert payroll.run_demo() == 0
    assert buffer.getvalue().strip().endswith("Demo completed successfully.")


def test_demo_writes_nothing_to_stderr():
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        run_demo()
    assert err.getvalue() == ""
