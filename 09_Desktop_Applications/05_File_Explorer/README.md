<div align="center">

# 📁 File Explorer

### The legacy listing did `names.sort()` and `Path(root) / name` — so `file10` came before `file2`, `Zebra.txt` came before `apple.txt`, and `data/site` + `../secret.txt` landed on `data/secret.txt`. This one sorts by value with case folded, and refuses anything that is not under its root.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
names = [entry.name for entry in Path(path).iterdir()]
names.sort()
return [Path(path) / name for name in names]
```

**1 → `sort()` compares characters, so a digit is not a number.** `"1" < "2"`, so ten files
are listed 1, 10, 2, 20. A person reads those as numbers, and the mistake gets worse as the
folder grows:

```text
sort():      file1.txt, file10.txt, file2.txt, file20.txt
by value:    file1.txt, file2.txt, file10.txt, file20.txt
```

**2 → A bare `sort()` compares by code point, so every capital comes first.**
`Zebra.txt` sorts before `apple.txt`, and the folder looks shuffled. Case-blind comparison is
the fix — and `str.lower()` is not `str.casefold()`: casefold maps the German sharp s to
`ss`, so two spellings of one word compare *equal* instead of one sorting after the other.

```text
sort():      Banana.txt, Zebra.txt, apple.txt
casefold():  apple.txt, Banana.txt, Zebra.txt
```

**3 → `Path(root) / name` is not confinement.** It honours `..`, so `data/site` +
`../secret.txt` lands on `data/secret.txt`, and an absolute name replaces the root entirely.
The guard people then reach for — `str(target).startswith(str(root))` — says that
`data/site-other/x.txt` is *inside* `data/site`, because a string prefix is not a directory
prefix:

```text
data/site + '../secret.txt' -> refused: True
the legacy join lands on:    data/secret.txt
data/site-other/x.txt is outside data/site here, and inside to startswith()
```

**4 → A byte count is not a float.** `f"{size / 1024:.1f} KB"` prints 1280 bytes as
`1.2 KB` (the double is exactly 1.25, and the formatter rounds half to even) where half-up
says `1.3 KB`; and it prints a one-byte file as `1.0 B`, a tenth of a byte that does not
exist.

So this module keeps a natural key whose digit runs compare as numbers, a case-folded sort
whose ties are broken by the raw name so the order is total, a `confine()` that normalises
the join and refuses anything not under the root, and a `format_size()` built from integer
tenths. The legacy paths are kept beside them, executable, so every claim above is
reproduced with a number.

The demonstration is offline: one bundled listing of thirteen entries.

---

# ✨ Features

- `natural_key(name)` — digit runs become `(0, int)`, text becomes `(1, str)`; the name is
  case-folded first, so `file2` and `FILE2` share a key
- `sort_names` / `sort_entries` — case-blind, natural order, raw name as the final tiebreak,
  so the order is total and never depends on input order
- `legacy_sort_names` / `legacy_sort_entries` — the transcribed `sort()` and
  `(is_file, name.lower())` keys, executable
- `is_hidden` — the leading-dot convention, stated as a convention
- `format_size` — bytes, KB, MB, GB, TB with integer tenths rounded **half-up**; a byte count
  carries no tenth
- `legacy_format_size` — the float loop, which rounds 1.25 KB down and gives a byte a tenth
- `Entry` — name, `file`/`dir`, bytes; `is_dir()`, `hidden()`, `shown_size()`, `legacy_size()`
- `parse_listing` — `name | kind | bytes` per line, `;` comments, distinct names
- `confine(root, name)` — the normalised join, or a refusal naming what left the root;
  absolute names and null bytes refused outright
- `contains` / `legacy_contains` — a path-part prefix against a string prefix
- `legacy_join` / `legacy_normalised` — `Path(root) / name`, and where it actually points
- `audit` — eleven named checks, every one falsifiable from a measurement
- CLI: `--listing`, `--sort natural|legacy`, `--hidden`, `--resolve`, `--root`, `--size`,
  `--audit`, `--json`, `--quiet`, `--demo`
- 174 passing pytest tests

---

# 📂 Folder Structure

```text
05_File_Explorer/
│
├── src/
│   ├── main.py      # CLI: list, sort, resolve, size, audit, JSON
│   └── explorer.py  # natural keys, case folding, confinement, sizes
│
├── tests/
│   └── test_explorer.py
│
├── data/
│   └── listing.txt   # thirteen entries, two of them hidden
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 09_Desktop_Applications/05_File_Explorer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: thirteen entries, two sorts, one escape, eleven checks
python src/main.py --demo

# The listing, naturally ordered, hidden names left out
python src/main.py

# The same listing the legacy way, to see what changed
python src/main.py --sort legacy

# Include the dot names
python src/main.py --hidden

# Join a name to the root, or refuse it
python src/main.py --resolve notes.txt
python src/main.py --resolve ../secret.txt

# One size, here and from the float formatter
python src/main.py --size 1280

# Every check
python src/main.py --audit

