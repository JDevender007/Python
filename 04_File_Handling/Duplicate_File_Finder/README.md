<div align="center">

# 📑 Duplicate File Finder

### The legacy project hashed every file it found, skipped the empty ones, and called two names for one file "two copies". A hard link hashes the same as its other name and deleting it frees **nothing** — the bytes are still there. And because the finder never cleared its own dictionary, a **second scan reported all eight files as duplicates of themselves**, including the two that have no copy at all.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old project walked a folder and hashed everything it found:

```python
def scan_files(self):
    files = [file for file in SCAN_FOLDER.rglob("*") if file.is_file()]
    for file in tqdm(files, desc="Scanning"):
        if file.stat().st_size == 0:
            continue
        try:
            file_hash = calculate_hash(file)
            if file_hash in self.hash_map:
                self.duplicates.setdefault(file_hash, []).append(file)
            else:
                self.hash_map[file_hash] = file
        except Exception as error:
            logger.error(f"{file}: {error}")
    return self.duplicates
```

Four things follow.

**1 · `if file.stat().st_size == 0: continue` throws away the best duplicate
pair there is.** Two empty files are byte-for-byte equal. The skip means they are
never scanned, never grouped, and never reported. Here a zero-byte file is
scanned like any other: it has a digest (`e3b0c44298fc…`, the SHA-256 of
nothing) and it takes its place in a group.

**2 · A path is not a copy.** `os.link(a, b)` makes `b` a second name for `a`'s
inode. Both paths are files. Both hash the same. Deleting one frees **zero
bytes**, because the bytes are still reachable under the other name. The legacy
scan reports such a pair as a duplicate and counts its size as reclaimable. This
module compares `(st_dev, st_ino)` **before** it hashes anything, and reports the
extra name as an *alias* worth nothing.

**3 · The finder is a session, not a value.** `self.duplicates` and
`self.hash_map` are never cleared, so the second call to `scan_files()` finds
every digest already in the map — and appends every path again, including
`budget.csv` and `unique.txt`, which have no copy at all. The demo runs that
exactly: one scan reports 2 duplicates, the second reports 8.

**4 · "Reclaimable" is `size × (copies − 1)` per group, over physical files.**
That is the only number that means anything: the bytes that come back if every
copy but one is deleted. The legacy report multiplies a doubled list by a size
and arrives at **1,315 bytes** where the honest answer is **343**.

| | legacy | here |
|---|---|---|
| empty files | skipped | one group of 2, worth 0 bytes |
| hard link | duplicate, size counted | alias, 0 bytes |
| second scan | every path is a duplicate | same value, not more groups |
| reclaimable | 1,315 bytes | 343 bytes |

Standard library only: `hashlib`, `os`, `pathlib`, no network.

---

# ✨ Features

- `digest` — SHA-256 in 64 KiB chunks; reads a 4 GB file without holding it
- `empty_digest` — the digest of nothing, a real answer rather than a special case
- `physical_key` — `(st_dev, st_ino)`, the identity of the bytes, not of the name
- `ScannedFile` — frozen value object; a path, a size, a digest and an inode
- `DuplicateGroup` — at least two copies, with `reclaimable = size × (copies − 1)`
- `Alias` — a second name for one file; `kept` is the name the scan counted, and nothing claims to be the "original"
- `ScanResult` — a value, not a session: `physical`, `total_bytes`, `reclaimable`, `duplicate_files`, `by_digest`
- `verify` — four checks that re-read every group from disk, with a negative control for each
- size before content — only equal-length files are ever read
- `report_rows` / `report_text` — a CSV report with digest, size, copies and returnable bytes
- `legacy_scan` / `LegacyFinder` — the defects, kept executable and measurable
- `data/files/` — 8 paths, 5 distinct sizes, 3 groups, 3 deletable copies, 343 bytes reclaimable
- CLI: `--summary`, `--duplicates`, `--verify`, `--report`, `--json`, `--legacy`, `--folder`, `--quiet`
- Exit `2` on a bad folder; `--demo` always returns `0`
- 129 passing pytest tests

---

# 📂 Folder Structure

