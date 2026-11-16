<div align="center">

# 📝 Text Editor

### The legacy editor saved with `open(path, "w")` — which truncates the file *before* writing a byte. A failed save left **8 bytes of a 52-byte note**, and the original was already gone. This one writes a sibling temporary file and `os.replace`s it into place, so the original never moves until the new bytes are complete.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def save(path, text):
    with open(path, "w") as handle:
        handle.write(text)
```

**1 → `open(path, "w")` truncates before a single byte is written.** A disk that fills up, a
permission that changes, a process that is killed — the original is already gone, and the
document is gone with it. There is no moment at which both exist:

```text
the legacy truncating save:   8 byte(s) -- the original is gone
the atomic save:              52 byte(s) -- the original never moved
```

**2 → Text mode chooses the newline for you.** A document whose lines end in `\n` is written
as `\r\n` on Windows, so the same text is 49 bytes on one machine and 52 on another, and a
round trip is not a no-op. The three line breaks cost exactly three bytes:

```text
the text has 3 line break(s)
written with LF:   49 bytes
written with CRLF: 52 bytes (3 more)
```

**3 → Undo cannot be a file re-read.** The editor kept the last saved text and called that
"undo": every edit since the save disappeared, and an edit made *before* the save could not
be undone at all.

**4 → `except UnicodeDecodeError: return ""` turns a damaged file into an empty one.** The
reader that swallows the error reports success and hands back nothing, so the next save writes
that nothing over the file:

```text
damaged bytes -> byte 3 is not valid UTF-8 (invalid continuation byte)
the legacy reader answered the damaged file with ''
```

**5 → A file uses one convention, and mixing them is a fact to report.** `first\r\nsecond\n`
is not "mostly CRLF"; it is a file that two readers will disagree about, and the line number
is the useful part of the message.

So this module keeps the document as text plus an explicit stack of `Edit`s, saves by writing
`name.tmp` beside the target and replacing it, and **states** the newline policy rather than
inheriting it from the platform. The legacy path is kept beside it, executable, so every claim
above is reproduced with a byte count.

The demonstration is offline and writes only inside a temporary directory.

---

# ✨ Features

- `encode(text, newline)` — the bytes under a **stated** policy; refuses text that already
  holds a `\r`, so the policy is the only thing that decides
- `decode(data)` — strict UTF-8, and the message names **which byte** was not valid
- `detect_newline(text)` / `normalise(text)` — one convention per file, or a sentence naming
  the line that broke it, and a lone carriage return refused
- `atomic_save(path, text, newline)` — write `name.tmp`, `os.replace` into place, return the
  byte count; a failure leaves the original untouched and the temporary removed
- `legacy_save(path, text, fail_after)` — the transcribed `open(path, "w")`, able to fail
  part-way through so the truncation is measurable
- `legacy_load(path)` — the reader that answers a decode error with `""`
- `Edit(start, removed, inserted, before_cursor, after_cursor)` — one change, with the cursor
  on both sides, so undo restores where you were as well as what you had
- `Document` — text, cursor, undo stack, redo stack, revision counter, saved revision,
  `dirty()`, `insert`, `backspace`, `delete`, `move_to`, `undo`, `redo`, `save`, `load`
- `audit` — eleven named checks, every one falsifiable by corrupting a measurement
- CLI: `--file`, `--edit`, `--save`, `--newline lf|crlf`, `--audit`, `--json`, `--quiet`,
  `--demo`
- 147 passing pytest tests

---

# 📂 Folder Structure

```text
02_Text_Editor/
│
├── src/
│   ├── main.py       # CLI: read, type, save, audit, JSON
│   └── documents.py  # bytes, newlines, atomic save, edits, undo/redo
│
├── tests/
│   └── test_documents.py
│
├── data/
│   └── notes.txt     # 52 bytes, CRLF, three lines of text
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 09_Desktop_Applications/02_Text_Editor

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: two saves, two policies, two damaged files, eleven checks
python src/main.py --demo

# The bundled note, as it is on disk
python src/main.py

# Type at the end and save as LF
python src/main.py --edit "!" --newline lf --save notes-lf.txt

# Keep the CRLF convention the file already had
python src/main.py --save notes-crlf.txt

# Every check
python src/main.py --audit

