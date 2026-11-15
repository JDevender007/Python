<div align="center">

# 💾 Folder Backup Tool

### The legacy verifier was two lines — `len(source_files) == len(backup_files)` — and it **passes a corrupted backup**. Five paths beside five paths, the same sizes, the same timestamps, and one file whose bytes are not the bytes you backed up.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def create_backup(self, source, destination):
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        raise FileNotFoundError("Source folder not found.")
    backup_folder = destination / f"{source.name}_{current_timestamp()}"
    create_directory(backup_folder)
    shutil.copytree(source, backup_folder, dirs_exist_ok=True)

def verify_backup(self, source, backup):
    source_files = list(Path(source).rglob("*"))
    backup_files = list(Path(backup).rglob("*"))
    return len(source_files) == len(backup_files)
```

Three defects, none of them visible when the copy worked.

**1 → Equal counts are not equal contents.** Delete one file and add another and the
count never moves. Edit a file in place and it never moves at all. `rglob("*")` also
counts *directories*, so a backup missing a file but holding a leftover empty folder
scores equal. Verification has to compare the thing a backup exists to preserve —
every relative path, its size, and a digest of its bytes — and it has to **name** the
path that failed and say *how*:

```text
verify by path, size and digest: 5 file(s) checked, 4 identical, 1 different, 0 extra
  digest  photo.jpg       the same 9 bytes, different content
```

**2 → `current_timestamp()` can collide, and `dirs_exist_ok=True` merges.** Two
backups inside the same second land in the same folder — and `copytree` with
`dirs_exist_ok=True` does not fail on an existing one, it **merges**. A file the
source no longer has survives inside the snapshot, so the "backup" is a mix of two
different days and looks like a clean copy of the current one. Here a name is chosen
against the names already taken:

```text
docs_20240101_120000
docs_20240101_120000-2
docs_20240101_120000-3
three backups, three names, no merge: True
```

**3 → A backup is a diff, and copying everything hides a deletion.** The legacy tool
re-copied the whole tree and never compared it with the previous backup, so "what
changed since last time" could only be answered by looking. A `Plan` compares two
trees by digest and puts **every** path in exactly one of four lists:

```text
the legacy count still says True: 5 path(s) then, 5 now
1 added, 1 changed, 1 removed, 3 unchanged
added     draft.md
changed   notes.txt
removed   settings.ini
unchanged index.html
unchanged photo.jpg
unchanged report.csv
'notes.txt' kept its size and changed its text, so only a digest finds it
```

Three changes, and the legacy check still says the two folders are the same.

**4 → A stop flag cannot interrupt a sleep.** The folder also held a scheduler:

```python
while self.running:
    time.sleep(interval)
    callback()
```

`stop()` sets the flag and returns, but the thread is already inside a
60-second `sleep`, so the callback that sleep was waiting for still runs — one
backup *after* somebody asked it to stop. And an exception in `callback()` kills
the thread while `is_running()` keeps saying `True`. This module replaces the thread
with arithmetic: given a start, an interval and the moment the window closes, `due()`
says exactly which ticks happen.

```text
a stop that arrives at t=10 with an interval of 60 leaves the tick at t=60
already sleeping, so the callback still runs: True
as arithmetic, a window 0 to 10 has ticks ()
a window 0 to 180 has ticks (60, 120, 180)
```

| | legacy | here |
|---|---|---|
| a corrupted backup | `5 == 5`, so it verifies | `1 different`, named: `photo.jpg` |
| a file edited in place | invisible to count **and** to size | a `digest` difference |
| a file deleted, another added | count unchanged | `missing` **and** `extra`, both named |
| two backups in one second | one folder, merged | `-2`, `-3`, no merge |
| what changed since last time | re-copy everything | `Plan`: added / changed / removed / unchanged |
| `stop()` during a sleep | one more callback fires | `due()`: zero ticks in a window that closed |
| an exception in the callback | thread dies, `is_running()` still `True` | no thread, no flag, no state to go stale |

The whole thing runs on an in-memory tree, so the demonstration is deterministic and
never writes into the repository.

Standard library only: no `shutil`, no `threading`, no `tkinter`, no network.

---

# ✨ Features

- `digest_of` — the SHA-256 of a file's bytes, checked against the published
  vectors for `""` and `"abc"`
- `check_path` — forward slashes only, relative only, no `.`/`..`, no blank segment,
  no control character
- `File` — path, text, **and the size and digest a manifest recorded**, kept as
  fields so an audit can disagree with them
- `Entry` — one manifest line: path, size, short digest
- `Tree` — unique paths, sorted manifest, lookup by path, one line per file
- `parse_tree` — `path<TAB>text`, with `;` and `//` comments and line-numbered errors
- `verify` — path, then size, then digest, and a `kind` on every difference
  (`missing` / `size` / `digest` / `extra`)
- `Verdict` — checked, identical, mismatches, extras, `ok()`, and a printable summary
- `count_only` — the legacy check, executable, so the demo can refute it
- `plan` — added / changed / removed / unchanged, diffed by digest
- `next_name` / `name_backups` — a free name every time, compared case-insensitively
- `due` / `would_fire_early` — a schedule as arithmetic, and the legacy loop's
  too-late tick
- `Session` — the two trees, the verdict, the plan and the names, wired once
- `audit` — nine named checks with a guard, so a broken tree is a `FAIL` not a
  traceback
