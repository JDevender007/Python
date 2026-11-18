"""Housing price prediction: regression training and evaluation - offline.

Loads a housing CSV (size, rooms, age, distance, floor, lift, garden,
district), one-hot encodes the district, trains a linear regression and a
random forest, compares both against a mean-predictor baseline, and reports
RMSE / MAE / R^2 plus the learned coefficients. Local files only - no
network, no dataset downloads, no model artifacts fetched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer

LOG = logging.getLogger("housing")

CATEGORICAL = ("district",)
NUMERIC = ("size_sqm", "rooms", "age_years", "dist_km", "floor",
           "has_lift", "has_garden")
REQUIRED_COLUMNS = NUMERIC + CATEGORICAL + ("price",)
DISTRICTS = ("Central", "East", "North", "South", "West")

RANGES = {
    "size_sqm": (10.0, 1000.0),
    "rooms": (1, 20),
    "age_years": (0, 150),
    "dist_km": (0.0, 200.0),
    "floor": (1, 100),
    "has_lift": (0, 1),
    "has_garden": (0, 1),
    "price": (1000.0, 100_000_000.0),
}


class HousingError(RuntimeError):
    """Raised for missing files, bad schemas, and training failures."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_housing(path: str | Path) -> pd.DataFrame:
    """Load the housing CSV, validate it, and return a cleaned DataFrame."""
    source = Path(path)
    if not source.is_file():
        raise HousingError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise HousingError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise HousingError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise HousingError(f"no rows in {source.name}")

    frame = frame.copy()
    for column in NUMERIC + ("price",):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise HousingError(f"column {column!r} contains non-numeric values")

    for column in ("rooms", "floor", "has_lift", "has_garden"):
        if (frame[column] % 1 != 0).any():
            raise HousingError(f"column {column!r} must be whole numbers")
    for column in ("has_lift", "has_garden"):
        bad = sorted(set(frame[column].unique()) - {0, 1})
        if bad:
            raise HousingError(f"column {column!r} must be 0 or 1 "
                               f"(got {bad})")

    for column in NUMERIC + ("price",):
        low, high = RANGES[column]
        if not frame[column].between(low, high).all():
            raise HousingError(f"column {column!r} outside {low:g}..{high:g}")

    frame["district"] = frame["district"].astype(str).str.strip().str.title()
    unknown = sorted(set(frame["district"]) - set(DISTRICTS))
    if unknown:
        raise HousingError(
            f"unknown district(s): {', '.join(unknown)} "
            f"(expected {', '.join(DISTRICTS)})"
        )
    if frame["district"].nunique() < 2:
        raise HousingError("need at least two districts")
    if len(frame) < 40:
        raise HousingError("need at least 40 rows to train")

    frame = frame.sample(frac=1, random_state=7).reset_index(drop=True)
    LOG.info("loaded %d rows from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
@dataclass
class ModelResult:
    """Hold-out metrics for the linear model, forest, and baseline."""

    metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    coefficients: pd.DataFrame = field(default_factory=pd.DataFrame)
    forest_importances: pd.DataFrame = field(default_factory=pd.DataFrame)
    test_actual: pd.Series = field(default_factory=pd.Series)
    test_pred_linear: pd.Series = field(default_factory=pd.Series)
    test_pred_forest: pd.Series = field(default_factory=pd.Series)
    linear: Any = None
    forest: Any = None

    @property
    def best_model_name(self) -> str:
        return min(self.metrics, key=lambda name: self.metrics[name]["rmse"])

    @property
    def best_rmse(self) -> float:
        return self.metrics[self.best_model_name]["rmse"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": {name: {k: round(v, 2) for k, v in values.items()}
                        for name, values in self.metrics.items()},
            "best_model": self.best_model_name,
            "coefficients": [
                {"feature": str(row["feature"]),
                 "coefficient": round(float(row["coefficient"]), 2)}
                for _, row in self.coefficients.iterrows()
            ],
            "forest_importances": [
                {"feature": str(row["feature"]),
                 "importance": round(float(row["importance"]), 4)}
                for _, row in self.forest_importances.iterrows()
            ],
        }


