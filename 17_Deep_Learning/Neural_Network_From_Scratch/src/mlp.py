"""Neural network from scratch: a pure-NumPy multilayer perceptron.

Implements forward propagation, backpropagation, mini-batch gradient
descent, He/Xavier initialisation, and BCE loss entirely with NumPy -
no deep-learning framework. Trains on a bundled concentric-circle
dataset, reports hold-out metrics against a majority-class baseline,
and can gradient-check its own derivatives. Local files only - no
network, no dataset downloads, no model artifacts fetched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LOG = logging.getLogger("mlp")

REQUIRED_COLUMNS = ("x1", "x2", "label")
MIN_ROWS = 50
HIDDEN_ACTIVATIONS = ("relu", "tanh")
EPS = 1e-12  # clamps BCE away from log(0)


class MLPError(RuntimeError):
    """Raised for bad configurations, invalid data, and training failures."""


# --------------------------------------------------------------------------- #
# Activations
# --------------------------------------------------------------------------- #
def sigmoid(z: np.ndarray) -> np.ndarray:
    """Numerically stable logistic sigmoid."""
    return np.where(z >= 0,
                    1.0 / (1.0 + np.exp(-np.abs(z))),
                    np.exp(-np.abs(z)) / (1.0 + np.exp(-np.abs(z))))


def relu(z: np.ndarray) -> np.ndarray:
    return np.maximum(z, 0.0)


def tanh(z: np.ndarray) -> np.ndarray:
    return np.tanh(z)


ACTIVATIONS = {"relu": relu, "tanh": tanh}


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_data(path: str | Path) -> pd.DataFrame:
    """Load the 2-D dataset CSV, validate it, and return a clean frame."""
    source = Path(path)
    if not source.is_file():
        raise MLPError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise MLPError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise MLPError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise MLPError(f"no rows in {source.name}")

    frame = frame.copy()
    for column in REQUIRED_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise MLPError(f"column {column!r} contains non-numeric values")
        if not np.isfinite(frame[column]).all():
            raise MLPError(f"column {column!r} must be finite")

    labels = sorted(frame["label"].unique())
    if labels != [0, 1]:
        raise MLPError(f"label must be binary 0/1 (got {labels})")
    if len(frame) < MIN_ROWS:
        raise MLPError(f"need at least {MIN_ROWS} rows, got {len(frame)}")
    counts = frame["label"].value_counts()
    for label in (0, 1):
        if counts.get(label, 0) < 10:
            raise MLPError(
                f"label {label} has {int(counts.get(label, 0))} rows "
                f"(need >= 10)")

    frame = frame.sample(frac=1, random_state=7).reset_index(drop=True)
    LOG.info("loaded %d rows from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# The network
# --------------------------------------------------------------------------- #
class MLP:
    """Fully-connected network: sizes = [input, hidden..., output].

    The output layer is a single sigmoid trained with binary cross-
    entropy; hidden layers use 'relu' or 'tanh'.
    """

    def __init__(self, sizes: list[int], hidden_activation: str = "relu",
                 lr: float = 0.1, epochs: int = 300, batch_size: int = 32,
                 seed: int = 42) -> None:
        if not isinstance(sizes, (list, tuple)) or len(sizes) < 2:
            raise MLPError("sizes must be [input, hidden..., output], "
                           "at least 2 entries")
        if any(not isinstance(s, (int, np.integer)) or s < 1 for s in sizes):
            raise MLPError(f"layer sizes must be positive integers: {sizes}")
        if sizes[-1] != 1:
            raise MLPError("output layer must have size 1 (binary sigmoid)")
        if hidden_activation not in HIDDEN_ACTIVATIONS:
            raise MLPError(
                f"hidden_activation must be one of {HIDDEN_ACTIVATIONS}")
        if not np.isfinite(lr) or lr <= 0:
            raise MLPError(f"lr must be > 0, got {lr}")
        if epochs < 1:
            raise MLPError(f"epochs must be >= 1, got {epochs}")
        if batch_size < 1:
            raise MLPError(f"batch_size must be >= 1, got {batch_size}")

        self.sizes = [int(s) for s in sizes]
        self.hidden_activation = hidden_activation
        self.lr = float(lr)
        self.epochs = int(epochs)
        self.batch_size = int(batch_size)
        self.seed = int(seed)

        self.weights: list[np.ndarray] = []
        self.biases: list[np.ndarray] = []
        self.history: list[dict[str, float]] = []
        self.fitted_ = False

    # ----------------------------------------------------------------- init
    def _init_params(self, rng: np.random.Generator) -> None:
        """He init for relu layers, Xavier for tanh/sigmoid outputs."""
        self.weights, self.biases = [], []
        for i, (fan_in, fan_out) in enumerate(zip(self.sizes[:-1],
                                                  self.sizes[1:])):
            is_hidden = i < len(self.sizes) - 2
            if is_hidden and self.hidden_activation == "relu":
                scale = np.sqrt(2.0 / fan_in)          # He
            else:
                scale = np.sqrt(1.0 / fan_in)          # Xavier/Glorot-ish
            self.weights.append(
                rng.normal(0.0, scale, size=(fan_out, fan_in)))
            self.biases.append(np.zeros((fan_out, 1)))

    # -------------------------------------------------------------- forward
    def forward(self, x: np.ndarray
                ) -> tuple[np.ndarray, list[tuple[np.ndarray, np.ndarray]]]:
        """Return (prediction, cache) where cache holds (z, a) per layer."""
        if len(self.weights) != len(self.sizes) - 1:
            raise MLPError("model has no layer parameters: call fit() first")
        a = np.asarray(x, dtype=float).T          # (features, samples)
        cache: list[tuple[np.ndarray, np.ndarray]] = []
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            z = w @ a + b
            if i < len(self.weights) - 1:
                a = ACTIVATIONS[self.hidden_activation](z)
            else:
                a = sigmoid(z)
            cache.append((z, a))
        return a, cache

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """P(label=1) for each row of x (n_samples,)."""
        out, _ = self.forward(np.atleast_2d(x))
        return out.ravel()

    def predict(self, x: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """Hard 0/1 labels from a probability threshold."""
        return (self.predict_proba(x) >= threshold).astype(int)

    # ------------------------------------------------------------- backward
    def gradients(self, x: np.ndarray, y: np.ndarray
                  ) -> tuple[list[np.ndarray], list[np.ndarray], float]:
        """Backpropagate a batch: return (dW, db, mean BCE loss)."""
        x = np.atleast_2d(np.asarray(x, dtype=float))
        y = np.asarray(y, dtype=float).reshape(-1, 1)
        if x.shape[0] != y.shape[0]:
            raise MLPError("x and y must contain the same number of rows")

        out, cache = self.forward(x)          # out: (1, m)
        m = x.shape[0]
        target = y.T                          # (1, m) to match out
        loss = float(-np.mean(target * np.log(out + EPS)
                              + (1 - target) * np.log(1 - out + EPS)))

        # sigmoid + BCE collapse to (a - y)/m
        delta = (out - target) / m
        dW: list[np.ndarray] = []
        db: list[np.ndarray] = []
        for i in range(len(self.weights) - 1, -1, -1):
            a_prev = cache[i - 1][1] if i > 0 else x.T
            dW.append(delta @ a_prev.T)
            db.append(delta.sum(axis=1, keepdims=True))
            if i > 0:
                z_prev = cache[i - 1][0]
                grad = self.weights[i].T @ delta
                if self.hidden_activation == "relu":
                    grad = grad * (z_prev > 0)
                else:
                    grad = grad * (1 - np.tanh(z_prev) ** 2)
                delta = grad
        return dW[::-1], db[::-1], loss

    # ----------------------------------------------------------------- fit
    def fit(self, x: np.ndarray, y: np.ndarray,
            x_val: np.ndarray | None = None,
            y_val: np.ndarray | None = None) -> MLP:
        """Train with mini-batch gradient descent; returns self."""
        x = np.atleast_2d(np.asarray(x, dtype=float))
        y = np.asarray(y, dtype=float).reshape(-1)
        if x.shape[0] != y.shape[0]:
            raise MLPError("x and y must contain the same number of rows")
        if x.shape[1] != self.sizes[0]:
            raise MLPError(
                f"expected {self.sizes[0]} features, got {x.shape[1]}")
        if x.shape[0] < 2:
            raise MLPError("need at least 2 training rows")
        if not np.isfinite(x).all():
            raise MLPError("x contains non-finite values")
        if not set(np.unique(y)) <= {0.0, 1.0}:
            raise MLPError("y must be binary 0/1")

        rng = np.random.default_rng(self.seed)
        self._init_params(rng)
        self.history = []

        for _ in range(self.epochs):
            order = rng.permutation(x.shape[0])
            for start in range(0, len(order), self.batch_size):
                idx = order[start:start + self.batch_size]
                dW, db, _ = self.gradients(x[idx], y[idx])
                for j in range(len(self.weights)):
                    self.weights[j] -= self.lr * dW[j]
                    self.biases[j] -= self.lr * db[j]

            train_loss, train_acc = self._score(x, y)
            entry = {"loss": train_loss, "accuracy": train_acc}
            if x_val is not None:
                val_loss, val_acc = self._score(
                    np.atleast_2d(np.asarray(x_val, dtype=float)),
                    np.asarray(y_val, dtype=float).reshape(-1))
                entry.update({"val_loss": val_loss, "val_accuracy": val_acc})
            self.history.append(entry)

        self.fitted_ = True
        LOG.info("trained %s for %d epochs (final loss %.4f, acc %.3f)",
                 self.sizes, self.epochs, self.history[-1]["loss"],
                 self.history[-1]["accuracy"])
        return self

    def _score(self, x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
        out, _ = self.forward(x)
        p = out.ravel()
        target = np.asarray(y, dtype=float).ravel()
        loss = float(-np.mean(target * np.log(p + EPS)
                              + (1 - target) * np.log(1 - p + EPS)))
        acc = float(((p >= 0.5).astype(int)
                     == target.astype(int)).mean())
        return loss, acc

    def get_params(self) -> dict[str, Any]:
        return {
            "sizes": list(self.sizes),
            "hidden_activation": self.hidden_activation,
            "lr": self.lr,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "seed": self.seed,
        }


# --------------------------------------------------------------------------- #
# Gradient checking (proves the hand-derived backprop is correct)
# --------------------------------------------------------------------------- #
def gradient_check(hidden: tuple[int, ...] = (6,), samples: int = 4,
                   eps: float = 1e-5, seed: int = 3) -> float:
    """Max relative error between analytic and numerical gradients."""
    rng = np.random.default_rng(seed)
    sizes = [2, *hidden, 1]
    model = MLP(sizes, lr=0.1, epochs=1, seed=seed)
    model._init_params(rng)
    x = rng.normal(size=(samples, 2))
    y = (rng.uniform(size=samples) >= 0.5).astype(float)

    dW, db, _ = model.gradients(x, y)

    def loss_only() -> float:
        out, _ = model.forward(x)
        p = out.ravel()
        return float(-np.mean(y * np.log(p + EPS)
                              + (1 - y) * np.log(1 - p + EPS)))

    max_rel = 0.0
    for li in range(len(model.weights)):
        for arr, grad in ((model.weights[li], dW[li]),
                          (model.biases[li], db[li])):
            for idx in np.ndindex(arr.shape):
                original = arr[idx]
                arr[idx] = original + eps
                plus = loss_only()
                arr[idx] = original - eps
                minus = loss_only()
                arr[idx] = original
                numeric = (plus - minus) / (2 * eps)
                analytic = float(grad[idx])
                denom = max(abs(numeric), abs(analytic), 1e-8)
                max_rel = max(max_rel, abs(numeric - analytic) / denom)
    return max_rel


# --------------------------------------------------------------------------- #
# Training orchestration
# --------------------------------------------------------------------------- #
@dataclass
class TrainResult:
    """Fitted model, learning history, and hold-out metrics."""

    model: MLP
    history: list[dict[str, float]]
    train_accuracy: float
    test_accuracy: float
    baseline_accuracy: float
    rows: int = 0
    train_rows: int = 0
    test_rows: int = 0

    @property
    def final_loss(self) -> float:
        return self.history[-1]["loss"] if self.history else float("nan")

    def to_dict(self) -> dict[str, Any]:
        first, last = self.history[0], self.history[-1]
        return {
            "params": self.model.get_params(),
            "rows": self.rows,
            "train_rows": self.train_rows,
            "test_rows": self.test_rows,
            "epochs": len(self.history),
            "initial_loss": round(first["loss"], 4),
            "final_loss": round(last["loss"], 4),
            "train_accuracy": round(self.train_accuracy, 4),
            "test_accuracy": round(self.test_accuracy, 4),
            "baseline_accuracy": round(self.baseline_accuracy, 4),
        }


def _stratified_split(frame: pd.DataFrame, test_fraction: float,
                      seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Shuffle each class separately, hold out a slice of each."""
    parts = []
    rng = np.random.default_rng(seed)
    for label in (0, 1):
        group = frame[frame["label"] == label].reset_index(drop=True)
        perm = rng.permutation(len(group))
        cut = int(round(len(group) * test_fraction))
        parts.append((group.iloc[perm[cut:]], group.iloc[perm[:cut]]))
    train = pd.concat([p[0] for p in parts]).sample(
        frac=1, random_state=seed).reset_index(drop=True)
    test = pd.concat([p[1] for p in parts]).sample(
        frac=1, random_state=seed).reset_index(drop=True)
    return train, test


