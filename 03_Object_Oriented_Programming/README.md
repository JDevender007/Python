<div align="center">

# 🏛 Object Oriented Programming

### Five management systems that were CRUD screens over a table, and the one question each of them could not answer. A balance kept in two places, a hotel with no arrival date, a stock level that goes *down* when you add five, one copy of a book stored in three columns, and a CGPA somebody typed — the rebuild keeps each defect executable, then removes the reason it was possible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Each of these five projects began as a tutorial "management system": SQLAlchemy models, a service class, a menu, and CRUD. They all work when the demonstration data is used exactly as the video does. They all fail the moment a real question is asked, and the failure is never a typo — it is the model.

**The lesson of each project is different, on purpose.** Five variations on "a class holds a dict" would teach nothing; five different ways a model betrays its own subject teach the language.

- **Banking_System** — a value object with a derived ledger and template-method hooks. The legacy `accounts.balance` was a `Float` column incremented on every deposit, so the same fact lived in two places and one of them drifted. The rebuild stores only signed amounts and computes the balance; `Account` is frozen, so an operation returns a **new** account.
- **Hotel_Management_System** — half-open date intervals, a status state machine, and rate strategy objects. The legacy model had no dates at all: `status` was a free string, so "is room 101 free on the 14th?" could not be asked, and its inclusive overlap test made a guest leaving on the 12th collide with one arriving on the 12th.
- **Inventory_Management_System** — dunder protocols. `item.quantity += quantity` never checked the number, so `stock_in(id, -5)` subtracted and `stock_out(id, -5)` added. Two rows for the same product were two products, because a row's only equality is identity — the rebuild makes an `Item` equal by SKU, hashable, and ordered.
- **Library_Management_System** — properties with validating setters, class-method constructors, and a shared class attribute. `available = max(quantity - issued, 0)` **destroys** information: correct the quantity down and the record is permanently one copy behind the shelf.
- **Student_Management_System** — an abstract base class, and a number that becomes derived. `cgpa = Column(Float)` was a claim; `B` is 8.00 on a ten-point scale and 3.00 on a four-point scale, so the scale has to be an object that owns the lookup.

**Every numeric fact is exact.** Money is integer cents in all three financial projects; grade points are integer hundredths with a `Fraction` for ordering; rounding is `round_half_up` on integers at the display boundary, never `round()` on a float.

Standard library only: no ORM, no database file, no network.

---

# 🎯 Learning Objectives

- Tell a stored fact from a derived one, and move it to the right side
- Recognise a clamp (`max(x - y, 0)`) as information loss, and replace it with a refusal
- Model a calendar range as a half-open interval and prove the boundary case
- Replace a status string with a state machine that refuses illegal transitions
- Choose between inheritance and composition, and use each where it fits
- Use an abstract base class as a template method, not as a namespace
- Validate a subclass's table at class-creation time with `__init_subclass__`
- Implement `__eq__`, `__hash__`, `__lt__` so a value object can be a dict key
- Use `@property` with a validating setter, and `@dataclass(frozen=True)` for records
- Use a class method as a named constructor (`Loan.of`, `Account.empty`)
- Show the shared-mutable-class-attribute bug on purpose, then avoid it
- Keep money in integer cents end to end, and round half-up only to display
- Compute a credit-weighted mean exactly, and order by a `Fraction`
- Write invariants that a constructor cannot enforce, each with a negative control
- Keep legacy source as an executable constant so a defect is asserted, not described

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Banking_System | Frozen `Account` value object, ledger-derived balance, template-method hooks, six-check audit. | ✅
02 | Hotel_Management_System | Half-open stay intervals, status state machine, rate strategy objects, night-by-night folio. | ✅
03 | Inventory_Management_System | Value-object `Item` with dunder protocols, quantity guards, valuation in cents, four-check audit. | ✅
04 | Library_Management_System | Availability derived from open loans, `Loan.of`, validating `copies` setter, shared-attribute defect. | ✅
05 | Student_Management_System | `GradeScale` ABC, transcripts, credit-weighted GPA in hundredths, exact `Fraction` ranking. | ✅

---

# 💡 Concepts Covered

