"""A patient registry: strict CSV, normalised dates, validated records.

The legacy program was PySpark:

    patients = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv("patient.csv")
    )
    ...
    patients = patients.dropDuplicates()
    report = patient_table.withColumn("ReportDate", current_date())

and the file it read looked like this:

    PatientID\tName\tAge\tGender\tDiagnosis\tAdmissionDate\t
    1\tJohn Smith\t45\tMale\tFever\t45667\t10-01-2025

Four problems that outlive the Spark dependency.

**1. The header ends in a tab.** ``"AdmissionDate\\t"`` is *seven* names, the
last of them empty. The data rows also have seven fields, so the real
admission date is read under a column called ``""`` and ``AdmissionDate`` is
``45667``.

**2. The admission date is an Excel serial number.** ``45667`` is 2025-01-10
in Excel's day-zero system (epoch 1899-12-30). It is a number, so
``inferSchema`` types the column as an integer and no date parsing happens at
all. The human date in the seventh column is a *second* copy of the same fact,
and the two disagree the moment either is edited.

**3. ``dropDuplicates()`` drops patients, not duplicates.** Two different
people who share a name, age and diagnosis are silently merged. Identity is
the id, and only the id.

**4. ``current_date()`` makes the report irreproducible.** The same input
produces different output tomorrow, so no result can be checked.

This module reads a CSV with a validated header, converts every date shape
(ISO, day-first, Excel serial) to ``YYYY-MM-DD``, validates each record, and
reports duplicates by id instead of deleting them. The bundled
``data/legacy_patients.csv`` is the original file, byte for byte, so the demo
can prove the misreading before it fixes it.

Standard library only -- no Spark, no JVM, no network.
"""

from __future__ import annotations

import csv
import datetime
import os
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "patients.csv"
LEGACY_FILE = (Path(__file__).resolve().parent.parent / "data"
               / "legacy_patients.csv")
DATE_FORMAT = "%Y-%m-%d"
EXCEL_EPOCH = datetime.date(1899, 12, 30)
GENDERS = ("Female", "Male")
COLUMNS = ("patient_id", "name", "age", "gender", "diagnosis", "admitted")
MAX_AGE = 120


class PatientError(ValueError):
    """A record, header or file that cannot be accepted."""


# --------------------------------------------------------------------------- #
# The legacy file
# --------------------------------------------------------------------------- #
LEGACY_HEADER = "PatientID\tName\tAge\tGender\tDiagnosis\tAdmissionDate\t"


def legacy_header_fields() -> list[str]:
    """The header split the way a tab-separated reader would split it."""
    return LEGACY_HEADER.split("\t")


def serial_to_date(serial) -> datetime.date:
    """Excel's day number to a date.

    Day zero is 1899-12-30, not 1900-01-01, because Excel keeps the
    non-existent 1900-02-29 as serial 60 for Lotus compatibility. Serial 60
    therefore *cannot* be represented: this function returns 1900-02-28 and
    says so, rather than inventing a date that never existed.
    """
    if isinstance(serial, bool):
        raise PatientError("an Excel serial must be a number, not a boolean")
    try:
        number = Decimal(str(serial))
    except (InvalidOperation, ValueError):
        raise PatientError(f"{serial!r} is not an Excel serial") from None
    if number != number.to_integral_value():
        raise PatientError(f"{serial!r} is not a whole serial number")
    days = int(number)
    if days < 1:
        raise PatientError(f"serial {days} is before Excel's day one")
    if days > 2958465:
        raise PatientError(f"serial {days} is past 9999-12-31")
    if days == 60:
        # 1900-02-29 does not exist; the honest answer is the day before.
        return datetime.date(1900, 2, 28)
    if days < 60:
        # Before the fake leap day, Excel's serial 1 is 1900-01-01, one day
        # after the plain 1899-12-30 epoch arithmetic would say.
        return EXCEL_EPOCH + datetime.timedelta(days=days + 1)
    return EXCEL_EPOCH + datetime.timedelta(days=days)


