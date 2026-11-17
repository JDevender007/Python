"""An aggregate counts rows, not people -- and the join decides the rows.

Three reporting queries in the legacy HR system each look reasonable and each
returns a different, wrong head count:

1. **`COUNT(*)` after a LEFT JOIN counts the phantom row.** A department with
   no active employees still produces one row, because the outer join guarantees
   the department appears. `COUNT(*)` reports 1; `COUNT(e.id)` reports 0. Only
   the second one means "people".

2. **A filter in `WHERE` turns a LEFT JOIN into an inner join.** Moving
   `e.is_active = 1` from the `ON` clause to the `WHERE` clause silently deletes
   every department that has no active staff. The report gets shorter and nobody
   notices, because a shorter report is not an error.

3. **An average of averages is not the average.** Department averages are not
   equally weighted when departments differ in size, so averaging them reports
   830000.00 as 772222.22 -- a 57777.78 gap on a six-person payroll.

Salaries are money, so they are integer paise parsed from text, and every
division goes through `divide_half_up` instead of `round()` or `AVG()`.

The three defective queries and the defective averaging are kept as executable
objects and run beside the corrected ones on the same seed files.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEPARTMENTS_FILE = DATA_DIR / "departments.csv"
EMPLOYEES_FILE = DATA_DIR / "employees.csv"

# The three defective reports, kept as strings so the demo can print them and
# the tests can execute them on the same database as the corrected versions.
LEGACY_COUNT_STAR = """
SELECT d.name AS name, COUNT(*) AS head
FROM departments d
LEFT JOIN employees e ON e.department_id = d.id AND e.is_active = 1
GROUP BY d.id
ORDER BY d.name
"""

LEGACY_INNER_FILTER = """
SELECT d.name AS name, COUNT(e.id) AS head
FROM departments d
LEFT JOIN employees e ON e.department_id = d.id
WHERE e.is_active = 1
GROUP BY d.id
ORDER BY d.name
"""

LEGACY_AVERAGE_OF_AVERAGES = "overall = sum(department AVG) / count(departments)"

SCHEMA = """
CREATE TABLE departments (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL
);
CREATE TABLE employees (
    id            INTEGER PRIMARY KEY,
    employee_code TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments (id),
    designation   TEXT NOT NULL,
    salary_paise  INTEGER NOT NULL CHECK (salary_paise >= 0),
    joined_on     TEXT NOT NULL,
    is_active     INTEGER NOT NULL CHECK (is_active IN (0, 1))
);
"""

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class PayrollError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation and money
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise PayrollError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise PayrollError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PayrollError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise PayrollError(f"{name} must be positive, got {number}")
    return number


def is_iso_date(text: str) -> bool:
    """True when the text is a YYYY-MM-DD calendar date; blank input is False."""
    if not isinstance(text, str):
        return False
    raw = text.strip()
    if not _DATE.match(raw):
        return False
    month = int(raw[5:7])
    day = int(raw[8:10])
    return 1 <= month <= 12 and 1 <= day <= 31


def require_iso_date(text: str, name: str = "joined_on") -> str:
    raw = _text(text, name).strip()
    if not is_iso_date(raw):
        raise PayrollError(f"{name} must be YYYY-MM-DD, got {raw!r}")
    return raw


def parse_money(text: str) -> int:
    """Parse a decimal money string into integer paise, exactly."""
    raw = _text(text, "money").strip()
    sign = 1
    if raw[0] in "+-":
        if raw[0] == "-":
            sign = -1
        raw = raw[1:]
    if raw.count(".") > 1:
        raise PayrollError(f"money has more than one decimal point: {text!r}")
    whole, _, frac = raw.partition(".")
    if not whole or not whole.isdigit():
        raise PayrollError(f"money has a non-digit integer part: {text!r}")
    if len(frac) > 2:
        raise PayrollError(f"money has more than 2 decimal places: {text!r}")
    if frac and not frac.isdigit():
        raise PayrollError(f"money has a non-digit fractional part: {text!r}")
    return sign * (int(whole) * 100 + int(frac.ljust(2, "0")))


def format_money(paise: int) -> str:
    amount = _whole(paise, "paise")
    sign = "-" if amount < 0 else ""
    magnitude = abs(amount)
    return f"{sign}{magnitude // 100}.{magnitude % 100:02d}"


def divide_half_up(numerator: int, denominator: int) -> int:
    top = _whole(numerator, "numerator")
    bottom = _positive(denominator, "denominator")
    sign = -1 if top < 0 else 1
    magnitude = abs(top)
    return sign * ((magnitude * 2 + bottom) // (2 * bottom))


def _int(text: str, name: str) -> int:
    raw = _text(text, name).strip()
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise PayrollError(f"{name} must be a whole number, got {raw!r}") from exc


def _flag(text: str, name: str) -> int:
    raw = _text(text, name).strip()
    if raw not in ("0", "1"):
        raise PayrollError(f"{name} must be 0 or 1, got {raw!r}")
    return int(raw)


# --------------------------------------------------------------------------- #
# Records and loading
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Department:
    id: int
    name: str
    location: str


@dataclass(frozen=True)
class Employee:
    id: int
    code: str
    name: str
    email: str
    department_id: int
    designation: str
    paise: int
    joined_on: str
    active: int


def _read_rows(path: str | Path, required: Sequence[str]) -> list[dict[str, str]]:
    target = Path(path)
    if not target.is_file():
        raise PayrollError(f"file not found: {target.name}")
    with target.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [column for column in required if column not in header]
        if missing:
            raise PayrollError(f"{target.name} is missing column(s): {', '.join(missing)}")
        return [dict(row) for row in reader]


def load_departments(path: str | Path | None = None) -> list[Department]:
    rows = _read_rows(path or DEPARTMENTS_FILE, ("id", "name", "location"))
    departments = [
        Department(
            id=_positive(_int(row["id"], "department id"), "department id"),
            name=_text(row["name"], "department name").strip(),
            location=(row["location"] or "").strip(),
        )
        for row in rows
    ]
    if len({d.id for d in departments}) != len(departments):
        raise PayrollError("department ids must be unique")
    if len({d.name for d in departments}) != len(departments):
        raise PayrollError("department names must be unique")
    return departments


def load_employees(path: str | Path | None = None) -> list[Employee]:
    rows = _read_rows(
        path or EMPLOYEES_FILE,
        ("id", "employee_code", "full_name", "email", "department_id",
         "designation", "salary", "joined_on", "is_active"),
    )
    employees = [
        Employee(
            id=_positive(_int(row["id"], "employee id"), "employee id"),
            code=_text(row["employee_code"], "employee_code").strip(),
            name=_text(row["full_name"], "full_name").strip(),
            email=_text(row["email"], "email").strip(),
            department_id=_positive(_int(row["department_id"], "department_id"), "department_id"),
            designation=_text(row["designation"], "designation").strip(),
            paise=parse_money(row["salary"]),
            joined_on=require_iso_date(row["joined_on"]),
            active=_flag(row["is_active"], "is_active"),
        )
        for row in rows
    ]
    if len({e.id for e in employees}) != len(employees):
        raise PayrollError("employee ids must be unique")
    if len({e.code for e in employees}) != len(employees):
        raise PayrollError("employee codes must be unique")
    return employees


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
def build_database(
    departments: Sequence[Department],
    employees: Sequence[Employee],
) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    known = {department.id for department in departments}
    for employee in employees:
        if employee.department_id not in known:
            raise PayrollError(
                f"employee {employee.code} names unknown department {employee.department_id}"
            )
    conn.executemany(
        "INSERT INTO departments VALUES (:id, :name, :location)",
        [{"id": d.id, "name": d.name, "location": d.location} for d in departments],
    )
    conn.executemany(
        "INSERT INTO employees VALUES (:id, :code, :name, :email, :department_id,"
        " :designation, :paise, :joined_on, :active)",
        [
            {
                "id": e.id,
                "code": e.code,
                "name": e.name,
                "email": e.email,
                "department_id": e.department_id,
                "designation": e.designation,
                "paise": e.paise,
                "joined_on": e.joined_on,
                "active": e.active,
            }
            for e in employees
        ],
    )
    conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def department_head_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Active head count per department, including departments with nobody."""
    rows = conn.execute(
        """
        WITH active AS (
            SELECT department_id, COUNT(*) AS head
            FROM employees
            WHERE is_active = 1
            GROUP BY department_id
        )
        SELECT d.name AS name, COALESCE(a.head, 0) AS head
        FROM departments d
        LEFT JOIN active a ON a.department_id = d.id
        ORDER BY d.name
        """
    ).fetchall()
    return {row["name"]: int(row["head"]) for row in rows}


