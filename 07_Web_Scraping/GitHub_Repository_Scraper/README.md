<div align="center">

# ⭐ GitHub Repository Scraper

### The legacy scraper turned `2.3k` into **23 stars** and `1.2m` into **12**, by deleting every character that was not a digit. The letters are not decoration — they are the magnitude, and the decimal place is the resolution.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def clean_number(value):
    cleaned = re.sub(r"[^\d]", "", value)
    try:
        return int(cleaned)
    except ValueError:
        return 0

def to_int(value):
    number = value.rstrip("kmb")
    return int(float(number)) * 1000
```

**1 → `2.3k` is not `23`.** Deleting the `k` and the `.` leaves `"23"`. On `"1.2m"` it
leaves `"12"` — a repository with 1.2 million stars becomes a repository with twelve.

**2 → A suffix is a resolution.** `2.3k` does not mean 2,300. It means the page printed
one decimal place in thousands, so the true figure is somewhere in 2,250..2,349.
Reading it as an exact integer invents precision the page never showed — and then
reports a difference of 4 against a repository at 2,304 that the page could not have
distinguished at all:

```text
price-lab prints 2.3k, which is 2,250..2,350
counts-lab prints 2,304, which is exactly 2,304
the page could not distinguish them: indistinguishable
the legacy integer would have said 23 against 2304
```

**3 → `int()` truncates where a person rounds.** `int(float("2.9"))` is 2, so `2.9k`
becomes 2,000 — a 31% error on the number the page printed, and eight hundred and
ninety-nine stars that vanished silently.

**4 → Zero is not "unknown".** Every failure path returns `0`, so a count the page did
not print is indistinguishable from a repository with no stars at all.

| | legacy | here |
|---|---|---|
| `2.3k` | `23` | `2,300`, step 100 |
| `1.2m` | `12` | `1,200,000`, step 100,000 |
| `12k` | `12` | `12,000`, step 1,000 |
| `2.9k` | `2,000` (`int()` truncates) | `2,900`, step 100 |
| `1,234` | `1,234` | `1,234`, step 1 — exact |
| `2.34k` | `234` | refused: one decimal is what the page prints |
| `0.9k` | `9` | refused: a suffixed figure is at least one magnitude |
| a count the page did not print | `0` | `None`, with the reason |

The demonstration is offline: one bundled listing page, one bundled star history, and
no network anywhere. Standard library only: no `requests`, no `beautifulsoup`.

---

# ✨ Features

- `Count` — an amount and the **step** it was printed in, validated at construction,
  with `low()`, `high()`, `could_be()` and `exact`
- `parse_count` — `1,234` exact, `12k` a step of 1,000, `2.3k` a step of 100, `1.2m` a
  step of 100,000, and a named refusal for everything else
- `format` — prints back in the shape the page used, and every count round-trips to
  the same amount *and* the same step
- `relation` — `same` / `different` only when both figures are exact; overlapping
  intervals are `indistinguishable`; otherwise `fewer` / `more`
- `gain` / `format_gain` — a change over time as an interval, `+600 to +800`
- `Element` / `parse_html` — just enough DOM to read a row by class
- `parse_listing` — name, stars, forks, language, and a note when a count is missing
- `Repository` lines — one for the row, one for the star figure with its interval
- `History` — tick-ordered samples and the gain as an interval
- `legacy_clean_number` / `legacy_magnitude` — the two legacy functions, executable
- `audit` — nine named checks with a guard, so a broken count is a `FAIL`
- CLI: `--listing`, `--history`, `--count`, `--compare`, `--audit`, `--json`,
  `--quiet`, `--demo`
- 187 passing pytest tests

---

# 📂 Folder Structure

```text
GitHub_Repository_Scraper/
│
├── src/
│   ├── main.py    # CLI: the page, one count, a comparison, the audit
│   └── counts.py  # counts, steps, comparisons, gains, DOM, the listing
│
├── tests/
│   └── test_counts.py
│
├── data/
│   ├── repos.html  # five repositories: 2.3k, 2,304, 1.2m, none, 999
│   └── history.txt # five days of one repository's star count
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 07_Web_Scraping/GitHub_Repository_Scraper

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: 2.3k read as 2,300, the interval it stands for, the gain
python src/main.py --demo