def parse_date(value) -> datetime.date:
    """ISO, day-first ``DD-MM-YYYY``, a date, or an Excel serial."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, bool):
        raise PatientError("a date must not be a boolean")
    if isinstance(value, (int, float)):
        return serial_to_date(value)
    if not isinstance(value, str):
        raise PatientError(f"date must be a string, got {type(value).__name__}")
    text = value.strip()
    if not text:
        raise PatientError("date must not be empty")

    for pattern in (DATE_FORMAT, "%d-%m-%Y"):
        try:
            parsed = datetime.datetime.strptime(text, pattern).date()
        except ValueError:
            continue
        if parsed.strftime(pattern) != text:
            continue                     # strptime accepts unpadded fields
        return parsed
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        raise PatientError(
            f"{text!r} is not ISO, day-first DD-MM-YYYY, or a serial"
        ) from None
    return serial_to_date(number)


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Patient:
    patient_id: int
    name: str
    age: int
    gender: str
    diagnosis: str
    admitted: datetime.date

    def __post_init__(self) -> None:
        if isinstance(self.patient_id, bool) or \
                not isinstance(self.patient_id, int):
            raise PatientError("patient_id must be an integer")
        if self.patient_id < 1:
            raise PatientError("patient_id must be positive")
        if not isinstance(self.name, str) or not self.name.strip():
            raise PatientError("name must not be empty")
        if isinstance(self.age, bool) or not isinstance(self.age, int):
            raise PatientError("age must be an integer")
        if not 0 <= self.age <= MAX_AGE:
            raise PatientError(f"age {self.age} is outside 0..{MAX_AGE}")
        if self.gender not in GENDERS:
            raise PatientError(
                f"gender {self.gender!r} is not one of {GENDERS}")
        if not isinstance(self.diagnosis, str) or not self.diagnosis.strip():
            raise PatientError("diagnosis must not be empty")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "diagnosis", self.diagnosis.strip())
        object.__setattr__(self, "admitted", parse_date(self.admitted))

    def to_row(self) -> dict[str, str]:
        return {"patient_id": str(self.patient_id), "name": self.name,
                "age": str(self.age), "gender": self.gender,
                "diagnosis": self.diagnosis,
                "admitted": self.admitted.strftime(DATE_FORMAT)}

    @staticmethod
    def from_row(row: dict) -> "Patient":
        if not isinstance(row, dict):
            raise PatientError("a row must be a mapping")
        missing = [name for name in COLUMNS if name not in row]
        if missing:
            raise PatientError(f"row is missing {missing[0]}")
        unknown = set(row) - set(COLUMNS)
        if unknown:
            raise PatientError(f"row has unknown column {sorted(unknown)[0]}")
        try:
            patient_id = int(str(row["patient_id"]).strip())
            age = int(str(row["age"]).strip())
        except ValueError:
            raise PatientError("patient_id and age must be whole numbers") \
                from None
        return Patient(patient_id, str(row["name"]), age, str(row["gender"]),
                       str(row["diagnosis"]), row["admitted"])


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def validate_header(fields) -> tuple[str, ...]:
    """Trim each name, then refuse empties and duplicates."""
    if not isinstance(fields, (list, tuple)):
        raise PatientError("header must be a sequence of names")
    names = [str(field).strip() for field in fields]
    if names and names[-1] == "":
        raise PatientError(
            "header ends with an empty name (a trailing tab or comma)")
    for name in names:
        if not name:
            raise PatientError("header contains an empty name")
    if len(set(names)) != len(names):
        raise PatientError("header repeats a name")
    return tuple(names)


def read_csv(path: str | Path = DATA_FILE) -> list[Patient]:
    """Strict: known columns, one optional ``#`` comment block, no extras."""
    path = Path(path)
    if not path.exists():
        raise PatientError(f"patient file not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        lines = [line for line in handle if not line.lstrip().startswith("#")]
    reader = csv.reader(lines)
    try:
        header = next(reader)
    except StopIteration:
        raise PatientError(f"{path.name} is empty") from None
    validate_header(header)
    names = [name.strip() for name in header]
    if tuple(names) != COLUMNS:
        raise PatientError(
            f"{path.name} header is {names}, expected {list(COLUMNS)}")
    patients: list[Patient] = []
    for number, row in enumerate(reader, start=2):
        if not any(field.strip() for field in row):
            continue                      # blank line between records
        if len(row) != len(COLUMNS):
            raise PatientError(
                f"{path.name} line {number}: {len(row)} fields, "
                f"expected {len(COLUMNS)}")
        try:
            patients.append(Patient.from_row(dict(zip(names, row))))
        except PatientError as exc:
            raise PatientError(f"{path.name} line {number}: {exc}") from None
    if not patients:
        raise PatientError(f"{path.name} has no patient records")
    return patients


def write_csv(path: str | Path, patients: list[Patient]) -> Path:
    """A clean file: the canonical header, ISO dates, integer ids."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with open(handle, "w", encoding="utf-8", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=list(COLUMNS),
                                    lineterminator="\n")
            writer.writeheader()
            for patient in patients:
                writer.writerow(patient.to_row())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


def reread_legacy(path: str | Path = LEGACY_FILE) -> dict:
    """What the original program's reader saw, without Spark.

    Returns the header names, the raw rows, and the two copies of the date
    that the trailing tab created.
    """
    path = Path(path)
    if not path.exists():
        raise PatientError(f"legacy file not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    header = rows[0] if rows else []
    body = [row for row in rows[1:] if any(field.strip() for field in row)]
    return {"header": header, "rows": body,
            "header_as_read": [name for name in header],
            "date_column": body[0][5] if body else "",
            "seventh_column": body[0][6] if body and len(body[0]) > 6 else ""}


# --------------------------------------------------------------------------- #
# Duplicates
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Duplicate:
    patient_id: int
    kept: Patient
    extra: tuple[Patient, ...]

    @property
    def conflict(self) -> bool:
        return any(patient != self.kept for patient in self.extra)


def find_duplicates(patients: list[Patient]) -> list[Duplicate]:
    """Group by id; the first occurrence is kept, the rest are reported."""
    seen: dict[int, Patient] = {}
    order: list[int] = []
    grouped: dict[int, list[Patient]] = {}
    for patient in patients:
        if patient.patient_id not in seen:
            seen[patient.patient_id] = patient
            order.append(patient.patient_id)
            grouped[patient.patient_id] = []
        else:
            grouped[patient.patient_id].append(patient)
    return [Duplicate(patient_id, seen[patient_id],
                      tuple(grouped[patient_id]))
            for patient_id in order if grouped[patient_id]]


def dedupe(patients: list[Patient]) -> list[Patient]:
    """Drop later rows with an id already seen, keeping file order."""
    seen: set[int] = set()
    kept: list[Patient] = []
    for patient in patients:
        if patient.patient_id in seen:
            continue
        seen.add(patient.patient_id)
        kept.append(patient)
    return kept


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
def older_than(patients: list[Patient], age: int) -> list[Patient]:
    if isinstance(age, bool) or not isinstance(age, int):
        raise PatientError("age must be an integer")
    return [patient for patient in patients if patient.age > age]


def by_gender(patients: list[Patient], gender: str) -> list[Patient]:
    if gender not in GENDERS:
        raise PatientError(f"gender {gender!r} is not one of {GENDERS}")
    return [patient for patient in patients if patient.gender == gender]


def by_diagnosis(patients: list[Patient], diagnosis: str) -> list[Patient]:
    needle = str(diagnosis).strip().casefold()
    if not needle:
        raise PatientError("diagnosis must not be empty")
    return [patient for patient in patients
            if patient.diagnosis.casefold() == needle]


def admitted_between(patients: list[Patient], start, end) -> list[Patient]:
    first, last = parse_date(start), parse_date(end)
    if last < first:
        raise PatientError("end date is before the start date")
    return [patient for patient in patients
            if first <= patient.admitted <= last]


def diagnosis_counts(patients: list[Patient]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for patient in patients:
        counts[patient.diagnosis] = counts.get(patient.diagnosis, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1],
                                                         item[0])))


def gender_counts(patients: list[Patient]) -> dict[str, int]:
    counts = {gender: 0 for gender in GENDERS}
    for patient in patients:
        counts[patient.gender] += 1
    return counts


def age_summary(patients: list[Patient]) -> dict:
    """Mean rounded at the boundary; median exact; honest nulls when empty."""
    ages = sorted(patient.age for patient in patients)
    if not ages:
        return {"count": 0, "mean": None, "median": None, "min": None,
                "max": None}
    middle = len(ages) // 2
    median = (ages[middle] if len(ages) % 2
              else (ages[middle - 1] + ages[middle]) / 2)
    return {"count": len(ages),
            "mean": round(sum(ages) / len(ages), 2),
            "median": median,
            "min": ages[0],
            "max": ages[-1]}


def stats(patients: list[Patient]) -> dict:
    return {"patients": len(patients),
            "genders": gender_counts(patients),
            "diagnoses": diagnosis_counts(patients),
            "ages": age_summary(patients),
            "first_admission": min((patient.admitted
                                    for patient in patients), default=None),
            "last_admission": max((patient.admitted
                                   for patient in patients), default=None)}


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_patient(patient: Patient) -> str:
    return (f"  {patient.patient_id:>3}  {patient.name:<18.18}  "
            f"{patient.age:>3}  {patient.gender:<6}  "
            f"{patient.diagnosis:<15.15}  "
            f"{patient.admitted.strftime(DATE_FORMAT)}")


def render_table(patients: list[Patient]) -> str:
    header = ("  id  name                age  gender  diagnosis        "
              "admitted")
    if not patients:
        return f"{header}\n  (no patients)"
    return "\n".join([header] + [render_patient(patient)
                                 for patient in patients])


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 70)
    print(" PATIENT ENTRY - a trailing tab, Excel serials and dropDuplicates")
    print("=" * 70)

    # 1. the header really does have a seventh, empty name
    fields = legacy_header_fields()
    assert len(fields) == 7, fields
    assert fields[-1] == "", fields
    assert fields[5] == "AdmissionDate"
    try:
        validate_header(fields)
    except PatientError as exc:
        assert "trailing tab" in str(exc), str(exc)
    else:
        raise AssertionError("the legacy header should be refused")
    print(f"  legacy header splits into {len(fields)} names, the last "
          f"{fields[-1]!r} - refused by validate_header")

    # 2. so the date landed in column 6 and a serial landed in column 5
    legacy = reread_legacy()
    assert len(legacy["header"]) == 7
    assert legacy["date_column"] == "45667"
    assert legacy["seventh_column"] == "10-01-2025"
    assert len(legacy["rows"]) == 15
    assert all(len(row) == 7 for row in legacy["rows"])
    assert serial_to_date(legacy["date_column"]) == datetime.date(2025, 1, 10)
    assert parse_date(legacy["seventh_column"]) == datetime.date(2025, 1, 10)
    print(f"  column 'AdmissionDate' = {legacy['date_column']!r} "
          f"(-> 2025-01-10), column '' = {legacy['seventh_column']!r} "
          f"(-> the same day)")

    # 3. the two date columns are a second copy of one fact
    agreements = sum(
        1 for row in legacy["rows"]
        if serial_to_date(row[5]) == parse_date(row[6]))
    assert agreements == 15, agreements
    print(f"  all {agreements} rows carry the same date twice")

    # 4. the fake 1900 leap day
    assert serial_to_date(1) == datetime.date(1900, 1, 1)
    assert serial_to_date(59) == datetime.date(1900, 2, 28)
    assert serial_to_date(60) == datetime.date(1900, 2, 28)   # 02-29 is a lie
    assert serial_to_date(61) == datetime.date(1900, 3, 1)
    assert serial_to_date(45292) == datetime.date(2024, 1, 1)
    print("  serial 60 (Excel's 1900-02-29, which never existed) -> "
          "1900-02-28; 59 and 61 are adjacent")

    # 5. day-first is ambiguous, and the module says which one it means
    assert parse_date("10-01-2025") == datetime.date(2025, 1, 10)
    american = datetime.datetime.strptime("10-01-2025", "%m-%d-%Y").date()
    assert american == datetime.date(2025, 10, 1) and american != \
        parse_date("10-01-2025")
    assert parse_date("2025-01-10") == datetime.date(2025, 1, 10)
    assert parse_date(45667) == datetime.date(2025, 1, 10)
    for bad in ("10/01/2025", "2025-1-10", "31-02-2025", "", "soon"):
        try:
            parse_date(bad)
        except PatientError:
            pass
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    print("  '10-01-2025' is 2025-01-10 (day first), not 2025-10-01; five "
          "bad shapes refused")

    # 6. the bundled file is clean, and its dates are all ISO
    patients = read_csv()
    assert len(patients) == 15
    assert all(patient.admitted.year == 2025 for patient in patients)
    assert patients[0].name == "John Smith"
    assert patients[-1].name == "Ethan Clark"
    assert find_duplicates(patients) == []
    print(f"  bundled patients.csv: 15 records, unique ids, ISO dates")

    # 7. validation refuses each bad field for its own reason
    good = {"patient_id": "16", "name": "Test", "age": "30",
            "gender": "Female", "diagnosis": "Fever",
            "admitted": "2025-02-01"}
    assert Patient.from_row(good).patient_id == 16
    bad_rows = [
        ("patient_id", "0"), ("name", "  "), ("age", "-1"), ("age", "121"),
        ("gender", "Other"), ("diagnosis", ""), ("admitted", "1 January"),
        ("age", "thirty"), ("extra", "x"),
    ]
    for key, value in bad_rows:
        row = dict(good)
        row[key] = value
        try:
            Patient.from_row(row)
        except PatientError:
            pass
        else:
            raise AssertionError(f"{key}={value!r} should have been refused")
    print(f"  {len(bad_rows)} invalid rows refused (id, name, age twice, "
          f"gender, diagnosis, date, non-numeric, unknown column)")

    # 8. duplicates are reported, and a conflicting duplicate is flagged
    twin = Patient(1, "John Smith", 45, "Male", "Fever", "2025-01-10")
    clash = Patient(1, "J. Smith", 46, "Male", "Fever", "2025-01-10")
    found = find_duplicates(patients + [twin, clash])
    assert len(found) == 1
    assert found[0].patient_id == 1
    assert len(found[0].extra) == 2
    assert found[0].conflict is True
    assert len(dedupe(patients + [twin, clash])) == 15
    same = find_duplicates(patients + [twin])
    assert same[0].conflict is False
    print("  an exact duplicate and a conflicting duplicate are both "
          "reported; dedupe keeps 15")

    # 9. the queries, with counts pinned to the file
    summary = stats(patients)
    assert summary["patients"] == 15
    assert summary["genders"] == {"Female": 7, "Male": 8}
    assert summary["ages"]["mean"] == 41.33
    assert summary["ages"]["median"] == 41
    assert summary["ages"]["min"] == 26 and summary["ages"]["max"] == 61
    assert len(older_than(patients, 40)) == 8
    assert len(by_gender(patients, "Female")) == 7
    assert len(by_diagnosis(patients, "diabetes")) == 2
    assert diagnosis_counts(patients)["Fever"] == 2
    assert list(diagnosis_counts(patients))[:4] == ["Asthma", "Diabetes",
                                                    "Fever", "Hypertension"]
    assert len(admitted_between(patients, "2025-01-12", "2025-01-16")) == 5
    assert summary["first_admission"] == datetime.date(2025, 1, 10)
    assert summary["last_admission"] == datetime.date(2025, 1, 24)
    print(f"  15 patients, 8 over 40, mean age {summary['ages']['mean']}, "
          f"median {summary['ages']['median']}, 7 Female / 8 Male")

    # 10. an empty registry answers with nulls, not invented numbers
    empty = stats([])
    assert empty["ages"] == {"count": 0, "mean": None, "median": None,
                             "min": None, "max": None}
    assert empty["first_admission"] is None
    assert render_table([]).endswith("(no patients)")
    print("  an empty registry returns None and 0, never a made-up mean")

    # 11. a clean write/read round trip is byte-identical
    with tempfile.TemporaryDirectory(prefix="pat-") as folder:
        path = Path(folder) / "out.csv"
        write_csv(path, patients)
        first = path.read_bytes()
        assert read_csv(path) == patients
        write_csv(path, read_csv(path))
        assert path.read_bytes() == first
        text = path.read_text(encoding="utf-8").splitlines()
        assert text[0] == \
            "patient_id,name,age,gender,diagnosis,admitted"
        assert text[1].startswith("1,John Smith,45,Male,Fever,2025-01-10")
        assert "\t" not in text[0]
    print("  write/re-read round trip identical, no tabs, ISO dates")

    # 12. file-level errors name the line or the column
    with tempfile.TemporaryDirectory(prefix="pat-") as folder:
        path = Path(folder) / "bad.csv"
        path.write_text(
            "patient_id,name,age,gender,diagnosis,admitted\n"
            "1,Ann,30,Female,Fever,2025-01-01\n"
            "2,Bob,thirty,Male,Fever,2025-01-02\n", encoding="utf-8")
        try:
            read_csv(path)
        except PatientError as exc:
            assert "line 3" in str(exc), str(exc)
        else:
            raise AssertionError("a bad age should have been refused")
        path.write_text(
            "patient_id,name,age,gender,diagnosis\n"
            "1,Ann,30,Female,Fever\n", encoding="utf-8")
        try:
            read_csv(path)
        except PatientError as exc:
            assert "expected" in str(exc), str(exc)
        else:
            raise AssertionError("a short header should have been refused")
        path.write_text(
            "patient_id,name,name,gender,diagnosis,admitted\n"
            "1,Ann,Ann,Female,Fever,2025-01-01\n", encoding="utf-8")
        try:
            read_csv(path)
        except PatientError as exc:
            assert "repeats" in str(exc), str(exc)
        else:
            raise AssertionError("a repeated column should have been refused")
    print("  a bad age names line 3, a short header and a repeated column "
          "are refused")

    print()
    print("Cross-checks OK: the legacy header split into 7 names with an "
          "empty seventh, the date sat in 'AdmissionDate' as serial 45667 "
          "while a second copy sat in the empty column, all 15 rows agreed "
          "on the date twice, Excel's fake 1900-02-29 and its neighbours "
          "were pinned, day-first parsing was distinguished from month-first, "
          "five bad date shapes refused, 15 cleaned records with unique ids, "
          "9 invalid rows refused, an exact and a conflicting duplicate "
          "reported without deleting either patient, pinned counts and ages "
          "(mean 41.33, median 41, 8 over 40), honest nulls for an empty "
          "registry, and a byte-identical clean round trip")
    print("Demo completed successfully.")
    return 0