def legacy_count_star(conn: sqlite3.Connection) -> dict[str, int]:
    """The COUNT(*)-after-LEFT-JOIN report, executed unchanged."""
    rows = conn.execute(LEGACY_COUNT_STAR).fetchall()
    return {row["name"]: int(row["head"]) for row in rows}


def legacy_inner_filter(conn: sqlite3.Connection) -> dict[str, int]:
    """The WHERE-on-a-LEFT-JOIN report, executed unchanged."""
    rows = conn.execute(LEGACY_INNER_FILTER).fetchall()
    return {row["name"]: int(row["head"]) for row in rows}


def department_summary(conn: sqlite3.Connection) -> list[tuple[str, int, int, int]]:
    """(name, head, total_paise, average_paise) for every department."""
    heads = department_head_counts(conn)
    totals = {
        row["name"]: int(row["total"])
        for row in conn.execute(
            """
            WITH active AS (
                SELECT department_id, SUM(salary_paise) AS total
                FROM employees
                WHERE is_active = 1
                GROUP BY department_id
            )
            SELECT d.name AS name, COALESCE(a.total, 0) AS total
            FROM departments d
            LEFT JOIN active a ON a.department_id = d.id
            ORDER BY d.name
            """
        ).fetchall()
    }
    summary = []
    for name in sorted(heads):
        head = heads[name]
        total = totals.get(name, 0)
        average = divide_half_up(total, head) if head else 0
        summary.append((name, head, total, average))
    return summary


