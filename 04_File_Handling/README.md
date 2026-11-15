<div align="center">

# 📂 File Handling

### Five projects that each looked like "open a file, loop over lines, print a table" — and each one turned out to be a question about *identity*. When is one file another file? Is a duplicate a path or a name? Is `backup.tar.gz` a `.gz` or a `.tar.gz`? Is "same size" the same file? Is `INFO` inside `INFORMATIONAL` an INFO entry? The rebuild keeps each defect executable, then removes the reason it was possible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Each of these five projects began as a tutorial file script. They all run on the demonstration data exactly as the video does, and every one of them answers a real question wrongly the moment the data is not the video's data — and the failure is never a typo. It is the model.

**The lesson of each project is different, on purpose.** Five variations on `for line in f` would teach nothing; five different ways a file-shaped assumption betrays its subject teach the language.

- **CSV_Student_Record_Manager** — a CSV file is a *wire format*, not a database. The legacy code rewrote the file in place, so a crash in the middle of a save left half a roster; the rebuild parses to records, validates every field, and saves through `<name>.saving` + `os.replace` so a reader never sees a partial file. Marks are integer hundredths, and the average is `round_half_up` at the display boundary only, so the total of 66,550 hundredths is exact and 83.19 comes from it rather than the other way round.
- **Duplicate_File_Finder** — a *path* is not a *file*. Eight paths hold five distinct sizes and three groups of identical bytes; the legacy report lists all eight again on a second scan, because "duplicate" and "file" were the same word. The rebuild separates identity (a SHA-256 digest) from content, models an alias with a `kept` original instead of replacing it, and reports 343 reclaimable bytes — with the legacy's 1,315 shown beside it.
- **File_Organizer** — a *name* is not a *suffix*. `backup.tar.gz` is not a gzip file called `backup.tar`, and `photo.JPG` is not a different kind of thing from `photo.jpg`. The legacy moved files one at a time with no plan, so a name collision silently overwrote a file; the rebuild builds a plan first, keeps compound extensions whole, resolves collisions with a numbered suffix in the original's spelling, and applies only what the plan printed — 12 files, 629 bytes, 7 folders, 4 renames.
- **File_Synchronization_Tool** — a *timestamp* is not a *file*, and a copy without a delete is not a mirror. The legacy hashed both sides of every pair and never removed anything, so a file deleted from the source lived in the destination forever while the tool printed "Synchronization Complete." The rebuild decides by size first (an exact test), hashes only where it can help, plans deletions as opt-in orphans, and copies through `<name>.syncing` + digest check + `os.replace`.
- **Log_File_Analyzer** — a *level* is a *field*, and an *entry* is not a *line*. The legacy counted `"INFO" in line.upper()`, so `DEBUG Informational banner` was filed under INFO, `DEBUG … errors 0` counted as an error, the only `CRITICAL` was filed under ERROR because `elif` tests ERROR first, and a four-line traceback became four entries. The rebuild parses the timestamp, then the level field, keeps continuation lines with their entry, keeps malformed lines with a reason, and closes the books: 18 entries + 6 continuations + 4 malformed = 28 non-blank lines.

**Every count is exact and every claim is checkable.** Money and marks are integer hundredths, byte totals are summed from the files on disk, and each project's `verify()`/`problems()` re-reads the data instead of restating the summary it just printed.

Standard library only: no `colorama`, no `tabulate`, no `tqdm`, no network, no API keys, no downloads.

---

# 🎯 Learning Objectives

- Tell a byte count from a file's identity, and a path from a file's content
- Use SHA-256 as an identity function, and know why the *size* is the cheap exact test
- Parse a structured text format by its fields rather than by words that appear in it
- Distinguish a record from the lines it occupies, and keep both countable
- Treat a file suffix as a hint: compound extensions, case, and names that lie
- Build a **plan** and then apply it, so a destructive run can be reviewed first
- Make deletion a permission recorded in a value, never a derivation from output
- Save atomically: write beside, verify, `os.replace`
- Keep money and marks in integer hundredths and round half-up only to display
- Write an `audit()` that returns every check, then force each one to fail
- Keep the original source as an executable constant so a defect is asserted, not described

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | CSV_Student_Record_Manager | Records, validation, atomic save, exact hundredths; 8 rows, total 66,550, average 83.19. | ✅
02 | Duplicate_File_Finder | Digest identity versus path, aliases with a `kept` original, 3 groups and 343 reclaimable bytes. | ✅
03 | File_Organizer | Compound extensions, plan/apply, collision renames in the original's spelling; 12 files in 7 folders. | ✅
04 | File_Synchronization_Tool | Size gate then digest, one-way mirror with opt-in deletes, `.syncing` + `os.replace`. | ✅
05 | Log_File_Analyzer | Timestamp and level as parsed fields, continuations and malformed lines kept; 18 + 6 + 4 = 28. | ✅

