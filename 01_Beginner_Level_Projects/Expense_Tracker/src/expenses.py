"""An expense tracker: CSV in, monthly aggregates, budget checks and outlier
detection out.

Three questions, three answers:

    how much did I spend?           monthly_totals / category_totals
    was I inside my budget?         budget_report
    which charge was abnormal?      find_anomalies

The last one is the interesting one. A single ``max()`` would call the biggest
charge "the anomaly" even when it is a normal month. Instead each expense is
scored against the other expenses *in its own category* using the modified
z-score of Iglewicz and Hoaglin:

    z = 0.6745 * (x - median) / MAD,   MAD = median(|x - median|)

MAD is used instead of the standard deviation because one huge outlier inflates
the standard deviation enough to hide itself; the median and MAD do not move.
A score of 3.5 or more is the published cut-off, and a category needs at least
three expenses before anything in it can be judged at all.

Fully offline: a CSV file in, numbers out.
"""

from __future__ import annotations

import csv
import statistics
import tempfile
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path
from typing import Iterable, Sequence

CATEGORIES = ("dining", "groceries", "shopping", "transport", "utilities")
CSV_FIELDS = ("date", "category", "description", "amount")
MAX_DESCRIPTION = 60
ANOMALY_THRESHOLD = 3.5
MIN_ANOMALY_SAMPLE = 3


class ExpenseError(ValueError):
    """An expense, file or query that cannot be used."""


# --------------------------------------------------------------------------- #
# Expense
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Expense:
    """One dated charge. Amounts are positive and rounded to cents."""

    date: Date
    category: str
    description: str
    amount: float

    def __post_init__(self) -> None:
        if not isinstance(self.date, Date):
            raise ExpenseError("date must be a datetime.date")
        category = str(self.category).strip().lower()
        if category not in CATEGORIES:
            raise ExpenseError(
                f"unknown category {self.category!r} "
                f"(expected one of: {', '.join(CATEGORIES)})")
        object.__setattr__(self, "category", category)
        description = " ".join(str(self.description).split())
        if not description:
            raise ExpenseError("description must not be empty")
        if len(description) > MAX_DESCRIPTION:
            raise ExpenseError(
                f"description is longer than {MAX_DESCRIPTION} characters")
        object.__setattr__(self, "description", description)
        try:
            amount = float(self.amount)
        except (TypeError, ValueError):
            raise ExpenseError(f"amount {self.amount!r} is not a number") from None
        if amount != amount:
            raise ExpenseError("amount must be a number, not NaN")
        amount = round(amount, 2)
        if amount <= 0:
            raise ExpenseError(f"amount must be greater than zero, got {amount}")
        object.__setattr__(self, "amount", amount)

    @property
    def month(self) -> str:
        return f"{self.date.year:04d}-{self.date.month:02d}"

    def to_row(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "category": self.category,
            "description": self.description,
            "amount": f"{self.amount:.2f}",
        }

    @classmethod
    def from_row(cls, row: dict) -> "Expense":
        if not isinstance(row, dict):
            raise ExpenseError("a row must be a mapping")
        missing = [key for key in CSV_FIELDS if key not in row
                   or row[key] in (None, "")]
        if missing:
            raise ExpenseError(f"row is missing {', '.join(missing)}")
        return cls(
            date=parse_date(row["date"]),
            category=row["category"],
            description=row["description"],
            amount=row["amount"],
        )


def parse_date(value) -> Date:
    """Accept only ISO ``YYYY-MM-DD``; ambiguity is a bug, not a feature."""
    if isinstance(value, Date):
        return value
    text = str(value).strip()
    if not text:
        raise ExpenseError("date must not be empty")
    try:
        return Date.fromisoformat(text)
    except ValueError:
        raise ExpenseError(
            f"date {text!r} is not ISO YYYY-MM-DD") from None


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_csv(path: Path | str) -> list[Expense]:
    source = Path(path)
    if not source.exists():
        raise ExpenseError(f"file not found: {source}")
    expenses: list[Expense] = []
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in CSV_FIELDS
                   if name not in (reader.fieldnames or [])]
        if missing:
            raise ExpenseError(
                f"CSV is missing column(s): {', '.join(missing)}")
        for line, row in enumerate(reader, start=2):
            try:
                expenses.append(Expense.from_row(row))
            except ExpenseError as exc:
                raise ExpenseError(f"line {line}: {exc}") from exc
    return expenses


