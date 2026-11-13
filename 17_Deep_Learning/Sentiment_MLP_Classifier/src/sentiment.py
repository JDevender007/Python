"""Sentiment MLP classifier: a PyTorch bag-of-words network - offline.

Loads labelled messages (text, 0/1) from a local CSV, featurises them
with a bag-of-words vocabulary built from the training split only,
trains a small fully-connected network with Adam + BCE, and reports
hold-out accuracy, precision/recall/F1, a confusion matrix, and
per-message probabilities. Local files only - no network, no dataset
downloads, no model artifacts fetched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.feature_extraction.text import CountVectorizer
from torch import nn

LOG = logging.getLogger("sentiment")

REQUIRED_COLUMNS = ("text", "label")
MIN_ROWS = 100
MIN_PER_CLASS = 20
MAX_VOCAB = 3000
MIN_TOKEN_LENGTH = 2


class SentimentError(RuntimeError):
    """Raised for missing files, bad schemas, and training failures."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_messages(path: str | Path) -> pd.DataFrame:
    """Load the messages CSV, validate it, and return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise SentimentError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise SentimentError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SentimentError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise SentimentError(f"no rows in {source.name}")

    frame = frame.copy()
    # empty CSV cells arrive as NaN; fillna keeps them "" instead of "nan"
    frame["text"] = frame["text"].fillna("").astype(str).str.strip()
    if (frame["text"] == "").all():
        raise SentimentError("column 'text' has no non-empty messages")
    empty = int((frame["text"] == "").sum())
    if empty:
        LOG.warning("dropped %d rows with empty text", empty)
        frame = frame[frame["text"] != ""]

    frame["label"] = pd.to_numeric(frame["label"], errors="coerce")
    if frame["label"].isna().any():
        raise SentimentError("column 'label' contains non-numeric values")
    if not (frame["label"] % 1 == 0).all():
        raise SentimentError("column 'label' must be whole numbers")
    labels = sorted(int(v) for v in frame["label"].unique())
    if labels != [0, 1]:
        raise SentimentError(f"label must be binary 0/1 (got {labels})")
    if len(frame) < MIN_ROWS:
        raise SentimentError(f"need at least {MIN_ROWS} rows, got {len(frame)}")
    counts = frame["label"].value_counts()
    for label in (0, 1):
        if counts.get(label, 0) < MIN_PER_CLASS:
            raise SentimentError(
                f"label {label} has {int(counts.get(label, 0))} rows "
                f"(need >= {MIN_PER_CLASS})"
            )

    frame["label"] = frame["label"].astype(int)
    frame = frame.sample(frac=1, random_state=11).reset_index(drop=True)
    LOG.info("loaded %d messages from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Featurisation and the network
# --------------------------------------------------------------------------- #
def build_vectorizer() -> CountVectorizer:
    """Bag-of-words (binary counts, unigrams) with no external corpora."""
    return CountVectorizer(
        max_features=MAX_VOCAB,
        binary=True,
        token_pattern=rf"(?u)\b\w{{{MIN_TOKEN_LENGTH},}}\b",
        lowercase=True,
    )


class SentimentMLP(nn.Module):
    """vocab -> hidden... -> 1 sigmoid sentiment score."""

    def __init__(self, vocab_size: int, hidden: tuple[int, ...] = (64, 32),
                 dropout: float = 0.1) -> None:
        super().__init__()
        if vocab_size < 1:
            raise SentimentError("vocab_size must be >= 1")
        if not hidden or any(h < 1 for h in hidden):
            raise SentimentError("hidden must be a non-empty tuple of sizes")
        if not 0.0 <= dropout < 1.0:
            raise SentimentError(f"dropout must be in [0, 1), got {dropout}")
        sizes = [vocab_size, *hidden, 1]
        layers: list[nn.Module] = []
        for fan_in, fan_out in zip(sizes[:-1], sizes[1:-1]):
            layers += [nn.Linear(fan_in, fan_out), nn.ReLU(),
                       nn.Dropout(dropout)]
        layers.append(nn.Linear(sizes[-2], sizes[-1]))
        self.net = nn.Sequential(*layers)
        self.sizes = list(sizes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)          # logits, (batch,)


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
@dataclass
class SentimentResult:
    """Trained model plus hold-out metrics and confusion matrix."""

    model: SentimentMLP
    vectorizer: CountVectorizer
    history: list[dict[str, float]]
    test_accuracy: float
    train_accuracy: float
    precision: float
    recall: float
    f1: float
    confusion: np.ndarray               # [[tn, fp], [fn, tp]]
    probabilities: np.ndarray = field(default_factory=lambda: np.zeros(0))
    test_texts: list[str] = field(default_factory=list)
    test_labels: np.ndarray = field(default_factory=lambda: np.zeros(0))
    rows: int = 0
    train_rows: int = 0
    test_rows: int = 0
    vocab_size: int = 0

    @property
    def final_loss(self) -> float:
        return self.history[-1]["loss"] if self.history else float("nan")

    def predict(self, text: str) -> tuple[int, float]:
        """Classify one message -> (label, P(positive))."""
        if not isinstance(text, str) or not text.strip():
            raise SentimentError("message must be a non-empty string")
        matrix = self.vectorizer.transform([text])
        features = torch.tensor(matrix.toarray().astype(np.float32))
        with torch.no_grad():
            logit = self.model(features)
            probability = torch.sigmoid(logit).item()
        return (1 if probability >= 0.5 else 0), float(probability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "train_rows": self.train_rows,
            "test_rows": self.test_rows,
            "vocab_size": self.vocab_size,
            "epochs": len(self.history),
            "train_accuracy": round(self.train_accuracy, 4),
            "test_accuracy": round(self.test_accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "confusion": {
                "tn": int(self.confusion[0, 0]),
                "fp": int(self.confusion[0, 1]),
                "fn": int(self.confusion[1, 0]),
                "tp": int(self.confusion[1, 1]),
            },
        }


def _metrics(y_true: np.ndarray, y_pred: np.ndarray
             ) -> tuple[float, float, float, float, np.ndarray]:
    """Accuracy, precision, recall, F1, and [[tn, fp], [fn, tp]]."""
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    accuracy = (tp + tn) / max(len(y_true), 1)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall else 0.0)
    matrix = np.array([[tn, fp], [fn, tp]], dtype=int)
    return accuracy, precision, recall, f1, matrix


def _stratified_split(frame: pd.DataFrame, test_fraction: float,
                      seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    trains, tests = [], []
    for label in (0, 1):
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


def train_model(frame: pd.DataFrame, epochs: int = 40, lr: float = 1e-3,
                batch_size: int = 32, hidden: tuple[int, ...] = (64, 32),
                dropout: float = 0.1, seed: int = 42,
                test_fraction: float = 0.25) -> SentimentResult:
    """Stratified split -> fit vectorizer on train -> MLP -> evaluation."""
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SentimentError(f"missing column(s): {', '.join(missing)}")
    if len(frame) < MIN_ROWS:
        raise SentimentError(f"need at least {MIN_ROWS} rows, got {len(frame)}")
    if epochs < 1:
        raise SentimentError(f"epochs must be >= 1, got {epochs}")
    if not np.isfinite(lr) or lr <= 0:
        raise SentimentError(f"lr must be > 0, got {lr}")
    if batch_size < 1:
        raise SentimentError(f"batch_size must be >= 1, got {batch_size}")
    if not 0.05 <= test_fraction <= 0.5:
        raise SentimentError("test_fraction must be in 0.05..0.5")

    train, test = _stratified_split(frame, test_fraction, seed)

    # vocabulary from the TRAIN split only (no leakage from hold-out)
    vectorizer = build_vectorizer()
    x_train = vectorizer.fit_transform(train["text"]).toarray().astype(
        np.float32)
    x_test = vectorizer.transform(test["text"]).toarray().astype(np.float32)
    vocab_size = x_train.shape[1]
    if vocab_size < 5:
        raise SentimentError(
            f"vocabulary too small ({vocab_size} tokens) - "
            "messages need at least 2 characters per token")

    y_train = train["label"].to_numpy(dtype=np.float32)
    y_test = test["label"].to_numpy(dtype=np.int64)

    torch.manual_seed(seed)
    model = SentimentMLP(vocab_size, hidden=hidden, dropout=dropout)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    generator = torch.Generator().manual_seed(seed)

    x_train_t = torch.tensor(x_train)
    y_train_t = torch.tensor(y_train)
    x_test_t = torch.tensor(x_test)

    history: list[dict[str, float]] = []
    model.train()
    for _ in range(epochs):
        order = torch.randperm(len(x_train_t), generator=generator)
        total = 0.0
        for start in range(0, len(order), batch_size):
            idx = order[start:start + batch_size]
            optimizer.zero_grad()
            loss = criterion(model(x_train_t[idx]), y_train_t[idx])
            loss.backward()
            optimizer.step()
            total += float(loss.detach()) * len(idx)

        model.eval()
        with torch.no_grad():
            val_loss = float(criterion(
                model(x_test_t), torch.tensor(y_test.astype(np.float32))))
        model.train()
        history.append({"loss": total / len(x_train_t), "val_loss": val_loss})

    # ---------------------------------------------------------- evaluation
    model.eval()
    with torch.no_grad():
        train_prob = torch.sigmoid(model(x_train_t)).numpy()
        test_prob = torch.sigmoid(model(x_test_t)).numpy()
    train_pred = (train_prob >= 0.5).astype(int)
    test_pred = (test_prob >= 0.5).astype(int)

    train_accuracy = float((train_pred == y_train.astype(int)).mean())
    accuracy, precision, recall, f1, confusion = _metrics(y_test, test_pred)

    result = SentimentResult(
        model=model, vectorizer=vectorizer, history=history,
        test_accuracy=accuracy, train_accuracy=train_accuracy,
        precision=precision, recall=recall, f1=f1, confusion=confusion,
        probabilities=test_prob, test_texts=test["text"].tolist(),
        test_labels=y_test, rows=len(frame), train_rows=len(train),
        test_rows=len(test), vocab_size=vocab_size)
    LOG.info("hold-out accuracy %.3f (f1 %.3f), vocab %d tokens",
             accuracy, f1, vocab_size)
    return result


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(result: SentimentResult) -> str:
    """Human-readable evaluation report used by the CLI and demo."""
    tn, fp, fn, tp = (int(result.confusion[0, 0]), int(result.confusion[0, 1]),
                      int(result.confusion[1, 0]), int(result.confusion[1, 1]))
    lines = [
        "SENTIMENT MLP CLASSIFIER (bag-of-words + PyTorch MLP)",
        "=" * 68,
        f"Dataset     : {result.rows} messages "
        f"({result.train_rows} train / {result.test_rows} hold-out)",
        f"Features    : binary bag-of-words, {result.vocab_size} tokens "
        f"(vocabulary fit on train only)",
        f"Network     : {' -> '.join(str(s) for s in result.model.sizes)} "
        f"(ReLU + dropout, sigmoid output)",
        f"Training    : {len(result.history)} epochs, Adam, BCE-with-logits",
        "",
        "Learning curve (BCE loss):",
        f"  {'epoch':>7}{'train loss':>13}{'val loss':>12}",
    ]
    marks = {0, 1, len(result.history) // 2, len(result.history) - 1}
    for i, entry in enumerate(result.history):
        if i in marks:
            lines.append(f"  {i + 1:>7}{entry['loss']:>13.5f}"
                         f"{entry['val_loss']:>12.5f}")

    lines += [
        "",
        "Hold-out results:",
        f"  accuracy  {result.test_accuracy:.3f}    "
        f"precision {result.precision:.3f}    "
        f"recall {result.recall:.3f}    f1 {result.f1:.3f}",
        f"  train accuracy {result.train_accuracy:.3f}",
        "",
        "Confusion matrix (rows = actual, cols = predicted):",
        "              pred 0  pred 1",
        f"   actual 0     {tn:>4}   {fp:>4}",
        f"   actual 1     {fn:>4}   {tp:>4}",
        "",
        "Most confident hold-out predictions:",
    ]
    order = np.argsort(-np.abs(result.probabilities - 0.5))[:3]
    for index in order:
        label = int(result.test_labels[index])
        probability = float(result.probabilities[index])
        text = result.test_texts[index]
        snippet = text if len(text) <= 44 else text[:41] + "..."
        lines.append(f"  [{label}] p={probability:.3f}  {snippet!r}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "messages.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Train on the bundled messages sample - fully offline."""
    print("=" * 68)
    print(" SENTIMENT MLP CLASSIFIER - offline demo")
    print(" Bundled labelled messages; bag-of-words + PyTorch; no network.")
    print("=" * 68)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise SentimentError(f"bundled sample not found: {source}")

    frame = load_messages(source)
    print(f"\nLoaded {len(frame)} messages from {source.name} "
          f"(positive/negative reviews)")

    result = train_model(frame, epochs=40, lr=1e-3, batch_size=32)
    print()
    print(render_report(result))

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(result.history) == 40, "history must have one entry/epoch"
    first, last = result.history[0], result.history[-1]
    assert last["loss"] < first["loss"] * 0.5, "training loss did not fall"
    assert result.test_accuracy > 0.85, "hold-out accuracy too low"
    assert result.f1 > 0.85, "hold-out F1 too low"
    assert int(result.confusion.sum()) == result.test_rows, \
        "confusion must count every hold-out row"
    assert 0.0 <= result.precision <= 1.0 and 0.0 <= result.recall <= 1.0
    assert result.vocab_size >= 50, "vocabulary unexpectedly small"

    # per-message API agrees with the hold-out probabilities
    label, probability = result.predict(result.test_texts[0])
    assert label in (0, 1) and 0.0 <= probability <= 1.0
    expected = 1 if result.probabilities[0] >= 0.5 else 0
    assert label == expected, "predict() disagrees with hold-out output"

    # obvious phrases classify the right way
    good, p_good = result.predict("i love this wonderful great movie")
    bad, p_bad = result.predict("i hate this terrible awful movie")
    assert good == 1 and bad == 0, "sentiment direction is wrong"
    assert p_good > p_bad, "positive phrase scored below negative one"

    # deterministic re-run
    again = train_model(frame, epochs=40, lr=1e-3, batch_size=32)
    assert again.test_accuracy == result.test_accuracy, "not deterministic"
    assert [h["loss"] for h in again.history] == \
        [h["loss"] for h in result.history], "history changed between runs"

    print(f"\nPhrase check: 'love/wonderful' p={p_good:.3f} vs "
          f"'hate/terrible' p={p_bad:.3f}")
    print(f"\nCross-checks OK: hold-out {result.test_accuracy:.3f}, "
          f"F1 {result.f1:.3f}, confusion counts {result.test_rows} rows, "
          f"vocab {result.vocab_size}, deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
