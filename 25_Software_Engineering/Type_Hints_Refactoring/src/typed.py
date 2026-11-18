"""Refactored module - the AFTER picture: full type hints, Protocols,
runtime validation, and manually-enforced interface contracts.

Every public function/class is fully annotated; data is validated at the
boundary (indexed, specific error messages); structural conformance is
expressed with ``typing.Protocol`` (``@runtime_checkable``); and
``verify_contracts`` re-implements the parts of mypy that matter here -
method presence, parameter shape, and annotation completeness - using
``inspect`` at runtime, so no external tool is needed. Stdlib only.
"""

from __future__ import annotations

import csv
import inspect
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import (Any, Iterable, Mapping, Protocol, Sequence, TypedDict,
                    runtime_checkable)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECORDS = PROJECT_ROOT / "data" / "records.csv"
BAD_RECORDS = PROJECT_ROOT / "data" / "records_bad.csv"
EMPTY_RECORDS = PROJECT_ROOT / "data" / "records_empty.csv"
INTERFACES = PROJECT_ROOT / "data" / "interfaces.json"

REQUIRED_COLUMNS = ("id", "units", "price")


class RecordError(ValueError):
    """Data/schema problem: bad file, bad column, invalid row value."""


class ContractError(RuntimeError):
    """A class does not satisfy its declared interface contract."""


# --------------------------------------------------------------------------- #
# Structural interfaces (typing.Protocol)
# --------------------------------------------------------------------------- #
@runtime_checkable
class SupportsRevenue(Protocol):
    """Anything that can report a revenue figure, however it stores it."""

    def revenue(self) -> float: ...


class SalePayload(TypedDict):
    """The wire shape a sale record serialises to."""

    id: str
    units: int
    price: float


# --------------------------------------------------------------------------- #
# Domain record (typed + validated)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class SaleRecord:
    """Immutable sale line with validation in __post_init__."""

    id: str
    units: int
    price: float

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise RecordError("id must be a non-empty string")
        if isinstance(self.units, bool) or not isinstance(self.units, int):
            raise RecordError("units must be an integer")
        if self.units < 1:
            raise RecordError("units must be >= 1")
        if isinstance(self.price, bool) or not isinstance(
                self.price, (int, float)):
            raise RecordError("price must be a number")
        if not math.isfinite(float(self.price)):
            raise RecordError("price must be finite")
        if self.price <= 0:
            raise RecordError("price must be > 0")

    def revenue(self) -> float:
        """Line revenue; declared on the SupportsRevenue Protocol."""
        return self.units * float(self.price)

    def as_payload(self) -> SalePayload:
        return {"id": self.id, "units": self.units,
                "price": float(self.price)}


class SaleRepository:
    """Typed repository over an in-memory list of SaleRecords."""

    def __init__(self, records: Sequence[SaleRecord] = ()) -> None:
        self._records: list[SaleRecord] = list(records)

    def load(self, path: str | Path | None = None) -> int:
        self._records = load_records(path)
        return len(self._records)

    def all(self) -> list[SaleRecord]:
        return list(self._records)

    def count(self) -> int:
        return len(self._records)

    def total(self) -> float:
        return round(sum(record.revenue() for record in self._records), 2)


# --------------------------------------------------------------------------- #
# Boundary loading and validation
# --------------------------------------------------------------------------- #
def _parse_units(raw: Any, index: int) -> int:
    text = str(raw).strip()
    try:
        units = int(text)
    except (TypeError, ValueError) as exc:
        raise RecordError(
            f"record {index}: units must be an integer") from exc
    if units < 1:
        raise RecordError(f"record {index}: units must be >= 1")
    return units


def _parse_price(raw: Any, index: int) -> float:
    text = str(raw).strip()
    try:
        price = float(text)
    except (TypeError, ValueError) as exc:
        raise RecordError(f"record {index}: price must be a number") from exc
    if not math.isfinite(price):
        raise RecordError(f"record {index}: price must be finite")
    if price <= 0:
        raise RecordError(f"record {index}: price must be > 0")
    return price


def parse_row(row: Mapping[str, Any], index: int) -> SaleRecord:
    """Validate one raw CSV row into a SaleRecord (first violation wins)."""
    missing = [column for column in REQUIRED_COLUMNS
               if column not in row or row[column] in (None, "")]
    if missing:
        raise RecordError(
            f"record {index} missing value(s): {', '.join(missing)}")
    record_id = str(row["id"]).strip()
    units = _parse_units(row["units"], index)
    price = _parse_price(row["price"], index)
    return SaleRecord(id=record_id, units=units, price=price)


