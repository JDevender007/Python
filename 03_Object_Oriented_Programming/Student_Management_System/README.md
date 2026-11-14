<div align="center">

# 🎓 Student Management System

### The legacy project stored the CGPA in a `Float` column — a number somebody typed. Nothing in the program could recompute it, disagree with it, or notice that the student it belonged to had no courses at all. A student with an empty transcript could hold a 9.2, and `order_by(desc(Student.cgpa))` would rank that claim above every real result.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old model was a table with a scalar where a computation belonged:

```python
class Student(Base):
    __tablename__ = "students"

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
```

There is no course table anywhere in that schema. Five things follow.

**1 · `cgpa` is a column, so it is a claim.** Whatever number was typed at the
keyboard is the number the program believes. It cannot be recomputed, and
nothing can contradict it.

**2 · `order_by(desc(Student.cgpa))` ranks the claim.** The top scorer is whoever
typed the biggest number. A tie goes to whichever row the database returns
first.

**3 · `query.first()` is not a search.** It returns one student out of however
many match, and there is no way to ask for the rest.

**4 · A CGPA is a credit-weighted mean, and a float is the wrong place to keep
it.** Three courses at 8.7, four at 9.1 and two at 7.6 come to
`77.69999999999999`; nine credits make that `8.6333333333333329`. In integer
hundredths the sum is exactly `7770` and the answer is `8.63`.

**5 · A class is not a namespace.** `Validator` and `Utils` were classes holding
`@staticmethod`s and a menu, never instantiated, while
`service = StudentService()` opened a session the moment the module was
imported. Here boundaries are functions and objects, and the CLI decides when to
open the file.

The lesson the project is built around is a modelling one rather than a bug:

**The scale is part of the answer.** `B` is worth 8.00 on a ten-point scale and
3.00 on a four-point scale, so a grade without its scale means nothing. That
makes the scale a first-class object: an abstract base class, `GradeScale`, that
owns the behaviour (`points`, `has`, `normalise`, `maximum`, `ordered_grades`)
and lets each concrete scale supply only its table of levels. `Transcript`
accepts any `GradeScale` and refuses a grade that scale does not have, so a
four-point transcript cannot quietly borrow ten-point grades.

Everything numeric is exact: grade points are integer hundredths (`A` is `900`),
`Transcript.score` is a `fractions.Fraction` used for ordering, and
`round_half_up` is applied only when a number is shown.

Standard library only: no ORM, no database file, no network.

---

# ✨ Features

- `GradeScale` — an ABC that refuses instantiation and validates the grade table at **class-creation** time, not on first use
- `TenPointScale` / `FourPointScale` — a `dict` of grades and hundredths, and nothing else
- `scale_named` / `SCALES` — the two scales a data file may name
- `Course` — frozen dataclass; code, title, 1–12 credits, grade; value equality, hashable
- `Transcript` — one scale, a dict of courses, `add` / `retake` / `remove`, plus collection protocol
- `credit_points` / `score` / `gpa_hundredths` / `gpa` — weighted on credits, exact in `Fraction`, rounded half-up only to show
- `Student` — `cgpa` is a **property** over the transcript; there is nowhere to store it
- `NoCourses` — an empty transcript refuses to name a CGPA instead of inventing a zero
- `Registry` — one student per roll number, one scale, duplicate refusal across roll, email and phone
- `search` — every match across roll, name, department and email
- `top` — ranked by the exact `Fraction` score, ties broken by roll number
- `audit` — five named invariants, each reported pass or fail
- `LEGACY_CLAIMS` and the transcribed `legacy_*` helpers — the typed column, kept executable
- `data/students.json` — 6 students, 4 departments, 80 credits, no `cgpa` key
- CLI: `--students`, `--search`, `--student`, `--top`, `--department`, `--report`, `--add`, `--course`, `--retake`, `--audit`, `--legacy`, `--write`, `--json`, `--quiet`
- Exit `2` on a `StudentError`; `--demo` always returns `0`
- 374 passing pytest tests

---

# 📂 Folder Structure

```text
Student_Management_System/
│
├── src/
│   ├── main.py     # CLI: list, search, rank, add, record, retake, audit
│   └── students.py # GradeScale, Course, Transcript, Student, Registry, the demo
│
├── tests/
│   └── test_students.py
│
├── data/
│   └── students.json  # 6 students, 80 credits, no cgpa
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 03_Object_Oriented_Programming/Student_Management_System

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# Every student, with credits and CGPA
python src/main.py

# Find a student
python src/main.py --search khan
python src/main.py --search an

# One student's transcript
python src/main.py --student CS-2023-014

# Who is doing best
python src/main.py --top 3

# By department
python src/main.py --department "computer science"
python src/main.py --report

# Change the record
python src/main.py --add CS-2024-090:Nadia Iqbal:Computer Science:1:nadia.iqbal@example.edu:9000000000
python src/main.py --course CS-2023-014:CS304:Compilers:4:A
python src/main.py --retake CS-2023-007:CS301:B

# The five invariants
python src/main.py --audit

# What the legacy column did
python src/main.py --legacy
```

