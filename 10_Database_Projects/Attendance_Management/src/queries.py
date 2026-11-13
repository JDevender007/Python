"""CRUD operations and reporting queries for Attendance Management."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import sqlite3


# --------------------------------------------------------------------------- #
# People
# --------------------------------------------------------------------------- #
def add_person(conn: sqlite3.Connection, code: str, name: str, group: str = "Default") -> int:
    """Register a person and return their id."""
    cur = conn.execute(
        "INSERT INTO people (code, full_name, group_name) VALUES (?, ?, ?)",
        (code.strip(), name.strip(), group.strip()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_people(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Everyone with their recorded attendance count."""
    return conn.execute(
        """
        SELECT p.id, p.code, p.full_name, p.group_name,
               COUNT(a.id) AS days_marked
        FROM people p
        LEFT JOIN attendance a ON a.person_id = p.id
        GROUP BY p.id
        ORDER BY p.code
        """
    ).fetchall()


def search_people(conn: sqlite3.Connection, term: str) -> list[sqlite3.Row]:
    """Case-insensitive search over code, name and group."""
    like = f"%{term.strip()}%"
    return conn.execute(
        """
        SELECT id, code, full_name, group_name
        FROM people
        WHERE code LIKE ? COLLATE NOCASE
           OR full_name LIKE ? COLLATE NOCASE
           OR group_name LIKE ? COLLATE NOCASE
        ORDER BY code
        """,
        (like, like, like),
    ).fetchall()


# --------------------------------------------------------------------------- #
# Marking attendance
# --------------------------------------------------------------------------- #
def mark_attendance(
    conn: sqlite3.Connection,
    person_id: int,
    day: str,
    status: str,
    note: str = "",
) -> str:
    """Mark (or update) attendance. Returns 'inserted' or 'updated'."""
    if status not in {"present", "absent", "late", "leave"}:
        raise ValueError(f"invalid status: {status}")

    cur = conn.execute(
        """
        INSERT INTO attendance (person_id, day, status, note)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (person_id, day)
        DO UPDATE SET status = excluded.status, note = excluded.note
        """,
        (person_id, day, status, note.strip()),
    )
    conn.commit()
    return "updated" if cur.rowcount == 0 else "inserted"


def mark_by_code(conn: sqlite3.Connection, code: str, day: str, status: str, note: str = "") -> str:
    """Mark attendance using a person code instead of an id."""
    person = conn.execute("SELECT id FROM people WHERE code = ?", (code.strip(),)).fetchone()
    if person is None:
        raise ValueError(f"unknown code: {code}")
    return mark_attendance(conn, person["id"], day, status, note)


def day_sheet(conn: sqlite3.Connection, day: str) -> list[sqlite3.Row]:
    """Who is marked what for a given day (everyone, with status or NULL)."""
    return conn.execute(
        """
        SELECT p.code, p.full_name, p.group_name,
               COALESCE(a.status, 'unmarked') AS status,
               COALESCE(a.note, '') AS note
        FROM people p
        LEFT JOIN attendance a ON a.person_id = p.id AND a.day = ?
        ORDER BY p.code
        """,
        (day,),
    ).fetchall()


def clear_day(conn: sqlite3.Connection, day: str) -> int:
    """Remove all markings for a day. Returns rows deleted."""
    cur = conn.execute("DELETE FROM attendance WHERE day = ?", (day,))
    conn.commit()
    return cur.rowcount


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def monthly_report(conn: sqlite3.Connection, month: str) -> list[sqlite3.Row]:
    """Per-person percentages for a month like '2026-01'."""
    like = f"{month}-%"
    return conn.execute(
        """
        SELECT p.code, p.full_name, p.group_name,
               COUNT(a.id) AS days_marked,
               SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present,
               SUM(CASE WHEN a.status = 'late'    THEN 1 ELSE 0 END) AS late,
               SUM(CASE WHEN a.status = 'absent'  THEN 1 ELSE 0 END) AS absent,
               SUM(CASE WHEN a.status = 'leave'   THEN 1 ELSE 0 END) AS leave_days,
               ROUND(100.0 * SUM(CASE WHEN a.status IN ('present', 'late') THEN 1 ELSE 0 END)
                     / NULLIF(COUNT(a.id), 0), 1) AS attendance_pct
        FROM people p
        LEFT JOIN attendance a ON a.person_id = p.id AND a.day LIKE ?
        GROUP BY p.id
        ORDER BY attendance_pct DESC, p.code
        """,
        (like,),
    ).fetchall()


def defaulters_report(conn: sqlite3.Connection, month: str, threshold: float = 75.0) -> list[sqlite3.Row]:
    """People below the attendance threshold for a month."""
    rows = monthly_report(conn, month)
    return [r for r in rows if r["days_marked"] and (r["attendance_pct"] or 0) < threshold]


def status_summary(conn: sqlite3.Connection, day: str | None = None) -> dict[str, Any]:
    """Counts per status, optionally for a single day."""
    if day:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS n
            FROM attendance WHERE day = ? GROUP BY status
            """,
            (day,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM attendance GROUP BY status"
        ).fetchall()
    summary = {r["status"]: r["n"] for r in rows}
    summary["total"] = sum(summary.values())
    return summary


# --------------------------------------------------------------------------- #
# CSV import / export
# --------------------------------------------------------------------------- #
def export_csv(conn: sqlite3.Connection, path: str | Path, month: str | None = None) -> Path:
    """Export the attendance ledger to a CSV file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    sql = """
        SELECT p.code, p.full_name, p.group_name, a.day, a.status, a.note
        FROM attendance a
        JOIN people p ON p.id = a.person_id
    """
    params: tuple = ()
    if month:
        sql += " WHERE a.day LIKE ?"
        params = (f"{month}-%",)
    sql += " ORDER BY a.day, p.code"

    rows = conn.execute(sql, params).fetchall()
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["code", "full_name", "group_name", "day", "status", "note"])
        for row in rows:
            writer.writerow([row["code"], row["full_name"], row["group_name"],
                             row["day"], row["status"], row["note"]])
    return target


def import_csv(conn: sqlite3.Connection, path: str | Path) -> int:
    """Import attendance rows from a CSV file. Returns rows processed."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    processed = 0
    with source.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            code = (row.get("code") or "").strip()
            day = (row.get("day") or "").strip()
            status = (row.get("status") or "").strip()
            if not code or not day or not status:
                continue
            try:
                mark_by_code(conn, code, day, status, (row.get("note") or "").strip())
            except ValueError:
                continue
            processed += 1
    return processed


def csv_to_text(rows: list[sqlite3.Row]) -> str:
    """Render rows as CSV text (handy for tests and previews)."""
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.writer(buf)
    headers = list(rows[0].keys())
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row[h] for h in headers])
    return buf.getvalue()
