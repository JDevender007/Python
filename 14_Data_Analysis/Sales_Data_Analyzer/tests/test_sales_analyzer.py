"""Tests for the Sales Data Analyzer project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import _run_demo, main  # noqa: E402
from sales_analyzer import (  # noqa: E402
    DEMO_CSV,
    PERIOD_CODES,
    PERIODS,
    REQUIRED_COLUMNS,
    SalesError,
    SalesReport,
    analyze,
    load_sales,
    render_report,
    run_demo,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _csv(tmp_path: Path, rows: list[dict], columns=None) -> Path:
    frame = pd.DataFrame(rows, columns=columns)
    path = tmp_path / "sales.csv"
    frame.to_csv(path, index=False)
    return path


def _row(**overrides) -> dict:
    row = {
        "order_id": "ORD-1", "date": "2024-01-05", "region": "North",
        "category": "Toys", "product": "Puzzle", "quantity": 2,
        "unit_price": 10.0, "revenue": 20.0,
    }
    row.update(overrides)
    return row


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_sales(DEMO_CSV)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) > 500
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert sample["date"].is_monotonic_increasing


def test_load_missing_file(tmp_path):
    with pytest.raises(SalesError, match="not found"):
        load_sales(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = _csv(tmp_path, [{"order_id": "1", "date": "2024-01-01"}])
    with pytest.raises(SalesError, match="missing column"):
        load_sales(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(SalesError, match="no rows"):
        load_sales(path)


def test_load_bad_date(tmp_path):
    path = _csv(tmp_path, [_row(date="not-a-date")])
    with pytest.raises(SalesError, match="unparseable date"):
        load_sales(path)


def test_load_non_numeric(tmp_path):
    path = _csv(tmp_path, [_row(quantity="two")])
    with pytest.raises(SalesError, match="non-numeric"):
        load_sales(path)


def test_load_negative_values(tmp_path):
    path = _csv(tmp_path, [_row(unit_price=-5.0, revenue=-10.0)])
    with pytest.raises(SalesError, match="negative"):
        load_sales(path)


def test_load_zero_quantity(tmp_path):
    path = _csv(tmp_path, [_row(quantity=0, revenue=0.0)])
    with pytest.raises(SalesError, match="zeros"):
        load_sales(path)


def test_load_recomputes_stale_revenue(tmp_path):
    path = _csv(tmp_path, [_row(quantity=3, unit_price=4.0, revenue=999.0)])
    frame = load_sales(path)
    assert float(frame["revenue"].iloc[0]) == 12.0  # qty * price, not the CSV


def test_load_sorts_by_date(tmp_path):
    path = _csv(tmp_path, [
        _row(order_id="B", date="2024-03-01"),
        _row(order_id="A", date="2024-01-01"),
    ])
    frame = load_sales(path)
    assert list(frame["order_id"]) == ["A", "B"]


def test_load_unparseable_file(tmp_path):
    path = tmp_path / "garbage.csv"
    path.write_bytes(b"\x00\x01\x02 not, really\na csv")
    with pytest.raises(SalesError, match="could not parse|missing column"):
        load_sales(path)


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def test_analyze_totals(sample):
    report = analyze(sample, period="M")
    assert report.total_orders == len(sample)
    assert report.total_units == int(sample["quantity"].sum())
    assert report.total_revenue == pytest.approx(float(sample["revenue"].sum()), abs=0.01)
    assert report.avg_order_value > 0
    assert report.avg_daily_revenue > 0
    assert report.date_min <= report.date_max


def test_analyze_monthly_buckets(sample):
    report = analyze(sample, period="M")
    assert 11 <= len(report.by_period) <= 13  # 2024 data -> 12 months
    assert list(report.by_period.columns) == ["revenue", "orders"]
    assert int(report.by_period["orders"].sum()) == len(sample)
    assert float(report.by_period["revenue"].sum()) == pytest.approx(
        report.total_revenue, abs=0.01)


def test_analyze_other_periods(sample):
    for period in PERIODS:
        report = analyze(sample, period=period)
        assert len(report.by_period) >= 1
        assert report.period == period


def test_analyze_growth(sample):
    report = analyze(sample, period="M")
    assert len(report.growth_pct) == len(report.by_period) - 1
    for label, value in report.growth_pct:
        assert isinstance(label, str) and isinstance(value, float)


def test_analyze_segments_partition_revenue(sample):
    report = analyze(sample)
    for segment in ("region", "category", "product"):
        total = float(report.by_segment[segment]["revenue"].sum())
        assert total == pytest.approx(report.total_revenue, abs=0.01), segment


def test_analyze_segment_sorted_by_revenue(sample):
    report = analyze(sample)
    values = list(report.by_segment["region"]["revenue"])
    assert values == sorted(values, reverse=True)


def test_analyze_top_products(sample):
    report = analyze(sample)
    top = report.top_products(3)
    assert len(top) == 3
    assert list(top.index)[:1] == list(report.by_segment["product"].index)[:1]


def test_analyze_moving_average(sample):
    report = analyze(sample, period="M", window=3)
    assert len(report.moving_average) == len(report.by_period)
    assert float(report.moving_average.iloc[-1]) > 0


def test_analyze_rejects_bad_period(sample):
    with pytest.raises(SalesError, match="unknown period"):
        analyze(sample, period="H")


def test_analyze_rejects_unknown_segment(sample):
    with pytest.raises(SalesError, match="unknown segment"):
        analyze(sample, segments=("warehouse",))


def test_analyze_single_row(tmp_path):
    frame = load_sales(_csv(tmp_path, [_row()]))
    report = analyze(frame, period="M")
    assert report.total_orders == 1
    assert report.growth_pct == []
    assert report.avg_order_value == 20.0


# --------------------------------------------------------------------------- #
# Report model and rendering
# --------------------------------------------------------------------------- #
def test_report_to_dict_shape(sample):
    payload = analyze(sample).to_dict()
    for key in ("total_revenue", "total_orders", "total_units", "avg_order_value",
                "date_range", "period", "by_period", "growth_pct",
                "by_region", "by_category", "top_products"):
        assert key in payload
    assert payload["by_region"][0]["name"] in {"North", "South", "East", "West"}
    # serializable
    json.dumps(payload)


def test_render_report_sections(sample):
    text = render_report(analyze(sample), top=3)
    assert "SALES ANALYSIS" in text
    assert "Revenue by period:" in text
    assert "By region:" in text
    assert "By category:" in text
    assert "Top 3 products:" in text
    assert "Trend" in text
    assert "$" in text


def test_render_growth_line(sample):
    text = render_report(analyze(sample, period="M"))
    assert "Growth" in text and "cumulative" in text


def test_render_single_period_no_growth(tmp_path):
    frame = load_sales(_csv(tmp_path, [_row()]))
    text = render_report(analyze(frame))
    assert "Growth" not in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Quarterly buckets" in out
    assert "SALES ANALYSIS" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(SalesError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_file_analysis(capsys):
    assert main(["--file", str(DEMO_CSV)]) == 0
    out = capsys.readouterr().out
    assert "SALES ANALYSIS" in out and "Done." in out


def test_cli_period_and_top(capsys):
    assert main(["--file", str(DEMO_CSV), "--period", "Q", "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "bucketed Q" in out
    assert "Top 3 products:" in out


def test_cli_segment_focus(capsys):
    assert main(["--file", str(DEMO_CSV), "--segment", "product", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Detailed product breakdown:" in out


def test_cli_json_output(tmp_path, capsys):
    out_file = tmp_path / "report.json"
    assert main(["--file", str(DEMO_CSV), "--json", str(out_file)]) == 0
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["total_orders"] > 500
    assert len(payload["by_region"]) == 4


def test_cli_chart_output(tmp_path, capsys):
    chart = tmp_path / "trend.png"
    assert main(["--file", str(DEMO_CSV), "--chart", str(chart), "--quiet"]) == 0
    assert chart.is_file() and chart.stat().st_size > 1000
    assert "Wrote" in capsys.readouterr().out


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_invalid_schema(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "missing column" in capsys.readouterr().err


def test_cli_bad_top(capsys):
    assert main(["--file", str(DEMO_CSV), "--top", "0"]) == 2
    assert "--top" in capsys.readouterr().err


def test_cli_requires_source(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_project_has_sample_data():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent == PROJECT_ROOT / "data"


def test_cli_demo_quiet_prints_nothing(capsys):
    """--demo --quiet writes nothing to stdout or to stderr."""
    assert main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_quiet_demo_returns_the_demo_status():
    """Quiet mode hides output but still reports what the demo returned."""
    assert _run_demo(True, lambda: 7) == 7
    assert _run_demo(False, lambda: 7) == 7


def test_quiet_demo_restores_logging(monkeypatch):
    """Logging is disabled only for the duration of the quiet demo."""
    import logging

    before = logging.root.manager.disable
    seen = []

    def probe():
        seen.append(logging.root.manager.disable)
        return 0

    _run_demo(True, probe)
    assert seen == [logging.CRITICAL]
    assert logging.root.manager.disable == before


# --------------------------------------------------------------------------- #
# Report invariants: the parts must add up to the whole
# --------------------------------------------------------------------------- #
def test_segment_revenue_sums_to_the_total():
    """Every order sits in exactly one region, so the shares must add up."""
    report = analyze(load_sales(DEMO_CSV))
    by_region = float(report.by_segment["region"]["revenue"].sum())
    assert round(by_region, 2) == round(report.total_revenue, 2)


def test_segment_orders_sum_to_the_order_count():
    """A segmentation that loses orders is a bug the totals would hide."""
    report = analyze(load_sales(DEMO_CSV))
    for segment in ("region", "category"):
        assert int(report.by_segment[segment]["orders"].sum()) == report.total_orders


def test_avg_order_value_is_revenue_over_orders():
    report = analyze(load_sales(DEMO_CSV))
    assert report.avg_order_value == round(
        report.total_revenue / report.total_orders, 2
    )


def test_avg_daily_revenue_counts_both_end_dates():
    report = analyze(load_sales(DEMO_CSV))
    span = (report.frame["date"].max() - report.frame["date"].min()).days + 1
    assert report.avg_daily_revenue == round(report.total_revenue / span, 2)


def test_top_products_are_ordered_by_revenue():
    report = analyze(load_sales(DEMO_CSV))
    top = report.top_products(3)
    assert len(top) == 3
    revenues = [float(value) for value in top["revenue"]]
    assert revenues == sorted(revenues, reverse=True)


def test_moving_average_with_a_window_of_one_is_the_raw_series():
    """A window of one is the series itself, so the trend adds nothing."""
    report = analyze(load_sales(DEMO_CSV), window=1)
    raw = [round(float(value), 2) for value in report.by_period["revenue"]]
    smoothed = [round(float(value), 2) for value in report.moving_average]
    assert smoothed == raw


def test_render_report_caps_the_peak_bar_at_twenty_four():
    text = render_report(analyze(load_sales(DEMO_CSV)))
    assert "#" * 24 in text
    assert "#" * 25 not in text


def test_to_dict_survives_a_json_round_trip():
    report = analyze(load_sales(DEMO_CSV))
    payload = json.loads(json.dumps(report.to_dict()))
    assert payload["total_orders"] == report.total_orders
    assert payload["date_range"] == [report.date_min, report.date_max]
    bucketed = sum(entry["revenue"] for entry in payload["by_period"])
    assert abs(bucketed - report.total_revenue) < 0.05


def test_period_codes_cover_every_period():
    """A period the CLI accepts must have a resample code behind it."""
    assert tuple(PERIOD_CODES) == PERIODS
