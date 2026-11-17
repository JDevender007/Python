# CRM System

A revenue report that joins deals and interactions in one `GROUP BY` is arithmetically
consistent and completely false: every deal row is repeated once per interaction on the
same customer. Add `int(value * 100)` for the cents conversion and the same report is also
a few cents wrong in the other direction. This project teaches that **a total is only as
trustworthy as the row it was built from, and money is never a float**.

The legacy query and the legacy conversion are kept in the module as executable objects,
run against the same seed files as the corrected code, and the gap is printed.

## What this project teaches

- Fan-out: two one-to-many joins in one `GROUP BY` multiply the first table's rows
- Why pre-aggregating each side before the join is the only fix that survives new rows
- Reading a query result that is *wrong but self-consistent*, and finding it with a second computation
- `int(float(text) * 100)` as truncation, and the exact values where it loses a cent
- Money as integer cents from the moment it is parsed, with no float in the path
- `divide_half_up` instead of `round()` on a money path
- Validating a seed file by name: missing files, missing columns, duplicate ids, unknown stages
- Making a report deterministic: no `date.today()`, no clock, no absolute path
- Auditing a number against an independent computation rather than against itself

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/deals.csv --json out.json
python src/main.py --file data/deals.csv --audit
python -m pytest tests -q
```

`--file` names the deals CSV; `customers.csv` and `interactions.csv` are read from the same
folder. Exit code `2` means the input was refused, with `error: ...` on stderr.

## Project structure

```
CRM_System/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   ├── customers.csv       # 3 customers
│   ├── deals.csv           # 3 deals, money as decimal text
│   └── interactions.csv    # 4 interactions
├── src/
│   ├── crm.py              # every rule, query, check and the demo
│   └── main.py             # argparse only
└── tests/
    └── test_crm.py         # 91 tests
```

`crm.py` holds `LEGACY_TOP_CUSTOMERS` (the fan-out query) and `LEGACY_TO_CENTS` (the
truncating conversion) as strings so the demo can print them and the tests can execute them
beside the corrected versions.

## What the demo shows

- 3 customers, 3 deals, 4 interactions loaded and validated from `data/`
- Per-customer totals from the fan-out query vs the pre-aggregated query:

  | customer | interactions | legacy | correct |
  | --- | --: | --: | --: |
  | Neha Gupta | 2 | 480000.20 | 240000.10 |
  | Sanjay Rao | 1 | 95000.25 | 95000.25 |
  | Fatima Khan | 1 | 42000.05 | 42000.05 |
  | **total** | 4 | **617000.50** | **377000.40** |

- The overstatement is exactly `240000.10` -- Neha's deal, counted twice
- `int(float*100)` keeps `240000.10` exact but reports `0.29`, `1.15`, `2.05` and `8.20`
  one cent low
- Won `42000.05` + open pipeline `335000.35` = `377000.40`, and the totals do not move
  when an extra interaction is logged
- 14/14 audit checks pass, every one comparing a measured number to an independent
  computation

## Requirements

Python 3.10+, standard library only (`sqlite3`, `csv`, `argparse`). Tests need
pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
