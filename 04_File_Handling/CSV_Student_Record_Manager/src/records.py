"""A student table where CSV is a wire format, not a place to keep a float.

The legacy project read and rewrote the same file for every operation:

    @dataclass
    class Student:
        roll_no: str
        name: str
        department: str
        year: int
        marks: float

    def save_students(self, students):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(CSV_HEADERS)
            for student in students:
                writer.writerow(student.to_list())

    def add_student(self):
        students = self.load_students()
        roll = input("Roll Number : ")
        if any(s.roll_no == roll for s in students):
            print("Student already exists.")
            return

    average = sum(student.marks for student in students) / len(students)

Six things follow.

**1. `marks: float` is a type that does not exist in the domain.** Marks are
recorded to two decimals; ``float`` can hold ``89.099999999999994``, and the
average of three rows of 89.10 is exactly that. This module stores marks as an
integer number of hundredths (``8910``) and parses the text without ever
building a float: ``"89.05"`` is 8905 by construction, and ``"89.005"`` is
refused rather than silently rounded.

**2. `open(path, "w")` truncates before it writes.** A failure halfway through
the loop leaves the file holding a header and two rows. ``save_atomic`` writes
to a temporary file in the same directory, flushes and fsyncs it, and only then
calls ``os.replace``, so the destination either has all of the old content or
all of the new content. The demo forces a mid-table failure to prove it.

**3. The duplicate check compares raw text.** ``" 421123102001"`` and
``"421123102001"`` are two different roll numbers to
``any(s.roll_no == roll ...)``, so a padded roll number becomes a second row.
Rolls are normalised before they are compared.

**4. The header is never checked.** ``csv.DictReader`` raises a bare
``KeyError: 'Marks'`` for a column that was renamed, with no file and no line.
Here the header is compared as a tuple and the complaint names the file, the
expected columns and the ones found.

**5. A bad row raises ``ValueError`` with no line number.** Nine rows load and
the tenth fails as ``invalid literal for int()``. Every row error here carries
the line it came from.

**6. The "report" is a copy.** ``ReportGenerator.generate(students)`` writes the
same five columns and the same rows to ``reports/student_report.csv``; it is the
data file under another name. A report that is worth writing aggregates: it
counts rows, averages marks and names the best student per department.

Standard library only: no pandas, no openpyxl, no network.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "students.csv"

#: The columns, in the order the file must have them.
HEADER = ("Roll No", "Name", "Department", "Year", "Marks")

#: The departments this table accepts.
DEPARTMENTS = ("CSE", "ECE", "IT", "MECH")

#: Marks, in hundredths, at the top of the scale.
MAX_MARKS = 10000

#: The legacy model: marks are a float, so the file holds a float.
LEGACY_FLOAT_ROW = "marks: float"

#: The legacy save: the file is truncated before the first row is written.
LEGACY_SAVE = 'open(CSV_FILE, "w")'

#: The legacy duplicate test: raw string equality.
LEGACY_DUPLICATE = "any(s.roll_no == roll for s in students)"

#: The legacy average: a float division of floats.
LEGACY_AVERAGE = "sum(student.marks for student in students) / len(students)"

_MARKS_TEXT = re.compile(r"^(\d{1,3})(?:\.(\d{1,2}))?$")


class RecordError(ValueError):
    """A row, a table or a file that is refused."""


class TableError(RecordError):
    """The file as a whole is not a student table."""


class RowError(RecordError):
    """One line of the file is not a student."""

    def __init__(self, line: int, reason: str):
        self.line = line
        self.reason = reason
        super().__init__(f"line {line}: {reason}")


# --------------------------------------------------------------------------- #
# Numbers, exactly
# --------------------------------------------------------------------------- #
def round_half_up(numerator: int, denominator: int) -> int:
    """Half away from zero, on integers only."""
    if denominator <= 0:
        raise RecordError("the denominator must be positive")
    if numerator < 0:
        return -(((-numerator) * 2 + denominator) // (2 * denominator))
    return (numerator * 2 + denominator) // (2 * denominator)


def parse_marks(text) -> int:
    """``"89.05"`` -> ``8905``; no float is ever built on the way."""
    if not isinstance(text, str):
        raise RecordError(f"marks must be text, got {type(text).__name__}")
    wanted = text.strip()
    if not wanted:
        raise RecordError("marks must not be empty")
    match = _MARKS_TEXT.match(wanted)
    if match is None:
        raise RecordError(
            f"{text!r} is not marks: a whole number with at most two "
            f"decimals, like 89 or 89.05")
    whole, fraction = match.group(1), match.group(2) or ""
    hundredths = int(whole) * 100 + int(fraction.ljust(2, "0"))
    if hundredths > MAX_MARKS:
        raise RecordError(f"{text!r} is over {format_marks(MAX_MARKS)}")
    return hundredths


def format_marks(hundredths) -> str:
    """``8905`` -> ``"89.05"``; the only place marks become text."""
    if isinstance(hundredths, bool) or not isinstance(hundredths, int):
        raise RecordError("only an integer number of hundredths can be shown")
    sign = "-" if hundredths < 0 else ""
    whole, fraction = divmod(abs(hundredths), 100)
    return f"{sign}{whole}.{fraction:02d}"


def check_whole(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RecordError(f"{label} must be a whole number, got "
                          f"{type(value).__name__}")
    return value


def check_year(value) -> int:
    year = check_whole(value, "the year")
    if not 1 <= year <= 4:
        raise RecordError(f"the year must be 1, 2, 3 or 4, got {year}")
    return year


def check_marks(value) -> int:
    marks = check_whole(value, "marks")
    if not 0 <= marks <= MAX_MARKS:
        raise RecordError(f"marks must be 0 to {format_marks(MAX_MARKS)}, got "
                          f"{format_marks(marks)}")
    return marks


# --------------------------------------------------------------------------- #
# The four text fields
# --------------------------------------------------------------------------- #
def normalise_roll(value) -> str:
    """Twelve digits, spaces removed first; anything else is refused."""
    if not isinstance(value, str):
        raise RecordError(f"a roll number must be text, got "
                          f"{type(value).__name__}")
    roll = value.strip()
    if not roll:
        raise RecordError("a roll number must not be empty")
    if not roll.isdigit():
        raise RecordError(f"{value!r} must be twelve digits, with nothing but "
                          f"spaces around them")
    if len(roll) != 12:
        raise RecordError(f"{value!r} has {len(roll)} digits; a roll number "
                          f"has twelve")
    return roll


def normalise_name(value) -> str:
    """Collapse the spaces, refuse an empty name or a newline in one."""
    if not isinstance(value, str):
        raise RecordError(f"a name must be text, got {type(value).__name__}")
    if "\n" in value or "\r" in value:
        raise RecordError(f"{value!r} contains a line break; a name is one "
                          f"line of a CSV file")
    name = " ".join(value.split())
    if not name:
        raise RecordError("a student needs a name")
    if any(character in name for character in "\r\n"):
        raise RecordError(f"{value!r} contains a line break; a name is one "
                          f"line of a CSV file")
    if len(name) > 40:
        raise RecordError(f"{name[:20]}... is {len(name)} characters; a name "
                          f"is at most 40")
    return name


def normalise_department(value) -> str:
    if not isinstance(value, str):
        raise RecordError(f"a department must be text, got "
                          f"{type(value).__name__}")
    wanted = " ".join(value.split()).upper()
    if wanted not in DEPARTMENTS:
        raise RecordError(f"{value!r} is not a department (choose from "
                          f"{', '.join(DEPARTMENTS)})")
    return wanted


# --------------------------------------------------------------------------- #
# Student: a value, validated once
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Student:
    """One row of the table. Marks are hundredths; there is no float here."""

    roll: str
    name: str
    department: str
    year: int
    marks: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "roll", normalise_roll(self.roll))
        object.__setattr__(self, "name", normalise_name(self.name))
        object.__setattr__(self, "department",
                           normalise_department(self.department))
        object.__setattr__(self, "year", check_year(self.year))
        object.__setattr__(self, "marks", check_marks(self.marks))

    # -- display ----------------------------------------------------------- #
    @property
    def marks_text(self) -> str:
        return format_marks(self.marks)

    def __str__(self) -> str:
        return (f"{self.roll}  {self.name:<16.16}  {self.department:<4}  "
                f"year {self.year}  {self.marks_text:>6}")

    def to_row(self) -> list:
        """The five cells this row becomes in the file."""
        return [self.roll, self.name, self.department, str(self.year),
                self.marks_text]

    def to_dict(self) -> dict:
        return {"roll": self.roll, "name": self.name,
                "department": self.department, "year": self.year,
                "marks": self.marks_text}

    # -- reading ----------------------------------------------------------- #
    @classmethod
    def from_row(cls, row, line: int = 0) -> "Student":
        if not isinstance(row, (list, tuple)):
            raise RowError(line, "a row must be a list of five cells")
        if len(row) != len(HEADER):
            raise RowError(line, f"a row has {len(HEADER)} cells, not "
                                 f"{len(row)}")
        try:
            return cls(row[0], row[1], row[2], parse_whole(row[3], "year"),
                       parse_marks(row[4]))
        except RecordError as exc:
            raise RowError(line, str(exc)) from None

    @classmethod
    def from_dict(cls, row, line: int = 0) -> "Student":
        if not isinstance(row, dict):
            raise RowError(line, "a student must be an object")
        unknown = set(row) - {"roll", "name", "department", "year", "marks"}
        if unknown:
            raise RowError(line, f"unknown student keys: {sorted(unknown)}")
        for key in ("roll", "name", "department", "year", "marks"):
            if key not in row:
                raise RowError(line, f"a student is missing {key!r}")
        try:
            year = row["year"]
            if isinstance(year, str):
                year = parse_whole(year, "year")
            marks = row["marks"]
            marks = parse_marks(marks) if isinstance(marks, str) else marks
            return cls(row["roll"], row["name"], row["department"], year,
                       marks)
        except RecordError as exc:
            raise RowError(line, str(exc)) from None


def parse_whole(text, label: str) -> int:
    if not isinstance(text, str):
        raise RecordError(f"{label} must be text, got {type(text).__name__}")
    wanted = text.strip()
    if not wanted.isdigit():
        raise RecordError(f"{text!r} is not {label}: a whole number is "
                          f"required")
    return int(wanted)


# --------------------------------------------------------------------------- #
# Writing: build every byte first, publish last
# --------------------------------------------------------------------------- #
def save_atomic(path, chunks) -> Path:
    """Write ``chunks`` to a temp file beside ``path``, then replace it.

    If building or writing a chunk fails, the destination keeps the bytes it
    already had and the temporary file is removed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent),
                                         prefix=path.name + ".",
                                         suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            for chunk in chunks:
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    return path


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #
class StudentTable:
    """Students, one per roll number, kept in a CSV file on disk."""

    def __init__(self, students=()):
        self._students: dict[str, Student] = {}
        for student in students:
            self.add(student)

    # -- collection protocol ------------------------------------------------ #
    def __len__(self) -> int:
        return len(self._students)

    def __iter__(self):
        return iter([self._students[roll] for roll in sorted(self._students)])

    def __contains__(self, roll) -> bool:
        if not isinstance(roll, str):
            return False
        try:
            return normalise_roll(roll) in self._students
        except RecordError:
            return False

    def __getitem__(self, roll) -> Student:
        return self.student(roll)

    def __repr__(self) -> str:
        return f"<StudentTable with {len(self)} students>"

    @property
    def students(self) -> tuple[Student, ...]:
        return tuple(self)

    # -- lookups ------------------------------------------------------------ #
    def student(self, roll) -> Student:
        key = normalise_roll(roll)
        try:
            return self._students[key]
        except KeyError:
            raise RecordError(f"no student with roll number {key}") from None

    def search(self, text) -> list[Student]:
        if not isinstance(text, str):
            raise RecordError("a search needs text")
        needle = " ".join(text.split()).casefold()
        if not needle:
            raise RecordError("a search needs something to look for")
        return [student for student in self
                if needle in student.roll.casefold()
                or needle in student.name.casefold()
                or needle in student.department.casefold()]

    def by_department(self) -> dict[str, tuple[Student, ...]]:
        grouped: dict[str, list[Student]] = {}
        for student in self:
            grouped.setdefault(student.department, []).append(student)
        return {department: tuple(grouped[department])
                for department in sorted(grouped)}

    # -- adding and removing ------------------------------------------------ #
    def add(self, student: Student) -> Student:
        if not isinstance(student, Student):
            raise RecordError("only a Student can be added, got "
                              f"{type(student).__name__}")
        if student.roll in self._students:
            raise RecordError(f"{student.roll} is already in the table as "
                              f"{self._students[student.roll].name!r}")
        self._students[student.roll] = student
        return student

    def remove(self, roll) -> Student:
        student = self.student(roll)
        del self._students[student.roll]
        return student

    def update(self, roll, **changes) -> Student:
        """Replacement, not mutation: a Student is frozen."""
        student = self.student(roll)
        allowed = {"name", "department", "year", "marks"}
        unknown = set(changes) - allowed
        if unknown:
            raise RecordError(f"a student has no {sorted(unknown)[0]!r}; the "
                              f"fields are {', '.join(sorted(allowed))}")
        merged = {field: getattr(student, field) for field in allowed}
        merged.update(changes)
        replacement = Student(student.roll, merged["name"],
                              merged["department"], merged["year"],
                              merged["marks"])
        self._students[replacement.roll] = replacement
        return replacement

    # -- aggregates ---------------------------------------------------------#
    @property
    def total_marks(self) -> int:
        return sum(student.marks for student in self._students.values())

    def average_marks(self) -> int:
        """The mean in hundredths, rounded half up; 0 for an empty table."""
        if not self._students:
            return 0
        return round_half_up(self.total_marks, len(self._students))

    def top(self, count: int = 3) -> list[Student]:
        wanted = check_whole(count, "the number of students")
        if wanted < 1:
            raise RecordError("the number of students must be at least one")
        return sorted(self._students.values(),
                      key=lambda student: (-student.marks, student.roll)
                      )[:wanted]

    def report(self) -> list[dict]:
        """Per department: how many, the mean and the best. Not a copy."""
        rows = []
        for department, members in self.by_department().items():
            total = sum(student.marks for student in members)
            best = max(members, key=lambda student: (student.marks,
                                                     student.roll))
            rows.append({"department": department, "students": len(members),
                         "average": format_marks(
                             round_half_up(total, len(members))),
                         "best": best.roll, "best_marks": best.marks_text})
        return rows

    # -- invariants --------------------------------------------------------- #
    def audit(self) -> list[tuple[str, bool]]:
        checks = []

        filed = all(roll == student.roll
                    for roll, student in self._students.items())
        checks.append(("every student is filed under its roll number", filed))

        rolls = [student.roll for student in self._students.values()]
        checks.append(("no two students share a roll number",
                       len(set(rolls)) == len(rolls)))

        bad_rolls = [student.roll for student in self._students.values()
                     if len(student.roll) != 12 or not student.roll.isdigit()]
        checks.append(("every roll number is twelve digits", not bad_rolls))

        bad_marks = [student.roll for student in self._students.values()
                     if not 0 <= student.marks <= MAX_MARKS]
        checks.append(("every mark is between 0 and 100", not bad_marks))

        bad_departments = [student.roll for student in self._students.values()
                           if student.department not in DEPARTMENTS]
        checks.append(("every department is one of the four", not
                       bad_departments))
        return checks

    def problems(self) -> list[str]:
        return [name for name, passed in self.audit() if not passed]

    # -- the file ----------------------------------------------------------- #
    def _chunks(self):
        """The file, one line at a time, produced lazily."""
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(HEADER)
        yield buffer.getvalue()
        for student in self._students.values():
            buffer.seek(0)
            buffer.truncate(0)
            writer.writerow(student.to_row())
            yield buffer.getvalue()

    def to_text(self) -> str:
        """Every byte of the file, built before anything is opened."""
        buffer = io.StringIO()
        buffer.write("".join(self._chunks()))
        return buffer.getvalue()

    def save(self, path=DATA_FILE) -> Path:
        """All of the old file or all of the new one; never half."""
        return save_atomic(path, self._chunks())

    def to_json(self) -> list:
        return [student.to_dict() for student in self]

    # -- reading ------------------------------------------------------------ #
    @classmethod
    def from_rows(cls, rows) -> "StudentTable":
        table = cls()
        for line, row in enumerate(rows, start=2):
            table.add(Student.from_row(row, line))
        return table

    @classmethod
    def from_dict(cls, payload) -> "StudentTable":
        if not isinstance(payload, list):
            raise RecordError("a table document must be a list of students")
        table = cls()
        for index, row in enumerate(payload, start=1):
            table.add(Student.from_dict(row, index))
        return table


