"""Tests for the Census Data Analyzer project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import _run_demo, main  # noqa: E402
from census_analyzer import (  # noqa: E402
    CORR_COLUMNS,
    DEMO_CSV,
    RATE_COLUMNS,
    REQUIRED_COLUMNS,
    CensusError,
    analyze,
    load_census,
    render_report,
    run_demo,
    weighted_mean,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _region(**overrides) -> dict:
    row = {
        "region_id": "AA-01", "region_name": "Alpha District", "state": "Alphaland",
        "population": 1000, "households": 400, "median_household_income": 50000,
        "poverty_rate": 0.12, "unemployment_rate": 0.05,
        "bachelor_degree_pct": 0.30, "median_age": 38.0,
        "urban_population_pct": 0.60,
    }
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "census.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_census(DEMO_CSV)


@pytest.fixture(scope="module")
def report(sample):
    return analyze(sample, top=5)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 120
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert not sample["region_id"].duplicated().any()
    assert sample["state"].nunique() == 6
    assert (sample["households"] <= sample["population"]).all()
    for column in RATE_COLUMNS:
        assert sample[column].between(0, 1).all()
    # sorted by state
    assert list(sample["state"].unique()) == sorted(sample["state"].unique())


def test_load_missing_file(tmp_path):
    with pytest.raises(CensusError, match="not found"):
        load_census(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = _csv(tmp_path, [{"region_id": "A", "state": "X"}])
    with pytest.raises(CensusError, match="missing column"):
        load_census(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(CensusError, match="no rows"):
        load_census(path)


def test_load_empty_state(tmp_path):
    path = _csv(tmp_path, [_region(state=None)])
    with pytest.raises(CensusError, match="empty 'state'"):
        load_census(path)


def test_load_duplicate_region_id(tmp_path):
    path = _csv(tmp_path, [_region(), _region(region_name="Second")])
    with pytest.raises(CensusError, match="duplicate region_id"):
        load_census(path)


def test_load_zero_population(tmp_path):
    path = _csv(tmp_path, [_region(population=0)])
    with pytest.raises(CensusError, match="positive whole numbers"):
        load_census(path)


def test_load_fractional_population(tmp_path):
    path = _csv(tmp_path, [_region(population=1000.5)])
    with pytest.raises(CensusError, match="positive whole numbers"):
        load_census(path)


def test_load_non_numeric_population(tmp_path):
    path = _csv(tmp_path, [_region(population="many")])
    with pytest.raises(CensusError, match="non-numeric"):
        load_census(path)


def test_load_households_exceed_population(tmp_path):
    path = _csv(tmp_path, [_region(population=500, households=800)])
    with pytest.raises(CensusError, match="households cannot exceed population"):
        load_census(path)


def test_load_income_out_of_range(tmp_path):
    path = _csv(tmp_path, [_region(median_household_income=5000)])
    with pytest.raises(CensusError, match="outside 10000..500000"):
        load_census(path)


def test_load_rate_out_of_range(tmp_path):
    path = _csv(tmp_path, [_region(poverty_rate=1.5)])
    with pytest.raises(CensusError, match="fraction in 0..1"):
        load_census(path)


def test_load_negative_rate(tmp_path):
    path = _csv(tmp_path, [_region(urban_population_pct=-0.1)])
    with pytest.raises(CensusError, match="fraction in 0..1"):
        load_census(path)


def test_load_age_out_of_range(tmp_path):
    path = _csv(tmp_path, [_region(median_age=12)])
    with pytest.raises(CensusError, match="median_age outside 18..100"):
        load_census(path)


def test_load_non_numeric_income(tmp_path):
    path = _csv(tmp_path, [_region(median_household_income="rich")])
    with pytest.raises(CensusError, match="non-numeric"):
        load_census(path)


# --------------------------------------------------------------------------- #
# weighted_mean
# --------------------------------------------------------------------------- #
def test_weighted_mean_exact_math():
    frame = pd.DataFrame({"income": [10000.0, 20000.0], "households": [1.0, 3.0]})
    assert weighted_mean(frame, "income", "households") == pytest.approx(17500.0)
    assert float(frame["income"].mean()) == pytest.approx(15000.0)  # differs!


def test_weighted_mean_unknown_column():
    frame = pd.DataFrame({"income": [1.0], "households": [1.0]})
    with pytest.raises(CensusError, match="unknown column"):
        weighted_mean(frame, "income", "population")


def test_weighted_mean_empty():
    frame = pd.DataFrame({"income": [], "households": []})
    with pytest.raises(CensusError, match="no rows"):
        weighted_mean(frame, "income", "households")


def test_weighted_mean_zero_weight():
    frame = pd.DataFrame({"income": [5.0], "households": [0.0]})
    with pytest.raises(CensusError, match="total weight"):
        weighted_mean(frame, "income", "households")


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def test_analyze_totals(sample, report):
    assert report.regions == 120
    assert report.states == 6
    assert report.population_total == int(sample["population"].sum()) == 28_267_889
    assert report.households_total == int(sample["households"].sum())
    assert report.avg_household_size > 2
    assert 0 < report.poverty_population <= report.population_total
    assert 0 < report.poverty_share_pct < 100


def test_analyze_weighted_vs_unweighted(tmp_path):
    rows = [
        _region(region_id="A-01", population=100, households=1,
                median_household_income=10000),
        _region(region_id="B-01", region_name="Beta", state="Betaland",
                population=900, households=3,
                median_household_income=20000),
    ]
    report = analyze(load_census(_csv(tmp_path, rows)))
    assert report.indicators["median_income_weighted"] == pytest.approx(17500.0)
    assert report.indicators["median_income_unweighted"] == pytest.approx(15000.0)


def test_analyze_weighted_income_in_range(sample, report):
    low = sample["median_household_income"].min()
    high = sample["median_household_income"].max()
    assert low <= report.indicators["median_income_weighted"] <= high
    assert low <= report.indicators["median_income_unweighted"] <= high
    for key in ("poverty_rate_weighted", "bachelor_pct_weighted",
                "unemployment_weighted", "urban_pct_weighted"):
        assert 0 <= report.indicators[key] <= 1, key


def test_analyze_state_partition(sample, report):
    assert len(report.by_state) == 6
    assert int(report.by_state["population"].sum()) == report.population_total
    assert int(report.by_state["households"].sum()) == report.households_total
    assert report.by_state["regions"].sum() == report.regions
    pops = list(report.by_state["population"])
    assert pops == sorted(pops, reverse=True)


def test_analyze_urban_split(sample, report):
    assert set(report.urban_split) == {"urban", "rural"}
    assert sum(v["regions"] for v in report.urban_split.values()) == report.regions
    total_pop = sum(v["population"] for v in report.urban_split.values())
    assert int(total_pop) == report.population_total


def test_analyze_urban_split_handles_empty_group(tmp_path):
    rows = [_region()]  # urban_pct 0.6 -> pure urban frame, rural is empty
    report = analyze(load_census(_csv(tmp_path, rows)))
    assert report.urban_split["rural"]["regions"] == 0.0
    assert report.urban_split["rural"]["median_income"] == 0.0


def test_analyze_correlations(sample, report):
    corr = report.correlations
    assert list(corr.columns) == list(CORR_COLUMNS)
    assert ((corr.values >= -1.0001) & (corr.values <= 1.0001)).all()
    assert abs(float(corr.values.diagonal().min()) - 1.0) < 1e-6
    assert ((corr.values - corr.values.T) ** 2).max() < 1e-6
    # richer regions should be less poor in the synthetic data
    assert corr.loc["median_household_income", "poverty_rate"] < 0


def test_analyze_rankings(sample, report):
    incomes = list(report.top_income["median_household_income"])
    assert incomes == sorted(incomes, reverse=True)
    poverties = list(report.top_poverty["poverty_rate"])
    assert poverties == sorted(poverties, reverse=True)
    assert len(report.top_income) == 5
    # rankings must display region names, not row positions
    assert set(report.top_income.index) <= set(sample["region_name"])
    assert set(report.top_poverty.index) <= set(sample["region_name"])


def test_analyze_inequality_ratio(sample, report):
    assert report.income_iqr_ratio >= 1.0
    assert report.income_iqr_ratio < 5.0


def test_analyze_rejects_bad_top(sample):
    with pytest.raises(CensusError, match="top must be"):
        analyze(sample, top=0)


def test_report_to_dict(report):
    payload = report.to_dict()
    json.dumps(payload)
    assert payload["regions"] == 120
    assert payload["population_total"] == 28_267_889
    assert len(payload["by_state"]) == 6
    assert len(payload["correlation"]) == len(CORR_COLUMNS)
    assert len(payload["top_income"]) == 5
    assert "poverty_population" in payload
    assert payload["income_iqr_ratio"] >= 1.0


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_render_report_sections(report):
    text = render_report(report)
    assert "CENSUS ANALYSIS" in text
    assert "By state (weighted):" in text
    assert "Urban vs rural regions:" in text
    assert "Indicator correlation:" in text
    assert "Highest incomes:" in text
    assert "Highest poverty:" in text
    assert "population" in text.lower()


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Weighted vs unweighted" in out
    assert "CENSUS ANALYSIS" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(CensusError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_file_analysis(capsys):
    assert main(["--file", str(DEMO_CSV)]) == 0
    out = capsys.readouterr().out
    assert "CENSUS ANALYSIS" in out and "Done." in out


def test_cli_top_option(tmp_path, capsys):
    out_file = tmp_path / "report.json"
    assert main(["--file", str(DEMO_CSV), "--top", "3",
                 "--json", str(out_file)]) == 0
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(payload["top_income"]) == 3
    assert len(payload["top_poverty"]) == 3


def test_cli_json_output(tmp_path, capsys):
    out_file = tmp_path / "report.json"
    assert main(["--file", str(DEMO_CSV), "--json", str(out_file)]) == 0
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["regions"] == 120
    assert payload["population_total"] == 28_267_889


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_invalid_schema(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "missing column" in capsys.readouterr().err


def test_cli_out_of_range_value(tmp_path, capsys):
    path = _csv(tmp_path, [_region(poverty_rate=42)])
    assert main(["--file", str(path)]) == 2
    assert "fraction in 0..1" in capsys.readouterr().err


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
# Totals and weighting
# --------------------------------------------------------------------------- #
def test_report_totals_match_the_frame():
    """The report's totals are the frame's totals, not a rounded restatement."""
    frame = load_census(DEMO_CSV)
    report = analyze(frame)
    assert report.regions == len(frame)
    assert report.population_total == int(frame["population"].sum())
    assert report.households_total == int(frame["households"].sum())


def test_weighted_mean_is_the_population_weighted_ratio():
    frame = load_census(DEMO_CSV)
    expected = float(
        (frame["poverty_rate"] * frame["population"]).sum()
        / frame["population"].sum()
    )
    assert weighted_mean(frame, "poverty_rate", "population") == pytest.approx(expected)
    assert weighted_mean(frame, "poverty_rate", "population") != pytest.approx(
        float(frame["poverty_rate"].mean())
    )


def test_weighted_mean_refuses_a_zero_total_weight():
    """A rate weighted by nothing has no value to report."""
    frame = load_census(DEMO_CSV).head(3).copy()
    frame["population"] = 0
    with pytest.raises(CensusError):
        weighted_mean(frame, "poverty_rate", "population")
