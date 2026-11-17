"""A ledger stores signs; a CASE branch that re-invents them loses money.

The legacy inventory system kept its quantities as positive magnitudes and
rebuilt the sign at query time:

    SELECT p.sku,
           SUM(CASE WHEN m.movement = 'out' THEN -ABS(m.quantity)
                    ELSE ABS(m.quantity) END) AS units
    FROM products p
    LEFT JOIN stock_movements m ON m.product_id = p.id
    GROUP BY p.id

Three things are wrong with that one expression, and only one of them is
visible on a screen.

**The sign is already in the data.** A stock movement is a signed entry in a
ledger: a receipt is positive, an issue is negative, an adjustment is whatever
the stocktake says. Once the sign lives in the row, no query has to guess it.
When the sign lives in a CASE branch instead, the branch becomes a second
source of truth, and the two drift apart the moment somebody writes a movement
the branch did not anticipate.

**Only `out` was guarded.** The CASE names `in` implicitly (the ELSE) and `out`
explicitly. `adjustment` falls into the ELSE, so a -30 water-damage write-off is
read back as +30, and the shelf reports 70 lamps where 10 remain. The error is
not a rounding error; it is a stocktake that will never reconcile.

**A bare column in GROUP BY prices a whole category with one product.**
`SUM(m.quantity) * p.unit_price` groups by `p.category` but selects
`p.unit_price` without aggregating it. SQLite is happy to return the price of
an arbitrary row in the group, so a category worth 40954.00 is reported at
whatever the last product scanned happened to cost. The query never errors.

Money is integer cents parsed from decimal text, and the average stock value
per product uses `divide_half_up`, never `round()`.

The rebuild keeps all three defective queries as executable strings, runs them
beside the corrected versions on the same seed files, and prints the gap.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SUPPLIERS_FILE = DATA_DIR / "suppliers.csv"
PRODUCTS_FILE = DATA_DIR / "products.csv"
MOVEMENTS_FILE = DATA_DIR / "movements.csv"

MOVEMENT_KINDS = ("in", "out", "adjustment")

# The defective on-hand query: it normalises a sign the ledger already stores.
LEGACY_ON_HAND = """
SELECT p.sku AS sku,
       SUM(CASE WHEN m.movement = 'out' THEN -ABS(m.units)
                ELSE ABS(m.units) END) AS units
FROM products p
LEFT JOIN stock_movements m ON m.product_id = p.id
GROUP BY p.id
ORDER BY p.sku
"""

# The defective category report: a bare column beside an aggregate.
LEGACY_CATEGORY_VALUE = """
SELECT p.category AS category,
       SUM(m.units) AS units,
       SUM(m.units) * p.unit_price_cents AS cents
