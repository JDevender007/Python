<div align="center">

# 🎬 IMDb Movie Scraper

### The legacy scraper deleted the units, so `2h 15min` became **215 minutes** and `1h 47min` became **147**. Worse: the same film printed two ways — `2h 15min` and `135 min` — came out seventy minutes apart.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def clean_runtime(value):
    cleaned = re.sub(r"[^\d]", "", value)
    try:
        return int(cleaned)
    except ValueError:
        return 0
```

**1 → Deleting the units concatenates the fields.** `"2h 15min"` loses the `h` and the
`min`, and `"215"` is what is left. The units are not decoration — they are the only
thing that says what the digits mean.

**2 → Two spellings of one length became two numbers.** The same runtime is printed
`"2h 15min"` on one page and `"135 min"` on another:

```text
Long One prints '2h 15min' -> 135 minutes
Long Two prints '135 min'  -> 135 minutes
the same runtime: True
the legacy reader says 215 and 135, so it thinks they differ by 80 minutes
```

**3 → A colon is not a runtime.** `"2:15"` could be two hours fifteen or two minutes
fifteen. The legacy reader answers `215` for both readings; here the shape is refused
with the sentence that says why, instead of being guessed at.

**4 → Zero is not "unknown".** Every failure path returns `0`, so a film whose runtime
the page did not print becomes a film that runs for no time at all — and a marathon
planner then schedules it without noticing.

**5 → A series is a runtime with a count.** Twenty-four episodes of forty-seven minutes
is 1,128 minutes, and the legacy reader can only ever hold one of those two numbers:

```text
24 episodes of 47 minutes is 1,128 minutes
the legacy reader can only hold one of those two numbers: 24 or 47
```

| | legacy | here |
|---|---|---|
| `135 min` | `135` | `135` minutes |
| `2h 15min` | `215` | `135` minutes |
| `2 hours 15 minutes` | `215` | `135` minutes |
| `1h 47min` | `147` | `107` minutes |
| `2h` | `2` | `120` minutes |
| `2h 75min` | `275` | refused: a minute field is below 60 |
| `2:15` | `215` | refused: a clock form, not a runtime |
| `2h 15min 30s` | `21530` | refused: a runtime is printed in minutes |
| a runtime the page did not print | `0` | `None`, with the reason |

The demonstration is offline: one bundled page, one bundled budget, no network.
Standard library only: no `requests`, no `beautifulsoup`.

---

# ✨ Features

- `Duration` — whole minutes in **one unit**, validated, ordered, addable,
  multiplied by an episode count, and printed as `2h 15min` / `45min` / `2h`
- `parse_duration` — `135`, `135 min`, `2h 15min`, `2h15min`, `2 hours 15 minutes`,
  `2h`, `45min`, and a named refusal for the shapes that are ambiguous
- `legacy_minutes` — the legacy reader, executable, so the demo can refute it
- `Film` — title, runtime or `None`, year, and the reason a runtime is unknown
- `Series` — a per-episode runtime and a count, and `total()` as their product
- `Catalogue` — films and series apart, `known_runtimes()`, `unknown()`
- `Marathon` / `plan` — a budget in minutes, whole films in page order, and the
  films that did not fit
- an `Element` tree with class and tag lookup, so the page is read without a parser
- `audit` — nine named checks with a guard, so a broken runtime is a `FAIL`
- CLI: `--page`, `--runtime`, `--budget`, `--audit`, `--json`, `--quiet`, `--demo`
- 175 passing pytest tests

---

# 📂 Folder Structure

```text
IMDb_Movie_Scraper/
│
├── src/
│   ├── main.py       # CLI: the page, one runtime, a budget, the audit
│   └── durations.py  # runtimes, parsing, series, the marathon, the audit
│
├── tests/
│   └── test_durations.py
│
├── data/
│   └── titles.html   # four films (2h 15min, 135 min, 1h 47min, none) and a series
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 07_Web_Scraping/IMDb_Movie_Scraper

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: 2h 15min read as 135, the two spellings, the series, the marathon
python src/main.py --demo

