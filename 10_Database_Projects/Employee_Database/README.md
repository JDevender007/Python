# Employee Database

Three HR reports, one seed file, three different head counts. A `COUNT(*)` after a
`LEFT JOIN` counts the phantom row that the outer join guarantees; a filter moved from
`ON` to `WHERE` silently deletes every department with no active staff; and the mean of
department averages is not the average of the payroll. This project teaches that **an
aggregate counts rows, not people -- and the join decides which rows exist**.

The three defective queries and the defective averaging are kept as executable objects
and run beside the corrected ones on the same data.

## What this project teaches

- `COUNT(*)` vs `COUNT(e.id)` after an outer join, and why one of them means "people"
- The difference between a filter in `ON` and a filter in `WHERE` on a `LEFT JOIN`
- Why a report that gets *shorter* is not an error you will notice
- Why an average of averages needs weights, and how to show the gap
- Integer paise parsed from decimal text, with no float in any money path
- `divide_half_up` as the only rounding rule in a payroll report
- Validating a seed file by name: unknown departments, duplicate codes, bad flags, bad dates
- Reconciling totals: department sums must equal the payroll total
- Auditing an aggregate against an independently computed one

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/employees.csv --json out.json
python src/main.py --file data/employees.csv --audit
python -m pytest tests -q
```

`--file` names the employees CSV; `departments.csv` is read from the same folder. Exit
code `2` means the input was refused, with `error: ...` on stderr.

## Project structure

```
Employee_Database/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   ├── departments.csv     # 5 departments, one of them empty
│   └── employees.csv       # 8 employees, 2 marked inactive
├── src/
│   ├── payroll.py          # every rule, query, check and the demo
│   └── main.py             # argparse only
└── tests/
    └── test_payroll.py     # 88 tests
```

## What the demo shows

| department | head | total | average | COUNT(*) |
| --- | --: | --: | --: | --: |
| Engineering | 3 | 2510000.00 | 836666.67 | 3 |
| Finance | 2 | 1980000.00 | 990000.00 | 2 |
| Human Resources | 1 | 490000.00 | 490000.00 | 1 |
| Research | 0 | 0.00 | 0.00 | **1** |
| Sales | 0 | 0.00 | 0.00 | **1** |
| **total** | **6** | **4980000.00** | **830000.00** | **8** |

- `COUNT(*)` reports 8 heads for 6 active employees: the two empty departments each
  contribute one phantom row
- Moving `is_active = 1` into `WHERE` returns only 3 departments, dropping Research and
  Sales entirely
- Total payroll `4980000.00` over 6 people averages `830000.00`, while averaging the three
  non-empty department averages reports `772222.22` -- a gap of `57777.78`
- Engineering's `836666.67` is `divide_half_up(251000000, 3)`, not a float
- 13/13 audit checks pass, plus negative controls that make the head-count and average
  checks fail on purpose

## Requirements

Python 3.10+, standard library only (`sqlite3`, `csv`, `argparse`, `re`). Tests need
pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
