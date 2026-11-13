<div align="center">

# 📇 Contact Book

### A validated address book: immutable records that refuse bad emails and phones, a repository that keeps its indexes honest, AND-search, two merge policies, and lossless JSON/CSV round-trips.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Database-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

An address book looks like a `dict` with a `save()` method until the first real contact arrives: a phone number typed as `+351 912-345 678`, an email with a stray space, the same person entered twice under two spellings. This project puts the decisions where they belong — in the record — and then makes the repository keep its three promises: unique ids, unique emails, and a search that means what it says.

**A record that validates itself.** `Contact` is a frozen dataclass, so `__post_init__` is the only way in and there is no way to write an invalid field afterwards:

| Field | Rule | Rejected example |
| --- | --- | --- |
| `name` | non-empty, whitespace collapsed, ≤ 60 chars | `"   "` |
| `email` | exactly one `@`, domain must contain a dot, lower-cased | `"ana@"`, `"two@@example.com"` |
| `phone` | separators stripped, 7–15 digits, optional leading `+` | `"12-34"` |
| `tags` | lower-cased, de-duplicated, letters/digits/`-` | `"Bad Tag!"` |

Normalisation happens once, on the way in:

```text
"+351 912-345 678"  ->  "+351912345678"
"(21) 98765-4321"   ->  "21987654321"
" ANA@Example.COM " ->  "ana@example.com"
["Work", "work"]    ->  ("work",)
```

**A repository with two indexes.** `ContactBook` keeps `_contacts` by id *and* `_emails` by address, and every write updates both. That is what makes the two conflict messages possible — and why `update("C-002", email="ana.silva@example.com")` fails with `email 'ana.silva@example.com' is already used by C-001` instead of quietly leaving a dangling index entry.

```text
C-001  Ana Silva      ana.silva@example.com       +351912345678
C-006  Ana Ferreira   ana.ferreira@example.com    967654321
```

**Search is AND, not OR.** `search("ana lisbon")` returns one contact, `search("ana nowhere")` returns none, and `--tag work` narrows rather than widens. Every term is matched against name, email, phone, company and tags in one case-folded haystack.

**Merge has an explicit policy.** `prefer-existing` keeps your values and counts the duplicate as `unchanged`; `prefer-incoming` takes the other book's non-empty values and unions the tags:

```text
prefer-existing -> {'added': 1, 'updated': 0, 'unchanged': 1, 'skipped': 0}
prefer-incoming -> {'added': 1, 'updated': 1, 'unchanged': 0, 'skipped': 0}
tags: ('friend', 'lisbon') + ('new',) -> ('friend', 'lisbon', 'new')
```

An unknown policy is refused *before* anything is written, so a typo cannot half-merge a book.

**Everything in the demo is falsifiable.** It asserts the six seed contacts and their normalised phones, that ids continue at `C-007`, that five invalid updates are rejected *and leave the book the same size*, that duplicate email and duplicate id both conflict, six search queries with exact result ids, that updates re-validate, both merge policies with exact counts, that an unknown policy changes nothing, that JSON and CSV round-trips are lossless, that `remove` is undone by `add`, and that loading the seed twice gives the same result.

No database, no network, no ORM.

---

# ✨ Features

- Immutable, self-validating `Contact` record (`frozen=True`) that normalises name, email, phone and tags
- Email validation with specific messages (`exactly one '@'`, `not a valid address`, `contains a space`)
- Phone normalisation to digits with an E.164-style 7–15 digit bound
- Tag cleaning: lower-case, de-duplicated, character-checked
- Repository with dual indexes (by id and by email) and sequential `C-001` ids
- `add` / `create` / `get` / `by_email` / `update` / `remove` / `clear` / `all`
- `update` re-validates through the frozen record and rolls nothing back on failure
- Duplicate id and duplicate email both raise `ConflictError`
- AND-search across name, email, phone, company and tags, plus `tag` and `company` filters
- Two merge policies with an exact `{added, updated, unchanged, skipped}` report
- JSON load/save and CSV import/export (tags joined with `;`)
- Indexed error messages for bad files (`contact 1: ...`, `row 2: ...`)
- CLI with `--search`, `--tag`, `--company`, `--add`, `--merge`, `--policy`, `--export-csv`, `--save`, `--json`, `--quiet`
- Exit `0` on success, `2` on any contact/file error
- `--demo` and `--quiet` (prints nothing)
- 102 passing pytest tests