def _metrics(y_true: Any, y_pred: Any) -> dict[str, float]:
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    # mean predictor's RMSE on the same split = std of the test targets
    baseline = np.full(actual.shape, float(actual.mean()))
    return {
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "mae": float(mean_absolute_error(actual, predicted)),
        "r2": float(r2_score(actual, predicted)),
        "baseline_rmse": float(np.sqrt(mean_squared_error(actual, baseline))),
    }


def train_model(frame: pd.DataFrame, seed: int = 42,
                test_size: float = 0.25) -> ModelResult:
    """Train linear regression + random forest and compare to a baseline."""
    if not 0.05 <= test_size <= 0.5:
        raise HousingError("test_size must be in 0.05..0.5")

    features = list(NUMERIC) + list(CATEGORICAL)
    x = frame[features]
    y = frame["price"]

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=test_size, random_state=seed)

    def _preprocessor() -> ColumnTransformer:
        return ColumnTransformer([
            ("district", OneHotEncoder(handle_unknown="ignore"),
             list(CATEGORICAL)),
        ], remainder="passthrough")

    linear_pipe = Pipeline([
        ("prep", _preprocessor()),
        ("model", LinearRegression()),
    ])
    linear_pipe.fit(x_train, y_train)
    pred_linear = pd.Series(linear_pipe.predict(x_test), index=y_test.index)

    forest_pipe = Pipeline([
        ("prep", _preprocessor()),
        ("model", RandomForestRegressor(
            n_estimators=200, max_depth=12, random_state=seed, n_jobs=1)),
    ])
    forest_pipe.fit(x_train, y_train)
    pred_forest = pd.Series(forest_pipe.predict(x_test), index=y_test.index)

    metrics = {
        "linear_regression": _metrics(y_test, pred_linear),
        "random_forest": _metrics(y_test, pred_forest),
        "mean_baseline": _metrics(y_test, np.full(len(y_test),
                                                  float(y_train.mean()))),
    }

    # linear coefficients mapped back to feature names
    fitted = linear_pipe.named_steps["model"]
    # ColumnTransformer output order: one-hot districts then passthrough
    hot = list(linear_pipe.named_steps["prep"]
               .named_transformers_["district"]
               .get_feature_names_out(CATEGORICAL))
    full_names = hot + [f for f in features if f not in CATEGORICAL]
    coefficients = pd.DataFrame({
        "feature": full_names,
        "coefficient": np.asarray(fitted.coef_, dtype=float).ravel(),
    }).sort_values("coefficient", key=abs, ascending=False)

    importances = pd.DataFrame({
        "feature": full_names,
        "importance": forest_pipe.named_steps["model"].feature_importances_,
    }).sort_values("importance", ascending=False)

    result = ModelResult(
        metrics=metrics, coefficients=coefficients,
        forest_importances=importances,
        test_actual=y_test, test_pred_linear=pred_linear,
        test_pred_forest=pred_forest,
        linear=linear_pipe, forest=forest_pipe,
    )
    LOG.info("trained: best model %s (RMSE %.0f)",
             result.best_model_name, result.best_rmse)
    return result


