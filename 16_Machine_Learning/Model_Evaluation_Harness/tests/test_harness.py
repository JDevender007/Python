"""Tests for the Model Evaluation Harness project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from harness import (  # noqa: E402
    DEMO_CSV,
    LABEL_COLUMN,
    MAX_FOLDS,
    METRICS,
    MIN_FOLDS,
    MODELS,
    HarnessError,
    HarnessResult,
    ModelScore,
    evaluate_model,
    load_dataset,
    render_report,
    run_demo,
    run_harness,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    row = {
        "feature_1": 0.5, "feature_2": -0.3, "feature_3": 1.2,
        "feature_4": 4.0, "feature_5": 5.5, LABEL_COLUMN: 1,
    }
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "dataset.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _grid(n: int = 80) -> list[dict]:
    """n valid rows, both classes, all features varying."""
    rows = []
    for i in range(n):
        rows.append(_row(
            feature_1=round(-2.0 + 4.0 * i / n, 4),
            feature_2=round(math.sin(i), 4),
            feature_3=round(0.1 * i, 4),
            feature_4=round(float(i % 10), 4),
            feature_5=round(3.0 + (i % 7), 4),
            label=i % 2,
        ))
    return rows


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_dataset(DEMO_CSV)


@pytest.fixture(scope="module")
def harness(sample):
    return run_harness(sample, folds=3)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 320
    assert LABEL_COLUMN in sample.columns
    assert set(sample[LABEL_COLUMN]) == {0, 1}
    counts = sample[LABEL_COLUMN].value_counts()
    assert counts[0] >= 10 and counts[1] >= 10
    features = [c for c in sample.columns if c != LABEL_COLUMN]
    assert len(features) == 5
    for column in features:
        assert sample[column].nunique() >= 2


def test_load_missing_file(tmp_path):
    with pytest.raises(HarnessError, match="not found"):
        load_dataset(tmp_path / "nope.csv")


def test_load_missing_label_column(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(HarnessError, match="missing column: label"):
        load_dataset(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(_row().keys()) + "\n", encoding="utf-8")
    with pytest.raises(HarnessError, match="no rows"):
        load_dataset(path)


def test_load_non_numeric_feature(tmp_path):
    rows = _grid()
    rows[0]["feature_1"] = "high"
    with pytest.raises(HarnessError, match="'feature_1' contains non-numeric"):
        load_dataset(_csv(tmp_path, rows))


def test_load_nan_feature(tmp_path):
    rows = _grid()
    rows[0]["feature_2"] = None
    with pytest.raises(HarnessError, match="'feature_2' contains non-numeric"):
        load_dataset(_csv(tmp_path, rows))


def test_load_infinite_feature(tmp_path):
    rows = _grid()
    rows[0]["feature_3"] = float("inf")
    with pytest.raises(HarnessError, match="finite"):
        load_dataset(_csv(tmp_path, rows))


def test_load_non_binary_label(tmp_path):
    rows = _grid()
    rows[0][LABEL_COLUMN] = 2
    with pytest.raises(HarnessError, match="binary 0/1"):
        load_dataset(_csv(tmp_path, rows))


def test_load_string_label(tmp_path):
    rows = _grid()
    rows[0][LABEL_COLUMN] = "yes"
    with pytest.raises(HarnessError,
                       match="'label' contains non-numeric"):
        load_dataset(_csv(tmp_path, rows))


def test_load_too_few_rows(tmp_path):
    with pytest.raises(HarnessError, match="at least 60"):
        load_dataset(_csv(tmp_path, _grid(30)))


def test_load_missing_class(tmp_path):
    rows = _grid()
    for row in rows:
        row[LABEL_COLUMN] = 1
    # the binary 0/1 check fires before the per-class count check
    with pytest.raises(HarnessError, match="binary 0/1"):
        load_dataset(_csv(tmp_path, rows))


def test_load_constant_feature(tmp_path):
    rows = _grid()
    for row in rows:
        row["feature_4"] = 4.0
    with pytest.raises(HarnessError, match="no variation.*feature_4"):
        load_dataset(_csv(tmp_path, rows))


# --------------------------------------------------------------------------- #
# Registry and evaluation protocol
# --------------------------------------------------------------------------- #
def test_registry_contains_expected_models():
    assert set(MODELS) == {
        "logistic_regression", "decision_tree", "random_forest",
        "naive_bayes"}
    for name, (factory, description) in MODELS.items():
        assert callable(factory), name
        assert description
        model = factory()
        assert hasattr(model, "fit") and hasattr(model, "predict")


def test_evaluate_unknown_model(sample):
    with pytest.raises(HarnessError, match="unknown model.*available"):
        evaluate_model("svm_magic", sample)


def test_evaluate_rejects_bad_folds(sample):
    with pytest.raises(HarnessError, match="folds must be"):
        evaluate_model("logistic_regression", sample, folds=1)
    with pytest.raises(HarnessError, match="folds must be"):
        evaluate_model("logistic_regression", sample, folds=99)


def test_evaluate_produces_all_metrics(sample):
    score = evaluate_model("logistic_regression", sample, folds=3)
    assert score.folds == 3
    for metric in METRICS:
        assert metric in score.cv_means, metric
        assert metric in score.cv_stds, metric
        assert 0.0 <= score.cv_means[metric] <= 1.0, metric
        assert score.cv_stds[metric] >= 0.0, metric


def test_evaluate_cv_mean_is_average_of_folds(sample, monkeypatch):
    # capture the per-fold scores by spying on _score_predictions
    import harness as harness_module
    captured: list[dict[str, list[float]]] = {m: [] for m in METRICS}
    original = harness_module._score_predictions

    def spy(y_true, y_pred, y_prob=None):
        scores = original(y_true, y_pred, y_prob)
        for metric in METRICS:
            captured[metric].append(scores[metric])
        return scores

    monkeypatch.setattr(harness_module, "_score_predictions", spy)
    score = evaluate_model("naive_bayes", sample, folds=4)
    for metric in METRICS:
        # 4 CV fold scorings + 1 hold-out scoring
        assert len(captured[metric]) == 5
        expected = float(np.nanmean(captured[metric][:4]))
        assert score.cv_means[metric] == pytest.approx(expected)
        assert score.cv_stds[metric] == pytest.approx(
            float(np.nanstd(captured[metric][:4])))
        assert score.holdout[metric] == pytest.approx(captured[metric][4])


def test_evaluate_is_deterministic(sample):
    first = evaluate_model("random_forest", sample, folds=3, seed=42)
    second = evaluate_model("random_forest", sample, folds=3, seed=42)
    assert first.cv_means == second.cv_means
    assert first.holdout == second.holdout


def test_evaluate_seed_changes_folds(sample):
    first = evaluate_model("logistic_regression", sample, folds=3, seed=1)
    second = evaluate_model("logistic_regression", sample, folds=3, seed=2)
    assert first.cv_means != second.cv_means or \
        first.cv_stds != second.cv_stds


def test_evaluate_confusion_counts_holdout(sample):
    score = evaluate_model("decision_tree", sample, folds=3)
    expected_test = math.ceil(0.25 * len(sample))
    assert int(score.confusion.values.sum()) == expected_test
    assert list(score.confusion.index) == ["actual 0", "actual 1"]
    assert list(score.confusion.columns) == ["pred 0", "pred 1"]


def test_evaluate_holdout_bounded(sample):
    score = evaluate_model("logistic_regression", sample, folds=3)
    for metric in METRICS:
        assert 0.0 <= score.holdout[metric] <= 1.0, metric


# --------------------------------------------------------------------------- #
# Harness (all models)
# --------------------------------------------------------------------------- #
def test_harness_evaluates_every_model(harness):
    assert len(harness.scores) == len(MODELS)
    assert {s.name for s in harness.scores} == set(MODELS)
    assert harness.rows == 320
    assert harness.features == 5


def test_harness_best_is_argmax_f1(harness):
    expected = max(harness.scores, key=lambda s: s.rank_score).name
    assert harness.best.name == expected
    assert harness.best.rank_score == max(s.rank_score
                                          for s in harness.scores)


def test_harness_ranking_is_sorted(harness):
    values = [s.rank_score for s in harness.ranking]
    assert values == sorted(values, reverse=True)


def test_harness_best_raises_when_empty():
    empty = HarnessResult()
    with pytest.raises(HarnessError, match="no models"):
        _ = empty.best


def test_harness_rejects_bad_folds(sample):
    with pytest.raises(HarnessError, match="folds must be"):
        run_harness(sample, folds=11)


def test_harness_to_dict(harness):
    payload = harness.to_dict()
    json.dumps(payload)
    assert payload["rows"] == 320
    assert payload["folds"] == 3
    assert len(payload["models"]) == len(MODELS)
    assert payload["best_model"] == harness.best.name
    assert payload["models"][0]["name"] == payload["best_model"]
    for entry in payload["models"]:
        assert set(entry["cv"]) == set(METRICS)
        assert "mean" in entry["cv"]["f1"] and "std" in entry["cv"]["f1"]


def test_model_score_to_dict_rounds(sample):
    score = evaluate_model("naive_bayes", sample, folds=3)
    payload = score.to_dict()
    json.dumps(payload)
    assert payload["folds"] == 3
    assert len(payload["holdout"]) == len(METRICS)


def test_model_score_rank_score_property():
    score = ModelScore(name="x", cv_means={"f1": 0.75})
    assert score.rank_score == 0.75
    assert ModelScore(name="y").rank_score == 0.0  # missing -> 0


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections(harness, sample):
    text = render_report(harness, sample)
    assert "MODEL EVALUATION HARNESS" in text
    assert "Ranking by" in text
    assert "<-- best" in text
    assert "Hold-out confusion matrix:" in text
    assert "CV F1 spread across models:" in text
    for name in MODELS:
        assert name in text


def test_render_report_lists_best_last_marked(harness, sample):
    text = render_report(harness, sample)
    best_line = next(line for line in text.splitlines()
                     if "<-- best" in line)
    assert harness.best.name in best_line


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Best model:" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(HarnessError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_demo_custom_folds(capsys):
    assert main(["--demo", "--folds", "3", "--quiet"]) == 0


def test_cli_file_evaluation(capsys):
    assert main(["--file", str(DEMO_CSV)]) == 0
    out = capsys.readouterr().out
    assert "Best model:" in out and "Done." in out


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "comparison.json"
    assert main(["--file", str(DEMO_CSV), "--folds", "3",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["best_model"] in MODELS
    assert len(payload["models"]) == len(MODELS)


def test_cli_list(capsys):
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    for name in MODELS:
        assert name in out
    assert f"{len(MODELS)} models available." in out


def test_cli_bad_folds(capsys):
    assert main(["--file", str(DEMO_CSV), "--folds", "99"]) == 2
    assert "folds must be" in capsys.readouterr().err


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


# --------------------------------------------------------------------------- #
# Metrics contract
# --------------------------------------------------------------------------- #
def test_harness_counts_match_the_frame(harness, sample):
    assert harness.rows == len(sample)
    assert harness.features == len(sample.columns) - 1


def test_harness_folds_recorded(harness):
    assert harness.folds == 3
    assert all(score.folds == 3 for score in harness.scores)


def test_harness_to_dict_models_follow_the_ranking(harness):
    payload = harness.to_dict()
    assert [m["name"] for m in payload["models"]] == [
        s.name for s in harness.ranking]
    assert payload["best_model"] == harness.best.name


def test_every_holdout_metric_is_bounded(sample):
    score = evaluate_model("logistic_regression", sample)
    for metric in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        assert 0.0 <= score.holdout[metric] <= 1.0


def test_cv_metrics_are_bounded(sample):
    score = evaluate_model("decision_tree", sample)
    for metric in METRICS:
        assert 0.0 <= score.cv_means[metric] <= 1.0
        assert score.cv_stds[metric] >= 0.0


def test_render_report_is_ascii(harness, sample):
    render_report(harness, sample).encode("ascii")


def test_minimum_rows_below_floor_rejected(tmp_path):
    rows = _grid(n=40)
    with pytest.raises(HarnessError):
        load_dataset(_csv(tmp_path, rows))
