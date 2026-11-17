"""Tests for the Sentiment MLP Classifier project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sentiment import (  # noqa: E402
    DEMO_CSV,
    MIN_PER_CLASS,
    MIN_ROWS,
    REQUIRED_COLUMNS,
    SentimentError,
    SentimentMLP,
    build_vectorizer,
    load_messages,
    render_report,
    run_demo,
    train_model,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _grid(n: int = 120) -> pd.DataFrame:
    """n valid rows, both labels, non-empty texts."""
    rows = []
    for i in range(n):
        label = i % 2
        word = "love great" if label else "hate terrible"
        rows.append([f"message {i} {word} service product", label])
    return pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS))


def _csv(tmp_path: Path, frame: pd.DataFrame,
         name: str = "messages.csv") -> Path:
    path = tmp_path / name
    frame.to_csv(path, index=False)
    return path


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_messages(DEMO_CSV)


@pytest.fixture(scope="module")
def trained(sample):
    # 25 epochs keeps the suite fast; the demo covers full convergence
    return train_model(sample, epochs=25)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 500
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    counts = sample["label"].value_counts()
    assert counts[0] == 250 and counts[1] == 250
    assert (sample["text"].str.len() > 0).all()


def test_load_missing_file(tmp_path):
    with pytest.raises(SentimentError, match="not found"):
        load_messages(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("message,label\nhi,1\n", encoding="utf-8")
    with pytest.raises(SentimentError, match="missing column"):
        load_messages(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("text,label\n", encoding="utf-8")
    with pytest.raises(SentimentError, match="no rows"):
        load_messages(path)


def test_load_all_empty_text(tmp_path):
    path = tmp_path / "blank.csv"
    path.write_text("text,label\n,1\n,0\n", encoding="utf-8")
    with pytest.raises(SentimentError, match="no non-empty"):
        load_messages(path)


def test_load_non_numeric_label(tmp_path):
    frame = _grid()
    frame["label"] = frame["label"].astype(object)
    frame.loc[0, "label"] = "positive"
    with pytest.raises(SentimentError, match="'label' contains non-numeric"):
        load_messages(_csv(tmp_path, frame))


def test_load_fractional_label(tmp_path):
    frame = _grid()
    frame["label"] = frame["label"].astype(float)
    frame.loc[0, "label"] = 0.5
    with pytest.raises(SentimentError, match="whole numbers"):
        load_messages(_csv(tmp_path, frame))


def test_load_non_binary_label(tmp_path):
    frame = _grid()
    frame.loc[0, "label"] = 2
    with pytest.raises(SentimentError, match="binary 0/1"):
        load_messages(_csv(tmp_path, frame))


def test_load_too_few_rows(tmp_path):
    with pytest.raises(SentimentError, match=f"at least {MIN_ROWS}"):
        load_messages(_csv(tmp_path, _grid(40)))


def test_load_missing_class(tmp_path):
    frame = _grid()
    frame["label"] = 1
    # the binary 0/1 check fires before the per-class count check
    with pytest.raises(SentimentError, match="binary 0/1"):
        load_messages(_csv(tmp_path, frame))


def test_load_sparse_class(tmp_path):
    frame = _grid(200)
    frame = frame[frame["label"] == 1]  # 100 rows of label 1 only
    with pytest.raises(SentimentError, match="binary 0/1"):
        load_messages(_csv(tmp_path, frame))


def test_load_drops_empty_rows(tmp_path):
    frame = _grid(120)
    frame = pd.concat([frame, pd.DataFrame(
        [{"text": "   ", "label": 1}, {"text": "", "label": 0}])],
        ignore_index=True)
    loaded = load_messages(_csv(tmp_path, frame))
    assert len(loaded) == 120
    assert (loaded["text"].str.len() > 0).all()


# --------------------------------------------------------------------------- #
# Model and featurisation
# --------------------------------------------------------------------------- #
def test_vectorizer_binary_bow():
    vectorizer = build_vectorizer()
    matrix = vectorizer.fit_transform(["good good movie", "bad film"])
    assert matrix.shape[0] == 2
    # binary=True: repeated tokens count once
    assert matrix[0, vectorizer.vocabulary_["good"]] == 1
    assert "movie" in vectorizer.vocabulary_


def test_model_output_shape():
    model = SentimentMLP(50, hidden=(16,), dropout=0.0)
    out = model(torch.zeros(7, 50))
    assert out.shape == (7,)


def test_model_rejects_bad_config():
    with pytest.raises(SentimentError, match="vocab_size"):
        SentimentMLP(0)
    with pytest.raises(SentimentError, match="hidden"):
        SentimentMLP(10, hidden=())
    with pytest.raises(SentimentError, match="dropout"):
        SentimentMLP(10, dropout=1.5)


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
def test_train_valid_metrics(trained):
    assert 0.0 <= trained.test_accuracy <= 1.0
    assert 0.0 <= trained.train_accuracy <= 1.0
    assert 0.0 <= trained.precision <= 1.0
    assert 0.0 <= trained.recall <= 1.0
    assert 0.0 <= trained.f1 <= 1.0
    assert trained.rows == 500
    assert trained.train_rows == 376 and trained.test_rows == 124
    assert trained.train_rows + trained.test_rows == trained.rows
    assert len(trained.history) == 25


def test_confusion_counts_test_rows(trained):
    assert int(trained.confusion.sum()) == trained.test_rows
    tn, fp, fn, tp = trained.confusion.ravel()
    assert tn + fp == trained.test_rows // 2  # 62 negatives
    assert fn + tp == trained.test_rows - trained.test_rows // 2


def test_metrics_consistent_with_confusion(trained):
    tn, fp, fn, tp = trained.confusion.ravel()
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    accuracy = (tp + tn) / trained.test_rows
    assert trained.precision == pytest.approx(precision)
    assert trained.recall == pytest.approx(recall)
    assert trained.test_accuracy == pytest.approx(accuracy)
    if precision + recall:
        expected_f1 = 2 * precision * recall / (precision + recall)
        assert trained.f1 == pytest.approx(expected_f1)


def test_vocabulary_fit_on_train_only(trained):
    # the hold-out must not be able to grow the vocabulary
    assert trained.vocab_size >= 50
    assert trained.vocab_size <= 3000


def test_probabilities_length(trained):
    assert len(trained.probabilities) == trained.test_rows
    assert ((trained.probabilities >= 0)
            & (trained.probabilities <= 1)).all()


def test_train_is_deterministic(sample):
    first = train_model(sample, epochs=3, seed=7)
    second = train_model(sample, epochs=3, seed=7)
    assert first.test_accuracy == second.test_accuracy
    assert first.f1 == second.f1
    assert [h["loss"] for h in first.history] == \
        [h["loss"] for h in second.history]


def test_seed_changes_training(sample):
    first = train_model(sample, epochs=3, seed=1)
    second = train_model(sample, epochs=3, seed=2)
    assert [h["loss"] for h in first.history] != \
        [h["loss"] for h in second.history]


def test_more_epochs_reduce_loss(sample):
    quick = train_model(sample, epochs=1)
    longer = train_model(sample, epochs=8)
    assert longer.history[-1]["loss"] < quick.history[-1]["loss"]


def test_train_rejects_bad_hyperparams(sample):
    with pytest.raises(SentimentError, match="epochs"):
        train_model(sample, epochs=0)
    with pytest.raises(SentimentError, match="lr must be"):
        train_model(sample, lr=0.0)
    with pytest.raises(SentimentError, match="batch_size"):
        train_model(sample, batch_size=0)
    with pytest.raises(SentimentError, match="test_fraction"):
        train_model(sample, test_fraction=0.9)


def test_train_rejects_missing_columns():
    with pytest.raises(SentimentError, match="missing column"):
        train_model(pd.DataFrame({"msg": ["hi"], "y": [1]}))


def test_train_rejects_short_frame(sample):
    with pytest.raises(SentimentError, match=f"at least {MIN_ROWS}"):
        train_model(sample.head(30))


def test_result_to_dict(trained):
    payload = trained.to_dict()
    json.dumps(payload)
    assert payload["epochs"] == 25
    assert 0 <= payload["test_accuracy"] <= 1
    confusion = payload["confusion"]
    total = sum(confusion.values())
    assert total == trained.test_rows
    assert set(confusion) == {"tn", "fp", "fn", "tp"}


# --------------------------------------------------------------------------- #
# Prediction
# --------------------------------------------------------------------------- #
def test_predict_positive_phrase(trained):
    label, probability = trained.predict(
        "i love this wonderful great movie")
    assert label == 1
    assert probability > 0.5


def test_predict_negative_phrase(trained):
    label, probability = trained.predict(
        "i hate this terrible awful movie")
    assert label == 0
    assert probability < 0.5


def test_predict_orders_phrases(trained):
    _, p_good = trained.predict("love wonderful great excellent")
    _, p_bad = trained.predict("hate terrible awful horrible")
    assert p_good > p_bad


def test_predict_rejects_empty(trained):
    with pytest.raises(SentimentError, match="non-empty"):
        trained.predict("   ")


def test_predict_rejects_non_string(trained):
    with pytest.raises(SentimentError, match="non-empty"):
        trained.predict(None)  # type: ignore[arg-type]


def test_predict_returns_same_class_as_probabilities(trained):
    # pick a real hold-out message: predict() must agree with training output
    label, probability = trained.predict(trained.test_texts[0])
    expected = 1 if trained.probabilities[0] >= 0.5 else 0
    assert label == expected
    assert 0.0 <= probability <= 1.0


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections(trained):
    text = render_report(trained)
    assert "SENTIMENT MLP CLASSIFIER" in text
    assert "Learning curve" in text
    assert "Hold-out results:" in text
    assert "Confusion matrix" in text
    assert "Most confident hold-out predictions:" in text
    assert "precision" in text and "recall" in text and "f1" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Phrase check:" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(SentimentError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_file_training(capsys):
    assert main(["--file", str(DEMO_CSV), "--epochs", "3"]) == 0
    out = capsys.readouterr().out
    assert "Hold-out results:" in out and "Done." in out


def test_cli_classify_path(capsys):
    assert main(["--classify", "i love this wonderful movie",
                 "--epochs", "25", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Sentiment: POSITIVE" in out


def test_cli_classify_negative(capsys):
    assert main(["--classify", "i hate this terrible awful movie",
                 "--epochs", "25", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Sentiment: NEGATIVE" in out


def test_cli_classify_empty_message(capsys):
    assert main(["--classify", "   "]) == 2
    assert "non-empty" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--epochs", "3",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["epochs"] == 3
    assert 0 <= payload["test_accuracy"] <= 1


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
# Result contract
# --------------------------------------------------------------------------- #
def test_result_to_dict_reports_row_split(trained):
    payload = trained.to_dict()
    assert payload["train_rows"] + payload["test_rows"] == payload["rows"]


def test_result_to_dict_has_vocabulary_size(trained):
    assert trained.to_dict()["vocab_size"] == trained.vocab_size
    assert trained.vocab_size > 0


def test_predict_matches_probability_threshold(trained):
    label, probability = trained.predict("I absolutely loved this movie")
    assert label == (1 if probability >= 0.5 else 0)


def test_probabilities_are_in_unit_interval(trained):
    assert np.all(trained.probabilities >= 0.0)
    assert np.all(trained.probabilities <= 1.0)


def test_render_report_is_ascii(trained):
    render_report(trained).encode("ascii")
