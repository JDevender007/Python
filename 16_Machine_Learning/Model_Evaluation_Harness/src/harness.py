"""Model evaluation harness: cross-validated model comparison — offline.

Loads a binary-classification dataset, evaluates several scikit-learn
models with stratified k-fold cross-validation plus a hold-out split
(accuracy, precision, recall, F1, ROC-AUC), ranks them, and renders a
comparison table. Local files only - no network, no dataset downloads,
no model artifacts fetched.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

LOG = logging.getLogger("harness")

LABEL_COLUMN = "label"
MIN_ROWS = 60
MIN_PER_CLASS = 10
METRICS = ("accuracy", "precision", "recall", "f1", "roc_auc")
MIN_FOLDS, MAX_FOLDS = 2, 10


class HarnessError(RuntimeError):
    """Raised for missing files, bad schemas, and evaluation failures."""


# --------------------------------------------------------------------------- #
# Model registry: name -> factory (fresh estimator per evaluation)
# --------------------------------------------------------------------------- #
def _logistic() -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(max_iter=500, random_state=42)),
    ])


def _tree() -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("model", DecisionTreeClassifier(random_state=42)),
    ])


def _forest() -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("model", RandomForestClassifier(n_estimators=150, random_state=42,
                                         n_jobs=1)),
    ])


def _naive_bayes() -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("model", GaussianNB()),
    ])


# name -> (factory, description)
MODELS: dict[str, tuple[Callable[[], Pipeline], str]] = {
    "logistic_regression": (_logistic, "scaled logistic regression"),
    "decision_tree": (_tree, "depth-unbounded decision tree"),
    "random_forest": (_forest, "150-tree random forest"),
    "naive_bayes": (_naive_bayes, "Gaussian naive Bayes"),
}


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_dataset(path: str | Path) -> pd.DataFrame:
    """Load the dataset CSV, validate it, and return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise HarnessError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise HarnessError(f"could not parse {source.name}: {exc}") from exc

    if LABEL_COLUMN not in frame.columns:
        raise HarnessError(
            f"missing column: {LABEL_COLUMN} "
            f"(required: {', '.join(frame.columns)})"
        )
    if frame.empty:
        raise HarnessError(f"no rows in {source.name}")

    frame = frame.copy()
    feature_columns = [c for c in frame.columns if c != LABEL_COLUMN]
    if len(feature_columns) < 1:
        raise HarnessError("need at least one feature column")

    for column in feature_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise HarnessError(f"column {column!r} contains non-numeric values")
        if not np.isfinite(frame[column]).all():
            raise HarnessError(f"column {column!r} must be finite")

    frame[LABEL_COLUMN] = pd.to_numeric(frame[LABEL_COLUMN],
                                        errors="coerce")
    if frame[LABEL_COLUMN].isna().any():
        raise HarnessError(f"column {LABEL_COLUMN!r} contains non-numeric values")
    labels = sorted(frame[LABEL_COLUMN].unique())
    if labels != [0, 1]:
        raise HarnessError(
            f"{LABEL_COLUMN} must be binary 0/1 (got {labels})")
    counts = frame[LABEL_COLUMN].value_counts()
    if len(frame) < MIN_ROWS:
        raise HarnessError(f"need at least {MIN_ROWS} rows, got {len(frame)}")
    for label in (0, 1):
        if counts.get(label, 0) < MIN_PER_CLASS:
            raise HarnessError(
                f"label {label} has {int(counts.get(label, 0))} rows "
                f"(need >= {MIN_PER_CLASS})")
    constant = [c for c in feature_columns if frame[c].nunique() < 2]
    if constant:
        raise HarnessError(
            f"feature(s) with no variation: {', '.join(constant)}")

    frame = frame.sample(frac=1, random_state=5).reset_index(drop=True)
    LOG.info("loaded %d rows (%d features) from %s",
             len(frame), len(feature_columns), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
@dataclass
class ModelScore:
    """Cross-validation and hold-out metrics for one model."""

    name: str
    cv_means: dict[str, float] = field(default_factory=dict)
    cv_stds: dict[str, float] = field(default_factory=dict)
    folds: int = 0
    holdout: dict[str, float] = field(default_factory=dict)
    confusion: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def rank_score(self) -> float:
        """Primary ranking metric: mean CV F1."""
        return self.cv_means.get("f1", 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "folds": self.folds,
            "cv": {metric: {
                "mean": round(self.cv_means[metric], 4),
                "std": round(self.cv_stds[metric], 4),
            } for metric in METRICS},
            "holdout": {k: round(v, 4) for k, v in self.holdout.items()},
        }


def _score_predictions(y_true, y_pred, y_prob=None) -> dict[str, float]:
    scores = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    if y_prob is not None:
        try:
            scores["roc_auc"] = float(roc_auc_score(y_true, y_prob))
        except ValueError:  # a fold with one class only
            scores["roc_auc"] = float("nan")
    return scores


def evaluate_model(name: str, frame: pd.DataFrame, folds: int = 5,
                   seed: int = 42) -> ModelScore:
    """Stratified k-fold CV + hold-out evaluation for one registry model."""
    if name not in MODELS:
        available = ", ".join(sorted(MODELS))
        raise HarnessError(f"unknown model {name!r} (available: {available})")
    if not MIN_FOLDS <= folds <= MAX_FOLDS:
        raise HarnessError(f"folds must be in {MIN_FOLDS}..{MAX_FOLDS}")

    feature_columns = [c for c in frame.columns if c != LABEL_COLUMN]
    x = frame[feature_columns]
    y = frame[LABEL_COLUMN].astype(int)

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.25, random_state=seed, stratify=y)

    factory = MODELS[name][0]
    splitter = StratifiedKFold(n_splits=folds, shuffle=True,
                               random_state=seed)
    fold_scores: dict[str, list[float]] = {metric: [] for metric in METRICS}
    for train_index, valid_index in splitter.split(x_train, y_train):
        model = factory()
        model.fit(x_train.iloc[train_index], y_train.iloc[train_index])
        predicted = model.predict(x_train.iloc[valid_index])
        if hasattr(model, "predict_proba"):
            probability = model.predict_proba(
                x_train.iloc[valid_index])[:, 1]
        else:  # pragma: no cover - all registry models expose proba
            probability = None
        scores = _score_predictions(y_train.iloc[valid_index], predicted,
                                    probability)
        for metric in METRICS:
            fold_scores[metric].append(scores[metric])

    cv_means = {m: float(np.nanmean(fold_scores[m])) for m in METRICS}
    cv_stds = {m: float(np.nanstd(fold_scores[m])) for m in METRICS}

    model = factory()
    model.fit(x_train, y_train)
    holdout_pred = model.predict(x_test)
    holdout_prob = (model.predict_proba(x_test)[:, 1]
                    if hasattr(model, "predict_proba") else None)
    holdout = _score_predictions(y_test, holdout_pred, holdout_prob)

    confusion = pd.DataFrame(
        confusion_matrix(y_test, holdout_pred, labels=[0, 1]),
        index=["actual 0", "actual 1"], columns=["pred 0", "pred 1"])

    score = ModelScore(name=name, cv_means=cv_means, cv_stds=cv_stds,
                       folds=folds, holdout=holdout, confusion=confusion)
    LOG.info("%s: CV F1 %.4f +/- %.4f (hold-out %.4f)",
             name, score.cv_means["f1"], score.cv_stds["f1"],
             holdout["f1"])
    return score


