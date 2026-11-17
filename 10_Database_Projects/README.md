<div align="center">

# 🗄️ Database Projects

### Five SQL reports that each looked like "join the tables and `SUM` a column" — and each one was really a question about *what a row is*. Is a total a sum across two joins? Is an aggregate counting rows or people? Does `<>` mean "the complement"? Does a ledger's sign live in the data or in a `CASE` branch? The rebuild keeps each mistake executable, then removes the reason it was possible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Each project loads bundled CSV seeds, validates them strictly, builds an in-memory SQLite
database, runs a report, and prints the numbers. Nothing touches the network: the seeds ship
in `data/`, every loader refuses bad input by name, and every demo asserts its own arithmetic
before it prints a conclusion.

The failure in each is never a typo. It is a **definition**: of what a total is, of what a head
count is, of what "not equal" covers, of where a sign belongs.

**The lesson of each project is different, on purpose.** Five variations on "add an index"
would teach nothing; five different ways a query can be arithmetically consistent and
completely false is the subject.

- **CRM_System** — *a total is not a sum across two joins.* Joining `deals` and `interactions`
  in one `GROUP BY` repeats every deal once per interaction, so one customer's `240000.10`
  reads as `480000.20` and the pipeline totals `617000.50` instead of `377000.40`. The
  rebuild pre-aggregates each side before the join, keeps money in integer cents parsed from
  decimal text, and shows that `int(float*100)` survives the large seeds but loses a cent on
  `0.29`, `1.15`, `2.05` and `8.20`.
- **Employee_Database** — *an aggregate counts rows, not people.* `COUNT(*)` after a `LEFT
  JOIN` counts the phantom row the outer join guarantees, so 6 active employees report as 8;
  moving `is_active = 1` from `ON` to `WHERE` silently deletes both empty departments; and
  averaging the department averages gives `772222.22` where the payroll average is
  `830000.00`. The rebuild states the filter in `ON`, counts `e.id`, and weights the average by
  head count.
- **Hospital_Database** — *NULL is not a value.* `blood_group <> 'O+'` returns 3 when 5
  patients are not `O+`, because `NULL <> 'O+'` is NULL and not TRUE; `COUNT(*)` beside "with
  blood group" claims 6 of 6 when 4 exist; and `ORDER BY blood_group LIMIT 3` leads with the
  unnamed NULL group and drops `B+` and `O+`. The rebuild writes the complement as
  `IS NULL OR <>`, counts `COUNT(column)` for completeness, and sorts NULL last.
- **Inventory_Database** — *the sign belongs in the data, not in a `CASE` branch.* A signed
  ledger needs no query-time sign; when the legacy `CASE` guards only `out`, a `-30` write-off
  falls into the `ELSE` and is read back as `+30`, so 10 lamps report as 70 and the ledger
  totals 436 units against a true 366. The same report also prices a whole category with one
  product's `unit_price` — a bare column beside an aggregate — reporting `75534.00` against
  `121534.00`.
- **Attendance_Management** — *a timestamp is not a date.* `WHERE stamp BETWEEN '2024-03-01'
  AND '2024-03-31'` on a `TEXT` column compares strings, and `'2024-03-31 09:10'` is greater
  than `'2024-03-31'`, so the last day of every range silently disappears — 3 of the 10
  check-ins in the bundled month. A `LIKE '2024-03%'` month is a string prefix that misses an
  unpadded `'2024-3-07'`, and text order only matches time order while the padding is fixed.
  The rebuild parses each stamp once into a day plus a minute of the day, compares every range
  half open, and divides the late-arrival average half up instead of letting `round()` pick.

**Every number is exact and every claim is checkable.** Money is integer cents or paise parsed
from text with no float in the path; averages divide through `divide_half_up` instead of
`round()` or `AVG()`; each project's `audit()` re-derives its own result from the loaded
records instead of restating the summary it just printed, and the readers are injectable so a
negative control can make exactly one check fail.

The libraries used are `sqlite3`, `csv`, `argparse` and `re` — the standard library, nothing
else. Nothing in any demo touches the network, reads a clock, or writes into the repository.