def write_csv(expenses: Iterable[Expense], path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for expense in sorted(expenses, key=lambda e: (e.date, e.category)):
            writer.writerow(expense.to_row())
    return target


# --------------------------------------------------------------------------- #
# Aggregates
# --------------------------------------------------------------------------- #
def _guard(expenses: Sequence[Expense]) -> None:
    for expense in expenses:
        if not isinstance(expense, Expense):
            raise ExpenseError("expected a list of Expense records")


def total(expenses: Sequence[Expense]) -> float:
    _guard(expenses)
    return round(sum(expense.amount for expense in expenses), 2)


def monthly_totals(expenses: Sequence[Expense]) -> dict[str, float]:
    _guard(expenses)
    totals: dict[str, float] = {}
    for expense in expenses:
        totals[expense.month] = round(
            totals.get(expense.month, 0.0) + expense.amount, 2)
    return dict(sorted(totals.items()))


def category_totals(expenses: Sequence[Expense]) -> dict[str, float]:
    _guard(expenses)
    totals: dict[str, float] = {}
    for expense in expenses:
        totals[expense.category] = round(
            totals.get(expense.category, 0.0) + expense.amount, 2)
    return dict(sorted(totals.items()))


def monthly_summary(expenses: Sequence[Expense]) -> list[dict]:
    """One row per month: total, count, biggest category, biggest expense."""
    _guard(expenses)
    rows: list[dict] = []
    for month, month_total in monthly_totals(expenses).items():
        within = [e for e in expenses if e.month == month]
        by_category: dict[str, float] = {}
        for expense in within:
            by_category[expense.category] = round(
                by_category.get(expense.category, 0.0) + expense.amount, 2)
        top_category = min(by_category, key=lambda name: (-by_category[name],
                                                          name))
        biggest = max(within, key=lambda e: (e.amount, e.date, e.category))
        rows.append({
            "month": month,
            "total": month_total,
            "count": len(within),
            "top_category": top_category,
            "biggest": biggest.amount,
        })
    return rows


def budget_report(expenses: Sequence[Expense], budgets: dict[str, float],
                  month: str | None = None) -> list[dict]:
    """Spend against a monthly budget, per category, for one month or all.

    Categories with no budget line are reported with ``budget=None`` so an
    unbudgeted category is visible instead of silently passing.
    """
    _guard(expenses)
    for name, limit in budgets.items():
        if name not in CATEGORIES:
            raise ExpenseError(f"budget for unknown category {name!r}")
        try:
            value = float(limit)
        except (TypeError, ValueError):
            raise ExpenseError(f"budget for {name!r} is not a number") from None
        if value < 0:
            raise ExpenseError(f"budget for {name!r} must not be negative")
    months = [month] if month else sorted({e.month for e in expenses})
    for name in months:
        if len(name) != 7 or name[4] != "-" or not name.replace("-", "").isdigit():
            raise ExpenseError(f"month {name!r} must look like YYYY-MM")

    rows: list[dict] = []
    for name in months:
        spent: dict[str, float] = {}
        for expense in expenses:
            if expense.month == name:
                spent[expense.category] = round(
                    spent.get(expense.category, 0.0) + expense.amount, 2)
        for category in CATEGORIES:
            used = spent.get(category, 0.0)
            limit = budgets.get(category)
            rows.append({
                "month": name,
                "category": category,
                "spent": used,
                "budget": None if limit is None else round(float(limit), 2),
                "remaining": None if limit is None
                else round(float(limit) - used, 2),
                "over": limit is not None and used > float(limit),
                "used_pct": None if not limit else round(used / float(limit) * 100, 1),
            })
    return rows


def over_budget(expenses: Sequence[Expense],
                budgets: dict[str, float]) -> list[tuple[str, str]]:
    return [(row["month"], row["category"])
            for row in budget_report(expenses, budgets) if row["over"]]


# --------------------------------------------------------------------------- #
# Anomalies
# --------------------------------------------------------------------------- #
def modified_zscore(value: float, sample: Sequence[float]) -> float | None:
    """Robust outlier score, or ``None`` when the sample cannot support one."""
    if len(sample) < MIN_ANOMALY_SAMPLE:
        return None
    middle = statistics.median(sample)
    mad = statistics.median([abs(item - middle) for item in sample])
    if mad == 0:
        # a constant category: fall back to the mean absolute deviation
        mean = statistics.fmean(sample)
        mad = statistics.fmean([abs(item - mean) for item in sample])
    if mad == 0:
        return None
    return 0.6745 * (value - middle) / mad


def find_anomalies(expenses: Sequence[Expense],
                   threshold: float = ANOMALY_THRESHOLD) -> list[dict]:
    """Expenses whose category-relative modified z-score is at least threshold."""
    _guard(expenses)
    if threshold <= 0:
        raise ExpenseError("threshold must be greater than zero")
    by_category: dict[str, list[float]] = {}
    for expense in expenses:
        by_category.setdefault(expense.category, []).append(expense.amount)

    found: list[dict] = []
    for expense in expenses:
        sample = by_category[expense.category]
        score = modified_zscore(expense.amount, sample)
        if score is None or abs(score) < threshold:
            continue
        found.append({
            "expense": expense,
            "category": expense.category,
            "median": round(statistics.median(sample), 2),
            "z": round(score, 3),
        })
    return sorted(found, key=lambda row: (-abs(row["z"]), row["expense"].date))


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
SEED_ROWS = (
    ("2024-01-03", "groceries", "Weekly shop", 52.40),
    ("2024-01-05", "transport", "Metro top-up", 30.00),
    ("2024-01-10", "dining", "Lunch with team", 24.50),
    ("2024-01-15", "utilities", "Electricity", 88.20),
    ("2024-01-22", "groceries", "Weekly shop", 61.10),
    ("2024-01-26", "dining", "Takeaway", 19.90),
    ("2024-01-30", "dining", "Birthday dinner for eight", 320.00),
    ("2024-02-02", "groceries", "Weekly shop", 48.75),
    ("2024-02-07", "transport", "Bus pass", 28.00),
    ("2024-02-11", "dining", "Lunch with team", 31.20),
    ("2024-02-14", "utilities", "Electricity", 82.40),
    ("2024-02-19", "shopping", "Winter coat", 129.99),
    ("2024-02-25", "groceries", "Weekly shop", 55.30),
    ("2024-03-01", "groceries", "Weekly shop", 50.10),
    ("2024-03-04", "transport", "Metro top-up", 30.00),
    ("2024-03-09", "dining", "Lunch with team", 27.80),
    ("2024-03-12", "utilities", "Electricity", 91.60),
    ("2024-03-17", "shopping", "Running shoes", 44.00),
    ("2024-03-24", "shopping", "Books", 39.50),
    ("2024-04-02", "groceries", "Weekly shop", 53.25),
    ("2024-04-06", "transport", "Metro top-up", 31.50),
    ("2024-04-13", "dining", "Lunch with team", 22.40),
    ("2024-04-18", "utilities", "Electricity", 79.90),
    ("2024-04-27", "shopping", "Garden tools", 61.00),
)

BUDGETS = {
    "groceries": 300.0,
    "transport": 90.0,
    "dining": 120.0,
    "utilities": 120.0,
    "shopping": 120.0,
}


def seed_expenses() -> list[Expense]:
    return [Expense(date=parse_date(row[0]), category=row[1],
                    description=row[2], amount=row[3]) for row in SEED_ROWS]


def run_demo() -> int:
    print("=" * 70)
    print(" EXPENSE TRACKER - CSV, monthly aggregates, budgets, outliers")
    print("=" * 70)

    expenses = seed_expenses()

    # 1. the seed loads into 24 expenses across four months
    assert len(expenses) == 24
    assert sorted({e.month for e in expenses}) == \
        ["2024-01", "2024-02", "2024-03", "2024-04"]
    print(f"  loaded {len(expenses)} expenses, 4 months, "
          f"{len(CATEGORIES)} categories")

    # 2. the grand total is the sum of the monthly totals
    assert total(expenses) == 1502.79
    months = monthly_totals(expenses)
    assert months == {"2024-01": 596.10, "2024-02": 375.64,
                      "2024-03": 283.00, "2024-04": 248.05}
    assert round(sum(months.values()), 2) == total(expenses)
    print(f"  total {total(expenses):.2f}; months {list(months.values())}")

    # 3. category totals add up to the same total
    categories = category_totals(expenses)
    assert categories == {"dining": 445.80, "groceries": 320.90,
                          "shopping": 274.49, "transport": 119.50,
                          "utilities": 342.10}
    assert round(sum(categories.values()), 2) == total(expenses)

    # 4. monthly summary: February's biggest category is shopping
    summary = monthly_summary(expenses)
    assert [row["month"] for row in summary] == list(months)
    assert [row["count"] for row in summary] == [7, 6, 6, 5]
    assert summary[1]["top_category"] == "shopping"
    assert summary[0]["top_category"] == "dining"
    assert summary[0]["biggest"] == 320.00

    # 5. budgets: exactly two month/category pairs are over
    over = over_budget(expenses, BUDGETS)
    assert over == [("2024-01", "dining"), ("2024-02", "shopping")], over
    january = {row["category"]: row
               for row in budget_report(expenses, BUDGETS, month="2024-01")}
    assert january["dining"]["remaining"] == -244.40
    assert january["dining"]["used_pct"] == 303.7
    assert january["groceries"]["over"] is False
    assert january["groceries"]["remaining"] == 186.50
    print(f"  over budget: {over}")

    # 6. anomalies: the 320 dinner and the 129.99 coat, nothing else
    found = find_anomalies(expenses)
    flagged = [(row["category"], row["expense"].amount) for row in found]
    assert flagged == [("dining", 320.00), ("shopping", 129.99)], flagged
    assert found[0]["median"] == 26.15
    assert found[0]["z"] > 40
    print(f"  anomalies: {flagged}")

    # 7. a single category with fewer than three expenses is never judged
    small = [Expense(date=parse_date("2024-05-01"), category="shopping",
                     description="Only one", amount=999.0)]
    assert find_anomalies(small) == []

    # 8. a higher threshold stops flagging the borderline charge
    strict = find_anomalies(expenses, threshold=10.0)
    assert [(row["category"], row["expense"].amount) for row in strict] == \
        [("dining", 320.00)]

    # 9. negative controls: each bad field is refused with a named reason
    bad_rows = (
        ({"date": "2024-13-01", "category": "dining",
          "description": "x", "amount": "10"}, "not ISO YYYY-MM-DD"),
        ({"date": "2024-01-01", "category": "dining",
          "description": "x", "amount": "0"}, "greater than zero"),
        ({"date": "2024-01-01", "category": "dining",
          "description": "x", "amount": "-5"}, "greater than zero"),
        ({"date": "2024-01-01", "category": "travel",
          "description": "x", "amount": "10"}, "unknown category"),
        ({"date": "2024-01-01", "category": "dining",
          "description": "  ", "amount": "10"}, "description must not be empty"),
        ({"date": "2024-01-01", "category": "dining",
          "description": "x", "amount": "ten"}, "is not a number"),
        ({"date": "2024-01-01", "category": "dining", "amount": "10"},
         "missing description"),
    )
    for row, needle in bad_rows:
        try:
            Expense.from_row(row)
        except ExpenseError as exc:
            assert needle in str(exc), (row, str(exc))
        else:
            raise AssertionError(f"{row} should have been rejected")
    print(f"  {len(bad_rows)} invalid rows rejected with named reasons")

    # 10. amounts are rounded to cents on the way in
    assert Expense(date=parse_date("2024-01-01"), category="dining",
                   description="Rounding", amount="10.121").amount == 10.12
    assert Expense(date=parse_date("2024-01-01"), category="dining",
                   description="Rounding", amount="10.126").amount == 10.13

    # 11. CSV round-trip is lossless and sorted by date
    with tempfile.TemporaryDirectory(prefix="expenses-") as folder:
        path = write_csv(expenses, Path(folder) / "expenses.csv")
        again = load_csv(path)
        assert again == expenses
        first_line = path.read_text(encoding="utf-8").splitlines()[1]
        assert first_line.startswith("2024-01-03,groceries"), first_line

    # 12. months and totals are stable across repeated runs
    assert monthly_totals(seed_expenses()) == months
    assert find_anomalies(seed_expenses()) == found

    print()
    print("Cross-checks OK: 24 expenses over 4 months, grand total 1502.79 "
          "matching both month and category breakdowns, monthly summary counts "
          "and top categories, exactly 2 over-budget pairs with exact "
          "remaining and used%, exactly 2 robust outliers (dining 320.00, "
          "shopping 129.99), small samples never judged, a stricter threshold "
          "flags only one, 7 malformed rows rejected, cent rounding, CSV "
          "round-trip, deterministic re-runs")
    print("Demo completed successfully.")
    return 0
