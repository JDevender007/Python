<div align="center">

# 🗂️ Bulk File Renamer

### The legacy renamer looped `for old_path, new_name in zip(files, new_names)`. Given six files and four names it renames four, returns `4`, and never mentions the other two — while `history.clear()` throws away the undo of the previous batch *before* this one has done anything.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def rename_files(self, files, new_names):
    self.history.clear()
    renamed = 0
    for old_path, new_name in zip(files, new_names):
        old_file = Path(old_path)
        new_file = old_file.with_name(new_name + old_file.suffix)
        move(str(old_file), str(new_file))
        self.history.append((str(new_file), str(old_file)))
        renamed += 1
    return renamed
```

Three defects, none of them visible on the tutorial's three files.

**1 → `zip` truncates in silence.** Six files and four names give four renames and
`4`. Nothing raises. The two untouched files look exactly like files the user chose
not to select.

**2 → A computed name can land on a file that is already there**, and `move` to an
existing path overwrites it. `with_name(new_name + suffix)` also appends the old
suffix to names that bring their own — `report.pdf` becomes `report.pdf.pdf` — and a
case-only rename (`photo.JPG` → `photo.jpg`) targets a name that already "exists" on
the case-insensitive filesystems Windows and macOS both use.

**3 → `history.clear()` empties the *previous* undo** before this batch starts, so a
failure in the middle leaves the folder half-renamed with no record of the half that
worked.

The rebuild replaces all three with one idea: **a rename is a plan, and a plan is a
value.**

```text
build_plan(folder, names)
  ├── the plan must cover every file, or it is refused with both counts
  ├── every name is checked against the rules Windows actually enforces
  ├── a name that would land on a file that is staying is numbered, not used
  └── two entries may not end up with the same name
apply(folder, plan)
  ├── the plan is re-checked against the folder as it is *now*
  └── one reversible record per rename
undo(folder, records)
  ├── the whole chain is walked before the first file moves
  └── notes.txt -> a.txt -> b.txt is undone newest first, in one pass
```

The folder is an interface, not the disk — `DiskFolder` for real work,
`MemoryFolder` for the demonstration — so the demo is deterministic and never
writes into the repository.

| | legacy | here |
|---|---|---|
| six files, four names | renames 4, says nothing | `the plan names 4 file(s) but the folder holds 6` |
| a name already in the folder | overwritten | `move.txt -> keep-1.txt`, with the reason |
| `report.pdf` from `scan.pdf` | `report.pdf.pdf` | `report.pdf` |
| `photo.JPG` → `photo.jpg` | collides with itself | one line, with a note |
| a second batch | previous undo erased | records accumulate; undo takes a count |
| a failed run | half renamed, no record | refused before the first move |

Standard library only: no `tkinter`, no `shutil`, no network.

---

# ✨ Features

- `split_name` — stem and suffix, with `backup.tar.gz` → `("backup.tar", ".gz")`
  and `.env` kept whole
- `check_name` — empty, spaces, `..`, path separators, trailing dot, over-long,
  control characters, and the reserved Windows names (`CON`, `NUL`, `COM1`…)
- `target_for` — the one rule, stated: a name with a suffix is used whole, a bare
  name takes the old suffix
- `numbered` — `report.pdf` and 2 gives `report-2.pdf`, suffix last
- `MemoryFolder` / `DiskFolder` — the same interface; the disk one does a case-only
  rename through a temporary name so it works on both kinds of filesystem
- `build_plan` — coverage, legality, collisions, and uniqueness, all before a move
- `Plan` / `Entry` / `Applied` — frozen values; `changed()`, `notes()`, `lines()`
- `apply` — re-validates, then records each rename
- `undo` — walks the whole chain in a predicted name set, then moves
- `Workbook` — plans, records and undo that accumulate instead of being cleared
- `read_folder` / `read_lines` — tab-separated contents and a name list, both with
  the failing line number
- `audit` — nine named checks, each with a negative control in the suite
- CLI: `--folder`, `--names`, `--short`, `--apply`, `--undo`, `--audit`, `--json`,
  `--quiet`, `--demo`
- 110 passing pytest tests

---

# 📂 Folder Structure

```text
Bulk_File_Renamer/
│
├── src/
│   ├── main.py      # CLI: the plan, the applied names, undo, the audit, json
│   └── renamer.py   # names, folders, plans, apply, undo, demo
│
├── tests/
│   └── test_renamer.py
│
├── data/
│   ├── folder.txt   # 6 files, name<TAB>contents
│   └── names.txt    # 6 names, in the folder's sorted order
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 06_Automation/Bulk_File_Renamer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the short list, the plan, apply, undo, the collision
python src/main.py --demo

