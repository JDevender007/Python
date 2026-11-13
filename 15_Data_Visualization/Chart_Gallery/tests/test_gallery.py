"""Tests for the Chart Gallery project."""

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

from gallery import (  # noqa: E402
    CHART_TYPES,
    DEMO_CSV,
    REQUIRED_COLUMNS,
    GalleryError,
    list_charts,
    load_sample,
    pivot,
    render_chart,
    run_demo,
    summary_table,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_CHARTS = {
    "line", "area", "bar", "stacked_bar", "ranked_bar",
    "histogram", "scatter", "pie", "box", "heatmap",
}


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_sample(DEMO_CSV)


def _csv(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "data.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 48
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert sample["region"].nunique() == 4
    assert sample["month"].nunique() == 12
    assert not sample.duplicated(subset=["month", "region"]).any()
    assert (sample["revenue"] >= 0).all() and (sample["orders"] >= 0).all()


def test_load_missing_file(tmp_path):
    with pytest.raises(GalleryError, match="not found"):
        load_sample(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("month,revenue\n2025-01,100\n", encoding="utf-8")
    with pytest.raises(GalleryError, match="missing column"):
        load_sample(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(GalleryError, match="no rows"):
        load_sample(path)


def test_load_bad_month(tmp_path):
    path = _csv(tmp_path, [{"month": "January", "region": "North",
                            "revenue": 1, "cost": 1, "orders": 1}])
    with pytest.raises(GalleryError, match="YYYY-MM"):
        load_sample(path)


def test_load_empty_region(tmp_path):
    path = _csv(tmp_path, [{"month": "2025-01", "region": None,
                            "revenue": 1, "cost": 1, "orders": 1}])
    with pytest.raises(GalleryError, match="empty region"):
        load_sample(path)


def test_load_non_numeric_revenue(tmp_path):
    path = _csv(tmp_path, [{"month": "2025-01", "region": "North",
                            "revenue": "lots", "cost": 1, "orders": 1}])
    with pytest.raises(GalleryError, match="non-numeric"):
        load_sample(path)


def test_load_negative_cost(tmp_path):
    path = _csv(tmp_path, [{"month": "2025-01", "region": "North",
                            "revenue": 10, "cost": -1, "orders": 1}])
    with pytest.raises(GalleryError, match="non-negative"):
        load_sample(path)


def test_load_fractional_orders(tmp_path):
    path = _csv(tmp_path, [{"month": "2025-01", "region": "North",
                            "revenue": 10, "cost": 1, "orders": 2.5}])
    with pytest.raises(GalleryError, match="whole numbers"):
        load_sample(path)


def test_load_duplicate_month_region(tmp_path):
    row = {"month": "2025-01", "region": "North", "revenue": 10,
           "cost": 1, "orders": 2}
    path = _csv(tmp_path, [row, dict(row, revenue=20)])
    with pytest.raises(GalleryError, match="duplicate"):
        load_sample(path)


# --------------------------------------------------------------------------- #
# Data helpers
# --------------------------------------------------------------------------- #
def test_pivot_shape(sample):
    table = pivot(sample)
    assert table.shape == (4, 12)
    assert list(table.columns) == sorted(sample["month"].unique())


def test_pivot_totals_match(sample):
    table = pivot(sample)
    assert float(table.values.sum()) == float(sample["revenue"].sum())


def test_summary_table_math(sample):
    summary = summary_table(sample)
    assert list(summary.columns) == ["revenue", "cost", "orders",
                                     "margin", "margin_pct", "aov"]
    assert int(summary["revenue"].sum()) == int(sample["revenue"].sum())
    assert int(summary["orders"].sum()) == int(sample["orders"].sum())
    for _, row in summary.iterrows():
        assert row["margin"] == row["revenue"] - row["cost"]
    revenues = list(summary["revenue"])
    assert revenues == sorted(revenues, reverse=True)


# --------------------------------------------------------------------------- #
# Registry and rendering
# --------------------------------------------------------------------------- #
def test_registry_contains_expected_charts():
    assert set(CHART_TYPES) == EXPECTED_CHARTS
    assert len(CHART_TYPES) == 10
    for name, (function, description) in CHART_TYPES.items():
        assert callable(function), name
        assert isinstance(description, str) and description


def test_list_charts_matches_registry():
    listed = list_charts()
    assert [name for name, _ in listed] == list(CHART_TYPES)
    assert all(description for _, description in listed)


@pytest.mark.parametrize("name", sorted(EXPECTED_CHARTS))
def test_every_chart_renders(tmp_path, sample, name):
    target = tmp_path / "out" / f"{name}.png"
    path = render_chart(name, sample, target)
    assert path.is_file()
    assert path.stat().st_size > 1000
    assert plt.get_fignums() == [], f"figure leaked for {name}"


def test_render_unknown_chart(tmp_path, sample):
    with pytest.raises(GalleryError, match="unknown chart.*available"):
        render_chart("sunburst", sample, tmp_path / "x.png")
    assert plt.get_fignums() == []


def test_render_creates_missing_directories(tmp_path, sample):
    target = tmp_path / "deep" / "nested" / "dir" / "line.png"
    path = render_chart("line", sample, target)
    assert path.is_file()


def test_repeated_rendering_does_not_leak_figures(tmp_path, sample):
    for _ in range(3):
        render_chart("scatter", sample, tmp_path / "s.png")
    assert plt.get_fignums() == []


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(tmp_path, capsys):
    out_dir = tmp_path / "charts"
    assert run_demo(out_dir=out_dir) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert len(list(out_dir.glob("*.png"))) == 10


def test_run_demo_is_idempotent(tmp_path, capsys):
    out_dir = tmp_path / "charts"
    assert run_demo(out_dir=out_dir) == 0
    assert run_demo(out_dir=out_dir) == 0
    out = capsys.readouterr().out
    assert out.count("Demo completed successfully.") == 2
    assert len(list(out_dir.glob("*.png"))) == 10  # overwritten, not doubled


def test_run_demo_quiet(tmp_path, capsys):
    assert run_demo(out_dir=tmp_path / "q", quiet=True) == 0
    out = capsys.readouterr().out
    assert out == ""


def test_run_demo_missing_sample(tmp_path, monkeypatch):
    import gallery
    monkeypatch.setattr(gallery, "DEMO_CSV", tmp_path / "absent.csv")
    with pytest.raises(GalleryError, match="bundled sample"):
        gallery.run_demo(out_dir=tmp_path / "x")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(tmp_path, capsys):
    out_dir = tmp_path / "cli_charts"
    assert main(["--demo", "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert len(list(out_dir.glob("*.png"))) == 10


def test_cli_demo_with_manifest(tmp_path, capsys):
    out_dir = tmp_path / "m_charts"
    manifest = tmp_path / "manifest.json"
    assert main(["--demo", "--out", str(out_dir), "--manifest", str(manifest)]) == 0
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert set(payload) == EXPECTED_CHARTS
    assert all(Path(p).is_file() for p in payload.values())


def test_cli_list(capsys):
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    for name in EXPECTED_CHARTS:
        assert name in out
    assert "10 chart types available." in out


def test_cli_single_chart(tmp_path, capsys):
    out_dir = tmp_path / "one"
    assert main(["--chart", "heatmap", "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "Rendered heatmap" in out and "Done." in out
    assert (out_dir / "heatmap.png").is_file()


def test_cli_single_chart_quiet(tmp_path, capsys):
    out_dir = tmp_path / "one"
    assert main(["--chart", "pie", "--out", str(out_dir), "--quiet"]) == 0
    assert capsys.readouterr().out == ""
    assert (out_dir / "pie.png").is_file()


def test_cli_unknown_chart(tmp_path, capsys):
    assert main(["--chart", "sunburst", "--out", str(tmp_path)]) == 2
    assert "unknown chart" in capsys.readouterr().err


def test_cli_custom_file(tmp_path, capsys):
    path = _csv(tmp_path, [
        {"month": "2025-01", "region": "North", "revenue": 100, "cost": 60, "orders": 2},
        {"month": "2025-02", "region": "North", "revenue": 140, "cost": 70, "orders": 3},
    ])
    out_dir = tmp_path / "custom"
    assert main(["--chart", "line", "--file", str(path), "--out", str(out_dir)]) == 0
    assert (out_dir / "line.png").is_file()


def test_cli_missing_custom_file(tmp_path, capsys):
    assert main(["--chart", "line", "--file", str(tmp_path / "nope.csv"),
                 "--out", str(tmp_path)]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_project_has_sample_data():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent == PROJECT_ROOT / "data"