```text
Duplicate_File_Finder/
│
├── src/
│   ├── main.py    # CLI: summary, duplicates, verify, report, legacy
│   └── finder.py  # digests, inodes, groups, the demo
│
├── tests/
│   └── test_finder.py
│
├── data/
│   └── files/
│       ├── report.txt        170 bytes ┐ identical
│       ├── report-copy.txt   170 bytes ┘
│       ├── notes.txt         173 bytes ┐ identical
│       ├── notes-backup.txt  173 bytes ┘
│       ├── empty-a.txt         0 bytes ┐ identical
│       ├── empty-b.txt         0 bytes ┘
│       ├── unique.txt        211 bytes
│       └── budget.csv         75 bytes
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 04_File_Handling/Duplicate_File_Finder

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# The folder, counted and grouped
python src/main.py
python src/main.py --summary
python src/main.py --duplicates

# Prove the groups still agree with the disk
python src/main.py --verify

# Write the findings
python src/main.py --report duplicates.csv
python src/main.py --json scan.json

# What the legacy project reported
python src/main.py --legacy

# Another folder
python src/main.py --folder "C:\Users\me\Downloads"
```

**Exit codes:** `0` = the command ran · `1` = a verification check failed ·
`2` = the folder does not exist or is a file.

---

# 🧠 How It Works

```text
scan(root)
  ├── rglob("*") -> files, sorted by name
  ├── for each path:
  │     key = (st_dev, st_ino)
  │     if key already seen -> Alias(path, kept)     <- before hashing
  │     else                -> ScannedFile(path, size, sha256, key)
  └── group by (size, digest)                        <- equal content implies
        keep groups of two or more                     equal size

DuplicateGroup.reclaimable = size * (len(copies) - 1)
ScanResult.reclaimable     = sum over groups
```

Details worth knowing:

- **The inode check comes first, and it is the whole point.** Hashing a hard
  link gives a digest identical to its other name. Only the inode says "this is
  the same bytes, not a copy of them".
- **A filesystem that reports inode 0** (some network shares) cannot answer the
  question. `physical_key` falls back to `(st_dev, realpath)` and says so in its
  docstring rather than pretending two hard links are two files.
- **Size before digest is exact, not a heuristic.** Equal content implies equal
  size, so bucketing by size first cannot split or merge a group. It only avoids
  reading files that cannot possibly match.
- **An empty file has a digest.** `sha256(b"")` is
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Skipping
  size 0 is a choice to ignore the most equal pair of files in the folder.
- **`verify` re-reads the disk.** It does not trust the digests it stored; it
  hashes again and compares, which is what makes it a check rather than a
  restatement.
- **A group's `copies` are sorted by name**, so the report is stable and a second
  scan is byte-identical.

---

# 🛠 Technologies

- Python 3 standard library: `hashlib`, `os`, `pathlib`, `dataclasses`, `json`,
  `tempfile`, `argparse`
- pytest 9.1.1

No `tqdm`, no `send2trash`, no third-party hashing, no network.

---

# 📚 Concepts Covered

- Content identity versus path identity (`(st_dev, st_ino)`)
- Hard links: two names, one inode, zero bytes freed
- Why empty files are a real duplicate group and zero reclaimable bytes
- `size × (count − 1)` as the only honest "space you would get back"
- Size bucketing before hashing, and why it is exact
- Streaming hashes: chunked reads of files larger than memory
- A function that returns a value versus a class that accumulates state
- Idempotence: the second scan must equal the first
- Verification by re-reading rather than by re-reporting
- Refusals: a missing folder, a file given as a folder, a directory given as a file

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**129 tests passed** covering the digest (chunk equivalence, the empty file, one
changed byte, missing file, directory, string paths), `physical_key` (hard links,
symlinks, missing files), `ScannedFile` (validation, key, `str`, dict, frozen),
`DuplicateGroup` (two copies required, reclaimable of 1/2/size 0, dict),
`Alias` (reclaims nothing, names both paths), `ScanResult` (protocol, summary,
`by_digest`, `to_dict`, all four verification checks and a negative control for
each), `scan` (missing folder, file-as-folder, empty folder, equal sizes with
different bytes, three copies, empty files, ordering, subfolders, aliases, chunk
size, idempotence), the reports, the legacy project (five defects pinned), the
seeded folder (fourteen pinned facts), the demo and every CLI mode including
`--folder`, `--report`, `--json` and `--quiet`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
