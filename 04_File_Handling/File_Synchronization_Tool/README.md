<div align="center">

# 🔄 File Synchronization Tool

### The legacy project hashed both sides of every pair, copied what differed, and never deleted anything — so a file removed from the source lived in the destination **forever**, and the tool still printed *Synchronization Complete.* Meanwhile the tempting shortcut — "same size, same file" — calls `5,6` and `9,9` identical, and a pinned timestamp fools a `st_mtime` check just as easily.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old project compared two files by hashing both of them:

```python
def files_are_different(source: Path, destination: Path) -> bool:
    if not destination.exists():
        return True
    return calculate_hash(source) != calculate_hash(destination)

for source_file in tqdm(files):
    relative_path = source_file.relative_to(SOURCE_FOLDER)
    destination_file = DESTINATION_FOLDER / relative_path
    destination_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        if files_are_different(source_file, destination_file):
            shutil.copy2(source_file, destination_file)
            self.synced_files.append(str(relative_path))
    except Exception as error:
        logger.error(f"{source_file}: {error}")

print("Synchronization Complete.")
print(f"Files Copied/Updated: {len(self.synced_files)}")
```

Four things follow.

**1 · A size is not a file.** The obvious speed-up to a hash is "same size, same
file". The bundled tree holds `x,y / 1,2 / 3,4 / 5,6` and `x,y / 1,2 / 3,4 / 9,9`
— 17 bytes each, different bytes. A size check calls them equal and the stale
copy stays stale forever. Here a size **mismatch** decides immediately (equal
content implies equal size), and a size **match** hashes, because a size cannot
tell `5,6` from `9,9`.

**2 · A timestamp is not a file either.** `shutil.copy2` preserves `mtime`, so a
copied file and its source share a timestamp *by design*; and a file edited twice
inside one timestamp tick keeps its `mtime` while its bytes change. The demo
builds exactly that pair — equal size, equal `mtime_ns`, different bytes — and
shows the timestamp check calling it identical while the digest does not.

**3 · A one-way mirror is not a copy job, it is a copy *and a delete* job.** The
legacy loop only walks the source, so a file removed from the source lives in the
destination forever, and the run still prints "Complete". Deletion is destructive,
so it is opt-in (`--delete`), every orphan is reported whether or not it will be
removed, and a `DELETE` only ever appears in a plan that says deletion was allowed.

**4 · `except Exception: logger.error(...)` plus "Complete" is a lie.** A run that
failed on three files prints the same two lines as a run that failed on none.
Here the plan is a value you can read, a copy goes to a `.syncing` name and is
renamed into place only after its digest matches, and `--apply` exits non-zero
when the mirror still fails.

| | legacy | here |
|---|---|---|
| equal size, different bytes | copied (it hashed) — but a size shortcut would not | `UPDATE`, "same size, different bytes" |
| equal size **and** equal mtime | copied | `UPDATE` by digest; the timestamp check says "same" |
| file removed from the source | left behind forever | `ORPHAN`, or `DELETE` with `--delete` |
| a failed copy | logged, "Complete" printed | refused, temp file removed, non-zero exit |
| review before writing | impossible | the default mode writes nothing |
| reads | both sides of every pair: 14 | 13 — the size gate spends a read only where it can help |

Standard library only: `hashlib`, `shutil`, `os`, no `tqdm`, no network.

---

# ✨ Features

- `digest` — SHA-256 in 64 KiB chunks; a 4 GB file never sits in memory
- `state` / `scan_tree` — size and `mtime_ns` per file, keyed by forward-slash relative path
- `Change` — one decision: `copy`, `update`, `skip`, `delete` or `orphan`, with the reason
- `Plan` — every change, `counts`, `by_action`, `to_copy`, `bytes_to_copy`, `orphans`, `summary`, `to_dict`
- `audit` — six checks, including "a delete is planned only when deletion is allowed", which is a real flag and not a restatement of the changes
- `apply_plan` — copy to `<name>.syncing`, compare digests, `os.replace`, then delete orphans and prune empty folders
- `verify_mirror` — presence, bytes and no extras, re-read from disk
- `legacy_mirror` / `naive_size_plan` / `naive_mtime_plan` — the three shortcuts, executable and measured
- `data/source/` (9 files, 374 bytes) and `data/destination/` (8 files, 269 bytes)
- CLI: `--delete`, `--apply`, `--verify`, `--legacy`, `--report`, `--json`, `--source`, `--target`, `--quiet`
- `--apply` **refuses** to write the bundled folders
- Exit `1` when the mirror still fails after an apply, `2` on a bad folder or a refused apply
- 130 passing pytest tests

---

# 📂 Folder Structure