# The listing, the measurements and the checks as JSON
python src/main.py --hidden --audit --json listing.json
```

**Exit codes:** `0` = every check held · `1` = an audit check failed · `2` = a missing
listing, an escaping name, an absolute name, a negative size, a `--sort` that is not
`natural`/`legacy`, or a `--size` that is not a whole number.

---

# ⚙️ How It Works

```text
natural_key("file10.txt")
  -> ((1, "file"), (0, 10), (1, ".txt"))     compare part by part
  -> (1, "file")  == (1, "file")
     (0, 10)        is an int, so 2 < 10
     (1, ".txt")  == (1, ".txt")

confine("data/site", "docs/../notes.txt")
  -> "data/site/notes.txt"     inside: allowed
confine("data/site", "../secret.txt")
  -> "data/secret.txt" is not "data/site" nor under it  -> refused
```

Details worth knowing:

- **A digit run is a number, and the parts never compare unlike types.** Every part is
  tagged `(0, number)` or `(1, text)`, so `(0, 10)` and `(1, "a")` compare on the tag before
  the payload — no `TypeError`, and digits sort before letters.
- **Case is folded, not lowered.** `"Stra\u00dfe".casefold() == "strasse"` and
  `"STRASSE".casefold() == "strasse"`, so the key ties; the raw name is the second element
  of the sort key, which makes the order total (`"STRASSE"` first, because `"S" < "s"`).
- **Leading zeros keep the order total without changing the value.** `file007` and `file7`
  share a digit part, so the raw name decides — deterministically.
- **`confine` normalises before it compares.** The join is `os.path.normpath`ed, so
  `docs/../notes.txt` collapses to `notes.txt` and is accepted, while `../secret.txt`
  collapses to something that does not start with `base + "/"` and is refused.
- **The prefix is a directory prefix.** The guard is `joined == base or
  joined.startswith(base + "/")`, which is why `data/site-other` is outside `data/site` — the
  exact comparison the legacy `startswith` gets wrong.
- **Absolute names are refused before the join.** A leading `/` or `\`, a drive letter, or a
  null byte is a refusal with its own message, because `Path(root) / "/etc/passwd"` silently
  discards the root.
- **Sizes are integer tenths.** `tenths = divide_half_up(size * 10, unit)`, printed as
  `whole.part` and with the `.0` dropped; below 1024 the count is printed as whole bytes,
  because there is no tenth of a byte.
- **Every check runs behind a guard.** A missing measurement is a `FAIL`, not a traceback, so
  the audit reports eleven verdicts no matter how the input was corrupted.

---

# 🧪 Technologies

- Python 3 standard library: `os.path`, `re`, `dataclasses`, `pathlib`, `argparse`, `json`,
  `contextlib`
- pytest 9.1.1

No GUI toolkit, no `os.scandir` on the real filesystem, no network. The "explorer" is a
listing in a text file and a confinement rule over strings.

---

# 📚 Concepts Covered

- Why lexicographic order is not the order a person reads
- Natural sort keys: splitting on digit runs and tagging the parts
- Case folding versus lowering, and why a tie needs a second key
- Making a sort total, so the result never depends on input order
- Hidden names as a convention rather than a property
- Path normalisation before comparison
- A directory prefix (`base + "/"`) versus a string prefix (`startswith`)
- Absolute names, null bytes, and the join that silently discards its root
- Integer tenths for a size, and why bytes carry none
- Auditing a sort and a path rule with corrupted measurements

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**174 tests passed** covering `divide_half_up` and its three refusals, `format_size` across
eleven pinned sizes plus its three refusals, the legacy formatter's 1.25 KB and 1.0 B,
`natural_key`'s structure, folding, leading zeros and two refusals, both sorts including the
tie and a permutation check, `is_hidden`, `Entry` and its six refusals, both entry sorts,
`visible`/`hidden`, the parser's five refusals, `confine` with eight refusals, `is_confined`,
the legacy join and both prefix guards, every measurement, eleven audit checks each with a
negative control, the demo, and every CLI mode including four exit-code-2 paths and two
argparse refusals — **34 `pytest.raises` refusals** in all.

---

# 🎯 Learning Outcomes

- Explain why `"file10" < "file2"` and what a natural key does about it
- Split a name on digit runs and compare numbers as numbers
- Fold case with `casefold()` rather than `lower()`, and say why it matters
- Break a tie with a second key so the sort is total
- Normalise a joined path before deciding whether it is inside
- Compare directory prefixes with a separator, not with `startswith`
- Refuse an absolute name instead of letting the join discard the root
- Print a size in integer tenths, half-up, and never a tenth of a byte
- Audit a rule by corrupting the measurement it reads

---

# 🚀 Future Improvements

- Windows hidden *attributes* as well as the leading dot, with the two sources kept apart
- A tree walk with the same confinement rule applied at every level
- Symlink resolution, so a link that points outside is refused for the reason it is outside
- A sort that can be locale-aware when the user asks, with the total order still guaranteed
- A real Tkinter tree in front of the same listing and the same `confine()`

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
