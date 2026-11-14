<div align="center">

# 📚 Library Management System

### The legacy project stored *one fact* in three columns — `quantity`, `available` and an `issued` boolean — and recomputed `available = max(quantity - issued, 0)` on every edit. Four copies out of five, then "correcting" the quantity to three, silently loses a copy: the record can only account for three loans while four are still open, and it stays one copy behind for ever.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old model was four columns and a service method that kept them roughly
agreeing:

```python
issued = Column(Boolean, default=False)

def issue_book(self, book_id):
    book.available -= 1
    if book.available != book.quantity:
        book.issued = True

def update_book(self, book_id, title, author, isbn, quantity):
    issued = book.quantity - book.available
    book.quantity = quantity
    book.available = max(quantity - issued, 0)
```

**1 · `issued` is a stored copy of a derivable fact.** It is recomputed on every
issue and return, so it is only as correct as the last write — and any code path
that forgets to recompute it leaves the flag lying.

**2 · `max(quantity - issued, 0)` destroys information.** Own five copies, have
four out, "correct" the quantity to three: `available = max(3 - 4, 0) = 0`.
Four copies are still out, but the record can only account for three. Each later
return moves `available` up by one, so the record is permanently one copy behind
the shelf.

**3 · `available` is unchecked.** It is a free integer, so `available > quantity`
and negative copies are both storable.

**4 · `validate_isbn` was `len(value.strip()) >= 5`.** `abcde` was an ISBN.

The replacement removes the second copy of every number.

**Availability is computed.** `Book` holds one number — how many copies the
library owns — and `Library` counts the open loans. `available(isbn)` is
`copies - open_loans`, `issued(isbn)` is `open_loans > 0`. There is no column to
fall out of date, so a flag cannot drift.

**A loan is a value with a due date it cannot fake.** `Loan.of(isbn, member,
day)` is the only way to start one, and `__post_init__` refuses any loan whose
`due` is not exactly `LOAN_DAYS` (14) after `borrowed`. Returning a book produces
a **new** `Loan` with `returned` filled in, so history is a value rather than a
mutation.

**`copies` is a property with a validating setter.** It refuses floats,
booleans and negatives; `Library.set_copies` refuses a shrink below the number
on loan, naming the loans that would be broken. That is the clamp, replaced by a
refusal.

**A class attribute is not per instance.** The mirror-image bug is one line
away:

```python
class LibraryService:
    books = []          # one list, shared by every instance
```

`first.books.append(...)` changes `second.books`, because lookup finds the class
object before the instance namespace. `shared_shelf()` in this module reproduces
it on purpose, and every `Library` builds its own dictionaries in `__init__`.

**The ISBN is checked, not measured.** ISBN-10 (mod 11, with `X` as ten) and
ISBN-13 (mod 10, alternating weights) are both validated, with hyphens and
spaces normalised away first.

Standard library only: no ORM, no database file, no network.

---

# ✨ Features

- `normalise_isbn` / `isbn_is_valid` / `isbn_kind` — real ISBN-10 and ISBN-13 checksums, `X` supported
- `legacy_isbn_ok` — the original five-character test, reproduced so the demo can prove it wrong
- `Member` — id, name, a loan limit, frozen
- `Loan` — borrow date, derived due date, optional return date; `days_late`, `fine`, `returned_on`
- `Book` — validated ISBN, `copies` as a property with a checking setter
- `Library` — books, members, loans; `available`, `on_loan`, `issued` all computed
- `borrow` — refuses an empty shelf, a duplicate loan, and a member over their limit
- `give_back` — closes the loan and returns the fine that was owed
- `overdue` / `fines` / `total_fine` — integer cents, `FINE_PER_DAY = 25`
- `set_copies` / `remove_book` — refuse to lose a loan
- `consistency` — five named invariants, each reported pass or fail
- `shared_shelf` and the transcribed `legacy_*` functions — the defects, kept executable
- `data/library.json` — 6 titles, 10 copies, 3 members, 5 loans (4 open), one 4 days late
- CLI: `--books`, `--search`, `--available`, `--member`, `--borrow`, `--return`, `--overdue`, `--fines`, `--on`, `--add-book`, `--copies`, `--consistency`, `--legacy`, `--write`, `--json`, `--quiet`
- Exit `2` on a `LibraryError`; `--demo` always returns `0`
- 301 passing pytest tests

---

# 📂 Folder Structure

