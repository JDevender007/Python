<div align="center">

# 🏥 Patient Entry System

### A PySpark program that needed a JVM to be run at all — reading a CSV whose header ended in a tab, so the admission date lived in a column called `""` while `AdmissionDate` held the Excel serial number `45667`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Spark](https://img.shields.io/badge/Spark-Not%20required-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The course version read one file with PySpark, ran a dozen `show()` calls, and wrote the result to a managed table:

```python
patients = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv("patient.csv")
)
patients = patients.dropDuplicates()
report = patient_table.withColumn("ReportDate", current_date())
```

The file it read:

```text
PatientID	Name	Age	Gender	Diagnosis	AdmissionDate	
1	John Smith	45	Male	Fever	45667	10-01-2025
```

Four problems survive the removal of Spark.

**1 · The header ends in a tab.** `"AdmissionDate\t"` splits into **seven** names, the last of them empty. The rows also have seven fields, so the real admission date is read under a column called `""`, and `AdmissionDate` is `45667`. The demo reads the original file and shows both.

**2 · `45667` is an Excel serial number.** With `inferSchema` the column is typed as an integer and no date parsing happens at all. `45667` is 2025-01-10 in Excel's day-number system. The seventh column holds `10-01-2025` — a second copy of the same fact, which will disagree with the first as soon as either is edited. The demo proves all 15 rows still agree today, so the duplication is latent rather than already broken.

**3 · `dropDuplicates()` drops patients, not duplicates.** Two different people who happen to share a name, age, gender and diagnosis are silently merged into one. Identity is the id, and only the id.

**4 · `current_date()` makes the report irreproducible.** The same input produces different output tomorrow, so no result can be verified.

The replacement is one strict reader, one validated record type, and queries you can pin with a test:

```text
patient_id,name,age,gender,diagnosis,admitted
1,John Smith,45,Male,Fever,2025-01-10
```

**Every date shape becomes ISO.** ISO (`2025-01-10`), day-first (`10-01-2025`), `date`, `datetime`, and Excel serials (`45667` or `"45667"`) all normalise to the same type. The day-first choice is stated explicitly, because `10-01-2025` is 10 January here and 1 October in a US system — the demo parses it both ways and shows the difference.

**Excel's fake leap day is handled honestly.** Serial 60 is 1900-02-29, which never existed. The function returns 1900-02-28 and says why; serials 59 and 61 are the adjacent real days, and the pre-1900-03-01 offset is applied so that serial 1 is 1900-01-01 rather than 1899-12-31.

**Duplicates are reported, not deleted.** A repeated id produces a `Duplicate` with its extra rows and a `conflict` flag — exact copies are harmless, conflicting ones are a data-entry problem the reader should see.

**The bundled legacy file is the original, byte for byte** (`data/legacy_patients.csv`), so the demo can prove the misreading before it fixes it. `data/patients.csv` is the same 15 patients, cleaned.

Standard library only — no Spark, no JVM, no network.

---

# ✨ Features

- `serial_to_date` — Excel serials, the fake 1900-02-29, and the pre-March-1900 offset
- `parse_date` — ISO, day-first, `date`, `datetime`, serials; five bad shapes refused
- `Patient` — frozen dataclass; positive id, non-blank name, age 0–120, known gender, non-blank diagnosis
- `validate_header` — trims, refuses an empty or repeated name (the trailing tab)
- `read_csv` — canonical header, line-numbered errors, quoted commas, comments and blank lines
- `write_csv` — atomic, LF endings, canonical header, ISO dates
- `reread_legacy` — what the original reader saw
- `find_duplicates` / `dedupe` — reported by id, with a conflict flag
- `older_than`, `by_gender`, `by_diagnosis`, `admitted_between`
- `age_summary` — mean rounded at the boundary, exact median, honest nulls
- `diagnosis_counts`, `gender_counts`, `stats`, `render_table`
- `data/patients.csv` + `data/legacy_patients.csv`
- CLI: `--older-than`, `--gender`, `--diagnosis`, `--between`, `--stats`, `--duplicates`, `--legacy`, `--write`, `--json`, `--quiet`
- Exit `2` on a `PatientError`; `--demo` always returns `0`
- 129 passing pytest tests

---

# 📂 Folder Structure

