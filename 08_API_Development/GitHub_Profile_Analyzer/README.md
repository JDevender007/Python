<div align="center">

# 📑 GitHub Profile Analyzer

### The legacy collector asked for `?page=2` and trusted it. A page number is not "the next items" — it is "items 5 to 8" of a list that keeps moving. One repository pushed between page 1 and page 2 and the walk returned **11 rows for 10 repositories**: `delta` twice, `kilo` never.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
out = []
page = 1
while True:
    data = client(url + "?page=%d" % page)
    if not data:
        break
    out += data
    page += 1
return out
```

**1 → A page number is an offset into a moving list.** Page 1 collects indices 0-3. A
repository is pushed, so everything shifts right by one and `delta` — the last item of
page 1 — is now at index 4, the first item of page 2:

```text
page 1 [alpha, bravo, charlie, delta] total=10 next=after=104
        one repository is pushed
page 2 [delta, echo, foxtrot, golf]   total=11 next=after=107
page 3 [hotel, india, juliet]         total=11 next=None
page 4 []                             total=11 next=None
offset 4 page(s) 11 row(s) 10 unique  1 duplicate(s) short  1 stopped on empty
duplicated: delta   never seen: kilo
```

`kilo` arrived at index 0, which every later page has already passed, so it is **never
seen at all**. Eleven rows for ten repositories, and the output looks like a clean list.

**2 → `if not data: break` is three different facts with one meaning.** An empty page is
the end of the collection, an empty page is a filter that matched nothing, and an empty
body is what a rate limit looks like once the JSON has already been parsed. The loop
treats all three as "finished", so a truncated collection reports success. Notice the
offset walk needs that **fourth empty request** purely to learn it is done.

**3 → `out += data` on a dictionary appends its keys.** When the server answers `403`
with an envelope instead of a list, `+=` does not raise — it extends the list with the
**strings**:

```text
8 row(s): alpha bravo charlie delta message documentation_url india juliet
2 of them are the error body's keys: message, documentation_url
```

Two English words are now rows of a repository list, and the four repositories that
should have been on that page are gone.

**4 → Nothing counts the rows against the total.** Every response carries `total_count`.
Nothing compared it with what was collected, so "we have them all" was an assumption.

**5 → A cursor is the only end signal that means what it says.** `next` is present or it
is not. The same moving list walked by cursor:

```text
page 1 [alpha, bravo, charlie, delta] total=10 next=after=104
page 2 [echo, foxtrot, golf, hotel]   total=11 next=after=108
page 3 [india, juliet]                total=11 next=None
cursor 3 page(s) 10 row(s) 10 unique  0 duplicate(s) short  1 stopped on next
```

No duplicates, no stranded middle items, and the total going 10 → 11 is the honest
statement that the collection **grew while it was being read** — `kilo` is not missing by
accident, it arrived after the walk began.

| | legacy loop | offset walk | cursor walk |
|---|---|---|---|
| pages requested | 4 | 4 | 3 |
| rows returned | 11 | 11 | 10 |
| distinct repositories | 10 | 10 | 10 |
| duplicate rows | 1 (`delta`) | 1 (`delta`) | **0** |
| saw `kilo` | no | no | no, and says so |
| a `403` adds | 2 string rows | refused | refused |
| end signal | empty body | empty page | **`next` is `None`** |

The demonstration is offline: one bundled repository list and one repository that arrives
mid-walk. Standard library only: no `requests`, no HTTP client, no API key.

---

# ✨ Features

- `Item` — a repository as an id, a name and a star count, validated and ordered
- `Page` — an explicit **window**: its items, its `total_count`, and its `next` token;
  refuses more items than its page size, and a total smaller than what it holds
- `Page.is_last()` — the one end signal that means what it says
- `Repository` — a deliberately **mutable** server with `page_number()` (offset) and
  `page_after()` (cursor), plus `arrive()` to push a repository onto the head mid-walk
- `Repository.raw_number()` — the body exactly as the wire would carry it, error envelope
  and all, so the legacy loop can be run against it
- `cursor_for` / `id_from_cursor` — `after=104` as a token, and its id, with a refusal for
  anything else
- `offset_walk` / `cursor_walk` — every page kept apart, the reason it stopped recorded
  (`empty`, `next`, `limit`)
- `Walk` — `rows()`, `unique()`, `duplicates()`, `missing()`, `shortfall()`, `complete()`
- `legacy_fetch` — the five legacy lines, executable, `+=` and `if not data` included
- `is_repository_row` — because a legacy row is a dictionary, and a `403` contributes
  strings
- `audit` — ten named checks, every one of them falsifiable by passing a corrupted walk
- CLI: `--repos`, `--per-page`, `--walk`, `--insert`, `--error-page`, `--audit`, `--json`,
  `--quiet`, `--demo`
- 178 passing pytest tests

---

# 📂 Folder Structure

```text
GitHub_Profile_Analyzer/
│
├── src/
│   ├── main.py        # CLI: both walks, one walk, the audit
│   └── pagination.py  # pages, cursors, walks, the legacy loop, the audit
│
├── tests/
│   └── test_pagination.py
│
├── data/
│   └── repos.txt  # ten repositories, and the one that arrives mid-walk
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 08_API_Development/GitHub_Profile_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: both walks over a moving list, and the legacy loop
python src/main.py --demo