- Value objects versus entities: equality by value, frozen records, hashing
- Derived state: a balance, an availability, a CGPA that cannot disagree with its source
- Append-only ledgers and signed amounts
- Template method pattern with an abstract base class
- `__init_subclass__` as validation at class-definition time
- Properties with validating setters, and setters that refuse instead of clamping
- Half-open intervals `[check_in, check_out)`, and the collision they prevent
- State machines: legal transitions, and a status that cannot be forged
- Strategy objects for rates, so a discount is a value rather than a branch
- Class methods as named constructors
- The shared-mutable-class-attribute bug, reproduced and then avoided
- Dunder protocols: `__eq__`, `__hash__`, `__lt__`, `__len__`, `__iter__`, `__contains__`
- Integer cents, `round_half_up`, and refusing floats at construction
- `fractions.Fraction` for exact ordering when the display rounds
- Invariants with a negative control for every check
- Legacy code as an executable constant: `compile()`, transcription, and proof

---

# 📁 Repository Structure

```text
03_Object_Oriented_Programming/
│
├── Banking_System/
├── Hotel_Management_System/
├── Inventory_Management_System/
├── Library_Management_System/
├── Student_Management_System/
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

---

# 🛠 Technologies

- Python 3 standard library: `dataclasses`, `fractions`, `abc`, `decimal`,
  `datetime`, `json`, `pathlib`, `argparse`, `contextlib`, `tempfile`
- pytest 9.1.1

No ORM, no database file, no third-party runtime dependencies, no network access.

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Banking System | ✅ |
| Hotel Management System | ✅ |
| Inventory Management System | ✅ |
| Library Management System | ✅ |
| Student Management System | ✅ |

**Completed:** **5 / 5 Projects** · 1,396 passing tests

---

# ▶️ Quick Start

```bash
cd 03_Object_Oriented_Programming/Library_Management_System

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

Each project follows the same shape: `python src/main.py --demo` for a
self-checking offline run, `python -m pytest tests/ -q` for the suite, and
`--quiet` to silence both. Every project also exposes its subject on the command
line:

```bash
cd 03_Object_Oriented_Programming/Banking_System
python src/main.py --balance AC-0001
python src/main.py --statement AC-0001
python src/main.py --legacy            # the Float column and the rebinding of id

cd ../Hotel_Management_System
python src/main.py --availability 2026-03-14:2026-03-16
python src/main.py --book "101:Asha Rao:9876543210:asha@example.com:2026-03-14:2026-03-16"

cd ../Inventory_Management_System
python src/main.py --stock-in B-300:5
python src/main.py --legacy            # stock_in(-5) subtracts five

cd ../Student_Management_System
python src/main.py --student CS-2023-014
python src/main.py --top 3
python src/main.py --legacy            # the typed 9.20 against the computed 9.08
```

---

# 📚 Skills Developed

- Reading a tutorial CRUD app and naming the question its schema cannot answer
- Deciding whether a number is stored or computed, and moving it once
- Writing a value object whose constructor refuses what the domain refuses
- Building a state machine small enough to read and strict enough to matter
- Designing method names that make an illegal operation impossible to type
- Expressing a rate as an object, so a rule is data rather than a branch
- Using `fractions.Fraction` where rounding would reorder a ranking
- Writing an `audit()` that returns every check, then forcing one to fail
- Keeping the original source as a string constant and asserting on its output
- Building 235–374 pytest cases per project, including every error message and flag

---

# 🚀 Key Learning Outcomes

- Show that a balance stored beside its ledger drifts, then derive it instead
- Show that `max(quantity - issued, 0)` loses a copy for ever, then refuse the shrink
- Show that `stock_in(-5)` subtracts five, then guard the quantity
- Show that an inclusive overlap test double-books a room on its changeover day
- Show that two identical rows are unequal, then define equality by SKU
- Show that a typed 9.20 outranks a computed 9.08, then rank the transcript
- Show that `B` is 8.00 or 3.00 depending only on its scale, then make the scale an object
- Keep every amount in integer cents from parse to print

---

# 🔮 Future Enhancements

- A shared `money` and `dates` toolkit for the three financial projects
- Property-based tests (Hypothesis) for the interval algebra and the ledger
- Interest and fees as composable strategy objects in the bank
- A rate calendar with seasons and minimum stays in the hotel
- Barcode and batch movements in the inventory
- Reservation queues and renewals in the library
- Multiple scales per student, with a scale change that restates the transcript

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
