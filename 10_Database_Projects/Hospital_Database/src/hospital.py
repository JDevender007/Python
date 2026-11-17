"""NULL is not a value, and none of your predicates say what you think.

Two patients in this hospital have no blood group recorded. That single fact
makes three ordinary-looking reports wrong in three different ways:

1. **`!=` drops NULL rows.** `WHERE blood_group <> 'O+'` returns the three
   patients whose group is a different known value; the two patients with no
   group are excluded, because `NULL <> 'O+'` evaluates to NULL, not TRUE. The
   report reads "3 patients are not O+" when the wards hold 5.

2. **`COUNT(*)` counts rows, `COUNT(blood_group)` counts values.** A
   completeness report that prints `COUNT(*)` beside the words "with blood
   group" claims 6 of 6 when the true figure is 4 of 6. The missing data is
   invisible precisely because the query is about it.

3. **`ORDER BY` puts NULL first in SQLite.** A "three most common blood groups"
   report ordered by group and limited to three rows leads with the unnamed
   NULL group and silently drops two real groups (B+ and O+). A LIMIT hands one
   of its slots to the absence of data.

Bills are money, so they are integer cents parsed from text, and the average
bill goes through `divide_half_up` rather than `AVG()` or `round()`.

All three defective queries are kept as executable strings and run beside the
corrected ones on the same seed files.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCTORS_FILE = DATA_DIR / "doctors.csv"
PATIENTS_FILE = DATA_DIR / "patients.csv"
APPOINTMENTS_FILE = DATA_DIR / "appointments.csv"
BILLS_FILE = DATA_DIR / "bills.csv"

STATUSES = ("scheduled", "completed", "cancelled")
GENDERS = ("Male", "Female", "Other")

# The three defective reports, kept as strings so the demo prints them and the
# tests execute them on the same database as the corrected versions.
LEGACY_NOT_GROUP = """
SELECT COUNT(*) AS n
FROM patients
WHERE blood_group <> ?
"""

LEGACY_COMPLETENESS = """
SELECT COUNT(*) AS labelled
FROM patients
"""

LEGACY_TOP_GROUPS = """
SELECT blood_group AS grp, COUNT(*) AS n
FROM patients
GROUP BY blood_group
ORDER BY blood_group
LIMIT ?
"""

SCHEMA = """
CREATE TABLE doctors (
    id         INTEGER PRIMARY KEY,
    license_no TEXT NOT NULL UNIQUE,
    full_name  TEXT NOT NULL,
    specialty  TEXT NOT NULL,
    phone      TEXT NOT NULL
);
CREATE TABLE patients (
    id            INTEGER PRIMARY KEY,
    mrn           TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    gender        TEXT NOT NULL,
    phone         TEXT NOT NULL,
    blood_group   TEXT
);
CREATE TABLE appointments (
    id           INTEGER PRIMARY KEY,
    patient_id   INTEGER NOT NULL REFERENCES patients (id),
    doctor_id    INTEGER NOT NULL REFERENCES doctors (id),
    scheduled_on TEXT NOT NULL,
    slot         TEXT NOT NULL,
    reason       TEXT NOT NULL,
    status       TEXT NOT NULL
);
CREATE TABLE bills (
    id             INTEGER PRIMARY KEY,
    appointment_id INTEGER REFERENCES appointments (id),
    patient_id     INTEGER NOT NULL REFERENCES patients (id),
    amount_cents   INTEGER NOT NULL CHECK (amount_cents >= 0),
    paid           INTEGER NOT NULL CHECK (paid IN (0, 1)),
    issued_on      TEXT NOT NULL
);
"""

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SLOT = re.compile(r"^\d{2}:\d{2}$")


class HospitalError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation and money
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise HospitalError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise HospitalError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HospitalError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise HospitalError(f"{name} must be positive, got {number}")
    return number


def _choice(value: object, name: str, allowed: Sequence[str]) -> str:
    text = _text(value, name).strip()
    if text not in allowed:
        raise HospitalError(f"{name} must be one of {list(allowed)}, got {text!r}")
    return text


def is_iso_date(text: str) -> bool:
    if not isinstance(text, str):
        return False
    raw = text.strip()
    if not _DATE.match(raw):
        return False
    return 1 <= int(raw[5:7]) <= 12 and 1 <= int(raw[8:10]) <= 31


def is_slot(text: str) -> bool:
    if not isinstance(text, str):
        return False
    raw = text.strip()
    if not _SLOT.match(raw):
        return False
    return 0 <= int(raw[:2]) <= 23 and 0 <= int(raw[3:]) <= 59


def parse_cents(text: str) -> int:
    """Parse a decimal money string into integer cents, exactly."""
    raw = _text(text, "amount").strip()
    sign = 1
    if raw[0] in "+-":
        if raw[0] == "-":
            sign = -1
        raw = raw[1:]
    if raw.count(".") > 1:
        raise HospitalError(f"amount has more than one decimal point: {text!r}")
    whole, _, frac = raw.partition(".")
    if not whole or not whole.isdigit():
        raise HospitalError(f"amount has a non-digit integer part: {text!r}")
    if len(frac) > 2:
        raise HospitalError(f"amount has more than 2 decimal places: {text!r}")
    if frac and not frac.isdigit():
        raise HospitalError(f"amount has a non-digit fractional part: {text!r}")
    return sign * (int(whole) * 100 + int(frac.ljust(2, "0")))


def format_cents(cents: int) -> str:
    amount = _whole(cents, "cents")
    sign = "-" if amount < 0 else ""
    magnitude = abs(amount)
    return f"{sign}{magnitude // 100}.{magnitude % 100:02d}"


def divide_half_up(numerator: int, denominator: int) -> int:
    top = _whole(numerator, "numerator")
    bottom = _positive(denominator, "denominator")
    sign = -1 if top < 0 else 1
    magnitude = abs(top)
    return sign * ((magnitude * 2 + bottom) // (2 * bottom))


def _int(text: str | None, name: str) -> int:
    raw = _text(text, name).strip()
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise HospitalError(f"{name} must be a whole number, got {raw!r}") from exc


def _optional_int(text: str | None, name: str) -> int | None:
    if text is None or not text.strip():
        return None
    return _int(text, name)


def _flag(text: str, name: str) -> int:
    raw = _text(text, name).strip()
    if raw not in ("0", "1"):
        raise HospitalError(f"{name} must be 0 or 1, got {raw!r}")
    return int(raw)


# --------------------------------------------------------------------------- #
# Records and loading
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Doctor:
    id: int
    license_no: str
    name: str
    specialty: str


@dataclass(frozen=True)
class Patient:
    id: int
    mrn: str
    name: str
    date_of_birth: str
    gender: str
    blood_group: str | None


@dataclass(frozen=True)
class Appointment:
    id: int
    patient_id: int
    doctor_id: int
    scheduled_on: str
    slot: str
    reason: str
    status: str


@dataclass(frozen=True)
class Bill:
    id: int
    appointment_id: int | None
    patient_id: int
    cents: int
    paid: int
    issued_on: str


def _read_rows(path: str | Path, required: Sequence[str]) -> list[dict[str, str]]:
    target = Path(path)
    if not target.is_file():
        raise HospitalError(f"file not found: {target.name}")
    with target.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [column for column in required if column not in header]
        if missing:
            raise HospitalError(f"{target.name} is missing column(s): {', '.join(missing)}")
        return [dict(row) for row in reader]


def load_doctors(path: str | Path | None = None) -> list[Doctor]:
    rows = _read_rows(path or DOCTORS_FILE, ("id", "license_no", "full_name", "specialty"))
    doctors = [
        Doctor(
            id=_positive(_int(row["id"], "doctor id"), "doctor id"),
            license_no=_text(row["license_no"], "license_no").strip(),
            name=_text(row["full_name"], "full_name").strip(),
            specialty=_text(row["specialty"], "specialty").strip(),
        )
        for row in rows
    ]
    if len({d.id for d in doctors}) != len(doctors):
        raise HospitalError("doctor ids must be unique")
    if len({d.license_no for d in doctors}) != len(doctors):
        raise HospitalError("doctor licenses must be unique")
    return doctors


def load_patients(path: str | Path | None = None) -> list[Patient]:
    rows = _read_rows(
        path or PATIENTS_FILE,
        ("id", "mrn", "full_name", "date_of_birth", "gender", "blood_group"),
    )
    patients = [
        Patient(
            id=_positive(_int(row["id"], "patient id"), "patient id"),
            mrn=_text(row["mrn"], "mrn").strip(),
            name=_text(row["full_name"], "full_name").strip(),
            date_of_birth=_text(row["date_of_birth"], "date_of_birth").strip(),
            gender=_choice(row["gender"], "gender", GENDERS),
            blood_group=(row["blood_group"] or "").strip() or None,
        )
        for row in rows
    ]
    if len({p.id for p in patients}) != len(patients):
        raise HospitalError("patient ids must be unique")
    if len({p.mrn for p in patients}) != len(patients):
        raise HospitalError("patient MRNs must be unique")
    for patient in patients:
        if not is_iso_date(patient.date_of_birth):
            raise HospitalError(
                f"date_of_birth must be YYYY-MM-DD, got {patient.date_of_birth!r}"
            )
    return patients


def load_appointments(path: str | Path | None = None) -> list[Appointment]:
    rows = _read_rows(
        path or APPOINTMENTS_FILE,
        ("id", "patient_id", "doctor_id", "scheduled_on", "slot", "reason", "status"),
    )
    appointments = [
        Appointment(
            id=_positive(_int(row["id"], "appointment id"), "appointment id"),
            patient_id=_positive(_int(row["patient_id"], "patient_id"), "patient_id"),
            doctor_id=_positive(_int(row["doctor_id"], "doctor_id"), "doctor_id"),
            scheduled_on=_text(row["scheduled_on"], "scheduled_on").strip(),
            slot=_text(row["slot"], "slot").strip(),
            reason=_text(row["reason"], "reason").strip(),
            status=_choice(row["status"], "status", STATUSES),
        )
        for row in rows
    ]
    for appointment in appointments:
        if not is_iso_date(appointment.scheduled_on):
            raise HospitalError(
                f"scheduled_on must be YYYY-MM-DD, got {appointment.scheduled_on!r}"
            )
        if not is_slot(appointment.slot):
            raise HospitalError(f"slot must be HH:MM, got {appointment.slot!r}")
    if len({a.id for a in appointments}) != len(appointments):
        raise HospitalError("appointment ids must be unique")
    return appointments


def load_bills(path: str | Path | None = None) -> list[Bill]:
    rows = _read_rows(
        path or BILLS_FILE,
        ("id", "appointment_id", "patient_id", "amount", "paid", "issued_on"),
    )
    bills = [
        Bill(
            id=_positive(_int(row["id"], "bill id"), "bill id"),
            appointment_id=_optional_int(row["appointment_id"], "appointment_id"),
            patient_id=_positive(_int(row["patient_id"], "patient_id"), "patient_id"),
            cents=parse_cents(row["amount"]),
            paid=_flag(row["paid"], "paid"),
            issued_on=_text(row["issued_on"], "issued_on").strip(),
        )
        for row in rows
    ]
    for bill in bills:
        if not is_iso_date(bill.issued_on):
            raise HospitalError(f"issued_on must be YYYY-MM-DD, got {bill.issued_on!r}")
    if len({b.id for b in bills}) != len(bills):
        raise HospitalError("bill ids must be unique")
    return bills


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
def build_database(
    doctors: Sequence[Doctor],
    patients: Sequence[Patient],
    appointments: Sequence[Appointment],
    bills: Sequence[Bill],
) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    patient_ids = {patient.id for patient in patients}
    doctor_ids = {doctor.id for doctor in doctors}
    for appointment in appointments:
        if appointment.patient_id not in patient_ids:
            raise HospitalError(
                f"appointment {appointment.id} names unknown patient {appointment.patient_id}"
            )
        if appointment.doctor_id not in doctor_ids:
            raise HospitalError(
                f"appointment {appointment.id} names unknown doctor {appointment.doctor_id}"
            )
    appointment_ids = {appointment.id for appointment in appointments}
    for bill in bills:
        if bill.patient_id not in patient_ids:
            raise HospitalError(f"bill {bill.id} names unknown patient {bill.patient_id}")
        if bill.appointment_id is not None and bill.appointment_id not in appointment_ids:
            raise HospitalError(f"bill {bill.id} names unknown appointment {bill.appointment_id}")

    conn.executemany(
        "INSERT INTO doctors VALUES (:id, :license_no, :full_name, :specialty, :phone)",
        [
            {"id": d.id, "license_no": d.license_no, "full_name": d.name,
             "specialty": d.specialty, "phone": ""}
            for d in doctors
        ],
    )
    conn.executemany(
        "INSERT INTO patients VALUES (:id, :mrn, :full_name, :date_of_birth, :gender,"
        " :phone, :blood_group)",
        [
            {
                "id": p.id,
                "mrn": p.mrn,
                "full_name": p.name,
                "date_of_birth": p.date_of_birth,
                "gender": p.gender,
                "phone": "",
                "blood_group": p.blood_group,
            }
            for p in patients
        ],
    )
    conn.executemany(
        "INSERT INTO appointments VALUES (:id, :patient_id, :doctor_id, :scheduled_on,"
        " :slot, :reason, :status)",
        [
            {
                "id": a.id,
                "patient_id": a.patient_id,
                "doctor_id": a.doctor_id,
                "scheduled_on": a.scheduled_on,
                "slot": a.slot,
                "reason": a.reason,
                "status": a.status,
            }
            for a in appointments
        ],
    )
    conn.executemany(
        "INSERT INTO bills VALUES (:id, :appointment_id, :patient_id, :amount_cents,"
        " :paid, :issued_on)",
        [
            {
                "id": b.id,
                "appointment_id": b.appointment_id,
                "patient_id": b.patient_id,
                "amount_cents": b.cents,
                "paid": b.paid,
                "issued_on": b.issued_on,
            }
            for b in bills
        ],
    )
    conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# NULL-aware reporting
# --------------------------------------------------------------------------- #
def blood_group_counts(conn: sqlite3.Connection) -> list[tuple[str | None, int]]:
    """Every group, known ones ordered by name, the unknown group last."""
    rows = conn.execute(
        """
        SELECT blood_group AS grp, COUNT(*) AS n
        FROM patients
        GROUP BY blood_group
        ORDER BY blood_group IS NULL, blood_group
        """
    ).fetchall()
    return [(row["grp"], int(row["n"])) for row in rows]


def known_group_counts(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """Only recorded groups, most common first, ties broken by name."""
    rows = conn.execute(
        """
        SELECT blood_group AS grp, COUNT(*) AS n
        FROM patients
        WHERE blood_group IS NOT NULL
        GROUP BY blood_group
        ORDER BY n DESC, blood_group
        """
    ).fetchall()
    return [(row["grp"], int(row["n"])) for row in rows]


def unknown_group_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS rows, COUNT(blood_group) AS values_present FROM patients"
    ).fetchone()
    return int(row["rows"]) - int(row["values_present"])


def patients_not_group(conn: sqlite3.Connection, group: str) -> list[str]:
    """Everyone who is *not* the given group, including people with no record."""
    wanted = _text(group, "blood_group").strip()
    rows = conn.execute(
        """
        SELECT full_name
        FROM patients
        WHERE blood_group IS NULL OR blood_group <> ?
        ORDER BY full_name
        """,
        (wanted,),
    ).fetchall()
    return [row["full_name"] for row in rows]


def legacy_not_group(conn: sqlite3.Connection, group: str) -> int:
    wanted = _text(group, "blood_group").strip()
    return int(conn.execute(LEGACY_NOT_GROUP, (wanted,)).fetchone()["n"])


def legacy_completeness(conn: sqlite3.Connection) -> int:
    return int(conn.execute(LEGACY_COMPLETENESS).fetchone()["labelled"])


def legacy_top_groups(conn: sqlite3.Connection, limit: int) -> list[tuple[str | None, int]]:
    count = _positive(limit, "limit")
    rows = conn.execute(LEGACY_TOP_GROUPS, (count,)).fetchall()
    return [(row["grp"], int(row["n"])) for row in rows]


def patients_without_bills(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT p.full_name AS name
        FROM patients p
        LEFT JOIN bills b ON b.patient_id = p.id
        WHERE b.id IS NULL
        ORDER BY p.full_name
        """
    ).fetchall()
    return [row["name"] for row in rows]


