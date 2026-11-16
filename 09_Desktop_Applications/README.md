<div align="center">

# 🖥️ Desktop Applications

### Five desktop programs that each looked like "draw the widget and read the value" — and each one was really a question about *what the value means*. Is `2^3` eight or one? Does `open(path, "w")` keep the file? Is `int(width * scale)` a size? Is a queue position an index? Does `sort()` list a folder the way a person reads it? The rebuild keeps each defect executable, then removes the reason it was possible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Each of these five projects began as a `tkinter` window with a model behind it. None of them
needs a display any more: every one runs on bundled data, works in whole numbers where the
domain is whole numbers, and reproduces the original defect exactly — then shows what a value
has to be for the defect to be impossible.

The failure in each is never a typo. It is a **definition**: of what a number means, of what
a write means, of what a size is, of what "the next track" means, of what "inside a folder"
means.

**The lesson of each project is different, on purpose.** Five variations on "validate the
input" would teach nothing; five different ways a desktop application answers a question
nobody asked is the subject.

- **Calculator_GUI** — *a number has a precision, and an operator has a precedence.* The
  legacy evaluator did `eval(expression)` and formatted the answer with `f"{value:g}"`. So
  `2^3` came out **1** (Python's `^` is exclusive-or), `2^3^2` came out **3** instead of
  **512** (`^` is left-associative), `10/0` raised inside the window, and `2.675` printed
  **2.67** where a half-up rule says **2.68** — while `2.675` as a double is not the decimal
  it looks like. The rebuild keeps a tokenizer, a recursive-descent parser with right-
  associative `^`, exact decimal arithmetic for money, half-up rounding from digits, and
  **three named refusals** instead of a traceback. Five numeric disagreements, twelve
  expressions.
- **Text_Editor** — *`open(path, "w")` truncates before it writes.* A save that failed part
  way through left **8 bytes of a 52-byte note**, and the original was already gone. Text
  mode also chose the newline for the platform, so the same text was 49 bytes on one machine
  and 52 on another, and a mixed-ending file was read as if it were one convention. The
  reader that answered a decode error with `""` turned a damaged file into an empty one —
  and the next save wrote that nothing back. The rebuild writes a sibling `.tmp` and
  `os.replace`s it, states the newline policy, names the byte that was not UTF-8, and keeps
  undo as a stack of invertible edits with the cursor on both sides.
- **Image_Viewer** — *`int(width * scale)` is not a size.* A 3×1 sliver in a 2×2 box came out
  **2×0**; a 3000×1000 panorama lost a pixel of height; **4 of 9** bundled images were the
  wrong size. A viewer that always scaled by width put a 90×160 portrait at **200×356** in a
  200×200 box and clipped a third of it, where fitting says **113×200**. And fitting is not
  filling: `100×50` in a `40×40` box covers with **80×40** at `(-20, 0)`, and the same image
  fitted inside is `40×20`. The rebuild compares two products to find the binding side, rounds
  the derived side to nearest for a fit and up for a cover, and refuses a zero size where it
  is created.
- **Music_Player** — *a queue position is not an index into a list people edit.* With `Ember`
  playing, deleting track 0 left the cursor on a number that now pointed one track too far:
  the next track was **`Quiet Hours` instead of `Drift`**, and one track was never played.
  `if cursor >= len(tracks): cursor = 0` also decided the repeat mode by itself, so *repeat
  off* played forever, and `f"{total // 60}:{total % 60}"` printed a 64-minute playlist as
  **`64:23`**. The rebuild keeps a cue into a permutation of positions, asks the repeat mode,
  shuffles with a seeded Fisher–Yates pass consumed in order, and prints `1:04:23`.
- **File_Explorer** — *`sort()` is not a listing order, and a join is not confinement.*
  `names.sort()` put `file10` before `file2` and `Zebra.txt` before `apple.txt`; **4 of 11**
  visible positions were wrong. `Path(root) / name` honoured `..`, so `data/site` +
  `../secret.txt` landed on **`data/secret.txt`**, and an absolute name discarded the root
  entirely. The guard people reach for, `str(path).startswith(str(root))`, called
  `data/site-other` *inside* `data/site`. The rebuild sorts by a natural key with case folded,
  breaks ties by the raw name so the order is total, and confines every name to its root — or
  refuses it by name.

**Every number is exact and every claim is checkable.** Pixels, bytes, seconds, positions and
tenths are integers; each demo prints the quantity it derived; each project's `audit()`
re-derives its own result from the data instead of restating the summary it just printed, and
every check has a negative control that makes it fail.

Standard library only: no `tkinter` at run time, no imaging library, no audio backend, no
network, no API keys, no downloads.

---

# 🎓 Learning Objectives

- Read a number for what it is: a whole count, a decimal with a scale, or a float that only
  approximates one
- Evaluate an expression with expected precedence and associativity, and refuse `10/0` by name
- Round half-up from digits, and explain why `round(2.675, 2)` is not 2.68
- Describe a write that can fail without losing what was there, and why `os.replace` is the
  moment the file changes
- State a file's newline convention instead of inheriting one from the platform
- Distinguish "the bytes are not UTF-8" from "the file is empty"
- Design undo so it restores the cursor as well as the text
- Compute a fitted rectangle in integers, and say which side binds from two products
- Choose a rounding direction from the requirement: never overflow, or never leave a seam
- Keep a cursor into a permutation so an edit cannot skip an item
- Make a repeat mode a decision the advance function takes
- Shuffle with Fisher–Yates from a seed, and prove a pass is a permutation
- Sort a listing by value with case folded, and break ties so the order is total
- Confine a name to a root with a directory prefix, not a string prefix
- Format a byte count in integer tenths, and never a tenth of a byte
- Write an `audit()` that returns every check, then force each one to fail

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Calculator_GUI | A real parser: right-associative `^`, decimals with a stated precision, half-up rounding, three named refusals instead of `eval` and a traceback. | 137 | ✅
02 | Text_Editor | An atomic save (`.tmp` + `os.replace`), an explicit newline policy, strict decoding that names the byte, and undo as invertible edits. | 147 | ✅
03 | Image_Viewer | The binding side from two products; nearest for a fit, up for a cover; a `Size` that cannot be zero; `2x0` becomes `2x1`. | 153 | ✅
04 | Music_Player | A cue into a permutation, three repeat modes, a seeded Fisher–Yates shuffle, and `1:04:23` instead of `64:23`. | 151 | ✅
05 | File_Explorer | A natural key with case folded, a total order, and `confine()` — a directory prefix, not `startswith`. | 174 | ✅

**Total: 762 tests.**

---

# 🧠 Concepts Covered

- Number kinds: integer counts, scaled decimals, and the double that approximates them
- Operator precedence and associativity, tokenised and parsed rather than `eval`ed
- Half-up rounding from integer division, at a stated scale
- Named refusals: a division by zero, an unknown token, an unbalanced expression
- Atomic replace, temporary files in the same directory, and a failure that leaves the
  original untouched
- Newline policy as a property of the file, applied at write time
- Strict UTF-8 decoding and the byte offset of the first bad byte
- Undo as an invertible edit with the cursor on both sides, and a redo stack that a new edit
  clears
- Fitting versus filling: which side binds, and which way the derived side rounds
- A cross product as the distance from an exact aspect ratio
- A cue into a permutation instead of an index into a list people edit
- Repeat modes, and a shuffle that is a permutation consumed in order
- Natural sort keys: digit runs compared as numbers, cases folded, ties broken
- Path confinement: normalise, then compare with a separator
- Integer tenths for a size, and units that do not apply below 1 KB
- Audits whose negative controls corrupt the argument rather than mocking a function

---

# 📁 Repository Structure

```text
09_Desktop_Applications/
│
├── 01_Calculator_GUI/
│   ├── src/    calculator.py, main.py
│   ├── tests/  test_calculator.py
│   └── data/   expressions.txt
│
├── 02_Text_Editor/
│   ├── src/    documents.py, main.py
│   ├── tests/  test_documents.py
│   └── data/   notes.txt
│
├── 03_Image_Viewer/
│   ├── src/    images.py, main.py
│   ├── tests/  test_images.py
│   └── data/   images.txt
│
├── 04_Music_Player/
│   ├── src/    player.py, main.py
│   ├── tests/  test_player.py
│   └── data/   playlist.txt
│
└── 05_File_Explorer/
    ├── src/    explorer.py, main.py
    ├── tests/  test_explorer.py
    └── data/   listing.txt
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse
CLI, a `tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a
`.gitignore`, and a `README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 09_Desktop_Applications/03_Image_Viewer

python src/main.py --demo          # offline, deterministic, exit 0
python src/main.py                 # the same work, printed as a table
python src/main.py --audit         # every check with PASS/FAIL
python -m pytest tests -q          # the suite
```

Every project supports `--demo`, `--quiet` with `--demo` (prints nothing), `--audit`,
`--json <path>`, and flags of its own (`--expression`, `--file`, `--edit`, `--save`,
`--newline`, `--image`, `--box`, `--mode`, `--centre`, `--playlist`, `--repeat`, `--seed`,
`--remove`, `--steps`, `--listing`, `--sort`, `--hidden`, `--resolve`, `--root`, `--size`).
Nothing opens a window, nothing touches the network, and no demo writes into the repository:
the text editor and the image viewer write only inside a `tempfile.TemporaryDirectory()`.

---

# ✅ Verify the whole category

```powershell
Get-ChildItem -Directory | ForEach-Object {
    Push-Location $_
    python -m compileall -q src tests
    python -m pytest tests -q
    python src\main.py --demo
    Pop-Location
}
```

The gates each project must pass, and does:

1. `compileall` on `src` and `tests` exits 0
2. `pytest` passes with no skips
3. `--demo` exits 0, prints `Cross-checks OK: ...` and `Demo completed successfully.`
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing
5. no non-ASCII byte in `src/`, `tests/` or `data/`

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why `eval` is not a calculator, and what a parser has to decide before it evaluates
- Why `round(2.675, 2)` is 2.67, and what half-up from digits does instead
- Why `open(path, "w")` can destroy a document before it writes a byte
- Why a newline is a property of the file rather than of the machine
- Why `except UnicodeDecodeError: return ""` is the worst possible recovery
- Why an undo stack of edits beats a snapshot of the text
- Why `int(width * scale)` can lose a pixel, and which side of a box binds
- Why fitting rounds to nearest while covering rounds up
- Why a track number breaks the moment a track is deleted
- Why reshuffling before every draw is neither fair nor debuggable
- Why `sort()` is not the order a person reads
- Why `startswith` is not a containment test for paths
- Why a byte count has no tenth, and a kilobyte does
- How to write an audit whose every check has a negative control
- How to make a demonstration reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `tokenise`, `parse`, `parse_duration`, `parse_playlist`, `parse_listing`,
`parse_images`, `detect_newline`
Values — `Quantity`, `Money`, `Document`, `Edit`, `Size`, `Placement`, `Track`, `Player`,
`Entry` (validated at construction)
Comparison — `binding_side`, `fit_inside`, `fill_box`, `centred`, `natural_key`, `contains`
Refusal — `CalculatorError`, `DocumentError`, `ImageError`, `PlayerError`, `ExplorerError`
Legacy — `LEGACY_SAVE`, `LEGACY_LOAD`, `LEGACY_RESIZE`, `LEGACY_NEXT`, `LEGACY_TOTAL`,
`LEGACY_LISTING`, `LEGACY_CONTAINS`
Arithmetic — `divide_half_up`, `round_div`, `ceil_div`, integer tenths, scaled decimals
Files — temporary sibling plus `os.replace`, stated newlines, strict decoding
State — a cue into a permutation, repeat modes, undo/redo stacks, a dirty revision
Reporting — `Quantity.line`, `Document.line`, `Placement.line`, `Player.line`, `Entry.line`
Testing — negative controls per audit check, pinned demo output, byte-identical runs

---

# 🚀 Future Improvements

- Real `tkinter` front ends over the same library modules, with the audits kept as they are
- A shared `--batch` runner that executes all five demos and compares their output hashes
- A single `audit` harness for the category, so all five report in the same shape
- Undo grouping in the editor, so ten keystrokes undo as one word
- EXIF orientation in the viewer, so a sideways photograph is rotated rather than letterboxed
- A reorderable queue in the player, with the cue expressed as "the track", not a slot
- Symlink-aware confinement in the explorer, so a link that leaves the root is refused
- A cross-platform newline and separator test matrix, run in CI

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a clear message.
4. Push the branch.
5. Open a Pull Request.

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
