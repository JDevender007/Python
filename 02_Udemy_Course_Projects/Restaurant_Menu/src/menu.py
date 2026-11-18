"""A menu and a cart: dot leaders that fit, prices in integer cents.

The legacy program was six lines:

    n = int(input())
    for i in range(n):
        dish = input()
        price = int(input())
        dash = 20 - len(dish) - len(str(price))
        print(dish + ('-' * dash) + "$" + str(price))

Four defects, and the fourth is the interesting one.

**1. A negative gap disappears silently.** ``'-' * -7`` is ``''`` in Python -
not an error. A dish name long enough to overrun the 20 columns prints with
*no* gap at all: ``"Slow-roasted lamb shoulder$24"``.

**2. ``len`` is not display width.** ``"Cafe\\u0301"`` (``e`` plus a combining
acute) has length 5 but occupies 4 columns, so the line is one column short.
Two CJK characters have length 2 and occupy 4, so the line is two columns
long. The rows stop lining up whenever the menu is not plain ASCII.

**3. Prices are integers.** ``int("4.50")`` raises, and a menu cannot express
4.50. Money is an integer number of cents, not a whole number of dollars.

**4. There is no menu, no cart and no total.** Every run is one throwaway
list; nothing can be added up.

The replacement keeps money in cents, measures width with ``unicodedata``
(combining marks count 0, East Asian wide characters count 2), guarantees a
gap of at least one column, and adds a cart with a stated tax rate rounded
half-up at the boundary.

Standard library only, no network.
"""

from __future__ import annotations

import csv
import os
import tempfile
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

MENU_WIDTH = 34
LEGACY_WIDTH = 20
TAX_BASIS_POINTS = 875          # 8.75%
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "menu.csv"


class MenuError(ValueError):
    """A menu, price or cart operation that cannot be completed."""


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #
def parse_price(value) -> int:
    """Currency to integer cents, exactly; at most two decimal places."""
    if isinstance(value, bool):
        raise MenuError("a price must not be a boolean")
    if isinstance(value, int):
        if value < 0:
            raise MenuError(f"{value!r} is negative")
        return value * 100
    text = str(value).strip()
    if text.startswith("$"):
        text = text[1:].strip()
    text = text.replace(",", "")
    if not text:
        raise MenuError("a price must not be empty")
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        raise MenuError(f"{value!r} is not a price") from None
    if not amount.is_finite():
        raise MenuError(f"{value!r} is not a finite price")
    if amount < 0:
        raise MenuError(f"{value!r} is negative")
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise MenuError(f"{value!r} has more than two decimal places")
    return int(cents)


