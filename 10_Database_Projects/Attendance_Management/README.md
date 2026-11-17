# Attendance Management

A check-in timestamp is stored as text, `'2024-03-31 09:10'`, and the legacy report asked for
a month with `WHERE stamp BETWEEN '2024-03-01' AND '2024-03-31'`. The comparison is
lexicographic, and `'2024-03-31 09:10'` is greater than `'2024-03-31'`, so every check-in on
the last day of the range silently disappeared -- three of the ten in the bundled month. This
project reads a stamp once into a day plus a minute of the day, compares ranges half open, and
keeps every late-arrival number in integer minutes.

## What this project teaches

- **A date is not a timestamp.** `day_of('2024-03-31 09:10')` is `'2024-03-31'`; the stamp is
  a different value, and a range that ends on a date must end on the *next* midnight:
  `[start 00:00, day_after(end) 00:00)`.
- **A string prefix is not a month.** `LIKE '2024-03%'` matches `'2024-03-01 09:15'` and
  misses `'2024-3-07 09:15'`; `substr(stamp, 1, 7) = '2024-03'` plus a strict parser refuses
  the unpadded row instead of hiding it.
- **Text order is only time order while the format is fixed.** `sorted(['2024-03-06 9:05',
  '2024-03-06 10:00'])` puts 10:00 first, because `'1' < '9'`.
- **Minutes, not floats.** A `09:15` grace and a `09:42` arrival is 27 late minutes; a mean of
  53 minutes over 2 late days is 26.5, printed as 27 by half-up division and 26 by `round()`.
- **A real calendar check.** `parse_day` and `parse_stamp` refuse `2024-02-30`, `24:00`,
  `09:60`, and every unpadded spelling, so the database column never has to trust a string.
- **A key is enforced, not assumed.** `PRAGMA foreign_keys = ON` plus a real foreign key means
  deleting a person takes their check-ins with them and no orphan can be inserted.

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/attendance_log.csv --json out.json
python src/main.py --from 2024-03-04 --to 2024-03-31
python src/main.py --audit
python -m pytest tests -q
```

Exit codes: `0` success, `1` an audit check failed, `2` a refused file, day, range or row.
`--demo` always exits 0 and ends with the two required lines; `--demo --quiet` writes nothing
to either stream.

## Project structure

```text
Attendance_Management/
│
├── src/
│   ├── attendance.py   # parsing, ranges, late minutes, database, audit, demo
│   └── main.py         # argparse front end, no business rules
│
├── tests/
│   └── test_attendance.py
│
├── data/
│   └── attendance_log.csv   # ten check-ins, three on the last day of March
│
├── README.md
├── requirements.txt
└── .gitignore
```

The demo needs no file at all: it builds the schema in `sqlite3.connect(':memory:')`, seeds
three people and ten check-ins from constants, closes the connection, and prints the same
bytes on every run. `data/attendance_log.csv` is the same ten rows as a flat export, for the
`--file` path, and a test keeps the two in step.

## What the demo shows

- The legacy `BETWEEN '2024-03-01' AND '2024-03-31'` reads **7** of the ten rows; the half-open
  range reads **10**.
- Check-ins on the last day: **3**, of which the legacy range sees **0**.
- `LIKE '2024-03%'` matches **1** of two sample stamps; parsing the month matches **0** and
  refuses `'2024-3-07 09:15'`.
- `sorted()` orders `2024-03-06 10:00` before `2024-03-06 9:05`; ordering by minute does not.
- STU001: 4 days, 2 late days, 53 late minutes, mean **27** (half-up) against **26** from
  `round()`; the whole month is **83** late minutes over **4** late days.
- `day_after('2024-03-31')` is `'2024-04-01'`, and `day_after('2024-02-29')` is `'2024-03-01'`.
- 12 checks print `PASS`, then `12/12 checks pass`, then the closing lines.

## Requirements

Python 3.10+, standard library only. Tests need pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