def overall_average_paise(summary: Sequence[tuple[str, int, int, int]]) -> int:
    """Total payroll divided by total head count -- the correct average."""
    if not summary:
        raise PayrollError("summary must not be empty")
    head = sum(row[1] for row in summary)
    total = sum(row[2] for row in summary)
    if head == 0:
        return 0
    return divide_half_up(total, head)


def average_of_averages_paise(summary: Sequence[tuple[str, int, int, int]]) -> int:
    """The defective averaging: mean of the non-empty department averages."""
    if not summary:
        raise PayrollError("summary must not be empty")
    averages = [row[3] for row in summary if row[1] > 0]
    if not averages:
        return 0
    return divide_half_up(sum(averages), len(averages))


def payroll(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS head,
               COALESCE(SUM(salary_paise), 0) AS total,
               COALESCE(MIN(salary_paise), 0) AS lowest,
               COALESCE(MAX(salary_paise), 0) AS highest
        FROM employees
        WHERE is_active = 1
        """
    ).fetchone()
    head = int(row["head"])
    total = int(row["total"])
    return {
        "head": head,
        "total": total,
        "average": divide_half_up(total, head) if head else 0,
        "lowest": int(row["lowest"]),
        "highest": int(row["highest"]),
    }


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(
    employees_path: str | Path | None = None,
    *,
    departments_path: str | Path | None = None,
) -> dict[str, Any]:
    if employees_path is not None:
        folder = Path(employees_path).resolve().parent
        departments_path = departments_path or folder / "departments.csv"
    departments = load_departments(departments_path)
    employees = load_employees(employees_path)
    conn = build_database(departments, employees)
    summary = department_summary(conn)
    return {
        "conn": conn,
        "departments": departments,
        "employees": employees,
        "summary": summary,
        "overall": overall_average_paise(summary),
        "average_of_averages": average_of_averages_paise(summary),
        "payroll": payroll(conn),
        "correct_heads": department_head_counts(conn),
        "legacy_heads": legacy_count_star(conn),
        "inner_heads": legacy_inner_filter(conn),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    return {
        "departments": len(measured["departments"]),
        "employees": len(measured["employees"]),
        "payroll": {key: measured["payroll"][key] for key in ("head", "total", "average")},
        "overall_average_paise": measured["overall"],
        "average_of_averages_paise": measured["average_of_averages"],
        "gap_paise": measured["overall"] - measured["average_of_averages"],
        "rows": [
            {"department": name, "head": head, "total_paise": total, "average_paise": average}
            for name, head, total, average in measured["summary"]
        ],
        "legacy_count_star": measured["legacy_heads"],
        "legacy_inner_filter": measured["inner_heads"],
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:
        return False


def audit(
    measured: dict[str, Any],
    *,
    read_heads: Callable[[sqlite3.Connection], dict[str, int]] = department_head_counts,
) -> list[tuple[str, bool]]:
    summary = measured["summary"]
    employees = measured["employees"]
    conn = measured["conn"]
    active = [employee for employee in employees if employee.active == 1]

    def heads_via_reader() -> dict[str, int]:
        return read_heads(conn)

    def inactive_are_invisible() -> bool:
        before = heads_via_reader()
        extra = Employee(
            id=max((e.id for e in employees), default=0) + 1,
            code="EMP999",
            name="Ghost Hire",
            email="ghost@example.com",
            department_id=measured["departments"][0].id,
            designation="Placeholder",
            paise=100,
            joined_on="2026-01-01",
            active=0,
        )
        grown = build_database(measured["departments"], [*employees, extra])
        return heads_via_reader_for(grown, read_heads) == before

    checks = [
        (
            "correct_head_total_is_active_count",
            lambda: sum(heads_via_reader().values()) == len(active) == 6,
        ),
        (
            "legacy_count_star_inflates_by_phantom_rows",
            lambda: sum(measured["legacy_heads"].values()) == 8,
        ),
        (
            "phantom_rows_are_the_empty_departments",
            lambda: (
                measured["legacy_heads"]["Research"] == 1
                and measured["legacy_heads"]["Sales"] == 1
                and heads_via_reader()["Research"] == 0
                and heads_via_reader()["Sales"] == 0
            ),
        ),
        (
            "legacy_inner_filter_drops_two_departments",
            lambda: sorted(measured["inner_heads"]) == ["Engineering", "Finance", "Human Resources"],
        ),
        (
            "overall_average_is_total_over_head",
            lambda: measured["overall"] == 83_000_000,
        ),
        (
            "average_of_averages_disagrees",
            lambda: measured["average_of_averages"] == 77_222_222
            and measured["overall"] - measured["average_of_averages"] == 5_777_778,
        ),
        (
            "engineering_average_rounds_half_up",
            lambda: dict((row[0], row[3]) for row in summary)["Engineering"] == 83_666_667,
        ),
        (
            "department_totals_reconcile",
            lambda: sum(row[2] for row in summary) == 498_000_000 == measured["payroll"]["total"],
        ),
        (
            "every_salary_round_trips",
            lambda: all(
                format_money(parse_money(value)) == value
                for value in ("720000.00", "1150000.00", "490000.00", "0.05", "8.20")
            ),
        ),
        (
            "divide_half_up_rounds_away_from_zero",
            lambda: (
                divide_half_up(251_000_000, 3) == 83_666_667
                and divide_half_up(1, 2) == 1
                and divide_half_up(5, 2) == 3
                and divide_half_up(-5, 2) == -3
            ),
        ),
        (
            "inactive_hires_change_nothing",
            lambda: inactive_are_invisible(),
        ),
        (
            "payroll_extremes_match_the_rows",
            lambda: measured["payroll"]["lowest"] == 49_000_000
            and measured["payroll"]["highest"] == 140_000_000,
        ),
        (
            "rebuild_is_deterministic",
            lambda: department_summary(
                build_database(measured["departments"], employees)
            )
            == summary,
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


def heads_via_reader_for(
    conn: sqlite3.Connection,
    reader: Callable[[sqlite3.Connection], dict[str, int]],
) -> dict[str, int]:
    return reader(conn)


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_summary(measured: dict[str, Any]) -> str:
    lines = ["  department          head      total        average    COUNT(*)"]
    for name, head, total, average in measured["summary"]:
        lines.append(
            f"  {name:<18}{head:>6}{format_money(total):>12}"
            f"{format_money(average):>14}{measured['legacy_heads'].get(name, 0):>10}"
        )
    lines.append(
        f"  {'TOTAL':<18}{sum(row[1] for row in measured['summary']):>6}"
        f"{format_money(sum(row[2] for row in measured['summary'])):>12}"
        f"{format_money(measured['overall']):>14}"
        f"{sum(measured['legacy_heads'].values()):>10}"
    )
    return "\n".join(lines)


def run_demo() -> int:
    measured = measure()
    print("Employee payroll -- aggregates count rows, not people")
    print("=" * 54)
    print()
    print("Three legacy reports, one seed file, three different head counts.")
    print()
    print(render_summary(measured))
    print()
    print("1. COUNT(*) after a LEFT JOIN counts the phantom row:")
    print("   Research and Sales have no active staff, yet COUNT(*) reports 1 each.")
    print(
        f"   legacy head total {sum(measured['legacy_heads'].values())} vs "
        f"active employees {len([e for e in measured['employees'] if e.active == 1])}."
    )
    print()
    print("2. The filter belongs in ON, not WHERE:")
    print("   " + " ".join(LEGACY_INNER_FILTER.split()[:6]) + " ...")
    print(
        f"   the WHERE form returns {len(measured['inner_heads'])} departments and "
        "silently drops Research and Sales."
    )
    print()
    print("3. An average of averages is not the average:")
    print(f"   total {format_money(measured['payroll']['total'])} / "
          f"{measured['payroll']['head']} people = {format_money(measured['overall'])}")
    print("   mean of the three non-empty department averages = "
          f"{format_money(measured['average_of_averages'])}")
    print(f"   gap {format_money(measured['overall'] - measured['average_of_averages'])} "
          "on a six-person payroll.")
    print()
    print("Checks")
    results = audit(measured)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: correct head total 6 equals the active employee count, "
        f"COUNT(*) reports {sum(measured['legacy_heads'].values())} by counting "
        "the 2 phantom rows for Research and Sales, the WHERE form drops both "
        "departments, total payroll "
        f"{format_money(measured['payroll']['total'])} over "
        f"{measured['payroll']['head']} people averages "
        f"{format_money(measured['overall'])} while averaging the department "
        f"averages reports {format_money(measured['average_of_averages'])}, a gap "
        f"of {format_money(measured['overall'] - measured['average_of_averages'])}; "
        f"{passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
