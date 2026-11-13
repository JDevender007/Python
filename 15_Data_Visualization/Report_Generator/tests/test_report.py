"""Tests for the Report Generator project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from report import (  # noqa: E402
    CHARTS,
    DEMO_CSV,
    DEMO_TITLE,
    REQUIRED_COLUMNS,
    ReportError,
    build_report,
    chart_channel_share,
    chart_margin_by_channel,
    chart_monthly_growth,
    chart_monthly_trend,
    load_data,
    render_html,
    render_markdown,
    run_demo,
    save_report,
    summarize,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    row = {"month": "2025-01", "channel": "Direct",
           "revenue": 1000, "cost": 600, "orders": 10}
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "data.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _grid(rows_by_month: dict[str, dict[str, tuple[int, int, int]]]) -> list[dict]:
    """rows_by_month = {month: {channel: (revenue, cost, orders)}}."""
    rows = []
    for month, channels in rows_by_month.items():
        for channel, (revenue, cost, orders) in channels.items():
            rows.append(_row(month=month, channel=channel,
                             revenue=revenue, cost=cost, orders=orders))
    return rows


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_data(DEMO_CSV)


@pytest.fixture(scope="module")
def summary(sample):
    return summarize(sample)


@pytest.fixture()
def tiny() -> pd.DataFrame:
    """Two months x two channels with exact hand-computable math.

    Direct:  400 + 600 = 1000 revenue, 240 + 300 = 540 cost, 4 + 6 = 10 orders
    Social:  200 + 300 = 500 revenue,  120 + 180 = 300 cost, 2 + 3 = 5 orders
    totals: revenue 1500, cost 840, margin 660 (44%), orders 15, aov 100
    """
    rows = [
        _row(month="2025-01", channel="Direct", revenue=400, cost=240, orders=4),
        _row(month="2025-01", channel="Social", revenue=200, cost=120, orders=2),
        _row(month="2025-02", channel="Direct", revenue=600, cost=300, orders=6),
        _row(month="2025-02", channel="Social", revenue=300, cost=180, orders=3),
    ]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 48
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert sample["channel"].nunique() == 4
    assert sample["month"].nunique() == 12
    assert not sample.duplicated(subset=["month", "channel"]).any()
    assert (sample["revenue"] >= 0).all() and (sample["orders"] >= 0).all()


def test_load_missing_file(tmp_path):
    with pytest.raises(ReportError, match="not found"):
        load_data(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("month,revenue\n2025-01,100\n", encoding="utf-8")
    with pytest.raises(ReportError, match="missing column"):
        load_data(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(ReportError, match="no rows"):
        load_data(path)


def test_load_bad_month(tmp_path):
    path = _csv(tmp_path, [_row(month="January")])
    with pytest.raises(ReportError, match="YYYY-MM"):
        load_data(path)


def test_load_empty_channel(tmp_path):
    path = _csv(tmp_path, [_row(channel=None)])
    with pytest.raises(ReportError, match="empty channel"):
        load_data(path)


def test_load_non_numeric_revenue(tmp_path):
    path = _csv(tmp_path, [_row(revenue="lots")])
    with pytest.raises(ReportError, match="non-numeric"):
        load_data(path)


def test_load_negative_cost(tmp_path):
    path = _csv(tmp_path, [_row(cost=-1)])
    with pytest.raises(ReportError, match="non-negative"):
        load_data(path)


def test_load_fractional_orders(tmp_path):
    path = _csv(tmp_path, [_row(orders=2.5)])
    with pytest.raises(ReportError, match="whole numbers"):
        load_data(path)


def test_load_duplicate_month_channel(tmp_path):
    path = _csv(tmp_path, [_row(), _row(revenue=2000)])
    with pytest.raises(ReportError, match="duplicate"):
        load_data(path)


def test_load_single_channel(tmp_path):
    rows = [_row(month="2025-01"), _row(month="2025-02")]
    with pytest.raises(ReportError, match="at least two channels"):
        load_data(_csv(tmp_path, rows))


def test_load_single_month(tmp_path):
    rows = [_row(channel="Direct"), _row(channel="Social")]
    with pytest.raises(ReportError, match="at least two months"):
        load_data(_csv(tmp_path, rows))


# --------------------------------------------------------------------------- #
# Summarize
# --------------------------------------------------------------------------- #
def test_summarize_exact_totals(tiny):
    summary = summarize(tiny)
    totals = summary.totals
    assert totals["revenue"] == 1500.0
    assert totals["cost"] == 840.0
    assert totals["margin"] == 660.0
    assert totals["margin_pct"] == pytest.approx(44.0)
    assert totals["orders"] == 15.0
    assert totals["aov"] == pytest.approx(100.0)
    assert totals["months"] == 2.0
    assert totals["channels"] == 2.0
    assert totals["rows"] == 4.0


def test_summarize_by_channel_math(tiny):
    summary = summarize(tiny)
    by_channel = summary.by_channel
    assert set(by_channel.index) == {"Direct", "Social"}
    assert by_channel.loc["Direct", "revenue"] == 1000.0
    assert by_channel.loc["Social", "revenue"] == 500.0
    assert by_channel.loc["Direct", "margin"] == 460.0
    assert by_channel.loc["Direct", "share_pct"] == pytest.approx(
        1000 / 1500 * 100)
    assert by_channel.loc["Direct", "margin_pct"] == pytest.approx(46.0)
    assert summary.best_channel == "Direct"
    revenues = list(by_channel["revenue"])
    assert revenues == sorted(revenues, reverse=True)


def test_summarize_monthly_math(tiny):
    summary = summarize(tiny)
    monthly = summary.monthly
    assert list(monthly.index) == ["2025-01", "2025-02"]
    assert monthly.loc["2025-01", "revenue"] == 600.0
    assert monthly.loc["2025-02", "revenue"] == 900.0
    # growth: (900 - 600) / 600 = +50%
    assert monthly.loc["2025-02", "growth_pct"] == pytest.approx(50.0)
    assert pd.isna(monthly.loc["2025-01", "growth_pct"])  # no prior month
    assert summary.best_month == "2025-02"
    assert summary.worst_month == "2025-01"


def test_summarize_partitions(sample, summary):
    assert summary.totals["revenue"] == float(sample["revenue"].sum())
    assert summary.by_channel["revenue"].sum() == float(sample["revenue"].sum())
    assert summary.monthly["revenue"].sum() == float(sample["revenue"].sum())
    assert abs(summary.by_channel["share_pct"].sum() - 100) < 1e-6


def test_summarize_notes_present(sample, summary):
    assert len(summary.notes) >= 4
    assert any("Revenue grew" in note or "Revenue fell" in note
               for note in summary.notes)
    assert any("leads with" in note for note in summary.notes)
    assert any("Thinnest margin" in note for note in summary.notes)


def test_summarize_to_dict_serializable(summary):
    payload = summary.to_dict()
    json.dumps(payload)
    assert payload["totals"]["revenue"] > 0
    assert len(payload["by_channel"]) == 4
    assert len(payload["monthly"]) == 12
    assert payload["best_channel"] in {c["channel"] for c in payload["by_channel"]}
    assert len(payload["notes"]) >= 4


def test_summarize_rejects_zero_orders():
    rows = [
        _row(month="2025-01", channel="Direct", revenue=100, cost=50, orders=0),
        _row(month="2025-01", channel="Social", revenue=200, cost=80, orders=0),
        _row(month="2025-02", channel="Direct", revenue=110, cost=55, orders=0),
        _row(month="2025-02", channel="Social", revenue=210, cost=85, orders=0),
    ]
    summary = summarize(pd.DataFrame(rows))
    assert summary.totals["aov"] == 0.0  # no division by zero


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def test_registry_contains_expected_charts():
    assert set(CHARTS) == {"trend", "share", "margin", "growth"}
    for name, (function, caption) in CHARTS.items():
        assert callable(function), name
        assert caption


@pytest.mark.parametrize("chart_fn", list(CHARTS.values()),
                         ids=[name for name, _ in CHARTS.items()])
def test_every_chart_returns_base64_png(summary, chart_fn):
    function, _ = chart_fn
    uri = function(summary)
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 5_000  # a real PNG, not an empty frame
    assert plt.get_fignums() == []


def test_charts_do_not_leak_figures(summary):
    for function, _ in CHARTS.values():
        function(summary)
    assert plt.get_fignums() == []


# --------------------------------------------------------------------------- #
# Report assembly
# --------------------------------------------------------------------------- #
def test_render_markdown_sections(tiny):
    summary = summarize(tiny)
    markdown = render_markdown(summary, "Tiny Report")
    assert markdown.startswith("# Tiny Report")
    assert "## Key metrics" in markdown
    assert "## By channel" in markdown
    assert "## Monthly totals" in markdown
    assert "## Insights" in markdown
    assert "| Direct | $1,000 |" in markdown
    assert "| Social | $500 |" in markdown
    assert "$1,500" in markdown  # total revenue
    assert "50.0%" in markdown   # Feb growth


def test_render_markdown_growth_dash_for_first_month(tiny):
    markdown = render_markdown(summarize(tiny), "T")
    assert "| 2025-01 | $600 | — |" in markdown
    assert "| 2025-02 | $900 | +50.0% |" in markdown


def test_render_html_structure(tiny):
    summary = summarize(tiny)
    document = render_html(summary, "Tiny <Report>")
    assert document.startswith("<!DOCTYPE html>")
    assert "<title>Tiny &lt;Report&gt;</title>" in document  # escaped
    assert document.count("data:image/png;base64,") == 4
    assert "<script" not in document
    assert "Tiny &lt;Report&gt;" in document  # header escaped too
    # tables
    assert "<th>Channel</th>" in document
    assert "<th>Month</th>" in document
    assert "<td>Direct</td>" in document


def test_render_html_has_no_external_resources(summary):
    document = render_html(summary, "X")
    for token in ('src="http', 'href="http', 'url(http', "<script"):
        assert token not in document, token


def test_render_html_escapes_channel_names(tmp_path):
    rows = _grid({
        "2025-01": {"<b>Direct</b>": (100, 60, 2), "Social": (50, 30, 1)},
        "2025-02": {"<b>Direct</b>": (120, 70, 2), "Social": (60, 36, 1)},
    })
    summary = summarize(load_data(_csv(tmp_path, rows)))
    document = render_html(summary, "Escapes")
    assert "&lt;b&gt;Direct&lt;/b&gt;" in document
    assert "<td><b>Direct</b>" not in document  # raw HTML must not survive
    assert "<title>Escapes</title>" in document  # plain title passes through


def test_build_report_returns_both_formats(tiny):
    document, markdown = build_report(tiny, "Both")
    assert "<!DOCTYPE html>" in document
    assert markdown.startswith("# Both")


def test_save_report_writes_files(tmp_path, sample):
    paths = save_report(sample, tmp_path / "out", "Saved")
    html_path, md_path = paths["html"], paths["markdown"]
    assert html_path.is_file() and html_path.stat().st_size > 50_000
    assert md_path.is_file() and md_path.stat().st_size > 0
    assert "data:image/png;base64," in html_path.read_text(encoding="utf-8")
    assert "# Saved" in md_path.read_text(encoding="utf-8")


def test_save_report_is_idempotent(tmp_path, sample):
    first = save_report(sample, tmp_path / "out", "Same")
    html_size = first["html"].stat().st_size
    second = save_report(sample, tmp_path / "out", "Same")
    assert second["html"].stat().st_size == html_size  # deterministic


def test_save_report_rejects_tiny_html(tmp_path, monkeypatch):
    import report
    monkeypatch.setattr(report, "render_html",
                        lambda summary, title: "<!DOCTYPE html><html></html>")
    frame = pd.DataFrame([
        _row(month="2025-01"), _row(month="2025-02", channel="Social"),
    ])
    with pytest.raises(ReportError, match="too small"):
        report.save_report(frame, tmp_path / "x", "T")


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert run_demo(out_dir=out_dir) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Insights:" in out
    assert (out_dir / "report.html").is_file()
    assert (out_dir / "report.md").is_file()


def test_run_demo_is_idempotent(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert run_demo(out_dir=out_dir) == 0
    html_size = (out_dir / "report.html").stat().st_size
    assert run_demo(out_dir=out_dir) == 0
    out = capsys.readouterr().out
    assert out.count("Demo completed successfully.") == 2
    assert (out_dir / "report.html").stat().st_size == html_size


def test_run_demo_quiet(tmp_path, capsys):
    assert run_demo(out_dir=tmp_path / "q", quiet=True) == 0
    assert capsys.readouterr().out == ""


def test_run_demo_missing_sample(tmp_path, monkeypatch):
    import report
    monkeypatch.setattr(report, "DEMO_CSV", tmp_path / "absent.csv")
    with pytest.raises(ReportError, match="bundled sample"):
        report.run_demo(out_dir=tmp_path / "x")


def test_demo_html_is_offline_safe(tmp_path):
    run_demo(out_dir=tmp_path / "out", quiet=True)
    document = (tmp_path / "out" / "report.html").read_text(encoding="utf-8")
    assert document.count("data:image/png;base64,") == len(CHARTS)
    for token in ('src="http', 'href="http', 'url(http', "<script"):
        assert token not in document, token


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(tmp_path, capsys):
    out_dir = tmp_path / "cli"
    assert main(["--demo", "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert (out_dir / "report.html").is_file()
    assert (out_dir / "report.md").is_file()


def test_cli_demo_quiet(tmp_path, capsys):
    assert main(["--demo", "--out", str(tmp_path / "q"), "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_demo_with_json(tmp_path, capsys):
    payload_path = tmp_path / "summary.json"
    out_dir = tmp_path / "charts"
    assert main(["--demo", "--out", str(out_dir),
                 "--json", str(payload_path)]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["totals"]["revenue"] > 0
    assert len(payload["by_channel"]) == 4
    assert len(payload["monthly"]) == 12


def test_cli_file_analysis(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert main(["--file", str(DEMO_CSV), "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "Insights:" in out and "Done." in out
    assert (out_dir / "report.html").is_file()


def test_cli_title_option(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert main(["--file", str(DEMO_CSV), "--title", "Q4 Review",
                 "--out", str(out_dir), "--quiet"]) == 0
    document = (out_dir / "report.html").read_text(encoding="utf-8")
    assert "Q4 Review" in document
    markdown = (out_dir / "report.md").read_text(encoding="utf-8")
    assert markdown.startswith("# Q4 Review")


def test_cli_format_md_only(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert main(["--file", str(DEMO_CSV), "--format", "md",
                 "--out", str(out_dir), "--quiet"]) == 0
    assert (out_dir / "report.md").is_file()
    assert not (out_dir / "report.html").exists()


def test_cli_format_html_only(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert main(["--file", str(DEMO_CSV), "--format", "html",
                 "--out", str(out_dir), "--quiet"]) == 0
    assert (out_dir / "report.html").is_file()
    assert not (out_dir / "report.md").exists()


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "summary.json"
    out_dir = tmp_path / "out"
    assert main(["--file", str(DEMO_CSV), "--out", str(out_dir),
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["totals"]["orders"] > 0


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_invalid_schema(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "missing column" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_project_has_sample_data():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent == PROJECT_ROOT / "data"
