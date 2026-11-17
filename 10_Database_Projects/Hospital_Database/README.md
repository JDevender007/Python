# Hospital Database

Two patients have no blood group recorded, and that one fact makes three ordinary
reports wrong in three different ways. `WHERE blood_group <> 'O+'` returns 3 patients when
the wards hold 5, because `NULL <> 'O+'` is NULL and not TRUE. A completeness report
printing `COUNT(*)` beside "with blood group" claims 6 of 6 when the true figure is 4. A
"three most common groups" report ordered by group leads with the unnamed NULL group and
drops two real ones. This project teaches that **NULL is not a value, and no predicate says
what you think it says**.

All three defective queries are kept as executable strings and run beside the corrected
versions on the same seed files.

## What this project teaches

- `!=` is not the complement of `=` when a column can be NULL
- `COUNT(*)` counts rows while `COUNT(column)` counts values, and why that matters for missing data
- `ORDER BY` sorts NULLs first in SQLite, so a `LIMIT` can spend a slot on nothing
- Writing the correct complement as `col IS NULL OR col <> ?`
- Reporting missing data explicitly instead of letting it disappear from a filter
- An anti-join (`LEFT JOIN ... WHERE b.id IS NULL`) for patients with no bills
- Integer cents parsed from decimal text, and `divide_half_up` for the average bill
- Validating nullable seed fields by name, with empty meaning NULL rather than an empty string
- Auditing counts against independently derived ones

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/patients.csv --json out.json
python src/main.py --file data/patients.csv --audit
python -m pytest tests -q
```

`--file` names the patients CSV; `doctors.csv`, `appointments.csv` and `bills.csv` are read
from the same folder. Exit code `2` means the input was refused, with `error: ...` on
stderr.

## Project structure

```
Hospital_Database/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   ├── doctors.csv         # 3 doctors
│   ├── patients.csv        # 6 patients, 2 without a blood group
│   ├── appointments.csv    # 5 appointments
│   └── bills.csv           # 5 bills, integer-cent amounts as text
├── src/
│   ├── hospital.py         # every rule, query, check and the demo
│   └── main.py             # argparse only
└── tests/
    └── test_hospital.py    # 99 tests
```

## What the demo shows

| blood group | patients |
| --- | --: |
| A+ | 1 |
| AB+ | 1 |
| B+ | 1 |
| O+ | 1 |
| (not recorded) | 2 |
| **total** | **6** |

- `<> 'O+'` returns **3**; the correct complement (`IS NULL OR <>`) returns **5**
- `COUNT(*)` claims **6** labelled rows; `COUNT(blood_group)` finds **4**
- Legacy `ORDER BY blood_group LIMIT 3` gives `(not recorded)=2, A+=1, AB+=1`, losing B+
  and O+; the corrected report returns only recorded groups
- Billing: billed `8583.33` = collected `4300.00` + pending `4283.33`, average
  `1716.67` by `divide_half_up(858333, 5)`
- Exactly one patient (Joseph Mathew) has no bills, found by an anti-join
- 15/15 audit checks pass, with negative controls that make the group counts fail on purpose

## Requirements

Python 3.10+, standard library only (`sqlite3`, `csv`, `argparse`, `re`). Tests need
pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
