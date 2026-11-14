<div align="center">

# 📦 Inventory Management System

### The legacy project stored stock in an ORM row and moved it with `item.quantity += quantity`. Nothing checked the number, so `stock_in(id, -5)` **subtracted** five units and `stock_out(id, -5)` **added** five. Two rows for the same product were two different products, because a row's only equality is identity.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The old service was three lines long and had no rules:

```python
def stock_in(self, item_id, quantity):
    item.quantity += quantity          # no check at all

def stock_out(self, item_id, quantity):
    if quantity > item.quantity:
        print("Insufficient stock.")
        return
    item.quantity -= quantity
```

Three consequences, and one more from the model.

**1 · A row has no rules, so arithmetic on it cannot fail.**

- `stock_in(id, -5)` subtracts five, because the method only ever adds.
- `stock_out(id, -5)` **adds** five, because `-5 > item.quantity` is false and
  `-= -5` is `+= 5`.
- The validator lived in the CLI, so any other caller — a script, a test, a
  future menu item — skipped it entirely.

**2 · Equality was identity.** Two `Item` rows loaded in two sessions are two
objects. `a == b` is `False` for the same product, and putting items in a set or
a dictionary never deduplicates them:

```python
>>> Session().query(Item).filter_by(sku="W-100").first() == \
... Session().query(Item).filter_by(sku="W-100").first()
False
```

**3 · The collection was a query.** `search_item` ended in `query.first()`:

```python
return query.first()
```

so `"bearing"` returned one bearing out of two, and there was no way to ask "is
this SKU in stock?" without another round trip.

**4 · `price = Column(Float)`.** Money in a float column drifts: three units at
`19.99` sum to `59.969999999999999`.

The replacement is a small hierarchy of values, and each one closes a hole.

**`Item` is a value whose identity is its SKU.** `__eq__` compares the SKU
normalised to uppercase, `__hash__` hashes it, so two objects for `W-100` are
equal, hash alike, collapse to one set member, and work as dictionary keys.
`Item` also defines `__lt__` (category, then name, then SKU), `__repr__`,
`__str__` and `__format__` with `:price`, `:name` and `:sku`.

**`Line` is a frozen value with arithmetic.** `line + 5` and `line - 5` return
**new** lines rather than mutating; subtracting too much raises instead of going
negative; `bool(line)` means "there is stock"; `len(line)` is the quantity;
`line.value` is price times quantity.

**`Inventory` is a real collection.** `len()` counts lines, `for line in
inventory` yields them in SKU order, `"W-100" in inventory` asks a question, and
`inventory["W-100"]` is one line. `stock_in` and `stock_out` live here, where
they can refuse a non-positive quantity, and `stock_out` refuses an overdraw
rather than printing a complaint and returning.

Money is integer cents throughout. `format_cents` is the only function that
turns money into text.

Standard library only: no ORM, no database file, no network.

---

# ✨ Features

- `normalise_sku` — text, trimmed, upper-cased, no inner whitespace
- `check_cents` / `check_quantity` — integer-only, no floats, no booleans, no negatives, with a drifting explanation
- `format_cents` — `617112` → `Rs 6,171.12`, grouping and sign
- `round_half_up` — integer rounding, both signs, no `round()`
- `Item` — SKU identity, `__eq__`/`__hash__`/`__lt__`/`__repr__`/`__str__`/`__format__`
- `Line` — frozen dataclass, `__add__`/`__sub__` returning new lines, `__bool__`, `__len__`, `value`, `is_low`
- `Inventory` — `__len__`/`__iter__`/`__contains__`/`__getitem__`/`__eq__`/`__repr__`, `lines`
- `search` — SKU, name, category and supplier, every match (not `query.first()`)
- `low_stock` — threshold inclusive, emptiest first
- `stock_in` / `stock_out` — positive whole numbers only; an overdraw is refused and the quantity is untouched
- `audit` — five named invariants, each reported pass or fail
- `load_inventory` / `save_inventory` — JSON round trip, unknown keys refused
- `data/inventory.json` — 8 lines, 617,112 cents, 3 low-stock lines
- CLI: `--items`, `--search`, `--low-stock`, `--add`, `--stock-in`, `--stock-out`, `--remove`, `--value`, `--audit`, `--legacy`, `--write`, `--json`, `--quiet`
- Exit `2` on an `InventoryError`; `--demo` always returns `0`
- 242 passing pytest tests

---

# 📂 Folder Structure

```text
Inventory_Management_System/
│
├── src/
│   ├── main.py       # CLI: list, search, add, move stock, value, audit
│   └── inventory.py  # Item, Line, Inventory, the demo
│
├── tests/
│   └── test_inventory.py
│
├── data/
│   └── inventory.json  # 8 lines, Rs 6,171.12, 3 low-stock lines
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 03_Object_Oriented_Programming/Inventory_Management_System

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# Every line, with the total
python src/main.py

# Every line whose SKU, name, category or supplier matches
python src/main.py --search bearing
python src/main.py --search motion

# Reorder list, emptiest first
python src/main.py --low-stock
python src/main.py --low-stock 6

# Take stock in and out
python src/main.py --stock-in W-100:5
python src/main.py --stock-out G-200:12

# A new item: SKU:NAME:CATEGORY:PRICE:QUANTITY[:SUPPLIER]
python src/main.py --add "P-600:Plunger:Hardware:4.25:25:Acme"

# Drop a line
python src/main.py --remove S-500

# Money, by category
python src/main.py --value

# The five invariants
python src/main.py --audit

# What the legacy model did
python src/main.py --legacy
```

