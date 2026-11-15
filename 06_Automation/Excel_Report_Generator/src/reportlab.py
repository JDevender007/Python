"""A report that carries its denominator, and money that is never a float.

The legacy generator was two lines long:

    self.summary = dataframe.describe(include="all")

    report["Data Type"] = dataframe.dtypes.values

Three defects, none of them visible on a tidy sheet with no gaps.

**1. ``describe`` averages the values that happen to be there and hides the
denominator behind a separate ``count`` row.** Two columns with means of 40 and
41 look comparable until you notice one was averaged over 12 rows and the other
over 3. A mean without its ``n`` is not a number you can compare, and
``include="all"`` makes it worse: object columns report ``count``/``unique``/
``top``/``freq`` while numeric columns report ``mean``/``std``/quartiles, so the
resulting frame is a union with blanks where the two shapes do not meet. Here
every statistic is a ``Stat`` that *cannot* be printed without its ``n``, and a
column with too many gaps is flagged instead of quietly averaged.

**2. ``dtypes.values`` is a positional shortcut that answers a different
question.** It reports the storage type, not the meaning: a price stored as
``object`` because one row says ``"N/A"``, a date stored as text, an id stored as
an integer. This module decides a column's *kind* by looking at every value --
money needs exactly two decimals in every row, a count needs whole numbers in
every row -- and refuses a column that mixes the two shapes instead of guessing.

**3. Money as a float is wrong before it is rounded.** ``0.10 + 0.20`` is
``0.30000000000000004``, and ``round`` is half-to-even, so ``round(3.185, 2)``
gives ``3.18`` where a person gets ``3.19``. Every amount here is an integer
number of cents, every total is an integer sum, and every mean is a half-up
integer division of two integers -- ``divide_half_up(2548, 8) == 319``. A
denominator that ends in exactly half a cent is therefore reproducible rather
than a matter of which way the platform's float landed.

The report is built from a CSV file with a hand-written reader, so the whole
thing runs with no pandas, no openpyxl and no spreadsheet. Writing the result is
CSV too, which means the output can be diffed.

Standard library only: no pandas, no openpyxl, no tkinter, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SALES_FILE = DATA_DIR / "sales.csv"

#: The legacy lines, transcribed, so the demo can refute them.
LEGACY_SUMMARY = 'self.summary = dataframe.describe(include="all")'
LEGACY_TYPES = 'report["Data Type"] = dataframe.dtypes.values'

#: A column is flagged when more than this share of its rows is empty.
GAP_LIMIT = 20

#: Money: an optional sign, digits, a dot, and exactly two decimals.
MONEY = re.compile(r"-?\d+\.\d{2}\Z")

#: A count: an optional sign and digits, and nothing else.
COUNT = re.compile(r"-?\d+\Z")

#: The kinds a column can be.
KINDS = ("text", "count", "money")


class ReportError(Exception):
    """A table, a value, a column or a statistic that cannot be accepted."""


# --------------------------------------------------------------------------- #
# Money, in cents
# --------------------------------------------------------------------------- #
def parse_money(text: str) -> int:
    """``"12.34"`` becomes ``1234``; ``"12.3"`` is refused, not rounded.

    A price with one decimal, or three, is a data entry error, and silently
    accepting it is how a column of prices becomes a column of guesses.
    """
    if not isinstance(text, str):
        raise ReportError(f"a money value must be text, got {text!r}")
    value = text.strip()
    if not MONEY.match(value):
        raise ReportError(f"a money value needs two decimals, got {value!r}")
    sign = -1 if value.startswith("-") else 1
    body = value[1:] if sign < 0 else value
    whole, _, cents = body.partition(".")
    return sign * (int(whole) * 100 + int(cents))


def parse_count(text: str) -> int:
    """``"12"`` becomes ``12``; ``"12.0"`` is refused."""
    if not isinstance(text, str):
        raise ReportError(f"a count must be text, got {text!r}")
    value = text.strip()
    if not COUNT.match(value):
        raise ReportError(f"a count needs whole numbers, got {value!r}")
    return int(value)


def money(cents: int) -> str:
    """``319`` becomes ``"3.19"``, and ``-5`` becomes ``"-0.05"``."""
    if not isinstance(cents, int) or isinstance(cents, bool):
        raise ReportError(f"money is kept in whole cents, got {cents!r}")
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def divide_half_up(total: int, count: int) -> int:
    """``total / count`` rounded half away from zero, in integers.

    ``2548 / 8`` is ``318.5`` cents, so the answer is ``319``. Python's
    ``round`` would give ``318`` -- half to even -- and a float would first lose
    the exactness of ``.5``.
    """
    if not isinstance(total, int) or isinstance(total, bool):
        raise ReportError(f"a total is a whole number of cents, got {total!r}")
    if not isinstance(count, int) or isinstance(count, bool):
        raise ReportError(f"a count is a whole number, got {count!r}")
    if count <= 0:
        raise ReportError(f"a mean needs something to divide by, got {count}")
    magnitude = (2 * abs(total) + count) // (2 * count)
    return -magnitude if total < 0 else magnitude


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Table:
    """A header and rows of text, with the header's rules already enforced."""

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.header:
            raise ReportError("a table needs a header")
        for name in self.header:
            if not name.strip():
                raise ReportError("every column needs a name")
        if len(set(self.header)) != len(self.header):
            raise ReportError("two columns share a name")
        for number, row in enumerate(self.rows, start=2):
            if len(row) != len(self.header):
                raise ReportError(f"line {number} holds {len(row)} field(s) "
                                  f"but the header holds {len(self.header)}")

    def __len__(self) -> int:
        return len(self.rows)

    def index(self, name: str) -> int:
        if name not in self.header:
            raise ReportError(f"the table holds no column called {name!r}")
        return self.header.index(name)

    def column(self, name: str) -> tuple[str, ...]:
        place = self.index(name)
        return tuple(row[place] for row in self.rows)


