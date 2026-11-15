<div align="center">

# 📄 PDF Merger

### The legacy engine ended with `except Exception: return False`, and its validator was `return len(pdf_files) >= 2`. **Six different failures, one bit.** A file that is gone, a text file renamed to `.pdf`, a truncated download, a password — all "merge failed", which is the one message that is never true.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def merge(self, pdf_files, output_file, progress_callback=None) -> bool:
    try:
        self.merger = PdfMerger()
        for index, pdf in enumerate(pdf_files, start=1):
            self.merger.append(pdf)
            ...
        return True
    except Exception:
        self.close()
        return False

def validate(self, pdf_files: list[str]) -> bool:
    return len(pdf_files) >= 2
```

Three defects, and the first one is why the other two survived.

**1 → `return False` throws the reason away.** Every way a merge fails collapses into
one bit: the file is gone, empty, not a PDF, truncated in transit, encrypted, or the
output is one of the inputs. The caller cannot say which file is at fault or what to
do about it, so the message becomes "merge failed" — and *something specific* failed.

Here every failure is a `Problem` that names a file and gives a reason, and a
`Reading` either holds a parsed document or holds the sentence that explains it:

```text
empty.pdf          the file is empty: there is not one byte in it
renamed.pdf        no %PDF- header: the file starts with 'this is '
truncated.pdf      truncated: the file has no %%EOF marker, so the download never finished
index.pdf          the index is said to start at byte 0, but the file holds '%PDF-1.7' there
locked.pdf         encrypted: the file declares /Encrypt, so its pages cannot be read without a password
cut-page.pdf       the page tree says /Count 9 and the file holds 3 page object(s)
```

Six inputs, six sentences, where the legacy engine gave one `False`.

**2 → `len(pdf_files) >= 2` validates the *list*, not the *files*.** Two paths that do
not exist pass it. So does a text file renamed `.pdf`, an empty file, a truncated
download, a password-protected document, and the same file twice:

```text
the legacy validator on 3 names that cannot be read:
    missing.pdf
    data/pages.txt
    notes.txt
    it answers True -- the count is the whole check

the same three names, asked properly:
    missing.pdf        there is no such file: missing.pdf
    data/pages.txt     no %PDF- header: the file starts with '; three '
    notes.txt          there is no such file: notes.txt
```

This module inspects every file **before a single byte is copied**: the magic number,
the `%%EOF` marker, the cross-reference index, every index entry, the trailer, the
page tree, the encryption flag — and whether the output would overwrite an input.

**3 → A name is a prefix of another name, and `count` cannot tell.** The page tree
declares `/Type /Pages`; each page declares `/Type /Page`. Every page's
`/Type /Page` is also the first fifteen bytes of the tree's `/Type /Pages`, so

```python
data.count(b"/Type /Page")
```

is **one too many for every document that has a page tree** — that is, all of them.
It looks right on a one-page file, and it is wrong on all the others:

```text
alpha.pdf holds 3 page object(s) with /Type /Page
it also holds 1 /Type /Pages tree, whose first fifteen bytes are the same
data.count(b'/Type /Page') answers 4 -- one too many
```

This module reads objects and compares the **whole** name token, and stops scanning
at an object's `stream` — because a page whose text happens to be `/Type /Page` is a
page with an odd title, not a second page.

The documents are written **by hand** here — header, objects, cross-reference table,
trailer, `startxref`, `%%EOF` — so nothing is installed and nothing is downloaded,
and the bytes are real enough that a reader can check them: every index entry must
point at its own object header, and the trailer's `/Size` must agree with the index.

| | legacy | here |
|---|---|---|
| a file that is gone | `False` | `there is no such file: missing.pdf` |
| a text file renamed `.pdf` | passes `validate` | `no %PDF- header: the file starts with 'this is '` |
| a truncated download | `False` | `truncated: the file has no %%EOF marker` |
| an encrypted document | `False` | `encrypted: the file declares /Encrypt` |
| the same file twice | allowed | `duplicate: this file is already in the list at position 1` |
| the output is an input | overwrites it | `writing it would overwrite a source` |
| `count(b"/Type /Page")` | 4 pages in a 3-page file | 3 objects read one at a time |
| one file in the list | `False` | `at least two documents are needed to merge, and the list holds 1` |

Standard library only: no pypdf, no PyMuPDF, no tkinter, no network.

---

# ✨ Features

- `describe` — the first bytes of a file, safely, so an error can quote them
- `check_title` — printable ASCII, no bracket, no backslash, never blank
- `Page` / `Document` — titles in order, `size()`, `number()`, `lines()`
- `build_document` / `merge` — values in, values out, no files touched
- `render` — a real PDF: header, catalog, page tree, page and content objects, a
  cross-reference table with measured offsets, trailer, `startxref`, `%%EOF`
- `objects_of` — every `N 0 obj`, its offset and its body
- `Object.type_name` — the whole `/Type` name, with the stream excluded
- `count_pages` / `count_pages_naive` — the right count, and the legacy one beside it
- `check_index` — every claim the index makes, checked against the bytes
- `parse_document` — seventeen documented reasons a file cannot be read
- `build_documents` / `read_bundle` — a `document<TAB>page title` bundle
- `Reading` / `Problem` / `Report` — a document *or* a sentence, never neither
- `inspect` / `inspect_path` / `read_bytes` / `check_files` — reasons instead of raises
- `check` — the list rules too: two documents, no duplicates, no output collision
- `merge_bytes` — bytes *and* the report that justifies them, or `b""` and the report
- `Lab` / `build_lab` / `audit` — nine named checks over the parts, the bytes and the report
- CLI: `--file`, `--output`, `--bundle`, `--write`, `--pages`, `--audit`, `--json`,
  `--quiet`, `--demo`
- 168 passing pytest tests

---

# 📂 Folder Structure

```text
PDF_Merger/
│
├── src/
│   ├── main.py         # CLI: validate, merge, write, count, audit
│   └── pdfdocument.py  # pages, the writer, the reader, the report
│
├── tests/
│   └── test_pdfdocument.py
│
├── data/
│   └── pages.txt       # three documents: 3 + 2 + 1 pages
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 06_Automation/PDF_Merger

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: six damages, six reasons, and the count that is always one too high
python src/main.py --demo

