"""Tests for the Statistical Visualizer project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stats_viz import (  # noqa: E402
    CHART_TYPES,
    DEMO_CSV,
    REQUIRED_COLUMNS,
    StatsError,
    analyze,
    chart_correlation,
    confidence_interval,
    correlation,
    describe,
    find_outliers,
    load_measurements,
    outlier_bounds,
    render_chart,
    render_report,
    run_demo,
    t_critical,
    welch_t_test,
    z_scores,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_CHARTS = {"histogram", "box", "qq", "means", "regression", "correlation"}


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    row = {
        "subject_id": "S-1", "group": "Control",
        "score": 50.0, "age": 30.0, "improved": "no",
    }
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "m.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _group(group: str, values: list[float], start: int = 1) -> list[dict]:
    return [_row(subject_id=f"{group[:3]}-{i:03d}", group=group, score=v)
            for i, v in enumerate(values, start=start)]


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_measurements(DEMO_CSV)


@pytest.fixture(scope="module")
def report(sample):
    return analyze(sample)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 120
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert not sample["subject_id"].duplicated().any()
    assert sample["group"].nunique() == 2
    assert set(sample["improved"]) <= {"yes", "no"}
    assert sample["age"].between(0, 120).all()
    for group, subset in sample.groupby("group"):
        assert len(subset) >= 3, group


def test_load_missing_file(tmp_path):
    with pytest.raises(StatsError, match="not found"):
        load_measurements(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("subject_id,score\nA,10\n", encoding="utf-8")
    with pytest.raises(StatsError, match="missing column"):
        load_measurements(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(StatsError, match="no rows"):
        load_measurements(path)


def test_load_empty_group(tmp_path):
    path = _csv(tmp_path, [_row(group=None)])
    with pytest.raises(StatsError, match="empty 'group'"):
        load_measurements(path)


def test_load_duplicate_subject(tmp_path):
    rows = _group("Control", [1, 2, 3]) + _group("Treatment", [4, 5, 6])
    rows[1]["subject_id"] = rows[0]["subject_id"]
    with pytest.raises(StatsError, match="duplicate subject_id"):
        load_measurements(_csv(tmp_path, rows))


def test_load_non_numeric_score(tmp_path):
    rows = _group("Control", [1, 2, 3]) + _group("Treatment", [4, 5, 6])
    rows[0]["score"] = "high"
    with pytest.raises(StatsError, match="'score' contains non-numeric"):
        load_measurements(_csv(tmp_path, rows))


def test_load_age_out_of_range(tmp_path):
    rows = _group("Control", [1, 2, 3]) + _group("Treatment", [4, 5, 6])
    rows[0]["age"] = 200
    with pytest.raises(StatsError, match="age outside 0..120"):
        load_measurements(_csv(tmp_path, rows))


def test_load_bad_improved(tmp_path):
    rows = _group("Control", [1, 2, 3]) + _group("Treatment", [4, 5, 6])
    rows[0]["improved"] = "maybe"
    with pytest.raises(StatsError, match="'yes' or 'no'"):
        load_measurements(_csv(tmp_path, rows))


def test_load_single_group_rejected(tmp_path):
    rows = _group("Control", [1, 2, 3, 4])
    with pytest.raises(StatsError, match="at least two groups"):
        load_measurements(_csv(tmp_path, rows))


def test_load_group_with_too_few_rows(tmp_path):
    rows = _group("Control", [1, 2]) + _group("Treatment", [4, 5, 6])
    with pytest.raises(StatsError, match="at least 3 rows"):
        load_measurements(_csv(tmp_path, rows))


# --------------------------------------------------------------------------- #
# Descriptive statistics
# --------------------------------------------------------------------------- #
def test_describe_exact_math():
    stats = describe([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
    assert stats["n"] == 8
    assert stats["mean"] == pytest.approx(5.0)
    assert stats["median"] == pytest.approx(4.5)
    assert stats["min"] == 2.0 and stats["max"] == 9.0
    assert stats["range"] == 7.0
    # sample std of this classic set is sqrt(32/7)
    assert stats["std"] == pytest.approx(math.sqrt(32 / 7))
    assert stats["variance"] == pytest.approx(32 / 7)
    assert stats["q1"] < stats["median"] < stats["q3"]
    assert stats["sem"] == pytest.approx(stats["std"] / math.sqrt(8))


def test_describe_rejects_tiny_sample():
    with pytest.raises(StatsError, match="at least 2"):
        describe([1.0])


def test_describe_rejects_nan():
    with pytest.raises(StatsError, match="non-finite"):
        describe([1.0, float("nan"), 3.0])


def test_skewness_signs():
    right = [1.0, 2.0, 3.0, 4.0, 20.0]
    left = [-x for x in right]
    assert describe(right)["skewness"] > 0
    assert describe(left)["skewness"] < 0
    assert describe([5.0] * 10)["skewness"] == 0.0  # flat


def test_z_scores_known_sample():
    values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    stats = describe(values)
    zs = z_scores(values)
    assert len(zs) == 8
    assert sum(zs) == pytest.approx(0.0, abs=1e-9)
    expected = (9.0 - stats["mean"]) / stats["std"]
    assert zs[-1] == pytest.approx(expected)


def test_z_scores_constant_rejected():
    with pytest.raises(StatsError, match="standard deviation is zero"):
        z_scores([3.0, 3.0, 3.0])


def test_outlier_bounds_and_finding():
    # np.percentile linear interpolation: Q1=4.5, Q3=9.5, IQR=5
    # -> fences [4.5-7.5, 9.5+7.5] = [-3.0, 17.0]
    values = [2.0, 4.0, 6.0, 8.0, 10.0, 50.0]
    low, high = outlier_bounds(values)
    assert low == pytest.approx(-3.0)
    assert high == pytest.approx(17.0)
    assert find_outliers(values) == [50.0]
    assert find_outliers([1.0, 2.0, 3.0]) == []


# --------------------------------------------------------------------------- #
# Inference
# --------------------------------------------------------------------------- #
def test_t_critical_table_values():
    assert t_critical(1) == pytest.approx(12.706)
    assert t_critical(10) == pytest.approx(2.228)
    assert t_critical(30) == pytest.approx(2.042)
    assert t_critical(100) == pytest.approx(1.960)  # normal approx


def test_t_critical_rejects_bad_input():
    with pytest.raises(StatsError, match="degrees of freedom"):
        t_critical(0)
    with pytest.raises(StatsError, match="95%"):
        t_critical(10, confidence=0.99)


def test_confidence_interval_brackets_mean():
    values = [10.0, 12.0, 14.0, 11.0, 13.0]
    low, high = confidence_interval(values)
    mean = sum(values) / len(values)
    assert low < mean < high
    # wider confidence would be wider; here just sanity on width
    assert high - low < 10


def test_welch_t_test_detects_clear_difference():
    a = [10.0, 11.0, 9.0, 10.5, 9.5, 10.2]
    b = [20.0, 21.0, 19.0, 20.5, 19.5, 20.2]
    result = welch_t_test(a, b)
    assert result["t"] < -10
    assert result["p_value"] < 0.001
    assert result["mean_diff"] == pytest.approx(
        float(np.mean(a) - np.mean(b)))


def test_welch_t_test_similar_samples_not_significant():
    a = [10.0, 11.0, 9.0, 10.5, 9.5, 10.2]
    b = [10.1, 10.9, 9.2, 10.4, 9.7, 10.0]
    result = welch_t_test(a, b)
    assert result["p_value"] > 0.05
    assert abs(result["t"]) < 2


def test_welch_t_test_rejects_constants():
    with pytest.raises(StatsError, match="constant"):
        welch_t_test([5.0, 5.0], [5.0, 5.0])


def test_welch_t_test_needs_two_points():
    with pytest.raises(StatsError, match="at least 2"):
        welch_t_test([1.0], [2.0, 3.0])


def test_p_value_is_symmetric_in_sign():
    a = [1.0, 2.0, 3.0, 4.0]
    b = [5.0, 6.0, 7.0, 8.0]
    forward = welch_t_test(a, b)
    backward = welch_t_test(b, a)
    assert forward["p_value"] == pytest.approx(backward["p_value"])
    assert forward["t"] == pytest.approx(-backward["t"])


def test_correlation_perfect_line():
    x = [1.0, 2.0, 3.0, 4.0]
    y = [2.0, 4.0, 6.0, 8.0]
    fit = correlation(x, y)
    assert fit["r"] == pytest.approx(1.0)
    assert fit["r2"] == pytest.approx(1.0)
    assert fit["slope"] == pytest.approx(2.0)
    assert fit["intercept"] == pytest.approx(0.0)


def test_correlation_inverse_line():
    fit = correlation([1.0, 2.0, 3.0], [3.0, 2.0, 1.0])
    assert fit["r"] == pytest.approx(-1.0)
    assert fit["slope"] == pytest.approx(-1.0)


def test_correlation_rejects_constant():
    with pytest.raises(StatsError, match="constant"):
        correlation([1.0, 2.0, 3.0], [5.0, 5.0, 5.0])


def test_correlation_rejects_mismatched_lengths():
    with pytest.raises(StatsError, match="same length"):
        correlation([1.0, 2.0], [1.0])


# --------------------------------------------------------------------------- #
# Analysis (whole report)
# --------------------------------------------------------------------------- #
def test_analyze_partitions_groups(sample, report):
    assert report.overall["n"] == 120
    total = sum(s["n"] for s in report.by_group.values())
    assert total == 120
    assert set(report.by_group) == {"Control", "Treatment"}
    assert report.by_group["Control"]["n"] == 60
    assert report.by_group["Treatment"]["n"] == 60


def test_analyze_group_means_match_sample(sample, report):
    for group in ("Control", "Treatment"):
        subset = sample.loc[sample["group"] == group, "score"]
        assert report.by_group[group]["mean"] == pytest.approx(
            float(subset.mean()), abs=1e-9)


def test_analyze_treatment_beats_control(sample, report):
    # generated data: Treatment ~N(58, 10), Control ~N(50, 8)
    assert report.by_group["Treatment"]["mean"] > \
        report.by_group["Control"]["mean"]
    assert report.comparison["p_value"] < 0.01
    assert report.comparison["group_a"] == "Control"
    assert report.comparison["group_b"] == "Treatment"


def test_analyze_quartile_ordering(sample, report):
    for stats in report.by_group.values():
        assert stats["min"] <= stats["q1"] <= stats["median"] \
            <= stats["q3"] <= stats["max"]


def test_analyze_age_fit_bounds(sample, report):
    assert abs(report.age_fit["r"]) <= 1.0
    assert 0.0 <= report.age_fit["r2"] <= 1.0
    assert report.age_fit["r2"] == pytest.approx(report.age_fit["r"] ** 2)


def test_analyze_outliers_are_outside_fences(sample, report):
    for group, values in report.outliers.items():
        low, high = outlier_bounds(
            sample.loc[sample["group"] == group, "score"])
        for value in values:
            assert value < low or value > high


def test_report_to_dict_serializable(report):
    payload = report.to_dict()
    json.dumps(payload)
    assert payload["n"] == 120
    assert set(payload["by_group"]) == {"Control", "Treatment"}
    assert "p_value" in payload["comparison"]
    assert "slope" in payload["age_fit"]
    assert payload["comparison"]["p_value"] >= 0


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_render_report_sections(report):
    text = render_report(report)
    assert "STATISTICAL SUMMARY" in text
    assert "By group:" in text
    assert "Welch t-test: Control vs Treatment" in text
    assert "Age vs score:" in text
    assert "Tukey outliers" in text
    assert "significant" in text
    assert "reject H0" in text or "retain H0" in text


def test_render_report_alignment(report):
    text = render_report(report)
    # the group table header and both rows must be present
    assert "mean" in text and "CI low" in text
    assert "Control" in text and "Treatment" in text


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def test_registry_contains_expected_charts():
    assert set(CHART_TYPES) == EXPECTED_CHARTS
    for name, (function, description) in CHART_TYPES.items():
        assert callable(function), name
        assert description


@pytest.mark.parametrize("name", sorted(EXPECTED_CHARTS))
def test_every_chart_renders(tmp_path, sample, name):
    path = render_chart(name, sample, tmp_path / "out" / f"{name}.png")
    assert path.is_file()
    assert path.stat().st_size > 1000
    assert plt.get_fignums() == [], f"figure leaked for {name}"


def test_render_unknown_chart(tmp_path, sample):
    with pytest.raises(StatsError, match="unknown chart.*available"):
        render_chart("violin", sample, tmp_path / "x.png")
    assert plt.get_fignums() == []


def test_repeated_rendering_does_not_leak_figures(tmp_path, sample):
    for _ in range(3):
        render_chart("histogram", sample, tmp_path / "h.png")
    assert plt.get_fignums() == []


def test_chart_correlation_rejects_missing_numeric(tmp_path, sample):
    frame = sample.copy()
    frame["note"] = "text"
    with pytest.raises(StatsError, match="not numeric"):
        chart_correlation(frame, columns=["note"])


def test_chart_correlation_needs_two_columns(sample):
    with pytest.raises(StatsError, match="at least two numeric"):
        chart_correlation(sample[["score"]])


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(tmp_path, capsys):
    out_dir = tmp_path / "charts"
    assert run_demo(out_dir=out_dir) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "STATISTICAL SUMMARY" in out
    assert len(list(out_dir.glob("*.png"))) == 6


def test_run_demo_is_idempotent(tmp_path, capsys):
    out_dir = tmp_path / "charts"
    assert run_demo(out_dir=out_dir) == 0
    assert run_demo(out_dir=out_dir) == 0
    out = capsys.readouterr().out
    assert out.count("Demo completed successfully.") == 2
    assert len(list(out_dir.glob("*.png"))) == 6  # overwritten, not doubled


def test_run_demo_quiet(tmp_path, capsys):
    assert run_demo(out_dir=tmp_path / "q", quiet=True) == 0
    assert capsys.readouterr().out == ""


def test_run_demo_missing_sample(tmp_path, monkeypatch):
    import stats_viz
    monkeypatch.setattr(stats_viz, "DEMO_CSV", tmp_path / "absent.csv")
    with pytest.raises(StatsError, match="bundled sample"):
        stats_viz.run_demo(out_dir=tmp_path / "x")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(tmp_path, capsys):
    out_dir = tmp_path / "cli"
    assert main(["--demo", "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert len(list(out_dir.glob("*.png"))) == 6


def test_cli_demo_quiet(tmp_path, capsys):
    assert main(["--demo", "--out", str(tmp_path / "q"), "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_demo_with_json(tmp_path, capsys):
    payload_path = tmp_path / "report.json"
    out_dir = tmp_path / "charts"
    assert main(["--demo", "--out", str(out_dir),
                 "--json", str(payload_path)]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["n"] == 120
    assert "p_value" in payload["comparison"]


def test_cli_file_analysis(capsys):
    assert main(["--file", str(DEMO_CSV)]) == 0
    out = capsys.readouterr().out
    assert "STATISTICAL SUMMARY" in out and "Done." in out


def test_cli_single_chart(tmp_path, capsys):
    out_dir = tmp_path / "one"
    assert main(["--file", str(DEMO_CSV), "--chart", "box",
                 "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "Rendered box" in out
    assert (out_dir / "box.png").is_file()


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "report.json"
    assert main(["--file", str(DEMO_CSV), "--json", str(payload_path),
                 "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["n"] == 120
    assert set(payload["by_group"]) == {"Control", "Treatment"}


def test_cli_list(capsys):
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    for name in EXPECTED_CHARTS:
        assert name in out
    assert "6 chart types available." in out


def test_cli_unknown_chart(tmp_path, capsys):
    assert main(["--file", str(DEMO_CSV), "--chart", "violin",
                 "--out", str(tmp_path)]) == 2
    assert "unknown chart" in capsys.readouterr().err


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
