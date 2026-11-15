<div align="center">

# 🔍 Log File Analyzer

### The legacy project counted level *words* inside lines, so `DEBUG Informational banner` was filed under INFO, `DEBUG Validation finished, errors 0` was counted as an **error**, the only `CRITICAL` entry was filed under ERROR because `elif` tests ERROR first, and a four-line traceback counted as four entries. Its own summary then called ten lines "UNKNOWN" — eight of which were never entries at all.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old project read every line, upper-cased it, and asked which level word it contained:

```python
for line in self.logs:
    upper = line.upper()
    if "INFO" in upper:
        self.counter["INFO"] += 1
    elif "WARNING" in upper:
        self.counter["WARNING"] += 1
    elif "ERROR" in upper:
        self.counter["ERROR"] += 1
    elif "CRITICAL" in upper:
        self.counter["CRITICAL"] += 1
    else:
        self.counter["UNKNOWN"] += 1

SUPPORTED_EXTENSIONS = [".log", ".txt"]
```

Five things follow.

**1 → A level is a field, not a substring.** `DEBUG Informational banner rendered`
contains the letters `INFO` inside `INFORMATIONAL`, so a debug line lands under
INFO. `WARNING User info record missing` does the same. `DEBUG Validation
finished, errors 0` — a line reporting *zero* errors — contains `ERROR` inside
`ERRORS` and is counted as an error. The level sits in one fixed field after the
timestamp; that field is the answer, and nothing else is.

**2 → The order of the `elif` chain silently decides ties.** `CRITICAL Worker 1
shutting down, error in loop` is filed under ERROR, because `ERROR` is tested
before `CRITICAL`. The one critical entry in this corpus disappears.

**3 → There is no DEBUG branch at all.** Nothing in the chain can ever produce
`DEBUG`, so a whole level is invisible: 4 of the 18 entries here vanish from the
legacy summary, and one of them (`errors 0`) is re-counted as an error.

**4 → An entry is more than one line, and a line is not always an entry.** A
Python traceback is three lines that belong to the ERROR above them: the chain
counts two of them as `UNKNOWN` and `PermissionError: denied` as an `ERROR`. A
timestamped line with no level, or a prose file that merely ends in `.log`, is not
an entry either. This module keeps **entries** (timestamp, level, message,
continuation lines) and **malformed lines** (kept, named, counted, with a reason)
and never equates the two.

**5 → `SUPPORTED_EXTENSIONS = [".log", ".txt"]` treats a suffix as a promise.**
`notes.log` here holds two sentences and no entries. That is a fact worth
reporting, not a file to skip in silence.

| | legacy | here |
|---|---|---|
| `DEBUG Informational …` | INFO | DEBUG |
| `DEBUG … errors 0` | ERROR | DEBUG |
| `WARNING User info record …` | INFO | WARNING |
| `CRITICAL … error in loop` | ERROR | CRITICAL |
| Python traceback (3 lines) | 3 UNKNOWN/ERROR lines | 1 entry, `4 lines` |
| `notes.log` (prose) | 2 UNKNOWN entries | 2 malformed lines, 0 entries |
| a quoted timestamp+level inside a message | one more line, one more count | still 18 entries |
| levels it can report | 4 (`DEBUG` unreachable) | 5, zeros included |
| lines accounted for | 28 counted as 28 "entries" | 18 + 6 + 4 = 28 |

Standard library only: `re`, `datetime`, `csv`. No `colorama`, no `tabulate`, no
network.

---

# ✨ Features

- `split_line` — one line → `(datetime, level, message)`; the level must be one of
  the five names, in capitals, in the field right after the stamp
- `Entry` — frozen value: file, line, timestamp, level, message, continuations;
  `text`, `lines`, `mentions()`, `__str__`, `to_dict`
- `read_file` — entries, continuations and malformed lines from one file, with the
  exact reason a line was refused
- `analyze(folder)` / `check_folder` — every file in the folder, in name order
- `Analysis` — `counts`, `file_counts`, `continuations`, `nonblank`, `blobs`,
  `bad`, `span()`, `summary()`, `to_dict()`, `verify()`, `problems()`