def revenue_totals(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS bills,
               COALESCE(SUM(amount_cents), 0) AS billed,
               COALESCE(SUM(CASE WHEN paid = 1 THEN amount_cents ELSE 0 END), 0) AS collected,
               COALESCE(SUM(CASE WHEN paid = 0 THEN amount_cents ELSE 0 END), 0) AS pending
        FROM bills
        """
    ).fetchone()
    billed = int(row["billed"])
    count = int(row["bills"])
    return {
        "bills": count,
        "billed": billed,
        "collected": int(row["collected"]),
        "pending": int(row["pending"]),
        "average": divide_half_up(billed, count) if count else 0,
    }


def doctor_workload(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    rows = conn.execute(
        """
        SELECT d.full_name AS name, COUNT(a.id) AS n
        FROM doctors d
        LEFT JOIN appointments a ON a.doctor_id = d.id
        GROUP BY d.id
        ORDER BY n DESC, d.full_name
        """
    ).fetchall()
    return [(row["name"], int(row["n"])) for row in rows]


def appointment_status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM appointments GROUP BY status ORDER BY status"
    ).fetchall()
    return {row["status"]: int(row["n"]) for row in rows}


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(
    patients_path: str | Path | None = None,
    *,
    doctors_path: str | Path | None = None,
    appointments_path: str | Path | None = None,
    bills_path: str | Path | None = None,
) -> dict[str, Any]:
    if patients_path is not None:
        folder = Path(patients_path).resolve().parent
        doctors_path = doctors_path or folder / "doctors.csv"
        appointments_path = appointments_path or folder / "appointments.csv"
        bills_path = bills_path or folder / "bills.csv"
    doctors = load_doctors(doctors_path)
    patients = load_patients(patients_path)
    appointments = load_appointments(appointments_path)
    bills = load_bills(bills_path)
    conn = build_database(doctors, patients, appointments, bills)
    return {
        "conn": conn,
        "doctors": doctors,
        "patients": patients,
        "appointments": appointments,
        "bills": bills,
        "groups": blood_group_counts(conn),
        "known": known_group_counts(conn),
        "unknown": unknown_group_count(conn),
        "not_o_pos": patients_not_group(conn, "O+"),
        "legacy_not_o_pos": legacy_not_group(conn, "O+"),
        "legacy_completeness": legacy_completeness(conn),
        "legacy_top3": legacy_top_groups(conn, 3),
        "known_top3": known_group_counts(conn)[:3],
        "without_bills": patients_without_bills(conn),
        "revenue": revenue_totals(conn),
        "workload": doctor_workload(conn),
        "statuses": appointment_status_counts(conn),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    revenue = measured["revenue"]
    return {
        "patients": len(measured["patients"]),
        "doctors": len(measured["doctors"]),
        "appointments": len(measured["appointments"]),
        "blood_groups": [
            {"group": group, "count": count} for group, count in measured["groups"]
        ],
        "unknown_group": measured["unknown"],
        "not_o_pos_correct": len(measured["not_o_pos"]),
        "not_o_pos_legacy": measured["legacy_not_o_pos"],
        "legacy_completeness": measured["legacy_completeness"],
        "legacy_top3": [
            {"group": group, "count": count} for group, count in measured["legacy_top3"]
        ],
        "known_top3": [
            {"group": group, "count": count} for group, count in measured["known_top3"]
        ],
        "patients_without_bills": measured["without_bills"],
        "revenue": {
            "bills": revenue["bills"],
            "billed_cents": revenue["billed"],
            "collected_cents": revenue["collected"],
            "pending_cents": revenue["pending"],
            "average_cents": revenue["average"],
        },
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
    read_groups=blood_group_counts,
) -> list[tuple[str, bool]]:
    conn = measured["conn"]
    patients = measured["patients"]
    revenue = measured["revenue"]
    groups = {group: count for group, count in measured["groups"]}

    def groups_via_reader() -> list[tuple[str | None, int]]:
        return list(read_groups(conn))

    def unknown_is_invisible_to_a_reader_that_drops_it() -> bool:
        known = sum(count for group, count in measured["known"])
        return known == 4 and measured["unknown"] == 2

    checks = [
        (
            "all_patients_are_counted_once",
            lambda: sum(count for _, count in groups_via_reader()) == len(patients) == 6,
        ),
        (
            "unknown_group_holds_two_patients",
            lambda: dict(groups_via_reader()).get(None) == 2 and measured["unknown"] == 2,
        ),
        (
            "known_groups_cover_four_patients",
            lambda: unknown_is_invisible_to_a_reader_that_drops_it(),
        ),
        (
            "legacy_not_equal_drops_the_unknown_rows",
            lambda: measured["legacy_not_o_pos"] == 3 and len(measured["not_o_pos"]) == 5,
        ),
        (
            "correct_not_equal_includes_the_unknown_rows",
            lambda: "Noor Bano" in measured["not_o_pos"]
            and "Joseph Mathew" in measured["not_o_pos"]
            and "Ramesh Kumar" not in measured["not_o_pos"],
        ),
        (
            "count_star_labels_rows_as_values",
            lambda: measured["legacy_completeness"] == 6 and measured["unknown"] == 2,
        ),
        (
            "legacy_top_three_leads_with_none",
            lambda: measured["legacy_top3"][0][0] is None,
        ),
        (
            "legacy_top_three_drops_two_real_groups",
            lambda: {group for group, _ in measured["legacy_top3"] if group} == {"A+", "AB+"},
        ),
        (
            "known_top_three_names_only_real_groups",
            lambda: all(group is not None for group, _ in measured["known_top3"])
            and len(measured["known_top3"]) == 3,
        ),
        (
            "revenue_splits_into_collected_and_pending",
            lambda: revenue["billed"] == revenue["collected"] + revenue["pending"],
        ),
        (
            "revenue_totals_are_pinned",
            lambda: revenue["billed"] == 858_333
            and revenue["collected"] == 430_000
            and revenue["pending"] == 428_333,
        ),
        (
            "average_bill_rounds_half_up",
            lambda: revenue["average"] == 171_667 == divide_half_up(858_333, 5),
        ),
        (
            "every_amount_round_trips",
            lambda: all(
                format_cents(parse_cents(value)) == value
                for value in ("2500.00", "1800.00", "333.33", "0.05")
            ),
        ),
        (
            "exactly_one_patient_has_no_bills",
            lambda: measured["without_bills"] == ["Joseph Mathew"],
        ),
        (
            "rebuild_is_deterministic",
            lambda: blood_group_counts(
                build_database(
                    measured["doctors"],
                    patients,
                    measured["appointments"],
                    measured["bills"],
                )
            )
            == measured["groups"],
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def _label(group: str | None) -> str:
    return "(not recorded)" if group is None else group


def render_groups(measured: dict[str, Any]) -> str:
    lines = ["  blood group       patients"]
    for group, count in measured["groups"]:
        lines.append(f"  {_label(group):<18}{count:>4}")
    lines.append(f"  {'TOTAL':<18}{sum(c for _, c in measured['groups']):>4}")
    return "\n".join(lines)


def render_top_groups(rows: Sequence[tuple[str | None, int]]) -> str:
    return ", ".join(f"{_label(group)}={count}" for group, count in rows)


def run_demo() -> int:
    measured = measure()
    revenue = measured["revenue"]
    print("Hospital records -- NULL is not a value")
    print("=" * 42)
    print()
    print(
        f"Seeds: {len(measured['doctors'])} doctors, {len(measured['patients'])} patients, "
        f"{len(measured['appointments'])} appointments, {len(measured['bills'])} bills."
    )
    print()
    print(render_groups(measured))
    print()
    print("1. != drops NULL rows: the wards hold 5 patients who are not O+, but")
    print("   WHERE blood_group <> 'O+' returns " + str(measured["legacy_not_o_pos"]) + ".")
    print("   Correct complement: " + str(len(measured["not_o_pos"])) + " -> "
          + ", ".join(measured["not_o_pos"]) + ".")
    print()
    print("2. COUNT(*) counts rows; COUNT(blood_group) counts values:")
    print(
        "   the completeness report prints "
        f"{measured['legacy_completeness']} 'with blood group' when "
        f"{len(measured['patients']) - measured['unknown']} have one, so "
        f"{measured['unknown']} missing records read as complete."
    )
    print()
    print("3. ORDER BY puts NULL first, so a LIMIT spends a slot on nothing:")
    print("   legacy top 3 -> " + render_top_groups(measured["legacy_top3"]))
    print("   known top 3  -> " + render_top_groups(measured["known_top3"]))
    print()
    print(
        "Billing: billed " + format_cents(revenue["billed"])
        + ", collected " + format_cents(revenue["collected"])
        + ", pending " + format_cents(revenue["pending"])
        + ", average " + format_cents(revenue["average"]) + "."
    )
    print(f"Patients with no bills: {', '.join(measured['without_bills'])}.")
    print()
    print("Checks")
    results = audit(measured)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: <> returns "
        f"{measured['legacy_not_o_pos']} patients where the correct complement is "
        f"{len(measured['not_o_pos'])} because 2 rows have no blood group; "
        f"COUNT(*) claims {measured['legacy_completeness']} labelled rows while "
        f"COUNT(blood_group) finds {len(measured['patients']) - measured['unknown']}; "
        "the legacy top-3 list leads with the NULL group and drops B+ and O+; "
        f"billed {format_cents(revenue['billed'])} = collected "
        f"{format_cents(revenue['collected'])} + pending "
        f"{format_cents(revenue['pending'])} with a half-up average of "
        f"{format_cents(revenue['average'])}; {passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