def format_price(cents: int) -> str:
    """``1250`` -> ``$12.50``; thousands separated."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise MenuError(f"{cents!r} is not a number of cents")
    sign = "-" if cents < 0 else ""
    whole, part = divmod(abs(cents), 100)
    return f"{sign}${whole:,}.{part:02d}"


# --------------------------------------------------------------------------- #
# Display width
# --------------------------------------------------------------------------- #
def display_width(text) -> int:
    """Columns the text occupies when printed in a terminal.

    Combining marks add nothing (they draw on the preceding character) and
    East Asian wide/fullwidth characters take two columns.
    """
    if not isinstance(text, str):
        raise MenuError(f"text must be a string, got {type(text).__name__}")
    width = 0
    for character in text:
        if unicodedata.combining(character):
            continue
        width += 2 if unicodedata.east_asian_width(character) in ("W", "F") \
            else 1
    return width


def legacy_line(dish: str, price: int, width: int = LEGACY_WIDTH) -> str:
    """The original formatter, including the negative-gap collapse."""
    dash = width - len(dish) - len(str(price))
    return dish + ("-" * dash) + "$" + str(price)


def dot_leader(name: str, cents: int, width: int = MENU_WIDTH) -> str:
    """A name, dots, and a right-aligned price.

    Every returned line has ``display_width(line) == width`` when the name
    fits; when it does not, the gap is a single space and the line is longer
    rather than losing the price.
    """
    price = format_price(cents)
    gap = width - display_width(name) - display_width(price)
    if gap < 1:
        return name + " " + price
    return name + "." * gap + price


# --------------------------------------------------------------------------- #
# Menu
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MenuItem:
    name: str
    price_cents: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise MenuError("a dish name must not be empty")
        if isinstance(self.price_cents, bool) or \
                not isinstance(self.price_cents, int):
            raise MenuError("price_cents must be an integer")
        if self.price_cents < 0:
            raise MenuError("price_cents must not be negative")
        object.__setattr__(self, "name", self.name.strip())

    def to_row(self) -> dict[str, str]:
        return {"name": self.name,
                "price": f"{self.price_cents // 100}.{self.price_cents % 100:02d}"}

    @staticmethod
    def from_row(row: dict) -> "MenuItem":
        if not isinstance(row, dict):
            raise MenuError("a menu row must be a mapping")
        for key in ("name", "price"):
            if key not in row:
                raise MenuError(f"menu row is missing {key}")
        unknown = set(row) - {"name", "price"}
        if unknown:
            raise MenuError(f"menu row has unknown column "
                            f"{sorted(unknown)[0]}")
        return MenuItem(row["name"], parse_price(row["price"]))


def load_menu(path: str | Path = DATA_FILE) -> list[MenuItem]:
    """``name,price`` per line; ``#`` starts a comment.

    Duplicate names are refused, because a cart line has to identify a dish.
    """
    path = Path(path)
    if not path.exists():
        raise MenuError(f"menu file not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        lines = [line for line in handle
                 if line.strip() and not line.lstrip().startswith("#")]
    reader = csv.reader(lines)
    try:
        header = [name.strip() for name in next(reader)]
    except StopIteration:
        raise MenuError(f"{path.name} is empty") from None
    if header != ["name", "price"]:
        raise MenuError(f"{path.name} header is {header}, expected "
                        f"['name', 'price']")
    menu: list[MenuItem] = []
    seen: set[str] = set()
    for number, row in enumerate(reader, start=2):
        if not any(field.strip() for field in row):
            continue
        if len(row) != 2:
            raise MenuError(f"{path.name} line {number}: {len(row)} fields, "
                            f"expected 2")
        try:
            item = MenuItem.from_row({"name": row[0], "price": row[1]})
        except MenuError as exc:
            raise MenuError(f"{path.name} line {number}: {exc}") from None
        key = item.name.casefold()
        if key in seen:
            raise MenuError(f"{path.name} line {number}: {item.name!r} "
                            f"appears twice")
        seen.add(key)
        menu.append(item)
    if not menu:
        raise MenuError(f"{path.name} has no dishes")
    return menu


def find_item(menu: list[MenuItem], name: str) -> MenuItem:
    """Case-insensitive exact lookup."""
    if not isinstance(name, str) or not name.strip():
        raise MenuError("a dish name must not be empty")
    needle = name.strip().casefold()
    for item in menu:
        if item.name.casefold() == needle:
            return item
    raise MenuError(f"{name!r} is not on the menu")


def render_menu(menu: list[MenuItem], width: int = MENU_WIDTH) -> str:
    heading = "MENU".center(width, " ")
    lines = [heading]
    for item in menu:
        lines.append(dot_leader(item.name, item.price_cents, width))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Cart
# --------------------------------------------------------------------------- #
def tax_for(subtotal_cents: int,
            basis_points: int = TAX_BASIS_POINTS) -> int:
    """Half-up rounding, in integers, at the boundary."""
    if isinstance(subtotal_cents, bool) or \
            not isinstance(subtotal_cents, int):
        raise MenuError("the subtotal must be an integer number of cents")
    if subtotal_cents < 0:
        raise MenuError("the subtotal must not be negative")
    if not 0 <= basis_points <= 10000:
        raise MenuError("the tax rate must be within 0..10000 basis points")
    return (subtotal_cents * basis_points + 5000) // 10000


@dataclass
class Cart:
    menu: list[MenuItem]
    lines: list[list] = field(default_factory=list)   # [[MenuItem, qty], ...]

    def add(self, name: str, quantity: int = 1) -> MenuItem:
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise MenuError("the quantity must be an integer")
        if quantity < 1:
            raise MenuError("the quantity must be at least 1")
        item = find_item(self.menu, name)
        for line in self.lines:
            if line[0] == item:
                line[1] += quantity
                return item
        self.lines.append([item, quantity])
        return item

    def remove(self, name: str) -> MenuItem:
        item = find_item(self.menu, name)
        for index, line in enumerate(self.lines):
            if line[0] == item:
                del self.lines[index]
                return item
        raise MenuError(f"{name!r} is not in the cart")

    def quantity_of(self, name: str) -> int:
        item = find_item(self.menu, name)
        return sum(line[1] for line in self.lines if line[0] == item)

    @property
    def count(self) -> int:
        return len(self.lines)

    @property
    def items(self) -> int:
        return sum(line[1] for line in self.lines)

    def subtotal(self) -> int:
        return sum(line[0].price_cents * line[1] for line in self.lines)

    def tax(self) -> int:
        return tax_for(self.subtotal())

    def total(self) -> int:
        return self.subtotal() + self.tax()

    def render(self, width: int = MENU_WIDTH) -> str:
        if not self.lines:
            return "(the cart is empty)"
        rows = []
        for item, quantity in self.lines:
            label = f"{quantity} x {item.name}"
            rows.append(dot_leader(label, item.price_cents * quantity, width))
        rows.append("-" * width)
        rows.append(dot_leader("Subtotal", self.subtotal(), width))
        rows.append(dot_leader("Tax (8.75%)", self.tax(), width))
        rows.append(dot_leader("Total", self.total(), width))
        return "\n".join(rows)


def stats(menu: list[MenuItem]) -> dict:
    prices = [item.price_cents for item in menu]
    if not prices:
        return {"dishes": 0, "cheapest": None, "dearest": None,
                "average": None}
    return {"dishes": len(menu),
            "cheapest": min(prices),
            "dearest": max(prices),
            "average": round(sum(prices) / len(prices))}


def write_menu(path: str | Path, menu: list[MenuItem]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with open(handle, "w", encoding="utf-8", newline="") as out:
            out.write("name,price\n")
            for item in menu:
                out.write(f'{item.name},{item.price_cents // 100}.'
                          f'{item.price_cents % 100:02d}\n')
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 70)
    print(" RESTAURANT MENU - a negative gap, and len() is not display width")
    print("=" * 70)

    # 1. the legacy negative gap collapses to nothing
    assert legacy_line("Pad Thai", 12) == "Pad Thai----------$12"
    assert len(legacy_line("Pad Thai", 12)) == 21       # 20 for the pair + $
    long_name = "Slow-roasted lamb shoulder"
    legacy_long = legacy_line(long_name, 24)
    assert legacy_long == long_name + "$24"             # gap == ''
    assert "." not in legacy_long
    print(f"  legacy, short name: {legacy_line('Pad Thai', 12)!r}")
    print(f"  legacy, long name:  {legacy_long!r}  (no gap at all)")

    # 2. the fixed line keeps a gap and the same total width
    short = dot_leader("Pad Thai", 1340)
    assert display_width(short) == MENU_WIDTH
    assert short.endswith("$13.40")
    assert "." in short
    overrun = "Slow-roasted lamb shoulder with rosemary"
    assert display_width(overrun) > MENU_WIDTH
    squeezed = dot_leader(overrun, 2400)
    assert display_width(squeezed) > MENU_WIDTH
    assert squeezed == overrun + " " + "$24.00"
    print(f"  fixed,  short name: {short!r}")
    print(f"  fixed,  long name:  {squeezed!r}  (one space, never none)")

    # 3. combining marks: len 5, width 4
    combining = "Cafe\u0301"
    assert len(combining) == 5
    assert display_width(combining) == 4
    legacy_combining = legacy_line(combining, 3)
    fixed_combining = dot_leader(combining, 300)
    assert display_width(legacy_combining) == 20
    assert display_width(fixed_combining) == MENU_WIDTH
    print(f"  'Cafe' + combining acute: len {len(combining)}, width "
          f"{display_width(combining)}; a len-based line ends a column short")

    # 4. wide characters: len 2, width 4
    wide = "\u5bff\u53f8"                                # two CJK characters
    assert len(wide) == 2
    assert display_width(wide) == 4
    assert display_width(legacy_line(wide, 5)) == 23       # two too long
    assert display_width(dot_leader(wide, 500)) == MENU_WIDTH
    print(f"  two CJK characters: len {len(wide)}, width "
          f"{display_width(wide)}; a len-based line ends two columns long")

    # 5. decimal prices: the legacy int() refuses them
    try:
        int("4.50")
    except ValueError:
        pass
    else:
        raise AssertionError("int('4.50') should have raised")
    assert parse_price("4.50") == 450
    assert parse_price("$1,234.56") == 123456
    assert parse_price(4) == 400
    assert format_price(450) == "$4.50"
    assert format_price(123456) == "$1,234.56"
    for bad in ("4.505", "abc", -1, "", "$"):
        try:
            parse_price(bad)
        except MenuError:
            pass
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    print("  prices: '4.50' -> 450 cents, 4 bad shapes refused, legacy "
          "int('4.50') raises ValueError")

    # 6. the bundled menu
    menu = load_menu()
    assert len(menu) == 10, len(menu)
    assert menu[0].name == "Garlic Bread" and menu[0].price_cents == 450
    summary = stats(menu)
    assert summary["cheapest"] == 325 and summary["dearest"] == 1995
    assert summary["average"] == round(sum(item.price_cents
                                           for item in menu) / 10)
    assert find_item(menu, "pad thai").price_cents == 1340
    for bad in ("Plague Burger", ""):
        try:
            find_item(menu, bad)
        except MenuError:
            pass
        else:
            raise AssertionError(f"{bad!r} should not be on the menu")
    print(f"  10 dishes, cheapest {format_price(summary['cheapest'])}, "
          f"dearest {format_price(summary['dearest'])}")

    # 7. every menu line has the same width and a right-aligned price
    rendered = render_menu(menu).splitlines()
    assert len(rendered) == 11
    for line in rendered[1:]:
        assert display_width(line) == MENU_WIDTH, line
        assert line.endswith(format_price(
            next(item.price_cents for item in menu
                 if line.startswith(item.name))))
    print(f"  all 10 menu lines are exactly {MENU_WIDTH} columns wide")

    # 8. the cart adds up, and tax rounds half-up at the boundary
    cart = Cart(menu)
    cart.add("Margherita Pizza", 2)
    cart.add("Lemonade")
    cart.add("Garlic Bread", 3)
    assert cart.subtotal() == 2 * 1250 + 325 + 3 * 450 == 4175
    assert cart.tax() == 365                             # 365.3125 -> 365
    assert cart.total() == 4540
    assert cart.items == 6 and cart.count == 3
    assert cart.quantity_of("Garlic Bread") == 3
    cart.add("Lemonade")
    assert cart.quantity_of("Lemonade") == 2
    assert cart.items == 7
    assert cart.subtotal() == 4500 and cart.tax() == 394
    assert cart.total() == 4894
    print(f"  cart: 2 pizza + 2 lemonade + 3 bread = "
          f"{format_price(cart.subtotal())}, tax {format_price(cart.tax())}, "
          f"total {format_price(cart.total())}")

    # 9. half-up rounding is pinned on an exact half cent
    assert tax_for(1000) == 88                            # 87.5 -> 88
    assert tax_for(0) == 0
    assert tax_for(571) == 50                             # 49.9625 -> 50
    assert tax_for(8000, basis_points=1000) == 800
    print("  8.75% of $10.00 is $0.88 (87.5 cents rounds up), of $5.71 "
          "is $0.50")

    # 10. cart operations refuse what they cannot do
    for attempt in (lambda: cart.add("Plague Burger"),
                    lambda: cart.add("Lemonade", 0),
                    lambda: cart.add("Lemonade", -2),
                    lambda: cart.add("Lemonade", "2"),
                    lambda: cart.remove("Tiramisu"),
                    lambda: Cart(menu).remove("Lemonade")):
        try:
            attempt()
        except MenuError:
            pass
        else:
            raise AssertionError("an impossible cart operation should fail")
    removed = cart.remove("Garlic Bread")
    assert removed.name == "Garlic Bread" and cart.count == 2
    print("  6 impossible cart operations refused; remove() drops a line")

    # 11. render the cart, and an empty one
    text = cart.render()
    assert "Subtotal" in text and "Total" in text
    assert "(the cart is empty)" == Cart(menu).render()
    width = MENU_WIDTH
    assert all(display_width(line) <= width for line in text.splitlines())
    print("  the cart renders with subtotal, tax and total; empty says so")

    # 12. a menu round trip, and duplicate names refused
    with tempfile.TemporaryDirectory(prefix="menu-") as folder:
        path = Path(folder) / "menu.csv"
        write_menu(path, menu)
        assert load_menu(path) == menu
        first = path.read_bytes()
        write_menu(path, load_menu(path))
        assert path.read_bytes() == first
        path.write_text("name,price\nSoup,4.00\nsoup,4.50\n", encoding="utf-8")
        try:
            load_menu(path)
        except MenuError as exc:
            assert "line 3" in str(exc) and "twice" in str(exc), str(exc)
        else:
            raise AssertionError("a duplicate dish should have been refused")
    print("  menu write/read round trip identical; a duplicate name is "
          "refused by line number")

    print()
    print("Cross-checks OK: the legacy negative gap printed a long name with "
          "no separator, len() disagreed with display width for a combining "
          "mark (5 vs 4) and for two CJK characters (2 vs 4) so the legacy "
          "lines were one short and two long, int('4.50') was refused while "
          "450 cents parsed exactly, 4 bad prices refused, 10 dishes loaded "
          "with pinned extremes, all 10 menu lines exactly 34 columns, a "
          "cart totalling 45.00 with 3.94 tax and 48.94 total, half-up tax "
          "pinned on 87.5 and 49.9625 cents, 6 impossible operations "
          "refused, and a byte-identical menu round trip")
    print("Demo completed successfully.")
    return 0
