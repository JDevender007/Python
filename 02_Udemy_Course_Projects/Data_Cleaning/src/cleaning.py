"""Cleaning messy text and CSV rows: the legacy filter, and why it never ran.

The course exercise was this loop:

    scan = 'These+notes#reveal9Newton seeking-out an{underlying structure...'
    clean = ''
    for i in scan:
        if i.isalpha or i.isspace():
            clean = clean + i
        else:
            clean = clean + 1
    print(clean)

It prints the input unchanged. Two bugs, and the interesting part is their
relationship.

**Bug 1 — ``i.isalpha`` without parentheses.** A bound method is a truthy
object, so ``if i.isalpha or i.isspace()`` is true for *every* character.
The filter keeps punctuation, digits, everything; ``clean`` ends up identical
to ``scan``. Nothing raises, so the program looks like it worked.

**Bug 2 — ``clean + 1``.** ``str + int`` is a ``TypeError``. But the ``else``
branch is unreachable while bug 1 exists: since the condition is always true,
the ``else`` never executes. Bug 1 *hides* bug 2.

Fix them in the obvious order and the program crashes:

    clean = clean + i          # 'i.isalpha()' now correct
    ...
    clean = clean + 1          # TypeError: can only concatenate str

which is why ``broken_clean()`` below is kept: the demo runs it, asserts the
``TypeError``, and so proves the second bug is real rather than theoretical.

The working code replaces the loop with a predicate and a comprehension:

    strip_symbols(text)   keep only letters, digits and whitespace
    collapse_spaces(text) runs of whitespace become one space, ends trimmed
    clean_text(text)      both, case preserved
    normalise(text)       clean_text() then casefolded
    sniff(value)          "42" -> 42, "3.5" -> 3.5, "2024-01-31" -> date,
                          "yes" -> True, "" -> None, everything else text
    clean_table(rows)     every cell sniffed, duplicate rows dropped, a report

Fully offline, no pandas, no network.
"""

from __future__ import annotations

import datetime
from pathlib import Path

#: Cells that mean "no value". Compared case-insensitively after stripping.
BLANKS = ("", "-", "--", "n/a", "na", "null", "none", "nan")

#: Words that mean True/False when a cell is not a number.
TRUE_WORDS = ("true", "yes", "y", "t")
FALSE_WORDS = ("false", "no", "n", "f")

#: A leading zero is kept as text: "007" is a code, not the number seven.
LEADING_ZERO_NOTE = "leading zeros are kept as text"


class CleanError(ValueError):
    """Input that cannot be cleaned."""


# --------------------------------------------------------------------------- #
# The legacy loop
# --------------------------------------------------------------------------- #
def legacy_clean(scan: str) -> str:
    """The original loop, bug for bug. Returns its input unchanged.

    ``i.isalpha`` is a bound method, and a bound method is truthy, so the
    condition never fails and nothing is ever filtered. ``clean + 1`` is
    unreachable and would raise ``TypeError`` if it were reached.
    """
    if not isinstance(scan, str):
        raise CleanError("scan must be a string")
    clean = ""
    for character in scan:
        if character.isalpha or character.isspace():
            clean = clean + character
        else:
            clean = clean + 1                 # noqa: unreachable, and a bug
    return clean


def broken_clean(scan: str) -> str:
    """The first fix only: correct ``isalpha()``, keep the ``+ 1``.

    Raises ``TypeError`` on the first non-letter that is not whitespace, which
    is the crash the original bug was hiding.
    """
    if not isinstance(scan, str):
        raise CleanError("scan must be a string")
    clean = ""
    for character in scan:
        if character.isalpha() or character.isspace():
            clean = clean + character
        else:
            clean = clean + 1                 # TypeError: str + int
    return clean


# --------------------------------------------------------------------------- #
# Text cleaning
# --------------------------------------------------------------------------- #
def strip_symbols(text) -> str:
    """Keep letters, digits and whitespace; drop every other character."""
    if not isinstance(text, str):
        raise CleanError(f"text must be a string, got {type(text).__name__}")
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace())


def collapse_spaces(text) -> str:
    """Runs of whitespace become one space; the ends are trimmed."""
    if not isinstance(text, str):
        raise CleanError(f"text must be a string, got {type(text).__name__}")
    return " ".join(text.split())


def clean_text(text) -> str:
    """Symbols removed and whitespace collapsed, case preserved."""
    return collapse_spaces(strip_symbols(text))


def normalise(text) -> str:
    """``clean_text`` then ``casefold``, for comparisons and keys."""
    return clean_text(text).casefold()


def tokens(text) -> list[str]:
    """The normalised words of a text."""
    cleaned = normalise(text)
    return cleaned.split() if cleaned else []