```text
File_Synchronization_Tool/
│
├── src/
│   ├── main.py    # CLI: plan, verify, legacy, report, json, apply
│   └── sync.py    # digests, the plan, apply, verify, the demo
│
├── tests/
│   └── test_sync.py
│
├── data/
│   ├── source/                       9 files, 374 bytes
│   │   ├── notes.txt  report.csv  settings.json  empty.txt
│   │   ├── docs/api.txt     52 bytes ┐ same name, 52 vs 39
│   │   ├── docs/guide.txt            ┘ only in the source
│   │   ├── data/points.csv  17 bytes ┐ same size, 17 vs 17,
│   │   ├── img/pixel.png             ┘ different bytes
│   │   └── deep/nested/deep.txt      # three folders deep
│   └── destination/                  8 files, 269 bytes
│       ├── notes.txt  report.csv  settings.json     # identical
│       ├── docs/api.txt  39 bytes                   # stale
│       ├── data/points.csv  17 bytes                # stale, same size
│       ├── old/obsolete.txt  old/notes.bak          # orphans
│       └── stray.txt                                # orphan
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 04_File_Handling/File_Synchronization_Tool

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# The plan: what would happen, nothing written
python src/main.py
python src/main.py --delete      # the same, with the deletes named

# Prove the destination is a mirror
python src/main.py --verify

# What the legacy loop would do
python src/main.py --legacy

# Write the plan
python src/main.py --report plan.csv
python src/main.py --json plan.json

# Do it: both folders must be named explicitly
python src/main.py --apply --source .\photos --target .\backup
python src/main.py --apply --delete --source .\photos --target .\backup
```

**Exit codes:** `0` = the command ran (and the mirror is complete, after
`--apply`) · `1` = the mirror still fails, or a verification check failed ·
`2` = a bad folder, a folder nested inside the other one, or a refused `--apply`.

---

# 🧠 How It Works

```text
build_plan(source, dest, delete=False)
  ├── refuse a destination inside the source, or a source inside the destination
  ├── from_source = scan_tree(source)      key -> (size, mtime_ns)
  ├── from_dest   = scan_tree(dest)
  └── for each relative path in sorted order:
        only in the source      -> COPY     (hash the source)
        both, sizes differ      -> UPDATE   (hash the source only)
        both, sizes agree       -> hash both:
                                     equal   -> SKIP
                                     unequal -> UPDATE "same size, different bytes"
        only in the destination -> DELETE if delete else ORPHAN

apply_plan(plan)
  ├── for each copy/update:  copy2 -> <name>.syncing -> digest -> os.replace
  ├── then each delete:      unlink, or refuse if it vanished
  └── prune empty folders, deepest first

verify_mirror(source, dest)
  ├── every source file is present
  ├── every source file has the same bytes
  └── the destination holds no extra files
```

Details worth knowing:

- **The size decides first, and that is exact.** Equal content implies equal
  size, so a size mismatch is a certain `UPDATE`; only a size match needs a
  digest. On this tree that saves one destination read out of fourteen.
- **A copy is not trusted until it is read back.** The file is written to
  `report.csv.syncing`, hashed, compared with the source, and only then
  `os.replace`d into place. A reader never sees half a file, and a failed copy
  leaves the old one untouched.
- **Relative paths are POSIX, on purpose.** `deep/nested/deep.txt` on every
  platform, so a plan and its JSON are stable.
- **Deletion is a permission, not a derivation.** `Plan.allowed_delete` is set
  by `build_plan(delete=True)`; deriving it from the changes would make the
  audit check unfalsifiable.
- **A partial apply is safe.** Everything it did reads as `SKIP` next time, so
  the repair for an interrupted run is to run it again.
- **Empty folders go with their files.** `old/notes.bak` and `old/obsolete.txt`
  both leave, and `old/` is pruned — a mirror has no empty directories the
  source does not have.

---

# 🛠 Technologies

- Python 3 standard library: `hashlib`, `shutil`, `os`, `pathlib`,
  `dataclasses`, `json`, `csv`, `tempfile`, `argparse`
- pytest 9.1.1

No `tqdm`, no `send2trash`, no network.

---

# 📚 Concepts Covered

- Content identity (a digest) versus metadata (size, `mtime`) as evidence
- Why "same size" is necessary but not sufficient, and why "different size" is proof
- Why `copy2` preserving `mtime` makes a timestamp check circular
- One-way mirroring: copy **and** delete, or it is not a mirror
- Destination-only files as *orphans* versus *deletes*
- Atomic replacement: write, verify, `os.replace`
- Permissions recorded in a value (`allowed_delete`), not inferred from the output
- Verification by re-reading rather than by re-reporting
- Idempotence: a second plan finds only skips
- Refusing folder arrangements that would copy or delete the source itself

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**130 tests passed** covering `digest` (chunk equivalence, the empty file, missing
files, directories), `state` / `scan_tree` (missing folders, relative keys,
ordering, empty folders), `Change` (validation, `writes`, `bytes`, dict, frozen),
`build_plan` (copy/skip/update by size and by bytes, orphans, deletes, a missing
destination, reads counted, nesting refused, idempotence), the `Plan` protocol,
all six audit checks with a negative control for each, `apply_plan` (copies,
folders, overwrites, no `.syncing` left, deletes, pruning, mirrors complete, a
second plan all skips, a failed copy, a vanished delete), `verify_mirror` (all
three checks both ways, a missing destination), the legacy loop (reads, copies,
matches, orphans ignored), both naive shortcuts fooled and the digest not fooled,
the seeded folders (pinned counts, bytes and reads), the demo, and every CLI mode
including `--apply`, `--delete`, `--report`, `--json` and the refusal to write the
bundled folders.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