---

# 🎓 Learning Objectives

- Spot a fan-out: two one-to-many joins inside one `GROUP BY` multiply the first table
- Pre-aggregate each side before joining, so a new child row cannot change the parent total
- Distinguish `COUNT(*)` from `COUNT(column)` and `ON` from `WHERE` on an outer join
- Weight an average by the population it describes, and show the gap the unweighted mean hides
- Write the complement of `=` safely when the column is nullable
- Predict what `ORDER BY` does with NULL, and stop a `LIMIT` spending a slot on nothing
- Keep a ledger's sign in the row, and refuse a sign that disagrees with its label
- Recognise a bare column beside an aggregate as an arbitrary answer, not a shorthand
- Parse decimal money into integer cents, and divide with an explicit half-up rule
- Reconcile a report against its source records, and state the partition that must add up
- Write an `audit()` whose every check fails when its argument is corrupted

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | CRM_System | Pre-aggregated revenue joins, integer-cent money, pipeline partitions and a measured fan-out gap. | 91 | ✅
02 | Employee_Database | Head counts that count people, `ON` versus `WHERE`, weighted averages and payroll reconciliation. | 88 | ✅
03 | Hospital_Database | NULL semantics across `<>`, `COUNT(*)`, `ORDER BY ... LIMIT`, plus an anti-join and billing. | 99 | ✅
04 | Inventory_Database | Signed movement ledgers, sign/label validation, bare-column category pricing and stock value. | 127 | ✅
05 | Attendance_Management | Time-of-day arithmetic, overnight shifts, an explicit grace policy and day-level reconciliation. | 136 | ✅

**Total: 541 tests.**

---

# 🧠 Concepts Covered

- Inner versus outer joins, and what a `LEFT JOIN` guarantees about row counts
- Fan-out from joining two independent one-to-many tables in one `GROUP BY`
- `COUNT(*)` versus `COUNT(column)` and the phantom row of an outer join
- Filter placement: `ON` keeps the outer join, `WHERE` turns it into an inner join
- Weighted means, and why an average of averages is a different number
- Three-valued logic: `NULL = x`, `NULL <> x` and `NOT (x = y)` all evaluate to NULL
- `IS NULL`, `COALESCE`, and writing a complement that includes missing data
- SQLite's NULL ordering, and how a `LIMIT` can rank absence above evidence
- Signed ledger entries versus positive magnitudes with a query-time sign
- Bare columns beside aggregates, and `SUM(a * b)` versus `SUM(a) * b`
- Decimal money to integer cents, and half-up division without floats
- Low-stock and reorder thresholds as an inclusive comparison
- A date range over a timestamp column as a half-open interval, not a string `BETWEEN`
- Why text sorts like time only while the format is fixed, and what zero padding buys
- Audits that re-derive from source records, with a negative control per check

---

# 📁 Repository Structure

```text
10_Database_Projects/
│
├── Attendance_Management/
│   ├── src/    attendance.py, main.py
│   ├── tests/  test_attendance.py
│   └── data/   attendance_log.csv
│
├── CRM_System/
│   ├── src/    crm.py, main.py
│   ├── tests/  test_crm.py
│   └── data/   customers.csv, deals.csv, interactions.csv
│
├── Employee_Database/
│   ├── src/    payroll.py, main.py
│   ├── tests/  test_payroll.py
│   └── data/   departments.csv, employees.csv
│
├── Hospital_Database/
│   ├── src/    hospital.py, main.py
│   ├── tests/  test_hospital.py
│   └── data/   doctors.csv, patients.csv, appointments.csv, bills.csv
│
└── Inventory_Database/
    ├── src/    ledger.py, main.py
    ├── tests/  test_ledger.py
    └── data/   suppliers.csv, products.csv, movements.csv
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse
CLI, a `tests/` suite, deterministic CSV seeds in `data/`, a pinned `requirements.txt`, a
`.gitignore`, and a `README.md` that states its own defect.

The database is built **in memory** from the seeds on every run (`sqlite3.connect(":memory:")`),
so no binary `.db` file is shipped and the report is reproducible from text alone. Each library
module still carries the defective query as an executable string — `LEGACY_TOP_CUSTOMERS`,
`LEGACY_COUNT_STAR`, `LEGACY_NOT_GROUP`, `LEGACY_ON_HAND` — so the tests can run the wrong
query beside the right one on the same data.

---

# ▶️ Run any project

```bash
cd 10_Database_Projects/04_Inventory_Database

