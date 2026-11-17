"""Tests for the Interactive Dashboard project."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dashboard import (  # noqa: E402
    DEFAULT_OUTPUT,
    DEMO_CSV,
    METRICS,
    REQUIRED_COLUMNS,
    DashboardError,
    build_dashboard,
    compute_kpis,
    figure_to_html,
    load_data,
    render_kpis,
    run_demo,
    save_dashboard,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    row = {
        "month": "2025-01", "segment": "Alpha",
        "revenue": 1000, "cost": 500, "orders": 10,
    }
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "data.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_data(DEMO_CSV)


@pytest.fixture(scope="module")
def tiny() -> pd.DataFrame:
    """Two months x one segment with exact hand-computable math.

    revenue 400 + 600 = 1000, cost 480 + 490 = 970, orders 40 + 60 = 100
    growth = (600 - 400) / 400 = 50.0%, margin = 30, margin_pct = 3.0%
    aov = 1000 / 100 = 10.0
    """
    rows = [
        _row(month="2025-01", segment="Alpha", revenue=400, cost=480, orders=40),
        _row(month="2025-02", segment="Alpha", revenue=600, cost=490, orders=60),
    ]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 48
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert sample["segment"].nunique() == 4
    assert sample["month"].nunique() == 12
    assert not sample.duplicated(subset=["month", "segment"]).any()
    assert (sample["revenue"] >= 0).all() and (sample["orders"] >= 0).all()


def test_load_missing_file(tmp_path):
    with pytest.raises(DashboardError, match="not found"):
        load_data(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("month,revenue\n2025-01,100\n", encoding="utf-8")
    with pytest.raises(DashboardError, match="missing column"):
        load_data(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(DashboardError, match="no rows"):
        load_data(path)


def test_load_bad_month(tmp_path):
    path = _csv(tmp_path, [_row(month="January")])
    with pytest.raises(DashboardError, match="YYYY-MM"):
        load_data(path)


def test_load_empty_segment(tmp_path):
    path = _csv(tmp_path, [_row(segment=None)])
    with pytest.raises(DashboardError, match="empty segment"):
        load_data(path)


def test_load_non_numeric_revenue(tmp_path):
    path = _csv(tmp_path, [_row(revenue="lots")])
    with pytest.raises(DashboardError, match="non-numeric"):
        load_data(path)


def test_load_negative_cost(tmp_path):
    path = _csv(tmp_path, [_row(cost=-1)])
    with pytest.raises(DashboardError, match="non-negative"):
        load_data(path)


def test_load_fractional_orders(tmp_path):
    path = _csv(tmp_path, [_row(orders=2.5)])
    with pytest.raises(DashboardError, match="whole numbers"):
        load_data(path)


def test_load_duplicate_month_segment(tmp_path):
    path = _csv(tmp_path, [_row(), _row(revenue=2000)])
    with pytest.raises(DashboardError, match="duplicate"):
        load_data(path)


# --------------------------------------------------------------------------- #
# KPI math
# --------------------------------------------------------------------------- #
def test_kpis_exact_math(tiny):
    kpis = compute_kpis(tiny)
    assert kpis["rows"] == 2
    assert kpis["segments"] == 1
    assert kpis["months"] == 2
    assert kpis["total_revenue"] == 1000.0
    assert kpis["total_cost"] == 970.0
    assert kpis["margin"] == 30.0
    assert kpis["margin_pct"] == 3.0
    assert kpis["total_orders"] == 100
    assert kpis["aov"] == 10.0
    assert kpis["revenue_growth_pct"] == 50.0
    assert kpis["best_segment"] == "Alpha"
    assert kpis["best_month"] == "2025-02"


def test_kpis_match_frame(sample):
    kpis = compute_kpis(sample)
    assert kpis["total_revenue"] == float(sample["revenue"].sum())
    assert kpis["margin"] == round(
        float(sample["revenue"].sum() - sample["cost"].sum()), 2)
    assert kpis["total_orders"] == int(sample["orders"].sum())
    assert kpis["aov"] == pytest.approx(
        float(sample["revenue"].sum()) / int(sample["orders"].sum()), abs=0.01)
    assert kpis["segments"] == 4 and kpis["months"] == 12
    assert kpis["best_segment"] in set(sample["segment"])
    assert kpis["best_month"] in set(sample["month"])


def test_kpis_growth_math(sample):
    kpis = compute_kpis(sample)
    monthly = sample.groupby("month")["revenue"].sum()
    expected = (float(monthly.iloc[-1]) - float(monthly.iloc[0])) \
        / float(monthly.iloc[0]) * 100
    assert kpis["revenue_growth_pct"] == pytest.approx(expected, abs=0.01)


def test_kpis_zero_orders_no_divide_by_zero():
    frame = pd.DataFrame([_row(orders=0)])
    kpis = compute_kpis(frame)
    assert kpis["aov"] == 0.0
    assert kpis["margin_pct"] == 50.0


def test_render_kpis_sections(tiny):
    text = render_kpis(compute_kpis(tiny))
    assert "DASHBOARD KPIs" in text
    assert "Total revenue" in text
    assert "Margin" in text
    assert "Avg order value" in text
    assert "Best segment" in text
    assert "50.0%" in text  # growth shown with sign


# --------------------------------------------------------------------------- #
# Figure structure
# --------------------------------------------------------------------------- #
def test_build_dashboard_trace_count(sample):
    figure = build_dashboard(sample)
    # 4 segments x 3 metrics = 12 line traces, + bar x2 + pie + scatter x2
    assert len(figure.data) == 17


def test_build_dashboard_default_visibility(sample):
    figure = build_dashboard(sample)
    visible = [i for i, trace in enumerate(figure.data)
               if trace.visible is not False]
    # revenue lines (4) + bars (2) + pie (1) + scatter (2)
    assert len(visible) == 9


def test_build_dashboard_metric_switcher(sample):
    figure = build_dashboard(sample)
    menus = figure.layout.updatemenus
    assert menus and len(menus) == 1
    buttons = menus[0].buttons
    assert [b.label for b in buttons] == ["Revenue", "Cost", "Orders"]
    # every button must set a visibility list of full length
    for button in buttons:
        flags = button.args[0]["visible"]
        assert len(flags) == 17
        assert sum(bool(v) for v in flags) == 9


def test_build_dashboard_rangeslider(sample):
    figure = build_dashboard(sample)
    # subplot 1 x axis carries the range slider
    assert figure.layout.xaxis.rangeslider.visible is True


def test_build_dashboard_titles(sample):
    figure = build_dashboard(sample)
    titles = [ann.text for ann in figure.layout.annotations]
    assert any("Monthly trend" in t for t in titles)
    assert any("Revenue vs cost" in t for t in titles)
    assert any("share" in t.lower() for t in titles)
    assert any("Revenue vs orders" in t for t in titles)


def test_build_dashboard_pie_is_dominant_trace(sample):
    figure = build_dashboard(sample)
    pies = [t for t in figure.data if t.type == "pie"]
    assert len(pies) == 1
    assert abs(sum(pies[0].values) - float(sample["revenue"].sum())) < 0.01


def test_build_dashboard_line_metrics(sample):
    figure = build_dashboard(sample)
    lines = [t for t in figure.data if t.type == "scatter" and t.mode == "lines+markers"]
    assert len(lines) == 12
    for trace in lines:
        assert len(trace.x) == 12


# --------------------------------------------------------------------------- #
# HTML export
# --------------------------------------------------------------------------- #
def test_figure_to_html_is_self_contained(sample):
    html = figure_to_html(build_dashboard(sample))
    assert "<html" in html.lower()
    assert "<script src=" not in html, "loads an external script"
    assert not re.search(r"<link[^>]*href=[\"']https?://", html), \
        "loads an external stylesheet"
    assert not re.search(r"<(?:img|iframe)[^>]*src=[\"']https?://", html), \
        "embeds a remote image/iframe"
    assert "plotly" in html.lower()


def test_save_dashboard_writes_large_html(tmp_path, sample):
    target = tmp_path / "site" / "index.html"
    path = save_dashboard(sample, target)
    assert path.is_file()
    assert path.stat().st_size > 1_000_000
    content = path.read_text(encoding="utf-8")
    assert "<script src=" not in content  # plotly.js embedded inline
    for segment in sample["segment"].unique():
        assert segment in content


def test_save_dashboard_is_idempotent(tmp_path, sample):
    target = tmp_path / "dashboard.html"
    first = save_dashboard(sample, target)
    size = first.stat().st_size
    second = save_dashboard(sample, target)
    assert second.stat().st_size == size


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert run_demo(out_dir=out_dir) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "DASHBOARD KPIs" in out
    assert (out_dir / "dashboard.html").is_file()


def test_run_demo_is_idempotent(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert run_demo(out_dir=out_dir) == 0
    assert run_demo(out_dir=out_dir) == 0
    out = capsys.readouterr().out
    assert out.count("Demo completed successfully.") == 2
    assert (out_dir / "dashboard.html").is_file()


def test_run_demo_quiet(tmp_path, capsys):
    assert run_demo(out_dir=tmp_path / "q", quiet=True) == 0
    assert capsys.readouterr().out == ""


def test_run_demo_missing_sample(tmp_path, monkeypatch):
    import dashboard
    monkeypatch.setattr(dashboard, "DEMO_CSV", tmp_path / "absent.csv")
    with pytest.raises(DashboardError, match="bundled sample"):
        dashboard.run_demo(out_dir=tmp_path / "x")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(tmp_path, capsys):
    out = tmp_path / "cli.html"
    assert main(["--demo", "--out", str(out)]) == 0
    captured = capsys.readouterr().out
    assert "Demo completed successfully." in captured
    assert "Open" in captured and "browser" in captured
    assert out.is_file() or (DEFAULT_OUTPUT / "dashboard.html").is_file()


def test_cli_demo_quiet(tmp_path, capsys):
    out = tmp_path / "cli.html"
    assert main(["--demo", "--out", str(out), "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_build_from_sample(capsys):
    out = DEFAULT_OUTPUT / "built.html"
    assert main(["--build", "--out", str(out)]) == 0
    captured = capsys.readouterr().out
    assert "DASHBOARD KPIs" in captured
    assert "self-contained" in captured
    assert out.is_file() and out.stat().st_size > 1_000_000
    out.unlink()  # keep the workspace clean


def test_cli_kpis_text(capsys):
    assert main(["--kpis"]) == 0
    out = capsys.readouterr().out
    assert "DASHBOARD KPIs" in out
    assert "Total revenue" in out


def test_cli_kpis_json(tmp_path, capsys):
    payload_path = tmp_path / "kpis.json"
    assert main(["--kpis", "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["segments"] == 4
    assert payload["months"] == 12
    assert payload["total_revenue"] > 0


def test_cli_build_custom_file(tmp_path, capsys):
    path = _csv(tmp_path, [
        _row(month="2025-01", segment="Alpha", revenue=100, cost=60, orders=2),
        _row(month="2025-02", segment="Alpha", revenue=140, cost=70, orders=3),
    ])
    out = tmp_path / "custom.html"
    assert main(["--build", "--file", str(path), "--out", str(out)]) == 0
    assert out.is_file() and out.stat().st_size > 1_000_000


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--build", "--file", str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_invalid_schema(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main(["--kpis", "--file", str(bad)]) == 2
    assert "missing column" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_project_has_sample_data():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent == PROJECT_ROOT / "data"


# --------------------------------------------------------------------------- #
# KPI contract and HTML assembly
# --------------------------------------------------------------------------- #
EXPECTED_KPI_KEYS = {
    "rows", "segments", "months", "total_revenue", "total_cost", "margin",
    "margin_pct", "total_orders", "aov", "revenue_growth_pct",
    "best_segment", "best_month",
}


def test_kpis_key_set_is_complete(sample):
    assert set(compute_kpis(sample)) == EXPECTED_KPI_KEYS


def test_kpis_best_segment_matches_groupby(sample):
    by_segment = sample.groupby("segment")["revenue"].sum()
    assert compute_kpis(sample)["best_segment"] == str(by_segment.idxmax())


def test_kpis_best_month_matches_groupby(sample):
    by_month = sample.groupby("month")["revenue"].sum()
    assert compute_kpis(sample)["best_month"] == str(by_month.idxmax())


def test_kpis_aov_and_margin_pct_math(sample):
    kpis = compute_kpis(sample)
    assert kpis["aov"] == pytest.approx(
        round(kpis["total_revenue"] / kpis["total_orders"], 2))
    assert kpis["margin_pct"] == pytest.approx(
        round(kpis["margin"] / kpis["total_revenue"] * 100, 2))


def test_metrics_constant_is_exactly_three():
    assert METRICS == ("revenue", "cost", "orders")


def test_render_kpis_has_every_label(tiny):
    text = render_kpis(compute_kpis(tiny))
    for label in ("Total revenue", "Total cost", "Margin", "Orders",
                  "Avg order value", "Revenue growth (first->last month)",
                  "Best segment", "Best month"):
        assert label in text


def test_render_kpis_is_ascii(tiny):
    render_kpis(compute_kpis(tiny)).encode("ascii")


def test_build_dashboard_returns_figure(sample):
    import plotly.graph_objects as go

    assert isinstance(build_dashboard(sample), go.Figure)


def test_figure_to_html_includes_plotly_bundle(sample):
    html = figure_to_html(build_dashboard(sample))
    assert "<html" in html.lower()
    assert "plotly" in html.lower()
    # the library itself is inlined, so no script tag fetches it
    assert '<script src="https://cdn.plot.ly' not in html


def test_save_dashboard_writes_readable_html(tmp_path, sample):
    path = save_dashboard(sample, tmp_path / "dash.html")
    text = path.read_text(encoding="utf-8")
    assert text.lstrip().lower().startswith("<!doctype html") or "<html" in text.lower()


def test_load_strips_surrounding_whitespace(tmp_path):
    rows = [_row(month="2025-01", segment="  Alpha  "),
            _row(month="2025-02", segment="Alpha")]
    frame = load_data(_csv(tmp_path, rows))
    assert list(frame["segment"].unique()) == ["Alpha"]