# The plan for the bundled folder
python src/main.py

# The list that does not cover the folder
python src/main.py --short 4

# Apply it in memory, then undo the last two renames
python src/main.py --apply
python src/main.py --apply --undo 2

# Every check, and the JSON
python src/main.py --audit
python src/main.py --apply --json plan.json

# A folder and a list of your own
python src/main.py --folder .\my_folder.txt --names .\my_names.txt
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a
missing or malformed folder or name file, a plan that does not cover the folder, a
repeated target, or an undo it cannot pay for.

---

# ⚙️ How It Works

```text
read_folder()      name<TAB>contents; ';' comments; a repeated name is an error
read_lines()       one name per line; ';' and '//' comments; max 60 characters
build_plan()       coverage -> legality -> numbering -> uniqueness
apply()            re-check the folder, then move and record
undo()             predict the chain, then move newest first
```

Details worth knowing:

- **A file that keeps its name does not free it.** The numbering pass only treats a
  name as available when the file holding it is actually leaving, which is what
  makes `keep.txt` (staying) and `move.txt` (moving to `keep.txt`) collide and
  resolve instead of overwriting.
- **Uniqueness is checked on the resolved names**, not on the requested ones,
  because numbering is a resolution and a repeat is a mistake.
- **`undo` predicts before it moves.** It walks the records newest first through a
  set of folded names, so a chain of renames is undone in one pass and a missing
  file refuses the whole undo instead of half of it.
- **Names are folded with `casefold`,** so the plan agrees with the filesystem about
  `Photo.JPG`, and a case-only rename is recognised as one line rather than a
  collision with itself.
- **The demo never writes to the repository**: it runs on `MemoryFolder`, so two
  runs print the same bytes.

---

# 🧪 Technologies

- Python 3 standard library: `dataclasses`, `pathlib`, `json`, `argparse`,
  `contextlib`
- pytest 9.1.1

No `tkinter`, no `shutil`, no network.

---

# 📚 Concepts Covered

- A batch operation as a plan: validate the whole thing, then apply it
- Silent truncation: `zip` and every other pairing that stops at the shorter side
- Name collisions, numbered alternatives, and why numbering keeps the suffix last
- Case-insensitive filesystems: `casefold`, and the case-only rename
- Names that are legal on one platform and not the other
- Reversible records versus a cleared history
- Undoing a chain of dependent renames in one pass
- Interfaces over the filesystem, so logic can be tested and demonstrated offline
- Audits whose negative controls plant the defect where the check looks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**110 tests passed** covering name splitting and every refusal, `target_for` and
`numbered`, both folder implementations (including a real case-only rename and a
refused overwrite on `tmp_path`), plan coverage and uniqueness errors, numbering of
a staying file, the case-only note, apply against a folder that moved on, undo
chains, the `Workbook` keeping three batches of records, both data readers, the
pinned bundled files, the three legacy constants, all nine audit checks with a
negative control each, the demo, and every CLI mode including four exit-2 paths.

---

# 🎯 Learning Outcomes

- Explain why a plan that covers part of a folder is not a plan
- Resolve a name collision by numbering instead of overwriting
- Keep a suffix rule that does not double a suffix
- Recognise a case-only rename as legal but special
- Undo a chain of renames newest first, predicting the whole chain first
- Test filesystem code without touching the filesystem

---

# 🚀 Future Improvements

- A `--disk DIR` mode that applies a plan to a real folder after printing it
- Undo across process restarts, from a JSON journal
- Numbering that respects a user's preferred pattern (`(1)`, `_1`, ` 1`)
- A dry-run diff of the folder listing, before and after the plan

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
