"""An inventory whose objects behave like values, not like rows.

The legacy project was SQLAlchemy over SQLite, and its model was a row:

    class Item(Base):
        item_name = Column(String(100), unique=True, nullable=False)
        quantity = Column(Integer, nullable=False, default=0)
        price = Column(Float, nullable=False, default=0.0)

    def stock_in(self, item_id, quantity):
        item.quantity += quantity          # no check at all

    def stock_out(self, item_id, quantity):
        if quantity > item.quantity:
            print("Insufficient stock.")
            return
        item.quantity -= quantity

Three things follow from that shape.

**1. A row has no rules, so arithmetic on it cannot fail.** ``stock_in(id, -5)``
subtracts five units because the method only adds. ``stock_out(id, -5)`` *adds*
five units, because ``-5 > item.quantity`` is false and ``-= -5`` is ``+= 5``.
The validator was in the CLI, so any other caller skipped it. Here every
movement is a method on a collection that refuses a non-positive quantity, and
``Line`` itself refuses to be constructed with a negative quantity -- so the
bad value cannot exist at all.

**2. Equality was identity.** Two ``Item`` rows loaded separately are two
objects, so ``a == b`` is ``False`` for the same product, and putting items in a
set or a dictionary never deduplicates them. ``Item`` here defines ``__eq__``
and ``__hash__`` on its normalised SKU: two objects for ``W-100`` are equal,
hash alike, and one of them can be a dictionary key.

**3. The collection was a session query.** ``search`` ended in
``query.first()``, so "bearing" returned one bearing out of two and there was no
way to ask "is this SKU in stock?" without a round trip. ``Inventory`` is a real
collection: ``len()`` counts lines, ``for line in inventory`` yields them in a
stable order, ``"W-100" in inventory`` asks a question, and
``inventory["W-100"]`` is one line.

The warm-up act is ``Line``: a frozen value with ``__add__`` and ``__sub__``, so
``line + 5`` and ``line - 5`` are new lines rather than mutations, ``bool(line)``
means "in stock", and the subtraction cannot produce a negative.

Prices are integer cents throughout. The legacy ``price = Column(Float)``
drifted: three units at ``19.99`` sum to ``59.969999999999999``.

Standard library only: no ORM, no database file, no network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "inventory.json"

#: The legacy price column: a float, so sums drift.
LEGACY_PRICE = "price = Column(Float, nullable=False, default=0.0)"

#: The legacy stock movement: arithmetic with no rule.
LEGACY_STOCK_IN = "item.quantity += quantity"

#: The legacy search: the first row only.
LEGACY_SEARCH = "query.first()"

#: A line at or below this quantity needs reordering.
LOW_STOCK = 5


class InventoryError(ValueError):
    """A SKU, a price, a quantity or a data file that cannot be accepted."""


class DuplicateItem(InventoryError):
    """The SKU is already in the inventory."""


class UnknownItem(InventoryError):
    """No line with that SKU."""


class NotEnoughStock(InventoryError):
    """A stock-out larger than the quantity on hand."""


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def normalise_sku(value) -> str:
    """A SKU is text, trimmed and upper-cased, so case never splits an item."""
    if not isinstance(value, str):
        raise InventoryError(f"a SKU must be text, got {type(value).__name__}")
    cleaned = value.strip().upper()
    if not cleaned:
        raise InventoryError("a SKU must not be empty")
    if any(character in cleaned for character in " \t\r\n"):
        raise InventoryError(f"{value!r} contains whitespace")
    return cleaned


def check_cents(value, label: str = "a price") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InventoryError(f"{label} is an integer number of cents, got "
                             f"{type(value).__name__}; a float would drift")
    if value < 0:
        raise InventoryError(f"{label} must not be negative")
    return value


def check_quantity(value, label: str = "a quantity") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InventoryError(f"{label} must be a whole number of units, got "
                             f"{type(value).__name__}")
    if value < 0:
        raise InventoryError(f"{label} must not be negative")
    return value


def format_cents(cents: int) -> str:
    """``617112`` -> ``Rs 6,171.12``; the only place money becomes text."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise InventoryError("only an integer number of cents can be shown")
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}Rs {whole:,}.{fraction:02d}"