---

# 💡 Concepts Covered

- File identity: content digest versus path, name, size and `mtime`
- Why "different size" is proof and "same size" is only a question
- CSV as a wire format: parse, validate, then render
- Atomic replacement: write beside the target, verify, rename
- Plans as values: every change printed before anything is written
- Deletion as a recorded permission, not an inference
- Compound extensions and case-folded collision detection
- One-way mirroring: copy **and** delete, or it is not a mirror
- Orphan files versus deletes
- Malformed input kept, named and counted instead of silently skipped
- Conservation laws as the strongest available audit
- Whole-word search: word boundaries, escaping, and never searching the level
- Integer hundredths and `round_half_up` at the display boundary
- Legacy code as an executable constant: transcription, `compile()`, and proof

---

# 📁 Repository Structure

```text
04_File_Handling/
│
├── CSV_Student_Record_Manager/
├── Duplicate_File_Finder/
├── File_Organizer/
├── File_Synchronization_Tool/
├── Log_File_Analyzer/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library module
├── tests/            # pytest test suite
├── data/             # bundled deterministic data
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3 standard library: `pathlib`, `shutil`, `hashlib`, `csv`, `json`, `os`,
  `re`, `datetime`, `collections`, `dataclasses`, `argparse`, `tempfile`
- pytest 9.1.1

No third-party runtime dependencies, no database file, no network access.

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| CSV Student Record Manager | ✅ |
| Duplicate File Finder | ✅ |
| File Organizer | ✅ |
| File Synchronization Tool | ✅ |
| Log File Analyzer | ✅ |

**Completed:** **5 / 5 Projects** · 762 passing tests

---

# ▶️ Quick Start

```bash
cd 04_File_Handling/Log_File_Analyzer

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

Each project follows the same shape: `python src/main.py --demo` for a
self-checking offline run, `python -m pytest tests/ -q` for the suite, and
`--quiet` to silence both. Every project also exposes its subject on the command
line:

```bash
cd 04_File_Handling/CSV_Student_Record_Manager
python src/main.py                          # the roster
python src/main.py --average --report       # exact mean and the department means
python src/main.py --search Priya           # one row
copy data\students.csv %TEMP%\mine.csv
python src/main.py --file %TEMP%\mine.csv --add 421123102009:Ravi Kumar:IT:2:88.50

cd ../Duplicate_File_Finder
python src/main.py                          # groups, aliases, reclaimable bytes
python src/main.py --legacy                 # the report that lists all eight paths twice

cd ../File_Organizer
python src/main.py                          # the plan: what would move, what would be renamed
python src/main.py --verify                 # the seven plan checks
python src/main.py --apply --inbox .\inbox --out .\library

cd ../File_Synchronization_Tool
python src/main.py                  # the plan: 4 copy, 2 update, 3 skip, 3 orphan
python src/main.py --verify         # prove the destination is a mirror
python src/main.py --legacy         # the loop that never deletes

cd ../Log_File_Analyzer
python src/main.py                  # summary and the per-file level table
python src/main.py --malformed      # every line that is not an entry, with the reason
python src/main.py --legacy         # the substring chain, and the ten UNKNOWNs
```

---

# 📚 Skills Developed

- Reading a tutorial script and naming the assumption its data structure encodes
- Choosing the cheapest *exact* test before the expensive one (size before digest)
- Writing a plan object whose printed form is the whole contract of the run
- Making destructive operations opt-in and visible in the value that allows them
- Parsing by fields, and refusing a line with a *reason* rather than a count
- Building a conservation law that a single dropped line would break
- Saving a file without ever leaving a half-written one behind
- Keeping integer money and marks from parse to print
- Writing an `audit()` that returns every check, then forcing one to fail
- Building 129–197 pytest cases per project, including every error message and flag

---

# 🚀 Key Learning Outcomes

- Show that a CSV saved in place can be half a roster, then save beside and rename
- Show that a second scan re-lists every duplicate path, then model aliases
- Show that `backup.tar.gz` is not a `.gz`, then keep compound extensions whole
- Show that a copy without a delete is not a mirror, then plan the orphan
- Show that `"INFO" in line` files `Informational` under INFO, then read the field
- Show that a four-line traceback is one entry, then prove 18 + 6 + 4 = 28
- Keep every byte count in a value summed from the files on disk

---

# 🔮 Future Enhancements

- A shared `paths` toolkit: compound suffixes, case folding and safe replacement
- Streaming scans for trees too large to hold a plan in memory
- Hard-link and content-addressed storage in the duplicate finder
- Rename-history and a dry-run diff for the organizer's second run
- A two-way sync mode with conflict files instead of last-writer-wins
- `--follow` mode for a log being written
- Scheduled runs behind the same plan/apply interface

---

# 🤝 Contributions

Contributions, issues and feature requests are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this category useful, consider giving this repository a star.

</div>