# The document, the byte counts and the measurements as JSON
python src/main.py --audit --json document.json
```

**Exit codes:** `0` = every check held · `1` = an audit check failed · `2` = a missing file, a
damaged file, a mixed-newline file, or a `--newline` value that is not `lf`/`crlf`.

---

# ⚙️ How It Works

```text
text (always \n internally)
  │
  ├── encode(text, "\n")    -> bytes with LF        (49)
  ├── encode(text, "\r\n")  -> bytes with CRLF      (52)
  │
  └── atomic_save(path)
        ├── write path.tmp with those bytes
        ├── os.replace(path.tmp, path)   <- the only moment the file changes
        └── on OSError: remove path.tmp, raise, original still in place
```

Details worth knowing:

- **The document holds `\n` only.** `Document` refuses text with a `\r` in it. The file's
  convention is a property of the *file*, carried in `newline`, and applied at save time.
  That is why a load → save round trip is byte-identical.
- **`os.replace` is atomic on both platforms.** On Windows it replaces the target in one
  step; on POSIX it is `rename(2)`. The temporary's name is the target's name plus `.tmp`,
  so it lands in the same directory and cannot cross a filesystem boundary.
- **The failure is demonstrated by blocking the temporary.** `atomic_save` on a path whose
  `name.tmp` is already a directory raises before touching the target: 52 bytes in, 52 bytes
  out. `legacy_save` with `fail_after=8` writes eight characters and raises: 52 bytes in,
  8 bytes out.
- **Undo is a stack of edits, not a snapshot.** Each `Edit` records `start`, `removed`,
  `inserted` and the cursor before and after, so `undo` rewrites exactly that span and puts
  the cursor back where it was. A new edit clears the redo stack, because the future you had
  is no longer the future you can have.
- **`revision` never counts an edit that changed nothing.** `insert("")` and a backspace at
  position 0 return `False` and leave both stacks and the counter alone, so "dirty" means a
  byte would actually change.
- **`dirty()` compares two numbers.** `revision != saved`, and `save` sets `saved = revision`.
  Undo counts as a revision, which is why undoing back to a saved state still reads dirty —
  the document you have is not the document on disk, even if the text matches.
- **Every check runs behind a guard.** A missing measurement is a `FAIL`, not a traceback, so
  the audit reports eleven verdicts no matter how badly the input was corrupted.

---

# 🧪 Technologies

- Python 3 standard library: `os`, `tempfile`, `pathlib`, `dataclasses`, `argparse`, `json`,
  `contextlib`
- pytest 9.1.1

No GUI toolkit, no editor library, no network. The demonstration writes only inside a
`tempfile.TemporaryDirectory()`.

---

# 📚 Concepts Covered

- Why `open(path, "w")` is not safe, and what "atomic replace" buys you
- The difference between a document's text and a file's bytes
- Newline policy as an explicit choice: LF, CRLF, and refusing a mixed file
- Strict decoding, and naming the exact byte that was not UTF-8
- Why `except: return ""` is the worst possible recovery
- Undo as an invertible edit, with the cursor as part of the state
- Why a new edit invalidates the redo stack
- Revision counters, and a dirty flag that means something
- Auditing with a corrupted measurement instead of a mocked function

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**147 tests passed** covering `encode` and its three refusals, `decode` and its two, both
newline conventions plus the mixed file and the lone carriage return, `normalise`,
`atomic_save` (byte counts, no temporary left behind, a blocked temporary, a directory
target, a fresh file), the legacy save's truncation and its failure, the legacy loader's
empty answer, `Edit` and its three refusals, `Document` construction and its four refusals,
every editing method, undo/redo across ten steps, `save`/`load` round trips, all
twenty-six measurements, eleven audit checks each with a negative control, the demo, and every
CLI mode including two exit-code-2 paths and one argparse refusal — **30 `pytest.raises**
refusals** in all.

---

# 🎯 Learning Outcomes

- Explain what `open(path, "w")` does to the file before `write()` is called
- Describe a write that can fail without losing what was there
- Say why `os.replace` is safer than `os.remove` followed by `os.rename`
- Keep one newline convention per file, and report the line that breaks it
- Distinguish "the bytes are not UTF-8" from "the file is empty"
- Design undo so it restores the cursor, not just the text
- Explain why an edit that changes nothing must not move the revision counter
- Read a byte count as evidence rather than a summary

---

# 🚀 Future Improvements

- A single `Ctrl+Z` group, so ten keystrokes undo as one word
- A redo stack that survives the application closing, written beside the document
- A save that keeps the last three versions, so a bad edit is recoverable a day later
- Encoding detection beyond UTF-8, with the detected encoding written into the file
- A real Tkinter `Text` widget in front of the same `Document`

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