# Both walks over a still list, side by side
python src/main.py

# One walk, page by page
python src/main.py --walk offset
python src/main.py --walk cursor

# The interesting case: a repository is pushed after page 1
python src/main.py --walk offset --insert
python src/main.py --walk cursor --insert

# A page size of 5 instead of 4
python src/main.py --walk offset --per-page 5

# Every check (the checks describe the moving list, so an arrival is applied)
python src/main.py --audit

# Both walks as JSON
python src/main.py --json pages.json --insert
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a page size
outside 1-100, a bundle with no arriving repository, a malformed bundle, or a missing file.

---

# ⚙️ How It Works

```text
Repository.page_number(number, per_page)
  └── start = (number - 1) * per_page      <- an OFFSET, not a bookmark
      items[start:start + per_page]

Repository.page_after(token, per_page)
  └── find the repository the token names
      start = its index + 1                <- a BOOKMARK, wherever it moved to
      items[start:start + per_page]

offset_walk(server, per_page)
  ├── page 1, 2, 3 ...
  └── stops when a page comes back EMPTY   <- ambiguous

cursor_walk(server, per_page)
  ├── page 1, then `next`, then `next` ...
  └── stops when `next` is None            <- unambiguous
```

Details worth knowing:

- **An offset is a position; a cursor is a place in the data.** When the list changes,
  an offset points at different data and a cursor still points after the same repository.
  That single difference is the whole lab.
- **The offset walk needs one request more than it has pages.** The last full page offers
  a `next`, so only an empty page can end the walk — `8 repositories at 4 per page` takes
  three requests, and the third is empty. A cursor walk of the same eight takes two.
- **A duplicate is worse than a gap in a report.** The eleven rows look complete; nothing
  in the output says `delta` is there twice or that `kilo` is missing. `Walk.duplicates()`
  and `Walk.missing()` are the two questions the legacy loop never asked.
- **`total_count` is the only witness that the list moved.** `totals == (10, 11, 11)`
  says the collection grew between page 1 and page 2 — which is a fact about the data,
  not about the code, and it deserves to be printed.
- **The cursor walk is short by one, and that is correct.** `kilo` arrived after the walk
  started, so a walk that claims to have read "the collection as of the first request"
  should not contain it. The difference between "short because it arrived late" and "short
  because the offset skipped it" is the duplicate.
- **A dictionary is not a list of its values.** `out += data` with a `dict` extends with
  the keys, so an error envelope becomes rows rather than an exception. Type-checking every
  row is what makes that visible.
- **A broken walk is a `FAIL`.** Every check runs behind a guard, because a negative control
  hands in a `Walk` that is wrong in exactly the way the check is looking for.

---

# 🧪 Technologies

- Python 3 standard library: `json`, `dataclasses`, `pathlib`, `argparse`, `contextlib`
- pytest 9.1.1

No `requests`, no HTTP client, no network, no API key.

---

# 📚 Concepts Covered

- Offset pagination and why it duplicates and strands rows when the list mutates
- Cursor pagination, and a `next` token as the only honest end signal
- The ambiguity of "an empty response means the end"
- `total_count` as evidence that the collection changed under the walk
- `+=` on a dictionary, and an error envelope becoming rows
- A page as an explicit window with a size, a total and a next
- Detecting duplicates and gaps by comparing rows against the total
- Audits where the negative control is a corrupted value, not an injected function

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**178 tests passed** covering `Item` construction and its seven refusals, cursor tokens and
their three refusals, `Page` construction, lines and six refusals, the server's offset and
cursor windows, `arrive()`, raw bodies and the error envelope, `Walk` counts, duplicates,
shortfalls and three refusals, both walks over a moving list and a still one, the extra
empty request offset pagination needs, the legacy loop and its string rows, the bundle
parser and its eight errors, ten audit checks each with a negative control, the demo, and
every CLI mode including five exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Explain why `?page=2` duplicates a row when an item is inserted at the head
- Explain why the item inserted at the head is never seen by a later page
- Replace a page number with a cursor and say what that changes
- Treat `next` as the only end signal, and an empty page as ambiguous
- Compare rows collected against `total_count` to detect a list that moved
- Recognise `out += data` on a dictionary as a type error that does not raise
- Report "short because it arrived late" differently from "short because we skipped it"

---

# 🚀 Future Improvements

- A `Link` header parser, so `next` comes from the wire as GitHub sends it
- An ETag or `If-None-Match`, so an unchanged page costs nothing
- A merge of two walks, so the newest items can be read without re-reading the tail
- A retry policy for the `403` envelope, reusing the retry lab from `REST_API_with_FastAPI`
- A rate-limit budget, so a walk can be paused and resumed from its cursor

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