**Exit codes:** `0` = the command ran · `2` = an unknown SKU, a duplicate SKU,
an overdraw, a non-positive movement, a bad price or quantity, a malformed spec,
or a missing data file.

---

# 🧠 How It Works

```text
 normalise_sku   text, trimmed, upper-cased, no inner space
 check_cents     int, not bool, not negative
 check_quantity  int, not bool, not negative

 Item            identity = the normalised SKU
   ├── __eq__ / __hash__     two objects for W-100 are one product
   ├── __lt__               category, then name, then SKU
   └── __format__           :price, :name, :sku

 Line  (frozen)  an Item and a quantity
   ├── __add__ / __sub__    returns a NEW line; below zero raises
   ├── __bool__             True when there is stock
   ├── __len__              the quantity
   └── value                price * quantity, in cents

 Inventory       SKU -> Line
   ├── __len__ / __iter__ / __contains__ / __getitem__
   ├── search()             every match, where query.first() took one
   ├── stock_in/out()       positive ints only; overdraw refused
   ├── low_stock()          quantity <= threshold, emptiest first
   └── audit()              5 invariants
```

Details worth knowing:

- **`stock_out` refuses instead of printing.** The legacy method printed
  `Insufficient stock.` and returned — the caller had no way to tell success
  from failure. Here it raises `NotEnoughStock`, and the demo proves the
  quantity is still `10` afterwards.
- **`line - 11` raises, so a negative quantity cannot be built.** Because `Line`
  is frozen and validates in `__post_init__`, `-1` is not a value the type can
  hold. The audit still checks for one, and the demo creates it with
  `object.__setattr__` to prove the check is real.
- **`line + 1.5` raises `TypeError`, not `InventoryError`.** `__add__` returns
  `NotImplemented` for a non-integer, which is the protocol: a float is not a
  unit count, so the operation does not exist.
- **`bool(line - 10)` is `False`.** A line at zero is falsy, so
  `if line:` reads as "if there is stock".
- **The low-stock threshold is inclusive.** `LOW_STOCK = 5`, and a line holding
  exactly five is low; the demo pins both sides of the boundary.
- **A duplicate is refused by normalised SKU.** `add(Item("a-1", ...))` after
  `A-1` raises `DuplicateItem` and suggests stocking it in instead, so the
  legacy `unique=True` column is enforced in code.
- **`by_category` is sorted.** Two runs print the same report, and the seeded
  `Motion` total is pinned at `204276` cents.
- **`from_dict` refuses unknown keys** at every level — document, line and item
  — so a typo in the data file is an error rather than silently ignored.

---

# 🛠 Technologies

- Python 3 standard library: `dataclasses` (frozen), `json`, `pathlib`,
  `argparse`, `contextlib`, `tempfile`
- pytest 9.1.1

No ORM, no database file, no network.

---

# 📚 Concepts Covered

- Value objects: identity by key, not by memory address
- `__eq__` / `__hash__` / `__ne__` and why a set needs both
- Operator overloading that returns new values instead of mutating
- The `NotImplemented` protocol and when it becomes `TypeError`
- Frozen dataclasses and validation in `__post_init__`
- The collection protocol: `__len__`, `__iter__`, `__contains__`, `__getitem__`
- Truthiness (`__bool__`) and length (`__len__`) as different questions
- Integer cents versus `Column(Float)` drift
- Invariants checked by name, with a negative control for each
- Why `query.first()` is not a search

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**242 tests passed** covering SKU normalisation (uppercase, trim, three
refusals), `check_cents` and `check_quantity` (six refusals and their labels),
`format_cents` (pinned total, zero, padding, grouping, a negative, two
refusals), `round_half_up` (both directions, both signs, a refused
denominator), `Item` (normalisation, eight refusals, equality, hashing, set and
dict behaviour, ordering, repr, str, four formats, an unknown format, round
trip, four `from_dict` refusals), `Line` (two constructor refusals, frozen,
arithmetic in five shapes, three `NotImplemented` paths, value, five threshold
checks, truthiness, length, text, repr, equality, round trip, three
`from_dict` refusals), `Inventory` (name, the six protocols, five containment
answers, `get`/`quantity`, twelve search cases, six low-stock cases, add /
duplicate / remove / seven movement refusals, totals, five audit checks, a
hand-edited negative quantity), persistence (nine `from_dict` refusals, save
idempotence), the seeded file (eight pinned facts), the demo, and every CLI mode
including `--add`, `--stock-in`, `--stock-out`, `--remove`, `--audit`,
`--legacy`, `--json`, `--write` and `--quiet`.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
