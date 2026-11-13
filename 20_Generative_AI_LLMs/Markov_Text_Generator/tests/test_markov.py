"""Tests for the Markov Text Generator project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from markov import (  # noqa: E402
    CORPUS_FILE,
    DEFAULT_ORDER,
    MAX_ORDER,
    MIN_ORDER,
    MarkovError,
    build_model,
    bundle_corpus,
    detokenize,
    generate_corpus,
    generate_text,
    load_corpus,
    most_likely,
    perplexity,
    run_demo,
    to_dict,
    tokenize,
    transition_report,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS = PROJECT_ROOT / "data" / "corpus.txt"

SMALL = "the cat sat . the cat ran . the dog sat .".split()


@pytest.fixture(scope="module")
def text() -> str:
    return load_corpus(CORPUS)


@pytest.fixture(scope="module")
def tokens(text: str) -> list[str]:
    return tokenize(text)


@pytest.fixture(scope="module")
def bigram(tokens):
    return build_model(tokens, order=2)


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #
def test_generate_corpus_is_deterministic():
    assert generate_corpus() == generate_corpus()


def test_generate_corpus_has_sentences():
    corpus = generate_corpus()
    assert corpus.endswith("\n")
    assert corpus.count(".") >= 90


def test_bundle_corpus_roundtrip(tmp_path):
    path = bundle_corpus(tmp_path)
    assert path.is_file()
    assert path.read_text(encoding="utf-8") == generate_corpus()


def test_load_corpus_missing(tmp_path):
    with pytest.raises(MarkovError, match="corpus not found"):
        load_corpus(tmp_path / "ghost.txt")


def test_load_corpus_empty(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("   \n", encoding="utf-8")
    with pytest.raises(MarkovError, match="corpus is empty"):
        load_corpus(path)


def test_load_corpus_defaults_to_bundled():
    assert "gardener" in load_corpus()


def test_tokenize_lowercases_and_keeps_punctuation():
    assert tokenize("The Cat, sat!") == ["the", "cat", ",", "sat", "!"]


def test_tokenize_rejects_non_string():
    with pytest.raises(MarkovError, match="text must be a string"):
        tokenize(12)


def test_tokenize_empty_text():
    assert tokenize("") == []


# --------------------------------------------------------------------------- #
# Model building
# --------------------------------------------------------------------------- #
def test_build_model_counts_bigrams():
    model = build_model(SMALL, order=2)
    assert model.successors(("the", "cat"))["sat"] == 1
    assert model.successors(("cat", "sat"))["."] == 1


def test_build_model_vocab_includes_every_token():
    model = build_model(SMALL, order=1)
    assert set(model.vocab) == set(SMALL)


def test_build_model_state_and_transition_counts():
    model = build_model(SMALL, order=1)
    assert model.states == len(set(SMALL[:-1]))
    assert model.transitions == sum(len(c) for c in model.counts.values())


@pytest.mark.parametrize("order", [MIN_ORDER - 1, MAX_ORDER + 1])
def test_build_model_rejects_bad_order(order):
    with pytest.raises(MarkovError, match="order must be in"):
        build_model(SMALL, order=order)


def test_build_model_rejects_empty_tokens():
    with pytest.raises(MarkovError, match="no tokens"):
        build_model([])


def test_build_model_rejects_tiny_corpus():
    with pytest.raises(MarkovError, match="needs more than"):
        build_model(["a", "b"], order=2)


def test_starts_contain_only_words():
    model = build_model(SMALL, order=1)
    assert all(token.isalpha() for context in model.starts for token in context)


def test_model_has_starts_even_without_sentence_boundaries():
    model = build_model(["a", "b", "c", "d"], order=2)
    assert model.starts


# --------------------------------------------------------------------------- #
# Prediction / generation
# --------------------------------------------------------------------------- #
def test_most_likely_returns_highest_count():
    model = build_model(SMALL, order=1)
    assert most_likely(model, ("sat",)) == "."


def test_most_likely_unknown_context():
    model = build_model(SMALL, order=1)
    assert most_likely(model, ("unicorn",)) is None


def test_generate_is_deterministic(bigram):
    assert generate_text(bigram, 20, seed=3) == generate_text(bigram, 20, seed=3)


def test_generate_seed_changes_output(bigram):
    assert generate_text(bigram, 20, seed=3) != generate_text(bigram, 20, seed=4)


def test_generate_respects_length(bigram):
    assert len(generate_text(bigram, 15, seed=1)) == 15


def test_generate_only_uses_vocabulary(bigram):
    sample = generate_text(bigram, 40, seed=9)
    assert set(sample) <= set(bigram.vocab)


def test_generate_honours_start_context(bigram):
    context = ("the", "garden")
    sample = generate_text(bigram, 10, seed=2, start=context)
    assert tuple(sample[:2]) == context


def test_generate_rejects_wrong_start_length(bigram):
    with pytest.raises(MarkovError, match="start context must have 2"):
        generate_text(bigram, 5, start=("the",))


@pytest.mark.parametrize("length", [0, -3])
def test_generate_rejects_bad_length(bigram, length):
    with pytest.raises(MarkovError, match="length must be at least 1"):
        generate_text(bigram, length)


def test_generate_rejects_empty_model():
    model = build_model(SMALL, order=1)
    model.counts.clear()
    with pytest.raises(MarkovError, match="no transitions"):
        generate_text(model, 5)


def test_detokenize_no_space_before_punctuation():
    assert detokenize(["the", "cat", "."]) == "The cat."


def test_detokenize_empty():
    assert detokenize([]) == ""


# --------------------------------------------------------------------------- #
# Perplexity
# --------------------------------------------------------------------------- #
def test_perplexity_is_finite_and_positive(bigram, tokens):
    score = perplexity(bigram, tokens)
    assert score > 1.0
    assert score < 1000.0


def test_bigram_beats_unigram(tokens):
    uni = perplexity(build_model(tokens, order=1), tokens)
    bi = perplexity(build_model(tokens, order=2), tokens)
    assert bi < uni


def test_perplexity_requires_tokens(bigram):
    with pytest.raises(MarkovError, match="empty token list"):
        perplexity(bigram, [])


def test_perplexity_needs_long_enough_sequence(bigram):
    with pytest.raises(MarkovError, match="too short to score"):
        perplexity(bigram, ["the"])


def test_perplexity_backs_off_for_unseen_context():
    model = build_model(SMALL, order=2)
    score = perplexity(model, ["zzz", "qqq", "cat"])
    assert score > 1.0


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def test_transition_report_lines(bigram):
    lines = transition_report(bigram, limit=4)
    assert len(lines) == 4
    assert all("->" in line for line in lines)


def test_to_dict_is_json_safe(bigram):
    payload = to_dict(bigram, generate_text(bigram, 10, seed=1))
    json.dumps(payload)
    assert payload["order"] == 2
    assert payload["tokens"] == 10


# --------------------------------------------------------------------------- #
# Demo + CLI
# --------------------------------------------------------------------------- #
def test_run_demo_prints_cross_checks(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    assert capsys.readouterr().out == first


def test_cli_demo(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_requires_a_mode():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_corpus_report(capsys):
    assert main(["--corpus", str(CORPUS), "--length", "12"]) == 0
    out = capsys.readouterr().out
    assert "Perplexity" in out
    assert "Top transitions" in out


@pytest.mark.parametrize("flag,value,needle", [
    ("--order", "0", "order must be in"),
    ("--order", "4", "order must be in"),
    ("--length", "0", "length must be at least 1"),
])
def test_cli_validates_flags(flag, value, needle, capsys):
    assert main(["--corpus", str(CORPUS), flag, value]) == 2
    assert needle in capsys.readouterr().err


def test_cli_missing_corpus(tmp_path, capsys):
    assert main(["--corpus", str(tmp_path / "nope.txt")]) == 2
    assert "corpus not found" in capsys.readouterr().err


def test_cli_json_export(tmp_path):
    out = tmp_path / "run.json"
    assert main(["--corpus", str(CORPUS), "--length", "10", "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["order"] == DEFAULT_ORDER
    assert payload["tokens"] == 10
    assert "perplexity" in payload


def test_bundled_corpus_matches_generator():
    assert CORPUS_FILE.is_file()
    assert load_corpus(CORPUS_FILE) == generate_corpus()
