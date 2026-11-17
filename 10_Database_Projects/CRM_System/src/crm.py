"""Money is not a float, and a total is not a sum across two joins.

The legacy CRM reported revenue with a single query:

    SELECT c.name, SUM(d.value) AS total
    FROM customers c
    LEFT JOIN deals d        ON d.customer_id = c.id
    LEFT JOIN interactions i ON i.customer_id = c.id
    GROUP BY c.id

and it stored `value` as a REAL column. Two independent defects live in those
two lines, and both push the same report in the same direction: too big, and
slightly off.

**Fan-out.** Joining two one-to-many tables inside one GROUP BY multiplies the
rows of the first by the count of the second. Neha Gupta has one deal and two
interactions, so her 240000.10 is counted twice and her total reads 480000.20.
The query is arithmetically consistent and completely false. Pre-aggregating
each side before the join -- or simply never joining the second table -- is the
only fix that survives somebody logging one more interaction.

**Binary money.** `int(value * 100)` looks like a cents conversion and is a
truncation: `float("8.20")` is `8.199999999999999289`, so
`int(float("8.20") * 100)` is `819` and the customer loses a cent. The three
seed deals below are large enough that the error cancels, which is exactly why
this helper survives review -- it fails on `0.29`, `1.15`, `2.05` and `8.20`,
and those are the values that will appear in the first discount you issue.
Money is parsed from text straight into integer cents with no float in the
path, and any division uses an explicit `divide_half_up`.

The rebuild keeps the legacy query and the legacy conversion as executable
objects, runs both against the same seed files, and prints the gap.
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CUSTOMERS_FILE = DATA_DIR / "customers.csv"
DEALS_FILE = DATA_DIR / "deals.csv"
INTERACTIONS_FILE = DATA_DIR / "interactions.csv"

STAGES = ("prospecting", "proposal", "negotiation", "won", "lost")
KINDS = ("call", "email", "meeting", "note")
CLOSED_STAGES = ("won", "lost")

# The defective query, kept as a string so the demo can print it and the tests
# can execute it against the same database as the corrected one.
LEGACY_TOP_CUSTOMERS = """
SELECT c.name AS name, SUM(d.value_cents) AS cents
FROM customers c
LEFT JOIN deals d        ON d.customer_id = c.id
LEFT JOIN interactions i ON i.customer_id = c.id
GROUP BY c.id
ORDER BY cents DESC, c.name
"""

# The defective conversion, kept executable so the lost cent is measurable.
LEGACY_TO_CENTS = "cents = int(float(text) * 100)"

SCHEMA = """
CREATE TABLE customers (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    phone      TEXT NOT NULL,
    company    TEXT NOT NULL,
    created_on TEXT NOT NULL
);
CREATE TABLE deals (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    title       TEXT NOT NULL,
    value_cents INTEGER NOT NULL CHECK (value_cents >= 0),
    stage       TEXT NOT NULL,
    close_on    TEXT NOT NULL
);
CREATE TABLE interactions (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    kind        TEXT NOT NULL,
    summary     TEXT NOT NULL,
    created_on  TEXT NOT NULL
);
"""


class CrmError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise CrmError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise CrmError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CrmError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise CrmError(f"{name} must be positive, got {number}")
    return number


def _choice(value: object, name: str, allowed: Sequence[str]) -> str:
    text = _text(value, name)
    if text not in allowed:
        raise CrmError(f"{name} must be one of {list(allowed)}, got {text!r}")
    return text


# --------------------------------------------------------------------------- #
# Money as integer cents
# --------------------------------------------------------------------------- #
def parse_cents(text: str) -> int:
    """Parse a decimal money string into integer cents, exactly."""
    raw = _text(text, "money").strip()
    sign = 1
    if raw[0] in "+-":
        if raw[0] == "-":
            sign = -1
        raw = raw[1:]
    if raw.count(".") > 1:
        raise CrmError(f"money has more than one decimal point: {text!r}")
    whole, _, frac = raw.partition(".")
    if not whole or not whole.isdigit():
        raise CrmError(f"money has a non-digit integer part: {text!r}")
    if len(frac) > 2:
        raise CrmError(f"money has more than 2 decimal places: {text!r}")
    if frac and not frac.isdigit():
        raise CrmError(f"money has a non-digit fractional part: {text!r}")
    frac = frac.ljust(2, "0")
    return sign * (int(whole) * 100 + int(frac))


def legacy_parse_cents(text: str) -> int:
    """The defective conversion: `int(float(text) * 100)` truncates."""
    _text(text, "money")
    return int(float(text) * 100)


def format_cents(cents: int) -> str:
    """Render integer cents as a fixed two-decimal string."""
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


# --------------------------------------------------------------------------- #
# Records and loading
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Customer:
    id: int
    name: str
    email: str
    company: str
    created_on: str


@dataclass(frozen=True)
class Deal:
    id: int
    customer_id: int
    title: str
    cents: int
    stage: str
    close_on: str


@dataclass(frozen=True)
class Interaction:
    id: int
    customer_id: int
    kind: str
    created_on: str


def _read_rows(path: str | Path, required: Sequence[str]) -> list[dict[str, str]]:
    target = Path(path)
    if not target.is_file():
        raise CrmError(f"file not found: {target.name}")
    with target.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [column for column in required if column not in header]
        if missing:
            raise CrmError(f"{target.name} is missing column(s): {', '.join(missing)}")
        return [dict(row) for row in reader]


def load_customers(path: str | Path | None = None) -> list[Customer]:
    rows = _read_rows(path or CUSTOMERS_FILE, ("id", "name", "email", "company", "created_on"))
    customers: list[Customer] = []
    for row in rows:
        customers.append(
            Customer(
                id=_positive(_int(row["id"], "customer id"), "customer id"),
                name=_text(row["name"], "customer name").strip(),
                email=_text(row["email"], "customer email").strip(),
                company=(row["company"] or "").strip(),
                created_on=_text(row["created_on"], "created_on").strip(),
            )
        )
    ids = [c.id for c in customers]
    if len(set(ids)) != len(ids):
        raise CrmError("customer ids must be unique")
    emails = [c.email.lower() for c in customers]
    if len(set(emails)) != len(emails):
        raise CrmError("customer emails must be unique")
    return customers


def load_deals(path: str | Path | None = None) -> list[Deal]:
    rows = _read_rows(path or DEALS_FILE, ("id", "customer_id", "title", "value", "stage", "close_on"))
    deals: list[Deal] = []
    for row in rows:
        deals.append(
            Deal(
                id=_positive(_int(row["id"], "deal id"), "deal id"),
                customer_id=_positive(_int(row["customer_id"], "customer_id"), "customer_id"),
                title=_text(row["title"], "deal title").strip(),
                cents=parse_cents(row["value"]),
                stage=_choice(row["stage"].strip(), "stage", STAGES),
                close_on=_text(row["close_on"], "close_on").strip(),
            )
        )
    if len({d.id for d in deals}) != len(deals):
        raise CrmError("deal ids must be unique")
    return deals


def load_interactions(path: str | Path | None = None) -> list[Interaction]:
    rows = _read_rows(path or INTERACTIONS_FILE, ("id", "customer_id", "kind", "created_on"))
    interactions: list[Interaction] = []
    for row in rows:
        interactions.append(
            Interaction(
                id=_positive(_int(row["id"], "interaction id"), "interaction id"),
                customer_id=_positive(_int(row["customer_id"], "customer_id"), "customer_id"),
                kind=_choice(row["kind"].strip(), "kind", KINDS),
                created_on=_text(row["created_on"], "created_on").strip(),
            )
        )
    if len({i.id for i in interactions}) != len(interactions):
        raise CrmError("interaction ids must be unique")
    return interactions


def _int(text: str, name: str) -> int:
    raw = _text(text, name).strip()
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise CrmError(f"{name} must be a whole number, got {raw!r}") from exc


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
def build_database(
    customers: Sequence[Customer],
    deals: Sequence[Deal],
    interactions: Sequence[Interaction],
) -> sqlite3.Connection:
    """Build an in-memory database from validated records."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    known = {customer.id for customer in customers}
    for deal in deals:
        if deal.customer_id not in known:
            raise CrmError(f"deal {deal.id} names unknown customer {deal.customer_id}")
    for interaction in interactions:
        if interaction.customer_id not in known:
            raise CrmError(
                f"interaction {interaction.id} names unknown customer {interaction.customer_id}"
            )
    conn.executemany(
        "INSERT INTO customers VALUES (:id, :name, :email, :phone, :company, :created_on)",
        [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "phone": "",
                "company": c.company,
                "created_on": c.created_on,
            }
            for c in customers
        ],
    )
    conn.executemany(
        "INSERT INTO deals VALUES (:id, :customer_id, :title, :cents, :stage, :close_on)",
        [
            {
                "id": d.id,
                "customer_id": d.customer_id,
                "title": d.title,
                "cents": d.cents,
                "stage": d.stage,
                "close_on": d.close_on,
            }
            for d in deals
        ],
    )
    conn.executemany(
        "INSERT INTO interactions VALUES (:id, :customer_id, :kind, :summary, :created_on)",
        [
            {
                "id": i.id,
                "customer_id": i.customer_id,
                "kind": i.kind,
                "summary": "",
                "created_on": i.created_on,
            }
            for i in interactions
        ],
    )
    conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# Reporting queries