```text
Library_Management_System/
│
├── src/
│   ├── main.py     # CLI: shelf, search, borrow, return, overdue, fines
│   └── library.py  # ISBNs, Member, Loan, Book, Library, the demo
│
├── tests/
│   └── test_library.py
│
├── data/
│   └── library.json  # 6 titles, 10 copies, 5 loans
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 03_Object_Oriented_Programming/Library_Management_System

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# The shelf: copies owned and copies out
python src/main.py

# Find a title
python src/main.py --search crockford
python src/main.py --search "martin fowler"

# One title, one reader
python src/main.py --available 9780596517748
python src/main.py --member M-01

# Lend and take back
python src/main.py --borrow 9780306406157:M-03:2026-03-10
python src/main.py --return 9780596517748:M-02:2026-03-10

# Who is late, and what they owe
python src/main.py --overdue --on 2026-03-10
python src/main.py --overdue --on 2026-03-20
python src/main.py --fines --on 2026-03-20

# Change the shelf
python src/main.py --add-book 9780262033848:CLRS:Thomas Cormen:2
python src/main.py --copies 9780132350884:4

# The five invariants
python src/main.py --consistency

# What the legacy model did
python src/main.py --legacy
```

**Exit codes:** `0` = the command ran · `2` = an unknown book or member, a bad
ISBN, an empty shelf, a duplicate loan, a member over their limit, a shrink
below the loans, a missing loan, a bad date, a malformed spec, or a missing data
file.

---

# 🧠 How It Works

```text
 normalise_isbn    strip hyphens, then prove the checksum
   ├── ISBN-10     sum((10-i) * digit) % 11 == 0, X counts as 10
   └── ISBN-13     sum(digit * (1 or 3)) % 10 == 0

 Loan (frozen)     borrowed + LOAN_DAYS -> due, checked in __post_init__
   ├── of()        the only way to start one
   ├── returned_on a NEW loan with `returned` set
   └── days_late / fine    0 on the due date, 25 cents a day after

 Book
   └── copies      a property: int, not bool, not negative

 Library
   ├── _books      isbn -> Book
   ├── _members    id -> Member
   ├── _loans      a list of Loan values
   ├── available() copies - open loans        <- computed, never stored
   ├── issued()    open loans > 0             <- computed, never stored
   ├── borrow()    refuse empty shelf, duplicate loan, over limit
   ├── set_copies() refuse a shrink below the loans
   └── consistency()  5 invariants
```

Details worth knowing:

- **The due date is not a parameter.** `Loan.of` adds `LOAN_DAYS` itself, and the
  constructor refuses any other due date, so a hand-written loan cannot claim a
  longer window. The error names the date it wanted.
- **A fine starts the day after the due date.** Returning on `2026-03-24` costs
  nothing; returning on the 25th costs 25 cents. Both are pinned in the demo.
- **A returned loan judges itself.** `days_late()` with no argument uses
  `returned`, so the fine is fixed at the moment of return and does not grow
  while nobody looks at it.
- **The duplicate check comes before the limit check.** Borrowing the same title
  twice is a precise complaint ("already has ... on loan"), not a vague one about
  the limit.
- **`set_copies` may shrink to exactly the number on loan.** That is legal —
  every copy is out — and only a shrink *below* the loans is refused.
- **`remove_book` refuses a title that is on loan**, because deleting the row
  would orphan the loan.
- **`consistency` catches what the constructor cannot.** `available` cannot be
  wrong by construction, but a loan appended past a limit, a loan naming a
  deleted member, or a hand-edited due date are all checkable, and the demo
  forces one to prove the check is real.
- **The shared list is reproduced, not just described.** `shared_shelf()`
  returns a fresh class, so the demo and the tests can show the leak without
  leaving state behind.

---

# 🛠 Technologies

- Python 3 standard library: `dataclasses` (frozen), `datetime`, `json`,
  `pathlib`, `argparse`, `contextlib`, `tempfile`
- pytest 9.1.1

No ORM, no database file, no network.

---

# 📚 Concepts Covered

- Derived state versus stored state: why a cached flag drifts
- The clamp that loses information, and a refusal that preserves it
- Properties with validating setters
- Frozen dataclasses as immutable records and history
- Class methods as named constructors (`Library.empty`, `Loan.of`)
- Class attributes versus instance attributes, and the shared-mutable-default bug
- ISBN-10 and ISBN-13 checksums
- Dates as values: half-open windows, due dates, fines in integer cents
- Invariants with a negative control for each

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**301 tests passed** covering date parsing (canonical, objects, seven bad
shapes, the 30th of February, booleans, datetimes, labels), `check_whole` and
`money`, ISBNs (13, 10, `X`, hyphens, spaces, seven bad checksums, the legacy
test), `Member` (limits, four refusals, frozen, trimming, three `from_dict`
refusals), `Loan` (the 14-day rule, six constructor refusals, `days_late` on and
after the due date, fines, `returned_on` twice, five `from_dict` refusals,
`str`), `Book` (normalisation, four refusals, the copies setter in three
shapes, round trip, three `from_dict` refusals), the shared class attribute in
three shapes, the legacy record in five shapes (including the drift), the
library's protocols and handles, `add`/`remove`/`set_copies`/`search`,
`borrow` (ten refusals and the limit boundary), `give_back`, `overdue`,
`fines`, the five consistency checks and six ways to fail them, persistence
(eight `from_dict` refusals, save idempotence), the seeded file (twelve pinned
facts), the demo, and every CLI mode including `--on`, `--json`, `--write` and
`--quiet`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