def train_model(frame: pd.DataFrame, hidden: tuple[int, ...] = (16, 16),
                lr: float = 0.1, epochs: int = 300, batch_size: int = 32,
                seed: int = 42, test_fraction: float = 0.25) -> TrainResult:
    """Validate, split, and train an MLP on a 2-D binary dataset."""
    if not 0.05 <= test_fraction <= 0.5:
        raise MLPError("test_fraction must be in 0.05..0.5")
    if len(frame) < MIN_ROWS:
        raise MLPError(f"need at least {MIN_ROWS} rows, got {len(frame)}")

    train, test = _stratified_split(frame, test_fraction, seed)
    x_train = train[["x1", "x2"]].to_numpy(dtype=float)
    y_train = train["label"].to_numpy(dtype=float)
    x_test = test[["x1", "x2"]].to_numpy(dtype=float)
    y_test = test["label"].to_numpy(dtype=float)

    model = MLP([2, *hidden, 1], hidden_activation="relu", lr=lr,
                epochs=epochs, batch_size=batch_size, seed=seed)
    model.fit(x_train, y_train, x_test, y_test)

    train_acc = float((model.predict(x_train) == y_train).mean())
    test_acc = float((model.predict(x_test) == y_test).mean())
    # honest baseline: always guess the majority class of the train split
    majority = int(np.mean(y_train) >= 0.5)
    baseline = float((y_test == majority).mean())

    result = TrainResult(
        model=model, history=model.history, train_accuracy=train_acc,
        test_accuracy=test_acc, baseline_accuracy=baseline,
        rows=len(frame), train_rows=len(train), test_rows=len(test))
    LOG.info("train acc %.3f, test acc %.3f (baseline %.3f)",
             train_acc, test_acc, baseline)
    return result


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(result: TrainResult) -> str:
    """Human-readable training report used by the CLI and demo."""
    params = result.model.get_params()
    lines = [
        "NEURAL NETWORK FROM SCRATCH (pure NumPy MLP)",
        "=" * 68,
        f"Architecture : {' -> '.join(str(s) for s in params['sizes'])} "
        f"(hidden: {params['hidden_activation']}, output: sigmoid)",
        f"Training     : {params['epochs']} epochs, "
        f"batch {params['batch_size']}, lr {params['lr']}, "
        f"seed {params['seed']}",
        f"Dataset      : {result.rows} rows "
        f"({result.train_rows} train / {result.test_rows} hold-out)",
        "",
        "Learning curve (loss / accuracy):",
        f"  {'epoch':>7}{'train loss':>13}{'train acc':>11}"
        f"{'val loss':>11}{'val acc':>10}",
    ]
    marks = {0, 1, len(result.history) // 2, len(result.history) - 2,
             len(result.history) - 1}
    for i, entry in enumerate(result.history):
        if i in marks:
            val_loss = entry.get("val_loss", float("nan"))
            val_acc = entry.get("val_accuracy", float("nan"))
            lines.append(f"  {i + 1:>7}{entry['loss']:>13.4f}"
                         f"{entry['accuracy']:>11.3f}"
                         f"{val_loss:>11.4f}{val_acc:>10.3f}")

    lines += [
        "",
        "Hold-out results:",
        f"  MLP accuracy        : {result.test_accuracy:.3f}",
        f"  Train accuracy      : {result.train_accuracy:.3f}",
        f"  Majority baseline   : {result.baseline_accuracy:.3f}",
        f"  Lift over baseline  : "
        f"{result.test_accuracy - result.baseline_accuracy:+.3f}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "dataset.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Train the MLP on the bundled circles sample - fully offline."""
    print("=" * 68)
    print(" NEURAL NETWORK FROM SCRATCH - offline demo")
    print(" Bundled sample; pure NumPy backprop; no network.")
    print("=" * 68)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise MLPError(f"bundled sample not found: {source}")

    frame = load_data(source)
    print(f"\nLoaded {len(frame)} rows from {source.name} "
          f"(concentric circles: a line cannot separate them)")

    result = train_model(frame, hidden=(16, 16), lr=0.1, epochs=300)
    print()
    print(render_report(result))

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(result.history) == 300, "history must have one entry/epoch"
    first, last = result.history[0], result.history[-1]
    assert last["loss"] < first["loss"] * 0.5, "loss did not fall enough"
    assert result.test_accuracy > 0.9, "hold-out accuracy too low"
    assert result.test_accuracy > result.baseline_accuracy + 0.3, \
        "model barely beats the majority baseline"
    assert 0.0 <= result.train_accuracy <= 1.0

    # the hand-derived gradients must match numerical differentiation
    error = gradient_check(hidden=(6,), samples=4)
    assert error < 1e-6, f"gradient check failed: {error:.2e}"

    # deterministic re-run
    again = train_model(frame, hidden=(16, 16), lr=0.1, epochs=300)
    assert again.test_accuracy == result.test_accuracy, "not deterministic"
    assert [h["loss"] for h in again.history] == \
        [h["loss"] for h in result.history], "history changed between runs"

    # probabilities are proper
    x_all = frame[["x1", "x2"]].to_numpy(dtype=float)
    probs = result.model.predict_proba(x_all)
    assert ((probs >= 0) & (probs <= 1)).all(), "probabilities out of [0,1]"

    print(f"\nCross-checks OK: hold-out {result.test_accuracy:.3f} vs "
          f"baseline {result.baseline_accuracy:.3f}, loss "
          f"{first['loss']:.3f} -> {last['loss']:.3f}, gradient check "
          f"{error:.1e}, deterministic re-run")
    print("Demo completed successfully.")
    return 0