def load_records(path: str | Path | None = None) -> list[SaleRecord]:
    """Load + validate a sales CSV; every problem names its row."""
    source = Path(path) if path is not None else RECORDS
    if not source.is_file():
        raise RecordError(f"file not found: {source}")
    try:
        with source.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            missing = [c for c in REQUIRED_COLUMNS if c not in header]
            if missing:
                raise RecordError(
                    f"missing column(s): {', '.join(missing)} "
                    f"(expected {', '.join(REQUIRED_COLUMNS)})")
            rows = list(reader)
    except UnicodeDecodeError as exc:
        raise RecordError(f"could not read {source.name}: {exc}") from exc
    if not rows:
        raise RecordError(f"no rows in {source.name}")
    return [parse_row(row, index) for index, row in enumerate(rows)]


# --------------------------------------------------------------------------- #
# Aggregates
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Summary:
    """Consistent aggregate: all numeric fields are floats, always."""

    count: int
    total: float
    mean: float
    top_id: str

    def as_dict(self) -> dict[str, Any]:
        return {"count": self.count, "total": self.total,
                "mean": self.mean, "top": self.top_id}


def summarize(records: Sequence[SaleRecord]) -> Summary:
    """Deterministic aggregate; empty input is an error, not a crash."""
    if not records:
        raise RecordError("no records to summarize")
    total = sum(record.revenue() for record in records)
    top = max(records, key=lambda record: record.revenue())
    return Summary(count=len(records), total=round(total, 2),
                   mean=round(total / len(records), 2), top_id=top.id)


def revenue_total(items: Iterable[SupportsRevenue]) -> float:
    """Sum revenues through the Protocol - any conforming type works."""
    return round(sum(item.revenue() for item in items), 2)


# --------------------------------------------------------------------------- #
# Manually enforced interface contracts (mypy-style, via inspect)
# --------------------------------------------------------------------------- #
def load_interface_spec(path: str | Path | None = None) -> dict[str, Any]:
    """Load the interface spec: {Class: {method: {params, annotated}}}."""
    source = Path(path) if path is not None else INTERFACES
    if not source.is_file():
        raise ContractError(f"file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(
            f"could not parse {source.name}: {exc}") from exc
    if not isinstance(payload, dict) or not payload:
        raise ContractError("interface spec must be a non-empty object")
    for class_name, methods in payload.items():
        if not isinstance(methods, dict) or not methods:
            raise ContractError(
                f"spec for {class_name!r} must be a non-empty object")
        for method_name, rule in methods.items():
            if not isinstance(rule, dict) or "params" not in rule:
                raise ContractError(
                    f"spec for {class_name}.{method_name} needs 'params'")
    return payload


def check_contract(cls: type, methods: Mapping[str, Any]) -> list[str]:
    """Compare one class against its spec; returns violation messages.

    This is the manual stand-in for a type checker: it verifies that each
    declared method exists, is callable, has the declared parameter names,
    and (when ``annotated`` is set) that parameters and return type carry
    annotations.
    """
    violations: list[str] = []
    for method_name, rule in methods.items():
        attribute = getattr(cls, method_name, None)
        if attribute is None:
            violations.append(f"{cls.__name__}: missing method "
                              f"'{method_name}'")
            continue
        if not callable(attribute):
            violations.append(f"{cls.__name__}.{method_name} is not callable")
            continue
        signature = inspect.signature(attribute)
        params = [p for p in signature.parameters if p != "self"]
        expected = list(rule["params"])
        if params != expected:
            violations.append(
                f"{cls.__name__}.{method_name}: params {params} != "
                f"declared {expected}")
        if rule.get("annotated"):
            if any(signature.parameters[p].annotation is
                   signature.empty for p in expected
                   if p in signature.parameters):
                violations.append(
                    f"{cls.__name__}.{method_name}: parameter without "
                    f"annotation")
            if signature.return_annotation is signature.empty:
                violations.append(
                    f"{cls.__name__}.{method_name}: missing return "
                    f"annotation")
    return violations


def verify_contracts(classes: Mapping[str, type],
                     spec: Mapping[str, Any]) -> dict[str, list[str]]:
    """Check every declared class; classes without a spec are reported."""
    results: dict[str, list[str]] = {}
    for class_name, methods in spec.items():
        cls = classes.get(class_name)
        if cls is None:
            results[class_name] = [f"no class registered for {class_name!r}"]
            continue
        results[class_name] = check_contract(cls, methods)
    return results


def contract_classes() -> dict[str, type]:
    """The classes whose interfaces are pinned by data/interfaces.json."""
    return {"SaleRecord": SaleRecord, "SaleRepository": SaleRepository}


