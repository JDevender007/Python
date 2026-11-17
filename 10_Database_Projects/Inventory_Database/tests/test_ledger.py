"""Tests for the inventory ledger lab: signed ledger data and bare columns."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import ledger  # noqa: E402
import main as cli  # noqa: E402
from ledger import (  # noqa: E402
    EXPECTED_SIGN,
    LedgerError,
    Movement,
    Product,
    apply_movement,
    audit,
    average_product_value_cents,
    build_database,
    category_values,
    check_signed_units,
    divide_half_up,
    format_cents,
    inventory_value_cents,
    is_iso_date,
    legacy_category_values,
    legacy_low_stock,
    legacy_on_hand,
    load_movements,
    load_products,
    load_suppliers,
    low_stock,
    measure,
    movement_counts,
    negative_skus,
    on_hand_ledger,
    on_hand_python,
    parse_cents,
    report,
    require_iso_date,
    run_demo,
)


# --------------------------------------------------------------------------- #
# money
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,cents",
    [
        ("499.00", 49_900),
        ("2499.00", 249_900),
        ("6499.00", 649_900),
        ("0.05", 5),
        ("8.20", 820),
        ("7", 700),
        ("7.5", 750),
        ("+1.00", 100),
        ("-1.05", -105),
        (" 12.30 ", 1230),
        ("121534.00", 12_153_400),
    ],
)
def test_parse_cents_is_exact(text, cents):
    assert parse_cents(text) == cents


@pytest.mark.parametrize("bad", ["", "  ", "1.2.3", "1.234", "abc", "1.a5", ".", "1,"])
def test_parse_cents_refuses_malformed(bad):
    with pytest.raises(LedgerError):
        parse_cents(bad)


def test_parse_cents_refuses_non_text():
    with pytest.raises(LedgerError, match="must be text"):
        parse_cents(499)


def test_parse_cents_names_the_decimal_places():
    with pytest.raises(LedgerError, match="2 decimal places"):
        parse_cents("1.234")


def test_parse_cents_names_the_double_point():
    with pytest.raises(LedgerError, match="more than one decimal point"):
        parse_cents("1.2.3")


@pytest.mark.parametrize(
    "cents,text", [(0, "0.00"), (5, "0.05"), (100, "1.00"), (-105, "-1.05"), (12_153_400, "121534.00")]
)
def test_format_cents(cents, text):
    assert format_cents(cents) == text


@pytest.mark.parametrize("bad", [True, 1.5, "10"])
def test_format_cents_refuses_non_integers(bad):
    with pytest.raises(LedgerError, match="must be an integer"):
        format_cents(bad)


@pytest.mark.parametrize(
    "top,bottom,expected",
    [(12_153_400, 6, 2_025_567), (5, 2, 3), (1, 3, 0), (2, 3, 1), (-5, 2, -3)],
)
def test_divide_half_up(top, bottom, expected):
    assert divide_half_up(top, bottom) == expected


@pytest.mark.parametrize("bottom", [0, -1])
def test_divide_half_up_refuses_bad_denominators(bottom):
    with pytest.raises(LedgerError, match="denominator must be positive"):
        divide_half_up(1, bottom)


# --------------------------------------------------------------------------- #
# dates
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", ["2026-01-02", "2026-01-16", "1999-12-31"])
def test_iso_dates_are_accepted(text):
    assert is_iso_date(text) is True


@pytest.mark.parametrize("text", ["2026-1-2", "2026-13-01", "2026-01-32", "02/01/2026", "", "2026-01-0x"])
def test_iso_dates_are_refused(text):
    assert is_iso_date(text) is False


def test_is_iso_date_refuses_non_text():
    assert is_iso_date(None) is False


def test_require_iso_date_names_the_offender():
    with pytest.raises(LedgerError, match="created_on must be YYYY-MM-DD"):
        require_iso_date("02/01/2026")


# --------------------------------------------------------------------------- #
# the sign rule
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kind,units", [("in", 10), ("out", -10), ("adjustment", 5), ("adjustment", -5)])
def test_a_consistent_sign_is_kept_unchanged(kind, units):
    assert check_signed_units(kind, units) == units


@pytest.mark.parametrize("kind,units", [("in", -1), ("out", 1), ("adjustment", 0), ("in", 0)])
def test_an_inconsistent_sign_is_refused(kind, units):
    with pytest.raises(LedgerError):
        check_signed_units(kind, units)


def test_a_receipt_with_negative_units_is_named():
    with pytest.raises(LedgerError, match="'in' must carry positive units"):
        check_signed_units("in", -4)


def test_an_issue_with_positive_units_is_named():
    with pytest.raises(LedgerError, match="'out' must carry negative units"):
        check_signed_units("out", 4)


def test_zero_units_is_named():
    with pytest.raises(LedgerError, match="must not be zero"):
        check_signed_units("adjustment", 0)


def test_an_unknown_label_is_named():
    with pytest.raises(LedgerError, match="movement must be one of"):
        check_signed_units("shrinkage", -1)


def test_only_out_is_guarded_by_a_sign():
    assert EXPECTED_SIGN["in"] == 1
    assert EXPECTED_SIGN["out"] == -1
    assert EXPECTED_SIGN["adjustment"] == 0


# --------------------------------------------------------------------------- #
# loaders
# --------------------------------------------------------------------------- #
def test_load_suppliers_from_bundled_seed():
    suppliers = load_suppliers()
    assert [s.name for s in suppliers] == ["Acme Traders", "Global Wholesale", "Coastal Distributors"]
    assert suppliers[0].city == "Mumbai"


def test_load_products_from_bundled_seed():
    products = load_products()
    assert [p.sku for p in products] == [f"SKU100{i}" for i in range(1, 7)]
    assert products[0].unit_price_cents == 49_900
    assert products[5].reorder_level == 5


def test_load_movements_keeps_the_signed_units():
    movements = load_movements()
    assert len(movements) == 13
    assert movements[6].units == -18
    assert movements[11].units == -5
    assert movements[0].units == 60


def test_loader_reports_a_missing_file(tmp_path):
    with pytest.raises(LedgerError, match="file not found"):
        load_movements(tmp_path / "nope.csv")


def test_loader_reports_a_missing_column(tmp_path):
    path = tmp_path / "suppliers.csv"
    path.write_text("id,name\n1,Acme\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="missing column"):
        load_suppliers(path)


def test_loader_refuses_duplicate_supplier_names(tmp_path):
    path = tmp_path / "suppliers.csv"
    path.write_text("id,name,contact,email,city\n1,A,1,a@x,P\n2,A,2,b@x,Q\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="supplier names must be unique"):
        load_suppliers(path)


def test_loader_refuses_duplicate_skus(tmp_path):
    path = tmp_path / "products.csv"
    path.write_text(
        "id,sku,name,category,unit_price,reorder_level,supplier_id\n"
        "1,SKU1,A,Cat,1.00,5,1\n2,SKU1,B,Cat,2.00,5,1\n",
        encoding="utf-8",
    )
    with pytest.raises(LedgerError, match="product SKUs must be unique"):
        load_products(path)


def test_loader_refuses_a_negative_price(tmp_path):
    path = tmp_path / "products.csv"
    path.write_text(
        "id,sku,name,category,unit_price,reorder_level,supplier_id\n"
        "1,SKU1,A,Cat,-1.00,5,1\n",
        encoding="utf-8",
    )
    with pytest.raises(LedgerError, match="unit_price must not be negative"):
        load_products(path)


MOVEMENT_HEADER = "id,product_id,movement,quantity,note,created_on\n"


def test_loader_refuses_a_receipt_with_a_negative_quantity(tmp_path):
    path = tmp_path / "movements.csv"
    path.write_text(MOVEMENT_HEADER + "1,1,in,-5,Bad,2026-01-02\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="'in' must carry positive units"):
        load_movements(path)


def test_loader_refuses_an_issue_with_a_positive_quantity(tmp_path):
    path = tmp_path / "movements.csv"
    path.write_text(MOVEMENT_HEADER + "1,1,out,5,Bad,2026-01-02\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="'out' must carry negative units"):
        load_movements(path)


def test_loader_refuses_a_bad_movement_date(tmp_path):
    path = tmp_path / "movements.csv"
    path.write_text(MOVEMENT_HEADER + "1,1,in,5,Ok,02/01/2026\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="created_on must be YYYY-MM-DD"):
        load_movements(path)


def test_loader_refuses_a_non_numeric_quantity(tmp_path):
    path = tmp_path / "movements.csv"
    path.write_text(MOVEMENT_HEADER + "1,1,in,five,Ok,2026-01-02\n", encoding="utf-8")
    with pytest.raises(LedgerError, match="whole number"):
        load_movements(path)


# --------------------------------------------------------------------------- #
# database and reports
# --------------------------------------------------------------------------- #
@pytest.fixture()
def seeded():
    suppliers = load_suppliers()
    products = load_products()
    movements = load_movements()
    conn = build_database(suppliers, products, movements)
    yield conn, suppliers, products, movements
    conn.close()


def test_build_database_rows(seeded):
    conn, _, _, _ = seeded
    assert conn.execute("SELECT COUNT(*) AS n FROM suppliers").fetchone()["n"] == 3
    assert conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"] == 6
    assert conn.execute("SELECT COUNT(*) AS n FROM stock_movements").fetchone()["n"] == 13


def test_build_database_refuses_an_unknown_supplier():
    suppliers = load_suppliers()
    products = [Product(1, "SKU1", "A", "Cat", 100, 5, 99)]
    with pytest.raises(LedgerError, match="unknown supplier 99"):
        build_database(suppliers, products, [])


def test_build_database_refuses_an_unknown_product():
    suppliers = load_suppliers()
    products = load_products()
    movements = [Movement(1, 99, "in", 5, "Ghost", "2026-01-02")]
    with pytest.raises(LedgerError, match="unknown product 99"):
        build_database(suppliers, products, movements)


def test_build_database_revalidates_the_sign():
    bad = Movement(1, 1, "in", -5, "Bad", "2026-01-02")
    with pytest.raises(LedgerError, match="'in' must carry positive units"):
        build_database(load_suppliers(), load_products(), [bad])


def test_on_hand_is_the_signed_sum(seeded):
    conn, _, _, _ = seeded
    assert on_hand_ledger(conn) == {
        "SKU1001": 37,
        "SKU1002": 9,
        "SKU1003": 125,
        "SKU1004": 180,
        "SKU1005": 10,
        "SKU1006": 5,
    }


def test_on_hand_matches_the_independent_python_sum(seeded):
    conn, _, products, movements = seeded
    totals = on_hand_python(movements)
    for product in products:
        assert on_hand_ledger(conn)[product.sku] == totals[product.id]


def test_legacy_on_hand_reproduces_the_case_branch(seeded):
    conn, _, _, _ = seeded
    assert legacy_on_hand(conn) == {
        "SKU1001": 47,
        "SKU1002": 9,
        "SKU1003": 125,
        "SKU1004": 180,
        "SKU1005": 70,
        "SKU1006": 5,
    }


def test_legacy_and_ledger_agree_without_an_adjustment(seeded):
    conn, _, _, _ = seeded
    ledger_rows = on_hand_ledger(conn)
    legacy_rows = legacy_on_hand(conn)
    for sku in ("SKU1002", "SKU1003", "SKU1004", "SKU1006"):
        assert ledger_rows[sku] == legacy_rows[sku]


def test_legacy_error_is_twice_the_adjustment(seeded):
    conn, _, _, movements = seeded
    ledger_rows = on_hand_ledger(conn)
    legacy_rows = legacy_on_hand(conn)
    for sku, product_id in (("SKU1001", 1), ("SKU1005", 5)):
        adjustments = sum(
            m.units for m in movements if m.product_id == product_id and m.movement == "adjustment"
        )
        assert legacy_rows[sku] - ledger_rows[sku] == -2 * adjustments


def test_low_stock_is_at_or_below_reorder(seeded):
    conn, _, _, _ = seeded
    assert low_stock(conn) == [("SKU1002", 9, 10), ("SKU1005", 10, 15), ("SKU1006", 5, 5)]


def test_legacy_low_stock_misses_the_write_off(seeded):
    conn, _, _, _ = seeded
    assert legacy_low_stock(conn) == ["SKU1002", "SKU1006"]


def test_low_stock_is_inclusive_of_the_reorder_level(seeded):
    conn, _, _, _ = seeded
    units = dict((sku, count) for sku, count, _ in low_stock(conn))
    assert units["SKU1006"] == 5


def test_category_values_price_every_product(seeded):
    conn, _, _, _ = seeded
    assert category_values(conn) == [
        ("Accessories", 125, 2_487_500),
        ("Electronics", 46, 4_095_400),
        ("Furniture", 15, 4_148_500),
        ("Stationery", 180, 1_422_000),
    ]


def test_legacy_category_values_use_one_price_per_category(seeded):
    conn, _, _, _ = seeded
    legacy_rows = legacy_category_values(conn)
    assert legacy_rows[0] == ("Accessories", 125, 2_487_500)
    assert legacy_rows[1] == ("Electronics", 46, 2_295_400)
    assert legacy_rows[2] == ("Furniture", 15, 1_348_500)


def test_legacy_category_total_understates_the_inventory(seeded):
    conn, _, _, _ = seeded
    assert inventory_value_cents(conn) == 12_153_400
    assert sum(row[2] for row in legacy_category_values(conn)) == 7_553_400


def test_category_values_sum_to_the_total(seeded):
    conn, _, _, _ = seeded
    assert sum(row[2] for row in category_values(conn)) == inventory_value_cents(conn)


def test_average_product_value(seeded):
    conn, _, _, _ = seeded
    assert average_product_value_cents(conn) == 2_025_567


def test_average_product_value_is_zero_without_products():
    conn = build_database([], [], [])
    assert average_product_value_cents(conn) == 0


def test_negative_skus_is_empty_for_the_seed(seeded):
    conn, _, _, _ = seeded
    assert negative_skus(conn) == []


def test_negative_skus_reports_an_over_issue(seeded):
    conn, _, _, _ = seeded
    apply_movement(conn, Movement(99, 6, "out", -6, "Lost in transit", "2026-01-25"))
    assert negative_skus(conn) == [("SKU1006", -1)]


def test_movement_counts(seeded):
    conn, _, _, _ = seeded
    counts = movement_counts(conn)
    assert counts["SKU1001"] == {"in": 1, "out": 1, "adjustment": 1}
    assert counts["SKU1005"] == {"in": 1, "out": 0, "adjustment": 1}
    assert sum(c["in"] for c in counts.values()) == 6


# --------------------------------------------------------------------------- #
# posting a movement
# --------------------------------------------------------------------------- #
def test_posting_a_receipt_increases_on_hand(seeded):
    conn, _, _, _ = seeded
    after = apply_movement(conn, Movement(90, 1, "in", 5, "Restock", "2026-01-20"))
    assert after == 42
    assert on_hand_ledger(conn)["SKU1001"] == 42


def test_posting_an_issue_decreases_on_hand(seeded):
    conn, _, _, _ = seeded
    assert apply_movement(conn, Movement(91, 6, "out", -1, "Damaged", "2026-01-20")) == 4


def test_posting_an_adjustment_uses_its_sign(seeded):
    conn, _, _, _ = seeded
    assert apply_movement(conn, Movement(92, 5, "adjustment", -3, "Recount", "2026-01-20")) == 7
    assert apply_movement(conn, Movement(93, 5, "adjustment", 2, "Found", "2026-01-21")) == 9


def test_posting_refuses_a_bad_sign(seeded):
    conn, _, _, _ = seeded
    with pytest.raises(LedgerError, match="'out' must carry negative units"):
        apply_movement(conn, Movement(94, 1, "out", 3, "Bad", "2026-01-20"))


def test_posting_refuses_an_unknown_product(seeded):
    conn, _, _, _ = seeded
    with pytest.raises(LedgerError, match="unknown product 99"):
        apply_movement(conn, Movement(95, 99, "in", 3, "Ghost", "2026-01-20"))


def test_posting_refuses_a_duplicate_id(seeded):
    conn, _, _, _ = seeded
    with pytest.raises(LedgerError, match="already posted"):
        apply_movement(conn, Movement(1, 1, "in", 3, "Again", "2026-01-20"))


def test_posting_refuses_a_bad_date(seeded):
    conn, _, _, _ = seeded
    with pytest.raises(LedgerError, match="created_on must be YYYY-MM-DD"):
        apply_movement(conn, Movement(96, 1, "in", 3, "Bad date", "20/01/2026"))


# --------------------------------------------------------------------------- #
# measure and report
# --------------------------------------------------------------------------- #
def test_measure_pins_the_totals():
    measured = measure()
    assert measured["on_hand"] == {
        "SKU1001": 37,
        "SKU1002": 9,
        "SKU1003": 125,
        "SKU1004": 180,
        "SKU1005": 10,
        "SKU1006": 5,
    }
    assert measured["value"] == 12_153_400
    assert measured["average_value"] == 2_025_567


def test_measure_pins_the_legacy_gap():
    measured = measure()
    assert sum(measured["legacy_on_hand"].values()) - sum(measured["on_hand"].values()) == 70
    assert measured["legacy_on_hand"]["SKU1005"] == 70


def test_measure_keeps_the_low_stock_lists():
    measured = measure()
    assert len(measured["low_stock"]) == 3
    assert measured["legacy_low_stock"] == ["SKU1002", "SKU1006"]


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "conn" not in text
    assert payload["value_cents"] == 12_153_400
    assert payload["on_hand"]["SKU1001"] == 37
    assert payload["legacy_low_stock"] == ["SKU1002", "SKU1006"]
    assert payload["negative"] == []


def test_measure_reads_siblings_from_the_movements_folder(tmp_path):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "suppliers.csv").write_text(
        "id,name,contact,email,city\n1,Only,1,a@x,P\n", encoding="utf-8"
    )
    (folder / "products.csv").write_text(
        "id,sku,name,category,unit_price,reorder_level,supplier_id\n"
        "1,SKU1,Widget,General,10.00,5,1\n",
        encoding="utf-8",
    )
    (folder / "movements.csv").write_text(
        MOVEMENT_HEADER + "1,1,in,20,Opening,2026-01-02\n", encoding="utf-8"
    )
    measured = measure(folder / "movements.csv")
    assert measured["on_hand"] == {"SKU1": 20}
    assert measured["value"] == 20_000


def test_measure_positive_adjustment_can_raise_stock(seeded):
    conn, _, _, _ = seeded
    assert apply_movement(conn, Movement(97, 4, "adjustment", 20, "Found a box", "2026-01-22")) == 200
    assert on_hand_ledger(conn)["SKU1004"] == 200


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_audit_passes_every_check():
    results = audit(measure())
    assert len(results) >= 20
    assert all(ok for _, ok in results)


def test_audit_names_are_unique():
    names = [name for name, _ in audit(measure())]
    assert len(names) == len(set(names))


def test_audit_negative_control_legacy_reader_flips_the_signed_sum():
    results = dict(audit(measure(), read_on_hand=legacy_on_hand))
    assert results["on_hand_is_the_signed_sum"] is False
    assert results["on_hand_matches_the_pinned_seed"] is False
    assert results["legacy_reads_the_shrinkage_as_a_receipt"] is False


def test_audit_negative_control_reader_that_returns_nothing():
    def broken(conn):
        return {}

    results = dict(audit(measure(), read_on_hand=broken))
    assert results["on_hand_is_the_signed_sum"] is False


def test_audit_negative_control_reader_with_one_wrong_value():
    def shifted(conn):
        rows = on_hand_ledger(conn)
        rows["SKU1001"] = 47
        return rows

    results = dict(audit(measure(), read_on_hand=shifted))
    assert results["on_hand_matches_the_pinned_seed"] is False
    assert results["on_hand_is_the_signed_sum"] is False
    assert results["legacy_reads_the_shrinkage_as_a_receipt"] is False


def test_audit_detects_a_tampered_value():
    measured = measure()
    measured["value"] = 1
    results = dict(audit(measured))
    assert results["inventory_value_is_pinned"] is False


def test_audit_detects_a_tampered_low_stock_list():
    measured = measure()
    measured["legacy_low_stock"] = ["SKU1002", "SKU1005", "SKU1006"]
    results = dict(audit(measured))
    assert results["legacy_low_stock_misses_the_write_off"] is False


# --------------------------------------------------------------------------- #
# demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_returns_zero_and_ends_with_the_contract(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    second = capsys.readouterr().out
    assert first == second


def test_demo_reports_the_pinned_numbers(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "121534.00" in out
    assert "20255.67" in out
    assert "SKU1005 10/15" in out
    assert "Legacy low stock: SKU1002, SKU1006" in out
    assert "75534.00" in out


def test_demo_prints_every_check_as_pass(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "FAIL" not in out
    assert "20/20 checks pass" in out


def test_cli_demo_exits_zero():
    assert cli.main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_json_writes_a_report(tmp_path):
    target = tmp_path / "report.json"
    assert cli.main(["--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["value_cents"] == 12_153_400


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such.csv"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_bad_sign_exits_two(tmp_path, capsys):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "suppliers.csv").write_text(
        "id,name,contact,email,city\n1,Only,1,a@x,P\n", encoding="utf-8"
    )
    (folder / "products.csv").write_text(
        "id,sku,name,category,unit_price,reorder_level,supplier_id\n"
        "1,SKU1,Widget,General,10.00,5,1\n",
        encoding="utf-8",
    )
    (folder / "movements.csv").write_text(
        MOVEMENT_HEADER + "1,1,out,5,Bad,2026-01-02\n", encoding="utf-8"
    )
    assert cli.main(["--file", str(folder / "movements.csv")]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_quiet_json_still_writes(tmp_path):
    target = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(target)]) == 0
    assert target.is_file()


def test_module_demo_entry_point():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        assert ledger.run_demo() == 0
    assert buffer.getvalue().strip().endswith("Demo completed successfully.")


def test_demo_writes_nothing_to_stderr():
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        run_demo()
    assert err.getvalue() == ""
