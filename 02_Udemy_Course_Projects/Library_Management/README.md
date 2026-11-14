<div align="center">

# 📚 Library Management

### The course version stored books in a fixed-width binary file with a `float32` price. `19.99` came back as `19.989999771118164`, a long title vanished without a warning, and deleting one book could delete a different one — because `readlines()` on a binary file splits on byte `10`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Storage](https://img.shields.io/badge/Storage-JSON%20%2B%20integer%20cents-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Two files: a menu, and a "book manager" that wrote `struct` records.

```python
FORMAT = "i30s20sf"                  # id, title[30], author[20], price(float32)

def pack_record(book_id, title, author, price):
    title = title.strip().encode()[:30].ljust(30)
    author = author.strip().encode()[:20].ljust(20)
    return struct.pack(FORMAT, book_id, title, author, price)

def delete_book():
    ...
    with open(FILE_NAME, "rb") as file:
        records = file.readlines()   # on a BINARY file
    with open(FILE_NAME, "wb") as file:
        for record in records:
            if len(record) != RECORD_SIZE:
                continue             # silently drop it
```

Five defects, and each one is a separate lesson.

**1 · A price is not a float.** `struct` packs a 4-byte IEEE-754 single. `19.99` is not exactly representable, so it comes back as `19.989999771118164`. Displaying it with `:.2f` hides that, but any equality test or sum drifts. Money is an integer number of cents.

**2 · Titles are sliced by byte, not by character.** `title.encode()[:30]` cuts UTF-8 in the middle of a code point. A title of accented text stores bytes that `.decode()` refuses — `pack` succeeds, and the corruption is already on disk when `unpack` raises.

**3 · Truncation is silent.** A 57-character title becomes 30 characters, and the other 27 are gone without a message. Fixed-width formats cannot represent what they cannot fit; they should say so.

**4 · `readlines()` on a binary file splits on `0x0A`.** That is byte 10 — a perfectly ordinary value inside a 4-byte integer or a 4-byte float. One record containing it becomes two short chunks. `delete_book` skips every chunk whose length is not exactly `RECORD_SIZE`, so deleting book 99 can silently remove book 10.

**5 · Append never checks ids.** `open(FILE_NAME, "ab")` writes a second record with the same id, and the delete loop then removes both.

The replacement is a JSON catalogue with integer cents:

```json
{
 "books": [
  {"isbn": "978-0132350884", "title": "Clean Code",
   "author": "Robert C. Martin", "price_cents": 4250,
   "copies_total": 2, "copies_available": 2}
 ],
 "loans": [
  {"isbn": "978-0201616224", "member": "asha",
   "borrowed_on": "2024-03-20", "due_on": "2024-04-03",
   "returned_on": null}
 ]
}
```

**Availability is derived, then verified.** `copies_available` is stored, because a book can legitimately be on the shelf or out, but `audit()` recomputes it from the open loans:

```text
copies_total - copies_available  ==  number of open loans for that isbn
```

A hand-edited file that claims a copy is on the shelf while a loan says otherwise produces a problem string rather than a wrong answer.

**Fines are 25 cents per day, capped at 10.00.** They are charged on return, and *projected* to today while a loan is still open — so an overdue loan has a fine you can quote without inventing a return date.

**Dates are validated by round trip.** `strptime("2024-4-5", "%Y-%m-%d")` succeeds, so the module re-renders the parsed date and compares. Only zero-padded ISO dates are accepted.

**The demo proves every defect rather than describing it:** the float32 mangling, a 30-byte slice that cannot decode, a long title cut silently, an id of 10 whose record contains `0x0A` and is therefore split in two and dropped on delete (while a healthy neighbour survives), and two appended records with one id. Then it verifies the replacement: 4 bad prices and a duplicate ISBN refused, borrowing refused on an empty shelf / for the same member / for an unknown ISBN, returns charging `0.00` and `1.25` and refusing a second return, a 138-day loan capped at `10.00`, a byte-identical save/reload with a clean audit, and the 6-book bundled catalogue agreeing with its own loans.

Standard library only, no files written outside a temporary directory.

---

# ✨ Features

- `parse_money` / `format_money` — exact integer cents, two decimal places enforced, thousands separators
- `parse_date` — strict `YYYY-MM-DD` via parse-and-render
- `legacy_pack` / `legacy_unpack` / `legacy_readlines_split` / `legacy_delete_keeps` — the original format, reproduced
- `Book` — frozen dataclass; ISBN uniqueness, copies range, non-negative price
- `Loan` — borrowed/due/returned dates, `days_late`, `fine_cents` with a cap
- `Catalog` — add, remove, search, borrow, give back, overdue, member loans
- `Catalog.audit` — recomputes availability from the loans and reports contradictions
- `Catalog.save` / `load` — sorted JSON, atomic replace, line-numbered-free but precise errors
- `stats` — books, copies, available, on loan, members, overdue, outstanding fines
- `data/catalog.json` — 6 books, 8 copies, 5 loans (3 open, 2 overdue)
- CLI: `--borrow`, `--return`, `--search`, `--loans`, `--overdue`, `--stats`, `--write`, `--legacy`, `--json`, `--quiet`
- Exit `2` on a `LibraryError`; `--demo` always returns `0`
- 159 passing pytest tests

