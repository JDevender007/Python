<div align="center">

# 📔 Journal Manager

### The legacy file has two syntax errors and a logic bug, layered so you can only see one at a time. Peel the first and the second appears. Peel that and the third prints "No entries found" after a successful search.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![JSONL](https://img.shields.io/badge/Storage-JSON%20Lines-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The course version appended text to `journal.txt` behind a menu. It never ran, and the reasons are staged:

```text
Layer 1   verbatim          SyntaxError: invalid syntax (<legacy>, line 14)
Layer 2   align the else    SyntaxError: 'break' outside loop (<legacy>, line 23)
Layer 3   remove the break  compiles — and the search misreports every query
```

**Layer 1 — the misindented `else`.** The `for` loop sits inside a `with` at eight spaces; its `else` sits at four, aligned with the `with`. `with` has no `else`, so the file is a syntax error before any logic is considered.

**Layer 2 — `break` outside a loop.** `main_menu` ends `elif choice == 4:` with `break`, but the `if` is not inside a loop. Aligning the `else` only moves the parser on to this.

**Layer 3 — the `for`/`else` bug.** With the file finally compiling, the search still lies:

```python
for line in file:
    if search in line:
        print(line)
else:
    print('No entries found')     # prints after EVERY query
```

A `for` `else` runs when the loop finishes **without** a `break` — not when the loop found nothing. There is no `break` anywhere, so the message appears after successful searches too. The demo asserts that a one-match search returns *two* things: the match and the message.

**The replacement is a data format, not a menu.** One JSON object per line, an explicit ISO date, an integer id, normalised tags:

```json
{"body": "Cut, drilled, sanded. Two shelves fit.", "date": "2024-03-09",
 "id": 3, "tags": ["build", "workshop"], "title": "Shelf done"}
```

**JSON Lines, not one JSON array, and not free text.** A damaged line is a line number you can report (`journal.jsonl line 4: Expecting property name...`) rather than a file you have to rewrite. And a date you cannot parse is a date you cannot sort, which is why the original's free text could never be searched by date.

**Dates are validated by round trip.** `strptime("2024-3-4", "%Y-%m-%d")` succeeds — it accepts unpadded fields — so parsing alone is not a format check. The module re-renders the parsed date and compares:

```text
parse_date("2024-03-04")  ->  date(2024, 3, 4)
parse_date("2024-3-4")    ->  JournalError: not zero padded
parse_date("2024-02-31")  ->  JournalError: is not %Y-%m-%d
```

**Tags are normalised, not trusted.** `[" Build ", "build", "#workShop", ""]` becomes `("build", "workshop")`: case-folded, `#` stripped, blanks dropped, de-duplicated, sorted. A tag containing a space is refused rather than silently mangled into two tags.

**Saves are atomic.** The payload is written to a temporary file in the same directory and then `os.replace`d into position. A crash mid-write leaves the previous journal intact instead of a truncated one — which matters, because a journal is append-only in spirit.

**Everything in the demo is falsifiable.** It compiles all three layers and asserts each error message, asserts the `for`/`else` misreport on a hit *and* a miss, adds three entries with sequential ids, refuses four malformed entries and four non-ISO dates, round-trips a save byte for byte, reports a damaged line by number, refuses duplicate ids on load and on save, runs case-insensitive search plus tag and date queries, checks stats with `None` rather than invented zeros when empty, proves ids are never reused, and loads the six-entry bundled journal asserting it is sorted and its word count matches.

Standard library only, no network.

---

# ✨ Features

- `LEGACY_SOURCE`, `LEGACY_ALIGNED`, `LEGACY_RUNNABLE` — the three layers, each compilable check asserted
- `legacy_search` — the `for`/`else` misreport, reproduced on demand
- `Entry` — frozen dataclass validating id, date, title, body and tags at construction
- `parse_date` — strict `YYYY-MM-DD` via a render-and-compare round trip
- `clean_tags` — case-folded, `#`-stripped, de-duplicated, sorted
- `load` / `save` / `dumps` — JSONL with line-numbered errors and atomic replace
- `add` / `next_id` — ids never reused, dates kept in order
- `search` / `by_tag` / `between` / `tag_counts` / `stats`
- `render` / `render_entry` — a readable journal
- `data/journal.jsonl` — six dated entries, 67 words, 6 tags
- CLI: `--search`, `--tag`, `--from`/`--to`, `--stats`, `--tags`, `--add`, `--dry-run`, `--legacy`, `--json`, `--quiet`
- Exit `2` on a journal error; `--demo` always returns `0`
- 122 passing pytest tests

---

# 📂 Folder Structure

