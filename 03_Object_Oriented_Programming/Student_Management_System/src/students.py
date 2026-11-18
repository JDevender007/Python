"""Students whose CGPA is computed from a transcript, not typed into a column.

The legacy project was SQLAlchemy over SQLite:

    class Student(Base):
        roll_number = Column(String(20), unique=True, nullable=False)
        name = Column(String(100), nullable=False)
        department = Column(String(50), nullable=False)
        year = Column(Integer, nullable=False)
        cgpa = Column(Float, nullable=False)
        email = Column(String(100), unique=True, nullable=False)
        phone = Column(String(15), unique=True, nullable=False)

    def search_student(self, keyword):
        return (self.session.query(Student)
                .filter((Student.roll_number == keyword)
                        | (Student.name.ilike(f"%{keyword}%")))
                .first())

    def top_scorer(self):
        return (self.session.query(Student)
                .order_by(desc(Student.cgpa))
                .first())

    service = StudentService()      # a database session, opened on import

There are no courses in that schema at all. Five things follow.

**1. ``cgpa`` is a column, so it is a claim.** The number is whatever the person
at the keyboard typed. A student with no marks on file can hold a CGPA of 9.2,
and nothing in the program can recompute it or disagree with it. Here
``Student.cgpa`` is a property that reads a transcript, and a transcript with no
credits *refuses to answer* -- ``NoCourses`` -- instead of inventing a zero.

**2. ``order_by(desc(Student.cgpa))`` ranks the claim.** The top scorer is
whoever typed the biggest number; a tie goes to whichever row the database
happened to return first.

**3. ``query.first()`` is not a search.** ``search_student("an")`` returns one
student out of however many match, and there is no way to ask for the rest.

**4. A CGPA is a credit-weighted mean, and a float is the wrong place to keep
it.** Three courses at 8.7, four at 9.1 and two at 7.6 come to
``77.69999999999999`` in a float; nine credits make that
``8.6333333333333329``. Kept as integer hundredths the sum is exactly ``7770``
and the answer is ``8.63``.

**5. A class is not a namespace.** ``Validator`` and ``Utils`` were classes
holding seven ``@staticmethod``s and a menu; nothing is ever instantiated, and
``service = StudentService()`` opens a session the moment the module is
imported. Here boundaries are functions and objects, and the CLI decides when to
open the file.

The lesson this project is built around is the last one, and it is a modelling
lesson rather than a bug:

**The scale is part of the answer.** ``B`` is worth 8.00 on a ten-point scale
and 3.00 on a four-point scale, so a grade without its scale means nothing. That
makes the scale a first-class object -- an abstract base class, ``GradeScale``,
that owns the behaviour (``points``, ``has``, ``normalise``, ``maximum``) and
lets each concrete scale supply only its table of levels. ``Transcript`` accepts
any ``GradeScale`` and refuses a grade that scale does not have, so a
four-point transcript cannot quietly borrow ten-point grades.

Everything numeric is exact: grade points are integer hundredths of a point
(``A`` is ``900``), ``Transcript.score`` is a ``fractions.Fraction`` used for
ordering, and ``round_half_up`` is applied only when a number is shown.

Standard library only: no ORM, no database file, no network.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "students.json"

#: The legacy CGPA column: a number a human typed.
LEGACY_CGPA = "cgpa = Column(Float, nullable=False)"

#: The legacy search: one row, whatever the database picked.
LEGACY_SEARCH = "query.first()"

#: The legacy ranking: order by the number in the column.
LEGACY_SORT = "order_by(desc(Student.cgpa))"

#: The legacy validator: a class with nothing but static methods.
LEGACY_VALIDATOR = "class Validator:"

#: The legacy service: a session opened when the module is imported.
LEGACY_IMPORT = "service = StudentService()"

#: The numbers the legacy ``cgpa`` column held for the seeded students.
LEGACY_CLAIMS = {
    "CE-2023-019": 9.08,
    "CS-2023-007": 7.50,
    "CS-2023-014": 8.93,
    "CS-2024-055": 9.20,
    "EC-2022-031": 9.00,
    "ME-2024-102": 7.30,
}

#: The departments the registry knows about.
DEPARTMENTS = ("Civil", "Computer Science", "Electronics", "Mechanical")

#: The largest number of credits one course may carry.
MAX_CREDITS_PER_COURSE = 12

#: A grade point is stored in hundredths: ``A`` on a ten-point scale is 900.
HUNDREDTHS = 100


class StudentError(ValueError):
    """A student, a course, a transcript, a scale or a file that is refused."""


class DuplicateStudent(StudentError):
    """A roll number, an email address or a phone number already on record."""


class UnknownStudent(StudentError):
    """No student with that roll number."""


class UnknownCourse(StudentError):
    """No course with that code on the transcript."""


class NoCourses(StudentError):
    """The transcript is empty, so there is no CGPA to report."""


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def check_whole(value, label: str = "a count") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StudentError(f"{label} must be a whole number, got "
                           f"{type(value).__name__}")
    if value < 0:
        raise StudentError(f"{label} must not be negative")
    return value


def round_half_up(numerator: int, denominator: int) -> int:
    """Half away from zero, on integers only."""
    if denominator <= 0:
        raise StudentError("the denominator must be positive")
    if numerator < 0:
        return -(((-numerator) * 2 + denominator) // (2 * denominator))
    return (numerator * 2 + denominator) // (2 * denominator)


def format_points(hundredths: int) -> str:
    """``875`` -> ``8.75``; the only place a grade point becomes text."""
    if isinstance(hundredths, bool) or not isinstance(hundredths, int):
        raise StudentError("only an integer number of hundredths can be shown")
    sign = "-" if hundredths < 0 else ""
    whole, fraction = divmod(abs(hundredths), HUNDREDTHS)
    return f"{sign}{whole}.{fraction:02d}"


def normalise_roll(value) -> str:
    """``cs-2023-014`` -> ``CS-2023-014``; the shape is checked too."""
    if not isinstance(value, str):
        raise StudentError(f"a roll number must be text, got "
                           f"{type(value).__name__}")
    roll = value.strip().upper()
    if not roll:
        raise StudentError("a roll number must not be empty")
    parts = roll.split("-")
    if len(parts) != 3:
        raise StudentError(f"{value!r} is not a roll number "
                           f"(expected DEPT-YEAR-SEQ, like CS-2023-014)")
    letters, year, serial = parts
    if not (2 <= len(letters) <= 4) or not letters.isalpha():
        raise StudentError(f"{value!r} needs 2 to 4 letters before the first "
                           f"dash, like CS-2023-014")
    if len(year) != 4 or not year.isdigit():
        raise StudentError(f"{value!r} needs four digits for the year, like "
                           f"CS-2023-014")
    if len(serial) != 3 or not serial.isdigit():
        raise StudentError(f"{value!r} needs three digits at the end, like "
                           f"CS-2023-014")
    return roll


def normalise_email(value) -> str:
    """Trim, lower-case and prove the shape: one ``@`` and a dotted domain."""
    if not isinstance(value, str):
        raise StudentError(f"an email address must be text, got "
                           f"{type(value).__name__}")
    email = value.strip().lower()
    if not email:
        raise StudentError("an email address must not be empty")
    if email.count("@") != 1:
        raise StudentError(f"{value!r} must contain exactly one '@'")
    local, domain = email.split("@")
    if not local:
        raise StudentError(f"{value!r} has nothing before the '@'")
    if "." not in domain:
        raise StudentError(f"{value!r} needs a domain with a dot, like "
                           f"name@example.edu")
    if domain.startswith(".") or domain.endswith(".") or " " in email:
        raise StudentError(f"{value!r} is not an email address")
    if not all(character.isalnum() or character in "._%+-"
               for character in local):
        raise StudentError(f"{value!r} has a character an email cannot hold "
                           f"before the '@'")
    if not all(character.isalnum() or character in ".-"
               for character in domain):
        raise StudentError(f"{value!r} has a character an email cannot hold "
                           f"after the '@'")
    return email


def normalise_phone(value) -> str:
    """Ten digits, with spaces and hyphens taken out first."""
    if not isinstance(value, str):
        raise StudentError(f"a phone number must be text, got "
                           f"{type(value).__name__}")
    digits = value.replace(" ", "").replace("-", "").strip()
    if not digits:
        raise StudentError("a phone number must not be empty")
    if not digits.isdigit():
        raise StudentError(f"{value!r} must be ten digits, with nothing but "
                           f"spaces or hyphens between them")
    if len(digits) != 10:
        raise StudentError(f"{value!r} has {len(digits)} digits; a phone "
                           f"number has ten")
    return digits


def normalise_department(value) -> str:
    """Accept any casing of a known department, store the canonical name."""
    if not isinstance(value, str):
        raise StudentError(f"a department must be text, got "
                           f"{type(value).__name__}")
    wanted = " ".join(value.split())
    for department in DEPARTMENTS:
        if wanted.casefold() == department.casefold():
            return department
    raise StudentError(f"{value!r} is not a department "
                       f"(choose from {', '.join(DEPARTMENTS)})")


def check_year(value) -> int:
    year = check_whole(value, "the year")
    if not 1 <= year <= 4:
        raise StudentError(f"the year must be 1, 2, 3 or 4, got {year}")
    return year


# --------------------------------------------------------------------------- #
# The scale: an abstract base class that owns the behaviour
# --------------------------------------------------------------------------- #
class GradeScale(ABC):
    """A grade table. Subclasses supply ``levels``; this class does the rest.

    ``name`` and ``levels`` are the only abstract members. ``points``,
    ``has``, ``normalise``, ``maximum`` and the rest are written once here and
    work for every scale, which is the point of the base class: a new scale is
    a table of numbers, not a new implementation.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The short name used in data files and error messages."""

    @property
    @abstractmethod
    def levels(self) -> dict[str, int]:
        """Grade -> grade points, in hundredths, highest first is not needed."""

    def __init_subclass__(cls, **kwargs) -> None:
        """Check the table at class-creation time, not on first use."""
        super().__init_subclass__(**kwargs)
        levels = cls.__dict__.get("levels")
        if levels is None:
            return                      # still abstract; nothing to check
        if isinstance(levels, property):
            if getattr(levels, "__isabstractmethod__", False):
                return                  # re-declared abstract; still abstract
            raise TypeError("a scale's levels must be a dict, not a property")
        if not isinstance(levels, dict) or not levels:
            raise TypeError("a scale's levels must be a non-empty dict")
        for grade, points in levels.items():
            if not isinstance(grade, str) or grade != grade.strip().upper() \
                    or not grade.strip():
                raise TypeError(f"{grade!r} is not an upper-case grade name")
            if isinstance(points, bool) or not isinstance(points, int):
                raise TypeError(f"{grade!r} must map to a whole number of "
                                f"hundredths")
            if points < 0:
                raise TypeError(f"{grade!r} must not map to a negative "
                                f"number")
        if max(levels.values()) == 0:
            raise TypeError("a scale needs at least one grade worth "
                            "something")

    # -- the behaviour every scale gets ------------------------------------ #
    def normalise(self, grade) -> str:
        if not isinstance(grade, str):
            raise StudentError(f"a grade must be text, got "
                               f"{type(grade).__name__}")
        key = grade.strip().upper()
        if not key:
            raise StudentError("a grade must not be empty")
        return key

    def points(self, grade) -> int:
        key = self.normalise(grade)
        try:
            return self.levels[key]
        except KeyError:
            raise StudentError(
                f"{key!r} is not on the {self.name} scale (allowed: "
                f"{', '.join(self.ordered_grades())})") from None

    def has(self, grade) -> bool:
        """True or False; never raises, so it is safe on user input."""
        try:
            key = self.normalise(grade)
        except StudentError:
            return False
        return key in self.levels

    def ordered_grades(self) -> tuple[str, ...]:
        """Every grade, best first."""
        return tuple(sorted(self.levels, key=lambda grade: (-self.levels[grade],
                                                            grade)))

    @property
    def maximum(self) -> int:
        return max(self.levels.values())

    @property
    def top_grade(self) -> str:
        return self.ordered_grades()[0]

    def __contains__(self, grade) -> bool:
        return self.has(grade)

    def __len__(self) -> int:
        return len(self.levels)

    def __repr__(self) -> str:
        return (f"<{type(self).__name__} {self.name}, {len(self)} grades, "
                f"top {format_points(self.maximum)}>")


class TenPointScale(GradeScale):
    """A ten-point scale: ``A+`` is 10.00, ``F`` is 0.00."""

    name = "ten-point"
    levels = {
        "A+": 1000,
        "A": 900,
        "B+": 800,
        "B": 700,
        "C+": 600,
        "C": 500,
        "D": 400,
        "F": 0,
    }


class FourPointScale(GradeScale):
    """A four-point scale: ``A`` is 4.00 and there are no plus grades."""

    name = "four-point"
    levels = {
        "A": 400,
        "B": 300,
        "C": 200,
        "D": 100,
        "F": 0,
    }


#: The scales that can be named in a data file.
SCALES = {"four-point": FourPointScale, "ten-point": TenPointScale}


def scale_named(text) -> GradeScale:
    """``"ten-point"`` -> a ``TenPointScale``; anything else is refused."""
    if not isinstance(text, str):
        raise StudentError(f"a scale name must be text, got "
                           f"{type(text).__name__}")
    wanted = text.strip().lower()
    try:
        return SCALES[wanted]()
    except KeyError:
        raise StudentError(f"{text!r} is not a scale (choose from "
                           f"{', '.join(sorted(SCALES))})") from None


def _wrong_scale(value) -> str:
    """``got ABCMeta`` says nothing; name a class the caller forgot to build."""
    if isinstance(value, type):
        return "got a class, not an instance"
    return f"got {type(value).__name__}"


# --------------------------------------------------------------------------- #
# Course: one row of a transcript
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Course:
    """A course code, a title, the credits it carries and the grade earned."""

    code: str
    title: str
    credits: int
    grade: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str):
            raise StudentError(f"a course code must be text, got "
                               f"{type(self.code).__name__}")
        code = self.code.strip().upper()
        if not code:
            raise StudentError("a course needs a code")
        if " " in code:
            raise StudentError(f"{self.code!r} contains whitespace; a course "
                               f"code has none")
        if not isinstance(self.title, str) or not self.title.strip():
            raise StudentError(f"{code} needs a title")
        credits = check_whole(self.credits, "credits")
        if not 1 <= credits <= MAX_CREDITS_PER_COURSE:
            raise StudentError(f"{code} carries 1 to "
                               f"{MAX_CREDITS_PER_COURSE} credits, not "
                               f"{credits}")
        if not isinstance(self.grade, str) or not self.grade.strip():
            raise StudentError(f"{code} needs a grade")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "grade", self.grade.strip().upper())

    def __str__(self) -> str:
        return (f"{self.code:<10} {self.title:<28.28} {self.credits:>2}cr  "
                f"{self.grade}")

    def to_dict(self) -> dict:
        return {"code": self.code, "title": self.title,
                "credits": self.credits, "grade": self.grade}

    @classmethod
    def from_dict(cls, row) -> "Course":
        if not isinstance(row, dict):
            raise StudentError("a course must be an object")
        unknown = set(row) - {"code", "title", "credits", "grade"}
        if unknown:
            raise StudentError(f"unknown course keys: {sorted(unknown)}")
        for key in ("code", "title", "credits", "grade"):
            if key not in row:
                raise StudentError(f"a course is missing {key!r}")
        return cls(row["code"], row["title"], row["credits"], row["grade"])


# --------------------------------------------------------------------------- #
# Transcript: the courses that make a CGPA, on one scale
# --------------------------------------------------------------------------- #
class Transcript:
    """The courses a student has taken, and the CGPA they add up to."""

    def __init__(self, scale=None):
        self.scale = TenPointScale() if scale is None else scale
        self._courses: dict[str, Course] = {}

    # -- the scale ---------------------------------------------------------- #
    @property
    def scale(self) -> GradeScale:
        return self._scale

    @scale.setter
    def scale(self, value) -> None:
        if not isinstance(value, GradeScale):
            raise StudentError("a transcript needs a GradeScale, "
                               f"{_wrong_scale(value)}")
        self._scale = value

    # -- collection protocol ------------------------------------------------ #
    def __len__(self) -> int:
        return len(self._courses)

    def __iter__(self):
        return iter([self._courses[code] for code in sorted(self._courses)])

    def __contains__(self, code) -> bool:
        if not isinstance(code, str):
            return False
        return code.strip().upper() in self._courses

    def __getitem__(self, code) -> Course:
        if not isinstance(code, str):
            raise UnknownCourse(f"no course with code {code!r}")
        key = code.strip().upper()
        try:
            return self._courses[key]
        except KeyError:
            raise UnknownCourse(f"no course with code {key} on this "
                                f"transcript") from None

    def __repr__(self) -> str:
        return (f"<Transcript {len(self)} course(s), {self.credits} credits "
                f"on the {self.scale.name} scale>")

    @property
    def courses(self) -> tuple[Course, ...]:
        return tuple(self)

    # -- adding ------------------------------------------------------------- #
    def add(self, course: Course) -> Course:
        """Record a course; a second attempt at the same code replaces it."""
        if not isinstance(course, Course):
            raise StudentError("only a Course can go on a transcript, got "
                               f"{type(course).__name__}")
        self.scale.points(course.grade)         # names the scale if refused
        self._courses[course.code] = course
        return course

    def retake(self, code, grade) -> Course:
        """Replace the grade of a course already on the transcript."""
        course = self[code]
        return self.add(Course(course.code, course.title, course.credits,
                               grade))

    def remove(self, code) -> Course:
        course = self[code]
        del self._courses[course.code]
        return course

    # -- the numbers -------------------------------------------------------- #
    @property
    def credits(self) -> int:
        return sum(course.credits for course in self._courses.values())

    @property
    def credit_points(self) -> int:
        """Credit-weighted grade points, in hundredths: ``sum(credits * p)``."""
        return sum(course.credits * self.scale.points(course.grade)
                   for course in self._courses.values())

    @property
    def score(self) -> Fraction:
        """The exact CGPA in hundredths, as a fraction -- for ordering."""
        if not self.credits:
            raise NoCourses("this transcript has no credits, so there is no "
                            "CGPA to report")
        return Fraction(self.credit_points, self.credits)

    def gpa_hundredths(self) -> int:
        """The CGPA rounded to whole hundredths, half away from zero."""
        if not self.credits:
            raise NoCourses("this transcript has no credits, so there is no "
                            "CGPA to report")
        return round_half_up(self.credit_points, self.credits)

    def gpa(self) -> str:
        return format_points(self.gpa_hundredths())

    def grade_counts(self) -> dict[str, int]:
        """How many courses carry each grade, best first."""
        counts: dict[str, int] = {}
        for course in self._courses.values():
            counts[course.grade] = counts.get(course.grade, 0) + 1
        return {grade: counts[grade] for grade in self.scale.ordered_grades()
                if grade in counts}

    # -- persistence -------------------------------------------------------- #
    def to_dict(self) -> list:
        return [course.to_dict() for course in self]

    @classmethod
    def from_dict(cls, payload, scale=None) -> "Transcript":
        if not isinstance(payload, list):
            raise StudentError("a transcript must be a list of courses")
        transcript = cls(scale)
        for row in payload:
            transcript.add(Course.from_dict(row))
        return transcript


# --------------------------------------------------------------------------- #
# Student: the CGPA is a property, not a column
# --------------------------------------------------------------------------- #
class Student:
    """One student and the courses that decide their CGPA."""

    def __init__(self, roll, name, department, year, email, phone,
                 transcript=None):
        self.roll = normalise_roll(roll)
        if not isinstance(name, str) or not name.strip():
            raise StudentError("a student needs a name")
        self.name = " ".join(name.split())
        self.department = normalise_department(department)
        self.year = check_year(year)
        self.email = normalise_email(email)
        self.phone = normalise_phone(phone)
        if transcript is None:
            transcript = Transcript()
        if not isinstance(transcript, Transcript):
            raise StudentError("a student needs a Transcript, got "
                               f"{type(transcript).__name__}")
        self.transcript = transcript

    # -- derived numbers ---------------------------------------------------- #
    @property
    def cgpa(self) -> str:
        """Computed from the transcript; there is nowhere to store it."""
        return self.transcript.gpa()

    @property
    def score(self) -> Fraction:
        return self.transcript.score

    @property
    def credits(self) -> int:
        return self.transcript.credits

    @property
    def courses(self) -> tuple[Course, ...]:
        return self.transcript.courses

    @property
    def cgpa_text(self) -> str:
        """The CGPA, or a dash when there are no courses yet."""
        return self.transcript.gpa() if self.credits else "-"

    # -- courses ------------------------------------------------------------ #
    def add_course(self, course: Course) -> Course:
        return self.transcript.add(course)

    def retake(self, code, grade) -> Course:
        return self.transcript.retake(code, grade)

    # -- display ------------------------------------------------------------ #
    def __repr__(self) -> str:
        return f"<Student {self.roll} {self.name!r} {self.cgpa_text}>"

    def __str__(self) -> str:
        return (f"{self.roll:<13} {self.name:<18.18} {self.department:<18.18} "
                f"{self.year}  {self.credits:>3}cr  {self.cgpa_text:>5}")

    # -- persistence -------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"roll": self.roll, "name": self.name,
                "department": self.department, "year": self.year,
                "email": self.email, "phone": self.phone,
                "courses": self.transcript.to_dict()}

    @classmethod
    def from_dict(cls, row, scale=None) -> "Student":
        if not isinstance(row, dict):
            raise StudentError("a student must be an object")
        unknown = set(row) - {"roll", "name", "department", "year", "email",
                              "phone", "courses"}
        if "cgpa" in row:
            raise StudentError("a student has no stored cgpa; it is computed "
                               "from the courses")
        if unknown:
            raise StudentError(f"unknown student keys: {sorted(unknown)}")
        for key in ("roll", "name", "department", "year", "email", "phone",
                    "courses"):
            if key not in row:
                raise StudentError(f"a student is missing {key!r}")
        transcript = Transcript.from_dict(row["courses"], scale)
        return cls(row["roll"], row["name"], row["department"], row["year"],
                   row["email"], row["phone"], transcript)


# --------------------------------------------------------------------------- #
# Registry: the collection, and the ranking the legacy project did not have
# --------------------------------------------------------------------------- #
class Registry:
    """Students, one per roll number, on a single grade scale."""

    def __init__(self, name: str = "Northgate Institute", scale=None):
        if not isinstance(name, str) or not name.strip():
            raise StudentError("the registry needs a name")
        self.name = name.strip()
        self.scale = TenPointScale() if scale is None else scale
        self._students: dict[str, Student] = {}

    # -- the scale ---------------------------------------------------------- #
    @property
    def scale(self) -> GradeScale:
        return self._scale

    @scale.setter
    def scale(self, value) -> None:
        if not isinstance(value, GradeScale):
            raise StudentError("a registry needs a GradeScale, "
                               f"{_wrong_scale(value)}")
        self._scale = value

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
        except StudentError:
            return False

    def __getitem__(self, roll) -> Student:
        return self.student(roll)

    def __repr__(self) -> str:
        return (f"<Registry {self.name!r} with {len(self)} students, "
                f"{self.total_credits} credits on the {self.scale.name} "
                f"scale>")

    @property
    def students(self) -> tuple[Student, ...]:
        return tuple(self)

    @property
    def total_credits(self) -> int:
        return sum(student.credits for student in self._students.values())

    # -- lookups ------------------------------------------------------------ #
    def student(self, roll) -> Student:
        key = normalise_roll(roll)
        try:
            return self._students[key]
        except KeyError:
            raise UnknownStudent(f"no student with roll number {key}") \
                from None

    def search(self, text) -> list[Student]:
        """Every student whose roll, name, department or email matches."""
        if not isinstance(text, str):
            raise StudentError("a search needs text")
        needle = " ".join(text.split()).casefold()
        if not needle:
            raise StudentError("a search needs something to look for")
        return [student for student in self
                if needle in student.roll.casefold()
                or needle in student.name.casefold()
                or needle in student.department.casefold()
                or needle in student.email.casefold()]

    # -- adding and removing ------------------------------------------------ #
    def add(self, student: Student) -> Student:
        if not isinstance(student, Student):
            raise StudentError("only a Student can be registered, got "
                               f"{type(student).__name__}")
        if student.transcript.scale.name != self.scale.name:
            raise StudentError(
                f"{student.roll} is graded on the "
                f"{student.transcript.scale.name} scale and this registry "
                f"uses the {self.scale.name} scale")
        if student.roll in self._students:
            raise DuplicateStudent(
                f"{student.roll} is already registered as "
                f"{self._students[student.roll].name!r}")
        for other in self._students.values():
            if other.email == student.email:
                raise DuplicateStudent(
                    f"{student.email} is already registered to "
                    f"{other.roll}")
            if other.phone == student.phone:
                raise DuplicateStudent(
                    f"{student.phone} is already registered to "
                    f"{other.roll}")
        self._students[student.roll] = student
        return student

    def remove(self, roll) -> Student:
        student = self.student(roll)
        del self._students[student.roll]
        return student

    # -- reports ------------------------------------------------------------ #
    def top(self, count: int = 3) -> list[Student]:
        """The best CGPAs, ranked by the exact score and then by roll."""
        wanted = check_whole(count, "the number of students to rank")
        if wanted < 1:
            raise StudentError("the number of students to rank must be at "
                               "least one")
        return sorted(self._students.values(),
                      key=lambda student: (-student.score, student.roll)
                      )[:wanted]

    def by_department(self) -> dict[str, tuple[Student, ...]]:
        grouped: dict[str, list[Student]] = {}
        for student in self:
            grouped.setdefault(student.department, []).append(student)
        return {department: tuple(grouped[department])
                for department in sorted(grouped)}

    def mean_credits(self) -> int:
        if not self._students:
            return 0
        return round_half_up(self.total_credits, len(self._students))

    # -- invariants --------------------------------------------------------- #
    def audit(self) -> list[tuple[str, bool]]:
        """Five invariants, each reported by name and verdict."""
        checks = []

        filed = all(roll == student.roll
                    for roll, student in self._students.items())
        checks.append(("every student is filed under its roll number", filed))

        emails = [student.email for student in self._students.values()]
        checks.append(("no two students share an email address",
                       len(set(emails)) == len(emails)))

        phones = [student.phone for student in self._students.values()]
        checks.append(("no two students share a phone number",
                       len(set(phones)) == len(phones)))

        empty = [student.roll for student in self._students.values()
                 if student.credits == 0]
        checks.append(("every student has at least one course", not empty))

        foreign = [f"{student.roll}/{course.code}"
                   for student in self._students.values()
                   for course in student.courses
                   if not self.scale.has(course.grade)]
        checks.append((f"every course grade is on the {self.scale.name} "
                       f"scale", not foreign))
        return checks

    def problems(self) -> list[str]:
        return [name for name, passed in self.audit() if not passed]

    # -- persistence -------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"name": self.name, "scale": self.scale.name,
                "students": [student.to_dict() for student in self]}

    @classmethod
    def from_dict(cls, payload) -> "Registry":
        if not isinstance(payload, dict):
            raise StudentError("a registry document must be an object")
        unknown = set(payload) - {"name", "scale", "students"}
        if unknown:
            raise StudentError(f"unknown registry keys: {sorted(unknown)}")
        for key in ("name", "scale", "students"):
            if key not in payload:
                raise StudentError(f"the registry is missing {key!r}")
        if not isinstance(payload["students"], list):
            raise StudentError("'students' must be a list")
        registry = cls(payload["name"], scale_named(payload["scale"]))
        for row in payload["students"]:
            registry.add(Student.from_dict(row, registry.scale))
        return registry


def load_registry(path=DATA_FILE) -> Registry:
    path = Path(path)
    if not path.exists():
        raise StudentError(f"student file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StudentError(f"{path.name} is not valid JSON: {exc}") from None
    return Registry.from_dict(payload)


def save_registry(path, registry: Registry) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict(), indent=2) + "\n",
                    encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# The legacy project, transcribed so the demo can prove it wrong
# --------------------------------------------------------------------------- #
def legacy_gpa(rows) -> float:
    """``sum(credits * points) / sum(credits)`` with points as floats."""
    credits = sum(count for count, _ in rows)
    if not credits:
        raise StudentError("there are no credits to average")
    return sum(count * points for count, points in rows) / credits


def legacy_record(cgpa, courses: int = 0) -> dict:
    """One row of the legacy table: a number and however many courses it has."""
    return {"cgpa": float(cgpa), "courses": courses}


def legacy_rows(registry: Registry) -> list:
    """What the legacy column would hold for the seeded students."""
    return [{"roll": student.roll, "cgpa": LEGACY_CLAIMS[student.roll]}
            for student in registry if student.roll in LEGACY_CLAIMS]


def legacy_top(rows):
    """``order_by(desc(Student.cgpa)).first()``: the biggest typed number."""
    if not rows:
        raise StudentError("there are no students to rank")
    return max(rows, key=lambda row: row["cgpa"])


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 74)
    print(" STUDENTS - a typed CGPA, and a CGPA computed from a transcript")
    print("=" * 74)

    # 1. the base class is abstract, and only the table is left to a scale
    abstract = 0
    for factory in (GradeScale,):
        try:
            factory()
        except TypeError as exc:
            abstract += 1
            assert "levels" in str(exc) and "name" in str(exc)
        else:
            raise AssertionError("GradeScale was instantiated")
    try:
        type("HalfScale", (GradeScale,), {"name": "half"})()
    except TypeError as exc:
        abstract += 1
        assert "levels" in str(exc)
    else:
        raise AssertionError("a subclass without levels was instantiated")
    ten, four = TenPointScale(), FourPointScale()
    assert isinstance(ten, GradeScale) and isinstance(four, GradeScale)
    assert abstract == 2 and len(ten) == 8 and len(four) == 5
    print(f"  GradeScale() and a subclass without levels were both refused "
          f"({abstract} TypeErrors); the two concrete scales have "
          f"{len(ten)} and {len(four)} grades")

    # 2. the same letter is a different number on a different scale
    assert ten.points("B") == 700 and four.points("B") == 300
    refused = 0
    for grade in ("A+", "B+"):
        try:
            four.points(grade)
        except StudentError:
            refused += 1
        else:
            raise AssertionError(f"the four-point scale took {grade}")
    assert refused == 2
    graded_ten, graded_four = Transcript(ten), Transcript(four)
    graded_ten.add(Course("CS301", "Algorithms", 3, "B"))
    graded_four.add(Course("CS301", "Algorithms", 3, "B"))
    assert graded_ten.gpa() == "7.00" and graded_four.gpa() == "3.00"
    print(f"  'B' is {ten.points('B')} hundredths on the {ten.name} scale and "
          f"{four.points('B')} on the {four.name} scale: one 3-credit course "
          f"reads {graded_ten.gpa()} against {graded_four.gpa()}; the "
          f"four-point scale refused {refused} ten-point grades")

    # 3. credits are weights, not a count
    weighted = Transcript()
    for code, credits, grade in (("CS301", 4, "A"), ("CS302", 3, "B+"),
                                 ("CS303", 3, "B")):
        weighted.add(Course(code, code, credits, grade))
    assert weighted.credits == 10 and weighted.credit_points == 8100
    assert weighted.gpa() == "8.10"
    assert format_points(round_half_up(2400, 3)) == "8.00"
    print(f"  4/3/3 credits at A/B+/B: weighted {weighted.gpa()} from "
          f"{weighted.credit_points} grade points over {weighted.credits} "
          f"credits; a plain mean of the same grades is "
          f"{format_points(round_half_up(2400, 3))}")

    # 4. the float the legacy table held
    rows = [(3, 8.7), (4, 9.1), (2, 7.6)]
    drift = format(legacy_gpa(rows), ".17g")
    assert drift == "8.6333333333333329"
    exact = sum(count * round(points * 100) for count, points in rows)
    assert exact == 7770 and round_half_up(exact, 9) == 863
    assert format_points(round_half_up(exact, 9)) == "8.63"
    print(f"  the float mean of 3x8.7, 4x9.1, 2x7.6 is {drift}; in integer "
          f"hundredths {exact}/9 is "
          f"{format_points(round_half_up(exact, 9))}")

    # 5. a retake replaces the attempt, it does not add a second course
    retaken = Transcript()
    retaken.add(Course("CS301", "Algorithms", 3, "B"))
    before = retaken.gpa()
    retaken.retake("cs301", "c")
    after = (retaken.credits, retaken.gpa())
    assert after == (3, "5.00")
    retaken.add(Course("CS302", "Databases", 2, "A"))
    assert len(retaken) == 2 and retaken.credits == 5
    assert retaken.gpa() == "6.60"
    try:
        retaken.retake("CS999", "A")
    except UnknownCourse as exc:
        missing = str(exc)
    else:
        raise AssertionError("a retake of a course that is not there passed")
    print(f"  retake CS301 moved the CGPA {before} -> {after[1]} and kept "
          f"{after[0]} credits; a second course made it {retaken.gpa()} over "
          f"{retaken.credits} credits, and an unknown retake was refused "
          f"({missing[:24]}...)")

    # 6. no courses means no CGPA -- unlike a typed column
    fresh = Student("CS-2024-099", "Nadia Iqbal", "Computer Science", 1,
                    "nadia.iqbal@example.edu", "9000000000")
    try:
        fresh.cgpa
    except NoCourses as exc:
        empty_message = str(exc)
    else:
        raise AssertionError("an empty transcript produced a CGPA")
    claim = legacy_record(8.7)
    assert claim == {"cgpa": 8.7, "courses": 0}
    assert fresh.cgpa_text == "-" and fresh.credits == 0
    print(f"  a new student has no CGPA ({empty_message[:38]}...); the "
          f"legacy row answers {claim['cgpa']} from {claim['courses']} "
          f"courses")

    # 7. duplicates are refused, and a search returns every match
    registry = load_registry()
    twins = 0
    for email, phone, roll in (("ASHA.RAO@Example.edu", "9100000001",
                                "CS-2024-090"),
                               ("new.person@example.edu", "9876543210",
                                "CS-2024-091"),
                               ("other@example.edu", "9100000003",
                                "cs-2023-014")):
        twin = Student(roll, "Twin Person", "Computer Science", 1, email,
                       phone)
        twin.add_course(Course("CS101", "Intro", 3, "A"))
        try:
            registry.add(twin)
        except DuplicateStudent:
            twins += 1
        else:
            raise AssertionError(f"{roll} was registered twice")
    assert twins == 3 and len(registry) == 6
    found = registry.search("an")
    assert [student.roll for student in found] == \
        ["CS-2023-007", "CS-2024-055", "ME-2024-102"]
    assert len(registry.search("a")) == 6
    print(f"  three duplicates refused (email across case, phone, roll); "
          f"search('an') returns {len(found)} and search('a') returns "
          f"{len(registry.search('a'))}, where query.first() returns 1")

    # 8. the typed claim against the computed transcript
    claimed = legacy_top(legacy_rows(registry))
    best = registry.top(1)[0]
    assert claimed["roll"] == "CS-2024-055" and claimed["cgpa"] == 9.20
    assert best.roll == "CE-2023-019" and best.cgpa == "9.08"
    assert claimed["roll"] != best.roll
    print(f"  the legacy column ranks {claimed['roll']} first on a typed "
          f"{claimed['cgpa']:.2f}; the transcript ranks {best.roll} first on "
          f"a computed {best.cgpa}")

    # 9. ordering is exact even when two CGPAs print the same
    class ProbeScale(GradeScale):
        name = "probe"
        levels = {"X": 833, "Y": 834}

    probe = ProbeScale()
    lower, higher = Transcript(probe), Transcript(probe)
    for index in range(4):
        lower.add(Course(f"P{index}", "Probe", 3, "X"))
        higher.add(Course(f"P{index}", "Probe", 3, "Y" if index == 3 else "X"))
    assert lower.gpa() == higher.gpa() == "8.33"
    assert lower.gpa_hundredths() == higher.gpa_hundredths() == 833
    assert lower.score == Fraction(833) and higher.score == Fraction(3333, 4)
    assert sorted([higher, lower], key=lambda sheet: sheet.score)[1] is higher
    print(f"  3332/4 and 3333/4 both print {lower.gpa()}; the exact scores "
          f"{float(lower.score):.2f} and {float(higher.score):.2f} still "
          f"order them")

    # 10. the seeded registry, and one broken grade
    assert len(registry) == 6 and registry.total_credits == 80
    assert [student.roll for student in registry.top(3)] == \
        ["CE-2023-019", "EC-2022-031", "CS-2023-014"]
    assert registry.mean_credits() == 13
    assert len(registry.audit()) == 5 and registry.problems() == []
    assert [student.roll for student in registry] == [
        "CE-2023-019", "CS-2023-007", "CS-2023-014", "CS-2024-055",
        "EC-2022-031", "ME-2024-102"]
    assert list(registry.by_department()) == ["Civil", "Computer Science",
                                              "Electronics", "Mechanical"]
    broken = Registry.from_dict(registry.to_dict())
    broken.student("CS-2023-014").transcript._courses["CS301"] = \
        Course("CS301", "Algorithms", 4, "Z")
    assert broken.problems() == ["every course grade is on the ten-point "
                                 "scale"]
    print(f"  seeded: {len(registry)} students, {registry.total_credits} "
          f"credits, top 3 CE/EC/CS at "
          f"{', '.join(s.cgpa for s in registry.top(3))}, mean "
          f"{registry.mean_credits()} credits, 5/5 checks; a forced 'Z' "
          f"grade fails exactly 1")

    # 11. save and load
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "copy.json"
        save_registry(target, registry)
        first_bytes = target.read_bytes()
        save_registry(target, load_registry(target))
        assert target.read_bytes() == first_bytes
        assert load_registry(target).to_dict() == registry.to_dict()
        assert "cgpa" not in target.read_text(encoding="utf-8")
    print("  the seeded registry saves and reloads byte for byte, and the "
          "file holds no cgpa")

    print()
    print("Cross-checks OK: GradeScale refused 2 attempts to instantiate it "
          "while two concrete scales were built from a table alone, the same "
          "'B' graded 7.00 on the ten-point scale and 3.00 on the four-point "
          "scale with 2 plus grades refused, 4/3/3 credits at A/B+/B weighed "
          "8.10 against a plain mean of 8.00, the legacy float mean drifted "
          "to 8.6333333333333329 where 7770/9 is 8.63, a retake replaced an "
          "attempt instead of adding one and an unknown retake was refused, "
          "an empty transcript refused to name a CGPA while a legacy row "
          "claimed 8.7 from 0 courses, 3 duplicates were refused across "
          "case, phone and roll and search found 3 students where "
          "query.first() found 1, the typed claim ranked CS-2024-055 first "
          "against the computed CE-2023-019, two CGPAs that both print 8.33 "
          "were still ordered exactly, the seeded 6 students and 80 credits "
          "ranked CE/EC/CS with 5/5 checks while one forced 'Z' grade failed "
          "exactly 1, and the file round-tripped byte for byte with no cgpa "
          "in it")
    print("Demo completed successfully.")
    return 0