---

# 📂 Folder Structure

```text
Library_Management/
│
├── src/
│   ├── main.py      # CLI: list, search, loans, overdue, borrow, return
│   └── library.py   # money, dates, Book, Loan, Catalog, legacy format
│
├── tests/
│   └── test_library.py
│
├── data/
│   └── catalog.json # 6 books and 5 loans
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/Library_Management

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: five legacy defects, then the catalogue
python src/main.py --demo

# The bundled catalogue
python src/main.py

# Counts and fines
python src/main.py --stats
python src/main.py --overdue

# Look things up
python src/main.py --search clean
python src/main.py --loans asha

# Lend a copy (measured against a fixed date), then persist
python src/main.py --borrow 978-0132350884:asha --today 2024-04-16 --write

# Take it back and see the fine
python src/main.py --return 978-0132350884:asha --today 2024-04-30 --write

# The legacy format, printed
python src/main.py --legacy
```

**Catalogue format** (`data/catalog.json`) — `books` keyed by unique ISBN, `loans` in insertion order. Prices are integer cents, dates are ISO strings, `returned_on` is `null` for an open loan.

**Exit codes:** `0` = the command ran · `2` = unknown ISBN, unavailable copy, duplicate loan, duplicate ISBN, bad price, bad date, malformed argument or a missing catalogue.

---

# 🧠 How It Works

```text
data/catalog.json
   │
   ▼
load()  ──►  Book.from_dict / Loan.from_dict  ──►  validation
   │         price_cents >= 0, 0 <= available <= total
   │         due_on > borrowed_on, returned_on >= borrowed_on
   ▼
Catalog
   ├── borrow()      available -= 1, due = today + 14 days
   ├── give_back()   available += 1, fine = min(days_late * 25, 1000)
   ├── overdue()     open loans with due_on < today
   └── audit()       copies_total - available == open loan count
```

Details worth knowing:

- **Why `float32` and not `float64`?** The legacy format used `f`, four bytes. Even `float64` would be wrong for money — `0.1 + 0.2 != 0.3` — but the single-precision version is dramatically visible, which is why the demo can quote the exact digits.
- **The `0x0A` bug is a data-dependent bug.** It only fires when a record contains byte 10, which means it can sit in production for months and then delete the wrong book. That is why the demo constructs `legacy_pack(10, ...)` deliberately.
- **`copies_available` is stored but checked.** Storing it makes borrowing O(1); recomputing it in `audit()` means a bad hand edit is caught instead of trusted.
- **A member cannot hold two copies of the same title.** Enforced in `borrow`, so the availability arithmetic and the loan list cannot drift.
- **Fines are projected, not invented.** `fine_cents(today)` uses `returned_on` when it exists and `today` otherwise, so an open overdue loan has a quote-able fine with no fake return date.
- **The save is a replace.** `mkstemp` in the target directory, write, `os.replace`, so a crash leaves the previous catalogue intact.

---

# 🛠 Technologies

- Python 3 standard library: `struct`, `json`, `datetime`, `decimal`, `dataclasses`, `os`, `tempfile`, `argparse`, `pathlib`
- pytest

No database, no ORM, no network.

---

# 📚 Concepts Covered

- Fixed-width binary records and their three failure modes
- IEEE-754 single precision and why money must not use it
- Byte slicing versus character slicing in UTF-8
- `readlines()` semantics on binary files, and the `0x0A` collision
- Silent truncation versus a refused write
- Derived state plus a consistency audit
- Integer cents for money and exact decimal parsing
- Fine caps and projecting a charge before it is realised
- Atomic file replacement
- Strict date formats by parse-and-render round trip
- Uniqueness enforcement at the boundary

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**159 tests passed** covering money parsing (string, float, integer units, whitespace, seven refused values, booleans and negatives) and formatting (padding, thousands, signs, non-integers), date parsing (three accepted types, five refused shapes), the legacy format (record size, float mangling, short and long titles, a mid-character UTF-8 cut, a valid UTF-8 title, `0x0A` splitting, the delete loop dropping chunks and removing the requested id, duplicate ids), `Book` and `Loan` validation and dict round trips, catalogue operations (add, duplicate, remove with loans, search across three fields, borrowing limits, returning with and without a fine, overdue ordering and the due-date boundary, member loans), `audit` for three contradiction types, storage (round trip, byte-identical rewrite, no temporary files, directory creation, six malformed files), the bundled catalogue's exact statistics, rendering, demo determinism, and every CLI mode including `--write`, `--legacy` and quiet.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
