<div align="center">

# 🗂 File Organizer

### The legacy project classified files with `file.suffix`, so `backup.tar.gz` became a `.gz`, missed the table entirely, and landed in **Others** next to a README with no extension. It also moved each file the moment it classified it — no plan to review, no record to undo, and a counter that turns `backup.tar.gz` into `backup.tar_1.gz`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old project walked a folder and moved as it went:

```python
def get_category(file_path: Path) -> str:
    extension = file_path.suffix.lower()
    for category, extensions in SUPPORTED_EXTENSIONS.items():
        if extension in extensions:
            return category
    return "Others"

for file in files:
    category = get_category(file)
    destination = OUTPUT_FOLDER / category
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / file.name
    counter = 1
    while target.exists():
        target = destination / f"{file.stem}_{counter}{file.suffix}"
        counter += 1
    shutil.move(file, target)
```

Four things follow.

**1 · `suffix` is only the last dot.** `Path("backup.tar.gz").suffix` is `".gz"`.
The table has no `.gz` in Archives, so a tar archive is filed under **Others**, in
the same folder as `README`, which has no extension at all. The suffix a person
means is the longest known tail: `.tar.gz` is Archives. The legacy table also
misses `.csv`, `.json` and `.md`, so it misplaces **4 of the 12** files.

**2 · Moving as you go means there is no plan.** The first four files have
already moved before the fifth raises, and nothing recorded what happened. Here
`build_plan` reads the folder and returns a `Plan` — a value. `--plan` prints it
and touches nothing; only `--apply` moves anything, and only when you name both
folders.

**3 · `while target.exists()` plans against the disk, not against the plan.**
`Images/photo.JPG` is already in the library, so `photo.JPG` wants
`Images/photo_1.JPG` — but the inbox also holds `photo_1.JPG`, whose own name is
now taken by a file that has **not moved yet**. Probe only the disk and you hand
`Images/photo_1.JPG` out twice, and the second move destroys the first. The plan
reserves each name as it hands it out, so it has 12 distinct targets for 12
files. This is the bug you create the moment you split planning from applying —
which is exactly the step that makes a plan reviewable.

**4 · `f"{file.stem}_{counter}{file.suffix}"` puts the counter inside the name.**
A collision on `backup.tar.gz` becomes `backup.tar_1.gz`. The counter belongs
before the whole suffix: `backup_1.tar.gz`.

| | legacy | here |
|---|---|---|
| `backup.tar.gz` | Others | Archives, `.tar.gz` |
| `data.csv` / `settings.json` | Others | Data |
| `notes.md` | Others | Documents |
| collision on a compound name | `backup.tar_1.gz` | `backup_1.tar.gz` |
| a name another move will take | handed out twice | reserved |
| review before moving | impossible | `--plan` |
| after a crash | half-moved folder | rollback, then `undo` |
| a subfolder | invisible | listed as skipped |

Standard library only: `pathlib`, `shutil`, `json`, no `colorama`, no network.

---

# ✨ Features

- `suffix_of` — the **longest known** suffix, case-insensitively; `archive.tar.gz` is `.tar.gz`, not `.gz`
- `classify` — a `Kind` with the folder, the suffix and whether the table knew it
- 8 folders: Images, Documents, Videos, Music, Archives, Data, Python, Others
- `unique_name` — `photo.JPG` → `photo_1.JPG`, and the counter goes **before** a compound suffix
- `FileEntry` / `Move` — frozen value objects; a move is a fact, not an action
- `Plan` — every move, `total_bytes`, `renamed`, `by_category`, `summary`, `to_dict`
- `audit` — seven checks, with a negative control for each in the tests
- `apply_plan` — one target at a time, size verified on arrival, rolled back on failure
- `undo` — puts every file back and removes the folders the apply created
- `legacy_category` / `legacy_plan` / `naive_targets` — the defects, executable and measured
- `data/inbox/` — 12 files, 629 bytes, 1 subfolder, 4 collisions; `data/organized/` — 3 files already in the library
- CLI: `--apply`, `--verify`, `--legacy`, `--categories`, `--json`, `--inbox`, `--out`, `--quiet`
- `--apply` **refuses** to move the bundled folders
- Exit `2` on a bad folder or a refused apply; `--demo` always returns `0`
- 146 passing pytest tests

---

# 📂 Folder Structure

