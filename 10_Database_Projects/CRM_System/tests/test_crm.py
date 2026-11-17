"""Tests for the CRM revenue lab: fan-out joins and integer-cent money."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import crm  # noqa: E402
import main as cli  # noqa: E402
from crm import (  # noqa: E402
    CrmError,
    Deal,
    Interaction,
    audit,
    build_database,
    counts,
    divide_half_up,
    format_cents,
    interaction_counts,
    legacy_parse_cents,
    legacy_top_customers,
    load_customers,
    load_deals,
    load_interactions,
    measure,
    open_pipeline_cents,
    parse_cents,
    report,
    run_demo,
    stage_total_cents,
    top_customers,
    won_cents,
)


# --------------------------------------------------------------------------- #
# parse_cents
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,cents",
    [
        ("240000.10", 24_000_010),
        ("95000.25", 9_500_025),
        ("42000.05", 4_200_005),
        ("0.00", 0),
        ("0.01", 1),
        ("0.29", 29),
        ("1.15", 115),
        ("8.20", 820),
        ("7.5", 750),
        ("7", 700),
        ("+1.00", 100),
        ("-1.05", -105),
        (" 12.30 ", 1230),
        ("999999.99", 99_999_999),
    ],
)
def test_parse_cents_is_exact(text, cents):
    assert parse_cents(text) == cents


@pytest.mark.parametrize("bad", ["", "   ", "1.2.3", "1.234", "abc", "1.a5", ".", "1,"])
def test_parse_cents_refuses_malformed_money(bad):
    with pytest.raises(CrmError):
        parse_cents(bad)


def test_parse_cents_refuses_non_text():
    with pytest.raises(CrmError, match="must be text"):
        parse_cents(1.20)


def test_parse_cents_refuses_more_than_two_decimals_by_name():
    with pytest.raises(CrmError, match="2 decimal places"):
        parse_cents("1.234")


def test_parse_cents_refuses_two_decimal_points_by_name():
    with pytest.raises(CrmError, match="more than one decimal point"):
        parse_cents("1.2.3")


# --------------------------------------------------------------------------- #
# legacy conversion
# --------------------------------------------------------------------------- #
def test_legacy_conversion_is_exact_on_the_large_seeds():
    assert legacy_parse_cents("240000.10") == 24_000_010
    assert legacy_parse_cents("95000.25") == 9_500_025


@pytest.mark.parametrize("text,cents", [("0.29", 28), ("1.15", 114), ("2.05", 204), ("8.20", 819)])
def test_legacy_conversion_truncates_small_values(text, cents):
    assert legacy_parse_cents(text) == cents
    assert parse_cents(text) == cents + 1


def test_legacy_conversion_loses_exactly_one_cent():
    for text in ("0.29", "1.15", "2.05", "8.20"):
        assert parse_cents(text) - legacy_parse_cents(text) == 1


# --------------------------------------------------------------------------- #
# format_cents and divide_half_up
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "cents,text",
    [(0, "0.00"), (5, "0.05"), (99, "0.99"), (100, "1.00"), (-105, "-1.05"), (24_000_010, "240000.10")],
)
def test_format_cents(cents, text):
    assert format_cents(cents) == text


@pytest.mark.parametrize("bad", [True, 1.5, "10"])
def test_format_cents_refuses_non_integers(bad):
    with pytest.raises(CrmError, match="must be an integer"):
        format_cents(bad)


@pytest.mark.parametrize("top,bottom,expected", [(5, 2, 3), (7, 2, 4), (1, 3, 0), (2, 3, 1), (0, 3, 0), (-5, 2, -3)])
def test_divide_half_up(top, bottom, expected):
    assert divide_half_up(top, bottom) == expected


def test_divide_half_up_refuses_zero_denominator():
    with pytest.raises(CrmError, match="denominator must be positive"):
        divide_half_up(1, 0)


def test_divide_half_up_refuses_negative_denominator():
    with pytest.raises(CrmError, match="denominator must be positive"):
        divide_half_up(1, -2)


def test_round_trip_is_canonical():
    for text in ("0.29", "1.15", "2.05", "8.20", "240000.10"):
        assert format_cents(parse_cents(text)) == text


# --------------------------------------------------------------------------- #
# loaders
# --------------------------------------------------------------------------- #
def test_load_customers_from_bundled_seed():
    customers = load_customers()
    assert [c.name for c in customers] == ["Neha Gupta", "Sanjay Rao", "Fatima Khan"]
    assert customers[0].email == "neha@example.com"
    assert customers[0].company == "Bright Labs"


def test_load_deals_parses_money_into_cents():
    deals = load_deals()
    assert [d.cents for d in deals] == [24_000_010, 9_500_025, 4_200_005]
    assert [d.stage for d in deals] == ["proposal", "negotiation", "won"]


def test_load_interactions_from_bundled_seed():
    interactions = load_interactions()
    assert len(interactions) == 4
    assert [i.customer_id for i in interactions] == [1, 1, 2, 3]


def test_loader_reports_a_missing_file(tmp_path):
    with pytest.raises(CrmError, match="file not found"):
        load_customers(tmp_path / "nope.csv")


def test_loader_reports_a_missing_column(tmp_path):
    path = tmp_path / "customers.csv"
    path.write_text("id,name,email\n1,A,a@x\n", encoding="utf-8")
    with pytest.raises(CrmError, match="missing column"):
        load_customers(path)


def test_loader_refuses_duplicate_customer_ids(tmp_path):
    path = tmp_path / "customers.csv"
    path.write_text(
        "id,name,email,company,created_on\n1,A,a@x,Co,2026-01-01\n1,B,b@x,Co,2026-01-02\n",
        encoding="utf-8",
    )
    with pytest.raises(CrmError, match="ids must be unique"):
        load_customers(path)


def test_loader_refuses_duplicate_customer_emails(tmp_path):
    path = tmp_path / "customers.csv"
    path.write_text(
        "id,name,email,company,created_on\n1,A,a@x,Co,2026-01-01\n2,B,A@X,Co,2026-01-02\n",
        encoding="utf-8",
    )
    with pytest.raises(CrmError, match="emails must be unique"):
        load_customers(path)


def test_loader_refuses_an_unknown_stage(tmp_path):
    path = tmp_path / "deals.csv"
    path.write_text(
        "id,customer_id,title,value,stage,close_on\n1,1,T,10.00,daydreaming,2026-01-01\n",
        encoding="utf-8",
    )
    with pytest.raises(CrmError, match="stage must be one of"):
        load_deals(path)


def test_loader_refuses_an_unknown_interaction_kind(tmp_path):
    path = tmp_path / "interactions.csv"
    path.write_text(
        "id,customer_id,kind,summary,created_on\n1,1,fax,hi,2026-01-01\n", encoding="utf-8"
    )
    with pytest.raises(CrmError, match="kind must be one of"):
        load_interactions(path)


def test_loader_refuses_a_non_numeric_id(tmp_path):
    path = tmp_path / "customers.csv"
    path.write_text(
        "id,name,email,company,created_on\nabc,A,a@x,Co,2026-01-01\n", encoding="utf-8"
    )
    with pytest.raises(CrmError, match="whole number"):
        load_customers(path)


# --------------------------------------------------------------------------- #
# database construction
# --------------------------------------------------------------------------- #
@pytest.fixture()
def seeded():
    customers = load_customers()
    deals = load_deals()
    interactions = load_interactions()
    conn = build_database(customers, deals, interactions)
    yield conn, customers, deals, interactions
    conn.close()


def test_build_database_row_counts(seeded):
    conn, _, _, _ = seeded
    assert counts(conn) == {"customers": 3, "deals": 3, "interactions": 4}


def test_build_database_refuses_unknown_customer_on_a_deal():
    customers = load_customers()
    deals = [Deal(1, 99, "Ghost", 100, "won", "2026-01-01")]
    with pytest.raises(CrmError, match="unknown customer 99"):
        build_database(customers, deals, [])


def test_build_database_refuses_unknown_customer_on_an_interaction():
    customers = load_customers()
    rows = [Interaction(1, 99, "call", "2026-01-01")]
    with pytest.raises(CrmError, match="unknown customer 99"):
        build_database(customers, [], rows)


def test_legacy_query_fans_out_neha(seeded):
    conn, _, _, _ = seeded
    rows = dict(legacy_top_customers(conn))
    assert rows["Neha Gupta"] == 48_000_020
    assert rows["Sanjay Rao"] == 9_500_025
    assert rows["Fatima Khan"] == 4_200_005


def test_correct_query_does_not_fan_out(seeded):
    conn, _, _, _ = seeded
    rows = top_customers(conn)
    assert rows[0] == ("Neha Gupta", 24_000_010, 1)
    assert rows[1] == ("Sanjay Rao", 9_500_025, 1)
    assert rows[2] == ("Fatima Khan", 4_200_005, 1)


def test_fan_out_multiplies_by_interaction_count(seeded):
    conn, _, _, _ = seeded
    counts_per_customer = interaction_counts(conn)
    legacy = dict(legacy_top_customers(conn))
    correct = {name: cents for name, cents, _ in top_customers(conn)}
    for name, cents in correct.items():
        assert legacy[name] == cents * counts_per_customer[name]


def test_adding_an_interaction_never_changes_totals(seeded):
    conn, customers, deals, interactions = seeded
    before = [cents for _, cents, _ in top_customers(conn)]
    extra = Interaction(99, customers[0].id, "note", "2026-02-01")
    grown = build_database(customers, deals, [*interactions, extra])
    after = [cents for _, cents, _ in top_customers(grown)]
    assert before == after


def test_interaction_counts(seeded):
    conn, _, _, _ = seeded
    assert interaction_counts(conn) == {"Neha Gupta": 2, "Sanjay Rao": 1, "Fatima Khan": 1}


def test_won_and_open_pipeline(seeded):
    conn, _, _, _ = seeded
    assert won_cents(conn) == 4_200_005
    assert open_pipeline_cents(conn) == 33_500_035


def test_stage_total_covers_only_requested_stages(seeded):
    conn, _, _, _ = seeded
    assert stage_total_cents(conn, ("proposal",)) == 24_000_010
    assert stage_total_cents(conn, ("proposal", "negotiation")) == 33_500_035


def test_stage_total_refuses_an_empty_stage_list(seeded):
    conn, _, _, _ = seeded
    with pytest.raises(CrmError, match="stages must not be empty"):
        stage_total_cents(conn, [])


# --------------------------------------------------------------------------- #
# measure and report
# --------------------------------------------------------------------------- #
def test_measure_pins_the_gap():
    measured = measure()
    assert measured["legacy_total"] == 61_700_050
    assert measured["true_total"] == 37_700_040
    assert measured["legacy_total"] - measured["true_total"] == 24_000_010


def test_measure_loads_counts():
    measured = measure()
    assert measured["counts"] == {"customers": 3, "deals": 3, "interactions": 4}


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "conn" not in text
    assert payload["correct"]["total"] == "377000.40"
    assert payload["legacy"]["total"] == "617000.50"
    assert payload["overstatement_cents"] == 24_000_010
    assert payload["correct"]["rows"][0]["name"] == "Neha Gupta"


def test_report_sibling_files_follow_the_deals_path(tmp_path):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "customers.csv").write_text(
        "id,name,email,company,created_on\n1,Solo,s@x,Solo Co,2026-01-01\n", encoding="utf-8"
    )
    (folder / "interactions.csv").write_text(
        "id,customer_id,kind,summary,created_on\n", encoding="utf-8"
    )
    (folder / "deals.csv").write_text(
        "id,customer_id,title,value,stage,close_on\n1,1,Only deal,10.00,won,2026-01-01\n",
        encoding="utf-8",
    )
    measured = measure(folder / "deals.csv")
    assert measured["counts"] == {"customers": 1, "deals": 1, "interactions": 0}
    assert measured["true_total"] == 1000
    assert measured["legacy_total"] == 1000


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_audit_passes_every_check():
    results = audit(measure())
    assert len(results) >= 12
    assert all(ok for _, ok in results)


def test_audit_names_are_unique():
    names = [name for name, _ in audit(measure())]
    assert len(names) == len(set(names))


def test_audit_negative_control_legacy_reader_fails_the_independent_sum():
    results = dict(audit(measure(), read_totals=legacy_top_customers))
    assert results["correct_rows_match_independent_sum"] is False
    assert results["reports_disagree_row_by_row"] is True


def test_audit_negative_control_reader_that_returns_nothing():
    def broken(conn):
        return []

    results = dict(audit(measure(), read_totals=broken))
    assert results["correct_rows_match_independent_sum"] is False


def test_audit_detects_a_tampered_measurement():
    measured = measure()
    measured["true_total"] = 1
    results = dict(audit(measured))
    assert results["legacy_total_overstates"] is False


# --------------------------------------------------------------------------- #
# demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_returns_zero_and_prints_the_contract(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical_across_runs(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    second = capsys.readouterr().out
    assert first == second


def test_demo_reports_the_pinned_numbers(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "617000.50" in out
    assert "377000.40" in out
    assert "480000.20" in out
    assert "240000.10" in out


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
    assert payload["correct"]["total"] == "377000.40"


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such.csv"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_bad_money_exits_two(tmp_path, capsys):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "customers.csv").write_text(
        "id,name,email,company,created_on\n1,A,a@x,Co,2026-01-01\n", encoding="utf-8"
    )
    (folder / "interactions.csv").write_text(
        "id,customer_id,kind,summary,created_on\n", encoding="utf-8"
    )
    (folder / "deals.csv").write_text(
        "id,customer_id,title,value,stage,close_on\n1,1,T,1.234,won,2026-01-01\n",
        encoding="utf-8",
    )
    assert cli.main(["--file", str(folder / "deals.csv")]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_quiet_json_still_writes(tmp_path):
    target = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(target)]) == 0
    assert target.is_file()


def test_module_demo_entry_point():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        assert crm.run_demo() == 0
    assert buffer.getvalue().strip().endswith("Demo completed successfully.")


def test_demo_prints_nothing_on_stderr():
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        run_demo()
    assert err.getvalue() == ""