def round_half_up(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise InventoryError("the denominator must be positive")
    if numerator < 0:
        return -(((-numerator) * 2 + denominator) // (2 * denominator))
    return (numerator * 2 + denominator) // (2 * denominator)


# --------------------------------------------------------------------------- #
# Item: equality by SKU, not by identity
# --------------------------------------------------------------------------- #
class Item:
    """A product: an SKU, a name, a category, a price and a supplier."""

    def __init__(self, sku, name, category, price_cents, supplier=""):
        self.sku = normalise_sku(sku)
        if not isinstance(name, str) or not name.strip():
            raise InventoryError("an item needs a name")
        if not isinstance(category, str) or not category.strip():
            raise InventoryError("an item needs a category")
        if not isinstance(supplier, str):
            raise InventoryError("a supplier must be text")
        self.name = name.strip()
        self.category = category.strip().title()
        self.price = check_cents(price_cents)
        self.supplier = supplier.strip()

    # -- equality and hashing ---------------------------------------------- #
    def __eq__(self, other):
        if not isinstance(other, Item):
            return NotImplemented
        return self.sku == other.sku

    def __ne__(self, other):
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return NotImplemented
        return not equal

    def __hash__(self) -> int:
        return hash(self.sku)

    # -- ordering and display ---------------------------------------------- #
    def __lt__(self, other):
        if not isinstance(other, Item):
            return NotImplemented
        return (self.category, self.name.casefold(), self.sku) < \
            (other.category, other.name.casefold(), other.sku)

    def __repr__(self) -> str:
        return (f"<Item {self.sku} {self.name!r} {self.category} "
                f"{format_cents(self.price)}>")

    def __str__(self) -> str:
        return f"{self.sku:<8} {self.name:<22.22} {self.category:<12.12} " \
               f"{format_cents(self.price):>12}"

    def __format__(self, spec: str) -> str:
        """``f"{item:price}"`` gives the money, ``:name`` the name."""
        if not spec:
            return str(self)
        if spec == "price":
            return format_cents(self.price)
        if spec == "name":
            return self.name
        if spec == "sku":
            return self.sku
        raise InventoryError(f"unknown item format {spec!r}")

    # -- persistence ------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"sku": self.sku, "name": self.name,
                "category": self.category, "price_cents": self.price,
                "supplier": self.supplier}

    @classmethod
    def from_dict(cls, row) -> "Item":
        if not isinstance(row, dict):
            raise InventoryError("an item must be an object")
        unknown = set(row) - {"sku", "name", "category", "price_cents",
                              "supplier"}
        if unknown:
            raise InventoryError(f"unknown item keys: {sorted(unknown)}")
        for key in ("sku", "name", "category", "price_cents"):
            if key not in row:
                raise InventoryError(f"an item is missing {key!r}")
        return cls(row["sku"], row["name"], row["category"],
                   row["price_cents"], row.get("supplier", ""))


# --------------------------------------------------------------------------- #
# Line: a frozen value with arithmetic
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Line:
    """One item and how many of it are on hand."""

    item: Item
    quantity: int

    def __post_init__(self) -> None:
        if not isinstance(self.item, Item):
            raise InventoryError("a line needs an Item")
        check_quantity(self.quantity)

    # -- arithmetic -------------------------------------------------------- #
    def __add__(self, units):
        """``line + 5`` is a new line; the old one is unchanged."""
        if isinstance(units, bool) or not isinstance(units, int):
            return NotImplemented
        return Line(self.item, self.quantity + units)

    def __sub__(self, units):
        """``line - 5``; a result below zero raises rather than going negative."""
        if isinstance(units, bool) or not isinstance(units, int):
            return NotImplemented
        return Line(self.item, self.quantity - units)

    # -- value and truth --------------------------------------------------- #
    @property
    def value(self) -> int:
        """The line's worth in cents: price times quantity."""
        return self.item.price * self.quantity

    def is_low(self, threshold: int = LOW_STOCK) -> bool:
        check_quantity(threshold, "a threshold")
        return self.quantity <= threshold

    def __bool__(self) -> bool:
        """A line is true when there is stock on it."""
        return self.quantity > 0

    def __len__(self) -> int:
        """``len(line)`` is the quantity, so a line reads like a container."""
        return self.quantity

    # -- display ----------------------------------------------------------- #
    def __str__(self) -> str:
        flag = "  LOW" if self.is_low() else ""
        return (f"{self.item.sku:<8} {self.item.name:<22.22} "
                f"{self.quantity:>4}  {format_cents(self.value):>14}{flag}")

    def __repr__(self) -> str:
        return f"<Line {self.item.sku} x{self.quantity}>"

    def to_dict(self) -> dict:
        return {"item": self.item.to_dict(), "quantity": self.quantity}

    @classmethod
    def from_dict(cls, row) -> "Line":
        if not isinstance(row, dict):
            raise InventoryError("a line must be an object")
        unknown = set(row) - {"item", "quantity"}
        if unknown:
            raise InventoryError(f"unknown line keys: {sorted(unknown)}")
        for key in ("item", "quantity"):
            if key not in row:
                raise InventoryError(f"a line is missing {key!r}")
        return cls(Item.from_dict(row["item"]), row["quantity"])


# --------------------------------------------------------------------------- #
# Inventory: a collection, with the protocols a caller expects
# --------------------------------------------------------------------------- #
class Inventory:
    """SKU -> Line, with the rules the legacy service kept in a CLI."""

    def __init__(self, name: str = "Main Store"):
        if not isinstance(name, str) or not name.strip():
            raise InventoryError("the inventory needs a name")
        self.name = name.strip()
        self._lines: dict[str, Line] = {}

    # -- collection protocol ----------------------------------------------- #
    def __len__(self) -> int:
        return len(self._lines)

    def __iter__(self):
        """Lines in SKU order, so two runs print the same report."""
        return iter([self._lines[key] for key in sorted(self._lines)])

    def __contains__(self, thing) -> bool:
        if isinstance(thing, Item):
            return thing.sku in self._lines
        if isinstance(thing, str):
            try:
                return normalise_sku(thing) in self._lines
            except InventoryError:
                return False
        return False

    def __getitem__(self, sku) -> Line:
        return self.get(sku)

    def __eq__(self, other):
        if not isinstance(other, Inventory):
            return NotImplemented
        return self.name == other.name and self._lines == other._lines

    def __repr__(self) -> str:
        return (f"<Inventory {self.name!r} with {len(self)} lines, "
                f"{format_cents(self.value())}>")

    @property
    def lines(self) -> tuple[Line, ...]:
        return tuple(self)

    # -- lookups ----------------------------------------------------------- #
    def get(self, sku) -> Line:
        key = normalise_sku(sku)
        try:
            return self._lines[key]
        except KeyError:
            raise UnknownItem(f"no line for SKU {key}") from None

    def quantity(self, sku) -> int:
        return self.get(sku).quantity

    def search(self, text: str) -> list[Line]:
        """Every line whose SKU, name, category or supplier contains the text."""
        if not isinstance(text, str):
            raise InventoryError("a search needs text")
        needle = text.strip().casefold()
        if not needle:
            raise InventoryError("a search needs something to look for")
        return [line for line in self.lines
                if needle in line.item.sku.casefold()
                or needle in line.item.name.casefold()
                or needle in line.item.category.casefold()
                or needle in line.item.supplier.casefold()]

    def low_stock(self, threshold: int = LOW_STOCK) -> list[Line]:
        """Lines at or below the threshold, emptiest first."""
        check_quantity(threshold, "a threshold")
        found = [line for line in self.lines if line.is_low(threshold)]
        return sorted(found, key=lambda line: (line.quantity, line.item.sku))

    # -- changing the collection ------------------------------------------- #
    def add(self, item: Item, quantity: int = 0) -> Line:
        if not isinstance(item, Item):
            raise InventoryError("only an Item can be stocked")
        check_quantity(quantity)
        if item.sku in self._lines:
            raise DuplicateItem(
                f"{item.sku} is already on the inventory as "
                f"{self._lines[item.sku].item.name!r}; stock it in instead")
        line = Line(item, quantity)
        self._lines[item.sku] = line
        return line

    def remove(self, sku) -> Line:
        key = normalise_sku(sku)
        try:
            return self._lines.pop(key)
        except KeyError:
            raise UnknownItem(f"no line for SKU {key}") from None

    # -- stock movements --------------------------------------------------- #
    def stock_in(self, sku, units) -> Line:
        if isinstance(units, bool) or not isinstance(units, int) or units <= 0:
            raise InventoryError("a stock-in must be a positive whole number")
        line = self.get(sku)
        self._lines[line.item.sku] = line + units
        return self._lines[line.item.sku]

    def stock_out(self, sku, units) -> Line:
        if isinstance(units, bool) or not isinstance(units, int) or units <= 0:
            raise InventoryError("a stock-out must be a positive whole number")
        line = self.get(sku)
        if units > line.quantity:
            raise NotEnoughStock(
                f"{line.item.sku} holds {line.quantity}, cannot remove {units}")
        self._lines[line.item.sku] = line - units
        return self._lines[line.item.sku]

    # -- totals ------------------------------------------------------------ #
    def value(self) -> int:
        return sum(line.value for line in self._lines.values())

    def by_category(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for line in self._lines.values():
            totals[line.item.category] = \
                totals.get(line.item.category, 0) + line.value
        return dict(sorted(totals.items()))

    def audit(self) -> list[tuple[str, bool]]:
        """Five invariants, each reported by name and verdict."""
        checks = []

        keys = list(self._lines)
        checks.append(("every SKU appears once",
                       len(keys) == len(set(keys))))

        negative = all(isinstance(line.quantity, int)
                       and not isinstance(line.quantity, bool)
                       and line.quantity >= 0
                       for line in self._lines.values())
        checks.append(("no line holds a negative quantity", negative))

        recomputed = sum(line.item.price * line.quantity
                         for line in self._lines.values())
        checks.append(("the total equals the sum of the lines",
                       recomputed == self.value()))

        reported = {line.item.sku for line in self.low_stock()}
        expected = {line.item.sku for line in self._lines.values()
                    if line.quantity <= LOW_STOCK}
        checks.append(("every line at or below the threshold is low stock",
                       reported == expected))

        well_formed = all(line.item.name.strip() and line.item.price >= 0
                          for line in self._lines.values())
        checks.append(("every item has a name and a non-negative price",
                       well_formed))
        return checks

    def problems(self) -> list[str]:
        return [name for name, passed in self.audit() if not passed]

    # -- persistence ------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"name": self.name,
                "lines": [line.to_dict() for line in self]}

    @classmethod
    def from_dict(cls, payload) -> "Inventory":
        if not isinstance(payload, dict):
            raise InventoryError("an inventory document must be an object")
        unknown = set(payload) - {"name", "lines"}
        if unknown:
            raise InventoryError(f"unknown inventory keys: {sorted(unknown)}")
        for key in ("name", "lines"):
            if key not in payload:
                raise InventoryError(f"the inventory is missing {key!r}")
        if not isinstance(payload["lines"], list):
            raise InventoryError("'lines' must be a list")
        inventory = cls(payload["name"])
        for row in payload["lines"]:
            line = Line.from_dict(row)
            inventory.add(line.item, line.quantity)
        return inventory


def load_inventory(path=DATA_FILE) -> Inventory:
    path = Path(path)
    if not path.exists():
        raise InventoryError(f"inventory file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InventoryError(f"{path.name} is not valid JSON: {exc}") from None
    return Inventory.from_dict(payload)


def save_inventory(path, inventory: Inventory) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory.to_dict(), indent=2) + "\n",
                    encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _legacy_row():
    """A stand-in for an ORM row: attributes, no rules, no ``__eq__``."""

    class Row:
        def __init__(self, sku, name, quantity, price):
            self.sku = sku
            self.name = name
            self.quantity = quantity
            self.price = price

        def __repr__(self):
            return f"<Row {self.sku} x{self.quantity}>"

    return Row


def run_demo() -> int:
    print("=" * 74)
    print(" INVENTORY - a row with no rules, and objects that are values")
    print("=" * 74)

    # 1. the legacy movement accepted any number
    Row = _legacy_row()
    row = Row("W-100", "Widget", 10, 19.99)
    for _ in range(3):
        exec(LEGACY_STOCK_IN, {"item": row, "quantity": -5})  # noqa: S102
    assert row.quantity == -5
    item = Item("W-100", "Widget", "Hardware", 1999)
    refuse = 0
    for bad in (-1, True, 2.5, "5"):
        try:
            Line(item, bad)
        except InventoryError:
            refuse += 1
        else:
            raise AssertionError(f"{bad!r} was accepted as a quantity")
    assert refuse == 4
    print(f"  legacy 'item.quantity += quantity' with -5, three times: "
          f"10 -> {row.quantity}; Line refuses {refuse} bad quantities")

    # 2. the float price column drifts
    drifted = row.price * 3
    assert f"{drifted:.17g}" == "59.969999999999999", f"{drifted:.17g}"
    assert 1999 * 3 == 5997
    assert format_cents(5997) == "Rs 59.97"
    print(f"  3 units at 19.99 in a Float column: {drifted:.17g}; "
          f"in cents: {5997} = {format_cents(5997)}")

    # 3. equality is the SKU, not the object
    left = Item("w-100", "Widget steel", "Hardware", 1299, "Acme")
    right = Item("W-100", "Widget brass", "Hardware", 1899, "Acme")
    assert left is not right and left == right
    assert hash(left) == hash(right)
    assert len({left, right}) == 1
    assert left != Item("W-101", "Widget brass", "Hardware", 1899)
    assert left != "W-100"
    assert left != 42
    legacy_left, legacy_right = Row("W-100", "Widget", 1, 1.0), \
        Row("W-100", "Widget", 1, 1.0)
    assert legacy_left != legacy_right
    print(f"  Item('w-100') == Item('W-100') is {left == right}, "
          f"hash equal, one set member; the legacy rows are unequal")

    # 4. Line arithmetic returns new lines and refuses to go negative
    line = Line(left, 10)
    bigger = line + 5
    smaller = line - 4
    assert (line.quantity, bigger.quantity, smaller.quantity) == (10, 15, 6)
    assert line.item is bigger.item
    assert bool(line) and not bool(line - 10)
    assert len(line) == 10
    assert line.value == 12990 and line.is_low() is False
    try:
        line - 11
    except InventoryError as exc:
        overdraw = str(exc)
    else:
        raise AssertionError("a negative line was built")
    assert "must not be negative" in overdraw
    try:
        line + 1.5
    except TypeError:
        pass
    else:
        raise AssertionError("a float was added")
    print(f"  Line: +5 -> {bigger.quantity}, -4 -> {smaller.quantity}, "
          f"bool(empty) False, len {len(line)}; -11 refused")

    # 5. the collection protocols
    store = Inventory("Demo Store")
    store.add(left, 10)
    store.add(Item("W-101", "Widget brass", "Hardware", 1899, "Acme"), 4)
    store.add(Item("B-300", "Bearing 608", "Motion", 2599, "Rotex"), 18)
    assert len(store) == 3
    assert [line.item.sku for line in store] == ["B-300", "W-100", "W-101"]
    assert "w-100" in store and left in store
    assert "NOPE" not in store and "  " not in store and 7 not in store
    assert store["W-101"].quantity == 4
    assert len(store.search("widget")) == 2
    assert [line.item.sku for line in store.search("ro")] == ["B-300"]
    assert [line.item.sku for line in store.search("bearing")] == ["B-300"]
    legacy_first = store.search("widget")[:1]
    assert len(legacy_first) == 1
    print(f"  {LEGACY_SEARCH} on 'widget' returns {len(legacy_first)}; "
          f"search() returns {len(store.search('widget'))}; "
          f"'w-100' in inventory is True")

    # 6. a stock-out cannot go below zero, and leaves the line alone
    before = store["W-100"].quantity
    try:
        store.stock_out("W-100", 11)
    except NotEnoughStock as exc:
        short = str(exc)
    else:
        raise AssertionError("an overdraw was accepted")
    assert store["W-100"].quantity == before
    refused = 0
    for units in (0, -3):
        for method in (store.stock_in, store.stock_out):
            try:
                method("W-100", units)
            except InventoryError:
                refused += 1
            else:
                raise AssertionError(f"{method.__name__}({units}) passed")
    assert refused == 4
    assert store.stock_in("W-100", 2).quantity == 12
    assert store.stock_out("W-100", 2).quantity == 10
    print(f"  stock_out(11) refused ({short[:40]}...), quantity still "
          f"{before}; 4 non-positive movements refused")

    # 7. the low-stock boundary, and the duplicate rule
    stores = Inventory("Boundary Store")
    stores.add(Item("A-1", "At the line", "Test", 100), LOW_STOCK)
    stores.add(Item("A-2", "One above", "Test", 100), LOW_STOCK + 1)
    assert [line.item.sku for line in stores.low_stock()] == ["A-1"]
    assert [line.item.sku for line in stores.low_stock(6)] == ["A-1", "A-2"]
    try:
        stores.add(Item("a-1", "A second", "Test", 100))
    except DuplicateItem as exc:
        duplicate = str(exc)
    else:
        raise AssertionError("a duplicate SKU was added")
    assert "stock it in instead" in duplicate
    assert len(stores) == 2
    print(f"  threshold {LOW_STOCK}: 1 low line; duplicate 'a-1' refused by "
          f"normalised SKU, still {len(stores)} lines")

    # 8. every dunder the caller needs, on a bad value
    assert stores.audit() == stores.audit()
    assert len(stores.audit()) == 5
    assert stores.problems() == []

    # 9. the seeded inventory
    seeded = load_inventory()
    assert len(seeded) == 8
    assert seeded.problems() == []
    assert seeded.value() == 617112
    assert [line.item.sku for line in seeded.low_stock()] == \
        ["G-201", "M-400", "W-101"]
    assert seeded.by_category()["Motion"] == 204276
    broken = Inventory.from_dict(seeded.to_dict())
    corrupt = Line(broken["W-100"].item, 0)
    object.__setattr__(corrupt, "quantity", -1)   # a hand-edited record
    broken._lines["W-100"] = corrupt
    assert broken.problems() == ["no line holds a negative quantity"]
    print(f"  seeded: 8 lines, {format_cents(seeded.value())}, 3 low-stock "
          f"lines, 5/5 checks; a -1 quantity fails exactly 1 check")

    # 10. save and load
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "copy.json"
        save_inventory(target, seeded)
        first_bytes = target.read_bytes()
        save_inventory(target, load_inventory(target))
        assert target.read_bytes() == first_bytes
        assert load_inventory(target) == seeded
    print("  the seeded inventory saves and reloads byte for byte")

    print()
    print("Cross-checks OK: the legacy movement took 10 units to -5 with no "
          "error while 4 non-positive movements were refused, 3 units at "
          "19.99 in a Float column drifted to 59.969999999999999 against 5997 "
          "exact cents, two Items for W-100 were equal, hashed alike and "
          "collapsed to one set member while two legacy rows were unequal, "
          "line +5 and -4 returned new lines and -11 was refused, the "
          "inventory answered len/iter/in/getitem, search('widget') returned "
          "2 lines where query.first() returned 1, stock_out(11) was refused "
          "with the quantity untouched and 4 more movements were refused, the "
          "low-stock boundary included exactly the threshold and a duplicate "
          "'a-1' was refused, the seeded 8 lines totalled 617112 cents with "
          "3 low-stock lines and 5/5 checks passing, a -1 quantity failed "
          "exactly one check, and the file round-tripped byte for byte")
    print("\nDemo completed successfully.")
    return 0