- `search(analysis, word)` — whole-word, case-insensitive, message text only,
  never the level
- `report_rows` / `report_text` — the per-file table as rows or as CSV
- `legacy_counts` / `legacy_lines` / `legacy_classify` / `legacy_unknowns` — the
  substring chain, executable and measured; its ten `UNKNOWN`s split into eight
  lines that are not entries and two real DEBUG entries
- `data/logs/` — three files, 1,460 bytes, 28 non-blank lines, 18 entries
- CLI: `--levels`, `--malformed`, `--search`, `--legacy`, `--report`, `--json`,
  `--logs`, `--quiet`, `--demo`
- 160 passing pytest tests

---

# 📂 Folder Structure

```text
Log_File_Analyzer/
│
├── src/
│   ├── main.py      # CLI: summary, levels, malformed, search, legacy, report, json
│   └── analyzer.py  # the parser, the analysis, the audit, the demo
│
├── tests/
│   └── test_analyzer.py
│
├── data/
│   └── logs/
│       ├── application.log   787 bytes  16 lines, 11 entries
│       ├── notes.log         123 bytes   2 lines,  0 entries  ← prose, not logs
│       └── worker.log        550 bytes  11 lines,  7 entries
│
├── README.md
├── requirements.txt
└── .gitignore
```

The corpus is small on purpose and every awkward case is in it: a four-line
traceback, a `CRITICAL` that also says "error", a `DEBUG` that says
"Informational", a `DEBUG` that says "errors 0", a `WARNING` that says "info",
a message that quotes another timestamp and level, a line whose level is `---`,
a timestamped line whose "level" is `[pid`, and a `.log` file with no entries.

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 04_File_Handling/Log_File_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the corpus, the misreadings, the legacy chain, the audit
python src/main.py --demo

# The summary and the per-file level table
python src/main.py

# One view at a time
python src/main.py --levels
python src/main.py --malformed
python src/main.py --search error
python src/main.py --legacy

# Write the table
python src/main.py --report report.csv
python src/main.py --json analysis.json

# Another folder
python src/main.py --logs .\my_logs
```

**Exit codes:** `0` = the command ran · `2` = the folder is missing or is a file.
`--demo` exits `0` and prints the audit it ran, so a broken corpus is visible in
the output rather than in a silent success.

---

# ⚙️ How It Works

```text
split_line(line)
  ├── refuse: no "YYYY-MM-DD HH:MM:SS " prefix  → "does not start with a timestamp"
  ├── refuse: an impossible date or time          → "not a real date"
  └── refuse: the next token is not a level       → "'---' is not a level"

read_file(path)
  ├── line starts with a stamp and a known level → a new entry
  ├── line starts with a stamp but no level      → malformed (closes the entry)
  ├── any other line, with an entry open         → a continuation of that entry
  └── any other line, no entry open              → malformed

analyze(folder)  → files in name order → Analysis

Analysis.verify()
  ├── every entry names one of the five levels
  ├── no file's timestamps go backwards
  ├── the files are listed in name order
  ├── no line is both an entry and a malformed line
  ├── entries + continuations + malformed == the non-blank line count
  └── every malformed line has text and a reason