```text
File_Organizer/
│
├── src/
│   ├── main.py       # CLI: plan, verify, legacy, categories, apply
│   └── organizer.py  # suffixes, the plan, apply, undo, the demo
│
├── tests/
│   └── test_organizer.py
│
├── data/
│   ├── inbox/                 # 12 loose files, 629 bytes, plus later/
│   │   ├── photo.JPG  photo_1.JPG  report.final.pdf  notes.txt
│   │   ├── notes.md   data.csv     settings.json     script.PY
│   │   ├── backup.tar.gz  archive.7z  track.mp3  README
│   │   └── later/old.txt      # a subfolder: reported, never moved
│   └── organized/             # the library, already holding three names
│       ├── Images/photo.JPG
│       ├── Documents/notes.txt
│       └── Archives/backup.tar.gz
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 04_File_Handling/File_Organizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# The plan: what would happen, and nothing else
python src/main.py
python src/main.py --verify

# Why each name is what it is
python src/main.py --legacy
python src/main.py --categories

# Write the plan
python src/main.py --json plan.json

# Do it: both folders must be named explicitly
python src/main.py --apply --inbox .\downloads --out .\library

# Your own folders, plan only
python src/main.py --inbox .\downloads --out .\library
```

**Exit codes:** `0` = the command ran · `1` = a plan check failed ·
`2` = a bad folder, a bad name, or a refused `--apply`.

---

# 🧠 How It Works

```text
classify("backup.tar.gz")
  ├── suffixes sorted longest first: .tar.bz2 .tar.zst .tar.gz ...
  ├── "backup.tar.gz".casefold().endswith(".tar.gz") -> ".tar.gz"
  └── Archives  (Path("backup.tar.gz").suffix is ".gz" -- too short)

build_plan(inbox, out)
  ├── entries:  every file, sorted by name
  ├── folders:  every subfolder, reported and skipped
  ├── reserved: existing names per folder, case-folded
  └── for each entry, in folder order then name order:
        name, renamed = unique_name(name, suffix, reserved[folder])
        reserved[folder].add(name.casefold())      <- the reservation
        moves.append(Move(source, out/folder/name, ...))

apply_plan(plan)     re-check source, re-check target, mkdir, move, verify size
                     any failure -> undo what has moved, then raise
undo(applied)        move back newest first, remove folders left empty
```

Details worth knowing:

- **Names are compared case-folded.** `NOTES.TXT` in the library blocks
  `notes.txt` from the inbox, because on Windows and macOS they are the same
  file.
- **The suffix is kept exactly as the file spells it.** `photo.JPG` becomes
  `photo_1.JPG`, not `photo_1.jpg` — the collision is a name problem, not a
  reason to rename someone's extension.
- **`Plan` has no `apply` on it.** A value cannot move a file; only the module
  function can. That is what makes `--plan` trustworthy.
- **Apply verifies the size on arrival.** Across volumes `shutil.move` is a copy
  and a delete; a truncated copy is caught before the source is trusted to be
  gone.
- **Undo removes only empty folders.** Anything still in `Images/` stays, which
  is why the bundled library keeps `Images/photo.JPG` and the four folders the
  run created disappear.
- **A subfolder is reported, not silently ignored.** `iterdir()` sees `later/`
  and the plan names it, because "I did not look there" and "there is nothing
  there" are different statements.

---

# 🛠 Technologies

- Python 3 standard library: `pathlib`, `shutil`, `dataclasses`, `json`,
  `tempfile`, `argparse`
- pytest 9.1.1

No `colorama`, no `send2trash`, no network.

---

# 📚 Concepts Covered

- Compound extensions and the longest-match rule
- Why `Path.suffix` is the last dot, and why that is often the wrong question
- Planning as a value: separate deciding from doing
- Reserving names inside a plan, because the disk has not moved yet
- Case-insensitive name collisions on case-insensitive filesystems
- Rolling back a partial apply, and undoing a completed one
- Verifying size after a move across volumes
- Idempotence: a second plan on an empty inbox has nothing to do
- Refusing to touch your own fixtures
- Skipping versus ignoring: reporting a subfolder by name

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**146 tests passed** covering name validation, suffix matching (compound,
case-insensitive, extension-only names, unknown tails, trailing dots), the folder
table, `FileEntry`, `Move` (rename consistency, unknown folders, string paths),
`unique_name` (counters, compound suffixes, hidden names, case), `folder_names`,
`build_plan` (empty inbox, subfolders, library collisions, reservations, ordering,
no folders created), the `Plan` protocol, all seven audit checks with a negative
control for each, `apply_plan` (counts, sizes, idempotence, stale plan,
half-way rollback, vanished source), `undo` (names, sizes, folders, double
undo), the legacy table and loop, `naive_targets`, the seeded folders (untouched
by planning), the demo and every CLI mode including `--apply`, `--json` and the
refusal to move the bundled folders.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