def split_fields(line: str) -> tuple[str, ...]:
    """Split one CSV line, honouring double quotes and doubled quotes."""
    fields, field, quoted, index = [], [], False, 0
    while index < len(line):
        character = line[index]
        if quoted:
            if character == '"':
                if index + 1 < len(line) and line[index + 1] == '"':
                    field.append('"')
                    index += 2
                    continue
                quoted = False
            else:
                field.append(character)
        elif character == '"':
            if field and any(part.strip() for part in field):
                raise ReportError(f"a quote may only open a field: {line!r}")
            quoted = True
        elif character == ",":
            fields.append("".join(field))
            field = []
        else:
            field.append(character)
        index += 1
    if quoted:
        raise ReportError(f"a quoted field never closes: {line!r}")
    fields.append("".join(field))
    return tuple(fields)


def parse_table(text: str) -> Table:
    """Read a CSV document: one header, then rows of the same width."""
    lines = [line for line in text.replace("\r\n", "\n").replace("\r", "\n")
             .split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise ReportError("the table is empty")
    header = tuple(name.strip() for name in split_fields(lines[0]))
    rows = []
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            raise ReportError(f"line {number} is blank; a row needs every "
                              f"field, and an empty field is written as "
                              f"nothing between two commas")
        fields = split_fields(line)
        if len(fields) != len(header):
            raise ReportError(f"line {number} holds {len(fields)} field(s) but "
                              f"the header holds {len(header)}")
        rows.append(tuple(field.strip() for field in fields))
    if not rows:
        raise ReportError("the table holds a header and no rows")
    return Table(header, tuple(rows))


def read_table(path=SALES_FILE) -> Table:
    path = Path(path)
    if not path.is_file():
        raise ReportError(f"file not found: {path}")
    return parse_table(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# A column, and a statistic
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Column:
    """What one column holds: its kind, how many values, and their total."""

    name: str
    kind: str
    present: int
    missing: int
    total: int | None = None
    rows: int = 0

    @property
    def n(self) -> int:
        return self.present

    def mean(self) -> int | None:
        if self.kind not in ("count", "money"):
            return None
        return divide_half_up(self.total, self.n)

    def gap(self) -> bool:
        """True when more than ``GAP_LIMIT`` per cent of the rows is empty."""
        return self.missing * 100 > GAP_LIMIT * self.rows

    def stat(self) -> "Stat | None":
        if self.kind not in ("count", "money"):
            return None
        return Stat(self.name, self.kind, self.total, self.n, self.rows)


@dataclass(frozen=True)
class Stat:
    """A total, the number of values behind it, and how many rows there are.

    The three travel together because a mean that cannot be printed without its
    denominator cannot be printed misleadingly.
    """

    name: str
    unit: str
    total: int
    n: int
    rows: int

    def mean(self) -> int:
        return divide_half_up(self.total, self.n)

    def value(self) -> str:
        return money(self.mean()) if self.unit == "money" else str(self.mean())

    def line(self) -> str:
        gaps = f" ({self.rows - self.n} missing)" if self.rows > self.n else ""
        return (f"{self.name}: mean {self.value()} over {self.n} of "
                f"{self.rows} rows{gaps}")

    def labelled(self) -> str:
        return f"{self.name} ({self.unit})"


def kind_of(name: str, values) -> str:
    """Decide what a column holds, or refuse a column that holds two things."""
    present = [value.strip() for value in values if value.strip()]
    if not present:
        raise ReportError(f"column {name!r} is empty in every row")
    amounts = [value for value in present if MONEY.match(value)]
    counts = [value for value in present if COUNT.match(value)]
    if len(amounts) == len(present):
        return "money"
    if len(counts) == len(present):
        return "count"
    if amounts and counts and len(amounts) + len(counts) == len(present):
        raise ReportError(f"column {name!r} holds {len(amounts)} amount(s) with "
                          f"two decimals and {len(counts)} whole number(s); "
                          f"decide whether it is money or a count")
    return "text"


def profile(table: Table, name: str) -> Column:
    """Everything the report knows about one column."""
    values = table.column(name)
    kind = kind_of(name, values)
    present = [value for value in values if value.strip()]
    missing = len(values) - len(present)
    total = None
    if kind == "money":
        total = sum(parse_money(value) for value in present)
    elif kind == "count":
        total = sum(parse_count(value) for value in present)
    return Column(name, kind, len(present), missing, total, len(table))


# --------------------------------------------------------------------------- #
# Groups
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Group:
    """One value of a key column: how many orders, how many units, how much."""

    name: str
    orders: int
    units: int
    revenue: int

    def line(self) -> str:
        return (f"{self.name:<10} {self.orders:>3} order(s) {self.units:>4} "
                f"unit(s) revenue {money(self.revenue):>10}")


@dataclass(frozen=True)
class Excluded:
    """A row that a group cannot count, and the reason it cannot."""

    line: int
    order: str
    reason: str


def group_rows(table: Table, key="region", units="units",
               price="unit_price") -> tuple[tuple[Group, ...],
                                            tuple[Excluded, ...]]:
    """Total revenue by ``key``, excluding -- and naming -- the rows it cannot.

    Revenue is ``units * price`` in whole cents, which is exact: an integer
    multiplied by an integer. In floats the same sum drifts.
    """
    for name in (key, units, price):
        table.index(name)
    order_column = "order_id" if "order_id" in table.header else None
    totals: dict[str, list] = {}
    excluded = []
    for number, row in enumerate(table.rows, start=2):
        record = dict(zip(table.header, row))
        gaps = []
        if not record[key].strip():
            gaps.append(f"{key} is empty")
        if not record[units].strip():
            gaps.append(f"{units} is empty")
        if not record[price].strip():
            gaps.append(f"{price} is empty")
        order = record[order_column] if order_column else ""
        if gaps:
            excluded.append(Excluded(number, order, "; ".join(gaps)))
            continue
        count = parse_count(record[units])
        cents = parse_money(record[price])
        entry = totals.setdefault(record[key].strip(), [0, 0, 0])
        entry[0] += 1
        entry[1] += count
        entry[2] += count * cents
    groups = tuple(Group(name, *totals[name]) for name in sorted(totals))
    return groups, tuple(excluded)


# --------------------------------------------------------------------------- #
# The report
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Report:
    """Every column profiled, every mean with its denominator, every row placed."""

    table: Table
    columns: tuple[Column, ...]
    groups: tuple[Group, ...]
    excluded: tuple[Excluded, ...]
    key: str = "region"
    flags: tuple[str, ...] = ()

    @property
    def rows(self) -> int:
        return len(self.table)

    def column(self, name: str) -> Column:
        for column in self.columns:
            if column.name == name:
                return column
        raise ReportError(f"the report holds no column called {name!r}")

    def stats(self) -> tuple[Stat, ...]:
        out = []
        for column in self.columns:
            stat = column.stat()
            if stat is not None:
                out.append(stat)
        return tuple(out)

    def flagged(self) -> tuple[str, ...]:
        """The columns the report decided to flag, kept with the report.

        The list is built once, when the report is built, so an audit can
        compare the decision against the columns it was made from.
        """
        return self.flags

    def revenue(self) -> int:
        return sum(group.revenue for group in self.groups)

    def units(self) -> int:
        return sum(group.units for group in self.groups)

    def accounts(self) -> bool:
        return (sum(group.orders for group in self.groups) +
                len(self.excluded) == self.rows)

    def table_lines(self) -> tuple[str, ...]:
        out = [f"  {'column':<12}{'kind':<8}{'present':>8}{'missing':>8}"
               f"{'total':>10}  mean"]
        for column in self.columns:
            total = "-"
            if column.total is not None:
                total = money(column.total) if column.kind == "money" else \
                    str(column.total)
            stat = column.stat()
            mean = stat.line().split(": ", 1)[1] if stat else "-"
            out.append(f"  {column.name:<12}{column.kind:<8}{column.present:>8}"
                       f"{column.missing:>8}{total:>10}  {mean}")
        return tuple(out)

    def csv_lines(self) -> tuple[str, ...]:
        out = ["column,kind,present,missing,total,mean,over,flagged"]
        for column in self.columns:
            stat = column.stat()
            total = "" if column.total is None else str(column.total)
            mean = "" if stat is None else str(stat.mean())
            over = "" if stat is None else str(stat.n)
            out.append(f"{column.name},{column.kind},{column.present},"
                       f"{column.missing},{total},{mean},{over},"
                       f"{'yes' if column.gap() else 'no'}")
        return tuple(out)


def build_report(table: Table, key: str = "region") -> Report:
    """Profile every column, group the rows, and keep the exclusions."""
    columns = tuple(profile(table, name) for name in table.header)
    groups, excluded = group_rows(table, key=key)
    flags = tuple(column.name for column in columns if column.gap())
    return Report(table, columns, groups, excluded, key, flags)


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    """Run one check, and report a structural break as a failure.

    An audit that raises is an audit that cannot report. A negative control
    plants a defect exactly where a check looks, so that check may well trip
    over the defect instead of describing it; it must answer ``False``.
    """
    try:
        return bool(check())
    except Exception:                                    # noqa: BLE001
        return False


def audit(report: Report) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived from the table rather than restated."""
    table = report.table
    rows = len(table)

    def counts_add_up() -> bool:
        return all(column.present + column.missing == rows
                   for column in report.columns)

    def every_mean_carries_a_denominator() -> bool:
        return all(stat.n >= 1 and stat.n <= stat.rows and
                   f"over {stat.n} of {stat.rows}" in stat.line()
                   for stat in report.stats())

    def every_mean_is_recomputed_from_the_column() -> bool:
        for stat in report.stats():
            values = [value for value in table.column(stat.name)
                      if value.strip()]
            parser = parse_money if stat.unit == "money" else parse_count
            total = sum(parser(value) for value in values)
            if len(values) != stat.n:
                return False
            if divide_half_up(total, len(values)) != stat.mean():
                return False
        return True

    def no_amount_is_a_float() -> bool:
        values = [column.total for column in report.columns
                  if column.total is not None]
        values += [stat.total for stat in report.stats()]
        values += [group.revenue for group in report.groups]
        return all(isinstance(value, int) and not isinstance(value, bool)
                   for value in values)

    def every_total_is_the_sum_of_its_column() -> bool:
        for column in report.columns:
            if column.kind == "count":
                wanted = sum(parse_count(value)
                             for value in table.column(column.name)
                             if value.strip())
            elif column.kind == "money":
                wanted = sum(parse_money(value)
                             for value in table.column(column.name)
                             if value.strip())
            else:
                continue
            if column.total != wanted:
                return False
        return True

    def every_group_is_units_times_price() -> bool:
        wanted: dict[str, int] = {}
        orders: dict[str, int] = {}
        for row in table.rows:
            record = dict(zip(table.header, row))
            if not (record[report.key].strip() and record["units"].strip() and
                    record["unit_price"].strip()):
                continue
            name = record[report.key].strip()
            wanted[name] = (wanted.get(name, 0) +
                            parse_count(record["units"]) *
                            parse_money(record["unit_price"]))
            orders[name] = orders.get(name, 0) + 1
        if {group.name: group.revenue for group in report.groups} != wanted:
            return False
        return {group.name: group.orders for group in report.groups} == orders

    def the_flags_match_the_threshold() -> bool:
        wanted = tuple(column.name for column in report.columns
                       if column.missing * 100 > GAP_LIMIT * rows)
        return report.flagged() == wanted

    def the_groups_and_the_exclusions_account_for_the_rows() -> bool:
        return report.accounts()

    def every_excluded_row_says_why() -> bool:
        return all(entry.reason and entry.reason.strip()
                   for entry in report.excluded)

    checks = [
        ("every column's present and missing values add up to the rows",
         counts_add_up),
        ("every mean is printed with the number of values behind it",
         every_mean_carries_a_denominator),
        ("every mean is recomputed from that column's own values",
         every_mean_is_recomputed_from_the_column),
        ("no amount anywhere is a float", no_amount_is_a_float),
        ("every column total is the sum of that column",
         every_total_is_the_sum_of_its_column),
        ("every group's revenue is its units times its price",
         every_group_is_units_times_price),
        ("exactly the columns over the gap limit are flagged",
         the_flags_match_the_threshold),
        ("the groups plus the excluded rows account for every row",
         the_groups_and_the_exclusions_account_for_the_rows),
        ("every excluded row names the field that is missing",
         every_excluded_row_says_why),
    ]
    return [(name, _guard(check)) for name, check in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    table = read_table()
    report = build_report(table)

    print("=" * 74)
    print(" REPORT LAB - a mean without its denominator is not a number")
    print("=" * 74)
    print(f"\n  {len(table)} rows, {len(table.header)} columns: "
          f"{', '.join(table.header)}")

    print(f"\n  {LEGACY_SUMMARY}")
    print(f"    the result is one frame holding two different shapes: an object "
          f"column")
    print(f"    reports count, unique, top and freq, while a numeric column "
          f"reports")
    print(f"    count, mean, std, min and quartiles -- and every cell the two "
          f"shapes")
    print(f"    do not share is blank, so the count row is the only place the "
          f"denominator")
    print(f"    is written down, one line away from the number it explains")

    print(f"\n  {LEGACY_TYPES}")
    print(f"    a storage type is not a meaning: an id made of digits is "
          f"'object' here,")
    print(f"    and one bad cell in a price column casts the whole column to "
          f"text")

    print("\n  the legacy arithmetic, on the same numbers:")
    print(f"    0.10 + 0.20 = {0.1 + 0.2!r}   in cents: 10 + 20 = "
          f"{10 + 20} -> {money(10 + 20)}")
    print(f"    a price times a quantity: 1.15 * 3 = {1.15 * 3!r}   in cents: "
          f"115 * 3 = {115 * 3} -> {money(115 * 3)}")
    print(f"    2548 cents over 8 rows is exactly 318.5 cents; round(318.5) = "
          f"{round(318.5)} (half to even)")
    print(f"    divide_half_up(2548, 8) = {divide_half_up(2548, 8)} -> "
          f"{money(divide_half_up(2548, 8))}")

    print("\n  every column, profiled:")
    for line in report.table_lines():
        print(line)

    print(f"\n  the flagged columns (more than {GAP_LIMIT}% empty):")
    for name in report.flagged():
        column = report.column(name)
        print(f"    {name}: {column.missing} of {column.rows} rows empty -- "
              f"a mean here is over {column.n} value(s), not {column.rows}")

    print(f"\n  revenue by {report.key}, in whole cents:")
    for group in report.groups:
        print(f"    {group.line()}")
    print(f"    {'total':<10}{'':>14} {report.units():>4} unit(s) revenue "
          f"{money(report.revenue())}")

    print(f"\n  the rows a group cannot count, and why:")
    for entry in report.excluded:
        print(f"    line {entry.line} {entry.order}: {entry.reason}")
    print(f"    {sum(group.orders for group in report.groups)} grouped + "
          f"{len(report.excluded)} excluded = {report.rows} rows: "
          f"{'yes' if report.accounts() else 'no'}")

    checks = audit(report)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(table)} rows and {len(table.header)} columns give "
          f"{len(report.stats())} mean(s) that each print their own "
          f"denominator, {len(report.flagged())} column(s) are flagged for "
          f"gaps ({', '.join(report.flagged())}), revenue is "
          f"{money(report.revenue())} in whole cents over "
          f"{sum(group.orders for group in report.groups)} grouped row(s) plus "
          f"{len(report.excluded)} excluded, 318.5 cents rounds half-up to "
          f"3.19 where round() gives 318 cents, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