# Read the bundled page and the bundled history
python src/main.py

# Read one count, with the interval it could stand for
python src/main.py --count "2.3k"

# Compare two displayed counts
python src/main.py --compare "2.3k" "2,304"

# Every check
python src/main.py --audit

# The whole reading as JSON
python src/main.py --json reading.json

# Your own page and log
python src/main.py --listing .\repos.html --history .\history.txt
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a count
that cannot be read, a missing file, or a line without a tab.

---

# ⚙️ How It Works

```text
parse_count(text)
  ├── one suffix at most (k, m, b), last character
  ├── with a suffix: at most one decimal -> step = magnitude / 10**decimals
  ├── a suffixed figure is at least one of its magnitude ("0.9k" is refused)
  ├── without a suffix: a whole number only, grouped in threes (1,234)
  └── grouping and a suffix never together

relation(a, b)
  ├── both exact        -> same / different
  ├── intervals overlap -> indistinguishable
  └── otherwise         -> fewer / more

gain(first, last)        # an interval, never a point when either end is an estimate
```

Details worth knowing:

- **A count is a measurement.** Every figure the page rounded to a suffix carries the
  step it was rounded to, so `2.3k` can be compared with `2,304` honestly: they may be
  the same number, and the page never said.
- **The step is what makes comparison honest.** Two displays whose intervals overlap
  are `indistinguishable` — not equal, not different. Only two fully printed figures
  can be called `same` or `different` at all.
- **`int()` truncates.** `int(float("2.9"))` is 2, which is why `2.9k` becomes 2,000.
  Rounding is a decision, and it has to be made on purpose.
- **Grouping is not a decimal point.** `1,234` is a grouped whole number; `1.234` is
  refused, because a page groups with a comma and a count has no fractional part.
- **A figure with a suffix is at least one magnitude.** `0.9k` is not a shape the page
  prints, so it is refused rather than rounded into `900`.
- **A missing count is `None` and a sentence**, not a zero, because zero is a figure
  the page can legitimately print.
- **A broken count is a `FAIL`.** Every audit check runs behind a guard, because a
  negative control plants the defect exactly where the check looks.

---

# 🧪 Technologies

- Python 3 standard library: `re`, `dataclasses`, `html.parser`, `pathlib`, `json`,
  `argparse`, `contextlib`
- pytest 9.1.1

No `requests`, no `beautifulsoup4`, no network.

---

# 📚 Concepts Covered

- A displayed figure as a measurement: amount plus the step it was rounded to
- Magnitude suffixes (`k`, `m`, `b`) and why deleting them is not parsing
- Intervals, overlap, and refusing to compare what the source could not distinguish
- `int()` truncation against rounding, and the error it hides
- Grouping separators as thousands, never decimals
- Unknown as a value distinct from zero
- Interval arithmetic for a change over time
- Audits whose negative controls plant the defect where the check looks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**187 tests passed** covering `Count` construction and refusals, every printing form
(`1,234`, `2.3k`, `12k`, `1.2m`, `3.4b`), the round trip from every text in the demo's
table, eight parse refusals, all five comparison verdicts, gain intervals and their
printing, the two legacy functions, the DOM's classes / tags / entities / void
elements, the listing and its notes, the history's ordering rules and line-numbered
errors, nine audit checks with six negative controls, the demo, and every CLI mode
including four exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Read a rounded figure as an interval rather than an exact number
- Convert a magnitude suffix instead of stripping it
- Say "the page could not tell these apart" instead of inventing a difference
- Tell `int()` truncation from rounding, and measure what it costs
- Report a gain over time as bounds, not a point
- Write a demo whose legacy defect is executable and refutable

---

# 🚀 Future Improvements

- A confidence field, so a later exact reading can tighten an earlier estimate
- Ranked comparisons, ordered by the *low* end of each interval
- A second page shape, so the row lookup is a strategy rather than a class name
- A rate of growth per day, with the same interval arithmetic
- Alignment with the search API, where the same figures arrive unrounded

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
