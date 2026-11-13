"""Legacy module - the BEFORE picture: no type hints, no validation.

Deliberately untyped and duck-typed, exactly like code written before a
refactoring pass: raw exceptions (KeyError, ValueError, ZeroDivisionError),
silent acceptance of nonsense data (negative units), and inconsistent return
values. Keep this module unannotated - its job is to be contrasted with
typed.py in the demo and in the tests.
"""

import csv


def load_records(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def row_revenue(row):
    return float(row["units"]) * float(row["price"])


def summarize(records):
    total = 0.0
    for row in records:
        total += row_revenue(row)
    mean = total / len(records)          # ZeroDivisionError on empty input
    top = None
    for row in records:
        if top is None or row_revenue(row) > row_revenue(top):
            top = row
    return {
        "count": len(records),
        "total": round(total, 2),
        "mean": round(mean, 2),
        "top": top["id"] if top else None,
    }