- CLI: `--source`, `--backup`, `--previous`, `--name`, `--taken`, `--audit`,
  `--json`, `--quiet`, `--demo`
- 147 passing pytest tests

---

# 📂 Folder Structure

```text
Folder_Backup_Tool/
│
├── src/
│   ├── main.py    # CLI: the verdict, the plan, the next free name, the audit
│   └── backup.py  # paths, files, trees, verify, plan, names, schedule
│
├── tests/
│   └── test_backup.py
│
├── data/
│   ├── tree.txt   # the folder being backed up: 5 files
│   ├── backup.txt # the "backup": 5 files, same sizes, one different byte
│   └── after.txt  # a day later: 1 edit, 1 added, 1 removed
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 06_Automation/Folder_Backup_Tool

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the count that passes a corrupt backup, the digest that does not
python src/main.py --demo

# Verify the backup, then plan the next one
python src/main.py

# Name a backup without merging into an existing one
python src/main.py --name docs --taken "docs,docs-2"

# Every check
python src/main.py --audit

# The whole session as JSON
python src/main.py --json session.json

# Your own trees
python src/main.py --source .\now.txt --backup .\then.txt --previous .\old.txt
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a
missing file, a line without a tab, a path that is not relative, or a name that is
not one folder name.

---

# ⚙️ How It Works

```text
parse_tree(text)
  ├── path<TAB>text, trimmed, comments and blank lines skipped
  ├── every path checked: relative, forward slashes, no dot segments
  └── the tree is sorted by path; a duplicate path is refused

verify(source, backup)            # path -> size -> digest, in that order
  ├── path in the source, absent from the backup -> "missing"
  ├── size disagrees                             -> "size"
  ├── size agrees, digest disagrees              -> "digest"
  └── path in the backup only                    -> "extra"

plan(source, previous)            # diff by digest
  ├── added     : in the source, not in the previous backup
  ├── removed   : in the previous backup, not in the source
  ├── changed   : in both, different digest
  └── unchanged : in both, same digest

due(start, interval, until)       # no clock, no thread
  └── start+interval, start+2*interval, ... while the tick is <= until
```

Details worth knowing:

- **The manifest is data, not a computation.** `File.size` and `File.digest` are
  fields, so verification compares recorded values against the recorded values of
  another tree — and the audit compares the record against the bytes. A tree whose
  digest was derived on demand could never disagree with its own content, so
  checking it would prove nothing.
- **The order of the three tests is the lesson.** A file missing from the backup is
  reported as `missing`, not as a `size` mismatch of `11 bytes` against `0`.
- **A same-size edit is only visible to a digest.** `alpha bravo` and `alpha BRAVO`
  are both 11 bytes; `st_size` and `st_mtime` can both agree and the content can
  still be wrong.
- **A name is a promise.** `next_name` compares case-insensitively, because Windows
  would hand you the same folder for `Docs` and `docs`.
- **A schedule is arithmetic.** `due(0, 60, 10)` is `()`, which is why the legacy
  `sleep`-first loop is wrong: it cannot know the window closed until the sleep it
  is already committed to has finished.
- **A broken tree is a `FAIL`.** Every audit check runs behind a guard, because a
  negative control plants the defect exactly where the check looks.

---

# 🧪 Technologies

- Python 3 standard library: `hashlib`, `dataclasses`, `pathlib`, `json`,
  `argparse`, `contextlib`
- pytest 9.1.1

No `shutil`, no `threading`, no network.

---

# 📚 Concepts Covered

- Why a count of paths cannot stand in for a copy of contents
- Verification by path, size and digest, and naming which one failed
- Manifests as data: recorded facts that an audit can disagree with
- Same-size edits, and the checks that cannot see them
- Atomic naming: never merge into an existing folder
- Incremental backups as a four-way diff
- Scheduling as arithmetic rather than a thread and a flag
- `stop()` that cannot interrupt a `sleep`, and a guard against it
- Audits whose negative controls plant the defect where the check looks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**147 tests passed** covering the SHA-256 vectors, ten path refusals, the stored
size and digest (including a planted wrong one, which must be *kept* so the audit
can catch it), every `Tree` rule, the parser's comments / blank lines / embedded
tabs / line-numbered errors, all four difference kinds with a real tree, the legacy
count check passing a corrupt backup **and** a swapped file, the eight `Plan`
shapes, eleven name cases, ten schedule windows, nine audit checks with a negative
control each (including one that proves the audit does not raise on a planted
digest), the demo, and every CLI mode including three exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Explain why `len(a) == len(b)` is not verification, and what is
- Compare content by digest, and report the difference by kind
- Spot an edit that kept its size and its timestamp
- Choose a name that cannot collide, and refuse to merge two backups
- Diff two trees into added / changed / removed / unchanged
- Replace a polling thread with arithmetic that a window can bound
- Write an audit whose negative controls cannot be swallowed by a broken tree

---

# 🚀 Future Improvements

- A real filesystem adapter, so the same `Tree` can be built from `pathlib`
- Chunked digests, so a multi-gigabyte file need not be read into memory
- A retention policy: keep the last N plans, prune the rest
- Restoring from a plan, with the removed files recoverable
- A calendar schedule, with working days and daylight-saving changes

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
