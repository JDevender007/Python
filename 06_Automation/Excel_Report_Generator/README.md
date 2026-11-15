<div align="center">

# 📊 Excel Report Generator

### The legacy summary was one line — `self.summary = dataframe.describe(include="all")` — and it averages **only the values that happen to be there**. A mean of 40 and a mean of 41 look comparable until you notice one was divided by 12 and the other by 3, and the only place that denominator is written down is a `count` row one line away.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def generate_summary(self, dataframe):
    self.summary = dataframe.describe(include="all")
    return self.summary

def generate_missing_report(self, dataframe):
    report = pd.DataFrame()
    report["Column"] = dataframe.columns
    report["Missing Values"] = dataframe.isna().sum().values
    report["Data Type"] = dataframe.dtypes.values
    return report
```

Three defects, none of them visible on a tidy sheet with no gaps.

**1 → `describe` hides the denominator.** `count` is computed over the values that
exist, and `mean` divides by exactly that `count`. So two columns with means of 40
and 41 are not comparable when one was divided by 12 rows and the other by 3 —
and the number that would tell you is a separate row, in a table you have to read
twice. `include="all"` makes it worse: object columns report
`count`/`unique`/`top`/`freq`, numeric columns report
`count`/`mean`/`std`/quartiles, and the result is a union with blanks wherever the
two shapes do not meet.

Here a `Stat` **cannot be printed without its `n`**:

```text
unit_price: mean 47.55 over 12 of 12 rows
shipping:   mean 3.19 over 8 of 12 rows (4 missing)
```

and a column with more than `20%` empty is flagged instead of quietly averaged.

**2 → `dtypes.values` is a positional shortcut that answers the wrong question.**
It reports the *storage* type, not the meaning: an id made of digits is `object`, a
date is text, and one bad cell in a price column casts the whole column to `object`.
This module decides a column's **kind** by looking at every value — money needs two
decimals in every row, a count needs whole numbers in every row — and refuses a
column that mixes the two shapes instead of guessing:

```text
column 'unit_price' holds 2 amount(s) with two decimals and 10 whole number(s);
decide whether it is money or a count
```

**3 → Money as a float is wrong before it is ever rounded.**

```text
0.10 + 0.20            = 0.30000000000000004
a price times a quantity: 1.15 * 3 = 3.4499999999999997
2548 cents over 8 rows = 318.5 cents exactly; round(318.5) = 318  (half to even)
divide_half_up(2548, 8) = 319 -> 3.19
```

Every amount here is an integer number of **cents**, every total is an integer sum,
revenue is `units * price_cents` (an integer times an integer, exact), and every mean
is `divide_half_up(total, n)` — two integers in, one integer out, with ties going away
from zero because that is what a person does with money.

| | legacy | here |
|---|---|---|
| a mean | `describe()` prints it beside a `count` row | printed as `mean 3.19 over 8 of 12 rows` |
| 4 of 12 rows empty | averaged silently | column flagged; `(4 missing)` on the line |
| a column mixing `12.50` and `12` | `object`, so `describe` gives `top`/`freq` | refused: decide money or a count |
| `0.10 + 0.20` | `0.30000000000000004` | `10 + 20 = 30`, printed `0.30` |
| `318.5` cents | `round()` gives 318 | `divide_half_up` gives 319 |
| revenue per region | `groupby().sum()` on floats | `units * price_cents`, exact, in cents |
| a row with no region | silently dropped by `groupby` | named: `line 8 A-1007: region is empty` |

The whole thing runs on a CSV file with a hand-written reader — no pandas, no
openpyxl, no spreadsheet — so the report is reproducible and its output can be
diffed.

Standard library only: no pandas, no openpyxl, no tkinter, no network.

---

# ✨ Features

- `parse_money` — `"12.34"` → `1234`; one decimal, three decimals, `"12"` and
  `"1,234.00"` are refused, never rounded
- `parse_count` — whole numbers only
- `money` — cents back to text, sign and trailing zero intact
- `divide_half_up` — integer half-away-from-zero, so `.5` is reproducible
- `split_fields` — a CSV splitter that honours quotes and doubled quotes
- `Table` — header rules enforced on construction; `column()` by name
- `kind_of` — money / count / text, and a refusal for a column that holds two
  shapes; blanks are skipped, an entirely empty column is refused
- `Column` — present, missing, total, `mean()`, `gap()`, `stat()`
- `Stat` — total, `n`, rows, and a `line()` that cannot omit the denominator
- `Group` / `Excluded` — revenue in cents, and every row a group could not count
  with the field that was empty
- `Report` — columns, stats, groups, exclusions, flags, `csv_lines()`
- `audit` — nine named checks, each with a negative control in the suite, and a
  guard so a broken report is a `FAIL` instead of a traceback
- CLI: `--data`, `--group`, `--csv`, `--audit`, `--json`, `--quiet`, `--demo`
- 136 passing pytest tests

---

# 📂 Folder Structure

```text
Excel_Report_Generator/
│
├── src/
│   ├── main.py      # CLI: the table, the groups, the CSV, the JSON, the audit
│   └── reportlab.py # money, the CSV reader, columns, statistics, groups
│
├── tests/
│   └── test_reportlab.py
│
├── data/
│   └── sales.csv    # 12 rows, 8 columns, and the gaps that matter
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 06_Automation/Excel_Report_Generator

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the denominator, the gap flags, the half-cent mean
python src/main.py --demo