```text
Journal_Manager/
│
├── src/
│   ├── main.py      # CLI: list, search, tag, range, stats, add, legacy
│   └── journal.py   # legacy layers, Entry, JSONL storage, queries
│
├── tests/
│   └── test_journal.py
│
├── data/
│   └── journal.jsonl   # six entries, one JSON object per line
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/Journal_Manager

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: three legacy layers, then the real journal
python src/main.py --demo

# The bundled six entries
python src/main.py

# Queries
python src/main.py --search shelf
python src/main.py --tag workshop
python src/main.py --from 2024-03-05 --to 2024-03-12

# Counts
python src/main.py --stats
python src/main.py --tags

# Write an entry (dry run first, then for real)
python src/main.py --add "Varnish" --date 2024-04-02 \
    --body "Two coats, sanding between." --add-tags workshop,finish --dry-run
python src/main.py --add "Varnish" --date 2024-04-02 \
    --body "Two coats, sanding between." --add-tags workshop,finish

# The legacy layers, printed
python src/main.py --legacy
```

**Entry format** (`data/journal.jsonl`) — one JSON object per line, `#` starts a comment:

```json
{"body": "Set up the workbench and labelled the drawers.", "date": "2024-03-04", "id": 1, "tags": ["setup", "workshop"], "title": "First light"}
```

Required fields are `id`, `date` and `title`; `body` and `tags` default to empty. Unknown fields are refused, so a typo like `"titel"` fails loudly instead of being ignored.

**Exit codes:** `0` = the command ran · `2` = missing file, damaged line, duplicate id, bad date or empty search term.

---

# 🧠 How It Works

```text
journal.jsonl
   │
   ▼
load()  ──►  JSON per line  ──►  Entry.from_dict()  ──►  validate
   │                             id > 0, real date, non-blank title
   │                             tags normalised; unknown fields refused
   ▼
sort_entries()  ──►  (date, id)

search(term)      case-insensitive over title + body + tags
by_tag(tag)       exact, after normalisation
between(start,end) inclusive, start <= end enforced
tag_counts()      most used first, then alphabetical
stats()           None / 0 when empty, never an invented date
```

Details worth knowing:

- **`for`/`else` is not `if`/`else`.** It means "the loop ended without `break`". That is genuinely useful for search loops — *if* you `break` on a hit. The original had no `break`, so the `else` was unconditional.
- **`next_id` uses `max + 1`, not `len + 1`.** After deleting entry 3, `len + 1` would reuse id 3 and silently merge two different entries' history.
- **Frozen entries.** `Entry` cannot be mutated after construction, so a stored entry cannot drift between the moment it is validated and the moment it is written.
- **The save is a replace.** `tempfile.mkstemp` in the target directory, write, `os.replace`. Same filesystem, so the replace is atomic; a different filesystem would silently degrade to a copy, which is why the temp file is created next to the target.
- **`dumps` sorts keys and entries.** Two saves of the same data produce identical bytes, which the demo asserts.
- **Validation errors carry the line number.** `load` re-raises `JournalError` with `f"{path.name} line {number}: {exc}"`, so a 10,000-line journal tells you where to look.

---

# 🛠 Technologies

- Python 3 standard library: `json`, `datetime`, `dataclasses`, `os`, `tempfile`, `argparse`, `pathlib`
- pytest

No database, no ORM, no network.

---

# 📚 Concepts Covered

- `for`/`else` semantics and the search-loop bug they invite
- Indentation as syntax: a misaligned `else` is not a style issue
- `break` outside a loop as a compile-time error
- Layered defects: fixing one reveals the next
- JSON Lines versus a single JSON document
- Atomic writes with a temporary file and `os.replace`
- Strict date formats via parse-and-render round trips
- Frozen dataclasses and validation at construction
- Id allocation that never reuses a gap
- Case folding and normalisation for tags
- Line-numbered error reporting for data files
- Honest nulls in summary statistics

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**122 tests passed** covering all three legacy layers (each error message, the misindented `else`, and the `for`/`else` misreport on a hit, a miss and an empty list); date parsing for valid ISO, `date`, `datetime`, padded whitespace and six rejected shapes; tag normalisation with case, duplicates, hashes, blanks, a comma string, inner spaces and non-strings; entry validation for id, title, body, date type, word counts, matching across title/body/tags, and dict round trips with missing and unknown fields; sorting by date then id; save/load round trips, byte-identical re-saves, comment skipping, damaged lines, bad dates by line number, duplicate ids on load and save, temporary-file cleanup and directory creation; id allocation including gaps; add/search/tag/range queries with their error paths; tag counts and stats including the empty case; rendering; the bundled six-entry journal; demo determinism; and every CLI path including `--add` with and without `--dry-run`, `--legacy`, JSON output and quiet mode.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