---

# 📂 Folder Structure

```text
Contact_Book/
│
├── src/
│   ├── main.py       # CLI: search, add, merge, export
│   └── contacts.py   # Contact, ContactBook, validation, demo
│
├── tests/
│   └── test_contacts.py
│
├── data/
│   └── contacts.json   # 6 seed contacts
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 01_Beginner_Level_Projects/Contact_Book

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: validation, search, merge, round-trips, 13 cross-checks
python src/main.py --demo

# List the bundled book
python src/main.py

# Search every term, then narrow by tag
python src/main.py --search "ana"
python src/main.py --search "ana" --tag work

# Add a contact (it is not saved unless you ask)
python src/main.py --add "Gita Patel|gita@example.com|+44 20 7946 0000"

# Merge another file, incoming values win
python src/main.py --merge other.json --policy prefer-incoming --save merged.json

# Export
python src/main.py --export-csv out/contacts.csv
python src/main.py --json out/contacts.json --quiet
```

**Seed format** (`data/contacts.json`):

```json
[
  { "id": "C-003", "name": "Carla Mendes", "email": "carla@example.org",
    "phone": "(21) 98765-4321", "company": "Acme", "tags": ["work", "vip"] }
]
```

**Exit codes:** `0` = the command ran · `2` = invalid contact, duplicate email, unknown policy or unreadable file.

---

# 🧠 How It Works

```text
contacts.json
     │
     ▼
Contact.from_dict()  ──►  __post_init__  ──►  clean_name / clean_email
     │                                        clean_phone / clean_tags
     ▼
ContactBook.add()  ──►  _contacts[id]  +  _emails[email]
     │
     ├── search(query, tag, company)  ──►  AND over one case-folded haystack
     ├── update(id, **fields)          ──►  replace() re-validates, then re-index
     ├── merge(other, policy)          ──►  add or rewrite, with a report
     └── export_csv / save             ──►  tags joined with ';' / JSON list
```

Details worth knowing:

- **`replace()` is the update path.** `dataclasses.replace` builds a new frozen record, which means `__post_init__` runs again — there is no second validation function to drift out of sync.
- **The email index is updated, not rebuilt.** On a successful email change the old key is removed and the new one added; on a rejected change neither happens, because validation runs first.
- **`next_id` scans the ids it loaded.** A book seeded with `C-001..C-006` continues at `C-007` instead of restarting and colliding.
- **Search is one haystack.** Name, email, phone, company and tags are joined and case-folded once per contact, so multi-term queries do not need a field list.
- **CSV uses the `csv` module.** Quoting, embedded commas and CRLF handling are the standard library's problem, not ours.
- **Merge never deletes.** `skipped` exists in the report for policies that drop records, and stays `0` today — an honest placeholder rather than an invented number.

---

# 🛠 Technologies

- Python 3 standard library: `dataclasses`, `re`, `json`, `csv`, `pathlib`, `argparse`, `tempfile`, `contextlib`
- pytest

No SQLite, no ORM, no network access.

---

# 📚 Concepts Covered

- Frozen dataclasses as self-validating value objects
- Normalisation on the boundary (strip, collapse, case-fold)
- Two-index repositories and index consistency on update/delete
- Exception hierarchies: `ContactError` → `ConflictError`, `NotFoundError`
- Validation before mutation, and the "leave the store untouched" guarantee
- Multi-term AND search over a derived haystack
- Merge with an explicit conflict policy and an auditable report
- JSON and CSV serialisation, including round-trip tests
- Indexed error messages for bulk file input
- Self-asserting demos with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**102 tests passed** covering name/email/phone/tag validation and their exact messages, normalisation, immutability, dict round-trips, missing keys, sequential ids, both duplicate conflicts, every repository method, `update` re-validation with an untouched store, the email index after a change, all search combinations, both merge policies and their counts, the no-op merge, unknown policies, JSON and CSV round-trips plus four failure modes with indexed messages, the bundled data file, demo determinism, and every CLI path including `--add`, `--merge` and exit code `2`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
