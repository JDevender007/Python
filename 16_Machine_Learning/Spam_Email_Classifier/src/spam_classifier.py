"""Spam email classifier: bag-of-words Naive Bayes - offline.

Loads a CSV of labelled messages (spam/ham), featurises subject+body with
a word/char n-gram bag-of-words, trains Multinomial Naive Bayes on a
stratified split, reports accuracy / precision / recall / F1 and a
confusion matrix, and classifies new messages with a spam probability.
Local files only - no network, no corpus downloads, no model artifacts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

LOG = logging.getLogger("spam")

REQUIRED_COLUMNS = ("label", "subject", "body")
LABELS = ("spam", "ham")
MIN_ROWS = 40
MIN_PER_CLASS = 10

# examples used by the demo and the CLI's default classify mode
SAMPLE_SPAM = ("Congratulations! You are the lucky WINNER. Click now to "
               "claim your FREE cash prize before it expires!")
SAMPLE_HAM = ("Hi team, here are the notes from todays meeting. Please "
              "review the agenda before the Thursday sync. Thanks!")


class SpamError(RuntimeError):
    """Raised for missing files, bad schemas, and training failures."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_messages(path: str | Path) -> pd.DataFrame:
    """Load the message CSV, validate it, and return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise SpamError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise SpamError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SpamError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise SpamError(f"no rows in {source.name}")

    frame = frame.copy()
    frame["label"] = (frame["label"].astype(str).str.strip().str.lower())
    unknown = sorted(set(frame["label"]) - set(LABELS))
    if unknown:
        raise SpamError(
            f"unknown label(s): {', '.join(unknown)} "
            f"(expected {', '.join(LABELS)})"
        )

    for column in ("subject", "body"):
        values = frame[column].fillna("").astype(str).str.strip()
        if values.eq("").any():
            raise SpamError(f"empty {column!r} value(s) in "
                            f"{int(values.eq('').sum())} row(s)")
        frame[column] = values

    if len(frame) < MIN_ROWS:
        raise SpamError(f"need at least {MIN_ROWS} messages, got {len(frame)}")
    counts = frame["label"].value_counts()
    sparse = [label for label in LABELS
              if counts.get(label, 0) < MIN_PER_CLASS]
    if sparse:
        raise SpamError(
            f"label(s) with too few messages (need >= {MIN_PER_CLASS}): "
            f"{', '.join(sparse)}"
        )

    frame = frame.sample(frac=1, random_state=11).reset_index(drop=True)
    LOG.info("loaded %d messages (%s) from %s",
             len(frame), dict(counts), source.name)
    return frame


def message_text(row: pd.Series | dict) -> str:
    """Subject + body as one document (subject repeated via separator)."""
    return f"{row['subject']} {row['subject']} {row['body']}"


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
@dataclass
class SpamResult:
    """Trained pipeline plus hold-out metrics and predictions."""

    model: Pipeline
    accuracy: float
    precision: float
    recall: float
    f1: float
    confusion: pd.DataFrame
    report_text: str
    test_labels: pd.Series = field(default_factory=pd.Series)
    test_pred: pd.Series = field(default_factory=pd.Series)
    vocabulary_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "holdout": {
                "accuracy": round(self.accuracy, 4),
                "precision_spam": round(self.precision, 4),
                "recall_spam": round(self.recall, 4),
                "f1": round(self.f1, 4),
            },
            "vocabulary_size": self.vocabulary_size,
            "confusion_matrix": {
                str(true): {str(pred): int(count)
                            for pred, count in row.items()}
                for true, row in self.confusion.to_dict("index").items()
            },
        }


def build_pipeline() -> Pipeline:
    """Bag-of-words (unigrams + bigrams) + Multinomial Naive Bayes."""
    return Pipeline([
        ("vectorize", CountVectorizer(
            lowercase=True,
            stop_words="english",      # bundled with scikit-learn
            ngram_range=(1, 2),
            min_df=1,
            max_features=4000,
        )),
        ("classify", MultinomialNB(alpha=1.0)),
    ])


def train_model(frame: pd.DataFrame, test_size: float = 0.25,
                seed: int = 42) -> SpamResult:
    """Train on a validated frame and score on a stratified hold-out."""
    if not 0.05 <= test_size <= 0.5:
        raise SpamError("test_size must be in 0.05..0.5")

    documents = frame.apply(message_text, axis=1)
    x_train, x_test, y_train, y_test = train_test_split(
        documents, frame["label"], test_size=test_size,
        random_state=seed, stratify=frame["label"])

    model = build_pipeline()
    model.fit(x_train, y_train)
    predicted = pd.Series(model.predict(x_test), index=y_test.index,
                          name="predicted")

    # spam is the positive class
    accuracy = float(accuracy_score(y_test, predicted))
    precision = float(precision_score(y_test, predicted, pos_label="spam"))
    recall = float(recall_score(y_test, predicted, pos_label="spam"))
    f1 = float(f1_score(y_test, predicted, pos_label="spam"))

    labels = ["spam", "ham"]
    confusion = pd.DataFrame(
        confusion_matrix(y_test, predicted, labels=labels),
        index=labels, columns=labels)
    report_text = classification_report(y_test, predicted, digits=3)

    vocabulary = model.named_steps["vectorize"].vocabulary_
    result = SpamResult(
        model=model, accuracy=accuracy, precision=precision,
        recall=recall, f1=f1, confusion=confusion,
        report_text=report_text, test_labels=y_test, test_pred=predicted,
        vocabulary_size=len(vocabulary),
    )
    LOG.info("trained: hold-out accuracy %.3f (vocab %d)",
             accuracy, result.vocabulary_size)
    return result


def classify(result: SpamResult, text: str) -> tuple[str, float]:
    """Return (label, spam probability) for one message."""
    if not isinstance(text, str) or not text.strip():
        raise SpamError("message must be a non-empty string")
    if len(text) > 20_000:
        raise SpamError("message too long (20 000 characters max)")
    cleaned = re.sub(r"\s+", " ", text).strip()
    probability = float(
        result.model.predict_proba([cleaned])[0][
            list(result.model.classes_).index("spam")])
    label = "spam" if probability >= 0.5 else "ham"
    return label, probability


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(result: SpamResult, frame: pd.DataFrame) -> str:
    """Human-readable training/evaluation report used by the CLI and demo."""
    counts = frame["label"].value_counts()
    lines = [
        "SPAM EMAIL CLASSIFIER (bag-of-words + Naive Bayes)",
        "=" * 66,
        f"Messages    : {len(frame)}  "
        f"(spam {counts.get('spam', 0)}, ham {counts.get('ham', 0)})",
        f"Vocabulary  : {result.vocabulary_size} features "
        f"(unigrams + bigrams, English stop words removed)",
        f"Hold-out    : accuracy {result.accuracy:.3f}  "
        f"precision {result.precision:.3f}  "
        f"recall {result.recall:.3f}  F1 {result.f1:.3f}",
        "",
        "Confusion matrix (rows = actual, cols = predicted):",
        f"  {'':8}{'pred spam':>10}{'pred ham':>10}",
    ]
    for true, row in result.confusion.iterrows():
        lines.append(f"  {true:<8}{int(row['spam']):>10}{int(row['ham']):>10}")

    lines += ["", "Per-class metrics:"]
    for line in result.report_text.rstrip().splitlines():
        lines.append(f"  {line}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "messages.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Train and evaluate on the bundled message sample - fully offline."""
    print("=" * 66)
    print(" SPAM EMAIL CLASSIFIER - offline demo")
    print(" Bundled labelled messages; scikit-learn; no network.")
    print("=" * 66)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise SpamError(f"bundled sample not found: {source}")

    frame = load_messages(source)
    print(f"\nLoaded {len(frame)} messages from {source.name}")

    result = train_model(frame)
    print()
    print(render_report(result, frame))

    spam_label, spam_prob = classify(result, SAMPLE_SPAM)
    ham_label, ham_prob = classify(result, SAMPLE_HAM)

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(result.test_labels) == len(result.test_pred), \
        "prediction lengths differ"
    assert int(result.confusion.values.sum()) == len(result.test_labels), \
        "confusion matrix must count every test row"
    recomputed = float((result.test_labels == result.test_pred).mean())
    assert abs(result.accuracy - recomputed) < 1e-12, "accuracy mismatch"
    assert result.accuracy >= 0.9, "hold-out accuracy unexpectedly low"
    for value in (result.precision, result.recall, result.f1):
        assert 0.0 <= value <= 1.0, "metric out of range"
    # the model must separate obvious examples
    assert spam_label == "spam" and spam_prob >= 0.5, \
        f"spammy text classified as {spam_label} ({spam_prob:.2f})"
    assert ham_label == "ham" and ham_prob < 0.5, \
        f"hammy text classified as {ham_label} ({ham_prob:.2f})"
    assert spam_prob > ham_prob, "probabilities do not separate the classes"
    # deterministic re-run
    again = train_model(frame)
    assert again.accuracy == result.accuracy, "training is not deterministic"
    assert (again.test_pred == result.test_pred).all(), "labels changed"

    print(f"\nSample classifications:")
    print(f"  SPAM? {spam_prob:>6.1%}  {spam_label:<5}  "
          f"\"{SAMPLE_SPAM[:52]}...\"")
    print(f"  SPAM? {ham_prob:>6.1%}  {ham_label:<5}  "
          f"\"{SAMPLE_HAM[:52]}...\"")
    print(f"\nCross-checks OK: accuracy {result.accuracy:.3f} matches the "
          f"test split, confusion matrix counts {len(result.test_labels)} "
          f"rows, sample messages labelled correctly, deterministic re-run")
    print("Demo completed successfully.")
    return 0
