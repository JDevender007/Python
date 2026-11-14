"""Tests for Patient_Entry_System: dates, records, CSV, duplicates, CLI."""

from __future__ import annotations

import csv
import datetime
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from patients import (                                    # noqa: E402
    COLUMNS,
    DATA_FILE,
    EXCEL_EPOCH,
    LEGACY_FILE,
    LEGACY_HEADER,
    MAX_AGE,
    Duplicate,
    Patient,
    PatientError,
    admitted_between,
    age_summary,
    by_diagnosis,
    by_gender,
    dedupe,
    diagnosis_counts,
    find_duplicates,
    gender_counts,
    legacy_header_fields,
    older_than,
    parse_date,
    read_csv,
    render_patient,
    render_table,
    reread_legacy,
    run_demo,
    serial_to_date,
    stats,
    validate_header,
    write_csv,
)

DAY = datetime.date
GOOD = {"patient_id": "16", "name": "Test", "age": "30",
        "gender": "Female", "diagnosis": "Fever",
        "admitted": "2025-02-01"}


def row(**overrides) -> dict:
    data = dict(GOOD)
    data.update(overrides)
    return data


@pytest.fixture()
def patients() -> list[Patient]:
    return read_csv()


# --------------------------------------------------------------------------- #
# Excel serials
# --------------------------------------------------------------------------- #
def test_serial_one_is_the_first_day_of_1900():
    assert serial_to_date(1) == DAY(1900, 1, 1)


def test_serial_fiftynine_is_the_end_of_february():
    assert serial_to_date(59) == DAY(1900, 2, 28)


def test_serial_sixty_is_the_fake_leap_day():
    # Excel keeps 1900-02-29 as serial 60; it never existed
    assert serial_to_date(60) == DAY(1900, 2, 28)


def test_serial_sixtynone_is_the_first_of_march():
    assert serial_to_date(61) == DAY(1900, 3, 1)


def test_serial_of_a_modern_date():
    assert serial_to_date(45292) == DAY(2024, 1, 1)


def test_serial_from_the_legacy_file():
    assert serial_to_date(45667) == DAY(2025, 1, 10)


def test_serial_accepts_a_numeric_string():
    assert serial_to_date("45667") == DAY(2025, 1, 10)


def test_serial_refuses_zero():
    with pytest.raises(PatientError, match="before Excel"):
        serial_to_date(0)


def test_serial_refuses_a_negative():
    with pytest.raises(PatientError, match="before Excel"):
        serial_to_date(-5)


def test_serial_refuses_a_fraction():
    with pytest.raises(PatientError, match="whole serial"):
        serial_to_date(45667.5)


def test_serial_refuses_a_boolean():
    with pytest.raises(PatientError, match="boolean"):
        serial_to_date(True)


def test_serial_refuses_a_word():
    with pytest.raises(PatientError, match="not an Excel serial"):
        serial_to_date("soon")


def test_serial_refuses_a_date_past_9999():
    with pytest.raises(PatientError, match="past"):
        serial_to_date(3000000)


def test_excel_epoch_constant():
    assert EXCEL_EPOCH == DAY(1899, 12, 30)


# --------------------------------------------------------------------------- #
# Date parsing
# --------------------------------------------------------------------------- #
def test_parse_iso():
    assert parse_date("2025-01-10") == DAY(2025, 1, 10)


def test_parse_day_first():
    assert parse_date("10-01-2025") == DAY(2025, 1, 10)


def test_day_first_differs_from_month_first():
    american = datetime.datetime.strptime("10-01-2025", "%m-%d-%Y").date()
    assert american == DAY(2025, 10, 1)
    assert parse_date("10-01-2025") != american


def test_parse_a_date_object():
    assert parse_date(DAY(2025, 1, 10)) == DAY(2025, 1, 10)


def test_parse_a_datetime():
    assert parse_date(datetime.datetime(2025, 1, 10, 8, 30)) == DAY(2025, 1, 10)


def test_parse_an_integer_serial():
    assert parse_date(45667) == DAY(2025, 1, 10)


def test_parse_a_serial_string():
    assert parse_date("45667") == DAY(2025, 1, 10)


def test_parse_strips_space():
    assert parse_date("  2025-01-10 ") == DAY(2025, 1, 10)


@pytest.mark.parametrize("bad", ["10/01/2025", "2025-1-10", "31-02-2025",
                                 "", "soon"])
def test_parse_refuses_bad_shapes(bad):
    with pytest.raises(PatientError):
        parse_date(bad)


