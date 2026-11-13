"""CRUD operations and reporting queries for the Employee Database."""

from __future__ import annotations

import sqlite3
from typing import Any


# --------------------------------------------------------------------------- #
# Departments
# --------------------------------------------------------------------------- #
def add_department(conn: sqlite3.Connection, name: str, location: str = "Head Office") -> int:
    """Insert a department and return its id."""
    cur = conn.execute(
        "INSERT INTO departments (name, location) VALUES (?, ?)",
        (name.strip(), location.strip()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_departments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return every department with its employee count."""
    return conn.execute(
        """
        SELECT d.id, d.name, d.location,
               COUNT(e.id) AS employee_count
        FROM departments d
        LEFT JOIN employees e ON e.department_id = d.id
        GROUP BY d.id
        ORDER BY d.name
        """
    ).fetchall()


# --------------------------------------------------------------------------- #
# Employees
# --------------------------------------------------------------------------- #
def add_employee(
    conn: sqlite3.Connection,
    *,
    employee_code: str,
    full_name: str,
    email: str,
    department_id: int,
    designation: str,
    salary: float,
    joined_on: str,
) -> int:
    """Insert an employee and return the new row id."""
    cur = conn.execute(
        """
        INSERT INTO employees
            (employee_code, full_name, email, department_id, designation, salary, joined_on)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (employee_code.strip(), full_name.strip(), email.strip(), department_id,
         designation.strip(), float(salary), joined_on),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_employee(conn: sqlite3.Connection, employee_id: int) -> sqlite3.Row | None:
    """Fetch a single employee joined with its department name."""
    return conn.execute(
        """
        SELECT e.*, d.name AS department_name
        FROM employees e
        JOIN departments d ON d.id = e.department_id
        WHERE e.id = ?
        """,
        (employee_id,),
    ).fetchone()


def list_employees(conn: sqlite3.Connection, *, active_only: bool = False) -> list[sqlite3.Row]:
    """List employees ordered by name."""
    sql = """
        SELECT e.id, e.employee_code, e.full_name, e.email, e.designation,
               e.salary, e.joined_on, e.is_active, d.name AS department_name
        FROM employees e
        JOIN departments d ON d.id = e.department_id
    """
    if active_only:
        sql += " WHERE e.is_active = 1"
    sql += " ORDER BY e.full_name"
    return conn.execute(sql).fetchall()


def search_employees(conn: sqlite3.Connection, term: str) -> list[sqlite3.Row]:
    """Case-insensitive search over name, email, code and designation."""
    like = f"%{term.strip()}%"
    return conn.execute(
        """
        SELECT e.id, e.employee_code, e.full_name, e.email, e.designation,
               e.salary, d.name AS department_name
        FROM employees e
        JOIN departments d ON d.id = e.department_id
        WHERE e.full_name LIKE ? COLLATE NOCASE
           OR e.email    LIKE ? COLLATE NOCASE
           OR e.employee_code LIKE ? COLLATE NOCASE
           OR e.designation LIKE ? COLLATE NOCASE
        ORDER BY e.full_name
        """,
        (like, like, like, like),
    ).fetchall()


def update_salary(conn: sqlite3.Connection, employee_id: int, salary: float) -> bool:
    """Update an employee salary. Returns True when a row changed."""
    cur = conn.execute(
        "UPDATE employees SET salary = ? WHERE id = ?",
        (float(salary), employee_id),
    )
    conn.commit()
    return cur.rowcount > 0


def deactivate_employee(conn: sqlite3.Connection, employee_id: int) -> bool:
    """Soft-delete an employee by flipping ``is_active``."""
    cur = conn.execute(
        "UPDATE employees SET is_active = 0 WHERE id = ?",
        (employee_id,),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_employee(conn: sqlite3.Connection, employee_id: int) -> bool:
    """Hard-delete an employee row. Returns True when a row was removed."""
    cur = conn.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
    conn.commit()
    return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def department_salary_summary(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Head count, total and average salary per department."""
    return conn.execute(
        """
        SELECT d.name AS department,
               COUNT(e.id) AS head_count,
               COALESCE(SUM(e.salary), 0) AS total_salary,
               COALESCE(AVG(e.salary), 0) AS average_salary
        FROM departments d
        LEFT JOIN employees e ON e.department_id = d.id AND e.is_active = 1
        GROUP BY d.id
        ORDER BY total_salary DESC
        """
    ).fetchall()


def top_earners(conn: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    """Highest paid active employees."""
    return conn.execute(
        """
        SELECT e.full_name, e.designation, e.salary, d.name AS department_name
        FROM employees e
        JOIN departments d ON d.id = e.department_id
        WHERE e.is_active = 1
        ORDER BY e.salary DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()


def payroll_cost(conn: sqlite3.Connection) -> dict[str, Any]:
    """Aggregate payroll figures used by the demo report."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS head_count,
               COALESCE(SUM(salary), 0) AS total,
               COALESCE(MIN(salary), 0) AS lowest,
               COALESCE(MAX(salary), 0) AS highest
        FROM employees
        WHERE is_active = 1
        """
    ).fetchone()
    return dict(row)