def load_table(path=DATA_FILE) -> StudentTable:
    """Read the file, checking the header before it checks a single row."""
    path = Path(path)
    if not path.exists():
        raise TableError(f"student file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TableError(f"{path.name} is not UTF-8 text: {exc}") from None
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise TableError(f"{path.name} is empty; a student table starts with "
                         f"{', '.join(HEADER)}") from None
    if tuple(header) != HEADER:
        missing = [column for column in HEADER if column not in header]
        extra = [column for column in header if column not in HEADER]
        detail = []
        if missing:
            detail.append(f"missing {', '.join(missing)}")
        if extra:
            detail.append(f"unexpected {', '.join(extra)}")
        raise TableError(f"{path.name} line 1 has the wrong header "
                         f"({'; '.join(detail) or 'columns out of order'}); "
                         f"expected {', '.join(HEADER)}")
    table = StudentTable()
    for line, row in enumerate(reader, start=2):
        if not row:
            continue                        # a blank line is not a row
        table.add(Student.from_row(row, line))
    return table


# --------------------------------------------------------------------------- #
# The legacy project, transcribed so the demo can prove it wrong
# --------------------------------------------------------------------------- #
def legacy_average(marks) -> float:
    """``sum(student.marks for student in students) / len(students)``."""
    values = list(marks)
    if not values:
        raise RecordError("there are no marks to average")
    return sum(values) / len(values)


def legacy_row(student: Student) -> list:
    """``Student.to_list()``: the year as an int and marks as a float."""
    return [student.roll, student.name, student.department, student.year,
            student.marks / 100]


def legacy_duplicate(rolls, roll) -> bool:
    """``any(s.roll_no == roll for s in students)``: raw string equality."""
    return any(existing == roll for existing in rolls)


def legacy_report_text(table: StudentTable) -> str:
    """``ReportGenerator.generate``: the same columns and rows, again."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    for student in table:
        writer.writerow(legacy_row(student))
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 74)
    print(" CSV RECORDS - a wire format, and marks that are never a float")
    print("=" * 74)

    # 1. marks as text, parsed exactly
    assert parse_marks("89") == 8900 and parse_marks("89.05") == 8905
    assert parse_marks(" 74.5 ") == 7450 and parse_marks("100") == 10000
    lost = int(float("0.29") * 100)
    assert lost == 28 and parse_marks("0.29") == 29
    three = float("89.005") * 100
    assert three == 8900.5
    refused = 0
    for text in ("89.005", "-1", "101", "eighty", "89,5"):
        try:
            parse_marks(text)
        except RecordError:
            refused += 1
        else:
            raise AssertionError(f"marks {text!r} were accepted")
    assert refused == 5
    print(f"  int(float('0.29') * 100) is {lost} while '0.29' is 29 here; "
          f"'89.005' times 100 is exactly {three} in a float, so a float "
          f"cannot tell 89.00 from 89.005, and 5 bad texts were refused")

    # 2. the float mean the legacy table printed
    mean = legacy_average([89.1, 89.1, 89.1])
    assert repr(mean) == "89.09999999999998"
    exact = (8910 * 3, 3)
    assert round_half_up(*exact) == 8910
    print(f"  three rows of 89.10: the legacy float mean is {mean!r}, which "
          f"prints 89.10 and is not 89.1; {exact[0]}/{exact[1]} hundredths is "
          f"exactly {format_marks(round_half_up(*exact))}")

    # 3. half up, where round() goes the other way
    assert round(8900.5) == 8900 and round_half_up(17801, 2) == 8901
    print(f"  the mean of 89.00 and 89.01 is 8900.5 hundredths: round() gives "
          f"{round(8900.5)}, half up gives {round_half_up(17801, 2)}")

    # 4. one normalisation, then byte for byte
    table = load_table()
    assert len(table) == 8 and table.total_marks == 66550
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "copy.csv"
        table.save(target)
        first = target.read_bytes()
        assert b",89.00\n" in first and b",89\n" not in first
        load_table(target).save(target)
        second = target.read_bytes()
        assert first == second
    print(f"  the shipped file writes '89' for a whole mark; one save "
          f"normalises all 8 rows to two decimals and the second save is "
          f"byte-identical ({len(first)} bytes)")

    # 5. the header is checked, with the file named
    with tempfile.TemporaryDirectory() as folder:
        wrong = Path(folder) / "students.csv"
        wrong.write_text("Roll No,Name,Department,Year,Mark\n"
                         "421123102001,Alex,CSE,3,89\n", encoding="utf-8")
        try:
            load_table(wrong)
        except TableError as exc:
            header_message = str(exc)
        else:
            raise AssertionError("a renamed column was accepted")
    assert "missing Marks" in header_message
    print(f"  a column renamed to 'Mark' is refused before any row is read "
          f"({header_message[:44]}...)")

    # 6. a bad row says which line
    with tempfile.TemporaryDirectory() as folder:
        broken = Path(folder) / "students.csv"
        broken.write_text(",".join(HEADER) + "\n"
                          "421123102001,Alex,CSE,3,89\n"
                          "421123102002,John,IT,3,91\n"
                          "421123102003,Priya,CSE,7,95\n", encoding="utf-8")
        try:
            load_table(broken)
        except RowError as exc:
            row_message, row_line = str(exc), exc.line
        else:
            raise AssertionError("a year of 7 was accepted")
    assert row_line == 4 and "must be 1, 2, 3 or 4" in row_message
    print(f"  a year of 7 on the fourth line is a RowError naming line "
          f"{row_line}: {row_message[:34]}...")

    # 7. the duplicate check, normalised
    assert legacy_duplicate(["421123102001"], " 421123102001") is False
    assert " 421123102001" in table
    twins = 0
    for roll, name, department, year, marks in (
            (" 421123102001", "Twin", "CSE", 1, 8900),
            ("421123102009", "Twin", "LAW", 1, 8900),
            ("421123102009", "Twin", "CSE", 5, 8900)):
        try:
            table.add(Student(roll, name, department, year, marks))
        except RecordError:
            twins += 1
        else:
            raise AssertionError(f"{roll} was added twice")
    assert twins == 3 and len(table) == 8
    print(f"  a padded roll number is a duplicate here and was not to "
          f"any(s.roll_no == roll); 3 additions refused, the table is still "
          f"{len(table)} rows")

    # 8. a save that fails leaves the file alone
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "students.csv"
        target.write_text("original\n", encoding="utf-8")
        before = target.read_bytes()

        def chunks():
            yield "Roll No,Name,Department,Year,Marks\n"
            raise OSError("the disk filled up")

        try:
            save_atomic(target, chunks())
        except OSError as exc:
            failure = str(exc)
        else:
            raise AssertionError("a failing save reported success")
        assert target.read_bytes() == before
        assert [entry.name for entry in Path(folder).iterdir()] == \
            ["students.csv"]
    print(f"  a save that fails after the header ({failure}) left the "
          f"destination byte-identical and no .tmp behind, where "
          f"'open(..., \"w\")' would have truncated it")

    # 9. the report is an aggregate, not a copy
    rows = table.report()
    assert [row["department"] for row in rows] == ["CSE", "ECE", "IT", "MECH"]
    assert [row["students"] for row in rows] == [3, 2, 2, 1]
    assert [row["average"] for row in rows] == ["90.75", "74.00", "85.38",
                                                "74.50"]
    assert table.average_marks() == 8319
    assert table.top(1)[0].roll == "421123102003"
    legacy = legacy_report_text(table)
    assert legacy.splitlines()[0] == ",".join(HEADER)
    assert len(legacy.splitlines()) == 9
    print(f"  the report is {len(rows)} rows of counts and means (CSE 90.75, "
          f"IT 85.38, MECH 74.50) where the legacy report is the same 9 lines "
          f"and the same 5 columns as the data file")

    # 10. search, ranking, invariants
    assert len(table.search("cse")) == 3 and len(table.search("ar")) == 2
    assert [student.roll for student in table.top(3)] == [
        "421123102003", "421123102002", "421123102001"]
    assert len(table.audit()) == 5 and table.problems() == []
    broken = StudentTable(table.students)
    object.__setattr__(broken.student("421123102001"), "marks", 12000)
    assert broken.problems() == ["every mark is between 0 and 100"]
    object.__setattr__(broken.student("421123102001"), "marks", 8900)
    assert broken.problems() == []
    print(f"  search('cse') finds {len(table.search('cse'))} and search('ar') "
          f"finds {len(table.search('ar'))}; 5/5 checks pass, and one mark "
          f"forced to 120.00 fails exactly 1")

    print()
    print("Cross-checks OK: int(float('0.29') * 100) is 28 where the text "
          "parser gives 29 and '89.005' times 100 is exactly 8900.5 so a "
          "float cannot tell 89.00 from 89.005, three rows of 89.10 average "
          "to 89.09999999999998 in the legacy float where 26730/3 hundredths "
          "is exactly 89.10, 8900.5 hundredths rounds to 8900 with round() "
          "and 8901 half up, one save normalised 8 rows and the next was "
          "byte-identical, a renamed column was refused before any row was "
          "read, a year of 7 on line 4 named its line, a padded roll number "
          "was a duplicate here and not to the legacy string test, a save "
          "that failed after the header left the file untouched with no "
          "temporary file behind, the per-department report is 4 aggregated "
          "rows where the legacy report was the data file again, and the 5 "
          "invariants passed until one mark was forced out of range")
    print("\nDemo completed successfully.")
    return 0
