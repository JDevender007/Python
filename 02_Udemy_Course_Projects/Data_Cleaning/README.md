<div align="center">

# 🧹 Data Cleaning

### Two bugs in a five-line loop, where the first one hides the second. `i.isalpha` without parentheses made the filter a no-op; fix it and `clean + 1` crashes. This rebuild shows both, then cleans text, cells and rows properly.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Network-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The course exercise was this:

```python
scan = 'These+notes#reveal9Newton seeking-out an{underlying structure to/the\pyramid}'
clean = ''

for i in scan:
    if i.isalpha or i.isspace():
        clean = clean + i
    else:
        clean = clean + 1

print(clean)
```

It prints the input, unchanged. Both bugs are worth looking at, because the relationship between them is the interesting part.

**Bug 1 — `i.isalpha` without parentheses.** In Python, `obj.method` is a *bound method object*, and every object is truthy. So `if i.isalpha or i.isspace()` is `True` for `'a'`, for `'+'`, for `'9'`, for a space — for everything. The `else` branch is dead code and the filter keeps every character:

```text
legacy_clean('These+notes#reveal9Newton')
->  'These+notes#reveal9Newton'      punctuation intact, 23 chars in, 23 out
```

Nothing raises. The program looks like it worked.

**Bug 2 — `clean + 1`.** `str + int` is a `TypeError`. But the `else` branch never executes while bug 1 exists, so the crash is unreachable. **Bug 1 hides bug 2.**

Fix them in the order they appear and the program breaks:

```text
broken_clean('a+b')
TypeError: can only concatenate str (not "int") to str
```

That is why `broken_clean()` ships in the module: the demo calls it, asserts the `TypeError`, and so proves the second bug is real rather than something the README asserts. A test that only claimed "there is a hidden bug" would be unfalsifiable; a test that makes the interpreter say it is not.

**The replacement is a predicate and a comprehension**, because the loop's shape was never the problem — the condition was:

```text
strip_symbols(text)     keep letters, digits and whitespace
collapse_spaces(text)   runs of whitespace become one space, ends trimmed
clean_text(text)        both, case preserved
normalise(text)         clean_text then casefold, for keys and comparison
tokens(text)            the normalised words
```

**Cleaning text is not parsing values**, and the demo shows the difference. `"rate=3.5"` cleans to `"rate35"` — the decimal point is a symbol and symbols go. That is correct for prose and wrong for numbers, which is exactly why `sniff()` exists as a second, separate step:

```text
sniff("42")         ->  42            int
sniff("3.5")        ->  3.5           float
sniff("2024-01-31") ->  date(2024,1,31)
sniff("yes")        ->  True
sniff("")           ->  None
sniff("007")        ->  "007"         text, on purpose
sniff("1e5")        ->  "1e5"         text, on purpose
```

**`"007"` stays a string.** A zip code, a product code or an account number that silently became `7` is corrupted data that looks cleaned. The rule is stated in the module and asserted in the demo: a leading zero means a code, not a number.

**The table cleaner reports what it did** rather than implying it. `clean_table()` returns the rows and a report whose type counts sum to the cell count, so the arithmetic can be checked instead of trusted:

```text
rows_in 6   rows_out 5   duplicate_rows 1
cells 35 = blanks 2 + bools 4 + dates 4 + ints 8 + floats 1 + text 16
```

The counts describe the **output**, so they add up to `rows_out × columns`. Counting the dropped duplicate's cells too would make the arithmetic impossible to verify.

**Everything in the demo is falsifiable.** It asserts the legacy loop returns its input exactly, that `'+'.isalpha` is truthy, that the half-fixed loop raises `TypeError`, the exact cleaned form of the legacy scan, idempotency of `clean_text`, four non-text inputs refused, 17 cells sniffed into six types (including `"007"` staying text), dedupe preserving order and first spelling, header collisions refused, five bundled scans cleaning to five distinct non-empty lines, and a six-row CSV becoming five rows with two blanks and one duplicate accounted for — then cleans the result again and asserts nothing changes.

No pandas, no network.

---

# ✨ Features

- `legacy_clean` — the original loop, bug for bug, for comparison
- `broken_clean` — the first fix only, so the hidden `TypeError` is reproducible
- `strip_symbols` — letters, digits and whitespace only; non-ASCII letters kept
- `collapse_spaces` — runs squeezed, ends trimmed
- `clean_text` / `normalise` / `tokens` — case-preserving, case-folding, word list
- `dedupe` — order-preserving, case-insensitive for text, optional key
- `sniff` — blank, bool, int, float, ISO date, then text
- `clean_header` — lower snake case, with collisions and empty names refused
- `clean_row` / `clean_table` — every cell sniffed, exact duplicates dropped
- A typed report whose counts sum to the cell count
- `data/scan.txt` — five messy lines, including the legacy string
- `data/messy.csv` — six rows: padding, a blank note, a blank city, a duplicate, `007`, a bad date, `maybe` where a boolean belongs
- CLI: `--scans`, `--text`, `--legacy`, `--file`, `--json`, `--quiet`
- Exit `2` on unreadable input; `--demo` always returns `0`
- 129 passing pytest tests

---

# 📂 Folder Structure

