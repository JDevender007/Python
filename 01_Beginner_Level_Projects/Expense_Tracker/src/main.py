"""Command line entry point for the expense tracker.

Usage
-----
    python src/main.py --demo                       # self-checking demo
    python src/main.py                              # summary of the bundled CSV
    python src/main.py --month 2024-01              # one month's budget report
    python src/main.py --anomalies                  # robust outliers only
    python src/main.py --budgets data/budgets.json
    python src/main.py --json out.json --quiet

Budget limits come from ``data/budgets.json`` (or ``--budgets``); a month
without a limit is reported as unbudgeted rather than silently passing.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from expenses import (
    CATEGORIES,
    ExpenseError,
    budget_report,
    category_totals,
    find_anomalies,
    load_csv,
    monthly_summary,
    over_budget,
    run_demo,
    total,
)

BANNER = """
====================================
 EXPENSE TRACKER
   CSV, budgets, outlier scores
====================================
"""

PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = PROJECT / "data" / "expenses.csv"
DEFAULT_BUDGETS = PROJECT / "data" / "budgets.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate an expense CSV by month and category, check "
                    "budgets and score outliers (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=None,
                        help="expense CSV (default: the bundled one)")
    parser.add_argument("--budgets", type=Path, default=None,
                        help="budget JSON (default: the bundled one)")
    parser.add_argument("--month", metavar="YYYY-MM", default=None,
                        help="restrict the report to one month")
    parser.add_argument("--anomalies", action="store_true",
                        help="print only the robust outliers")
    parser.add_argument("--threshold", type=float, default=3.5,
                        help="modified z-score cut-off (default: 3.5)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the report as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def load_budgets(path: Path | None) -> dict[str, float]:
    source = path or DEFAULT_BUDGETS
    if not source.exists():
        raise ExpenseError(f"file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExpenseError(f"{source.name} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExpenseError(f"{source.name} must map category names to limits")
    unknown = [name for name in payload if name not in CATEGORIES]
    if unknown:
        raise ExpenseError(
            f"unknown budget categor(ies): {', '.join(sorted(unknown))}")
    return {name: float(value) for name, value in payload.items()}


def render_summary(rows: list[dict]) -> str:
    lines = [f"  {'month':<9}{'total':>10}{'n':>4}  {'top category':<13}"
             f"{'biggest':>9}", "  " + "-" * 46]
    for row in rows:
        lines.append(f"  {row['month']:<9}{row['total']:>10.2f}{row['count']:>4}"
                     f"  {row['top_category']:<13}{row['biggest']:>9.2f}")
    return "\n".join(lines)


def render_budgets(rows: list[dict]) -> str:
    lines = [f"  {'month':<9}{'category':<12}{'spent':>9}{'budget':>9}"
             f"{'remaining':>11}", "  " + "-" * 50]
    for row in rows:
        budget = "-" if row["budget"] is None else f"{row['budget']:.2f}"
        remaining = "-" if row["remaining"] is None else f"{row['remaining']:.2f}"
        flag = "  OVER" if row["over"] else ""
        lines.append(f"  {row['month']:<9}{row['category']:<12}"
                     f"{row['spent']:>9.2f}{budget:>9}{remaining:>11}{flag}")
    return "\n".join(lines)


def render_anomalies(rows: list[dict]) -> str:
    if not rows:
        return "  no outliers above the threshold"
    lines = [f"  {'date':<12}{'category':<12}{'amount':>9}{'median':>9}{'z':>8}",
             "  " + "-" * 50]
    for row in rows:
        lines.append(f"  {row['date']:<12}{row['category']:<12}"
                     f"{row['amount']:>9.2f}{row['median']:>9.2f}"
                     f"{row['z']:>8.2f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except ExpenseError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    try:
        expenses = load_csv(args.file or DEFAULT_FILE)
        budgets = load_budgets(args.budgets)
        if args.anomalies:
            payload = {
                "total": total(expenses),
                "anomalies": [
                    {
                        "date": row["expense"].date.isoformat(),
                        "category": row["category"],
                        "description": row["expense"].description,
                        "amount": row["expense"].amount,
                        "median": row["median"],
                        "z": row["z"],
                    }
                    for row in find_anomalies(expenses, args.threshold)
                ],
            }
        else:
            months = monthly_summary(expenses)
            if args.month:
                months = [row for row in months if row["month"] == args.month]
            payload = {
                "total": total(expenses),
                "months": months,
                "categories": category_totals(expenses),
                "budgets": budget_report(expenses, budgets, month=args.month),
                "over_budget": over_budget(expenses, budgets),
            }
    except ExpenseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        if args.anomalies:
            print(render_anomalies(payload["anomalies"]))
        else:
            print(render_summary(payload["months"]))
            print()
            print(render_budgets(payload["budgets"]))
            print(f"\nGrand total: {payload['total']:.2f}"
                  f"   over budget: {len(payload['over_budget'])} pair(s)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