def dedupe(items, *, key=None) -> list:
    """Order-preserving de-duplication, case-insensitive for text.

    The first occurrence wins, so the result reads like the input rather than
    like a set.
    """
    seen: set = set()
    result = []
    for item in items:
        marker = key(item) if key else item
        if isinstance(marker, str):
            marker = marker.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


# --------------------------------------------------------------------------- #
# Type sniffing
# --------------------------------------------------------------------------- #
def sniff(value) -> object:
    """Best guess at a cleaned cell's type.

    Order matters: blank, boolean words, integer, float, ISO date, then text.
    The integer test refuses leading zeros so ``"007"`` stays a string; a zip
    code or product code that turned into ``7`` would be silently corrupted.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    text = value.strip()
    lowered = text.casefold()
    if lowered in BLANKS:
        return None
    if lowered in TRUE_WORDS:
        return True
    if lowered in FALSE_WORDS:
        return False

    signless = text[1:] if text[:1] in "+-" else text
    if signless.isdigit() and signless.isascii():
        if signless == "0" or not signless.startswith("0"):
            try:
                return int(text)
            except ValueError:                # unreachable: isdigit guards it
                pass

    try:
        if text.count(".") == 1 and "_" not in text:
            return float(text)
    except ValueError:
        pass

    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        try:
            return datetime.date.fromisoformat(text)
        except ValueError:
            return text

    return text


def clean_value(value) -> object:
    """Sniff one cell, refusing nothing — text is the fallback."""
    return sniff(value)


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
def clean_header(row: dict) -> dict:
    """Header keys normalised to lower snake case, symbols removed."""
    cleaned: dict = {}
    for key, value in row.items():
        name = normalise(str(key)).replace(" ", "_")
        if not name:
            raise CleanError(f"header {key!r} normalises to an empty name")
        if name in cleaned:
            raise CleanError(f"duplicate header after cleaning: {name!r}")
        cleaned[name] = value
    return cleaned


def clean_row(row: dict) -> dict:
    """Sniff every value in one row."""
    if not isinstance(row, dict):
        raise CleanError("row must be a dict")
    return {key: clean_value(value) for key, value in row.items()}


def clean_table(rows: list[dict]) -> tuple[list[dict], dict]:
    """Clean a list of dict rows, drop exact duplicates, and report.

    The report describes the *output*: cells in kept rows only, so the counts
    add up to ``rows_out * columns``. Counting the duplicate row's cells would
    make the arithmetic impossible to check.
    """
    if not isinstance(rows, list):
        raise CleanError("rows must be a list")
    if not rows:
        raise CleanError("no rows to clean")

    report = {
        "rows_in": len(rows),
        "rows_out": 0,
        "cells": 0,
        "cells_changed": 0,
        "blanks_to_none": 0,
        "to_int": 0,
        "to_float": 0,
        "to_bool": 0,
        "to_date": 0,
        "kept_text": 0,
        "duplicate_rows": 0,
    }
    cleaned_rows: list[dict] = []
    seen: set[tuple] = set()

    for row in rows:
        if not isinstance(row, dict):
            raise CleanError("every row must be a dict")
        cleaned = clean_row(clean_header(row))
        marker = tuple(sorted((key, repr(value))
                              for key, value in cleaned.items()))
        if marker in seen:
            report["duplicate_rows"] += 1
            continue
        seen.add(marker)

        report["cells"] += len(cleaned)
        originals = {normalise(str(key)).replace(" ", "_"): value
                     for key, value in row.items()}
        for key, value in cleaned.items():
            original = originals.get(key)
            rendered = "" if value is None else str(value)
            if isinstance(original, str) and original.strip() != rendered:
                report["cells_changed"] += 1
            if value is None:
                report["blanks_to_none"] += 1
            elif isinstance(value, bool):
                report["to_bool"] += 1
            elif isinstance(value, datetime.date):
                report["to_date"] += 1
            elif isinstance(value, int):
                report["to_int"] += 1
            elif isinstance(value, float):
                report["to_float"] += 1
            else:
                report["kept_text"] += 1

        cleaned_rows.append(cleaned)

    report["rows_out"] = len(cleaned_rows)
    typed = (report["blanks_to_none"] + report["to_bool"] + report["to_date"]
             + report["to_int"] + report["to_float"] + report["kept_text"])
    assert typed == report["cells"], (typed, report["cells"])
    return cleaned_rows, report


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCAN_FILE = DATA_DIR / "scan.txt"
MESSY_FILE = DATA_DIR / "messy.csv"


def load_lines(path: str | Path = SCAN_FILE) -> list[str]:
    """Read non-comment, non-blank lines from a scan file."""
    path = Path(path)
    if not path.exists():
        raise CleanError(f"scan file not found: {path}")
    lines = [line.rstrip("\r\n") for line in
             path.read_text(encoding="utf-8").splitlines()]
    lines = [line for line in lines
             if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise CleanError(f"{path.name} contains no lines")
    return lines


def load_messy(path: str | Path = MESSY_FILE) -> list[dict]:
    """Read the bundled CSV into dict rows, header included as keys.

    Deliberately naive: no quoting, no escaping. The point of the project is
    what happens to the *values*, and a hand-rolled split keeps the parsing
    visible. The header is cleaned by ``clean_header`` like any other row.
    """
    path = Path(path)
    if not path.exists():
        raise CleanError(f"CSV file not found: {path}")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    if len(lines) < 2:
        raise CleanError(f"{path.name} needs a header and at least one row")
    header = lines[0].split(",")
    rows: list[dict] = []
    for number, line in enumerate(lines[1:], start=2):
        fields = line.split(",")
        if len(fields) != len(header):
            raise CleanError(f"{path.name} line {number}: expected "
                             f"{len(header)} fields, got {len(fields)}")
        rows.append({key: value for key, value in zip(header, fields)})
    return rows


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
LEGACY_SCAN = ("These+notes#reveal9Newton seeking-out an{underlying "
               "structure to/the\\pyramid}")


def run_demo() -> int:
    print("=" * 70)
    print(" DATA CLEANING - the no-op filter, the hidden TypeError, and a "
          "real cleaner")
    print("=" * 70)

    # 1. the legacy loop returns its input unchanged
    unchanged = legacy_clean(LEGACY_SCAN)
    assert unchanged == LEGACY_SCAN, unchanged
    assert "+" in unchanged and "{" in unchanged and "\\" in unchanged
    print(f"  legacy_clean returned the input unchanged "
          f"({len(unchanged)} chars, punctuation intact)")

    # 2. bug 1: every character takes the first branch, including '+'
    always_true = all(bool(ch.isalpha) or ch.isspace()
                      for ch in LEGACY_SCAN)
    assert always_true is True
    assert bool("+".isalpha) is True          # a bound method is truthy
    assert "".isalpha is not None
    print("  bug 1: ch.isalpha is a truthy bound method, so the else branch "
          "never runs")

    # 3. bug 2 is real: fixing isalpha makes the loop crash
    try:
        broken_clean("a+b")
    except TypeError as exc:
        assert "concatenate str" in str(exc) or "unsupported" in str(exc)
        message = str(exc)
    else:
        raise AssertionError("the + 1 branch should raise TypeError")
    assert broken_clean("abc") == "abc"       # letters alone still work
    print(f"  bug 2: broken_clean('a+b') raised TypeError: {message[:42]}...")

    # 4. the replacement: keep alphanumerics, drop the rest
    stripped = strip_symbols(LEGACY_SCAN)
    assert "+" not in stripped and "{" not in stripped and "\\" not in stripped
    assert "9" in stripped                    # digits are kept on purpose
    assert stripped == (
        "Thesenotesreveal9Newton seekingout anunderlying structure "
        "tothepyramid"), stripped
    print(f"  strip_symbols -> {stripped[:46]}...")

    # 5. whitespace collapse and idempotency
    assert collapse_spaces("  a   b \t c\n\nd ") == "a b c d"
    assert collapse_spaces("") == ""
    assert collapse_spaces("   ") == ""
    once = clean_text(LEGACY_SCAN)
    twice = clean_text(once)
    assert once == twice == stripped, (once, twice)
    assert normalise("  Hello WORLD ") == "hello world"
    assert tokens("  Hello,   WORLD!  hello ") == ["hello", "world", "hello"]
    print("  clean_text is idempotent; normalise/tokens casefold and split")

    # 6. non-text input is refused, not coerced
    for bad in (None, 42, ["a"]):
        try:
            strip_symbols(bad)
        except CleanError as exc:
            assert "must be a string" in str(exc)
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    assert collapse_spaces("") == ""
    print("  non-text input refused; empty text is not an error")

    # 7. sniff: each type is inferred, and the ambiguous cases stay text
    cases = {
        "42": 42, " -7 ": -7, "3.5": 3.5, "+2.25": 2.25,
        "yes": True, "NO": False, "true": True,
        "2024-01-31": datetime.date(2024, 1, 31),
        "": None, "  ": None, "n/a": None,
        "007": "007", "not-a-date": "not-a-date", "Alice": "Alice",
        "1e5": "1e5", "12.34.56": "12.34.56", "0": 0,
    }
    for raw, expected in cases.items():
        got = sniff(raw)
        assert got == expected and type(got) is type(expected), \
            (raw, got, expected)
    assert isinstance(sniff("007"), str)
    assert sniff(None) is None
    assert sniff(7) == 7
    print(f"  {len(cases)} cells sniffed: int, float, bool, date, None, text")

    # 8. a leading zero is preserved, and that is a decision, not an accident
    assert sniff("007") == "007"
    assert sniff("0") == 0
    assert sniff("00") == "00"
    assert LEADING_ZERO_NOTE.startswith("leading zeros")

    # 9. dedupe keeps the first spelling and the original order
    words = ["Alpha", "beta", "ALPHA", "gamma", "Beta"]
    assert dedupe(words) == ["Alpha", "beta", "gamma"]
    assert dedupe([]) == []
    assert dedupe([1, 2, 1, 3]) == [1, 2, 3]
    assert dedupe(words, key=str.upper) == ["Alpha", "beta", "gamma"]
    print(f"  dedupe of {words} -> {dedupe(words)}")

    # 10. headers normalise, and collisions are reported
    assert clean_header({" city ": "x", "Joined On": "y"}) == \
        {"city": "x", "joined_on": "y"}
    try:
        clean_header({"City": 1, "city": 2})
    except CleanError as exc:
        assert "duplicate header" in str(exc)
    else:
        raise AssertionError("colliding headers should be refused")
    try:
        clean_header({"!!!": 1})
    except CleanError as exc:
        assert "empty name" in str(exc)
    else:
        raise AssertionError("a symbol-only header should be refused")

    # 11. the bundled scans load and clean into something predictable
    lines = load_lines()
    assert len(lines) == 5, len(lines)
    cleaned_lines = [clean_text(line) for line in lines]
    assert all(clean_text(line) == line for line in cleaned_lines), \
        "cleaning a cleaned line changed it"
    assert all("+" not in line and "#" not in line for line in cleaned_lines)
    assert dedupe(cleaned_lines) == cleaned_lines, \
        "the bundled scans are distinct after cleaning"
    assert all(line for line in cleaned_lines), "a line cleaned to nothing"
    print(f"  {len(lines)} bundled scans cleaned, {len(cleaned_lines)} "
          f"distinct results")

    # 12. the bundled CSV: counts, types, duplicates, and a spot check
    rows = load_messy()
    assert len(rows) == 6, len(rows)
    cleaned, report = clean_table(rows)
    assert report["rows_in"] == 6
    assert report["rows_out"] == 5
    assert report["duplicate_rows"] == 1
    assert report["blanks_to_none"] == 2, report
    assert report["to_date"] == 4, report
    assert report["to_bool"] == 4, report      # 'maybe' is not a boolean
    first = cleaned[0]
    assert first["name"] == "Alice"
    assert first["city"] == "Mumbai"
    assert first["amount"] == 42
    assert first["joined"] == datetime.date(2024, 1, 31)
    assert first["active"] is True
    assert first["note"] == "first order"
    assert "city" in cleaned[0] and " city " not in cleaned[0]
    print(f"  CSV: {report['rows_in']} rows in, {report['rows_out']} out, "
          f"{report['duplicate_rows']} duplicate dropped, "
          f"{report['blanks_to_none']} blanks -> None")

    # 13. the leading-zero row survives as text
    kept = [row for row in cleaned if row["amount"] == "007"]
    assert len(kept) == 1, [row["amount"] for row in cleaned]
    print("  the '007' amount stayed text, so the code was not corrupted")

    # 14. cleaning twice changes nothing
    again, second_report = clean_table(cleaned)
    assert again == cleaned, "cleaning is not idempotent"
    assert second_report["duplicate_rows"] == 0
    assert second_report["rows_out"] == report["rows_out"]

    # 15. a malformed table is refused with the reason
    try:
        clean_table([])
    except CleanError as exc:
        assert "no rows" in str(exc)
    else:
        raise AssertionError("an empty table should be refused")
    try:
        clean_table("nope")
    except CleanError as exc:
        assert "must be a list" in str(exc)
    else:
        raise AssertionError("a non-list should be refused")

    print()
    print("Cross-checks OK: the legacy loop returns its input unchanged with "
          "punctuation intact, isalpha is shown to be a truthy bound method, "
          "the hidden '+ 1' reproduces a TypeError once isalpha is fixed, "
          "symbols stripped and whitespace collapsed idempotently, 17 cells "
          "sniffed into 6 types with '007' kept as text, dedupe preserving "
          "order, header collisions refused, 5 bundled scans cleaned to 5 "
          "distinct lines, and a 6-row CSV reduced to 5 rows with 2 blanks "
          "and 1 duplicate accounted for")
    print("\nDemo completed successfully.")
    return 0