```text
Data_Cleaning/
│
├── src/
│   ├── main.py       # CLI: table, scans, one string, legacy mode
│   └── cleaning.py   # the two bugs, text cleaning, sniffing, tables
│
├── tests/
│   └── test_cleaning.py
│
├── data/
│   ├── scan.txt      # five messy lines
│   └── messy.csv     # six rows with one duplicate
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/Data_Cleaning

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: both bugs, the crash, then the real cleaner
python src/main.py --demo

# Clean the bundled CSV and print the report
python src/main.py

# Clean the bundled scan lines
python src/main.py --scans

# Clean one string
python src/main.py --text "  Hello,   WORLD!  "

# Show the legacy loop and the half-fixed one side by side
python src/main.py --legacy

# Your own file, machine-readable
python src/main.py --file messy.csv --json out.json --quiet
```

**CSV format** (`data/messy.csv`) — a plain header and comma-separated rows, `#` starts a comment:

```text
id,name, city ,amount,joined,active,note
  1,  Alice ,Mumbai,42,2024-01-31,yes, first order
  5,Eve,,18,not-a-date,maybe,missing city
```

The header is cleaned like any other row, so `" city "` becomes `city`.

**What the bundled rows exercise:**

| cell | raw | cleaned | rule |
|------|-----|---------|------|
| `name` | `"  Alice "` | `"Alice"` | trimmed text |
| `city` | `""` | `None` | a blank is missing, not empty text |
| `amount` | `"42"` | `42` | integer |
| `amount` | `"3.5"` | `3.5` | float |
| `amount` | `"007"` | `"007"` | leading zero stays text |
| `joined` | `"2024-01-31"` | `date(2024,1,31)` | ISO date |
| `joined` | `"not-a-date"` | `"not-a-date"` | text, not an error |
| `active` | `"yes"` | `True` | boolean word |
| `active` | `"maybe"` | `"maybe"` | not a boolean, so text |
| row 4/5 | — | one dropped | exact duplicate after cleaning |

**Exit codes:** `0` = the command ran · `2` = unreadable input (missing file, wrong field count, empty table).

---

# 🧠 How It Works

```text
raw text
   │
   ├── strip_symbols()   keep alnum + whitespace
   ├── collapse_spaces() squeeze runs, trim ends
   └── clean_text()      both  ──►  "Hello WORLD"
                │
                └── normalise()  casefold  ──►  "hello world"  ──► tokens()

raw cell
   │
   ▼
sniff()  ──►  blank -> None
             yes/no/true/false -> bool
             digits without a leading zero -> int
             one dot -> float
             YYYY-MM-DD -> date
             anything else -> stripped text
```

Details worth knowing:

- **A truthy bound method is the whole bug.** `bool(obj.method)` is `True` regardless of what the method would return; only calling it, `obj.method()`, can be false. Linters catch this (`E712`, `B015`), which is why the original never survived review in a real project.
- **The unreachable bug is the dangerous one.** Dead code is not tested by the program running, so a bug inside it can live for years. The demo makes it reachable on purpose.
- **Text cleaning discards decimal points.** `"rate=3.5"` becomes `"rate35"`. That is why the project has two layers: `clean_text` for prose, `sniff` for values, and neither pretends to do the other's job.
- **Leading zeros are meaningful.** `"007"`, `"00"`, `"01234"` stay strings; only `"0"` and sign-prefixed numerals become integers.
- **Sniffing order matters.** Booleans are checked before integers (`"1"` is an int, `"yes"` a bool), and the date check runs before the text fallback.
- **Duplicates are compared after cleaning.** `"  Alice "` and `"Alice"` in two rows are the same row, which is the point of deduplicating a cleaned table rather than a raw one.
- **The report's arithmetic is asserted inside `clean_table`.** If a new type branch were added without updating the counters, that assertion would fire before the caller saw a wrong report.

---

# 🛠 Technologies

- Python 3 standard library: `datetime`, `argparse`, `json`, `pathlib`, `contextlib`
- pytest

No pandas, no csv module, no network access.

---

# 📚 Concepts Covered

- Bound methods and truthiness — the classic missing-parentheses bug
- Unreachable code hiding a second defect
- Type errors as evidence rather than as failure
- Predicate + comprehension instead of an accumulating loop
- Idempotent cleaning: `clean(clean(x)) == clean(x)`
- Separating text normalisation from value parsing
- Type inference with explicit, documented refusals (leading zeros, `1e5`)
- Order-preserving de-duplication
- Header normalisation and collision detection
- Reporting counts that can be checked arithmetically
- Self-asserting demos with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**129 tests passed** covering the legacy loop returning its input unchanged (punctuation, digits, empty, letters, non-text) and the proof that its `else` branch is unreachable; the half-fixed loop raising `TypeError` on punctuation, digits and the real scan while still working on letters; symbol stripping for eight punctuation shapes, whitespace preservation, non-ASCII letters and idempotency; whitespace collapsing with tabs and newlines; `clean_text`, `normalise` and `tokens` including the exact cleaned legacy string and case handling; dedupe with case, order, numbers and a key; fourteen sniff cases across int, float, bool, date, blank and text, plus six ambiguous cells that must stay text; header normalisation with collision and empty-name refusal; row sniffing; table counts, deduplication, blank counting, idempotency and three input errors; the bundled five-line scan file and six-row CSV with every cleaned cell asserted, including `"007"` and the bad date; demo determinism; and every CLI path including JSON date serialisation and exit `2`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
