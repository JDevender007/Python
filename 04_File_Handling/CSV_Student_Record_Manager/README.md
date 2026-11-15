<div align="center">

# 📄 CSV Student Record Manager

### The legacy project kept marks in a `float` column and rewrote the whole file with `open(CSV_FILE, "w")` on every operation. Reading `0.29` back out of a float and multiplying by 100 gives **28**, not 29 — and a crash halfway through `save_students` leaves the file holding a header and two rows.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old project was a dataclass, a manager and a menu:

```python
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
```

Six things follow.

**1 · `marks: float` is a type the domain does not have.** Marks are recorded to
two decimals. `int(float("0.29") * 100)` is `28`, and the mean of three rows of
`89.1` is `89.09999999999998`. This module keeps marks as an integer number of
hundredths and parses the *text*: `"89.05"` is 8905 by construction, and
`"89.005"` is refused rather than rounded.

**2 · `open(path, "w")` truncates before it writes.** A failure halfway through
the loop leaves a header and two rows. `save_atomic` writes to a temporary file
beside the destination, fsyncs it, and only then calls `os.replace`.

**3 · The duplicate check compares raw text.** `" 421123102001"` is not
`"421123102001"` to `any(s.roll_no == roll ...)`, so a padded roll becomes a
second row. Rolls are normalised before they are compared.

**4 · The header is never checked.** `csv.DictReader` raises a bare
`KeyError: 'Marks'` with no file and no line. Here the header is compared as a
tuple, and the complaint names the missing and unexpected columns.

**5 · A bad row raises a `ValueError` with no line number.** Every row error here
carries the line it came from, because a 400-row file needs a location, not a
type name.

**6 · The "report" is a copy.** `ReportGenerator.generate(students)` writes the
same five columns and the same rows to `reports/student_report.csv`. A report
worth writing aggregates: one row per department with a count, a mean and the
best student.

Standard library only: no pandas, no openpyxl, no network.

---

# ✨ Features

- `parse_marks` — text to hundredths with **no float on the way**; three decimals refused
- `format_marks` — the only place marks become text
- `round_half_up` — integer half-up, so `8900.5` becomes `8901`, not `8900`
- `normalise_roll` / `normalise_name` / `normalise_department` — twelve digits, one line, four departments
- `Student` — frozen dataclass, validated in `__post_init__`, equal by value, hashable
- `RowError` — carries `.line` and `.reason`, so a complaint names its line
- `StudentTable` — one row per roll number, `search`, `by_department`, `top`, `average_marks`
- `report` — per department: count, mean, best roll and best mark
- `save_atomic` — temp file, fsync, `os.replace`; a failure leaves the destination untouched
- `audit` — five invariants, each with a negative control in the tests
- `legacy_average` / `legacy_row` / `legacy_duplicate` / `legacy_report_text` — the defects, kept executable
- `data/students.csv` — 8 rows, 4 departments, 66,550 marks in total, whole marks written as `89`
- CLI: `--list`, `--search`, `--student`, `--sort`, `--average`, `--report`, `--add`, `--update`, `--remove`, `--audit`, `--legacy`, `--write`, `--json`, `--quiet`
- Exit `2` on a `RecordError`; `--demo` always returns `0`
- 197 passing pytest tests

---

# 📂 Folder Structure

```text
CSV_Student_Record_Manager/
│
├── src/
│   ├── main.py     # CLI: list, search, sort, add, update, remove, report
│   └── records.py  # marks as hundredths, strict CSV, atomic saves, the demo
│
├── tests/
│   └── test_records.py
│
├── data/
│   └── students.csv  # 8 rows, 66,550 marks
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 04_File_Handling/CSV_Student_Record_Manager

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# The table
python src/main.py
python src/main.py --sort marks
python src/main.py --sort name

# Look something up
python src/main.py --search cse
python src/main.py --student 421123102003

# Aggregates
python src/main.py --average
python src/main.py --report

# Change the table
python src/main.py --add 421123102009:Nadia Iqbal:CSE:1:90.5
python src/main.py --update 421123102001:marks=91.25
python src/main.py --remove 421123102008

# The five invariants
python src/main.py --audit

# What the legacy model did
python src/main.py --legacy
```

**Exit codes:** `0` = the command ran · `2` = a bad roll number, name,
department, year or mark, a duplicate, a renamed column, a bad line, a malformed
spec, or a missing file.

---

# 🧠 How It Works

```text
 parse_marks("88.25")   regex -> whole 88, fraction 25 -> 88 * 100 + 25
   ├── "89"             8900
   ├── "74.5"           7450        (padded, not multiplied by 10)
   └── "89.005"         refused     (a float cannot tell it from 89.00)

 format_marks(8825)     divmod(8825, 100) -> "88.25"

 Student (frozen)      roll 12 digits, name one line, 4 departments, 1..4,
                       marks 0..10000, all checked in __post_init__

 StudentTable
   ├── _students        roll -> Student
   ├── average_marks()  round_half_up(total, count)
   ├── report()         per department: count, mean, best
   ├── audit()          5 invariants
   └── save()           save_atomic(path, self._chunks())

 save_atomic           mkstemp -> write -> flush -> fsync -> os.replace
                       any failure: unlink the temp, leave the destination
```

Details worth knowing:

- **A whole mark is written as `89.00`, not `89`.** The loader accepts both. The
  first save normalises the file; the second is byte-identical, which is what the
  demo pins.
- **`newline=""` on both ends, and `lineterminator="\n"`.** Without both, Windows
  turns `\n` into `\r\n` on the way out and the round trip is no longer byte
  identical.
- **A BOM is tolerated on read and never written.** That is the one concession to
  Excel: `utf-8-sig` on the way in, plain `utf-8` on the way out.
- **`RowError` carries the line.** It is raised inside `Student.from_row`, so the
  loader does not have to re-derive where a row came from.
- **`update` replaces, it does not mutate.** `Student` is frozen, so a change
  builds a new value and puts it in the dictionary.
- **The audit exists because the constructor cannot see everything.** A student
  filed under the wrong key, or a mark mutated past the constructor via
  `object.__setattr__`, is only visible from the outside.

---

# 🛠 Technologies

- Python 3 standard library: `csv`, `io`, `os`, `tempfile`, `dataclasses`,
  `re`, `json`, `pathlib`, `argparse`, `contextlib`
- pytest 9.1.1

No pandas, no openpyxl, no network.

---

# 📚 Concepts Covered

- A wire format is not a store: parse strictly, write atomically
- Text-to-integer parsing without a float in the middle
- Half-up rounding on integers versus `round()` on floats
- Frozen dataclasses, validation in `__post_init__`, value equality
- Line-numbered errors: an error that names where it happened
- Atomic file replacement with a temporary file, `fsync` and `os.replace`
- Idempotent serialisation: normalise once, then byte for byte
- Tolerating a BOM on input and never emitting one
- Aggregation versus copying: what a report is for
- Invariants as a second line of defence behind the constructor

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**197 tests passed** covering `round_half_up`, `parse_marks` (eighteen shapes,
three decimals, negatives, the top of the scale), `format_marks`, `check_whole`,
`check_year`, `check_marks`, the three text normalisers, `Student` (validation,
frozen, hashing, rows, dicts, five refusals), the table (protocol, duplicates,
search, ordering, ties, aggregates, the report), all five invariants and four
ways to fail them, the file (BOM, header, line numbers, blank lines, non-UTF-8,
atomic failure, no temporary file left behind), the seeded file (nine pinned
facts), the legacy project (eight pinned defects), the demo, and every CLI mode
including `--sort`, `--update`, `--write`, `--json` and `--quiet`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
