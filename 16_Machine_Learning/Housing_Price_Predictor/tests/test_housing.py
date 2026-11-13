"""Tests for the Housing Price Predictor project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from housing import (  # noqa: E402
    DEMO_CSV,
    DISTRICTS,
    NUMERIC,
    REQUIRED_COLUMNS,
    HousingError,
    _metrics,
    load_housing,
    predict_price,
    render_report,
    run_demo,
    train_model,
)
from main import main, parse_house  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    row = {
        "size_sqm": 120.0, "rooms": 4, "age_years": 8, "dist_km": 6.5,
        "floor": 7, "has_lift": 1, "has_garden": 0,
        "district": "Central", "price": 400000,
    }
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "housing.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _grid(n: int = 40) -> list[dict]:
    """n valid rows across two districts (enough to train)."""
    rows = []
    for i in range(n):
        rows.append(_row(
            district="Central" if i % 2 else "South",
            size_sqm=60.0 + (i % 10) * 15,
            rooms=1 + i % 6,
            age_years=i % 50,
            dist_km=1.0 + i % 30,
            floor=1 + i % 18,
            price=150000 + i * 8000,
        ))
    return rows


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_housing(DEMO_CSV)


@pytest.fixture(scope="module")
def trained(sample):
    return train_model(sample)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 400
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert set(sample["district"]) <= set(DISTRICTS)
    assert sample["district"].nunique() == 5
    assert (sample["price"] >= 1000).all()
    for column in ("has_lift", "has_garden"):
        assert set(sample[column]) <= {0, 1}


def test_load_missing_file(tmp_path):
    with pytest.raises(HousingError, match="not found"):
        load_housing(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("size_sqm,price\n120,400000\n", encoding="utf-8")
    with pytest.raises(HousingError, match="missing column"):
        load_housing(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(HousingError, match="no rows"):
        load_housing(path)


def test_load_non_numeric_price(tmp_path):
    rows = _grid()
    rows[0]["price"] = "expensive"
    with pytest.raises(HousingError, match="'price' contains non-numeric"):
        load_housing(_csv(tmp_path, rows))


def test_load_nan_size(tmp_path):
    rows = _grid()
    rows[0]["size_sqm"] = None
    with pytest.raises(HousingError, match="'size_sqm' contains non-numeric"):
        load_housing(_csv(tmp_path, rows))


def test_load_size_out_of_range(tmp_path):
    rows = _grid()
    rows[0]["size_sqm"] = 5000.0
    with pytest.raises(HousingError, match="size_sqm.*outside"):
        load_housing(_csv(tmp_path, rows))


def test_load_negative_distance(tmp_path):
    rows = _grid()
    rows[0]["dist_km"] = -3.0
    with pytest.raises(HousingError, match="dist_km.*outside"):
        load_housing(_csv(tmp_path, rows))


def test_load_fractional_rooms(tmp_path):
    rows = _grid()
    rows[0]["rooms"] = 3.5
    with pytest.raises(HousingError, match="'rooms' must be whole numbers"):
        load_housing(_csv(tmp_path, rows))


def test_load_non_binary_lift(tmp_path):
    rows = _grid()
    rows[0]["has_lift"] = 7
    with pytest.raises(HousingError, match="'has_lift' must be 0 or 1"):
        load_housing(_csv(tmp_path, rows))


def test_load_non_binary_garden(tmp_path):
    rows = _grid()
    rows[0]["has_garden"] = 2
    with pytest.raises(HousingError, match="'has_garden' must be 0 or 1"):
        load_housing(_csv(tmp_path, rows))


def test_load_unknown_district(tmp_path):
    rows = _grid()
    rows[0]["district"] = "Rivendell"
    with pytest.raises(HousingError, match="unknown district.*Rivendell"):
        load_housing(_csv(tmp_path, rows))


def test_load_district_case_normalized(tmp_path):
    rows = _grid()
    for row in rows:
        row["district"] = "central" if row["district"] == "Central" else "SOUTH"
    frame = load_housing(_csv(tmp_path, rows))
    assert set(frame["district"]) <= set(DISTRICTS)


def test_load_single_district_rejected(tmp_path):
    rows = _grid()
    for row in rows:
        row["district"] = "Central"
    with pytest.raises(HousingError, match="at least two districts"):
        load_housing(_csv(tmp_path, rows))


def test_load_too_few_rows(tmp_path):
    with pytest.raises(HousingError, match="at least 40 rows"):
        load_housing(_csv(tmp_path, _grid(10)))


# --------------------------------------------------------------------------- #
# Metric math
# --------------------------------------------------------------------------- #
def test_metrics_exact_math_on_tiny_split():
    actual = [100.0, 200.0, 300.0]
    predicted = [110.0, 190.0, 330.0]
    values = _metrics(actual, predicted)
    # errors: 10, 10, 30 -> mae 16.667, mse (100+100+900)/3 = 366.667
    assert values["mae"] == pytest.approx((10 + 10 + 30) / 3)
    assert values["rmse"] == pytest.approx((366.666666) ** 0.5, rel=1e-5)
    # mean baseline predicts 200: errors 100, 0, 100 -> rmse sqrt(20000/3)
    assert values["baseline_rmse"] == pytest.approx((20000 / 3) ** 0.5,
                                                    rel=1e-5)
    assert -1.0 <= values["r2"] <= 1.0


def test_metrics_perfect_prediction():
    values = _metrics([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert values["rmse"] == 0.0
    assert values["mae"] == 0.0
    assert values["r2"] == pytest.approx(1.0)


def test_metrics_r2_zero_for_mean_predictor():
    actual = [10.0, 20.0, 30.0]
    values = _metrics(actual, [20.0, 20.0, 20.0])
    assert values["r2"] == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
def test_train_produces_valid_scores(trained):
    for name, values in trained.metrics.items():
        assert values["rmse"] > 0, name
        assert values["mae"] >= 0, name
        assert -1.0 <= values["r2"] <= 1.0, name
        assert values["mae"] <= values["rmse"], name


def test_train_models_beat_baseline(trained):
    baseline = trained.metrics["mean_baseline"]["rmse"]
    assert trained.metrics["linear_regression"]["rmse"] < baseline
    assert trained.metrics["random_forest"]["rmse"] < baseline


def test_train_forest_r2_is_high(trained):
    assert trained.metrics["random_forest"]["r2"] > 0.7
    assert trained.metrics["linear_regression"]["r2"] > 0.7


def test_train_prediction_lengths_match(trained):
    n = len(trained.test_actual)
    assert len(trained.test_pred_linear) == n
    assert len(trained.test_pred_forest) == n
    assert n == 100  # 25% of 400


def test_train_is_deterministic(sample):
    first = train_model(sample, seed=42)
    second = train_model(sample, seed=42)
    assert first.metrics["random_forest"]["rmse"] == \
        second.metrics["random_forest"]["rmse"]
    assert first.best_model_name == second.best_model_name


def test_train_seed_changes_split(sample):
    first = train_model(sample, seed=1)
    second = train_model(sample, seed=2)
    assert len(first.test_actual) == len(second.test_actual)
    # different seeds -> different hold-out rows
    assert list(first.test_actual.index) != list(second.test_actual.index)


def test_train_rejects_bad_test_size(sample):
    with pytest.raises(HousingError, match="test_size"):
        train_model(sample, test_size=0.9)


def test_best_model_is_min_rmse(trained):
    expected = min(trained.metrics,
                   key=lambda name: trained.metrics[name]["rmse"])
    assert trained.best_model_name == expected
    assert trained.best_rmse == trained.metrics[expected]["rmse"]


def test_coefficients_cover_all_numeric_features(trained):
    features = set(trained.coefficients["feature"])
    assert set(NUMERIC) <= features
    assert any(f.startswith("district_") for f in features)


def test_forest_importances_sum_to_one(trained):
    total = float(trained.forest_importances["importance"].sum())
    assert total == pytest.approx(1.0, abs=0.05)


def test_result_to_dict(trained):
    payload = trained.to_dict()
    json.dumps(payload)
    assert set(payload["metrics"]) == {
        "linear_regression", "random_forest", "mean_baseline"}
    assert payload["best_model"] in payload["metrics"]
    assert len(payload["forest_importances"]) >= len(NUMERIC)
    assert all(isinstance(row["coefficient"], (int, float))
               for row in payload["coefficients"])


# --------------------------------------------------------------------------- #
# Prediction
# --------------------------------------------------------------------------- #
def test_predict_central_beats_peripheral(trained):
    central = {"size_sqm": 120.0, "rooms": 4, "age_years": 8, "dist_km": 6.5,
               "floor": 7, "has_lift": 1, "has_garden": 0,
               "district": "Central"}
    south = dict(central, district="South", dist_km=40.0, age_years=50)
    assert predict_price(trained, central) > predict_price(trained, south)


def test_predict_larger_costs_more(trained):
    base = {"size_sqm": 100.0, "rooms": 3, "age_years": 10, "dist_km": 10.0,
            "floor": 5, "has_lift": 1, "has_garden": 0,
            "district": "Central"}
    bigger = dict(base, size_sqm=200.0)
    assert predict_price(trained, bigger) > predict_price(trained, base)


def test_predict_newer_costs_more(trained):
    base = {"size_sqm": 100.0, "rooms": 3, "age_years": 40, "dist_km": 10.0,
            "floor": 5, "has_lift": 1, "has_garden": 0,
            "district": "Central"}
    new = dict(base, age_years=2)
    assert predict_price(trained, new) > predict_price(trained, base)


def test_predict_returns_positive_float(trained):
    house = {"size_sqm": 90.0, "rooms": 3, "age_years": 12, "dist_km": 8.0,
             "floor": 4, "has_lift": 1, "has_garden": 0,
             "district": "East"}
    price = predict_price(trained, house)
    assert isinstance(price, float)
    assert price > 0


def test_predict_missing_field(trained):
    with pytest.raises(HousingError, match="missing field"):
        predict_price(trained, {"size_sqm": 100.0})


def test_predict_non_numeric_field(trained):
    house = {"size_sqm": "big", "rooms": 3, "age_years": 12, "dist_km": 8.0,
             "floor": 4, "has_lift": 1, "has_garden": 0,
             "district": "East"}
    with pytest.raises(HousingError, match="must be a number"):
        predict_price(trained, house)


def test_predict_out_of_range_field(trained):
    house = {"size_sqm": 100.0, "rooms": 3, "age_years": 12, "dist_km": 8.0,
             "floor": 4, "has_lift": 1, "has_garden": 0,
             "district": "East"}
    house["floor"] = 0
    with pytest.raises(HousingError, match="floor.*outside"):
        predict_price(trained, house)


def test_predict_unknown_district(trained):
    house = {"size_sqm": 100.0, "rooms": 3, "age_years": 12, "dist_km": 8.0,
             "floor": 4, "has_lift": 1, "has_garden": 0,
             "district": "Gotham"}
    with pytest.raises(HousingError, match="unknown district"):
        predict_price(trained, house)


def test_parse_house():
    values = parse_house("180,5,3,3.0,12,1,1,Central")
    assert values == {"size_sqm": 180.0, "rooms": 5, "age_years": 3,
                      "dist_km": 3.0, "floor": 12, "has_lift": 1,
                      "has_garden": 1, "district": "Central"}
    assert isinstance(values["rooms"], int)
    assert isinstance(values["has_lift"], int)


def test_parse_house_wrong_count():
    with pytest.raises(HousingError, match="expected 8"):
        parse_house("1,2,3")


def test_parse_house_not_a_number():
    with pytest.raises(HousingError, match="not a number"):
        parse_house("big,5,3,3.0,12,1,1,Central")


def test_parse_house_bad_district():
    with pytest.raises(HousingError, match="unknown district"):
        parse_house("180,5,3,3.0,12,1,1,Atlantis")


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections(trained, sample):
    text = render_report(trained, sample)
    assert "HOUSING PRICE PREDICTOR" in text
    assert "linear_regression" in text
    assert "random_forest" in text
    assert "mean_baseline" in text
    assert "Best model:" in text
    assert "Linear coefficients" in text
    assert "Random forest importances" in text
    assert "size_sqm" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Sample predictions:" in out
    assert "-> $" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(HousingError, match="bundled sample"):
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
    assert "Best model:" in out and "Done." in out


def test_cli_file_with_predict(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV),
                 "--predict", "180,5,3,3.0,12,1,1,Central",
                 "--json", str(payload_path)]) == 0
    out = capsys.readouterr().out
    assert "Prediction: 180,5,3,3.0,12,1,1,Central -> $" in out
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["prediction"] > 0
    assert payload["best_model"] in payload["metrics"]


def test_cli_predict_uses_bundled_data(capsys):
    assert main(["--predict", "180,5,3,3.0,12,1,1,Central", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Prediction:" in out and "-> $" in out


def test_cli_predict_bad_count(capsys):
    assert main(["--predict", "1,2", "--quiet"]) == 2
    assert "expected 8" in capsys.readouterr().err


def test_cli_predict_bad_district(capsys):
    assert main(["--predict", "180,5,3,3.0,12,1,1,Atlantis",
                 "--quiet"]) == 2
    assert "unknown district" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--json", str(payload_path),
                 "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert set(payload["metrics"]) == {
        "linear_regression", "random_forest", "mean_baseline"}


def test_cli_seed_option(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--seed", "7",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["best_model"] in payload["metrics"]


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