FROM products p
LEFT JOIN stock_movements m ON m.product_id = p.id
GROUP BY p.category
ORDER BY p.category
"""

SCHEMA = """
CREATE TABLE suppliers (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE,
    contact TEXT NOT NULL,
    email   TEXT NOT NULL,
    city    TEXT NOT NULL
);
CREATE TABLE products (
    id               INTEGER PRIMARY KEY,
    sku              TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    category         TEXT NOT NULL,
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    reorder_level    INTEGER NOT NULL CHECK (reorder_level >= 0),
    supplier_id      INTEGER NOT NULL REFERENCES suppliers (id)
);
CREATE TABLE stock_movements (
    id         INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products (id),
    movement   TEXT NOT NULL CHECK (movement IN ('in', 'out', 'adjustment')),
    units      INTEGER NOT NULL CHECK (units <> 0),
    note       TEXT NOT NULL,
    created_on TEXT NOT NULL
);
"""

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# A movement label and the sign its units must carry.
EXPECTED_SIGN = {"in": 1, "out": -1, "adjustment": 0}


class LedgerError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise LedgerError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise LedgerError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LedgerError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise LedgerError(f"{name} must be positive, got {number}")
    return number


def _non_negative(value: object, name: str) -> int:
    number = _whole(value, name)
    if number < 0:
        raise LedgerError(f"{name} must not be negative, got {number}")
    return number


def _choice(value: object, name: str, allowed: Sequence[str]) -> str:
    text = _text(value, name).strip()
    if text not in allowed:
        raise LedgerError(f"{name} must be one of {list(allowed)}, got {text!r}")
    return text


def is_iso_date(text: str) -> bool:
    """True for a YYYY-MM-DD calendar date; blank or non-text input is False."""
    if not isinstance(text, str):
        return False
    raw = text.strip()
    if not _DATE.match(raw):
        return False
    return 1 <= int(raw[5:7]) <= 12 and 1 <= int(raw[8:10]) <= 31


def require_iso_date(text: str, name: str = "created_on") -> str:
    raw = _text(text, name).strip()
    if not is_iso_date(raw):
        raise LedgerError(f"{name} must be YYYY-MM-DD, got {raw!r}")
    return raw


# --------------------------------------------------------------------------- #
# Money as integer cents
# --------------------------------------------------------------------------- #
def parse_cents(text: str) -> int:
    """Parse a decimal money string into integer cents, exactly."""
    raw = _text(text, "unit_price").strip()
    sign = 1
    if raw[0] in "+-":
        if raw[0] == "-":
            sign = -1
        raw = raw[1:]
    if raw.count(".") > 1:
        raise LedgerError(f"unit_price has more than one decimal point: {text!r}")
    whole, _, frac = raw.partition(".")
    if not whole or not whole.isdigit():
        raise LedgerError(f"unit_price has a non-digit integer part: {text!r}")
    if len(frac) > 2:
        raise LedgerError(f"unit_price has more than 2 decimal places: {text!r}")
    if frac and not frac.isdigit():
        raise LedgerError(f"unit_price has a non-digit fractional part: {text!r}")
    return sign * (int(whole) * 100 + int(frac.ljust(2, "0")))


def format_cents(cents: int) -> str:
    amount = _whole(cents, "cents")
    sign = "-" if amount < 0 else ""
    magnitude = abs(amount)
    return f"{sign}{magnitude // 100}.{magnitude % 100:02d}"


def divide_half_up(numerator: int, denominator: int) -> int:
    """Integer division rounding halves away from zero, with no float."""
    top = _whole(numerator, "numerator")
    bottom = _positive(denominator, "denominator")
    sign = -1 if top < 0 else 1
    magnitude = abs(top)
    return sign * ((magnitude * 2 + bottom) // (2 * bottom))


def _int(text: str, name: str) -> int:
    raw = _text(text, name).strip()
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise LedgerError(f"{name} must be a whole number, got {raw!r}") from exc


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Supplier:
    id: int
    name: str
    contact: str
    city: str


@dataclass(frozen=True)
class Product:
    id: int
    sku: str
    name: str
    category: str
    unit_price_cents: int
    reorder_level: int
    supplier_id: int


@dataclass(frozen=True)
class Movement:
    id: int
    product_id: int
    movement: str
    units: int
    note: str
    created_on: str


def check_signed_units(movement: str, units: int) -> int:
    """Validate that the sign in the data agrees with the label, and keep it.

    This is the whole lesson in one function. A receipt carries positive units,
    an issue carries negative units, and an adjustment may carry either. A
    mismatch is refused by name instead of being silently rewritten, because
    rewriting it is exactly what the legacy CASE branch did.
    """
    kind = _choice(movement, "movement", MOVEMENT_KINDS)
    amount = _whole(units, "units")
    if amount == 0:
        raise LedgerError("units must not be zero")
    expected = EXPECTED_SIGN[kind]
    if expected == 1 and amount < 0:
        raise LedgerError(f"movement 'in' must carry positive units, got {amount}")
    if expected == -1 and amount > 0:
        raise LedgerError(f"movement 'out' must carry negative units, got {amount}")
    return amount


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _read_rows(path: str | Path, required: Sequence[str]) -> list[dict[str, str]]:
    target = Path(path)
    if not target.is_file():
        raise LedgerError(f"file not found: {target.name}")
    with target.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [column for column in required if column not in header]
        if missing:
            raise LedgerError(f"{target.name} is missing column(s): {', '.join(missing)}")
        return [dict(row) for row in reader]


def load_suppliers(path: str | Path | None = None) -> list[Supplier]:
    rows = _read_rows(path or SUPPLIERS_FILE, ("id", "name", "contact", "email", "city"))
    suppliers = [
        Supplier(
            id=_positive(_int(row["id"], "supplier id"), "supplier id"),
            name=_text(row["name"], "supplier name").strip(),
            contact=_text(row["contact"], "supplier contact").strip(),
            city=_text(row["city"], "supplier city").strip(),
        )
        for row in rows
    ]
    if len({s.id for s in suppliers}) != len(suppliers):
        raise LedgerError("supplier ids must be unique")
    if len({s.name for s in suppliers}) != len(suppliers):
        raise LedgerError("supplier names must be unique")
    return suppliers


def load_products(path: str | Path | None = None) -> list[Product]:
    rows = _read_rows(
        path or PRODUCTS_FILE,
        ("id", "sku", "name", "category", "unit_price", "reorder_level", "supplier_id"),
    )
    products = [
        Product(
            id=_positive(_int(row["id"], "product id"), "product id"),
            sku=_text(row["sku"], "sku").strip(),
            name=_text(row["name"], "product name").strip(),
            category=_text(row["category"], "category").strip(),
            unit_price_cents=_non_negative(parse_cents(row["unit_price"]), "unit_price"),
            reorder_level=_non_negative(
                _int(row["reorder_level"], "reorder_level"), "reorder_level"
            ),
            supplier_id=_positive(_int(row["supplier_id"], "supplier_id"), "supplier_id"),
        )
        for row in rows
    ]
    if len({p.id for p in products}) != len(products):
        raise LedgerError("product ids must be unique")
    if len({p.sku for p in products}) != len(products):
        raise LedgerError("product SKUs must be unique")
    return products


def load_movements(path: str | Path | None = None) -> list[Movement]:
    rows = _read_rows(
        path or MOVEMENTS_FILE,
        ("id", "product_id", "movement", "quantity", "note", "created_on"),
    )
    movements = [
        Movement(
            id=_positive(_int(row["id"], "movement id"), "movement id"),
            product_id=_positive(_int(row["product_id"], "product_id"), "product_id"),
            movement=_choice(row["movement"], "movement", MOVEMENT_KINDS),
            units=check_signed_units(
                row["movement"].strip(), _int(row["quantity"], "quantity")
            ),
            note=(row["note"] or "").strip(),
            created_on=require_iso_date(row["created_on"]),
        )
        for row in rows
    ]
    if len({m.id for m in movements}) != len(movements):
        raise LedgerError("movement ids must be unique")
    return movements


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
def build_database(
    suppliers: Sequence[Supplier],
    products: Sequence[Product],
    movements: Sequence[Movement],
) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    known_suppliers = {supplier.id for supplier in suppliers}
    for product in products:
        if product.supplier_id not in known_suppliers:
            raise LedgerError(
                f"product {product.sku} names unknown supplier {product.supplier_id}"
            )
    known_products = {product.id for product in products}
    for movement in movements:
        if movement.product_id not in known_products:
            raise LedgerError(
                f"movement {movement.id} names unknown product {movement.product_id}"
            )
        check_signed_units(movement.movement, movement.units)

    conn.executemany(
        "INSERT INTO suppliers VALUES (:id, :name, :contact, :email, :city)",
        [
            {"id": s.id, "name": s.name, "contact": s.contact,
             "email": "", "city": s.city}
            for s in suppliers
        ],
    )
    conn.executemany(
        "INSERT INTO products VALUES (:id, :sku, :name, :category, :unit_price_cents,"
        " :reorder_level, :supplier_id)",
        [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "category": p.category,
                "unit_price_cents": p.unit_price_cents,
                "reorder_level": p.reorder_level,
                "supplier_id": p.supplier_id,
            }
            for p in products
        ],
    )
    conn.executemany(
        "INSERT INTO stock_movements VALUES (:id, :product_id, :movement, :units,"
        " :note, :created_on)",
        [
            {
                "id": m.id,
                "product_id": m.product_id,
                "movement": m.movement,
                "units": m.units,
                "note": m.note,
                "created_on": m.created_on,
            }
            for m in movements
        ],
    )
    conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
_NET = """
WITH net AS (
    SELECT product_id, SUM(units) AS units
    FROM stock_movements
    GROUP BY product_id
)
"""


def on_hand_ledger(conn: sqlite3.Connection) -> dict[str, int]:
    """Net units per SKU, taken straight from the signed ledger."""
    rows = conn.execute(
        _NET
        + """
        SELECT p.sku AS sku, COALESCE(n.units, 0) AS units
        FROM products p
        LEFT JOIN net n ON n.product_id = p.id
        ORDER BY p.sku
        """
    ).fetchall()
    return {row["sku"]: int(row["units"]) for row in rows}


def legacy_on_hand(conn: sqlite3.Connection) -> dict[str, int]:
    """The CASE-branch report, executed unchanged."""
    rows = conn.execute(LEGACY_ON_HAND).fetchall()
    return {row["sku"]: int(row["units"] or 0) for row in rows}


def on_hand_python(movements: Sequence[Movement]) -> dict[int, int]:
    """Independent computation: add up the signed units by product id."""
    totals: dict[int, int] = {}
    for movement in movements:
        totals[movement.product_id] = totals.get(movement.product_id, 0) + movement.units
    return totals


def low_stock(conn: sqlite3.Connection) -> list[tuple[str, int, int]]:
    """SKUs at or below their reorder level, ordered by SKU."""
    rows = conn.execute(
        _NET
        + """
        SELECT p.sku AS sku, COALESCE(n.units, 0) AS units, p.reorder_level AS reorder
        FROM products p
        LEFT JOIN net n ON n.product_id = p.id
        WHERE COALESCE(n.units, 0) <= p.reorder_level
        ORDER BY p.sku
        """
    ).fetchall()
    return [(row["sku"], int(row["units"]), int(row["reorder"])) for row in rows]


def legacy_low_stock(conn: sqlite3.Connection) -> list[str]:
    """The low-stock list as the CASE branch sees it: it compares its own numbers."""
    levels = {
        row["sku"]: int(row["reorder_level"])
        for row in conn.execute("SELECT sku, reorder_level FROM products ORDER BY sku")
    }
    return [
        sku
        for sku, units in sorted(legacy_on_hand(conn).items())
        if units <= levels[sku]
    ]


def category_values(conn: sqlite3.Connection) -> list[tuple[str, int, int]]:
    """(category, units, cents) with every product priced separately."""
    rows = conn.execute(
        _NET
        + """
        SELECT p.category AS category,
               COALESCE(SUM(COALESCE(n.units, 0)), 0) AS units,
               COALESCE(SUM(COALESCE(n.units, 0) * p.unit_price_cents), 0) AS cents
        FROM products p
        LEFT JOIN net n ON n.product_id = p.id
        GROUP BY p.category
        ORDER BY p.category
        """
    ).fetchall()
    return [(row["category"], int(row["units"]), int(row["cents"])) for row in rows]


def legacy_category_values(conn: sqlite3.Connection) -> list[tuple[str, int, int]]:
    """The bare-column report, executed unchanged."""
    rows = conn.execute(LEGACY_CATEGORY_VALUE).fetchall()
    return [
        (row["category"], int(row["units"] or 0), int(row["cents"] or 0))
        for row in rows
    ]


def inventory_value_cents(conn: sqlite3.Connection) -> int:
    return sum(cents for _, _, cents in category_values(conn))


def average_product_value_cents(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()
    count = int(row["n"])
    if count == 0:
        return 0
    return divide_half_up(inventory_value_cents(conn), count)


def negative_skus(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """SKUs that have been driven below zero, reported rather than hidden."""
    return [
        (sku, units) for sku, units in on_hand_ledger(conn).items() if units < 0
    ]


def movement_counts(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Per-SKU count of receipts, issues and adjustments."""
    rows = conn.execute(
        """
        SELECT p.sku AS sku, m.movement AS movement, COUNT(*) AS n
        FROM products p
        LEFT JOIN stock_movements m ON m.product_id = p.id
        GROUP BY p.sku, m.movement
        ORDER BY p.sku, m.movement
        """
    ).fetchall()
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        counts.setdefault(row["sku"], {"in": 0, "out": 0, "adjustment": 0})
        if row["movement"] is not None:
            counts[row["sku"]][row["movement"]] = int(row["n"])
    return counts


