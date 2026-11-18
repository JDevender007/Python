"""Tests for Expense_Tracker: records, CSV, aggregates, budgets, outliers."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import expenses                                          # noqa: E402
import main as cli                                       # noqa: E402
from expenses import (                                   # noqa: E402
    CATEGORIES,
    Expense,
    ExpenseError,
    budget_report,
    category_totals,
    find_anomalies,
    load_csv,
    modified_zscore,
    monthly_summary,
    monthly_totals,
    over_budget,
    parse_date,
    run_demo,
    seed_expenses,
    total,
    write_csv,
)


def make(day: str = "2024-01-01", category: str = "dining",
         description: str = "Lunch", amount=10.0) -> Expense:
    return Expense(date=parse_date(day), category=category,
                   description=description, amount=amount)


# --------------------------------------------------------------------------- #
# Dates and records
# --------------------------------------------------------------------------- #
def test_parse_date_accepts_iso():
    assert parse_date("2024-03-09") == date(2024, 3, 9)


def test_parse_date_accepts_a_date_object():
    assert parse_date(date(2024, 1, 1)) == date(2024, 1, 1)


@pytest.mark.parametrize("text", ["2024-13-01", "01/02/2024", "2024-2-1",
                                  "not a date", ""])
def test_parse_date_rejects_other_formats(text):
    with pytest.raises(ExpenseError):
        parse_date(text)


def test_expense_normalises_category_and_description():
    expense = make(category=" Dining ", description="  Lunch   with  team ")
    assert expense.category == "dining"
    assert expense.description == "Lunch with team"


def test_expense_month_property():
    assert make("2024-07-04").month == "2024-07"


def test_expense_rounds_amount_to_cents():
    assert make(amount="10.126").amount == 10.13
    assert make(amount="10.121").amount == 10.12


@pytest.mark.parametrize("amount", [0, -1, "-0.01", "abc", "nan", None])
def test_expense_rejects_bad_amounts(amount):
    with pytest.raises(ExpenseError):
        make(amount=amount)


@pytest.mark.parametrize("category", ["travel", "", "DINING FOOD"])
def test_expense_rejects_unknown_categories(category):
    with pytest.raises(ExpenseError, match="unknown category"):
        make(category=category)


def test_expense_rejects_empty_description():
    with pytest.raises(ExpenseError, match="description must not be empty"):
        make(description="   ")


def test_expense_rejects_long_description():
    with pytest.raises(ExpenseError, match="longer than 60"):
        make(description="x" * 61)


def test_expense_rejects_non_date():
    with pytest.raises(ExpenseError, match="datetime.date"):
        Expense(date="2024-01-01", category="dining",       # type: ignore[arg-type]
                description="x", amount=10)


def test_expense_is_hashable_and_frozen():
    expense = make()
    assert expense in {expense}
    with pytest.raises(Exception):
        expense.amount = 5.0                              # type: ignore[misc]


def test_expense_row_round_trip():
    expense = make()
    assert Expense.from_row(expense.to_row()) == expense


def test_expense_from_row_reports_missing_fields():
    with pytest.raises(ExpenseError, match="missing description"):
        Expense.from_row({"date": "2024-01-01", "category": "dining",
                          "amount": "10"})


def test_expense_from_row_rejects_non_mapping():
    with pytest.raises(ExpenseError, match="must be a mapping"):
        Expense.from_row(["2024-01-01"])                  # type: ignore[arg-type]


def test_categories_are_documented():
    assert CATEGORIES == ("dining", "groceries", "shopping",
                          "transport", "utilities")


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def test_seed_has_24_expenses():
    assert len(seed_expenses()) == 24


def test_bundled_csv_matches_the_seed():
    assert load_csv(PROJECT / "data" / "expenses.csv") == seed_expenses()


def test_write_then_load_round_trip(tmp_path):
    expenses = seed_expenses()
    path = write_csv(expenses, tmp_path / "e.csv")
    assert load_csv(path) == expenses


def test_write_csv_sorts_by_date(tmp_path):
    path = write_csv([make("2024-05-01"), make("2024-01-01")],
                     tmp_path / "e.csv")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[1].startswith("2024-01-01")
    assert lines[2].startswith("2024-05-01")


def test_load_missing_file(tmp_path):
    with pytest.raises(ExpenseError, match="file not found"):
        load_csv(tmp_path / "nope.csv")


def test_load_reports_missing_columns(tmp_path):
    path = tmp_path / "e.csv"
    path.write_text("date,category\n2024-01-01,dining\n", encoding="utf-8")
    with pytest.raises(ExpenseError, match="missing column"):
        load_csv(path)


def test_load_reports_line_numbers(tmp_path):
    path = tmp_path / "e.csv"
    path.write_text("date,category,description,amount\n"
                    "2024-01-01,dining,Lunch,10\n"
                    "2024-01-02,dining,Lunch,-3\n", encoding="utf-8")
    with pytest.raises(ExpenseError, match="line 3"):
        load_csv(path)


# --------------------------------------------------------------------------- #
# Aggregates
# --------------------------------------------------------------------------- #
def test_total_sums_amounts():
    assert total([make(amount=10), make(amount=2.5)]) == 12.5


def test_total_of_nothing_is_zero():
    assert total([]) == 0.0


def test_monthly_totals_are_sorted():
    totals = monthly_totals([make("2024-02-01"), make("2024-01-01", amount=5),
                             make("2024-01-20", amount=5)])
    assert totals == {"2024-01": 10.0, "2024-02": 10.0}


def test_category_totals_are_sorted_by_name():
    totals = category_totals([make(category="transport"),
                              make(category="dining", amount=5)])
    assert list(totals) == ["dining", "transport"]
    assert totals["dining"] == 5.0


def test_monthly_summary_counts_and_top_category():
    rows = monthly_summary(seed_expenses())
    assert [row["month"] for row in rows] == \
        ["2024-01", "2024-02", "2024-03", "2024-04"]
    assert [row["count"] for row in rows] == [7, 6, 6, 5]
    assert [row["top_category"] for row in rows] == \
        ["dining", "shopping", "utilities", "utilities"]


def test_monthly_summary_biggest_expense():
    rows = monthly_summary(seed_expenses())
    assert [row["biggest"] for row in rows] == [320.0, 129.99, 91.60, 79.90]


def test_aggregates_reject_non_expenses():
    with pytest.raises(ExpenseError, match="list of Expense"):
        total(["not an expense"])                         # type: ignore[list-item]


# --------------------------------------------------------------------------- #
# Budgets
# --------------------------------------------------------------------------- #
def test_budget_report_covers_every_category():
    rows = budget_report(seed_expenses(), expenses.BUDGETS, month="2024-01")
    assert [row["category"] for row in rows] == list(CATEGORIES)


def test_budget_report_figures():
    rows = {row["category"]: row
            for row in budget_report(seed_expenses(), expenses.BUDGETS,
                                     month="2024-01")}
    assert rows["dining"]["spent"] == 364.40
    assert rows["dining"]["remaining"] == -244.40
    assert rows["dining"]["over"] is True
    assert rows["dining"]["used_pct"] == 303.7
    assert rows["groceries"]["remaining"] == 186.50
    assert rows["groceries"]["over"] is False


def test_budget_report_all_months():
    rows = budget_report(seed_expenses(), expenses.BUDGETS)
    assert len(rows) == 4 * len(CATEGORIES)


def test_budget_report_unbudgeted_category():
    rows = {row["category"]: row for row in budget_report(
        seed_expenses(), {"dining": 120.0}, month="2024-01")}
    assert rows["groceries"]["budget"] is None
    assert rows["groceries"]["remaining"] is None
    assert rows["groceries"]["over"] is False
    assert rows["groceries"]["used_pct"] is None


def test_over_budget_lists_exactly_two_pairs():
    assert over_budget(seed_expenses(), expenses.BUDGETS) == \
        [("2024-01", "dining"), ("2024-02", "shopping")]


def test_budget_rejects_unknown_category():
    with pytest.raises(ExpenseError, match="unknown category"):
        budget_report(seed_expenses(), {"travel": 10})


def test_budget_rejects_negative_limit():
    with pytest.raises(ExpenseError, match="must not be negative"):
        budget_report(seed_expenses(), {"dining": -1})


def test_budget_rejects_bad_month():
    with pytest.raises(ExpenseError, match="must look like YYYY-MM"):
        budget_report(seed_expenses(), expenses.BUDGETS, month="January")


def test_month_with_no_spending_is_under_budget():
    rows = {row["category"]: row for row in budget_report(
        seed_expenses(), expenses.BUDGETS, month="2024-06")}
    assert rows["dining"]["spent"] == 0.0
    assert rows["dining"]["over"] is False


# --------------------------------------------------------------------------- #
# Outliers
# --------------------------------------------------------------------------- #
def test_modified_zscore_needs_three_points():
    assert modified_zscore(10, [10, 10]) is None


def test_modified_zscore_is_zero_at_the_median():
    assert modified_zscore(5.0, [1.0, 5.0, 9.0]) == pytest.approx(0.0)


def test_modified_zscore_flags_the_far_value():
    score = modified_zscore(100.0, [10.0, 11.0, 12.0, 100.0])
    assert score is not None and score > 3.5


def test_modified_zscore_handles_a_constant_sample():
    assert modified_zscore(10.0, [10.0, 10.0, 10.0]) is None


def test_find_anomalies_flags_two_charges():
    flagged = [(row["category"], row["expense"].amount)
               for row in find_anomalies(seed_expenses())]
    assert flagged == [("dining", 320.0), ("shopping", 129.99)]


def test_find_anomalies_reports_the_median():
    first = find_anomalies(seed_expenses())[0]
    assert first["median"] == 26.15
    assert first["z"] > 40


def test_find_anomalies_threshold_is_configurable():
    strict = find_anomalies(seed_expenses(), threshold=10.0)
    assert len(strict) == 1


def test_find_anomalies_small_category_is_never_judged():
    assert find_anomalies([make(category="shopping", amount=999)]) == []


def test_find_anomalies_rejects_bad_threshold():
    with pytest.raises(ExpenseError, match="greater than zero"):
        find_anomalies(seed_expenses(), threshold=0)


def test_anomalies_sorted_by_score():
    scores = [abs(row["z"]) for row in find_anomalies(seed_expenses())]
    assert scores == sorted(scores, reverse=True)


# --------------------------------------------------------------------------- #
# Demo and CLI
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_summary(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "Grand total: 1502.79" in out
    assert "over budget: 2 pair(s)" in out
    assert "OVER" in out


def test_cli_single_month(capsys):
    assert cli.main(["--month", "2024-04"]) == 0
    out = capsys.readouterr().out
    assert "2024-04" in out
    assert "2024-01" not in out


def test_cli_anomalies(capsys):
    assert cli.main(["--anomalies"]) == 0
    out = capsys.readouterr().out
    assert "2024-01-30" in out
    assert "2024-02-19" in out


def test_cli_anomalies_with_threshold(capsys):
    assert cli.main(["--anomalies", "--threshold", "10"]) == 0
    out = capsys.readouterr().out
    assert "2024-01-30" in out
    assert "2024-02-19" not in out


def test_cli_json_summary(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["total"] == 1502.79
    assert len(payload["months"]) == 4
    assert payload["over_budget"] == [["2024-01", "dining"],
                                      ["2024-02", "shopping"]]


def test_cli_json_anomalies(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--anomalies", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert [row["amount"] for row in payload["anomalies"]] == [320.0, 129.99]


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.csv"]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_bad_budget_file_exits_two(tmp_path, capsys):
    path = tmp_path / "b.json"
    path.write_text('{"travel": 10}', encoding="utf-8")
    assert cli.main(["--budgets", str(path)]) == 2
    assert "unknown budget" in capsys.readouterr().err


def test_cli_bad_month_exits_two(capsys):
    assert cli.main(["--month", "January"]) == 2
    assert "YYYY-MM" in capsys.readouterr().err


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_load_budgets_uses_the_bundled_file():
    assert cli.load_budgets(None) == expenses.BUDGETS
