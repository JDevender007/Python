"""Tests for the hospital records lab: NULL semantics and integer-cent money."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import hospital  # noqa: E402
import main as cli  # noqa: E402
from hospital import (  # noqa: E402
    Appointment,
    Bill,
    HospitalError,
    Patient,
    appointment_status_counts,
    audit,
    blood_group_counts,
    build_database,
    divide_half_up,
    doctor_workload,
    format_cents,
    is_iso_date,
    is_slot,
    known_group_counts,
    legacy_completeness,
    legacy_not_group,
    legacy_top_groups,
    load_appointments,
    load_bills,
    load_doctors,
    load_patients,
    measure,
    parse_cents,
    patients_not_group,
    patients_without_bills,
    report,
    revenue_totals,
    run_demo,
    unknown_group_count,
)


# --------------------------------------------------------------------------- #
# money
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,cents",
    [
        ("2500.00", 250_000),
        ("1800.00", 180_000),
        ("333.33", 33_333),
        ("0.05", 5),
        ("8.20", 820),
        ("7", 700),
        ("7.5", 750),
        ("+1.00", 100),
        ("-1.05", -105),
        (" 12.30 ", 1230),
    ],
)
def test_parse_cents_is_exact(text, cents):
    assert parse_cents(text) == cents


@pytest.mark.parametrize("bad", ["", "  ", "1.2.3", "1.234", "abc", "1.a5", ".", "1,"])
def test_parse_cents_refuses_malformed(bad):
    with pytest.raises(HospitalError):
        parse_cents(bad)


def test_parse_cents_refuses_non_text():
    with pytest.raises(HospitalError, match="must be text"):
        parse_cents(2500)


def test_parse_cents_names_the_decimal_places():
    with pytest.raises(HospitalError, match="2 decimal places"):
        parse_cents("1.234")


@pytest.mark.parametrize(
    "cents,text", [(0, "0.00"), (5, "0.05"), (100, "1.00"), (-105, "-1.05"), (171_667, "1716.67")]
)
def test_format_cents(cents, text):
    assert format_cents(cents) == text


@pytest.mark.parametrize("bad", [True, 1.5, "10"])
def test_format_cents_refuses_non_integers(bad):
    with pytest.raises(HospitalError, match="must be an integer"):
        format_cents(bad)


@pytest.mark.parametrize(
    "top,bottom,expected", [(858_333, 5, 171_667), (5, 2, 3), (1, 3, 0), (2, 3, 1), (-5, 2, -3)]
)
def test_divide_half_up(top, bottom, expected):
    assert divide_half_up(top, bottom) == expected


@pytest.mark.parametrize("bottom", [0, -1])
def test_divide_half_up_refuses_bad_denominators(bottom):
    with pytest.raises(HospitalError, match="denominator must be positive"):
        divide_half_up(1, bottom)


# --------------------------------------------------------------------------- #
# dates and slots
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", ["1985-04-12", "2026-01-05", "1996-02-29"])
def test_iso_dates_are_accepted(text):
    assert is_iso_date(text) is True


@pytest.mark.parametrize("text", ["1985-4-12", "2026-13-01", "2026-01-32", "12/04/1985", "", "2026-01-0x"])
def test_iso_dates_are_refused(text):
    assert is_iso_date(text) is False


@pytest.mark.parametrize("text", ["09:00", "23:59", "00:00"])
def test_slots_are_accepted(text):
    assert is_slot(text) is True


@pytest.mark.parametrize("text", ["9:00", "24:00", "09:60", "09-00", ""])
def test_slots_are_refused(text):
    assert is_slot(text) is False


# --------------------------------------------------------------------------- #
# loaders
# --------------------------------------------------------------------------- #
def test_load_patients_keeps_missing_blood_groups_as_none():
    patients = load_patients()
    assert len(patients) == 6
    assert patients[3].blood_group == "AB+"
    assert patients[4].blood_group is None
    assert patients[5].blood_group is None


def test_load_doctors_from_bundled_seed():
    doctors = load_doctors()
    assert [d.name for d in doctors] == ["Dr. Kavita Rao", "Dr. Arjun Menon", "Dr. Sunita Verma"]


def test_load_appointments_from_bundled_seed():
    appointments = load_appointments()
    assert len(appointments) == 5
    assert appointments[0].slot == "09:00"
    assert appointments[0].status == "completed"


def test_load_bills_parses_money_and_null_appointments():
    bills = load_bills()
    assert [b.cents for b in bills] == [250_000, 180_000, 320_000, 75_000, 33_333]
    assert bills[0].appointment_id == 1
    assert bills[3].appointment_id is None


def test_loader_reports_a_missing_file(tmp_path):
    with pytest.raises(HospitalError, match="file not found"):
        load_patients(tmp_path / "nope.csv")


def test_loader_reports_a_missing_column(tmp_path):
    path = tmp_path / "patients.csv"
    path.write_text("id,mrn,full_name\n1,MRN1,A\n", encoding="utf-8")
    with pytest.raises(HospitalError, match="missing column"):
        load_patients(path)


PATIENT_HEADER = "id,mrn,full_name,date_of_birth,gender,phone,blood_group\n"


def test_loader_refuses_an_unknown_gender(tmp_path):
    path = tmp_path / "patients.csv"
    path.write_text(PATIENT_HEADER + "1,MRN1,A,1990-01-01,Alien,1,O+\n", encoding="utf-8")
    with pytest.raises(HospitalError, match="gender must be one of"):
        load_patients(path)


def test_loader_refuses_a_bad_date_of_birth(tmp_path):
    path = tmp_path / "patients.csv"
    path.write_text(PATIENT_HEADER + "1,MRN1,A,01/01/1990,Male,1,O+\n", encoding="utf-8")
    with pytest.raises(HospitalError, match="date_of_birth must be YYYY-MM-DD"):
        load_patients(path)


def test_loader_refuses_duplicate_mrns(tmp_path):
    path = tmp_path / "patients.csv"
    path.write_text(
        PATIENT_HEADER
        + "1,MRN1,A,1990-01-01,Male,1,O+\n"
        + "2,MRN1,B,1991-01-01,Female,2,A+\n",
        encoding="utf-8",
    )
    with pytest.raises(HospitalError, match="MRNs must be unique"):
        load_patients(path)


APPOINTMENT_HEADER = "id,patient_id,doctor_id,scheduled_on,slot,reason,status\n"


def test_loader_refuses_an_unknown_status(tmp_path):
    path = tmp_path / "appointments.csv"
    path.write_text(APPOINTMENT_HEADER + "1,1,1,2026-01-01,09:00,X,waiting\n", encoding="utf-8")
    with pytest.raises(HospitalError, match="status must be one of"):
        load_appointments(path)


def test_loader_refuses_a_bad_slot(tmp_path):
    path = tmp_path / "appointments.csv"
    path.write_text(APPOINTMENT_HEADER + "1,1,1,2026-01-01,9:00,X,scheduled\n", encoding="utf-8")
    with pytest.raises(HospitalError, match="slot must be HH:MM"):
        load_appointments(path)


# --------------------------------------------------------------------------- #
# database and NULL-aware reports
# --------------------------------------------------------------------------- #
@pytest.fixture()
def seeded():
    doctors = load_doctors()
    patients = load_patients()
    appointments = load_appointments()
    bills = load_bills()
    conn = build_database(doctors, patients, appointments, bills)
    yield conn, doctors, patients, appointments, bills
    conn.close()


def test_build_database_rows(seeded):
    conn, _, _, _, _ = seeded
    assert conn.execute("SELECT COUNT(*) AS n FROM patients").fetchone()["n"] == 6
    assert conn.execute("SELECT COUNT(*) AS n FROM bills").fetchone()["n"] == 5


def test_build_database_refuses_unknown_patient(seeded):
    conn, doctors, patients, _, _ = seeded
    conn.close()
    bad = [Appointment(99, 99, 1, "2026-01-01", "09:00", "X", "scheduled")]
    with pytest.raises(HospitalError, match="unknown patient 99"):
        build_database(doctors, patients, bad, [])


def test_build_database_refuses_unknown_appointment_on_a_bill(seeded):
    _, doctors, patients, appointments, _ = seeded
    bad = [Bill(99, 404, 1, 100, 0, "2026-01-01")]
    with pytest.raises(HospitalError, match="unknown appointment 404"):
        build_database(doctors, patients, appointments, bad)


def test_blood_group_counts_put_the_unknown_group_last(seeded):
    conn, _, _, _, _ = seeded
    groups = blood_group_counts(conn)
    assert groups[-1] == (None, 2)
    assert [group for group, _ in groups[:-1]] == ["A+", "AB+", "B+", "O+"]


def test_known_group_counts_exclude_the_unknown_group(seeded):
    conn, _, _, _, _ = seeded
    groups = known_group_counts(conn)
    assert all(group is not None for group, _ in groups)
    assert sum(count for _, count in groups) == 4


def test_unknown_group_count(seeded):
    conn, _, _, _, _ = seeded
    assert unknown_group_count(conn) == 2


def test_legacy_not_equal_returns_three(seeded):
    conn, _, _, _, _ = seeded
    assert legacy_not_group(conn, "O+") == 3


def test_correct_not_equal_returns_five_including_unknown(seeded):
    conn, _, _, _, _ = seeded
    names = patients_not_group(conn, "O+")
    assert len(names) == 5
    assert "Noor Bano" in names and "Joseph Mathew" in names
    assert "Ramesh Kumar" not in names


def test_legacy_completeness_counts_every_row(seeded):
    conn, _, _, _, _ = seeded
    assert legacy_completeness(conn) == 6


def test_legacy_top_groups_puts_null_first(seeded):
    conn, _, _, _, _ = seeded
    rows = legacy_top_groups(conn, 3)
    assert rows[0] == (None, 2)
    assert {group for group, _ in rows if group} == {"A+", "AB+"}


def test_legacy_top_groups_refuses_a_bad_limit(seeded):
    conn, _, _, _, _ = seeded
    with pytest.raises(HospitalError, match="limit must be positive"):
        legacy_top_groups(conn, 0)


def test_patients_without_bills_uses_an_anti_join(seeded):
    conn, _, _, _, _ = seeded
    assert patients_without_bills(conn) == ["Joseph Mathew"]


def test_revenue_totals(seeded):
    conn, _, _, _, _ = seeded
    revenue = revenue_totals(conn)
    assert revenue["bills"] == 5
    assert revenue["billed"] == 858_333
    assert revenue["collected"] == 430_000
    assert revenue["pending"] == 428_333
    assert revenue["average"] == 171_667


def test_revenue_is_zero_when_there_are_no_bills():
    conn = build_database([], [], [], [])
    assert revenue_totals(conn)["average"] == 0


def test_doctor_workload(seeded):
    conn, _, _, _, _ = seeded
    assert doctor_workload(conn) == [("Dr. Arjun Menon", 2), ("Dr. Kavita Rao", 2), ("Dr. Sunita Verma", 1)]


def test_appointment_status_counts(seeded):
    conn, _, _, _, _ = seeded
    assert appointment_status_counts(conn) == {"completed": 2, "scheduled": 3}


# --------------------------------------------------------------------------- #
# measure and report
# --------------------------------------------------------------------------- #
def test_measure_pins_the_three_defects():
    measured = measure()
    assert measured["legacy_not_o_pos"] == 3
    assert len(measured["not_o_pos"]) == 5
    assert measured["legacy_completeness"] == 6
    assert measured["unknown"] == 2
    assert measured["legacy_top3"][0][0] is None


def test_measure_keeps_the_known_top_three_clean():
    measured = measure()
    assert len(measured["known_top3"]) == 3
    assert all(group is not None for group, _ in measured["known_top3"])


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "conn" not in text
    assert payload["not_o_pos_legacy"] == 3
    assert payload["not_o_pos_correct"] == 5
    assert payload["unknown_group"] == 2
    assert payload["revenue"]["billed_cents"] == 858_333


def test_measure_reads_siblings_from_the_patients_folder(tmp_path):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "doctors.csv").write_text("id,license_no,full_name,specialty,phone\n1,D1,Doc,GP,1\n", encoding="utf-8")
    (folder / "patients.csv").write_text(
        PATIENT_HEADER + "1,MRN1,A,1990-01-01,Male,1,O+\n", encoding="utf-8"
    )
    (folder / "appointments.csv").write_text(APPOINTMENT_HEADER, encoding="utf-8")
    (folder / "bills.csv").write_text(
        "id,appointment_id,patient_id,amount,paid,issued_on\n1,,1,10.00,0,2026-01-01\n",
        encoding="utf-8",
    )
    measured = measure(folder / "patients.csv")
    assert len(measured["patients"]) == 1
    assert measured["revenue"]["billed"] == 1000


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_audit_passes_every_check():
    results = audit(measure())
    assert len(results) >= 14
    assert all(ok for _, ok in results)


def test_audit_names_are_unique():
    names = [name for name, _ in audit(measure())]
    assert len(names) == len(set(names))


def test_audit_negative_control_reader_that_drops_nulls():
    def known_only(conn):
        return known_group_counts(conn)

    results = dict(audit(measure(), read_groups=known_only))
    assert results["all_patients_are_counted_once"] is False
    assert results["unknown_group_holds_two_patients"] is False


def test_audit_negative_control_tampered_revenue():
    measured = measure()
    measured["revenue"]["pending"] = 0
    results = dict(audit(measured))
    assert results["revenue_splits_into_collected_and_pending"] is False


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
    assert "8583.33" in out
    assert "1716.67" in out
    assert "returns 3" in out
    assert "(not recorded)=2" in out


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
    assert payload["not_o_pos_correct"] == 5


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such.csv"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_bad_amount_exits_two(tmp_path, capsys):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "doctors.csv").write_text("id,license_no,full_name,specialty,phone\n1,D1,Doc,GP,1\n", encoding="utf-8")
    (folder / "patients.csv").write_text(
        PATIENT_HEADER + "1,MRN1,A,1990-01-01,Male,1,O+\n", encoding="utf-8"
    )
    (folder / "appointments.csv").write_text(APPOINTMENT_HEADER, encoding="utf-8")
    (folder / "bills.csv").write_text(
        "id,appointment_id,patient_id,amount,paid,issued_on\n1,,1,1.234,0,2026-01-01\n",
        encoding="utf-8",
    )
    assert cli.main(["--file", str(folder / "patients.csv")]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_quiet_json_still_writes(tmp_path):
    target = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(target)]) == 0
    assert target.is_file()


def test_module_demo_entry_point():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        assert hospital.run_demo() == 0
    assert buffer.getvalue().strip().endswith("Demo completed successfully.")


def test_demo_writes_nothing_to_stderr():
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        run_demo()
    assert err.getvalue() == ""
