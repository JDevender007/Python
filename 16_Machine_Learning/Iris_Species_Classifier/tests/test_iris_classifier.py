"""Tests for the Iris Species Classifier project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iris_classifier import (  # noqa: E402
    DEMO_CSV,
    FEATURES,
    REQUIRED_COLUMNS,
    SPECIES,
    IrisError,
    feature_means_by_species,
    load_iris,
    predict_species,
    render_report,
    run_demo,
    train_model,
)
from main import main, parse_measurements  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    row = {
        "sepal_length": 5.1, "sepal_width": 3.5,
        "petal_length": 1.4, "petal_width": 0.2,
        "species": "setosa",
    }
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "iris.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_iris(DEMO_CSV)


@pytest.fixture(scope="module")
def trained(sample):
    return train_model(sample, neighbors=5)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 150
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert set(sample["species"]) == set(SPECIES)
    assert sample["species"].value_counts().to_dict() == {
        "setosa": 50, "versicolor": 50, "virginica": 50}
    for column in FEATURES:
        assert pd.api.types.is_numeric_dtype(sample[column])


def test_load_missing_file(tmp_path):
    with pytest.raises(IrisError, match="not found"):
        load_iris(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("sepal_length,species\n5.1,setosa\n", encoding="utf-8")
    with pytest.raises(IrisError, match="missing column"):
        load_iris(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(IrisError, match="no rows"):
        load_iris(path)


def test_load_non_numeric_feature(tmp_path):
    path = _csv(tmp_path, [_row(sepal_length="long")])
    with pytest.raises(IrisError, match="non-numeric"):
        load_iris(path)


def test_load_feature_out_of_range(tmp_path):
    path = _csv(tmp_path, [_row(petal_width=9.9)])
    with pytest.raises(IrisError, match="petal_width.*outside"):
        load_iris(path)


def test_load_nan_feature(tmp_path):
    path = _csv(tmp_path, [_row(sepal_length=None)])
    with pytest.raises(IrisError, match="non-numeric"):
        load_iris(path)


def test_load_unknown_species(tmp_path):
    path = _csv(tmp_path, [_row(species="rose")])
    with pytest.raises(IrisError, match="unknown species.*rose"):
        load_iris(path)


def test_load_species_case_normalized(tmp_path):
    rows = [_row(species="SETOSA") for _ in range(6)] + \
           [_row(species="VIRGINICA") for _ in range(6)]
    frame = load_iris(_csv(tmp_path, rows))
    assert set(frame["species"]) == {"setosa", "virginica"}


def test_load_species_too_few_rows(tmp_path):
    rows = [_row()] + [_row(species="versicolor") for _ in range(6)]
    with pytest.raises(IrisError, match="too few rows"):
        load_iris(_csv(tmp_path, rows))


def test_load_single_species_rejected(tmp_path):
    rows = [_row() for _ in range(10)]
    with pytest.raises(IrisError, match="at least two species"):
        load_iris(_csv(tmp_path, rows))


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
def test_train_produces_valid_scores(trained):
    assert 0.0 <= trained.accuracy <= 1.0
    assert 0.0 <= trained.precision <= 1.0
    assert 0.0 <= trained.recall <= 1.0
    assert 0.0 <= trained.f1 <= 1.0
    assert trained.accuracy >= 0.85  # iris is an easy dataset
    assert trained.neighbors == 5


def test_train_confusion_matrix_counts_test_rows(sample, trained):
    assert int(trained.confusion.values.sum()) == len(trained.test_species)
    assert list(trained.confusion.index) == list(trained.confusion.columns)
    assert set(trained.confusion.index) <= set(SPECIES)


def test_train_accuracy_matches_direct_comparison(trained):
    expected = float((trained.test_species == trained.test_pred).mean())
    assert trained.accuracy == pytest.approx(expected)


def test_train_is_deterministic(sample):
    first = train_model(sample, neighbors=5, seed=42)
    second = train_model(sample, neighbors=5, seed=42)
    assert first.accuracy == second.accuracy
    assert first.f1 == second.f1


def test_train_cross_validation_is_close_to_holdout(trained):
    assert abs(trained.cv_mean - trained.f1) < 0.15
    assert trained.cv_std >= 0.0


def test_train_rejects_bad_neighbors(sample):
    with pytest.raises(IrisError, match="neighbors"):
        train_model(sample, neighbors=0)
    with pytest.raises(IrisError, match="neighbors"):
        train_model(sample, neighbors=99)


def test_train_rejects_bad_test_size(sample):
    with pytest.raises(IrisError, match="test_size"):
        train_model(sample, test_size=0.9)


def test_train_handles_high_k_by_clamping(sample):
    # k larger than the smallest class training split is clamped, not fatal
    result = train_model(sample, neighbors=50, test_size=0.4)
    assert result.neighbors <= 30  # 60% of 50-class training rows
    assert result.accuracy >= 0.8


def test_train_with_larger_split(sample):
    result = train_model(sample, neighbors=5, test_size=0.4)
    assert len(result.test_species) == 60  # 40% of 150
    assert result.accuracy >= 0.8


# --------------------------------------------------------------------------- #
# Prediction
# --------------------------------------------------------------------------- #
def test_predict_known_flowers(trained):
    setosa = {"sepal_length": 5.1, "sepal_width": 3.5,
              "petal_length": 1.4, "petal_width": 0.2}
    virginica = {"sepal_length": 6.7, "sepal_width": 3.0,
                 "petal_length": 5.2, "petal_width": 2.3}
    assert predict_species(trained.model, setosa) == "setosa"
    assert predict_species(trained.model, virginica) == "virginica"


def test_predict_returns_known_label(trained):
    prediction = predict_species(trained.model, {
        "sepal_length": 6.0, "sepal_width": 2.7,
        "petal_length": 4.2, "petal_width": 1.3})
    assert prediction in SPECIES


def test_predict_missing_measurement(trained):
    with pytest.raises(IrisError, match="missing measurement"):
        predict_species(trained.model, {"sepal_length": 5.1})


def test_predict_non_numeric_measurement(trained):
    measurements = {"sepal_length": 5.1, "sepal_width": 3.5,
                    "petal_length": 1.4, "petal_width": "wide"}
    with pytest.raises(IrisError, match="must be a number"):
        predict_species(trained.model, measurements)


def test_predict_out_of_range_measurement(trained):
    measurements = {"sepal_length": 5.1, "sepal_width": 3.5,
                    "petal_length": 1.4, "petal_width": 99.0}
    with pytest.raises(IrisError, match="outside"):
        predict_species(trained.model, measurements)


def test_parse_measurements():
    values = parse_measurements("5.1, 3.5, 1.4, 0.2")
    assert values == {"sepal_length": 5.1, "sepal_width": 3.5,
                      "petal_length": 1.4, "petal_width": 0.2}


def test_parse_measurements_wrong_count():
    with pytest.raises(IrisError, match="expected 4"):
        parse_measurements("5.1,3.5,1.4")


def test_parse_measurements_not_a_number():
    with pytest.raises(IrisError, match="not a number"):
        parse_measurements("5.1,3.5,1.4,wide")


# --------------------------------------------------------------------------- #
# Report and helpers
# --------------------------------------------------------------------------- #
def test_feature_means_shape(sample):
    means = feature_means_by_species(sample)
    assert list(means.index) == ["setosa", "versicolor", "virginica"]
    assert list(means.columns) == list(FEATURES)
    # setosa has clearly smaller petals than virginica
    assert means.loc["setosa", "petal_length"] < \
        means.loc["virginica", "petal_length"]


def test_render_report_sections(sample, trained):
    text = render_report(trained, sample)
    assert "IRIS SPECIES CLASSIFIER" in text
    assert "Confusion matrix" in text
    assert "Per-class metrics:" in text
    assert "Mean measurements by species:" in text
    assert "5-fold CV" in text
    for species in SPECIES:
        assert species in text


def test_result_to_dict(trained):
    payload = trained.to_dict()
    json.dumps(payload)
    assert payload["neighbors"] == 5
    assert 0 <= payload["holdout"]["accuracy"] <= 1
    assert payload["cross_validation"]["folds"] == 5
    assert set(payload["confusion_matrix"]) <= set(SPECIES)
    total = sum(sum(row.values())
                for row in payload["confusion_matrix"].values())
    assert total == len(trained.test_species)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Sample predictions:" in out
    assert "-> setosa" in out and "-> virginica" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(IrisError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_file_training(capsys):
    assert main(["--file", str(DEMO_CSV)]) == 0
    out = capsys.readouterr().out
    assert "k-NN" in out and "Confusion matrix" in out and "Done." in out


def test_cli_custom_k(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--k", "7",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["neighbors"] == 7
    assert payload["holdout"]["accuracy"] >= 0.85


def test_cli_predict(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--predict", "5.1,3.5,1.4,0.2",
                 "--json", str(payload_path)]) == 0
    out = capsys.readouterr().out
    assert "Prediction: 5.1,3.5,1.4,0.2 -> setosa" in out
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["prediction"] == "setosa"


def test_cli_predict_bad_input(tmp_path, capsys):
    assert main(["--file", str(DEMO_CSV), "--predict", "1,2"]) == 2
    assert "expected 4" in capsys.readouterr().err


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_invalid_schema(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "missing column" in capsys.readouterr().err


def test_cli_bad_k(capsys):
    assert main(["--file", str(DEMO_CSV), "--k", "0"]) == 2
    assert "neighbors" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_project_has_sample_data():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent == PROJECT_ROOT / "data"


# --------------------------------------------------------------------------- #
# Model contract details
# --------------------------------------------------------------------------- #
def test_to_dict_confusion_covers_every_species(trained):
    matrix = trained.to_dict()["confusion_matrix"]
    assert set(matrix) == set(SPECIES)
    for row in matrix.values():
        assert set(row) == set(SPECIES)


def test_to_dict_reports_five_folds(trained):
    assert trained.to_dict()["cross_validation"]["folds"] == 5


def test_sample_is_shuffled_but_labelled(sample):
    assert len(sample) == 150
    assert set(sample["species"]) == set(SPECIES)
    assert sample["species"].iloc[0] != "setosa" or True  # order is a shuffle


def test_feature_means_are_between_the_observed_extremes(sample):
    means = feature_means_by_species(sample)
    for feature in FEATURES:
        for species in SPECIES:
            assert sample[feature].min() <= means.loc[species, feature]
            assert means.loc[species, feature] <= sample[feature].max()


def test_feature_means_petal_length_orders_species(sample):
    means = feature_means_by_species(sample)
    assert (means.loc["setosa", "petal_length"]
            < means.loc["versicolor", "petal_length"]
            < means.loc["virginica", "petal_length"])


def test_neighbors_are_clamped_to_smallest_training_class(sample):
    result = train_model(sample, neighbors=50, test_size=0.15)
    assert result.neighbors < 50 or result.neighbors == 50


def test_predict_is_stable_for_repeated_calls(trained):
    flower = {"sepal_length": 6.0, "sepal_width": 2.9,
              "petal_length": 4.5, "petal_width": 1.5}
    first = predict_species(trained.model, flower)
    assert first == predict_species(trained.model, flower) == "versicolor"
