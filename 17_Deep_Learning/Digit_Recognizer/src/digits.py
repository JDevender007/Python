"""Digit recognizer: a PyTorch MLP on 8x8 handwritten digits - offline.

Loads a local CSV of flattened 8x8 digit images (64 pixel columns, 0-16
greyscale, labels 0-9), trains a small fully-connected network with
Adam + cross-entropy, and reports hold-out accuracy, per-class metrics,
a confusion matrix, and ASCII previews of test digits. Local files only
- no network, no dataset downloads, no model artifacts fetched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn

LOG = logging.getLogger("digits")

PIXELS = tuple(f"pixel_{i}" for i in range(64))
REQUIRED_COLUMNS = PIXELS + ("label",)
CLASSES = tuple(range(10))
MIN_ROWS = 100
MIN_PER_CLASS = 5
PIXEL_MAX = 16.0
SHADES = " .:-=+*#%@"          # ASCII ramp for 8x8 previews


class DigitError(RuntimeError):
    """Raised for missing files, bad schemas, and training failures."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_digits_data(path: str | Path) -> pd.DataFrame:
    """Load the digits CSV, validate it, and return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise DigitError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise DigitError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise DigitError(
            f"missing column(s): {', '.join(missing[:4])}"
            f"{' ...' if len(missing) > 4 else ''} "
            f"(expected pixel_0..pixel_63 + label)"
        )
    if frame.empty:
        raise DigitError(f"no rows in {source.name}")

    frame = frame.copy()
    for column in PIXELS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise DigitError(f"column {column!r} contains non-numeric values")
        if not np.isfinite(frame[column]).all():
            raise DigitError(f"column {column!r} must be finite")
        if not frame[column].between(0, PIXEL_MAX).all():
            raise DigitError(
                f"column {column!r} outside 0..{PIXEL_MAX:g} "
                f"(8-bit greyscale scaled 0..16)")

    frame["label"] = pd.to_numeric(frame["label"], errors="coerce")
    if frame["label"].isna().any():
        raise DigitError("column 'label' contains non-numeric values")
    if not (frame["label"] % 1 == 0).all():
        raise DigitError("column 'label' must be whole numbers")
    labels = sorted(int(v) for v in frame["label"].unique())
    if not set(labels) <= set(CLASSES):
        raise DigitError(f"label must be 0..9 (got {labels})")
    if len(frame) < MIN_ROWS:
        raise DigitError(f"need at least {MIN_ROWS} rows, got {len(frame)}")
    counts = frame["label"].value_counts()
    sparse = [c for c in CLASSES if counts.get(c, 0) < MIN_PER_CLASS]
    if sparse:
        raise DigitError(
            f"class(es) with too few samples (need >= {MIN_PER_CLASS}): "
            f"{', '.join(str(c) for c in sparse)}"
        )

    frame["label"] = frame["label"].astype(int)
    frame = frame.sample(frac=1, random_state=13).reset_index(drop=True)
    LOG.info("loaded %d digit images from %s", len(frame), source.name)
    return frame


def to_tensor(frame: pd.DataFrame) -> tuple[torch.Tensor, torch.Tensor]:
    """Pixels scaled to [0,1] plus integer labels."""
    x = torch.tensor(frame[list(PIXELS)].to_numpy(dtype=np.float32)
                     / PIXEL_MAX, dtype=torch.float32)
    y = torch.tensor(frame["label"].to_numpy(dtype=np.int64),
                     dtype=torch.long)
    return x, y


# --------------------------------------------------------------------------- #
# The network
# --------------------------------------------------------------------------- #
class DigitNet(nn.Module):
    """64 -> hidden... -> 10 fully-connected classifier."""

    def __init__(self, hidden: tuple[int, ...] = (128, 64)) -> None:
        super().__init__()
        if not hidden or any(h < 1 for h in hidden):
            raise DigitError("hidden must be a non-empty tuple of sizes")
        sizes = [64, *hidden, 10]
        layers: list[nn.Module] = []
        for fan_in, fan_out in zip(sizes[:-1], sizes[1:-1]):
            layers += [nn.Linear(fan_in, fan_out), nn.ReLU()]
        layers.append(nn.Linear(sizes[-2], sizes[-1]))
        self.net = nn.Sequential(*layers)
        self.sizes = list(sizes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def build_model(hidden: tuple[int, ...] = (128, 64),
                seed: int = 42) -> DigitNet:
    """Seeded construction so initial weights are reproducible."""
    torch.manual_seed(seed)
    model = DigitNet(hidden)
    model.eval()  # no dropout/batchnorm present; kept for clarity
    return model


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
@dataclass
class DigitResult:
    """Trained model plus hold-out metrics and confusion matrix."""

    model: DigitNet
    history: list[dict[str, float]]
    test_accuracy: float
    train_accuracy: float
    confusion: pd.DataFrame
    per_class: pd.DataFrame
    misclassified: list[tuple[int, int, int]] = field(default_factory=list)
    train_rows: int = 0
    test_rows: int = 0
    rows: int = 0

    def predict(self, pixels: np.ndarray) -> tuple[int, float]:
        """Classify one 64-value image -> (label, confidence)."""
        values = np.asarray(pixels, dtype=np.float32).ravel()
        if values.size != 64:
            raise DigitError(
                f"expected 64 pixel values, got {values.size}")
        if not np.isfinite(values).all():
            raise DigitError("pixel values must be finite")
        if values.min() < 0 or values.max() > PIXEL_MAX:
            raise DigitError(
                f"pixel values must be in 0..{PIXEL_MAX:g}")
        with torch.no_grad():
            logits = self.model(
                torch.tensor(values / PIXEL_MAX).unsqueeze(0))
            probs = torch.softmax(logits, dim=1)[0]
        index = int(torch.argmax(probs))
        return index, float(probs[index])

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "train_rows": self.train_rows,
            "test_rows": self.test_rows,
            "epochs": len(self.history),
            "train_accuracy": round(self.train_accuracy, 4),
            "test_accuracy": round(self.test_accuracy, 4),
            "per_class_recall": {
                str(int(row["label"])): round(float(row["recall"]), 4)
                for _, row in self.per_class.iterrows()
            },
            "confusion_matrix": {
                str(int(true)): {str(int(pred)): int(count)
                                 for pred, count in row.items()}
                for true, row in self.confusion.to_dict("index").items()
            },
            "misclassified": len(self.misclassified),
        }


def _stratified_split(frame: pd.DataFrame, test_fraction: float,
                      seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    trains, tests = [], []
    for label in CLASSES:
        group = frame[frame["label"] == label].reset_index(drop=True)
        perm = rng.permutation(len(group))
        cut = int(round(len(group) * test_fraction))
        trains.append(group.iloc[perm[cut:]])
        tests.append(group.iloc[perm[:cut]])
    train = pd.concat(trains).sample(frac=1, random_state=seed).reset_index(
        drop=True)
    test = pd.concat(tests).sample(frac=1, random_state=seed).reset_index(
        drop=True)
    return train, test


def train_model(frame: pd.DataFrame, epochs: int = 12, lr: float = 1e-3,
                batch_size: int = 64, hidden: tuple[int, ...] = (128, 64),
                seed: int = 42, test_fraction: float = 0.25) -> DigitResult:
    """Stratified split + Adam training + hold-out evaluation."""
    if not 0.05 <= test_fraction <= 0.5:
        raise DigitError("test_fraction must be in 0.05..0.5")
    if epochs < 1:
        raise DigitError(f"epochs must be >= 1, got {epochs}")
    if not np.isfinite(lr) or lr <= 0:
        raise DigitError(f"lr must be > 0, got {lr}")
    if batch_size < 1:
        raise DigitError(f"batch_size must be >= 1, got {batch_size}")

    train, test = _stratified_split(frame, test_fraction, seed)
    x_train, y_train = to_tensor(train)
    x_test, y_test = to_tensor(test)

    model = build_model(hidden=hidden, seed=seed)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    generator = torch.Generator().manual_seed(seed)

    history: list[dict[str, float]] = []
    model.train()
    for epoch in range(epochs):
        order = torch.randperm(len(x_train), generator=generator)
        total_loss = 0.0
        for start in range(0, len(order), batch_size):
            idx = order[start:start + batch_size]
            optimizer.zero_grad()
            loss = criterion(model(x_train[idx]), y_train[idx])
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(idx)

        model.eval()
        with torch.no_grad():
            train_pred = model(x_train).argmax(dim=1)
            train_acc = float((train_pred == y_train).float().mean())
            test_pred = model(x_test).argmax(dim=1)
            test_acc = float((test_pred == y_test).float().mean())
        model.train()
        history.append({"epoch": epoch + 1,
                        "loss": total_loss / len(x_train),
                        "train_accuracy": train_acc,
                        "test_accuracy": test_acc})

    # ---------------------------------------------------------- evaluation
    model.eval()
    with torch.no_grad():
        train_pred = model(x_train).argmax(dim=1)
        test_pred = model(x_test).argmax(dim=1)
        train_acc = float((train_pred == y_train).float().mean())
        test_acc = float((test_pred == y_test).float().mean())

    true_np = y_test.numpy()
    pred_np = test_pred.numpy()
    matrix = np.zeros((10, 10), dtype=int)
    for t, p in zip(true_np, pred_np):
        matrix[int(t), int(p)] += 1
    confusion = pd.DataFrame(matrix, index=[str(c) for c in CLASSES],
                             columns=[str(c) for c in CLASSES])

    rows = []
    for label in CLASSES:
        tp = int(matrix[label, label])
        fn = int(matrix[label].sum() - tp)
        fp = int(matrix[:, label].sum() - tp)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        rows.append({"label": label, "precision": precision,
                     "recall": recall,
                     "support": int(matrix[label].sum())})
    per_class = pd.DataFrame(rows)

    mis = [(int(i), int(t), int(p))
           for i, (t, p) in enumerate(zip(true_np, pred_np)) if t != p]

    result = DigitResult(
        model=model, history=history, test_accuracy=test_acc,
        train_accuracy=train_acc, confusion=confusion,
        per_class=per_class, misclassified=mis,
        train_rows=len(train), test_rows=len(test), rows=len(frame))
    LOG.info("test accuracy %.3f (%d misclassified of %d)",
             test_acc, len(mis), len(test))
    return result


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def ascii_digit(pixels: np.ndarray) -> str:
    """Render one 64-value image as 8 lines of ASCII shade."""
    values = np.asarray(pixels, dtype=float).ravel()
    if values.size != 64:
        raise DigitError(f"expected 64 pixel values, got {values.size}")
    ramp = np.clip(np.round(values / PIXEL_MAX * (len(SHADES) - 1)),
                   0, len(SHADES) - 1).astype(int)
    art = ["".join(SHADES[v] for v in ramp[row * 8:(row + 1) * 8])
           for row in range(8)]
    return "\n".join(art)


def render_report(result: DigitResult, frame: pd.DataFrame) -> str:
    """Human-readable training/evaluation report used by the CLI and demo."""
    lines = [
        "DIGIT RECOGNIZER (PyTorch MLP on 8x8 digits)",
        "=" * 68,
        f"Dataset      : {result.rows} images "
        f"({result.train_rows} train / {result.test_rows} hold-out), "
        f"64 pixels, 10 classes",
        f"Network      : {' -> '.join(str(s) for s in result.model.sizes)} "
        f"(ReLU hidden, softmax output)",
        f"Training     : {len(result.history)} epochs, Adam",
        f"Final epoch  : loss {result.history[-1]['loss']:.4f}  "
        f"train acc {result.history[-1]['train_accuracy']:.3f}  "
        f"hold-out acc {result.history[-1]['test_accuracy']:.3f}",
        "",
        "Hold-out accuracy: "
        f"{result.test_accuracy:.3f}  "
        f"({len(result.misclassified)} misclassified "
        f"of {result.test_rows})",
        "",
        "Confusion matrix (rows = actual, cols = predicted):",
        "        " + "".join(f"{c:>4}" for c in CLASSES),
    ]
    for label, row in result.confusion.iterrows():
        cells = "".join(f"{int(v):>4}" for v in row)
        lines.append(f"   {label}   {cells}")

    lines += ["", "Per-class metrics:"]
    for _, row in result.per_class.iterrows():
        bar = "#" * int(round(row["recall"] * 20))
        lines.append(f"  class {int(row['label'])}: "
                     f"precision {row['precision']:.3f}  "
                     f"recall {row['recall']:.3f}  "
                     f"support {int(row['support']):>3}  {bar}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "digits.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Train on the bundled digits sample - fully offline."""
    print("=" * 68)
    print(" DIGIT RECOGNIZER - offline demo")
    print(" Bundled 8x8 digits; PyTorch on CPU; no network.")
    print("=" * 68)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise DigitError(f"bundled sample not found: {source}")

    frame = load_digits_data(source)
    print(f"\nLoaded {len(frame)} digit images from {source.name}")

    result = train_model(frame, epochs=12, lr=1e-3, batch_size=64)
    print()
    print(render_report(result, frame))

    # --- cross-checks the demo asserts ----------------------------------- #
    assert result.test_accuracy > 0.90, "hold-out accuracy too low"
    assert int(result.confusion.values.sum()) == result.test_rows, \
        "confusion must count every hold-out row"
    assert list(result.confusion.index) == [str(c) for c in CLASSES]
    assert result.per_class["support"].sum() == result.test_rows
    assert result.per_class["recall"].min() > 0.6, "a class recall collapsed"
    assert result.per_class["recall"].mean() > 0.9, "mean recall too low"
    assert len(result.history) == 12

    # a fresh image must classify with a sane confidence
    sample_row = frame.iloc[0]
    label, confidence = result.predict(
        sample_row[list(PIXELS)].to_numpy(dtype=float))
    assert label in CLASSES and 0.1 <= confidence <= 1.0, \
        "prediction/confidence out of range"

    # ASCII art round-trips the right shape
    art = ascii_digit(sample_row[list(PIXELS)].to_numpy(dtype=float))
    assert len(art.splitlines()) == 8 and all(len(l) == 8
                                              for l in art.splitlines())

    # deterministic re-run: identical hold-out predictions
    again = train_model(frame, epochs=12, lr=1e-3, batch_size=64)
    assert again.test_accuracy == result.test_accuracy, "not deterministic"
    assert again.misclassified == result.misclassified, \
        "misclassified set changed between runs"

    print(f"\nSample digit classified as {label} "
          f"(confidence {confidence:.1%}):")
    for line in art.splitlines():
        print(f"  |{line}|")

    print(f"\nCross-checks OK: hold-out {result.test_accuracy:.3f}, "
          f"confusion counts {result.test_rows} rows, all class recalls "
          f"> 0.6, deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
