# Network Monitor

A state-change log records the **moments** a service changed state. The legacy availability
report turns that log into a percentage by counting rows:

```python
uptime = round(100 * sum(1 for row in rows if row["state"] == "up") / len(rows), 1)
```

A forty-five second blip and an eight-hour outage each cost exactly one row, so the number on
the dashboard is a count of transitions wearing the word "uptime". In the bundled window the
service is up for 600 seconds and down for 9400 out of 10000 -- **6.00%** availability -- yet
three of the six transitions say `up`, and the report prints **50.0%**.

The second defect is smaller and easier to ship: the natural loop that turns transitions into
durations

```python
for current, following in zip(rows, rows[1:]):
    record(current.state, following.changed_at_s - current.changed_at_s)
```

never records the state that is **still in force when the window closes**. That quietly deletes
the final 300 seconds of downtime here, so 9700 seconds get reported instead of 10000 and the
answer moves to 6.19%. The window's end is an event.

The rebuild turns the log into half-open intervals that tile the window exactly, refuses a log
that does not start at the window's start, a log whose states do not alternate, and a
transition outside the window. Durations are integer seconds, percentages are basis points
with `divide_half_up`, and MTTR and MTBF come from the intervals rather than from row counts.

## What this project teaches

- A transition log stores events; availability is the **integral** of the state over time
- Why `up rows / rows` is not a percentage of anything a user experiences
- The last state has no successor, so a pairwise loop drops the tail
- The window's end as an event, and half-open intervals that tile it exactly
- Alternation as an invariant: two `up` rows in a row mean the log, not the service, is wrong
- Availability in basis points with an explicit half-up division, never a float
- MTTR as downtime over outages, MTBF as uptime over recoveries -- both from intervals
- Reporting the longest outage beside the mean so one 8700-second hole is not averaged away
- Refusing a log that starts mid-window instead of inventing the state before it
- Auditing every total against an independent per-transition loop

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/state_changes.csv --json out.json
python src/main.py --file data/state_changes.csv --audit
python -m pytest tests -q
```

`--file` names the state-change CSV; `window.csv` is read from the same folder. Exit code `2`
means the input was refused -- a missing column, a non-numeric time, a repeated state, a first
transition after the window start, or a transition at or beyond the window end.

## Project structure

```
Network_Monitor/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   ├── window.csv          # start_s,end_s -> 0,10000
│   └── state_changes.csv   # 6 transitions: up, down, up, down, up, down
├── src/
│   ├── monitor.py          # intervals, totals, MTTR/MTBF, checks, demo
│   └── main.py             # argparse only
└── tests/
    └── test_monitor.py     # 105 tests
```

## What the demo shows

| state | start_s | end_s | seconds | share |
| --- | --: | --: | --: | --: |
| up | 0 | 100 | 100 | 1.00% |
| down | 100 | 8800 | **8700** | 87.00% |
| up | 8800 | 9000 | 200 | 2.00% |
| down | 9000 | 9400 | 400 | 4.00% |
| up | 9400 | 9700 | 300 | 3.00% |
| down | 9700 | 10000 | **300** | 3.00% |
| **total** | | | **10000** | 100.00% |

- The ledger of time is `up 600 s` and `down 9400 s`: availability is **6.00%**
- The legacy row count sees **3 of 6** transitions as `up` and prints **50.00%** -- an
  overstatement of **44.00** percentage points, because a 100-second blip and an 8700-second
  outage weigh the same
- The pairwise loop covers **9700 s**, losing the trailing **300 s** of downtime, and reports
  **6.19%** over the span it did cover
- `MTTR 3133 s = 9400 s / 3 outages` and `MTBF 200 s = 600 s / 3 recoveries`; the longest
  outage is **8700 s**, which no mean should be allowed to hide
- 18/18 audit checks pass, with a negative control that feeds the audit the legacy pairwise
  reader and watches the tiling check fail

## Requirements

Python 3.10+, standard library only (`csv`, `pathlib`, `argparse`, `dataclasses`). Tests need
pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
