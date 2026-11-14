<div align="center">

# 🎓 Udemy Course Projects

### Eleven exercises from a Python course, each taken past the point where the lesson stopped. The lesson code is kept, verbatim, inside the demo that proves what it gets wrong — a backwards equality test that prints "Password Changed" when nothing changed, a `break` outside a loop, an `isalpha` without parentheses, a `'-' * -7`, and `find()` returning `-1` into a slice.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-11-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

These are the projects a course gives you to practise strings, dicts, files and SQL. The interesting part is not the exercise — it is what the short solution silently does when the input is not the one in the video. Every project here starts there.

**The course code is kept as evidence, not as history.** Where a defect is worth proving, the original source is a documented string constant in the module, and the demo runs it:

- **Journal_Manager** keeps the legacy file verbatim and calls `compile()` on it, because a `break` outside a loop is a `SyntaxError` — the program never ran at all. Its search message sat in a `for`/`else`, which runs when the loop finishes *without* a `break`, so "No entries found" printed after every search, successful ones included.
- **Data_Cleaning** keeps `if i.isalpha or i.isspace()` and `clean + 1`. The first is true for every character because a bound method is truthy, so the filter passes everything through; the second is a `TypeError` that the first bug hides, because the `else` branch is never reached.
- **Password_Checker** keeps `if pwd1 == pwd2: print("Password Changed")`. The test is backwards: it reports success for exactly the case it should reject, and accepts a single character.
- **URL_Parsing** keeps the three `find()` slices. `find` returns `-1`, and `-1` is a legal slice index, so `www.kaggle.com` becomes `kaggle`, `example.com` becomes `co` with `page` = the letter `m`, and `http://localhost:8000` becomes the whole "domain".
- **Restaurant_Menu** keeps `20 - len(dish) - len(str(price))`, where `'-' * -7` is `''` and `len` is not display width.

Where the defect is a design, the replacement is the design:

- **Anagrams** compares *multisets*, and the one-directional `S1.count(ch)` loop called pairs anagrams when `S1` simply had fewer of some letter. Sorting into a signature turns grouping into a dictionary lookup.
- **Bank_DB_Using_SQLite** removes `accounts.balance` and derives the balance from the ledger (`opening + SUM(amount_cents)`), so a stale balance is not a bug to avoid — it is a number that cannot exist. Transfers are two signed rows in one `BEGIN IMMEDIATE` transaction, and money is integer cents.
- **Card_Payment** replaces a hard-coded sixteen-`X` prefix with a real mask: Luhn, brand, length policy per brand, and a redaction whose length matches the number. `"123"[-4:]` is `"123"`, and the legacy program printed short input in full.
- **Library_Management** replaces `struct` over a flat binary file — where `readlines()` on a binary handle and a `len(record) != RECORD_SIZE` skip quietly delete books — with a JSON catalogue, a loan model, and fines in integer cents.
- **Patient_Entry_System** replaces the PySpark loader with strict CSV: a header that ends in a tab is seven names, an Excel serial is not a date, and serial 60 is the 29th of February 1900, which did not exist.
- **Palindrome** replaces `S1.replace(' ', '')` with normalisation that removes punctuation too, because the comma and colon break the mirror, not the sentence.

Every project runs on bundled data, prints a `Cross-checks OK` line naming what was actually verified, exits `0`, and has a `--demo --quiet` mode that prints nothing at all.

---

# 🎯 Learning Objectives

- Read a short script and list the inputs it silently mishandles
- Keep the original source as an executable constant instead of describing it
- Tell a compile-time failure from a runtime one, and prove which happened
- Recognise a bound method used as a boolean, and why it is always true
- Explain why `for`/`else` runs when nothing is found, and what `break` changes
- Compare multisets instead of comparing characters one way
- Derive state from an append-only ledger rather than storing it twice
- Prove the two representations agree with an `audit` that returns every check
- Validate a card number with Luhn and select the length policy from the brand
- Redact output so the redaction is the same width as the number it hides
- Parse money as integer cents and keep floats out of the ledger
- Distinguish a binary file from a text file, and what `readlines()` does to each
- Decode Excel serial dates, including the 1900 leap-year fiction
- Normalise text before comparing it, and keep the original for display
- Compute display width from combining marks and East Asian width
- Parse a grammar instead of slicing between the first two dots

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Anagrams | Multiset signatures, grouping, pair search, one-directional legacy comparison. | ✅
02 | Bank_DB_Using_SQLite | SQLite schema, derived balances, two-leg atomic transfers, six-check audit. | ✅
03 | Card_Payment | Luhn, brand detection, per-brand lengths, width-matched masking, CSV batch. | ✅
04 | Data_Cleaning | Legacy filter that never ran, text cleaning, CSV row normalisation, scan report. | ✅
05 | Journal_Manager | JSON Lines journal, tags, search, three legacy syntax/runtime defects. | ✅
06 | Library_Management | Catalogue, copies, 14-day loans, capped fines, atomic save, binary legacy. | ✅
07 | Palindrome | Normalised checks, shortest completion, longest run, mirror strings. | ✅
08 | Password_Checker | Policy object, seven finding codes, leet skeleton, entropy bound, score. | ✅
09 | Patient_Entry_System | Strict CSV, Excel serials, duplicate reporting, age summary, legacy file. | ✅
10 | Restaurant_Menu | Integer-cent prices, display width, guaranteed dot leaders, taxed cart. | ✅
11 | URL_Parsing | Hand-written RFC 3986 parser, percent decoding, query pairs, normalise. | ✅

---

# 💡 Concepts Covered