**Exit codes:** `0` = the command ran · `2` = an unknown student, an unknown
course, a bad roll number, department, year, email or phone, a duplicate, a
grade the scale does not have, a malformed spec, or a missing data file.

---

# 🧠 How It Works

```text
 GradeScale (ABC)      levels  ->  the only thing a scale supplies
   ├── normalise()     trim + upper-case, once, for every scale
   ├── points()        lookup, or an error naming the allowed grades
   ├── has()           True/False, never raises (safe on user input)
   ├── maximum / top_grade / ordered_grades()
   ├── __init_subclass__   validate the table when the class is created
   │
   ├── TenPointScale   A+ 1000 ... F 0        (8 grades)
   └── FourPointScale  A 400 ... F 0          (5 grades)

 Course (frozen)       code, title, credits 1..12, grade
 Transcript            scale + {code: Course}
   ├── add()           refuses a grade the scale does not have
   ├── retake()        replaces the attempt, does not add a second course
   ├── credit_points   sum(credits * points), all integers
   ├── score           Fraction(points, credits)   <- ordering
   └── gpa()           round_half_up, then format_points

 Student               cgpa is a property: self.transcript.gpa()

 Registry              one scale, one student per roll number
   ├── add()           duplicate roll / email / phone refused
   ├── search()        every match, not query.first()
   ├── top()           (-score, roll) so the order is total
   └── audit()         5 invariants
```

Details worth knowing:

- **The scale is checked before the credits are counted.** `Transcript.add`
  calls `self.scale.points(course.grade)` first, so a refused grade leaves the
  transcript untouched rather than half-written.
- **A retake is a replacement.** `retake("cs301", "c")` looks the course up
  case-insensitively, keeps its credits and title, and swaps the grade. The
  credit count does not move; only the numerator does.
- **An empty transcript refuses to answer.** `gpa()` raises `NoCourses`; the CLI
  prints `-`. A CGPA of `0.00` would be a lie about a student nobody has graded.
- **Ordering is exact.** `score` is a `Fraction`, so two transcripts whose CGPAs
  both print `8.33` are still ordered correctly — the demo pins that case with a
  purpose-built scale.
- **The table is validated when the class is written.** `__init_subclass__`
  refuses an empty table, a non-dict, a lower-case grade, a float or bool point,
  a negative point, and a scale worth nothing — at import time, not on the first
  CGPA.
- **A class attribute is not per instance, again.** `Registry.__init__` builds
  its own dictionary; nothing is shared between two registries, which the tests
  prove by building two.
- **`audit` catches what construction cannot.** A student filed under the wrong
  key, a shared email or phone, a student with no courses and a grade from
  another scale are all reachable only by reaching past the API; the demo forces
  one to prove the check is real.

---

# 🛠 Technologies

- Python 3 standard library: `abc`, `dataclasses` (frozen), `fractions`,
  `json`, `pathlib`, `argparse`, `contextlib`, `tempfile`
- pytest 9.1.1

No ORM, no database file, no network.

---

# 📚 Concepts Covered

- Abstract base classes: template method, abstract properties, `__init_subclass__`
- Turning a *stored* number into a *derived* one, and why that is a modelling fix
- Credit-weighted means, integer hundredths, `Fraction` for exact ordering
- `round_half_up` on integers instead of `round()` on floats
- Value objects: frozen dataclasses, equality by value, hashing
- Collection protocol: `__len__`, `__iter__`, `__contains__`, `__getitem__`
- Duck-typed polymorphism: one `Transcript` class, any `GradeScale`
- Duplicate detection across three different keys
- Invariants with a negative control for each
- JSON as a document format that refuses its own stored answers

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**374 tests passed** covering `check_whole`, `round_half_up` (half up, below
half, exact, negatives, two bad denominators), `format_points`, roll numbers
(casing, trimming, six bad shapes), emails (nine refusals), phones (six
refusals), departments and years, the `GradeScale` ABC (both abstract members
named, a subclass without levels, a non-abstract property, six bad tables), the
two concrete scales (points, `has`, `in`, ordering, `maximum`, `repr`,
`scale_named`), `Course` (normalisation, seven refusals, frozen, hashing, round
trip), `Transcript` (scale setters, add/retake/remove, the collection protocol,
credits, `credit_points`, `Fraction` scores, `NoCourses`, grade counts, the file
shape in five refusals), `Student` (validation, `cgpa` as a property, the dash,
round trip, `from_dict` refusals), `Registry` (protocol, duplicates across
three keys, the scale mismatch, search, ranking and ties, `by_department`,
`mean_credits`), all five audit checks and six ways to fail them, persistence
(eight `from_dict` refusals, byte-identical re-save), the seeded file (nine
pinned facts), the legacy project (ten pinned defects), the demo, and every CLI
mode including `--course`, `--retake`, `--write`, `--json` and `--quiet`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
