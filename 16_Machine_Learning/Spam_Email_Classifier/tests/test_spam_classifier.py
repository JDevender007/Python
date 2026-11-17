"""Tests for the Spam Email Classifier project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from spam_classifier import (  # noqa: E402
    DEMO_CSV,
    LABELS,
    MIN_PER_CLASS,
    MIN_ROWS,
    REQUIRED_COLUMNS,
    SAMPLE_HAM,
    SAMPLE_SPAM,
    SpamError,
    build_pipeline,
    classify,
    load_messages,
    message_text,
    render_report,
    run_demo,
    train_model,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    row = {
        "label": "ham",
        "subject": "Meeting notes",
        "body": "Please review the agenda before the Thursday sync. Thanks!",
    }
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "messages.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _grid(spam: int = 25, ham: int = 25) -> list[dict]:
    rows = []
    for i in range(spam):
        rows.append(_row(
            label="spam", subject=f"WINNER claim {i}",
            body=f"Congratulations you won a FREE prize worth {i}. "
                 f"Click now to claim before it expires!"))
    for i in range(ham):
        rows.append(_row(
            label="ham", subject=f"Notes {i}",
            body=f"Here are the meeting notes for item {i}. "
                 f"Please review and add comments before Friday."))
    return rows


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_messages(DEMO_CSV)


@pytest.fixture(scope="module")
def trained(sample):
    return train_model(sample)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 140
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert set(sample["label"]) == set(LABELS)
    counts = sample["label"].value_counts()
    assert counts["spam"] == 70 and counts["ham"] == 70
    assert sample["subject"].str.len().min() > 0
    assert sample["body"].str.len().min() > 0


def test_load_missing_file(tmp_path):
    with pytest.raises(SpamError, match="not found"):
        load_messages(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("label,body\nham,hello\n", encoding="utf-8")
    with pytest.raises(SpamError, match="missing column"):
        load_messages(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(SpamError, match="no rows"):
        load_messages(path)


def test_load_unknown_label(tmp_path):
    rows = _grid()
    rows[0]["label"] = "phishing"
    with pytest.raises(SpamError, match="unknown label.*phishing"):
        load_messages(_csv(tmp_path, rows))


def test_load_label_case_normalized(tmp_path):
    rows = _grid()
    for row in rows[:5]:
        row["label"] = "SPAM"
    for row in rows[5:10]:
        row["label"] = "Ham"
    frame = load_messages(_csv(tmp_path, rows))
    assert set(frame["label"]) <= set(LABELS)


def test_load_empty_subject(tmp_path):
    rows = _grid()
    rows[0]["subject"] = "  "
    with pytest.raises(SpamError, match="empty 'subject'"):
        load_messages(_csv(tmp_path, rows))


def test_load_empty_body(tmp_path):
    rows = _grid()
    rows[0]["body"] = None
    with pytest.raises(SpamError, match="empty 'body'"):
        load_messages(_csv(tmp_path, rows))


def test_load_too_few_messages(tmp_path):
    with pytest.raises(SpamError, match=f"at least {MIN_ROWS}"):
        load_messages(_csv(tmp_path, _grid(10, 10)))


def test_load_class_with_too_few_rows(tmp_path):
    with pytest.raises(SpamError, match=f"need >= {MIN_PER_CLASS}"):
        load_messages(_csv(tmp_path, _grid(5, 40)))


def test_load_single_class(tmp_path):
    rows = _grid(0, 45)
    with pytest.raises(SpamError, match="too few messages"):
        load_messages(_csv(tmp_path, rows))


# --------------------------------------------------------------------------- #
# Featurisation and pipeline
# --------------------------------------------------------------------------- #
def test_message_text_includes_subject_twice():
    row = _row(subject="Hello", body="World")
    text = message_text(row)
    assert text == "Hello Hello World"


def test_pipeline_steps():
    model = build_pipeline()
    assert set(model.named_steps) == {"vectorize", "classify"}
    assert model.named_steps["classify"].__class__.__name__ == "MultinomialNB"
    vectorizer = model.named_steps["vectorize"]
    assert vectorizer.ngram_range == (1, 2)
    assert vectorizer.lowercase is True


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
def test_train_valid_scores(trained):
    assert 0.0 <= trained.accuracy <= 1.0
    assert 0.0 <= trained.precision <= 1.0
    assert 0.0 <= trained.recall <= 1.0
    assert 0.0 <= trained.f1 <= 1.0
    assert trained.accuracy >= 0.9  # template data separates cleanly


def test_train_confusion_counts_test_rows(trained):
    assert int(trained.confusion.values.sum()) == len(trained.test_labels)
    assert list(trained.confusion.index) == ["spam", "ham"]
    assert list(trained.confusion.columns) == ["spam", "ham"]


def test_train_accuracy_matches_direct_comparison(trained):
    expected = float((trained.test_labels == trained.test_pred).mean())
    assert abs(trained.accuracy - expected) < 1e-12


def test_train_is_deterministic(sample):
    first = train_model(sample, seed=42)
    second = train_model(sample, seed=42)
    assert first.accuracy == second.accuracy
    assert (first.test_pred == second.test_pred).all()


def test_train_seed_changes_split(sample):
    first = train_model(sample, seed=1)
    second = train_model(sample, seed=2)
    assert len(first.test_labels) == len(second.test_labels)
    assert list(first.test_labels.index) != list(second.test_labels.index)


def test_train_rejects_bad_test_size(sample):
    with pytest.raises(SpamError, match="test_size"):
        train_model(sample, test_size=0.9)


def test_train_vocabulary_is_reasonable(trained):
    assert trained.vocabulary_size >= 50
    assert trained.vocabulary_size <= 4000


def test_train_recall_perfect_on_template_data(trained):
    # no ham message should be flagged as spam in this clean sample
    assert trained.confusion.loc["ham", "spam"] <= 1
    assert trained.recall >= 0.9


def test_result_to_dict(trained):
    payload = trained.to_dict()
    json.dumps(payload)
    assert 0 <= payload["holdout"]["accuracy"] <= 1
    assert payload["vocabulary_size"] == trained.vocabulary_size
    assert set(payload["confusion_matrix"]) == {"spam", "ham"}
    total = sum(sum(row.values())
                for row in payload["confusion_matrix"].values())
    assert total == len(trained.test_labels)


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def test_classify_obvious_spam(trained):
    label, probability = classify(trained, SAMPLE_SPAM)
    assert label == "spam"
    assert probability >= 0.5


def test_classify_obvious_ham(trained):
    label, probability = classify(trained, SAMPLE_HAM)
    assert label == "ham"
    assert probability < 0.5


def test_classify_separates_probabilities(trained):
    _, spam_prob = classify(trained, SAMPLE_SPAM)
    _, ham_prob = classify(trained, SAMPLE_HAM)
    assert spam_prob > ham_prob
    assert 0.0 <= ham_prob < spam_prob <= 1.0


def test_classify_is_case_insensitive(trained):
    label, _ = classify(trained, SAMPLE_SPAM.lower())
    assert label == "spam"


def test_classify_rejects_empty(trained):
    with pytest.raises(SpamError, match="non-empty"):
        classify(trained, "   ")


def test_classify_rejects_non_string(trained):
    with pytest.raises(SpamError, match="non-empty"):
        classify(trained, None)


def test_classify_rejects_huge_message(trained):
    with pytest.raises(SpamError, match="too long"):
        classify(trained, "word " * 5_000)


def test_classify_unseen_words_still_works(trained):
    label, probability = classify(
        trained, "zorble flimnap wibbleton quuxical free winner")
    assert label in LABELS
    assert 0.0 <= probability <= 1.0


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections(trained, sample):
    text = render_report(trained, sample)
    assert "SPAM EMAIL CLASSIFIER" in text
    assert "Confusion matrix" in text
    assert "Per-class metrics:" in text
    assert "pred spam" in text and "pred ham" in text
    assert "Vocabulary" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Sample classifications:" in out
    assert "100.0%  spam" in out or "spam" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(SpamError, match="bundled sample"):
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
    assert "Confusion matrix" in out and "Done." in out


def test_cli_classify_spam(capsys):
    assert main(["--classify", SAMPLE_SPAM, "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Verdict: SPAM" in out


def test_cli_classify_ham(capsys):
    assert main(["--classify", SAMPLE_HAM, "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Verdict: HAM" in out


def test_cli_classify_with_file(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV),
                 "--classify", "claim your FREE winner prize now",
                 "--json", str(payload_path)]) == 0
    out = capsys.readouterr().out
    assert "Verdict: SPAM" in out
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["classification"]["label"] == "spam"
    assert 0 <= payload["classification"]["spam_probability"] <= 1


def test_cli_classify_empty(capsys):
    assert main(["--classify", "   "]) == 2
    assert "non-empty" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--json", str(payload_path),
                 "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["holdout"]["accuracy"] >= 0.9
    assert set(payload["confusion_matrix"]) == {"spam", "ham"}


def test_cli_seed_option(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--seed", "7",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["holdout"]["accuracy"] >= 0.9


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
# Pipeline and probability details
# --------------------------------------------------------------------------- #
def test_message_text_joins_subject_and_body():
    text = message_text({"subject": "Big sale", "body": "click here now"})
    assert "Big sale" in text and "click here now" in text


def test_result_to_dict_keys(trained):
    payload = trained.to_dict()
    assert set(payload) == {"holdout", "vocabulary_size", "confusion_matrix"}
    assert set(payload["holdout"]) == {"accuracy", "precision_spam",
                                       "recall_spam", "f1"}


def test_classify_probabilities_sum_to_one(trained):
    label, probability = classify(
        trained, "congratulations you won a free prize claim now")
    assert label in {"spam", "ham"}
    assert 0.5 <= probability <= 1.0


def test_render_report_is_ascii(trained, sample):
    render_report(trained, sample).encode("ascii")


def test_build_pipeline_returns_a_fresh_instance():
    assert build_pipeline() is not build_pipeline()