# The column profile and the revenue by region
python src/main.py

# Grouped by something else
python src/main.py --group channel

# A report you can diff, and the JSON
python src/main.py --csv report.csv
python src/main.py --json report.json

# Every check
python src/main.py --audit

# A CSV of your own
python src/main.py --data .\my_sales.csv
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a
missing file, a malformed row, a column that mixes money and counts, or a column
that is empty in every row.

---

# ⚙️ How It Works

```text
parse_table(text)
  ├── one header, then rows of exactly that width
  ├── quotes and doubled quotes are honoured; an unclosed quote is refused
  └── every error names the line

kind_of(name, values)
  ├── every value with two decimals -> money
  ├── every value whole             -> count
  ├── both, and nothing else        -> refused: decide which
  └── anything else                 -> text

build_report(table)
  ├── every column profiled: present, missing, total, mean with its n
  ├── columns over 20% empty are flagged
  ├── groups: orders, units, revenue = sum(units * price_cents)
  └── rows a group cannot count, with the field that is empty
```

Details worth knowing:

- **The denominator travels with the number.** `Stat.line()` builds the text from
  `n` and `rows` itself, so there is no way to print a mean without it.
- **Revenue is exact because it is integer multiplication.** `units * price_cents`
  cannot drift; the same sum in floats is `3.4499999999999997`.
- **A tie is reproducible.** `divide_half_up` moves half away from zero, so
  `318.5` cents is `319` on every machine, while `round()` follows the binary value
  of the float and lands on `318`.
- **The flags are decided once and kept.** An audit compares the stored list against
  a fresh recomputation, so a decision that no longer matches its columns is caught.
- **Excluded rows are named, not dropped.** `groupby` discards a row with no key;
  this report prints its line number, its order id, and which field was empty — and
  `grouped + excluded == rows` is a check, not a hope.
- **A broken report is a `FAIL`.** Every check runs behind a guard, because a
  negative control plants a defect exactly where the check looks.

---

# 🧪 Technologies

- Python 3 standard library: `dataclasses`, `pathlib`, `json`, `argparse`,
  `contextlib`, `re`
- pytest 9.1.1

No pandas, no openpyxl, no network.

---

# 📚 Concepts Covered

- Why a mean without its denominator is not a comparable number
- `describe(include="all")` and the two shapes it unions into one frame
- Storage type versus meaning, and why `object` is not an answer
- Money as integer cents; floats that cannot represent a tenth
- Half-up rounding versus `round()`'s half-to-even, and why it must be reproducible
- Strict parsing: a price needs two decimals, and a count needs none
- Grouping that names what it drops, and accounting that adds up
- Flagging a column whose gaps make an average misleading
- Audits whose negative controls plant the defect where the check looks
- A guard that turns a structural break into a failing check instead of a traceback

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**136 tests passed** covering eight money parses and five refusals, `money()`
including a negative and a refused float, fifteen half-up divisions (ties, thirds,
negatives, zero denominators), the CSV splitter with quotes and doubled quotes, every
`Table` rule, the kind decision for all four shapes, every column profile pinned to
the bundled data, the four statistics and their printed lines, the four groups and
their two exclusions, `csv_lines()`, the three legacy constants, all nine audit checks
with a negative control each (including one that proves the audit does not raise on a
float total), the demo, and every CLI mode including three exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Explain why `count` beside `mean` is not the same as printing them together
- Decide what a column holds by looking at every value, and refuse an ambiguity
- Keep money in integer cents and round it half-up on purpose
- Show that a float sum and an integer sum disagree before any rounding happens
- Group rows in a way that names the rows it cannot use
- Report a column whose gaps make its average misleading
- Write an audit that cannot be silenced by a broken report

---

# 🚀 Future Improvements

- An `.xlsx` writer, so the report opens in a spreadsheet without pandas
- A currency symbol per column, and a mixed-currency refusal
- Weighted means, where the weight and the count have to be printed together too
- A first-difference column, to report the change between two reports
- Quartile and median columns, with the same denominator discipline

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