def test_parse_refuses_a_boolean():
    with pytest.raises(PatientError, match="boolean"):
        parse_date(False)


def test_parse_refuses_a_list():
    with pytest.raises(PatientError, match="must be a string"):
        parse_date(["2025-01-10"])


# --------------------------------------------------------------------------- #
# Patients
# --------------------------------------------------------------------------- #
def test_patient_accepts_a_good_row():
    patient = Patient.from_row(GOOD)
    assert patient.patient_id == 16 and patient.age == 30
    assert patient.admitted == DAY(2025, 2, 1)


def test_patient_trims_name_and_diagnosis():
    patient = Patient(1, "  Ann  ", 30, "Female", "  Fever  ", "2025-01-01")
    assert patient.name == "Ann" and patient.diagnosis == "Fever"


def test_patient_row_round_trip():
    patient = Patient.from_row(GOOD)
    assert Patient.from_row(patient.to_row()) == patient


def test_patient_refuses_id_zero():
    with pytest.raises(PatientError, match="positive"):
        Patient(0, "A", 30, "Female", "Fever", "2025-01-01")


def test_patient_refuses_a_non_integer_id():
    with pytest.raises(PatientError, match="must be an integer"):
        Patient("1", "A", 30, "Female", "Fever", "2025-01-01")  # type: ignore[arg-type]


def test_patient_refuses_a_blank_name():
    with pytest.raises(PatientError, match="name must not be empty"):
        Patient(1, "  ", 30, "Female", "Fever", "2025-01-01")


def test_patient_refuses_a_negative_age():
    with pytest.raises(PatientError, match="outside"):
        Patient(1, "A", -1, "Female", "Fever", "2025-01-01")


def test_patient_refuses_an_impossible_age():
    with pytest.raises(PatientError, match="outside"):
        Patient(1, "A", MAX_AGE + 1, "Female", "Fever", "2025-01-01")


def test_patient_accepts_the_boundary_ages():
    assert Patient(1, "A", 0, "Female", "Fever", "2025-01-01").age == 0
    assert Patient(2, "B", MAX_AGE, "Male", "Fever",
                   "2025-01-01").age == MAX_AGE


def test_patient_refuses_an_unknown_gender():
    with pytest.raises(PatientError, match="not one of"):
        Patient(1, "A", 30, "Other", "Fever", "2025-01-01")


def test_patient_refuses_a_blank_diagnosis():
    with pytest.raises(PatientError, match="diagnosis must not be empty"):
        Patient(1, "A", 30, "Female", " ", "2025-01-01")


def test_patient_normalises_the_date():
    assert Patient(1, "A", 30, "Female", "Fever", 45667).admitted == \
        DAY(2025, 1, 10)


def test_from_row_refuses_a_missing_field():
    data = dict(GOOD)
    del data["age"]
    with pytest.raises(PatientError, match="missing age"):
        Patient.from_row(data)


def test_from_row_refuses_an_unknown_field():
    with pytest.raises(PatientError, match="unknown column"):
        Patient.from_row(row(extra="x"))


def test_from_row_refuses_a_non_mapping():
    with pytest.raises(PatientError, match="mapping"):
        Patient.from_row(["1", "Ann"])


def test_from_row_refuses_a_non_numeric_age():
    with pytest.raises(PatientError, match="whole numbers"):
        Patient.from_row(row(age="thirty"))


def test_from_row_refuses_a_non_numeric_id():
    with pytest.raises(PatientError, match="whole numbers"):
        Patient.from_row(row(patient_id="one"))


# --------------------------------------------------------------------------- #
# Headers
# --------------------------------------------------------------------------- #
def test_validate_header_accepts_the_canonical_names():
    assert validate_header(list(COLUMNS)) == COLUMNS


def test_validate_header_strips_names():
    assert validate_header([" patient_id ", "name"]) == ("patient_id", "name")


def test_validate_header_refuses_a_trailing_empty_name():
    with pytest.raises(PatientError, match="trailing tab"):
        validate_header(["a", "b", ""])


def test_validate_header_refuses_an_inner_empty_name():
    with pytest.raises(PatientError, match="empty name"):
        validate_header(["a", "", "b"])


def test_validate_header_refuses_a_duplicate_name():
    with pytest.raises(PatientError, match="repeats"):
        validate_header(["a", "b", "a"])


def test_validate_header_refuses_a_non_sequence():
    with pytest.raises(PatientError, match="sequence"):
        validate_header("a,b")