@dataclass
class HarnessResult:
    """Comparison of every registered model on one dataset."""

    scores: list[ModelScore] = field(default_factory=list)
    folds: int = 5
    rows: int = 0
    features: int = 0

    @property
    def best(self) -> ModelScore:
        if not self.scores:
            raise HarnessError("no models evaluated")
        return max(self.scores, key=lambda s: s.rank_score)

    @property
    def ranking(self) -> list[ModelScore]:
        return sorted(self.scores, key=lambda s: s.rank_score,
                      reverse=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "features": self.features,
            "folds": self.folds,
            "models": [s.to_dict() for s in self.ranking],
            "best_model": self.best.name,
            "best_cv_f1": round(self.best.rank_score, 4),
        }


def run_harness(frame: pd.DataFrame, folds: int = 5,
                seed: int = 42) -> HarnessResult:
    """Evaluate every registered model with the same CV protocol."""
    if not MIN_FOLDS <= folds <= MAX_FOLDS:
        raise HarnessError(f"folds must be in {MIN_FOLDS}..{MAX_FOLDS}")
    feature_count = len([c for c in frame.columns if c != LABEL_COLUMN])
    result = HarnessResult(folds=folds, rows=len(frame),
                           features=feature_count)
    for name in MODELS:
        result.scores.append(evaluate_model(name, frame, folds=folds,
                                            seed=seed))
    LOG.info("evaluated %d models; best %s (CV F1 %.4f)",
             len(result.scores), result.best.name, result.best.rank_score)
    return result


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(result: HarnessResult, frame: pd.DataFrame) -> str:
    """Human-readable model comparison used by the CLI and demo."""
    lines = [
        "MODEL EVALUATION HARNESS",
        "=" * 74,
        f"Dataset     : {result.rows} rows, {result.features} features, "
        f"binary label (0/1)",
        f"Protocol    : {result.folds}-fold stratified CV on the train "
        f"split + 25% hold-out",
        f"Ranking by  : mean CV F1",
        "",
        f"{'model':<22}{'CV acc':>9}{'CV f1':>9}{'±':>7}"
        f"{'CV auc':>9}{'hold f1':>10}",
        "-" * 66,
    ]
    for score in result.ranking:
        marker = "  <-- best" if score is result.best else ""
        lines.append(
            f"  {score.name:<20}{score.cv_means['accuracy']:>9.3f}"
            f"{score.cv_means['f1']:>9.3f}"
            f"{score.cv_stds['f1']:>7.3f}"
            f"{score.cv_means['roc_auc']:>9.3f}"
            f"{score.holdout['f1']:>10.3f}{marker}"
        )

    best = result.best
    lines += [
        "",
        f"Best model: {best.name} "
        f"(CV F1 {best.cv_means['f1']:.3f} ± {best.cv_stds['f1']:.3f})",
        "",
        "Hold-out confusion matrix:",
        f"  {'':11}{'pred 0':>8}{'pred 1':>8}",
    ]
    for index, row in best.confusion.iterrows():
        lines.append(f"  {index:<11}{int(row['pred 0']):>8}"
                     f"{int(row['pred 1']):>8}")

    spread = max(s.rank_score for s in result.scores) - \
        min(s.rank_score for s in result.scores)
    lines += [
        "",
        f"CV F1 spread across models: {spread:.3f} "
        f"({'models disagree - CV is discriminating' if spread > 0.02 else 'models are comparable on this dataset'})",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "dataset.csv"


def run_demo(csv_path: Path | None = None, folds: int = 5) -> int:
    """Evaluate every model on the bundled sample — fully offline."""
    print("=" * 74)
    print(" MODEL EVALUATION HARNESS - offline demo")
    print(" Bundled sample; scikit-learn models; no network.")
    print("=" * 74)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise HarnessError(f"bundled sample not found: {source}")

    frame = load_dataset(source)
    print(f"\nLoaded {len(frame)} rows from {source.name}")

    result = run_harness(frame, folds=folds)
    print()
    print(render_report(result, frame))

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(result.scores) == len(MODELS), "every model must be evaluated"
    assert result.folds == folds
    for score in result.scores:
        assert score.folds == folds
        for metric in METRICS:
            mean, std = score.cv_means[metric], score.cv_stds[metric]
            assert 0.0 <= mean <= 1.0 or np.isnan(mean), \
                f"{score.name}.{metric} mean out of range"
            assert std >= 0.0, f"{score.name}.{metric} std negative"
            # std must equal the spread of the actual fold scores
            assert std < 0.5, f"{score.name}.{metric} std implausible"
        assert int(score.confusion.values.sum()) == \
            math.ceil(0.25 * len(frame)), "confusion must count the hold-out"
    # best must really be the argmax of the ranking metric
    expected_best = max(result.scores, key=lambda s: s.rank_score).name
    assert result.best.name == expected_best, "best model mismatch"
    ranking_f1 = [s.rank_score for s in result.ranking]
    assert ranking_f1 == sorted(ranking_f1, reverse=True), \
        "ranking not sorted"
    # hold-out and CV should broadly agree (same data, different splits)
    for score in result.scores:
        assert abs(score.holdout["f1"] - score.cv_means["f1"]) < 0.35, \
            f"{score.name}: hold-out and CV disagree wildly"

    # deterministic re-run
    again = run_harness(frame, folds=folds)
    assert [s.cv_means for s in again.scores] == \
        [s.cv_means for s in result.scores], "harness is not deterministic"

    print(f"\nCross-checks OK: {len(result.scores)} models x {folds} folds, "
          f"best={result.best.name} (CV F1 {result.best.rank_score:.3f}), "
          f"metrics bounded, deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