# --------------------------------------------------------------------------- #
# Protocol demonstrations (used by the demo and the tests)
# --------------------------------------------------------------------------- #
class Refund:
    """Structurally conforms to SupportsRevenue without inheriting it."""

    def __init__(self, amount: float) -> None:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise RecordError("refund amount must be a number")
        if amount <= 0:
            raise RecordError("refund amount must be > 0")
        self._amount = float(amount)

    def revenue(self) -> float:
        return -self._amount


class NotConforming:
    """Deliberately lacks revenue(): must fail the Protocol check."""


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    """Before/after comparison with self-assertions; always returns 0."""
    import legacy

    print("=" * 68)
    print(" TYPE HINTS REFACTORING")
    print(" legacy.py (before) vs typed.py (after): hints, Protocols,")
    print(" runtime validation, manual contracts. Fully offline.")
    print("=" * 68)

    records = load_records()
    typed_summary = summarize(records)
    legacy_summary = legacy.summarize(legacy.load_records(str(RECORDS)))
    print(f"\nLoaded {len(records)} records from {RECORDS.name}")
    print(f"  BEFORE legacy.py : {legacy_summary}")
    print(f"  AFTER  typed.py  : {typed_summary.as_dict()}")

    # Bad data: legacy shrugs, typed refuses.
    try:
        load_records(BAD_RECORDS)
    except RecordError as exc:
        typed_rejection = str(exc)
    else:
        typed_rejection = ""
    legacy_bad = legacy.summarize(legacy.load_records(str(BAD_RECORDS)))
    print(f"\n  BEFORE on bad data : silently total={legacy_bad['total']} "
          f"(accepts negative units - bug!)")
    print(f"  AFTER  on bad data : RecordError: {typed_rejection}")

    # Empty file: legacy crashes with a bare ZeroDivisionError, typed says why.
    try:
        legacy.summarize(legacy.load_records(str(EMPTY_RECORDS)))
    except ZeroDivisionError:
        legacy_empty = "ZeroDivisionError (no explanation)"
    try:
        load_records(EMPTY_RECORDS)
    except RecordError as exc:
        typed_empty = f"RecordError: {exc}"
    print(f"  Empty file         : BEFORE {legacy_empty}; "
          f"AFTER {typed_empty}")

    # Protocol: unrelated types satisfy the same interface structurally.
    refund = Refund(20.0)
    mixed = revenue_total([*records, refund])
    print(f"\n  Protocol  : isinstance(SaleRecord, SupportsRevenue) = "
          f"{isinstance(records[0], SupportsRevenue)}; "
          f"isinstance(Refund, SupportsRevenue) = "
          f"{isinstance(refund, SupportsRevenue)}")
    print(f"              revenue_total(records + refund) = {mixed}")

    # Manual, mypy-style contract checking with inspect.
    spec = load_interface_spec()
    results = verify_contracts(contract_classes(), spec)
    violations = sum(len(items) for items in results.values())
    print(f"  Contracts : {', '.join(results)} -> {violations} violations")

    class BrokenThing:
        def count(self, extra: int):        # wrong params, no return hint
            return 1

    broken = check_contract(BrokenThing, {
        "count": {"params": [], "annotated": True},
        "absent": {"params": [], "annotated": False},
    })
    print(f"              checker flags a broken class: {len(broken)} "
          f"violations")

    # --- cross-checks the demo asserts ----------------------------------- #
    assert legacy_summary["count"] == typed_summary.count == 8
    assert legacy_summary["total"] == typed_summary.total
    assert round(typed_summary.total, 2) == 581.58, "unexpected total"
    assert legacy_summary["mean"] == typed_summary.mean
    assert legacy_summary["top"] == typed_summary.top_id == "S-5"

    assert typed_rejection.startswith("record 0: units must be >= 1")
    assert legacy_bad["total"] == -14.0, "legacy should be silently wrong"
    assert legacy_empty.startswith("ZeroDivisionError")
    assert typed_empty.endswith("no rows in records_empty.csv")

    assert isinstance(records[0], SupportsRevenue)
    assert isinstance(refund, SupportsRevenue)
    assert not isinstance(NotConforming(), SupportsRevenue)
    assert mixed == 561.58
    assert isinstance(records[0].as_payload(), dict)
    assert records[0].as_payload() == {"id": "S-1", "units": 3, "price": 19.99}

    assert violations == 0, f"contract violations: {results}"
    assert len(broken) == 3, "checker must flag all three defects"

    repository = SaleRepository(records)
    assert repository.count() == 8
    assert repository.total() == typed_summary.total
    assert summarize(load_records()) == typed_summary, "not deterministic"

    print(f"\nCross-checks OK: before/after agree ({typed_summary.total}) on "
          f"valid data, typed rejects bad row 0 that legacy silently "
          f"accepts, {violations} contract violations, "
          f"Protocol conformance, deterministic re-run")
    print("Demo completed successfully.")
    return 0