def test_legacy_header_splits_into_seven_names():
    fields = legacy_header_fields()
    assert len(fields) == 7 and fields[-1] == ""
    assert fields[5] == "AdmissionDate"


def test_legacy_header_constant_ends_with_a_tab():
    assert LEGACY_HEADER.endswith("\t")


# --------------------------------------------------------------------------- #
# CSV reading
# --------------------------------------------------------------------------- #
def test_bundled_file_has_fifteen_patients(patients):
    assert len(patients) == 15


def test_bundled_ids_are_one_to_fifteen(patients):
    assert [patient.patient_id for patient in patients] == list(range(1, 16))


def test_bundled_first_and_last_names(patients):
    assert patients[0].name == "John Smith"
    assert patients[-1].name == "Ethan Clark"


def test_bundled_dates_are_iso(patients):
    assert all(patient.admitted.year == 2025 for patient in patients)


def test_read_csv_refuses_a_missing_file(tmp_path):
    with pytest.raises(PatientError, match="not found"):
        read_csv(tmp_path / "nope.csv")


def test_read_csv_refuses_an_empty_file(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(PatientError, match="is empty"):
        read_csv(path)


def test_read_csv_refuses_a_file_without_records(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text(",".join(COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(PatientError, match="no patient records"):
        read_csv(path)


def test_read_csv_refuses_the_wrong_header(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text("id,name,age,gender,diagnosis,admitted\n"
                    "1,Ann,30,Female,Fever,2025-01-01\n", encoding="utf-8")
    with pytest.raises(PatientError, match="expected"):
        read_csv(path)


def test_read_csv_names_the_line_of_a_bad_record(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text(",".join(COLUMNS) + "\n"
                    "1,Ann,30,Female,Fever,2025-01-01\n"
                    "2,Bob,thirty,Male,Fever,2025-01-02\n", encoding="utf-8")
    with pytest.raises(PatientError, match="line 3"):
        read_csv(path)


def test_read_csv_refuses_a_row_with_too_few_fields(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text(",".join(COLUMNS) + "\n"
                    "1,Ann,30,Female\n", encoding="utf-8")
    with pytest.raises(PatientError, match="expected 6"):
        read_csv(path)


def test_read_csv_skips_blank_lines(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text(",".join(COLUMNS) + "\n"
                    "\n"
                    "1,Ann,30,Female,Fever,2025-01-01\n"
                    "\n", encoding="utf-8")
    assert len(read_csv(path)) == 1


def test_read_csv_skips_comments(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text("# a note\n" + ",".join(COLUMNS) + "\n"
                    "1,Ann,30,Female,Fever,2025-01-01\n", encoding="utf-8")
    assert len(read_csv(path)) == 1


def test_read_csv_accepts_quoted_commas(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text(",".join(COLUMNS) + "\n"
                    '1,"Smith, Ann",30,Female,Fever,2025-01-01\n',
                    encoding="utf-8")
    assert read_csv(path)[0].name == "Smith, Ann"


# --------------------------------------------------------------------------- #
# CSV writing
# --------------------------------------------------------------------------- #
def test_write_uses_the_canonical_header(tmp_path, patients):
    path = tmp_path / "out.csv"
    write_csv(path, patients)
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert header == ",".join(COLUMNS)


def test_write_has_no_tabs(tmp_path, patients):
    path = tmp_path / "out.csv"
    write_csv(path, patients)
    assert "\t" not in path.read_text(encoding="utf-8")


def test_write_round_trips(tmp_path, patients):
    path = tmp_path / "out.csv"
    write_csv(path, patients)
    assert read_csv(path) == patients


def test_write_is_byte_identical_on_a_second_write(tmp_path, patients):
    path = tmp_path / "out.csv"
    write_csv(path, patients)
    first = path.read_bytes()
    write_csv(path, read_csv(path))
    assert path.read_bytes() == first


def test_write_creates_directories(tmp_path, patients):
    path = tmp_path / "a" / "b" / "out.csv"
    write_csv(path, patients)
    assert path.is_file()


def test_write_leaves_no_temporary_file(tmp_path, patients):
    write_csv(tmp_path / "out.csv", patients)
    assert [item.name for item in tmp_path.iterdir()] == ["out.csv"]


def test_write_writes_iso_dates(tmp_path):
    write_csv(tmp_path / "out.csv",
              [Patient(1, "A", 30, "Female", "Fever", 45667)])
    assert "2025-01-10" in (tmp_path / "out.csv").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# The legacy file
# --------------------------------------------------------------------------- #
def test_legacy_file_exists_and_is_named_for_its_origin():
    assert LEGACY_FILE.name == "legacy_patients.csv"
    assert LEGACY_FILE.exists()


def test_legacy_header_has_an_empty_seventh_name():
    legacy = reread_legacy()
    assert len(legacy["header"]) == 7
    assert legacy["header"][-1] == ""


def test_legacy_file_has_fifteen_rows_of_seven_fields():
    legacy = reread_legacy()
    assert len(legacy["rows"]) == 15
    assert all(len(item) == 7 for item in legacy["rows"])


def test_legacy_date_column_is_a_serial():
    assert reread_legacy()["date_column"] == "45667"


def test_legacy_seventh_column_is_a_human_date():
    assert reread_legacy()["seventh_column"] == "10-01-2025"


def test_both_legacy_date_columns_agree_everywhere():
    legacy = reread_legacy()
    for item in legacy["rows"]:
        assert serial_to_date(item[5]) == parse_date(item[6])


def test_reread_legacy_refuses_a_missing_file(tmp_path):
    with pytest.raises(PatientError, match="not found"):
        reread_legacy(tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# Duplicates
# --------------------------------------------------------------------------- #
def test_bundled_file_has_no_duplicates(patients):
    assert find_duplicates(patients) == []


def test_an_exact_duplicate_is_reported_but_not_conflicting(patients):
    twin = Patient(1, "John Smith", 45, "Male", "Fever", "2025-01-10")
    found = find_duplicates(patients + [twin])
    assert len(found) == 1 and found[0].conflict is False


def test_a_conflicting_duplicate_is_flagged(patients):
    clash = Patient(1, "J. Smith", 46, "Male", "Fever", "2025-01-10")
    found = find_duplicates(patients + [clash])
    assert found[0].conflict is True


def test_two_extra_rows_are_grouped(patients):
    extra = [Patient(1, "A", 40, "Male", "Fever", "2025-01-10"),
             Patient(1, "B", 41, "Male", "Fever", "2025-01-10")]
    found = find_duplicates(patients + extra)
    assert len(found[0].extra) == 2


def test_dedupe_keeps_the_file_order(patients):
    extra = Patient(3, "Someone Else", 20, "Female", "Fever", "2025-01-12")
    kept = dedupe(patients + [extra])
    assert len(kept) == 15
    assert kept[2].name == "David Lee"


def test_dedupe_of_an_empty_list():
    assert dedupe([]) == []


def test_duplicate_dataclass_reports_its_extra_rows():
    kept = Patient(1, "A", 30, "Female", "Fever", "2025-01-01")
    other = Patient(1, "B", 31, "Female", "Fever", "2025-01-01")
    duplicate = Duplicate(1, kept, (other,))
    assert duplicate.conflict is True


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
def test_older_than_is_strict(patients):
    assert len(older_than(patients, 40)) == 8
    assert len(older_than(patients, 61)) == 0


def test_older_than_refuses_non_integers(patients):
    with pytest.raises(PatientError, match="must be an integer"):
        older_than(patients, "40")                           # type: ignore[arg-type]


def test_by_gender_counts(patients):
    assert len(by_gender(patients, "Female")) == 7
    assert len(by_gender(patients, "Male")) == 8


def test_by_gender_refuses_an_unknown_value(patients):
    with pytest.raises(PatientError, match="not one of"):
        by_gender(patients, "Other")


def test_by_diagnosis_is_case_insensitive(patients):
    assert len(by_diagnosis(patients, "diabetes")) == 2


def test_by_diagnosis_of_a_missing_condition_is_empty(patients):
    assert by_diagnosis(patients, "Plague") == []


def test_by_diagnosis_refuses_a_blank(patients):
    with pytest.raises(PatientError, match="must not be empty"):
        by_diagnosis(patients, "  ")


def test_admitted_between_is_inclusive(patients):
    assert len(admitted_between(patients, "2025-01-12", "2025-01-16")) == 5


def test_admitted_between_a_single_day(patients):
    assert len(admitted_between(patients, "2025-01-10", "2025-01-10")) == 1


def test_admitted_between_refuses_a_reversed_range(patients):
    with pytest.raises(PatientError, match="before the start"):
        admitted_between(patients, "2025-01-20", "2025-01-10")


def test_admitted_between_accepts_a_serial(patients):
    assert len(admitted_between(patients, 45667, 45667)) == 1


def test_gender_counts_include_both_totals(patients):
    assert gender_counts(patients) == {"Female": 7, "Male": 8}


def test_diagnosis_counts_are_sorted_by_count_then_name(patients):
    counts = diagnosis_counts(patients)
    assert list(counts)[:4] == ["Asthma", "Diabetes", "Fever",
                               "Hypertension"]
    assert sum(counts.values()) == 15


def test_age_summary_of_the_bundled_file(patients):
    summary = age_summary(patients)
    assert summary["count"] == 15
    assert summary["mean"] == 41.33
    assert summary["median"] == 41
    assert summary["min"] == 26 and summary["max"] == 61


def test_age_summary_of_an_even_count_uses_a_half_median():
    rows = [Patient(1, "A", 20, "Female", "Fever", "2025-01-01"),
            Patient(2, "B", 30, "Male", "Fever", "2025-01-01")]
    assert age_summary(rows)["median"] == 25


def test_age_summary_of_nothing_is_all_none():
    assert age_summary([]) == {"count": 0, "mean": None, "median": None,
                               "min": None, "max": None}


def test_stats_of_the_bundled_file(patients):
    summary = stats(patients)
    assert summary["patients"] == 15
    assert summary["first_admission"] == DAY(2025, 1, 10)
    assert summary["last_admission"] == DAY(2025, 1, 24)


def test_stats_of_nothing_has_null_dates():
    summary = stats([])
    assert summary["first_admission"] is None
    assert summary["last_admission"] is None


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_render_patient_shows_every_field(patients):
    text = render_patient(patients[0])
    assert "John Smith" in text and "45" in text
    assert "2025-01-10" in text


def test_render_table_has_a_header(patients):
    assert "diagnosis" in render_table(patients).splitlines()[0]


def test_render_table_of_nothing_says_so():
    assert render_table([]).endswith("(no patients)")


# --------------------------------------------------------------------------- #
# Demo and CLI
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_mentions_the_serial_and_the_empty_column(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "45667" in out and "trailing tab" in out


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_the_bundled_patients(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "John Smith" in out and "15 patient(s)" in out
    assert "41.33" in out


def test_cli_stats(capsys):
    assert cli.main(["--stats"]) == 0
    out = capsys.readouterr().out
    assert "patients     15" in out
    assert "2025-01-10 .. 2025-01-24" in out


def test_cli_older_than(capsys):
    assert cli.main(["--older-than", "40"]) == 0
    out = capsys.readouterr().out
    assert "8 record(s)" in out and "Daniel Thomas" in out


def test_cli_gender(capsys):
    assert cli.main(["--gender", "Female"]) == 0
    assert "7 record(s)" in capsys.readouterr().out


def test_cli_diagnosis(capsys):
    assert cli.main(["--diagnosis", "Diabetes"]) == 0
    out = capsys.readouterr().out
    assert "2 record(s)" in out and "Sarah Jones" in out


def test_cli_between(capsys):
    assert cli.main(["--between", "2025-01-12:2025-01-16"]) == 0
    out = capsys.readouterr().out
    assert "5 record(s)" in out


def test_cli_between_refuses_a_malformed_range(capsys):
    assert cli.main(["--between", "nocolon"]) == 2
    assert "expected START:END" in capsys.readouterr().err


def test_cli_duplicates(capsys):
    assert cli.main(["--duplicates"]) == 0
    assert "no repeated patient ids" in capsys.readouterr().out


def test_cli_duplicates_reports_a_conflict(tmp_path, capsys):
    path = tmp_path / "p.csv"
    path.write_text(",".join(COLUMNS) + "\n"
                    "1,Ann,30,Female,Fever,2025-01-01\n"
                    "1,Bob,31,Male,Fever,2025-01-02\n", encoding="utf-8")
    assert cli.main(["--file", str(path), "--duplicates"]) == 0
    out = capsys.readouterr().out
    assert "conflicting" in out


def test_cli_write_normalises_and_reports(tmp_path, capsys):
    target = tmp_path / "clean.csv"
    assert cli.main(["--write", str(target)]) == 0
    assert "written to clean.csv" in capsys.readouterr().out
    assert target.is_file()


def test_cli_legacy_mode(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "45667" in out and "10-01-2025" in out


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.csv"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_json_list(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "list"
    assert len(payload["rows"]) == 15


def test_cli_json_stats(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--stats", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["stats"]["ages"]["median"] == 41


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--stats", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