def predict_price(result: ModelResult, house: dict[str, Any]) -> float:
    """Predict the price of one house using the better hold-out model."""
    missing = [f for f in NUMERIC + CATEGORICAL if f not in house]
    if missing:
        raise HousingError(f"missing field(s): {', '.join(missing)}")

    values: dict[str, Any] = {}
    for column in NUMERIC:
        raw = house[column]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise HousingError(f"field {column!r} must be a number")
        low, high = RANGES[column]
        if not low <= float(raw) <= high:
            raise HousingError(
                f"field {column!r} outside {low:g}..{high:g}: {raw}")
        values[column] = float(raw)
    district = str(house["district"]).strip().title()
    if district not in DISTRICTS:
        raise HousingError(f"unknown district {district!r}")
    values["district"] = district

    row = pd.DataFrame([values], columns=list(NUMERIC) + list(CATEGORICAL))
    estimator = result.linear if result.best_model_name == "linear_regression" \
        else result.forest
    return float(estimator.predict(row)[0])


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(result: ModelResult, frame: pd.DataFrame) -> str:
    """Human-readable training/evaluation report used by the CLI and demo."""
    lines = [
        "HOUSING PRICE PREDICTOR",
        "=" * 66,
        f"Rows        : {len(frame)}   features: {len(NUMERIC)} numeric + "
        f"1 categorical ({frame['district'].nunique()} districts)",
        f"Target      : price  mean ${frame['price'].mean():,.0f}  "
        f"range ${frame['price'].min():,.0f}..${frame['price'].max():,.0f}",
        "",
        f"{'model':<22}{'RMSE':>14}{'MAE':>14}{'R^2':>10}",
        "-" * 60,
    ]
    for name in ("linear_regression", "random_forest", "mean_baseline"):
        values = result.metrics[name]
        lines.append(f"  {name:<20}{values['rmse']:>14,.0f}"
                     f"{values['mae']:>14,.0f}{values['r2']:>10.3f}")
    lines.append(f"\nBest model: {result.best_model_name} "
                 f"(RMSE ${result.best_rmse:,.0f})")

    lines += ["", "Linear coefficients (largest |value| first):"]
    for _, row in result.coefficients.head(8).iterrows():
        direction = "+" if row["coefficient"] >= 0 else "-"
        lines.append(f"  {row['feature']:<18} {direction} "
                     f"${abs(row['coefficient']):>12,.0f}")

    lines += ["", "Random forest importances:"]
    for _, row in result.forest_importances.iterrows():
        bar = "#" * max(1, round(float(row["importance"]) * 60))
        lines.append(f"  {row['feature']:<14} {row['importance']:.3f}  {bar}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "housing.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Train and evaluate on the bundled housing sample - fully offline."""
    print("=" * 66)
    print(" HOUSING PRICE PREDICTOR - offline demo")
    print(" Bundled synthetic listings; scikit-learn; no network.")
    print("=" * 66)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise HousingError(f"bundled sample not found: {source}")

    frame = load_housing(source)
    print(f"\nLoaded {len(frame)} rows from {source.name}")

    result = train_model(frame)
    print()
    print(render_report(result, frame))

    # --- cross-checks the demo asserts ----------------------------------- #
    for name, values in result.metrics.items():
        assert values["rmse"] > 0, f"{name} rmse must be positive"
        assert values["mae"] >= 0, name
        assert -1.0 <= values["r2"] <= 1.0, f"{name} r2 out of range"
        assert values["mae"] <= values["rmse"] * 1.5, \
            f"{name}: MAE should stay below RMSE"
    # both real models must beat the constant baseline
    for name in ("linear_regression", "random_forest"):
        assert result.metrics[name]["rmse"] < \
            result.metrics["mean_baseline"]["rmse"], \
            f"{name} failed to beat the mean baseline"
    assert result.metrics["random_forest"]["r2"] > 0.7, \
        "forest R^2 unexpectedly low"
    assert int(result.test_actual.shape[0]) == len(result.test_pred_linear) \
        == len(result.test_pred_forest), "prediction lengths differ"
    assert set(result.coefficients["feature"]) >= set(NUMERIC), \
        "numeric coefficients missing"
    assert abs(float(result.forest_importances["importance"].sum()) - 1.0) \
        < 0.05, "forest importances must sum to ~1"

    sample = {"size_sqm": 180.0, "rooms": 5, "age_years": 3, "dist_km": 3.0,
              "floor": 12, "has_lift": 1, "has_garden": 1,
              "district": "Central"}
    predicted = predict_price(result, sample)
    assert predicted > 0, "prediction must be positive"
    # a large central house should cost more than the dataset mean
    assert predicted > float(frame["price"].mean()), \
        "sample house predicted below dataset mean"
    cheap_twin = dict(sample, district="South", dist_km=40.0, age_years=50,
                      has_garden=0, size_sqm=70.0, rooms=2)
    cheap = predict_price(result, cheap_twin)
    assert cheap < predicted, \
        "far/old/south house should cost less than central one"

    print(f"\nSample predictions:")
    print(f"  {sample['size_sqm']} m2 Central, new, close  -> ${predicted:,.0f}")
    print(f"  {cheap_twin['size_sqm']} m2 South, old, far   -> ${cheap:,.0f}")
    print(f"\nCross-checks OK: both models beat the mean baseline, "
          f"forest R^2 {result.metrics['random_forest']['r2']:.3f}, "
          f"importances sum to 1, sanity ordering holds")
    print("Demo completed successfully.")
    return 0