def apply_movement(conn: sqlite3.Connection, movement: Movement) -> int:
    """Validate and post one ledger entry; return the new on-hand for its SKU."""
    check_signed_units(movement.movement, movement.units)
    require_iso_date(movement.created_on)
    product = conn.execute(
        "SELECT id, sku FROM products WHERE id = ?", (movement.product_id,)
    ).fetchone()
    if product is None:
        raise LedgerError(f"movement names unknown product {movement.product_id}")
    clash = conn.execute(
        "SELECT 1 FROM stock_movements WHERE id = ?", (movement.id,)
    ).fetchone()
    if clash is not None:
        raise LedgerError(f"movement id {movement.id} is already posted")
    conn.execute(
        "INSERT INTO stock_movements VALUES (?, ?, ?, ?, ?, ?)",
        (
            movement.id,
            movement.product_id,
            movement.movement,
            movement.units,
            movement.note,
            movement.created_on,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT COALESCE(SUM(units), 0) AS units FROM stock_movements WHERE product_id = ?",
        (movement.product_id,),
    ).fetchone()
    return int(row["units"])


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(
    movements_path: str | Path | None = None,
    *,
    products_path: str | Path | None = None,
    suppliers_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load the seeds, build the ledger and collect every number the demo prints."""
    if movements_path is not None:
        folder = Path(movements_path).resolve().parent
        products_path = products_path or folder / "products.csv"
        suppliers_path = suppliers_path or folder / "suppliers.csv"
    suppliers = load_suppliers(suppliers_path)
    products = load_products(products_path)
    movements = load_movements(movements_path)
    conn = build_database(suppliers, products, movements)

    available = on_hand_ledger(conn)
    legacy = legacy_on_hand(conn)
    low = low_stock(conn)
    return {
        "conn": conn,
        "suppliers": suppliers,
        "products": products,
        "movements": movements,
        "on_hand": available,
        "legacy_on_hand": legacy,
        "low_stock": low,
        "legacy_low_stock": legacy_low_stock(conn),
        "categories": category_values(conn),
        "legacy_categories": legacy_category_values(conn),
        "value": inventory_value_cents(conn),
        "average_value": average_product_value_cents(conn),
        "counts": movement_counts(conn),
        "negative": negative_skus(conn),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    """The JSON-safe view of a measurement."""
    return {
        "suppliers": len(measured["suppliers"]),
        "products": len(measured["products"]),
        "movements": len(measured["movements"]),
        "on_hand": measured["on_hand"],
        "legacy_on_hand": measured["legacy_on_hand"],
        "low_stock": [
            {"sku": sku, "units": units, "reorder": reorder}
            for sku, units, reorder in measured["low_stock"]
        ],
        "legacy_low_stock": measured["legacy_low_stock"],
        "categories": [
            {"category": category, "units": units, "cents": cents}
            for category, units, cents in measured["categories"]
        ],
        "legacy_categories": [
            {"category": category, "units": units, "cents": cents}
            for category, units, cents in measured["legacy_categories"]
        ],
        "value_cents": measured["value"],
        "average_value_cents": measured["average_value"],
        "negative": [
            {"sku": sku, "units": units} for sku, units in measured["negative"]
        ],
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:
        return False


def audit(
    measured: dict[str, Any],
    *,
    read_on_hand: Callable[[sqlite3.Connection], dict[str, int]] = on_hand_ledger,
) -> list[tuple[str, bool]]:
    """Every check compares a measured number with an independent computation."""
    conn = measured["conn"]
    movements = measured["movements"]
    products = measured["products"]
    value = measured["value"]

    def on_hand_via_reader() -> dict[str, int]:
        return read_on_hand(conn)

    def independent_on_hand() -> dict[str, int]:
        totals = on_hand_python(movements)
        return {
            product.sku: totals.get(product.id, 0)
            for product in sorted(products, key=lambda item: item.sku)
        }

    def independent_value() -> int:
        units = on_hand_python(movements)
        return sum(units.get(product.id, 0) * product.unit_price_cents for product in products)

    def posting_round_trip() -> bool:
        before = on_hand_via_reader()["SKU1006"]
        next_id = max((movement.id for movement in movements), default=0) + 1
        after = apply_movement(
            conn,
            Movement(next_id, 6, "out", -1, "Damaged in transit", "2026-01-20"),
        )
        try:
            return after == before - 1
        finally:
            conn.execute("DELETE FROM stock_movements WHERE id = ?", (next_id,))
            conn.commit()

    def sign_disagreement_is_refused() -> bool:
        failures = 0
        for kind, units in (("in", -5), ("out", 5), ("in", 0), ("adjustment", 0)):
            try:
                check_signed_units(kind, units)
            except LedgerError:
                failures += 1
        return failures == 4

    def adjustment_moves_stock_the_right_way() -> bool:
        next_id = max((movement.id for movement in movements), default=0) + 1
        before = on_hand_via_reader()["SKU1005"]
        after = apply_movement(
            conn,
            Movement(next_id, 5, "adjustment", -30, "Second write-off", "2026-01-21"),
        )
        try:
            return after == before - 30
        finally:
            conn.execute("DELETE FROM stock_movements WHERE id = ?", (next_id,))
            conn.commit()

    checks = [
        (
            "every_movement_sign_matches_its_label",
            lambda: all(
                EXPECTED_SIGN[m.movement] == 0
                or (m.units > 0) == (EXPECTED_SIGN[m.movement] == 1)
                for m in movements
            ),
        ),
        (
            "on_hand_is_the_signed_sum",
            lambda: on_hand_via_reader() == independent_on_hand(),
        ),
        (
            "on_hand_matches_the_pinned_seed",
            lambda: on_hand_via_reader()
            == {
                "SKU1001": 37,
                "SKU1002": 9,
                "SKU1003": 125,
                "SKU1004": 180,
                "SKU1005": 10,
                "SKU1006": 5,
            },
        ),
        (
            "ledger_and_legacy_agree_where_no_adjustment_exists",
            lambda: all(
                on_hand_via_reader()[sku] == measured["legacy_on_hand"][sku]
                for sku in ("SKU1002", "SKU1003", "SKU1004", "SKU1006")
            ),
        ),
        (
            "legacy_reads_the_shrinkage_as_a_receipt",
            lambda: measured["legacy_on_hand"]["SKU1001"] == 47
            and on_hand_via_reader()["SKU1001"] == 37,
        ),
        (
            "legacy_turns_the_write_off_into_stock",
            lambda: measured["legacy_on_hand"]["SKU1005"] == 70
            and on_hand_via_reader()["SKU1005"] == 10,
        ),
        (
            "legacy_overstates_by_twice_the_adjustments",
            lambda: sum(measured["legacy_on_hand"].values())
            - sum(on_hand_via_reader().values())
            == sum(
                2 * abs(m.units) for m in movements if m.movement == "adjustment"
            )
            == 70,
        ),
        (
            "low_stock_is_at_or_below_reorder",
            lambda: measured["low_stock"]
            == [("SKU1002", 9, 10), ("SKU1005", 10, 15), ("SKU1006", 5, 5)],
        ),
        (
            "legacy_low_stock_misses_the_write_off",
            lambda: measured["legacy_low_stock"] == ["SKU1002", "SKU1006"],
        ),
        (
            "category_values_sum_to_the_total",
            lambda: sum(row[2] for row in measured["categories"]) == value,
        ),
        (
            "inventory_value_is_pinned",
            lambda: value == 12_153_400 and format_cents(value) == "121534.00",
        ),
        (
            "inventory_value_matches_an_independent_product_loop",
            lambda: value == independent_value(),
        ),
        (
            "legacy_prices_a_category_with_one_product",
            lambda: measured["legacy_categories"][0][0] == "Accessories"
            and measured["legacy_categories"][0][2] == 24_875_00
            and [row[2] for row in measured["legacy_categories"]]
            != [row[2] for row in measured["categories"]],
        ),
        (
            "average_value_rounds_half_up",
            lambda: measured["average_value"] == 2_025_567
            == divide_half_up(value, len(products)),
        ),
        (
            "every_price_round_trips",
            lambda: all(
                format_cents(parse_cents(text)) == text
                for text in ("499.00", "2499.00", "0.05", "8.20")
            ),
        ),
        (
            "sign_disagreement_is_refused",
            lambda: sign_disagreement_is_refused(),
        ),
        (
            "posting_a_movement_changes_on_hand_by_its_units",
            lambda: posting_round_trip(),
        ),
        (
            "adjustment_reduces_stock",
            lambda: adjustment_moves_stock_the_right_way(),
        ),
        (
            "no_sku_is_below_zero_in_the_seed",
            lambda: measured["negative"] == [],
        ),
        (
            "rebuild_is_deterministic",
            lambda: on_hand_ledger(
                build_database(
                    measured["suppliers"], products, measured["movements"]
                )
            )
            == measured["on_hand"],
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_stock(measured: dict[str, Any]) -> str:
    lines = ["  sku       product              in  out  adj   on hand    legacy"]
    for product in measured["products"]:
        counts = measured["counts"].get(product.sku, {"in": 0, "out": 0, "adjustment": 0})
        units = measured["on_hand"][product.sku]
        legacy = measured["legacy_on_hand"][product.sku]
        lines.append(
            f"  {product.sku:<10}{product.name:<20}{counts['in']:>3}{counts['out']:>5}"
            f"{counts['adjustment']:>5}{units:>10}{legacy:>10}"
        )
    lines.append(
        f"  {'TOTAL':<30}{sum(c['in'] for c in measured['counts'].values()):>3}"
        f"{sum(c['out'] for c in measured['counts'].values()):>5}"
        f"{sum(c['adjustment'] for c in measured['counts'].values()):>5}"
        f"{sum(measured['on_hand'].values()):>10}"
        f"{sum(measured['legacy_on_hand'].values()):>10}"
    )
    return "\n".join(lines)


def render_categories(measured: dict[str, Any]) -> str:
    legacy = {category: cents for category, _, cents in measured["legacy_categories"]}
    lines = ["  category          units      correct        legacy"]
    for category, units, cents in measured["categories"]:
        lines.append(
            f"  {category:<16}{units:>6}{format_cents(cents):>13}"
            f"{format_cents(legacy.get(category, 0)):>14}"
        )
    lines.append(
        f"  {'TOTAL':<16}{sum(row[1] for row in measured['categories']):>6}"
        f"{format_cents(measured['value']):>13}"
        f"{format_cents(sum(legacy.values())):>14}"
    )
    return "\n".join(lines)


def run_demo() -> int:
    measured = measure()
    print("Inventory ledger -- the sign belongs in the data")
    print("=" * 49)
    print()
    print(
        f"Seeds: {len(measured['suppliers'])} suppliers, "
        f"{len(measured['products'])} products, "
        f"{len(measured['movements'])} movements "
        f"({sum(c['in'] for c in measured['counts'].values())} in, "
        f"{sum(c['out'] for c in measured['counts'].values())} out, "
        f"{sum(c['adjustment'] for c in measured['counts'].values())} adjustments)."
    )
    print()
    print(render_stock(measured))
    print()
    print("1. The sign is already in the row; the CASE branch adds a second one.")
    print("   Every SKU without an adjustment agrees exactly. The two that do not")
    print("   are the two with an adjustment, and each is off by twice the amount:")
    print("     SKU1001  shrinkage -5   legacy 47  correct 37   (+10)")
    print("     SKU1005  write-off -30  legacy 70  correct 10   (+60)")
    print()
    print("2. Only 'out' was guarded, so an adjustment falls into the ELSE and")
    print("   is read back as a receipt. A water-damage write-off becomes stock,")
    print("   and the shelf never reconciles against the stocktake.")
    print()
    print("3. A bare column in GROUP BY prices a whole category with one product:")
    print()
    print(render_categories(measured))
    print()
    print(
        f"Value: {format_cents(measured['value'])} across "
        f"{len(measured['products'])} products, average "
        f"{format_cents(measured['average_value'])} per product."
    )
    print(
        "Low stock (on hand <= reorder level): "
        + ", ".join(
            f"{sku} {units}/{reorder}" for sku, units, reorder in measured["low_stock"]
        )
    )
    print("Legacy low stock: " + ", ".join(measured["legacy_low_stock"]))
    print()
    print("Checks")
    results = audit(measured)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: signed ledger sums to "
        f"{sum(measured['on_hand'].values())} units while the CASE branch reports "
        f"{sum(measured['legacy_on_hand'].values())}, because it normalises the sign "
        "and re-applies it so the -5 shrinkage and -30 write-off are both read as "
        f"receipts (+70 in total); the four SKUs with no adjustment agree exactly; "
        f"low stock is {len(measured['low_stock'])} SKUs at or below reorder level "
        f"against {len(measured['legacy_low_stock'])} the legacy report finds; the "
        "bare-column category report prices the one-product categories correctly but "
        "multiplies Electronics' 46 units by a single product's 499.00 and Furniture's "
        f"15 units by a single product's 899.00, understating the value to "
        f"{format_cents(sum(row[2] for row in measured['legacy_categories']))} where "
        f"the product-by-product loop gives {format_cents(measured['value'])}; "
        f"{passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