# Merge the bundled three documents and show every page
python src/main.py --pages

# Write the bundle out as real PDFs, then merge your own files
python src/main.py --write out
python src/main.py --file out\alpha.pdf out\beta.pdf --output merged.pdf --pages

# Every check
python src/main.py --audit

# The report as JSON
python src/main.py --json report.json
```

**Exit codes:** `0` = merged (or written) · `1` = the report has a problem, so
nothing was merged and nothing was written · `2` = the bundle is missing or
malformed.

---

# ⚙️ How It Works

```text
render(document)
  ├── offsets measured while writing, so the index can be checked
  ├── catalog -> page tree -> (page, contents) for every page
  └── xref | trailer /Size /Root | startxref | %%EOF

parse_document(bytes)                # header, tail, index, objects, tree, titles
  ├── "%PDF-" ? version?  "%%EOF" last?
  ├── check_index: startxref -> xref -> 19-byte entries -> each object header
  ├── objects_of: "N 0 obj" ... "endobj", no duplicate numbers
  ├── page_objects: type_name() == "Page" -- whole token, stream excluded
  └── /Count must equal the page objects, and every page must name a title

check(files, output)
  ├── fewer than two inputs?        -> "(list)" reason
  ├── duplicate input?              -> the position it first appeared
  ├── output is one of the inputs?  -> it would overwrite a source
  └── every input: a Reading, then a Problem for each failure
```

Details worth knowing:

- **The reason is the return value.** `PdfError` carries the sentence; `inspect`
  turns it into a `Reading`; `check` turns readings into `Problem`s. Nothing
  anywhere returns a bare `False`.
- **`b""` is a third state.** `merge_bytes` returns `(b"", report)` on failure, which
  is neither `True` nor "an empty PDF" — the report says which.
- **Validation happens before the copy.** Every file is inspected first, so a bad
  input cannot leave a half-written output behind.
- **A prefix is not a name.** `/Type /Page` lives inside `/Type /Pages`, so the
  substring count is one too many for every document with a tree.
- **A stream is not a dictionary.** `type_name` stops at `stream`, so a title that
  says `/Type /Page` does not become a second page.
- **An index is a claim.** Every entry must point at its own object header, and the
  trailer's `/Size` must match, or the file is a guess about itself.
- **A broken file is a `FAIL`.** Every audit check runs behind a guard, because a
  negative control plants the defect exactly where the check looks.

---

# 🧪 Technologies

- Python 3 standard library: `re`, `dataclasses`, `pathlib`, `json`, `argparse`,
  `contextlib`
- pytest 9.1.1

No pypdf, no PyMuPDF, no network.

---

# 📚 Concepts Covered

- Why a boolean return value cannot carry a diagnosis
- Validation of files rather than of a list of names
- Magic numbers, trailer markers and truncated downloads
- A cross-reference table as a set of checkable claims about offsets
- Encrypted documents, and detecting one before parsing
- `/Type /Page` versus `/Type /Pages`: a prefix that inflates every count
- Reading an object's dictionary without reading its stream
- Duplicate inputs and an output that is one of the inputs
- Reports as data: readings, problems, reasons, and a summary
- Audits with a negative control per check, behind a guard

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**168 tests passed** covering the byte describer, nine title rules, the document and
merge values, eleven writer rules including the pinned first-object offset, object
reading and the whole-name rule, the naive-versus-exact count at four sizes, sixteen
index and trailer refusals, fourteen reader refusals (one per documented reason),
the bundle parser, ten report shapes, the path helpers, twelve list rules including
duplicate and output-collision, `merge_bytes`'s three states, nine audit checks with
a negative control each (including one that proves the audit does not raise on a
broken index), the demo, and every CLI mode including two exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Explain why `except Exception: return False` is a bug even when it "works"
- Validate what a file *is* instead of how many names were passed
- Check a cross-reference table against the bytes it points at
- Spot why `count(b"/Type /Page")` is wrong, and how to count properly
- Separate an object's dictionary from its stream when reading either
- Refuse a duplicate input and an output that is one of the inputs
- Build a report that a caller can print, log and test

---

# 🚀 Future Improvements

- Reading real-world PDFs, with object streams and compressed cross-references
- Incremental updates, so a merge appends rather than rewrites
- Page ranges: `alpha.pdf:1-2`, so a merge can select
- A bookmark per input document, in the merged outline
- A rotation and page-size check, so mixed orientations are reported not guessed

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