python src/main.py --demo          # offline, deterministic, exit 0
python src/main.py --file data/movements.csv --json out.json
python src/main.py --audit         # every check with PASS/FAIL
python -m pytest tests -q          # the suite
```

Every project supports `--demo`, `--quiet` with `--demo` (prints nothing on stdout or stderr),
`--audit`, `--json <path>` and `--file <csv>` naming the primary seed file; its sibling seed
files are read from the same folder. Exit code `2` means the input was refused, with
`error: ...` on stderr. Nothing opens a connection to a server and no demo writes into the
repository: JSON output goes only where you point it.

---

# ✅ Verify the whole category

```powershell
Get-ChildItem -Directory | ForEach-Object {
    Push-Location $_
    python -m compileall -q src tests
    python -m pytest tests -q
    python src\main.py --demo
    python src\main.py --demo --quiet
    Pop-Location
}
```

The gates each project must pass, and does:

1. `compileall` on `src` and `tests` exits 0
2. `pytest` passes with no skips, 88+ tests
3. `--demo` exits 0, prints `Cross-checks OK: ...` then `Demo completed successfully.` as its last two lines
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing at all
5. no non-ASCII byte in `src/`, `tests/` or the text data files

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why a report can be internally consistent and still false
- Why every one-to-many join you add to a `GROUP BY` changes the meaning of `SUM`
- Why "6 people" and "8 rows" answer different questions
- Why `<>` is not the complement of `=` in a nullable column
- Why a shorter report is not an error you will notice
- Why an average of averages needs weights to mean anything
- Why a sign is data, and a `CASE` branch that re-derives it is a second source of truth
- Why a bare column beside an aggregate is an arbitrary answer
- Why a timestamp compared as text loses the last day of every range
- Why money must never pass through a float
- How to write an audit whose every check has a negative control
- How to make a demonstration reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `load_customers`, `load_departments`, `load_patients`, `load_products`, `parse_log`
Records — `Customer`, `Deal`, `Employee`, `Patient`, `Bill`, `Product`, `Movement`
Validation — `CrmError`, `PayrollError`, `HospitalError`, `LedgerError`, `AttendanceError`
Money — `parse_cents`, `parse_money`, `format_cents`, `format_money`, `divide_half_up`
Queries — `top_customers`, `department_head_counts`, `patients_not_group`, `on_hand_ledger`
Legacy — `LEGACY_TOP_CUSTOMERS`, `LEGACY_COUNT_STAR`, `LEGACY_NOT_GROUP`, `LEGACY_ON_HAND`
Aggregation — pre-aggregated CTEs, weighted means, inclusive thresholds, anti-joins
Time — `parse_stamp`, `split_stamp`, `minutes_of`, `day_after`, `range_bounds`, `legacy_bounds`
Reporting — `measure`, `report`, `render_summary`, `--json`
Auditing — `audit`, `_guard`, injectable readers for negative controls
Testing — exact pinned numbers, validation refusals, one failing check per negative control

---

# 🚀 Future Improvements

- A shared `--batch` runner that executes all five demos and compares their output hashes
- A schema-comparison demo that proves the in-memory build is byte-equivalent to a shipped `.db`
- Window functions (`LAG`, running totals) so a ledger report can show movement-by-movement drift
- A second database dialect behind the same report layer, to show the SQL that is portable
- Property-based tests that generate random seeds and assert the invariants still hold
- A single `audit` harness for the category, so all five report in the same shape
- Migration notes from the positive-magnitude schema to the signed ledger, with a data fix-up script

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a clear message.
4. Push the branch.
5. Open a Pull Request.

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
