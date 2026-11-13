"""Tests for the Type Hints Refactoring project (before/after modules)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import dataclasses
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import legacy  # noqa: E402
from typed import (  # noqa: E402
    BAD_RECORDS,
    EMPTY_RECORDS,
    INTERFACES,
    RECORDS,
    ContractError,
    NotConforming,
    Refund,
    RecordError,
    SaleRecord,
    SaleRepository,
    SupportsRevenue,
    Summary,
    check_contract,
    contract_classes,
    load_interface_spec,
    load_records,
    parse_row,
    revenue_total,
    run_demo,
    summarize,
    verify_contracts,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _csv(tmp_path: Path, text: str, name: str = "sales.csv") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Legacy module (BEFORE)
# --------------------------------------------------------------------------- #
def test_legacy_loads_valid_csv():
    rows = legacy.load_records(str(RECORDS))
    assert len(rows) == 8
    assert rows[0] == {"id": "S-1", "units": "3", "price": "19.99"}


def test_legacy_summary_values():
    result = legacy.summarize(legacy.load_records(str(RECORDS)))
    assert result["count"] == 8
    assert result["total"] == 581.58
    assert result["mean"] == 72.7
    assert result["top"] == "S-5"


def test_legacy_empty_crashes_with_zerodivision():
    rows = legacy.load_records(str(EMPTY_RECORDS))
    with pytest.raises(ZeroDivisionError):
        legacy.summarize(rows)


def test_legacy_missing_column_raises_raw_keyerror(tmp_path):
    path = _csv(tmp_path, "id,units\nL-1,2\n")
    with pytest.raises(KeyError):
        legacy.summarize(legacy.load_records(str(path)))


def test_legacy_accepts_negative_units_silently():
    result = legacy.summarize(legacy.load_records(str(BAD_RECORDS)))
    assert result["total"] == -14.0       # the bug the refactor fixes


def test_legacy_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        legacy.load_records(str(tmp_path / "nope.csv"))


# --------------------------------------------------------------------------- #
# Typed module: loading and validation (AFTER)
# --------------------------------------------------------------------------- #
def test_typed_loads_valid_csv():
    records = load_records()
    assert len(records) == 8
    assert all(isinstance(r, SaleRecord) for r in records)
    assert RECORDS.parent == PROJECT_ROOT / "data"
    first = records[0]
    assert first.id == "S-1" and first.units == 3 and first.price == 19.99
    assert first.revenue() == pytest.approx(59.97)


def test_typed_missing_file(tmp_path):
    with pytest.raises(RecordError, match="file not found"):
        load_records(tmp_path / "nope.csv")


def test_typed_missing_column(tmp_path):
    path = _csv(tmp_path, "id,units\nS-1,2\n")
    with pytest.raises(RecordError, match="missing column"):
        load_records(path)


def test_typed_no_rows(tmp_path):
    path = _csv(tmp_path, "id,units,price\n")
    with pytest.raises(RecordError, match="no rows"):
        load_records(path)


def test_typed_empty_id_cell(tmp_path):
    path = _csv(tmp_path, "id,units,price\n,2,5.00\n")
    with pytest.raises(RecordError,
                       match=r"record 0 missing value\(s\): id"):
        load_records(path)


def test_typed_units_not_integer(tmp_path):
    path = _csv(tmp_path, "id,units,price\nA-1,1.5,2.00\n")
    with pytest.raises(RecordError, match="record 0: units must be an int"):
        load_records(path)


def test_typed_units_below_one():
    with pytest.raises(RecordError, match="record 0: units must be >= 1"):
        load_records(BAD_RECORDS)


def test_typed_price_not_number(tmp_path):
    path = _csv(tmp_path, "id,units,price\nA-1,2,cheap\n")
    with pytest.raises(RecordError, match="record 0: price must be a number"):
        load_records(path)


def test_typed_price_must_be_positive(tmp_path):
    path = _csv(tmp_path, "id,units,price\nA-1,2,0.00\n")
    with pytest.raises(RecordError, match="record 0: price must be > 0"):
        load_records(path)


def test_typed_price_must_be_finite(tmp_path):
    path = _csv(tmp_path, "id,units,price\nA-1,2,nan\n")
    with pytest.raises(RecordError, match="record 0: price must be finite"):
        load_records(path)


def test_parse_row_first_error_wins():
    with pytest.raises(RecordError, match="missing value"):
        parse_row({"id": "", "units": "bad", "price": "bad"}, 0)


# --------------------------------------------------------------------------- #
# SaleRecord contract
# --------------------------------------------------------------------------- #
def test_sale_record_revenue_math():
    record = SaleRecord(id="X", units=4, price=2.5)
    assert record.revenue() == 10.0


def test_sale_record_is_frozen_with_slots():
    record = SaleRecord(id="X", units=1, price=1.0)
    assert not hasattr(record, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.id = "Y"  # type: ignore[misc]


def test_sale_record_post_init_validation():
    with pytest.raises(RecordError, match="id must be a non-empty string"):
        SaleRecord(id="", units=1, price=1.0)
    with pytest.raises(RecordError, match="units must be an integer"):
        SaleRecord(id="X", units=True, price=1.0)  # type: ignore[arg-type]
    with pytest.raises(RecordError, match="units must be >= 1"):
        SaleRecord(id="X", units=0, price=1.0)
    with pytest.raises(RecordError, match="price must be > 0"):
        SaleRecord(id="X", units=1, price=0.0)


def test_sale_record_as_payload():
    payload = SaleRecord(id="S-1", units=3, price=19.99).as_payload()
    assert payload == {"id": "S-1", "units": 3, "price": 19.99}
    assert set(payload) == {"id", "units", "price"}
    json.dumps(payload)


# --------------------------------------------------------------------------- #
# Summaries
# --------------------------------------------------------------------------- #
def test_summarize_values():
    summary = summarize(load_records())
    assert isinstance(summary, Summary)
    assert summary.count == 8
    assert summary.total == 581.58
    assert summary.mean == 72.7
    assert summary.top_id == "S-5"


def test_summarize_empty_is_an_error():
    with pytest.raises(RecordError, match="no records to summarize"):
        summarize([])


def test_summarize_is_deterministic_and_serialisable():
    first, second = summarize(load_records()), summarize(load_records())
    assert first == second
    assert set(first.as_dict()) == {"count", "total", "mean", "top"}


# --------------------------------------------------------------------------- #
# Protocols
# --------------------------------------------------------------------------- #
def test_runtime_protocol_conformance():
    assert isinstance(SaleRecord(id="X", units=1, price=1.0),
                      SupportsRevenue)
    assert isinstance(Refund(5.0), SupportsRevenue)
    assert not isinstance(NotConforming(), SupportsRevenue)


def test_revenue_total_over_records():
    assert revenue_total(load_records()) == 581.58


def test_revenue_total_mixes_unrelated_types():
    mixed = revenue_total([*load_records(), Refund(20.0)])
    assert mixed == 561.58


def test_refund_validation():
    refund = Refund(5)
    assert refund.revenue() == -5.0
    with pytest.raises(RecordError, match="refund amount must be > 0"):
        Refund(0)
    with pytest.raises(RecordError, match="refund amount must be a number"):
        Refund("five")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Repository
# --------------------------------------------------------------------------- #
def test_repository_basics():
    repository = SaleRepository(load_records())
    assert repository.count() == 8
    assert repository.total() == 581.58
    assert len(repository.all()) == 8


def test_repository_load_replaces_contents():
    repository = SaleRepository()
    assert repository.count() == 0
    assert repository.load(RECORDS) == 8
    assert repository.total() == 581.58


def test_repository_all_returns_a_copy():
    repository = SaleRepository(load_records())
    snapshot = repository.all()
    snapshot.clear()
    assert repository.count() == 8


# --------------------------------------------------------------------------- #
# Manual interface contracts
# --------------------------------------------------------------------------- #
def test_load_bundled_interface_spec():
    spec = load_interface_spec()
    assert set(spec) == {"SaleRecord", "SaleRepository"}
    assert spec["SaleRecord"]["revenue"]["params"] == []
    assert INTERFACES.parent == PROJECT_ROOT / "data"


def test_real_classes_satisfy_their_contracts():
    spec = load_interface_spec()
    results = verify_contracts(contract_classes(), spec)
    assert results == {"SaleRecord": [], "SaleRepository": []}


def test_check_contract_missing_method():
    violations = check_contract(NotConforming,
                                {"revenue": {"params": [],
                                             "annotated": False}})
    assert violations == ["NotConforming: missing method 'revenue'"]


def test_check_contract_param_mismatch():
    violations = check_contract(
        Refund, {"revenue": {"params": ["amount"], "annotated": False}})
    assert violations == [
        "Refund.revenue: params [] != declared ['amount']"]


def test_check_contract_annotation_requirements():
    class Sloppy:
        def run(self, x):
            return x

    violations = check_contract(Sloppy,
                                {"run": {"params": ["x"], "annotated": True}})
    assert any("parameter without annotation" in v for v in violations)
    assert any("missing return annotation" in v for v in violations)


def test_verify_contracts_unknown_class():
    results = verify_contracts({"SaleRecord": SaleRecord},
                               {"Ghost": {"whatever": {"params": []}}})
    assert results["Ghost"] == ["no class registered for 'Ghost'"]


def test_interface_spec_errors(tmp_path):
    with pytest.raises(ContractError, match="file not found"):
        load_interface_spec(tmp_path / "nope.json")
    bad = tmp_path / "spec.json"
    bad.write_text("{oops", encoding="utf-8")
    with pytest.raises(ContractError, match="could not parse"):
        load_interface_spec(bad)
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    with pytest.raises(ContractError, match="non-empty object"):
        load_interface_spec(empty)


def test_interface_spec_rule_requires_params(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"A": {"m": {"annotated": True}}}),
                    encoding="utf-8")
    with pytest.raises(ContractError, match="needs 'params'"):
        load_interface_spec(path)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "BEFORE legacy.py" in out and "AFTER  typed.py" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_cli_file_summary(capsys):
    assert main(["--file", str(RECORDS)]) == 0
    out = capsys.readouterr().out
    assert "Records: 8" in out
    assert "Total revenue: 581.58" in out
    assert "Top record: S-5" in out and "Done." in out


def test_cli_file_missing(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.csv")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_file_invalid_rows(capsys):
    assert main(["--file", str(BAD_RECORDS)]) == 2
    assert "record 0: units must be >= 1" in capsys.readouterr().err


def test_cli_spec_clean(capsys):
    assert main(["--spec", str(INTERFACES)]) == 0
    out = capsys.readouterr().out
    assert "0 violations across 2 interfaces" in out


def test_cli_spec_violations(tmp_path, capsys):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"Ghost": {"m": {"params": []}}}),
                    encoding="utf-8")
    assert main(["--spec", str(path)]) == 2
    assert "no class registered" in capsys.readouterr().err


def test_cli_spec_missing(tmp_path, capsys):
    assert main(["--spec", str(tmp_path / "nope.json")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])
    assert "--demo --file --spec" in capsys.readouterr().err


def test_cli_mutually_exclusive_actions(capsys):
    with pytest.raises(SystemExit):
        main(["--demo", "--file", str(RECORDS)])


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""
