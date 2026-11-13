"""Iris species classifier: k-NN training, evaluation, and prediction — offline.

Loads the bundled iris CSV, trains a k-nearest-neighbours classifier with a
stratified train/test split, evaluates it (accuracy, per-class precision /
recall / F1, confusion matrix), and predicts species for new flower
measurements. Cross-validation runs inside scikit-learn - no network, no
dataset downloads, no model files fetched from anywhere.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.neighbors import KNeighborsClassifier

LOG = logging.getLogger("iris")

FEATURES = ("sepal_length", "sepal_width", "petal_length", "petal_width")
REQUIRED_COLUMNS = FEATURES + ("species",)
SPECIES = ("setosa", "versicolor", "virginica")
# plausible ranges for iris measurements (cm) - validated on load
RANGES = {
    "sepal_length": (4.0, 8.0),
    "sepal_width": (2.0, 4.5),
    "petal_length": (1.0, 7.0),
    "petal_width": (0.1, 2.6),
}


class IrisError(RuntimeError):
    """Raised for missing files, bad schemas, and training failures."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_iris(path: str | Path) -> pd.DataFrame:
    """Load the iris CSV, validate it, and return a cleaned DataFrame."""
    source = Path(path)
    if not source.is_file():
        raise IrisError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise IrisError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise IrisError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise IrisError(f"no rows in {source.name}")

    frame = frame.copy()
    for column in FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise IrisError(f"column {column!r} contains non-numeric values")
        low, high = RANGES[column]
        if not frame[column].between(low, high).all():
            raise IrisError(f"column {column!r} outside {low}..{high}")

    frame["species"] = frame["species"].astype(str).str.strip().str.lower()
    unknown = sorted(set(frame["species"]) - set(SPECIES))
    if unknown:
        raise IrisError(
            f"unknown species: {', '.join(unknown)} "
            f"(expected {', '.join(SPECIES)})"
        )

    counts = frame["species"].value_counts()
    if len(counts) < 2:
        raise IrisError("need at least two species to classify")
    if counts.min() < 5:
        small = counts[counts < 5].index.tolist()
        raise IrisError(
            f"species with too few rows (need >= 5): {', '.join(small)}"
        )

    frame = frame.sample(frac=1, random_state=42).reset_index(drop=True)
    LOG.info("loaded %d rows across %d species from %s",
             len(frame), len(counts), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
@dataclass
class ModelResult:
    """Trained k-NN model plus its hold-out and cross-validation metrics."""

    model: KNeighborsClassifier
    neighbors: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    cv_mean: float
    cv_std: float
    confusion: pd.DataFrame
    report_text: str
    test_species: pd.Series = field(default_factory=pd.Series)
    test_pred: pd.Series = field(default_factory=pd.Series)

    def to_dict(self) -> dict[str, Any]:
        return {
            "neighbors": self.neighbors,
            "holdout": {
                "accuracy": round(self.accuracy, 4),
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4),
                "f1": round(self.f1, 4),
            },
            "cross_validation": {
                "folds": 5,
                "f1_mean": round(self.cv_mean, 4),
                "f1_std": round(self.cv_std, 4),
            },
            "confusion_matrix": {
                str(true): {str(pred): int(count)
                            for pred, count in row.items()}
                for true, row in self.confusion.to_dict("index").items()
            },
        }


def train_model(frame: pd.DataFrame, neighbors: int = 5,
                test_size: float = 0.25, seed: int = 42) -> ModelResult:
    """Train k-NN on a validated frame and score it on a held-out split."""
    if neighbors < 1 or neighbors > 50:
        raise IrisError("neighbors must be in 1..50")
    if not 0.05 <= test_size <= 0.5:
        raise IrisError("test_size must be in 0.05..0.5")

    x = frame[list(FEATURES)]
    y = frame["species"]

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=test_size, random_state=seed, stratify=y)

    # k cannot exceed the smallest training fold
    min_class_train = int(y_train.value_counts().min())
    effective_k = min(neighbors, min_class_train)
    if effective_k < 1:
        raise IrisError("training split too small for k-NN")

    model = KNeighborsClassifier(n_neighbors=effective_k)
    model.fit(x_train, y_train)
    predicted = pd.Series(model.predict(x_test), index=y_test.index,
                          name="predicted")

    accuracy = float(accuracy_score(y_test, predicted))
    precision = float(precision_score(y_test, predicted, average="macro"))
    recall = float(recall_score(y_test, predicted, average="macro"))
    f1 = float(f1_score(y_test, predicted, average="macro"))

    # stratified cross-validation on the training portion only
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    cv_scores = cross_val_score(model, x_train, y_train,
                                cv=folds, scoring="f1_macro")
    labels = sorted(set(y) | set(predicted))
    confusion = pd.DataFrame(
        confusion_matrix(y_test, predicted, labels=labels),
        index=labels, columns=labels)
    report_text = classification_report(y_test, predicted, digits=3)

    result = ModelResult(
        model=model, neighbors=effective_k, accuracy=accuracy,
        precision=precision, recall=recall, f1=f1,
        cv_mean=float(cv_scores.mean()), cv_std=float(cv_scores.std()),
        confusion=confusion, report_text=report_text,
        test_species=y_test, test_pred=predicted,
    )
    LOG.info("trained k=%d: hold-out F1 %.4f, CV F1 %.4f +/- %.4f",
             effective_k, f1, result.cv_mean, result.cv_std)
    return result


