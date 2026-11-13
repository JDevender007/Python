"""Tests for the Survey Data Analyzer project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from survey_analyzer import (  # noqa: E402
    DEMO_CSV,
    GROUP_COLUMNS,
    REQUIRED_COLUMNS,
    SAT_BUCKETS,
    SurveyError,
    analyze,
    load_survey,
    nps_scores,
    render_report,
    run_demo,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    row = {
        "response_id": "R-1", "date": "2025-07-01", "department": "Engineering",
        "gender": "F", "age": 30, "tenure_years": 2.5, "satisfaction": 4,
        "recommend_score": 9, "remote": "yes",
    }
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "survey.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_survey(DEMO_CSV)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 500
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert not sample["response_id"].duplicated().any()
    assert sample["date"].is_monotonic_increasing
    assert sample["satisfaction"].between(1, 5).all()
    assert sample["recommend_score"].between(1, 10).all()


def test_load_missing_file(tmp_path):
    with pytest.raises(SurveyError, match="not found"):
        load_survey(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = _csv(tmp_path, [{"response_id": "R-1", "date": "2025-07-01"}])
    with pytest.raises(SurveyError, match="missing column"):
        load_survey(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(SurveyError, match="no rows"):
        load_survey(path)


def test_load_bad_date(tmp_path):
    path = _csv(tmp_path, [_row(date="someday")])
    with pytest.raises(SurveyError, match="unparseable date"):
        load_survey(path)


def test_load_empty_response_id(tmp_path):
    path = _csv(tmp_path, [_row(response_id="")])
    with pytest.raises(SurveyError, match="empty response_id"):
        load_survey(path)


def test_load_duplicate_response_id(tmp_path):
    path = _csv(tmp_path, [_row(), _row(date="2025-07-02")])
    with pytest.raises(SurveyError, match="duplicate response_id"):
        load_survey(path)


def test_load_blank_department(tmp_path):
    path = _csv(tmp_path, [_row(department="   ")])
    with pytest.raises(SurveyError, match="empty 'department'"):
        load_survey(path)


def test_load_missing_gender_cell(tmp_path):
    path = _csv(tmp_path, [_row(gender=None)])
    with pytest.raises(SurveyError, match="empty 'gender'"):
        load_survey(path)


def test_load_satisfaction_out_of_range(tmp_path):
    path = _csv(tmp_path, [_row(satisfaction=6)])
    with pytest.raises(SurveyError, match="outside 1..5"):
        load_survey(path)


def test_load_recommend_out_of_range(tmp_path):
    path = _csv(tmp_path, [_row(recommend_score=11)])
    with pytest.raises(SurveyError, match="outside 1..10"):
        load_survey(path)


def test_load_age_out_of_range(tmp_path):
    path = _csv(tmp_path, [_row(age=10)])
    with pytest.raises(SurveyError, match="outside 16..120"):
        load_survey(path)


def test_load_non_numeric(tmp_path):
    path = _csv(tmp_path, [_row(satisfaction="very happy")])
    with pytest.raises(SurveyError, match="non-numeric"):
        load_survey(path)


def test_load_fractional_score(tmp_path):
    path = _csv(tmp_path, [_row(satisfaction=4.5)])
    with pytest.raises(SurveyError, match="whole numbers"):
        load_survey(path)


def test_load_sorts_by_date(tmp_path):
    path = _csv(tmp_path, [
        _row(response_id="B", date="2025-08-01"),
        _row(response_id="A", date="2025-07-01"),
    ])
    frame = load_survey(path)
    assert list(frame["response_id"]) == ["A", "B"]


# --------------------------------------------------------------------------- #
# NPS math
# --------------------------------------------------------------------------- #
def test_nps_known_scores():
    result = nps_scores(pd.Series([10, 9, 7, 2]))
    assert result["nps"] == pytest.approx(25.0)     # (2-1)/4*100
    assert result["promoter_pct"] == 50.0
    assert result["passive_pct"] == 25.0
    assert result["detractor_pct"] == 25.0


def test_nps_all_promoters():
    result = nps_scores(pd.Series([9, 10, 10]))
    assert result["nps"] == 100.0
    assert result["detractor_pct"] == 0.0


def test_nps_all_detractors():
    result = nps_scores(pd.Series([1, 5, 6]))
    assert result["nps"] == -100.0
    assert result["promoter_pct"] == 0.0


def test_nps_empty_rejected():
    with pytest.raises(SurveyError, match="no responses"):
        nps_scores(pd.Series([], dtype=int))


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def _tiny(tmp_path: Path) -> pd.DataFrame:
    rows = [
        _row(response_id="A", satisfaction=5, recommend_score=10, department="Engineering"),
        _row(response_id="B", satisfaction=5, recommend_score=9, department="Engineering"),
        _row(response_id="C", satisfaction=1, recommend_score=2, department="Support"),
        _row(response_id="D", satisfaction=3, recommend_score=7, department="Support"),
    ]
    return load_survey(_csv(tmp_path, rows))


def test_analyze_counts_and_range(tmp_path):
    report = analyze(_tiny(tmp_path))
    assert report.n_responses == 4
    assert report.date_min <= report.date_max


def test_analyze_satisfaction_math(tmp_path):
    report = analyze(_tiny(tmp_path))
    sat = report.satisfaction
    assert sat["mean"] == pytest.approx(3.5)
    assert sat["top_box_pct"] == pytest.approx(50.0)     # 5,5
    assert sat["bottom_box_pct"] == pytest.approx(25.0)  # 1
    assert sat["net_top_box_pct"] == pytest.approx(25.0)
    assert report.satisfaction_dist == {1: 1, 3: 1, 5: 2}


def test_analyze_nps_math(tmp_path):
    report = analyze(_tiny(tmp_path))
    assert report.recommend["nps"] == pytest.approx(25.0)


def test_analyze_distribution_sums_to_n(sample):
    report = analyze(sample)
    assert sum(report.satisfaction_dist.values()) == report.n_responses
    assert set(report.satisfaction_dist) <= {1, 2, 3, 4, 5}


def test_analyze_weighted_group_mean(sample):
    report = analyze(sample, group="department")
    table = report.by_group["department"]
    weighted = float((table["mean_satisfaction"] * table["responses"]).sum()
                     / table["responses"].sum())
    assert weighted == pytest.approx(report.satisfaction["mean"], abs=0.02)
    assert int(table["responses"].sum()) == report.n_responses


def test_analyze_crosstab_rows_sum_to_100(sample):
    report = analyze(sample, group="department")
    assert list(report.crosstab.index) == list(SAT_BUCKETS)
    row_sums = report.crosstab.sum(axis=1)
    assert ((row_sums - 100).abs() < 0.1).all()
    assert set(report.crosstab.columns) == set(sample["department"])


def test_analyze_all_groupings(sample):
    for group in GROUP_COLUMNS:
        report = analyze(sample, group=group)
        assert group in report.by_group
        assert len(report.by_group[group]) >= 2
        assert report.by_group[group]["responses"].sum() == report.n_responses


def test_analyze_remote_split(sample):
    report = analyze(sample)
    assert set(report.remote_split) == {"yes", "no"}
    total = sum(v["responses"] for v in report.remote_split.values())
    assert total == report.n_responses


def test_analyze_unknown_group(sample):
    with pytest.raises(SurveyError, match="unknown group"):
        analyze(sample, group="office")


def test_analyze_single_response(tmp_path):
    report = analyze(load_survey(_csv(tmp_path, [_row()])))
    assert report.n_responses == 1
    assert report.satisfaction["std"] == 0.0
    assert len(report.by_group["department"]) == 1


def test_report_to_dict_serializable(sample):
    payload = analyze(sample).to_dict()
    json.dumps(payload)
    assert payload["n_responses"] == 500
    assert len(payload["by_department"]) == 5
    assert len(payload["crosstab_pct"]) == 3
    assert "nps" in payload["recommend"]
    assert set(payload["satisfaction_dist"]) == {"1", "2", "3", "4", "5"}


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_render_report_sections(sample):
    text = render_report(analyze(sample), group="department")
    assert "SURVEY ANALYSIS" in text
    assert "Satisfaction distribution:" in text
    assert "By department:" in text
    assert "Remote split:" in text
    assert "NPS" in text and "promoters" in text


def test_render_follows_group(sample):
    text = render_report(analyze(sample, group="gender"), group="gender")
    assert "By gender:" in text
    assert "By department:" not in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "SURVEY ANALYSIS" in out
    assert "Grouped by gender instead" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(SurveyError, match="bundled sample"):
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
    assert "SURVEY ANALYSIS" in out and "Done." in out


def test_cli_group_option(capsys):
    assert main(["--file", str(DEMO_CSV), "--group", "gender"]) == 0
    assert "By gender:" in capsys.readouterr().out


def test_cli_json_output(tmp_path, capsys):
    out_file = tmp_path / "report.json"
    assert main(["--file", str(DEMO_CSV), "--json", str(out_file)]) == 0
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["n_responses"] == 500
    assert len(payload["by_department"]) == 5


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_invalid_schema(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "missing column" in capsys.readouterr().err


def test_cli_out_of_range_value(tmp_path, capsys):
    path = _csv(tmp_path, [_row(satisfaction=99)])
    assert main(["--file", str(path)]) == 2
    assert "outside" in capsys.readouterr().err


def test_cli_requires_source(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_project_has_sample_data():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent == PROJECT_ROOT / "data"
