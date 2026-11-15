<div align="center">

# 📰 News Scraper

### The legacy parser's `except` branch returned `datetime.now()`. So every date it could not read — a relative phrase, a prose date, an empty cell — was reported as **published just now**, and the freshest article in the feed was the one it understood least.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return datetime.now()

def age_seconds(now, published):
    try:
        return (now - published).total_seconds()
    except TypeError:
        return 0
```

**1 → The fallback is the worst possible answer.** A page that prints `"3 hours ago"`,
`"13 Nov 2026 18:05 +02:00"`, or nothing at all is answered with `datetime.now()`. The
defect is not a crash; it is a wrong answer that looks like the freshest possible one:

```text
'3 hours ago'                legacy new  2026-11-15T09:00:00Z   3 h ago
'2026-11-15'                 legacy new  refused   names a day, not an instant
''                           legacy new  refused   the timestamp text is empty
8 of 13 read here; the legacy parser answers 'new' for every one of them
```

**2 → A naive datetime is not an instant.** `strptime` returns a datetime with no zone.
Subtract it from `datetime.now(timezone.utc)` and Python raises `TypeError`; the legacy
`except` turns that into **0 seconds**, which is "published just now" again:

```text
legacy_age(aware, naive) = 0.0 s  -- 'just now'
this lab refuses the naive reading time: True
```

**3 → A phrase is only a time relative to something.** `"3 hours ago"` is not a
timestamp; it is an offset from the moment the page was read. Computed against
`datetime.now()` inside the parser, the same page gives a different answer on every run,
and nothing about it can be tested. Here the reading time is an **argument**:

```text
'3 hours ago' measured from 2026-11-15T12:00:00Z is 2026-11-15T09:00:00Z
'3 hours ago' measured from 2026-11-16T12:00:00Z is 2026-11-16T09:00:00Z
```

**4 → Sorting by the printed text is not sorting by time.** `"13 Nov 2026"` sorts before
`"2019-03-01"` as text and after it as an instant, and `"yesterday"` sorts after every
digit. A feed ordered by string is not a feed ordered by date:

```text
by the instant: iso2      2026-11-15T11:00:00Z  (Late result)
by the text:    yesterday 'yesterday'  (Yesterday's rally)
the same article: False
```

**5 → Zero is not "unknown".** Every failure path ends at "now" or at zero, so a
timestamp the page did not print is indistinguishable from one printed a moment ago.

| printed | legacy | here |
|---|---|---|
| `2026-11-15T11:00:00Z` | `now` (wrong format) | `2026-11-15T11:00:00Z`, `1 h ago` |
| `2026-11-15T13:00:00+02:00` | `now` | the same instant as 11:00 UTC |
| `13 Nov 2026 18:05 +02:00` | `now` | `2026-11-13T16:05:00Z` |
| `3 hours ago` | `now` | measured from the supplied reading time |
| `2026-11-15 10:00:00` | `now` | refused: no zone |
| `2026-11-15` | `now` | refused: a day has no time |
| `09:30` | `now` | refused: a clock has no day |
| an empty cell | `now` | `None`, with the sentence |

The demonstration is offline: one bundled feed, one bundled reading time, and **no
clock** — nothing in the module calls `datetime.now()`. The legacy functions do, and
that is exactly what the demo refutes.

---

# ✨ Features

- `Moment` — one instant as **whole seconds since the epoch, in UTC**, validated,
  ordered, with `iso()`, `human()`, `age_seconds(now)` and `age_text(now)`
- `parse_timestamp(text, now=None)` — ISO 8601 with `Z` or an offset, prose with a
  named zone or an offset, `3 hours ago` / `2 weeks ago` / `yesterday` / `just now`,
  and a named refusal for every ambiguous shape
- `legacy_fallback` / `legacy_age` — the two legacy functions, executable, so the demo
  can refute them
- `Article` — an id, a title, the text as printed, the instant or `None`, and the
  reason when there is none
- `Feed` — a reading time, the articles, `known()`, `unknown()`, `order()` (newest
  first **by instant**), `newest()`, `lines()`
- `parse_feed` — `id<TAB>title<TAB>timestamp`, line-numbered errors, and a bad row
  kept as a note rather than aborting the page
- `reading_time` — the bundled `2026-11-15T12:00:00Z`, parsed, not hard-coded twice
- `audit` — nine named checks with a guard, and `clock` injected so a negative control
  can hand in a reader that ignores the moment it was given
- CLI: `--feed`, `--at`, `--timestamp`, `--audit`, `--json`, `--quiet`, `--demo`
- 127 passing pytest tests

---

# 📂 Folder Structure

```text
News_Scraper/
│
├── src/
│   ├── main.py       # CLI: the feed, one timestamp, a reading time, the audit
│   └── timestamps.py # instants, parsing, ages, the feed, the audit
│
├── tests/
│   └── test_timestamps.py
│
├── data/
│   └── feed.txt  # eight articles: ISO, prose, phrase, naive, empty, repeat
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 07_Web_Scraping/News_Scraper

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the legacy fallback, the two orders, the ages
python src/main.py --demo

# Read the bundled feed at the bundled reading time
python src/main.py

# Read the same feed as if it were read a day earlier
python src/main.py --at "2026-11-14T12:00:00Z"

# Read one timestamp
python src/main.py --timestamp "3 hours ago"

# Read it against your own reading time
python src/main.py --at "2026-11-15T00:00:00Z" --timestamp "3 hours ago"

# Every check
python src/main.py --audit

# The reading as JSON
python src/main.py --json reading.json

# Your own feed
python src/main.py --feed .\feed.txt
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a
timestamp that cannot be read, a reading time that cannot be read, a missing file, or a
line without three fields.

---

# ⚙️ How It Works

```text
parse_timestamp(text, now)
  ├── "just now"            -> now
  ├── "yesterday"           -> now - 1 day
  ├── "N <unit>s ago"       -> now - N * unit   (second/minute/hour/day/week)
  ├── ISO 8601 [T ]HH:MM    -> fromisoformat, and it MUST carry a zone
  ├── prose                 -> "15 Nov 2026 09:30 UTC" / "+02:00", must carry a zone
  ├── "2026-11-15"          -> refused: a day has no time
  ├── "09:30"               -> refused: a clock has no day
  └── anything else         -> refused, with the shape it looks like

Feed.order()
  ├── keep the articles with an instant
  ├── sort by epoch, descending -- never by the printed text
  └── the unknown rows are kept, and keep their reason
```

Details worth knowing:

- **An instant is one number.** `13:00+02:00` and `11:00Z` are the same `Moment`, so
  comparing them cannot raise the `TypeError` that the legacy `except` hid.
- **A zone is required, not assumed.** `2026-11-15 10:00:00` is a wall clock with no
  address. Reading it as UTC would be a guess, and the guess is wrong for every reader
  who is not in UTC.
- **A phrase needs the moment it was read.** `now` is a parameter with a default of
  `None`, and a relative phrase with no `now` is refused rather than read from the
  clock. That is what makes the demo deterministic and the tests exact.
- **A day and a clock are each half an instant.** `2026-11-15` has no time; `09:30` has
  no day. Both are refused with which half is missing.
- **The reading time is data, not the environment.** `--at` changes the ages of every
  article, and nothing else; the same feed read a day earlier is the same file.
- **The future has no age.** An instant after the reading time is refused by
  `age_seconds`, so a clock skew cannot masquerade as a very fresh article.
- **A broken row is a note, not an exception.** One unreadable timestamp does not throw
  away the rest of the page.
- **A broken instant is a `FAIL`.** Every audit check runs behind a guard, because a
  negative control plants the defect exactly where the check looks.

---

# 🧪 Technologies

- Python 3 standard library: `datetime`, `re`, `dataclasses`, `pathlib`, `json`,
  `argparse`, `contextlib`
- pytest 9.1.1

No `requests`, no `beautifulsoup4`, no network, and no `datetime.now()` in the module.

---

# 📚 Concepts Covered

- An instant as seconds since the epoch, and a zone as a way of writing it down
- Naive versus aware datetimes, and the `TypeError` that a `try/except` can hide
- "Now" as a fallback: the wrong answer that looks like the newest one
- Relative phrases as offsets from a supplied reading time
- Ambiguity refusal: a day without a time, a clock without a day, a value without a zone
- Sorting by a value rather than by its display text
- Unknown as `None`, distinct from the epoch and from zero
- Deterministic time handling, and audits with an injected reader

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**127 tests passed** covering `Moment` construction, printing, ordering and refusals,
the four age bands and their exact boundaries, every accepted timestamp shape and
fifteen refusals, the two legacy functions, the feed's ordering / newest / unknown
accessors, the bundled eight rows and their two unknowns, the line-numbered file errors,
nine audit checks with six negative controls, the demo, and every CLI mode including six
exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Store a timestamp as one number in UTC, and compare instants without a `TypeError`
- Explain why `datetime.now()` in an `except` branch is a wrong answer, not a safe one
- Resolve a relative phrase against a supplied reading time, so it can be tested
- Refuse a value that names a day without a time, or a time without a day
- Order a feed by the instant instead of the printed text
- Keep an unreadable timestamp as unknown, with the sentence that says why

---

# 🚀 Future Improvements

- Time zones by name (`Europe/Berlin`), so DST is handled rather than assumed
- A duration type shared with the runtime lab, for "age" as a quantity
- A feed merge, so two pages are one ordered stream
- `robots.txt`-style freshness rules, so an old article is flagged rather than hidden
- A calendar arithmetic mode (`next Monday`), refused here because it is not an instant

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