def predict_species(model: KNeighborsClassifier,
                    measurements: dict[str, float]) -> str:
    """Predict the species for one flower's measurements."""
    missing = [f for f in FEATURES if f not in measurements]
    if missing:
        raise IrisError(f"missing measurement(s): {', '.join(missing)}")
    row = []
    for feature in FEATURES:
        value = measurements[feature]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise IrisError(f"measurement {feature!r} must be a number")
        low, high = RANGES[feature]
        if not low <= float(value) <= high:
            raise IrisError(
                f"measurement {feature!r} outside {low}..{high}: {value}")
        row.append(float(value))
    # predict with a named DataFrame so sklearn sees the fitted feature names
    input_frame = pd.DataFrame([row], columns=list(FEATURES))
    return str(model.predict(input_frame)[0])


def feature_means_by_species(frame: pd.DataFrame) -> pd.DataFrame:
    """Mean measurements per species (helps explain predictions)."""
    table = frame.groupby("species")[list(FEATURES)].mean().round(3)
    return table.reindex([s for s in SPECIES if s in table.index])


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(result: ModelResult, frame: pd.DataFrame) -> str:
    """Human-readable training/evaluation report used by the CLI and demo."""
    lines = [
        "IRIS SPECIES CLASSIFIER (k-NN)",
        "=" * 64,
        f"Rows        : {len(frame)}  features: {len(FEATURES)}  "
        f"species: {frame['species'].nunique()}",
        f"Model       : k-NN (k={result.neighbors}), "
        f"stratified 75/25 split",
        f"Hold-out    : accuracy {result.accuracy:.3f}  "
        f"precision {result.precision:.3f}  "
        f"recall {result.recall:.3f}  F1 {result.f1:.3f}",
        f"5-fold CV   : F1 {result.cv_mean:.3f} +/- {result.cv_std:.3f} "
        f"(train split only)",
        "",
        "Confusion matrix (rows = actual, cols = predicted):",
    ]
    header = "          " + "".join(f"{c:>11}" for c in result.confusion.columns)
    lines.append(header)
    for true, row in result.confusion.iterrows():
        cells = "".join(f"{int(v):>11}" for v in row)
        lines.append(f"  {true:<8}{cells}")

    lines += ["", "Per-class metrics:"]
    for line in result.report_text.rstrip().splitlines():
        lines.append(f"  {line}")

    means = feature_means_by_species(frame)
    lines += ["", "Mean measurements by species:"]
    lines.append("  " + f"{'species':<12}" + "".join(
        f"{f:>13}" for f in FEATURES))
    for species, row in means.iterrows():
        lines.append("  " + f"{species:<12}" + "".join(
            f"{row[f]:>13.2f}" for f in FEATURES))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "iris.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Train and evaluate on the bundled iris sample — fully offline."""
    print("=" * 64)
    print(" IRIS SPECIES CLASSIFIER - offline demo")
    print(" Bundled CSV; scikit-learn k-NN; no network, no downloads.")
    print("=" * 64)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise IrisError(f"bundled sample not found: {source}")

    frame = load_iris(source)
    print(f"\nLoaded {len(frame)} rows from {source.name}")

    result = train_model(frame, neighbors=5)
    print()
    print(render_report(result, frame))

    # --- cross-checks the demo asserts ----------------------------------- #
    counts = frame["species"].value_counts()
    assert int(counts.sum()) == len(frame), "class counts must sum to n"
    assert result.accuracy == float(
        (result.test_species == result.test_pred).mean()), "accuracy mismatch"
    assert 0.0 <= result.accuracy <= 1.0
    assert 0.0 <= result.f1 <= 1.0
    assert int(result.confusion.values.sum()) == len(result.test_species), \
        "confusion matrix must count every test row"
    # diagonal dominance: a working model gets most rows right
    diagonal = float(np.trace(result.confusion.values))
    assert diagonal / len(result.test_species) >= 0.85, \
        "hold-out accuracy unexpectedly low"
    assert abs(result.cv_mean - result.f1) < 0.2, \
        "CV and hold-out scores disagree wildly"

    # known flowers classify sensibly
    setosa_like = {"sepal_length": 5.1, "sepal_width": 3.5,
                   "petal_length": 1.4, "petal_width": 0.2}
    virginica_like = {"sepal_length": 6.7, "sepal_width": 3.0,
                      "petal_length": 5.2, "petal_width": 2.3}
    predicted_setosa = predict_species(result.model, setosa_like)
    predicted_virginica = predict_species(result.model, virginica_like)
    assert predicted_setosa == "setosa", f"got {predicted_setosa}"
    assert predicted_virginica == "virginica", f"got {predicted_virginica}"

    print(f"\nSample predictions:")
    print(f"  {setosa_like}  -> {predicted_setosa}")
    print(f"  {virginica_like}  -> {predicted_virginica}")
    print(f"\nCross-checks OK: accuracy {result.accuracy:.3f} matches the "
          f"test split, confusion matrix counts {len(result.test_species)} "
          f"rows, sanity predictions correct")
    print("\nDemo completed successfully.")
    return 0