- Multisets and canonical signatures
- One-directional comparisons and why they accept too much
- Frozen dataclasses as self-validating records
- SQL schemas, foreign keys and `UNIQUE` constraints
- Derived state versus duplicated state
- Atomic multi-row transactions with `BEGIN IMMEDIATE`
- Integer cents and per-row rounding drift
- Luhn checksums and brand-specific length policies
- Redaction width as a security property
- Bound methods used as booleans, and unreachable `else` branches
- Compile-time versus runtime failure, shown with `compile()`
- `for`/`else` and the meaning of `break`
- JSON Lines as an append-only store
- Fixed-width binary records and `struct`
- `readlines()` on a binary handle, and silent record loss
- Excel serial dates, the 1900 leap-year fiction, and the serial-60 offset
- Strict CSV headers, line-numbered errors, duplicates reported not dropped
- Text normalisation versus display
- Combining marks, East Asian width, and dot leaders
- The URL grammar, percent escapes, and bracketed IPv6 literals
- Query strings as ordered pairs rather than a dict

---

# 📁 Repository Structure

```text
02_Udemy_Course_Projects/
│
├── Anagrams/
├── Bank_DB_Using_SQLite/
├── Card_Payment/
├── Data_Cleaning/
├── Journal_Manager/
├── Library_Management/
├── Palindrome/
├── Password_Checker/
├── Patient_Entry_System/
├── Restaurant_Menu/
├── URL_Parsing/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library module
├── tests/            # pytest test suite
├── data/             # bundled deterministic data
├── README.md
├── requirements.txt
└── .gitignore
```

Two projects keep a second data file on purpose: `Patient_Entry_System/data/legacy_patients.csv` is the original file byte for byte (header ending in a tab, Excel serial dates), and `Data_Cleaning/data/messy.csv` is the messy input the cleaner is tested against.

---

# 🛠 Technologies

- Python 3 standard library: `re`, `csv`, `json`, `sqlite3`, `struct`, `dataclasses`, `decimal`, `datetime`, `unicodedata`, `tempfile`, `pathlib`, `argparse`, `contextlib`
- `urllib.parse.urlsplit` and `parse_qsl`, used as the reference the hand-written parser is tested against
- pytest 9.1.1

No third-party runtime dependencies, no Spark, no database server, no network access.

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Anagrams | ✅ |
| Bank DB Using SQLite | ✅ |
| Card Payment | ✅ |
| Data Cleaning | ✅ |
| Journal Manager | ✅ |
| Library Management | ✅ |
| Palindrome | ✅ |
| Password Checker | ✅ |
| Patient Entry System | ✅ |
| Restaurant Menu | ✅ |
| URL Parsing | ✅ |

**Completed:** **11 / 11 Projects** · 1,488 passing tests

---

# ▶️ Quick Start

```bash
cd 02_Udemy_Course_Projects/Restaurant_Menu

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

Each project follows the same shape: `python src/main.py --demo` for a self-checking offline run, `python -m pytest tests/ -q` for the suite, and `--quiet` to silence both. Every project also exposes its subject on the command line:

```bash
cd 02_Udemy_Course_Projects/URL_Parsing
python src/main.py --parse "https://user@example.com:8443/a?b=1#c"
python src/main.py --legacy "https://example.com"     # 'co' and page 'm'

cd ../Restaurant_Menu
python src/main.py --order "Margherita Pizza:2" --order Lemonade
python src/main.py --legacy "Slow-roasted lamb shoulder:24"   # no gap at all
```

---

# 📚 Skills Developed

- Auditing a short script for the inputs it mishandles, before rewriting it
- Preserving original source as an executable constant so a defect can be asserted
- Turning a demonstration into a falsifiable check with a negative control beside it
- Choosing derived state over stored state, and proving the two agree
- Designing a transaction so a partial write cannot leave a valid-looking balance
- Making money exact end to end: parse, store, compute, render
- Redacting output without changing its width
- Telling a compile error from a runtime error by compiling rather than hoping
- Recognising `for`/`else` misuse and bound-method truthiness on sight
- Writing strict parsers that refuse bad input instead of repairing it silently
- Reporting duplicates instead of dropping them, so a data problem stays visible
- Building fixed-width reports from display width rather than `len`
- Implementing a grammar from the specification, then cross-checking it against a reference library
- Writing 73–179 pytest cases per project, including every error message and CLI flag

---

# 🚀 Key Learning Outcomes

- Show that a backwards equality test accepts a one-character password, and design a policy that scores instead
- Show that a `break` outside a loop is a `SyntaxError`, and that the legacy journal never started
- Show that `i.isalpha` is truthy for every character, and that it hid a `TypeError` behind it
- Show that `'-' * -7` is `''`, and that `len("Cafe\u0301")` is 5 while it prints as 4 columns
- Show that `find()` returning `-1` turns `example.com` into `co` and gives `page` the letter `m`
- Store a bank ledger so the balance cannot disagree with it, and audit six invariants
- Mask a card so the wrong number is caught by Luhn before it is stored
- Load a patient file written by a spreadsheet, including a date that never existed
- Parse URLs without a regex, and match `urlsplit` on all twenty bundled cases

---

# 🔮 Future Enhancements

- A property-based suite (Hypothesis) that compares the URL parser with `urlsplit` on generated inputs
- Import and export for the bank ledger in a standard format such as OFX
- Card BIN ranges as data, so brands can be updated without touching code
- A journal index so search does not read the whole file
- Reservation queues and renewals for the library
- Full `wcwidth` behaviour in the menu, including emoji sequences and control characters

---

# 🤝 Contributions

Contributions, issues and feature requests are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this category useful, consider giving this repository a star.

</div>