# Read the bundled page and plan the bundled marathon
python src/main.py

# Read one runtime, in the one unit
python src/main.py --runtime "2h 15min"

# Plan a marathon with your own budget
python src/main.py --budget "2h"

# Every check
python src/main.py --audit

# The whole reading as JSON
python src/main.py --json reading.json

# Your own page
python src/main.py --page .\titles.html
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a runtime
that cannot be read, a missing file, or an audit requested for a page with no series.

---

# ⚙️ How It Works

```text
parse_duration(text)
  ├── a colon form is refused: it does not say which unit is which
  ├── seconds are refused: a runtime is printed in hours and minutes
  ├── a bare number is minutes (that is what the page prints)
  ├── hours and minutes are separate fields, ADDED not concatenated
  ├── a minute field beside an hour is below 60
  └── anything left over is refused, by name

plan(films, budget)
  ├── a film with no runtime is skipped: it cannot be known to fit
  ├── a film is taken while spent + runtime <= budget
  └── the order is the page order, so the result is reproducible
```

Details worth knowing:

- **One unit means no ambiguity.** Every runtime is stored in minutes; the printing
  splits hours and minutes by integer division, so `2h 15min` and `135 min` are the
  same `Duration` and compare equal by definition.
- **The conversion is arithmetic, not concatenation.** `2 * 60 + 15`, and the
  expression is the whole lesson.
- **The minute field has a range.** `2h 75min` is refused rather than silently read as
  195 or 275: the page writes `3h 15min`, and so should anything that prints one.
- **A colon is ambiguous, so it is not parsed.** One form (`2:15`), two readings
  (135 or 2.25 hours), and no evidence on the page to choose between them.
- **An unknown runtime is `None`, and the planner skips it.** Assuming zero schedules
  a film nobody can finish.
- **A budget never goes negative.** `remaining()` is `None` when the plan does not
  fit, because "minus fifteen minutes left" is not a thing a budget has.
- **A broken runtime is a `FAIL`.** Every audit check runs behind a guard.

---

# 🧪 Technologies

- Python 3 standard library: `re`, `dataclasses`, `html.parser`, `pathlib`, `json`,
  `argparse`, `contextlib`
- pytest 9.1.1

No `requests`, no `beautifulsoup4`, no network.

---

# 📚 Concepts Covered

- A quantity stored in one unit, converted by arithmetic
- Units as meaning: why an hours field and a minutes field cannot be concatenated
- Refusing an ambiguous form (`2:15`) instead of picking a reading
- Range rules for a field (`a minute field is below 60`)
- Unknown as distinct from zero, and the planner that must skip it
- A composite figure (episodes × per-episode) as one duration
- Budgeting in whole units, and a remainder that cannot go negative
- Audits whose negative controls plant the defect where the check looks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**175 tests passed** covering `Duration` construction, printing and refusals, every
accepted spelling, nine parse refusals, the legacy reader's concatenation, the DOM's
classes / entities / void elements, the catalogue and its notes, the series product,
the marathon's budget arithmetic and skip rules, nine audit checks with six negative
controls, the demo, and every CLI mode including four exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Store a runtime in one unit and convert with arithmetic
- Explain why `2h 15min` and `135 min` must compare equal
- Refuse a colon form rather than guess which unit is which
- Enforce a range on a field (`0 <= minutes < 60`)
- Multiply a per-episode duration by a count
- Plan a budget in whole units and report what did not fit

---

# 🚀 Future Improvements

- A duration in seconds, for a cut that is printed to the second
- A season list, so a series total is a sum of season products
- Time zones and air dates, read from the same page
- A planner that maximises minutes used instead of taking page order
- A text mode, so a pasted line reads without an HTML page

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