```text
Patient_Entry_System/
│
├── src/
│   ├── main.py      # CLI: queries, duplicates, legacy view, normalise
│   └── patients.py  # dates, Patient, CSV, duplicates, statistics
│
├── tests/
│   └── test_patients.py
│
├── data/
│   ├── patients.csv          # 15 clean records, ISO dates
│   └── legacy_patients.csv   # the original file, verbatim
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/Patient_Entry_System

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

No Java, no Spark, no `spark-warehouse` directory.

---

# ▶️ Run

```bash
# Offline demo: the legacy misreading, then the clean registry
python src/main.py --demo

# The bundled 15 patients
python src/main.py

# Counts and age summary
python src/main.py --stats

# Queries
python src/main.py --older-than 40
python src/main.py --gender Female
python src/main.py --diagnosis Diabetes
python src/main.py --between 2025-01-12:2025-01-16

# Duplicates, by id
python src/main.py --duplicates

# What the old reader saw
python src/main.py --legacy

# Normalise any compatible file to the canonical form
python src/main.py --file data/legacy_patients.csv --write clean.csv
```

**Record format** (`data/patients.csv`) — six columns, one header, ISO dates:

```text
patient_id,name,age,gender,diagnosis,admitted
12,Isabella Jackson,31,Female,Fever,2025-01-21
```

**Exit codes:** `0` = the command ran · `2` = missing file, wrong header, bad record (named by line), bad date, reversed range, or a malformed `--between`.

---

# 🧠 How It Works

```text
CSV
 │
 ├─ validate_header()      trims; refuses empty / repeated names
 ├─ Patient.from_row()     id > 0, name, age 0..120, gender, diagnosis
 │      └─ parse_date()    ISO | DD-MM-YYYY | date | serial  ->  date
 ▼
list[Patient]
 ├─ find_duplicates()     grouped by id, conflict flag
 ├─ dedupe()              keeps the first row per id, in file order
 └─ queries               older_than, by_gender, by_diagnosis, between
```

Details worth knowing:

- **Excel's epoch is 1899-12-30, not 1900-01-01.** The two-day gap is the fake leap day plus the day-one convention. Before serial 60 the formula needs `+1`, which is why `serial_to_date(1)` is 1900-01-01 and not 1899-12-31.
- **`strptime` is too permissive on its own.** `"2025-1-10"` parses, so the format check is a render-and-compare round trip; unpadded input is refused.
- **Day-first is a decision, not a default by accident.** `%d-%m-%Y` is tried before any numeric fallback, and the demo shows that `%m-%d-%Y` would give a different month.
- **Errors carry a line number.** `read_csv` re-raises with `patients.csv line 3: age must be an integer`, so a 10,000-row file tells you where to look.
- **`age_summary` rounds the mean, not the median.** The median is exact (25 for `[20, 30]`); the mean is rounded to two places at the boundary.
- **`stats([])` returns `None`, not `0`.** An empty registry has no first admission date, and inventing one would be a lie the type system cannot catch.

---

# 🛠 Technologies

- Python 3 standard library: `csv`, `datetime`, `decimal`, `dataclasses`, `os`, `tempfile`, `argparse`, `json`, `pathlib`
- pytest

No Spark, no pandas, no Java, no network.

---

# 📚 Concepts Covered

- Tab-separated headers and how a trailing tab creates an unnamed column
- Excel serial dates, the 1900 leap-year bug, and the 1899-12-30 epoch
- Day-first versus month-first ambiguity, stated rather than assumed
- Strict date formats via parse-and-render round trips
- Validation at construction with a frozen dataclass
- Duplicate *reporting* versus duplicate *deletion*
- Identity keys: why `dropDuplicates()` is not a dedupe by id
- Reproducible reports (`current_date()` removed)
- Line-numbered errors for data files
- Honest nulls in summary statistics

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**129 tests passed** covering Excel serials (1, 59, 60, 61, 45292, 45667, a numeric string, and seven refused shapes), date parsing (six accepted inputs, five refused shapes, booleans and non-strings), `Patient` validation for id, name, age boundaries, gender, diagnosis, date normalisation and row round trips, header validation including the trailing tab, blank names and duplicates, CSV reading (15 records, missing and empty files, wrong header, line-numbered bad ages, short rows, blank lines, comments, quoted commas), writing (canonical header, no tabs, round trip, byte-identical rewrite, directory creation, no temporary files), the legacy file's shape and its two agreeing date columns, duplicate detection (none, exact, conflicting, multiple extras, ordering), every query and its error paths, age summaries for odd, even and empty lists, statistics, rendering, demo determinism, and every CLI mode.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
