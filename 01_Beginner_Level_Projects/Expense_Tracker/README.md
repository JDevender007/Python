<div align="center">

# 💸 Expense Tracker

### A CSV in, three honest answers out: what each month and category cost, whether a budget was breached, and which single charge was genuinely abnormal — scored with a robust median-based z-score instead of a misleading `max()`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Database-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

The hard part of an expense tracker is not adding up a column. It is answering "was this month unusual?" without lying.

Calling `max(expenses)` the anomaly is wrong twice over: it always finds something, and it compares a grocery run against a rent payment. Calling anything above the average abnormal is worse, because a single large charge drags the average up until it stops looking large — the outlier hides itself.

This project scores every expense against the other expenses **in its own category**, using the modified z-score of Iglewicz and Hoaglin:

```text
z = 0.6745 * (x - median) / MAD        MAD = median(|x - median|)
flagged when |z| >= 3.5, and only in a category with at least 3 expenses
```

The median and MAD are used because they are *breakdown points*: a single wild value cannot move them the way it moves the mean and the standard deviation. On the bundled data that difference is the whole point:

```text
dining      median 26.15  MAD 4.40    320.00  ->  z =  45.0   flagged
shopping    median 52.50  MAD 10.75   129.99  ->  z =   4.9   flagged
groceries   median 52.83  MAD 3.03     61.10  ->  z =   1.8   normal
utilities   median 85.30  MAD 4.15     91.60  ->  z =   1.0   normal
```

Two charges are abnormal, with reasons a person can check by hand. Nothing else is.

**Budgets are per month and per category.** The report says what a category spent, what is left, and by what percentage it was used — including the negative remainder, so "over by 9.99" and "over by 244.40" are distinguishable:

```text
2024-01  dining     364.40   120.00   -244.40  OVER    303.7% used
2024-01  groceries  113.50   300.00    186.50
2024-02  shopping   129.99   120.00     -9.99  OVER
```

An unbudgeted category is reported with `budget=None` rather than a fake `0.0`, so "no limit set" can never be mistaken for "spent nothing".

**Every claim in the demo is falsifiable.** It asserts 24 rows over 4 months, a grand total of `1502.79` that equals *both* the month breakdown and the category breakdown, the exact per-month counts and top categories, exactly two over-budget pairs with exact remainders, exactly two outliers, that a category with one expense is never judged, that raising the threshold to 10 leaves only the `320.00` dinner, seven malformed rows rejected with named reasons, cent rounding, and a lossless CSV round-trip.

No database, no pandas, no network.

---

# ✨ Features

- Frozen, self-validating `Expense` record with cent rounding and a positive-amount rule
- Strict ISO `YYYY-MM-DD` dates — one format, no locale ambiguity
- Five fixed categories, so a typo like `travel` is an error instead of a new column
- CSV loading with column checks and `line N:` error messages
- CSV writing sorted by date, with amounts fixed to two decimals
- `total`, `monthly_totals`, `category_totals` — all rounded, all sorted
- `monthly_summary`: per month total, count, top category and biggest single charge
- `budget_report`: per month and category spend, limit, remainder, `over`, `used_pct`
- `over_budget`: the exact list of `(month, category)` breaches
- `modified_zscore` and `find_anomalies` with a configurable 3.5 cut-off
- Small-sample guard: fewer than three expenses in a category means no verdict
- CLI with `--month`, `--anomalies`, `--threshold`, `--budgets`, `--json`, `--quiet`
- Exit `0` on success, `2` on any bad file, row, month or budget
- `--demo` and `--quiet` (prints nothing)
- 75 passing pytest tests

---

# 📂 Folder Structure

```text
Expense_Tracker/
│
├── src/
│   ├── main.py       # CLI: summary, month, anomalies, JSON
│   └── expenses.py   # Expense, aggregates, budgets, robust z-score, demo
│
├── tests/
│   └── test_expenses.py
│
├── data/
│   ├── expenses.csv    # 24 expenses, 2024-01 .. 2024-04
│   └── budgets.json    # one monthly limit per category
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 01_Beginner_Level_Projects/Expense_Tracker

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: aggregates, budgets, outliers, 12 cross-checks
python src/main.py --demo

# Monthly summary plus the full budget table
python src/main.py

# One month only
python src/main.py --month 2024-01

# Just the outliers
python src/main.py --anomalies

# A stricter cut-off keeps only the biggest charge
python src/main.py --anomalies --threshold 10

# Machine-readable
python src/main.py --json out.json --quiet
```

**CSV format** (`data/expenses.csv`):

```csv
date,category,description,amount
2024-01-30,dining,Birthday dinner for eight,320.00
```

**Budget format** (`data/budgets.json`):

```json
{ "groceries": 300.0, "transport": 90.0, "dining": 120.0,
  "utilities": 120.0, "shopping": 120.0 }
```

**Exit codes:** `0` = the report ran · `2` = bad row, missing file, unknown category, bad month or bad budget file.

---

# 🧠 How It Works

```text
expenses.csv
     │
     ▼
load_csv()  ──►  Expense.from_row()  ──►  __post_init__
     │                                   date / category / description / amount
     ▼
 ┌───────────────────┬────────────────────┬──────────────────────┐
 │ monthly_totals    │ budget_report      │ find_anomalies       │
 │ category_totals   │ over_budget        │ (median + MAD)       │
 └───────────────────┴────────────────────┴──────────────────────┘
     │
     ▼
table / --json  {total, months, categories, budgets, over_budget}
```

Details worth knowing:

- **Amounts are rounded on construction.** `10.126` becomes `10.13` once, at the boundary, so every later sum is a sum of cents rather than a sum of binary noise.
- **`budget_report` always lists all five categories.** A category with no spending appears with `0.00` instead of vanishing, which is what makes month-to-month comparison readable.
- **`used_pct` is `None` when there is no budget**, never `0`, so the CLI can print a dash and the JSON stays honest.
- **`over` is `spent > limit`.** Exactly on budget is not over — a test pins `120.00 / 120.00` as not over.
- **The MAD fallback.** If more than half the values in a category are identical, `MAD` is `0` and the score is undefined; the code falls back to the mean absolute deviation and returns `None` if that is zero too, rather than dividing by zero.
- **Anomalies are sorted by absolute score**, so the worst charge is first regardless of direction.

---

# 🛠 Technologies

- Python 3 standard library: `csv`, `statistics`, `dataclasses`, `datetime`, `json`, `pathlib`, `argparse`, `tempfile`, `contextlib`
- pytest

No pandas, no NumPy, no database, no network.

---

# 📚 Concepts Covered

- Frozen dataclasses with validation in `__post_init__`
- Money handling: rounding at the boundary, not at display time
- Strict date parsing (one accepted format)
- Grouping and aggregation without `groupby`
- Budget reporting with three states: under, over, unbudgeted
- Robust statistics: median, MAD, modified z-score
- Breakdown points and why the mean hides outliers
- Small-sample thresholds and refusing to judge too little data
- CSV round-trips with per-line error messages
- Self-asserting demos with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**75 tests passed** covering ISO date parsing and six rejected formats, record normalisation, cent rounding, six bad amounts, three unknown categories, description limits, immutability and hashing, row round-trips, CSV loading with missing columns and `line N:` errors, round-trip identity, sorted output, every aggregate, monthly summary counts/top categories/biggest charges, budget figures including remainders and percentages, unbudgeted categories, an empty month, bad category/limit/month inputs, the modified z-score (small sample, median, far value, constant sample), anomaly detection with two thresholds, ordering by score, demo determinism, and every CLI path including JSON and `--quiet`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
