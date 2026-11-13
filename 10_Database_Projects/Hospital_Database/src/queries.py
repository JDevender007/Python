"""CRUD operations and reporting queries for the Hospital Database."""

from __future__ import annotations

import sqlite3
from typing import Any


# --------------------------------------------------------------------------- #
# Doctors
# --------------------------------------------------------------------------- #
def add_doctor(conn: sqlite3.Connection, license_no: str, name: str, specialty: str, phone: str) -> int:
    """Register a doctor and return the new row id."""
    cur = conn.execute(
        "INSERT INTO doctors (license_no, full_name, specialty, phone) VALUES (?, ?, ?, ?)",
        (license_no.strip(), name.strip(), specialty.strip(), phone.strip()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_doctors(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """List doctors with the number of appointments they hold."""
    return conn.execute(
        """
        SELECT d.id, d.license_no, d.full_name, d.specialty, d.phone,
               COUNT(a.id) AS appointments
        FROM doctors d
        LEFT JOIN appointments a ON a.doctor_id = d.id
        GROUP BY d.id
        ORDER BY d.full_name
        """
    ).fetchall()


# --------------------------------------------------------------------------- #
# Patients
# --------------------------------------------------------------------------- #
def add_patient(
    conn: sqlite3.Connection,
    *,
    mrn: str,
    full_name: str,
    date_of_birth: str,
    gender: str,
    phone: str,
    blood_group: str | None = None,
) -> int:
    """Register a patient and return the new row id."""
    cur = conn.execute(
        """
        INSERT INTO patients (mrn, full_name, date_of_birth, gender, phone, blood_group)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (mrn.strip(), full_name.strip(), date_of_birth, gender.strip(), phone.strip(), blood_group),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_patient(conn: sqlite3.Connection, patient_id: int) -> sqlite3.Row | None:
    """Fetch one patient with their outstanding balance."""
    return conn.execute(
        """
        SELECT p.*,
               COALESCE(SUM(CASE WHEN b.paid = 0 THEN b.amount ELSE 0 END), 0) AS balance_due
        FROM patients p
        LEFT JOIN bills b ON b.patient_id = p.id
        WHERE p.id = ?
        GROUP BY p.id
        """,
        (patient_id,),
    ).fetchone()


def search_patients(conn: sqlite3.Connection, term: str) -> list[sqlite3.Row]:
    """Case-insensitive search over name, MRN, phone and blood group."""
    like = f"%{term.strip()}%"
    return conn.execute(
        """
        SELECT id, mrn, full_name, date_of_birth, gender, phone, blood_group
        FROM patients
        WHERE full_name LIKE ? COLLATE NOCASE
           OR mrn LIKE ? COLLATE NOCASE
           OR phone LIKE ? COLLATE NOCASE
           OR blood_group LIKE ? COLLATE NOCASE
        ORDER BY full_name
        """,
        (like, like, like, like),
    ).fetchall()


# --------------------------------------------------------------------------- #
# Appointments
# --------------------------------------------------------------------------- #
def book_appointment(
    conn: sqlite3.Connection,
    *,
    patient_id: int,
    doctor_id: int,
    scheduled_on: str,
    slot: str,
    reason: str,
) -> int:
    """Book an appointment and return its id."""
    cur = conn.execute(
        """
        INSERT INTO appointments (patient_id, doctor_id, scheduled_on, slot, reason, status)
        VALUES (?, ?, ?, ?, ?, 'scheduled')
        """,
        (patient_id, doctor_id, scheduled_on, slot, reason.strip()),
    )
    conn.commit()
    return int(cur.lastrowid)


def set_appointment_status(conn: sqlite3.Connection, appointment_id: int, status: str) -> bool:
    """Update an appointment status. Returns True when a row changed."""
    if status not in {"scheduled", "completed", "cancelled"}:
        raise ValueError(f"invalid status: {status}")
    cur = conn.execute(
        "UPDATE appointments SET status = ? WHERE id = ?",
        (status, appointment_id),
    )
    conn.commit()
    return cur.rowcount > 0


def discharge_patient(conn: sqlite3.Connection, appointment_id: int) -> bool:
    """Convenience alias: mark an appointment completed (patient discharged)."""
    return set_appointment_status(conn, appointment_id, "completed")


def list_appointments(
    conn: sqlite3.Connection, *, status: str | None = None, day: str | None = None
) -> list[sqlite3.Row]:
    """Appointments joined with patient and doctor names."""
    sql = """
        SELECT a.id, a.scheduled_on, a.slot, a.reason, a.status,
               p.full_name AS patient_name, d.full_name AS doctor_name, d.specialty
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        JOIN doctors d  ON d.id = a.doctor_id
    """
    clauses, params = [], []
    if status:
        clauses.append("a.status = ?")
        params.append(status)
    if day:
        clauses.append("a.scheduled_on = ?")
        params.append(day)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY a.scheduled_on, a.slot"
    return conn.execute(sql, params).fetchall()


# --------------------------------------------------------------------------- #
# Billing
# --------------------------------------------------------------------------- #
def create_bill(
    conn: sqlite3.Connection,
    *,
    patient_id: int,
    amount: float,
    issued_on: str,
    appointment_id: int | None = None,
) -> int:
    """Issue a bill and return its id."""
    cur = conn.execute(
        """
        INSERT INTO bills (appointment_id, patient_id, amount, paid, issued_on)
        VALUES (?, ?, ?, 0, ?)
        """,
        (appointment_id, patient_id, float(amount), issued_on),
    )
    conn.commit()
    return int(cur.lastrowid)


def pay_bill(conn: sqlite3.Connection, bill_id: int) -> bool:
    """Mark a bill as paid. Returns True when a row changed."""
    cur = conn.execute("UPDATE bills SET paid = 1 WHERE id = ?", (bill_id,))
    conn.commit()
    return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def schedule_view(conn: sqlite3.Connection, day: str) -> list[sqlite3.Row]:
    """The day's schedule ordered by slot."""
    return list_appointments(conn, day=day)


def revenue_report(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Revenue per day with collected vs pending amounts."""
    return conn.execute(
        """
        SELECT issued_on AS day,
               COUNT(*) AS bills,
               SUM(amount) AS billed,
               SUM(CASE WHEN paid = 1 THEN amount ELSE 0 END) AS collected,
               SUM(CASE WHEN paid = 0 THEN amount ELSE 0 END) AS pending
        FROM bills
        GROUP BY issued_on
        ORDER BY issued_on
        """
    ).fetchall()


def revenue_totals(conn: sqlite3.Connection) -> dict[str, Any]:
    """Aggregate revenue figures used by the demo report."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS bills,
               COALESCE(SUM(amount), 0) AS billed,
               COALESCE(SUM(CASE WHEN paid = 1 THEN amount ELSE 0 END), 0) AS collected,
               COALESCE(SUM(CASE WHEN paid = 0 THEN amount ELSE 0 END), 0) AS pending
        FROM bills
        """
    ).fetchone()
    return dict(row)


def specialty_workload(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Appointments grouped by doctor specialty."""
    return conn.execute(
        """
        SELECT d.specialty,
               COUNT(a.id) AS appointments,
               SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) AS completed,
               SUM(CASE WHEN a.status = 'scheduled' THEN 1 ELSE 0 END) AS scheduled
        FROM doctors d
        LEFT JOIN appointments a ON a.doctor_id = d.id
        GROUP BY d.id
        ORDER BY appointments DESC
        """
    ).fetchall()