# --------------------------------------------------------------------------- #
def legacy_top_customers(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """The fan-out query, executed unchanged."""
    rows = conn.execute(LEGACY_TOP_CUSTOMERS).fetchall()
    return [(row["name"], int(row["cents"] or 0)) for row in rows]


def top_customers(conn: sqlite3.Connection) -> list[tuple[str, int, int]]:
    """Per-customer totals, pre-aggregated so interactions cannot fan out."""
    rows = conn.execute(
        """
        WITH totals AS (
            SELECT customer_id, SUM(value_cents) AS cents, COUNT(*) AS deals
            FROM deals
            GROUP BY customer_id
        )
        SELECT c.name AS name,
               COALESCE(t.cents, 0) AS cents,
               COALESCE(t.deals, 0) AS deals
        FROM customers c
        LEFT JOIN totals t ON t.customer_id = c.id
        ORDER BY cents DESC, c.name
        """
    ).fetchall()
    return [(row["name"], int(row["cents"]), int(row["deals"])) for row in rows]


def interaction_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT c.name AS name, COUNT(i.id) AS n
        FROM customers c
        LEFT JOIN interactions i ON i.customer_id = c.id
        GROUP BY c.id
        ORDER BY c.name
        """
    ).fetchall()
    return {row["name"]: int(row["n"]) for row in rows}


def stage_total_cents(conn: sqlite3.Connection, stages: Iterable[str]) -> int:
    wanted = tuple(stages)
    if not wanted:
        raise CrmError("stages must not be empty")
    placeholders = ",".join("?" for _ in wanted)
    row = conn.execute(
        f"SELECT COALESCE(SUM(value_cents), 0) AS cents FROM deals WHERE stage IN ({placeholders})",
        wanted,
    ).fetchone()
    return int(row["cents"])


def won_cents(conn: sqlite3.Connection) -> int:
    return stage_total_cents(conn, ("won",))


def open_pipeline_cents(conn: sqlite3.Connection) -> int:
    return stage_total_cents(conn, [stage for stage in STAGES if stage not in CLOSED_STAGES])


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    def one(table: str) -> int:
        return int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])

    return {"customers": one("customers"), "deals": one("deals"), "interactions": one("interactions")}


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(
    deals_path: str | Path | None = None,
    *,
    customers_path: str | Path | None = None,
    interactions_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load the seeds, build the database and collect every number the demo prints."""
    if deals_path is not None:
        folder = Path(deals_path).resolve().parent
        customers_path = customers_path or folder / "customers.csv"
        interactions_path = interactions_path or folder / "interactions.csv"
    customers = load_customers(customers_path)
    deals = load_deals(deals_path)
    interactions = load_interactions(interactions_path)
    conn = build_database(customers, deals, interactions)

    true_rows = top_customers(conn)
    legacy_rows = legacy_top_customers(conn)
    true_total = sum(cents for _, cents, _ in true_rows)
    legacy_total = sum(cents for _, cents in legacy_rows)
    won = won_cents(conn)
    open_pipeline = open_pipeline_cents(conn)

    return {
        "conn": conn,
        "customers": customers,
        "deals": deals,
        "interactions": interactions,
        "true_rows": true_rows,
        "legacy_rows": legacy_rows,
        "true_total": true_total,
        "legacy_total": legacy_total,
        "won": won,
        "open": open_pipeline,
        "counts": counts(conn),
        "interactions_per_customer": interaction_counts(conn),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    """The JSON-safe view of a measurement."""
    return {
        "customers": measured["counts"]["customers"],
        "deals": measured["counts"]["deals"],
        "interactions": measured["counts"]["interactions"],
        "correct": {
            "total_cents": measured["true_total"],
            "total": format_cents(measured["true_total"]),
            "won_cents": measured["won"],
            "open_cents": measured["open"],
            "rows": [
                {"name": name, "cents": cents, "deals": deals}
                for name, cents, deals in measured["true_rows"]
            ],
        },
        "legacy": {
            "total_cents": measured["legacy_total"],
            "total": format_cents(measured["legacy_total"]),
            "rows": [{"name": name, "cents": cents} for name, cents in measured["legacy_rows"]],
        },
        "overstatement_cents": measured["legacy_total"] - measured["true_total"],
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
    read_totals=top_customers,
) -> list[tuple[str, bool]]:
    """Every check compares a measured number with an independent computation."""
    conn = measured["conn"]
    deals = measured["deals"]
    independent_total = sum(deal.cents for deal in deals)
    probes = ("0.29", "1.15", "2.05", "8.20", "95000.25", "240000.10")

    def totals_via_reader() -> list[tuple[str, int, int]]:
        rows = read_totals(conn)
        return list(rows)

    def independent_rows() -> list[tuple[str, int, int]]:
        by_customer: dict[int, int] = {}
        for deal in deals:
            by_customer[deal.customer_id] = by_customer.get(deal.customer_id, 0) + deal.cents
        pairs = []
        for customer in measured["customers"]:
            pairs.append((customer.name, by_customer.get(customer.id, 0), 0))
        return sorted(pairs, key=lambda row: (-row[1], row[0]))

    def interaction_robustness() -> bool:
        before = [cents for _, cents, _ in top_customers(conn)]
        extra = Interaction(
            id=max((i.id for i in measured["interactions"]), default=0) + 1,
            customer_id=measured["customers"][0].id,
            kind="note",
            created_on="2026-02-01",
        )
        grown = build_database(measured["customers"], deals, [*measured["interactions"], extra])
        after = [cents for _, cents, _ in top_customers(grown)]
        return before == after

    checks = [
        (
            "parse_cents_keeps_the_cent",
            lambda: parse_cents("240000.10") == 24_000_010,
        ),
        (
            "legacy_parse_survives_the_large_seeds",
            lambda: legacy_parse_cents("240000.10") == 24_000_010,
        ),
        (
            "legacy_parse_drops_the_cent_on_small_values",
            lambda: legacy_parse_cents("8.20") == 819
            and legacy_parse_cents("0.29") == 28,
        ),
        (
            "legacy_total_overstates",
            lambda: measured["legacy_total"] == 61_700_050
            and measured["true_total"] == 37_700_040,
        ),
        (
            "overstatement_is_the_duplicated_deal",
            lambda: measured["legacy_total"] - measured["true_total"] == 24_000_010,
        ),
        (
            "correct_rows_match_independent_sum",
            lambda: [row[:2] for row in totals_via_reader()] == [row[:2] for row in independent_rows()],
        ),
        (
            "total_ignores_interaction_count",
            lambda: interaction_robustness(),
        ),
        (
            "won_plus_open_equals_everything",
            lambda: measured["won"] + measured["open"] == independent_total,
        ),
        (
            "open_pipeline_excludes_closed_stages",
            lambda: measured["open"] == 33_500_035 and measured["won"] == 4_200_005,
        ),
        (
            "every_probe_value_round_trips",
            lambda: all(format_cents(parse_cents(value)) == _normalise(value) for value in probes),
        ),
        (
            "legacy_conversion_loses_a_cent_on_small_values",
            lambda: (
                legacy_parse_cents("0.29") == 28
                and legacy_parse_cents("1.15") == 114
                and legacy_parse_cents("2.05") == 204
                and legacy_parse_cents("8.20") == 819
                and all(parse_cents(value) > legacy_parse_cents(value)
                        for value in ("0.29", "1.15", "2.05", "8.20"))
            ),
        ),
        (
            "divide_half_up_rounds_away_from_zero",
            lambda: (
                divide_half_up(5, 2) == 3
                and divide_half_up(1, 3) == 0
                and divide_half_up(2, 3) == 1
                and divide_half_up(-5, 2) == -3
                and divide_half_up(7, 2) == 4
            ),
        ),
        (
            "reports_disagree_row_by_row",
            lambda: [row[:2] for row in top_customers(conn)] != measured["legacy_rows"],
        ),
        (
            "rebuild_is_deterministic",
            lambda: top_customers(
                build_database(measured["customers"], deals, measured["interactions"])
            )
            == top_customers(conn),
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


def _normalise(value: str) -> str:
    """Render a hand-written money string in canonical two-decimal form."""
    return format_cents(parse_cents(value))


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_rows(measured: dict[str, Any]) -> str:
    legacy = dict(measured["legacy_rows"])
    per_customer = measured["interactions_per_customer"]
    lines = ["  customer          interactions      legacy        correct"]
    for name, cents, _ in measured["true_rows"]:
        lines.append(
            f"  {name:<18}{per_customer.get(name, 0):>12}"
            f"{format_cents(legacy.get(name, 0)):>14}{format_cents(cents):>15}"
        )
    lines.append(
        f"  {'TOTAL':<18}{sum(per_customer.values()):>12}"
        f"{format_cents(measured['legacy_total']):>14}"
        f"{format_cents(measured['true_total']):>15}"
    )
    return "\n".join(lines)


def run_demo() -> int:
    measured = measure()
    print("CRM revenue report -- fan-out and binary money")
    print("=" * 46)
    print()
    print("The legacy query joins deals and interactions in one GROUP BY, so")
    print("each deal row is repeated once per interaction on the same customer:")
    print()
    for line in LEGACY_TOP_CUSTOMERS.strip().splitlines():
        print(f"  {line}")
    print()
    print(
        f"Seeds: {measured['counts']['customers']} customers, "
        f"{measured['counts']['deals']} deals, "
        f"{measured['counts']['interactions']} interactions."
    )
    print()
    print(render_rows(measured))
    print()
    print(
        "The legacy total is "
        f"{format_cents(measured['legacy_total'] - measured['true_total'])} too high --"
    )
    print("exactly Neha's deal, counted once per interaction.")
    print()
    print("Binary money: the legacy conversion is " + repr(LEGACY_TO_CENTS))
    print("  the large seed values survive it; small amounts do not:")
    for value in ("0.29", "1.15", "2.05", "8.20"):
        print(
            f"  {value:>10}  legacy {legacy_parse_cents(value):>9} cents"
            f"   correct {parse_cents(value):>9} cents"
        )
    print()
    print(f"Won: {format_cents(measured['won'])}   Open pipeline: {format_cents(measured['open'])}")
    print()
    print("Checks")
    results = audit(measured)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: legacy fan-out total "
        f"{format_cents(measured['legacy_total'])} vs pre-aggregated "
        f"{format_cents(measured['true_total'])}, overstatement "
        f"{format_cents(measured['legacy_total'] - measured['true_total'])} equals the "
        f"duplicated deal; int(float*100) keeps 240000.10 exact but reports "
        f"0.29, 1.15, 2.05 and 8.20 one cent low; won "
        f"{format_cents(measured['won'])} + open {format_cents(measured['open'])} "
        f"= {format_cents(measured['true_total'])}; totals unchanged by an extra "
        f"interaction; {passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
