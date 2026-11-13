"""Tests for the Pos Tag Tagger project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hmm_tagger import (  # noqa: E402
    DEFAULT_CORPUS,
    MIN_SENTENCES,
    TAGS,
    TaggerError,
    HmmModel,
    baseline_accuracy,
    corpus_stats,
    evaluate,
    load_corpus,
    render_report,
    run_demo,
    split_corpus,
    split_words,
    train_hmm,
    viterbi,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TOY = (
    [[("the", "DT"), ("dogs", "NNS"), ("read", "VBD"), (".", ".")]] * 5 +
    [[("we", "PRP"), ("will", "MD"), ("read", "VB"), (".", ".")]] * 5
)


def _write_corpus(path: Path, n: int = 25) -> Path:
    """Valid CoNLL file with n short sentences."""
    lines: list[str] = []
    for _ in range(n):
        lines += ["the\tDT", "cats\tNNS", "ran\tVBD", ".\t.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def sentences() -> list:
    return load_corpus(DEFAULT_CORPUS)


@pytest.fixture(scope="module")
def model(sentences) -> HmmModel:
    train, _ = split_corpus(sentences, 0.8)
    return train_hmm(train)


@pytest.fixture(scope="module")
def toy_model() -> HmmModel:
    return train_hmm(TOY)


# --------------------------------------------------------------------------- #
# Corpus loading
# --------------------------------------------------------------------------- #
def test_load_bundled_corpus(sentences):
    assert len(sentences) == 600
    stats = corpus_stats(sentences)
    assert stats == {"sentences": 600, "tokens": 4080, "words": 167,
                     "tags": 20}
    for sentence in sentences:
        assert sentence
        for word, tag in sentence:
            assert word and word.strip() == word
            assert tag in TAGS


def test_load_missing_file(tmp_path):
    with pytest.raises(TaggerError, match="corpus file not found"):
        load_corpus(tmp_path / "nope.txt")


def test_load_malformed_line(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("the DT\n", encoding="utf-8")
    with pytest.raises(TaggerError, match="expected 'word<TAB>tag'"):
        load_corpus(path)


def test_load_unknown_tag(tmp_path):
    path = tmp_path / "tag.txt"
    path.write_text("the\tXYZ\n", encoding="utf-8")
    with pytest.raises(TaggerError, match="unknown tag 'XYZ'"):
        load_corpus(path)


def test_load_too_few_sentences(tmp_path):
    path = _write_corpus(tmp_path / "small.txt", n=MIN_SENTENCES - 1)
    with pytest.raises(TaggerError,
                       match=f"at least {MIN_SENTENCES} sentences"):
        load_corpus(path)


def test_load_empty_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("\n\n", encoding="utf-8")
    with pytest.raises(TaggerError, match="no sentences"):
        load_corpus(path)


# --------------------------------------------------------------------------- #
# Splitting and stats
# --------------------------------------------------------------------------- #
def test_split_corpus_is_chronological(sentences):
    train, test = split_corpus(sentences, 0.8)
    assert len(train) == 480 and len(test) == 120
    assert train + test == sentences
    assert train[0] == sentences[0]


def test_split_corpus_rejects_bad_ratio():
    with pytest.raises(TaggerError, match=r"ratio must be in \(0, 1\)"):
        split_corpus(TOY, ratio=0)
    with pytest.raises(TaggerError, match=r"ratio must be in \(0, 1\)"):
        split_corpus(TOY, ratio=1.5)


def test_split_corpus_needs_two_sentences():
    with pytest.raises(TaggerError, match="at least 2 sentences"):
        split_corpus(TOY[:1], ratio=0.5)


def test_corpus_stats_empty_rejected():
    with pytest.raises(TaggerError, match="no sentences"):
        corpus_stats([])


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
def test_train_shapes_and_finiteness(model, sentences):
    train, _ = split_corpus(sentences, 0.8)
    t_count = len(model.tags)
    assert model.initial.shape == (t_count,)
    assert model.transition.shape == (t_count, t_count)
    assert model.emission.shape == (t_count, len(model.words) + 1)
    assert model.unk_index == len(model.words)
    for table in (model.initial, model.transition, model.emission):
        assert np.isfinite(table).all()
    assert model.majority_tag in TAGS
    assert train[0][0][0] in model.word_index


def test_probability_tables_sum_to_one(model):
    assert np.allclose(np.exp(model.initial).sum(), 1.0)
    assert np.allclose(np.exp(model.transition).sum(axis=1), 1.0)
    assert np.allclose(np.exp(model.emission).sum(axis=1), 1.0)


def test_training_is_deterministic(sentences):
    train, _ = split_corpus(sentences, 0.8)
    first = train_hmm(train)
    second = train_hmm(train)
    assert np.array_equal(first.initial, second.initial)
    assert np.array_equal(first.transition, second.transition)
    assert np.array_equal(first.emission, second.emission)


def test_train_rejects_bad_alpha():
    for alpha in (0, -0.5, True, "fast"):
        with pytest.raises(TaggerError, match="alpha must be > 0"):
            train_hmm(TOY, alpha=alpha)


def test_train_rejects_bad_sentences():
    with pytest.raises(TaggerError, match="at least one training sentence"):
        train_hmm([])
    with pytest.raises(TaggerError, match="must not be empty"):
        train_hmm([[]])
    with pytest.raises(TaggerError, match="unknown tag"):
        train_hmm([[("x", "BOGUS")]])


# --------------------------------------------------------------------------- #
# Viterbi decoding
# --------------------------------------------------------------------------- #
def test_viterbi_reproduces_toy_sentences(toy_model):
    assert viterbi(toy_model, ["the", "dogs", "read", "."]) == \
        ["DT", "NNS", "VBD", "."]
    assert viterbi(toy_model, ["we", "will", "read", "."]) == \
        ["PRP", "MD", "VB", "."]


def test_viterbi_uses_context_for_ambiguous_read(toy_model):
    # 'read' appears with both VB and VBD; only the left context decides.
    assert viterbi(toy_model, ["the", "dogs", "read"])[-1] == "VBD"
    assert viterbi(toy_model, ["we", "will", "read"])[-1] == "VB"


def test_viterbi_output_lengths_and_tags(model, sentences):
    _, test = split_corpus(sentences, 0.8)
    for sentence in test[:10]:
        words = [w for w, _ in sentence]
        tags = viterbi(model, words)
        assert len(tags) == len(words)
        assert all(t in TAGS for t in tags)


def test_viterbi_case_insensitive_lookup(model):
    lower = viterbi(model, ["the", "dog", "sleeps", "often", "."])
    title = viterbi(model, ["The", "dog", "sleeps", "often", "."])
    assert lower == title
    assert title[0] == "DT"


def test_viterbi_handles_unknown_words(model):
    tags = viterbi(model, ["zzz", "qqq"])
    assert len(tags) == 2 and all(t in TAGS for t in tags)


def test_viterbi_rejects_bad_inputs(model):
    with pytest.raises(TaggerError, match="at least one word"):
        viterbi(model, [])
    with pytest.raises(TaggerError, match="non-empty strings"):
        viterbi(model, [""])
    with pytest.raises(TaggerError, match="whitespace"):
        viterbi(model, ["two words"])


# --------------------------------------------------------------------------- #
# Raw sentence helper
# --------------------------------------------------------------------------- #
def test_split_words_normalizes_whitespace():
    assert split_words("  where   does \t the dog  ") == \
        ["where", "does", "the", "dog"]


def test_split_words_rejects_bad_input():
    with pytest.raises(TaggerError, match="must be a string"):
        split_words(None)
    with pytest.raises(TaggerError, match="must not be empty"):
        split_words("    ")


def test_tag_text_returns_word_tag_pairs(model):
    pairs = model.tag_text("Where does the dog sleep")
    assert pairs == [("Where", "WRB"), ("does", "VBZ"), ("the", "DT"),
                     ("dog", "NN"), ("sleep", "VB")]


# --------------------------------------------------------------------------- #
# Evaluation and baseline
# --------------------------------------------------------------------------- #
def test_evaluate_perfect_on_toy(toy_model):
    result = evaluate(toy_model, TOY)
    assert result["accuracy"] == 1.0
    assert result["tokens"] == 40
    assert result["correct"] == 40
    assert sum(row["support"] for row in result["tags"].values()) == 40
    assert result["tags"]["VBD"]["f1"] == 1.0


def test_evaluate_matches_hand_computed_accuracy(sentences, model):
    _, test = split_corpus(sentences, 0.8)
    result = evaluate(model, test)
    assert result["accuracy"] == result["correct"] / result["tokens"]
    assert result["tokens"] == sum(len(s) for s in test)
    assert result["accuracy"] >= 0.9
    assert 0 <= result["correct"] <= result["tokens"]


def test_evaluate_rejects_empty():
    toy = train_hmm(TOY)
    with pytest.raises(TaggerError, match="no sentences to evaluate"):
        evaluate(toy, [])


def test_baseline_hand_computed(toy_model):
    # 'read' ties VB/VBD (5-5) -> alphabetical majority 'VB': 5 errors.
    assert baseline_accuracy(toy_model, TOY) == pytest.approx(35 / 40)
    assert toy_model.majority_tag == "."


def test_baseline_rejects_empty(toy_model):
    with pytest.raises(TaggerError, match="no sentences to evaluate"):
        baseline_accuracy(toy_model, [])


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections(sentences, model):
    train, test = split_corpus(sentences, 0.8)
    result = evaluate(model, test)
    baseline = baseline_accuracy(model, test)
    sample = model.tag_text("Where does the dog sleep")
    report = render_report(corpus_stats(sentences), (len(train), len(test)),
                           baseline, result, sample)
    assert "POS TAGGER" in report
    assert "Baseline" in report and "Viterbi accuracy" in report
    assert "Per-tag metrics" in report
    assert "Sample tagging:" in report
    assert "Where/WRB" in report


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK:" in out
    assert "Viterbi accuracy" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_corpus(tmp_path):
    with pytest.raises(TaggerError, match="bundled corpus"):
        run_demo(corpus_path=tmp_path / "nope.txt")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_twice_exits_zero(capsys):
    assert main(["--demo"]) == 0
    assert main(["--demo"]) == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_cli_file_mode(tmp_path, capsys):
    path = _write_corpus(tmp_path / "corpus.txt")
    assert main(["--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "POS TAGGER" in out and "Viterbi accuracy" in out
    assert "Done." in out


def test_cli_sentence_mode(capsys):
    assert main(["--sentence", "Where does the dog sleep"]) == 0
    out = capsys.readouterr().out
    assert ("Tagged: Where/WRB  does/VBZ  the/DT  dog/NN  "
            "sleep/VB") in out


def test_cli_sentence_with_file(tmp_path, capsys):
    path = _write_corpus(tmp_path / "corpus.txt")
    assert main(["--file", str(path), "--sentence", "the cats ran",
                 "--quiet"]) == 0
    assert "Tagged: the/DT  cats/NNS  ran/VBD" in capsys.readouterr().out


def test_cli_demo_rejects_sentence(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--demo", "--sentence", "hi"])
    assert excinfo.value.code == 2
    assert "cannot be combined" in capsys.readouterr().err


def test_cli_empty_sentence_fails_fast(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--sentence", "   "])
    assert excinfo.value.code == 2
    assert "must not be empty" in capsys.readouterr().err


def test_cli_bad_ratio_fails_fast(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--file", "corpus.txt", "--ratio", "1"])
    assert excinfo.value.code == 2
    assert "--ratio must be in (0, 1)" in capsys.readouterr().err


def test_cli_missing_file_returns_two(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.txt"), "--quiet"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEFAULT_CORPUS), "--ratio", "0.8",
                 "--sentence", "the dog sleeps", "--json",
                 str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["train"] == 480 and payload["test"] == 120
    assert 0.0 <= payload["baseline_accuracy"] <= 1.0
    assert 0.0 <= payload["hmm_accuracy"] <= 1.0
    assert payload["hmm_accuracy"] >= payload["baseline_accuracy"]
    assert [p["tag"] for p in payload["tagged"]] == ["DT", "NN", "VBZ"]


def test_cli_requires_an_action(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
    assert "--demo --file --sentence" in capsys.readouterr().err


def test_project_ships_bundled_data():
    assert DEFAULT_CORPUS.is_file()
    assert DEFAULT_CORPUS.parent == PROJECT_ROOT / "data"
