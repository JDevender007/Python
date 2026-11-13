"""Tests for the Word2Vec From Scratch project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from word2vec import (  # noqa: E402
    BATCH_SIZE,
    CORPUS_FILE,
    DIM,
    EPOCHS,
    Word2Vec,
    Word2VecError,
    build_vocab,
    bundle_corpus,
    generate_corpus,
    generate_pairs,
    load_corpus,
    negative_table,
    run_demo,
    tokenize,
    train_model,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS = PROJECT_ROOT / "data" / "corpus.txt"


@pytest.fixture(scope="module")
def text() -> str:
    return load_corpus(CORPUS)


@pytest.fixture(scope="module")
def model(text: str) -> Word2Vec:
    return train_model(text)


@pytest.fixture(scope="module")
def tiny(text: str) -> Word2Vec:
    return train_model(text, dim=8, epochs=3)


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #
def test_generate_corpus_is_deterministic():
    assert generate_corpus() == generate_corpus()


def test_generate_corpus_contains_key_words():
    corpus = generate_corpus()
    for word in ("king", "queen", "man", "woman", "paris"):
        assert word in corpus


def test_bundle_corpus_writes_file(tmp_path):
    path = bundle_corpus(tmp_path)
    assert path.is_file()
    assert path.read_text(encoding="utf-8") == generate_corpus()


def test_load_corpus_missing(tmp_path):
    with pytest.raises(Word2VecError, match="corpus not found"):
        load_corpus(tmp_path / "nope.txt")


def test_load_corpus_empty(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("   \n", encoding="utf-8")
    with pytest.raises(Word2VecError, match="corpus is empty"):
        load_corpus(path)


def test_load_corpus_defaults_to_bundled():
    assert "king" in load_corpus()


# --------------------------------------------------------------------------- #
# Tokenisation / vocabulary
# --------------------------------------------------------------------------- #
def test_tokenize_lowercases_and_filters():
    assert tokenize("The KING rules, 42 times!") == ["the", "king", "rules",
                                                     "times"]


def test_tokenize_rejects_non_string():
    with pytest.raises(Word2VecError, match="text must be a string"):
        tokenize(42)


def test_tokenize_empty():
    assert tokenize("") == []


def test_build_vocab_counts_and_order():
    vocab, frequencies = build_vocab(["b", "a", "a", "b", "b"])
    assert vocab == {"b": 0, "a": 1}
    assert frequencies.tolist() == [3, 2]


def test_build_vocab_min_count():
    vocab, _ = build_vocab(["a", "a", "b", "b", "c"], min_count=2)
    assert set(vocab) == {"a", "b"}


def test_build_vocab_rejects_bad_min_count():
    with pytest.raises(Word2VecError, match="min_count must be at least 1"):
        build_vocab(["a", "b"], min_count=0)


def test_build_vocab_rejects_empty_tokens():
    with pytest.raises(Word2VecError, match="no tokens"):
        build_vocab([])


def test_build_vocab_needs_two_words():
    with pytest.raises(Word2VecError, match="at least two words"):
        build_vocab(["a", "a", "a"])


# --------------------------------------------------------------------------- #
# Pairs
# --------------------------------------------------------------------------- #
def test_pairs_window_one():
    pairs = generate_pairs(np.array([1, 2, 3]), window=1)
    assert pairs.tolist() == [[1, 2], [2, 3], [2, 1], [3, 2]]


def test_pairs_window_two_has_more():
    small = generate_pairs(np.arange(6), window=1)
    large = generate_pairs(np.arange(6), window=2)
    assert large.shape[0] > small.shape[0]


def test_pairs_never_self():
    pairs = generate_pairs(np.array([4, 4, 4]), window=1)
    assert not (pairs[:, 0] == pairs[:, 1]).any()


def test_pairs_reject_bad_window():
    with pytest.raises(Word2VecError, match="window must be at least 1"):
        generate_pairs(np.arange(5), window=0)


def test_pairs_reject_2d_ids():
    with pytest.raises(Word2VecError, match="ids must be 1-D"):
        generate_pairs(np.zeros((3, 3), dtype=int))


def test_pairs_need_enough_tokens():
    with pytest.raises(Word2VecError, match="corpus too short"):
        generate_pairs(np.array([7]), window=2)


# --------------------------------------------------------------------------- #
# Negative sampling table
# --------------------------------------------------------------------------- #
def test_negative_table_shape_and_range():
    table = negative_table(np.array([10.0, 5.0, 1.0]), size=1000)
    assert table.shape == (1000,)
    assert table.min() >= 0
    assert table.max() < 3


def test_negative_table_matches_power_distribution():
    frequencies = np.array([50.0, 30.0, 15.0, 5.0])
    table = negative_table(frequencies, size=50_000)
    empirical = np.bincount(table, minlength=4) / table.size
    expected = frequencies ** 0.75
    expected = expected / expected.sum()
    assert np.abs(empirical - expected).max() < 0.02


def test_negative_table_power_emphasis():
    frequencies = np.array([100.0, 1.0])
    flat = np.bincount(negative_table(frequencies, power=1.0, size=10_000))
    sharp = np.bincount(negative_table(frequencies, power=0.0, size=10_000))
    assert flat[0] > 0.9 * 10_000
    assert abs(sharp[0] - sharp[1]) < 100


@pytest.mark.parametrize("bad", [np.array([1.0]), np.array([0.0, 0.0]),
                                 np.array([-1.0, 2.0])])
def test_negative_table_rejects_bad_frequencies(bad):
    with pytest.raises(Word2VecError, match="frequencies"):
        negative_table(bad)


def test_negative_table_rejects_bad_size():
    with pytest.raises(Word2VecError, match="table size must be positive"):
        negative_table(np.array([1.0, 2.0]), size=0)


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kwargs,needle", [
    ({"dim": 1}, "dim must be at least 2"),
    ({"epochs": 0}, "epochs must be at least 1"),
    ({"negatives": 0}, "negatives must be at least 1"),
    ({"learning_rate": 0.0}, "learning_rate must be in"),
    ({"learning_rate": 20.0}, "learning_rate must be in"),
])
def test_train_validates_flags(kwargs, needle, text):
    with pytest.raises(Word2VecError, match=needle):
        train_model(text, **kwargs)


def test_train_returns_expected_shape(model):
    assert model.vectors.shape == (len(model.words), DIM)
    assert len(model.losses) == EPOCHS
    assert np.isfinite(model.vectors).all()


def test_train_loss_decreases(model):
    assert model.losses[-1] < model.losses[0]


def test_train_is_deterministic(text):
    first = train_model(text, dim=8, epochs=2)
    second = train_model(text, dim=8, epochs=2)
    assert np.allclose(first.vectors, second.vectors)
    assert first.losses == second.losses


def test_train_seed_changes_vectors(text):
    first = train_model(text, dim=8, epochs=2, seed=1)
    second = train_model(text, dim=8, epochs=2, seed=2)
    assert not np.allclose(first.vectors, second.vectors)


def test_train_rejects_empty_corpus():
    with pytest.raises(Word2VecError):
        train_model("")


# --------------------------------------------------------------------------- #
# Similarity / analogy
# --------------------------------------------------------------------------- #
def test_similarity_self_is_one(model):
    assert model.similarity("king", "king") == pytest.approx(1.0)


def test_similarity_symmetric(model):
    assert model.similarity("king", "queen") == pytest.approx(
        model.similarity("queen", "king"))


def test_similarity_known_vs_unrelated(model):
    assert model.similarity("king", "queen") > \
        model.similarity("king", "banana") + 0.1


def test_similarity_unknown_word(model):
    with pytest.raises(Word2VecError, match="word not in vocabulary"):
        model.similarity("king", "unicorn")


def test_most_similar_excludes_query(model):
    neighbours = model.most_similar("king", topn=5)
    assert len(neighbours) == 5
    assert all(word != "king" for word, _ in neighbours)


def test_most_similar_sorted_descending(model):
    scores = [score for _, score in model.most_similar("paris", topn=5)]
    assert scores == sorted(scores, reverse=True)


def test_most_similar_finds_queen(model):
    assert model.most_similar("king", topn=5)[0][0] == "queen"


def test_most_similar_validates_topn(model):
    with pytest.raises(Word2VecError, match="topn must be positive"):
        model.most_similar("king", topn=0)


def test_analogy_finds_queen(model):
    words = [word for word, _ in model.analogy("man", "king", "woman", 5)]
    assert "queen" in words


def test_analogy_excludes_inputs(model):
    words = [word for word, _ in model.analogy("man", "king", "woman", 5)]
    for word in ("man", "king", "woman"):
        assert word not in words


def test_vector_lookup(model):
    assert model.vector("king").shape == (DIM,)


def test_to_dict_json_safe(model):
    payload = model.to_dict()
    json.dumps(payload)
    assert payload["vocab_size"] == len(model.words)
    assert payload["epochs"] == EPOCHS


def test_tiny_model_still_valid(tiny):
    assert tiny.dim == 8
    assert len(tiny.losses) == 3


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


def test_cli_similar_uses_bundled_corpus(capsys):
    assert main(["--similar", "king", "--epochs", "3", "--dim", "8"]) == 0
    out = capsys.readouterr().out
    assert "king" in out.split("Most")[0] or "Vocabulary" in out
    # five ranked neighbours, each printed as "  word   +0.xxxx"
    ranked = [line for line in out.splitlines()
              if line.startswith("  ") and line.strip()]
    assert len([line for line in ranked if len(line.split()) == 2]) == 5


def test_cli_analogy(capsys):
    assert main(["--analogy", "man", "king", "woman",
                 "--epochs", "3", "--dim", "8"]) == 0
    out = capsys.readouterr().out
    assert "man : king :: woman : ?" in out
    ranked = [line for line in out.splitlines()
              if line.startswith("  ") and len(line.split()) == 2]
    assert len(ranked) == 5


def test_cli_corpus_report(capsys):
    assert main(["--corpus", str(CORPUS), "--epochs", "2", "--dim", "8"]) == 0
    out = capsys.readouterr().out
    assert "Vocabulary" in out
    assert "Loss" in out


@pytest.mark.parametrize("flag,value", [
    ("--dim", "1"), ("--epochs", "0"), ("--window", "0"),
    ("--negatives", "0"),
])
def test_cli_validates_flags(flag, value, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--corpus", str(CORPUS), flag, value])
    assert exc.value.code == 2


def test_cli_missing_corpus(tmp_path, capsys):
    assert main(["--corpus", str(tmp_path / "nope.txt")]) == 2
    assert "corpus not found" in capsys.readouterr().err


def test_cli_unknown_word(capsys):
    assert main(["--similar", "unicorn", "--epochs", "2",
                 "--dim", "8"]) == 2
    assert "word not in vocabulary" in capsys.readouterr().err


def test_cli_json_export(tmp_path):
    out = tmp_path / "model.json"
    assert main(["--corpus", str(CORPUS), "--epochs", "2", "--dim", "8",
                 "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["dim"] == 8
    assert payload["epochs"] == 2


def test_bundled_corpus_present():
    assert CORPUS_FILE.is_file()
    assert CORPUS_FILE.read_text(encoding="utf-8") == generate_corpus()
    assert BATCH_SIZE == 256