```

Details worth knowing:

- **The timestamp is anchored, the level is exact.** `LINE` matches
  `^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\S+)(?: (.*))?$`, then `datetime`
  validates the date and `LEVELS` validates the level. `info` in lower case is not
  a level; `[pid` is not a level; `TRACE` is not a level.
- **An embedded stamp is not a new entry.** `2026-05-11 08:00:01 INFO quoted
  "2026-05-11 07:00:00 ERROR x"` is one entry: the anchor is the *start* of the
  line, and the quoted text is inside the message. Scanning the line for a level
  anywhere would invent a nineteenth entry — and the audit would still pass.
- **A blank line does not end a traceback.** Blank lines are skipped, so a
  traceback with a blank line in the middle stays one entry. Physical line numbers
  are preserved and are the numbers a user would count.
- **A continuation is not a silent drop.** It belongs to an entry and is counted as
  a continuation, so the conservation law holds: 18 + 6 + 4 = 28 non-blank lines.
  Nothing is dropped, nothing is counted twice.
- **`counts()` is filled, not sparse.** A `Counter` that omits a zero makes "no
  critical in this file" indistinguishable from "this file was not read";
  `application.log` prints `CRITICAL 0`.
- **The audit checks are falsifiable.** The level check re-reads the entries; the
  count check re-reads the lines; the malformed check demands both text and reason.
  None of them is derived from the number it validates.
- **`legacy_counts` returns the counter the chain actually produced.** `CRITICAL`
  is *absent* rather than `0`, because no line ever reached that branch — and that
  absence is the point: the legacy report cannot show a level it cannot count.

---

# 🧪 Technologies

- Python 3 standard library: `re`, `datetime`, `pathlib`, `collections.Counter`,
  `dataclasses`, `csv`, `json`, `argparse`
- pytest 9.1.1

No `colorama`, no `tabulate`, no network.

---

# 📚 Concepts Covered

- A level as a parsed field versus a substring of the whole line
- `elif` ordering as hidden policy: ties are broken by source order, not severity
- A missing branch versus a zero count
- Entries versus physical lines: continuations and multi-line records
- Malformed input kept, named and counted instead of silently skipped
- A conservation law as the strongest available audit (sum of parts equals whole)
- Anchored patterns: why `re.match` on the line start beats `in` on the whole line
- Whole-word search: word boundaries, escaping, and never searching the level
- Suffix-based trust: `.log` says nothing about the contents
- Verification by re-reading the data, not by re-reporting a summary

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**160 tests passed** covering `split_line` (three-part split, no message, trailing
`\n` and `\r`, colons in the message, missing stamp, prose, unknown level,
bracketed token, lower-case level, impossible date, impossible time, another date
format), `Entry` (fields, unknown level, line below one, non-timestamp, `text`,
continuations in `text`, `lines`, `mentions` whole words and continuations,
`__str__`, `to_dict`, frozen), `BadLine` (reason required, dict, `__str__`),
`FileReport` (filled counts, continuations summed, dict shape), `read_file`
(missing file, directory, one entry, continuation kept, `PermissionError` not an
entry, malformed timestamped line, prose with no open entry, prose after an entry,
blank lines skipped, a blank line inside a traceback, the last entry closed, one-based
physical numbers, bytes counted, name kept, empty file, CRLF, an embedded stamp),
`check_folder`/`analyze` (missing folder, file as folder, empty folder, name order,
subfolders ignored, any suffix), `Analysis` (length, iteration, `__repr__`, filled
counts, `file_counts`, continuations, `nonblank`, `blobs`, `bad`, `span` and its
refusal, `summary`, `to_dict`), all six audit checks with a negative control each,
`search` (whole word, case-insensitive, longer words, prefixes, continuations,
never the level, empty word, non-text, regex characters escaped), the legacy chain
(counts, a line it cannot name, no DEBUG branch, `Informational`→INFO,
`errors 0`→ERROR, `CRITICAL … error`→ERROR, `WARNING … info`→INFO, case, pinned
constants, the 28 lines, the 2 real DEBUG entries among 10 UNKNOWNs, the
traceback), the two report shapes, the seeded corpus (pinned bytes, lines, entries,
continuations, malformed line numbers, level counts, per-file counts, span, the
traceback as one entry, the quoted stamp, the legacy totals, three whole-word hits),
the demo, and every CLI mode including `--quiet` printing nothing at all.

---

# 🎯 Learning Outcomes

- Parse a structured text format by its fields, not by words that appear in it
- Distinguish a record from the lines it occupies, and keep both countable
- Turn "the numbers look wrong" into a specific, named, testable defect
- Audit a summary against the input it came from
- Design search that cannot be fooled by a level name inside a message

---

# 🚀 Future Improvements

- `--since` / `--until` windows over the parsed timestamps
- Level escalation: pair an entry with the next one from the same process
- Structured formats (JSON lines) behind the same `Entry` interface
- Streaming mode for files too large to hold in memory
- A `--follow` mode for a log being written

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
