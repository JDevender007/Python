"""Tests for the Attention Visualizer project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from attention import (  # noqa: E402
    DEFAULT_HEADS,
    HEAT_CHARS,
    REQUIRED_IDS,
    TEXTS_FILE,
    AttentionError,
    Sentence,
    analyse,
    ascii_heatmap,
    build_vocab,
    causal_mask,
    cooccurrence,
    embed_tokens,
    head_diversity,
    head_projections,
    load_texts,
    multi_head_attention,
    normalized_entropy,
    ppmi,
    positional_encoding,
    row_entropy,
    run_demo,
    scaled_scores,
    sentence_matrix,
    softmax,
    to_dict,
    tokenize,
    top_attended,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEXTS = PROJECT_ROOT / "data" / "texts.json"


@pytest.fixture(scope="module")
def sentences():
    return load_texts(TEXTS)


@pytest.fixture(scope="module")
def embedded(sentences):
    return embed_tokens(sentences)


@pytest.fixture(scope="module")
def first_matrix(sentences, embedded):
    embeddings, vocab = embedded
    return sentence_matrix(sentences[0], vocab, embeddings)


@pytest.fixture(scope="module")
def maps(first_matrix):
    return multi_head_attention(first_matrix, n_heads=4, seed=7)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_load_texts_returns_bundled_sentences(sentences):
    assert len(sentences) == 4
    assert {sentence.id for sentence in sentences} == REQUIRED_IDS


def test_load_texts_keeps_text_and_ids(sentences):
    assert sentences[0].id == "s1"
    assert "lighthouse" in sentences[0].text


def test_load_texts_missing_file(tmp_path):
    with pytest.raises(AttentionError, match="text store not found"):
        load_texts(tmp_path / "ghost.json")


def test_load_texts_rejects_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(AttentionError, match="not valid JSON"):
        load_texts(path)


def test_load_texts_requires_sentences_key(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"rows": []}), encoding="utf-8")
    with pytest.raises(AttentionError, match="'sentences'"):
        load_texts(path)


def test_load_texts_rejects_empty_list(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"sentences": []}), encoding="utf-8")
    with pytest.raises(AttentionError, match="non-empty list"):
        load_texts(path)


def test_load_texts_rejects_bad_entry(tmp_path):
    path = tmp_path / "bad_entry.json"
    path.write_text(json.dumps({"sentences": [42]}), encoding="utf-8")
    with pytest.raises(AttentionError, match="not an object or string"):
        load_texts(path)


def test_load_texts_rejects_missing_field(tmp_path):
    path = tmp_path / "missing.json"
    path.write_text(json.dumps({"sentences": [{"id": "a"}]}),
                    encoding="utf-8")
    with pytest.raises(AttentionError, match="needs 'id' and 'text'"):
        load_texts(path)


def test_load_texts_rejects_empty_text(tmp_path):
    path = tmp_path / "blank.json"
    path.write_text(json.dumps({"sentences": [{"id": "a", "text": "  "}]}),
                    encoding="utf-8")
    with pytest.raises(AttentionError, match="empty text"):
        load_texts(path)


def test_load_texts_rejects_duplicate_ids(tmp_path):
    rows = [{"id": "a", "text": "One two."}, {"id": "a", "text": "Three four."}]
    path = tmp_path / "dupe.json"
    path.write_text(json.dumps({"sentences": rows}), encoding="utf-8")
    with pytest.raises(AttentionError, match="duplicate sentence id"):
        load_texts(path)


def test_load_texts_accepts_plain_strings(tmp_path):
    path = tmp_path / "plain.json"
    path.write_text(json.dumps({"sentences": ["one two", "three four"]}),
                    encoding="utf-8")
    loaded = load_texts(path)
    assert [sentence.id for sentence in loaded] == ["s1", "s2"]


def test_sentence_tokens_and_dict(sentences):
    assert sentences[0].tokens[0] == "the"
    assert sentences[0].to_dict()["tokens"] == len(sentences[0].tokens)


# --------------------------------------------------------------------------- #
# Tokenisation and vocabulary
# --------------------------------------------------------------------------- #
def test_tokenize_lowercases_and_splits_punctuation():
    assert tokenize("The Sailor, watched!") == ["the", "sailor", "watched"]


def test_tokenize_keeps_apostrophes():
    assert tokenize("don't stop") == ["don't", "stop"]


def test_tokenize_empty():
    assert tokenize("") == []


def test_tokenize_rejects_non_string():
    with pytest.raises(AttentionError, match="text must be a string"):
        tokenize(7)


def test_build_vocab_is_frequency_ordered():
    sentences = [Sentence("a", "the cat the dog"), Sentence("b", "the cat")]
    vocab = build_vocab(sentences)
    assert vocab["the"] == 0
    assert list(vocab)[1:3] == ["cat", "dog"]


def test_build_vocab_rejects_empty():
    with pytest.raises(AttentionError, match="no sentences"):
        build_vocab([])


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def test_cooccurrence_is_symmetric(sentences):
    counts, _ = cooccurrence(sentences, window=2)
    assert counts.shape[0] == counts.shape[1]
    assert np.allclose(counts, counts.T)


def test_cooccurrence_diagonal_is_zero(sentences):
    counts, _ = cooccurrence(sentences, window=2)
    assert np.allclose(np.diag(counts), 0.0)


def test_cooccurrence_window_changes_counts(sentences):
    narrow, _ = cooccurrence(sentences, window=1)
    wide, _ = cooccurrence(sentences, window=3)
    assert wide.sum() >= narrow.sum()


def test_cooccurrence_rejects_bad_window(sentences):
    with pytest.raises(AttentionError, match="window must be >= 1"):
        cooccurrence(sentences, window=0)


def test_ppmi_matches_the_formula():
    counts = np.array([[0.0, 4.0], [4.0, 0.0]])
    matrix = ppmi(counts)
    # pmi = ln( (4 * 8) / (4 * 4) ) = ln(2)
    assert matrix.shape == (2, 2)
    assert matrix[0, 1] == pytest.approx(math.log(2.0))
    assert np.all(matrix >= 0)


def test_ppmi_rejects_non_square():
    with pytest.raises(AttentionError, match="square matrix"):
        ppmi(np.zeros((2, 3)))


def test_ppmi_rejects_empty():
    with pytest.raises(AttentionError, match="empty"):
        ppmi(np.zeros((0, 0)))


def test_ppmi_rejects_bad_smoothing():
    with pytest.raises(AttentionError, match="smoothing must be > 0"):
        ppmi(np.ones((2, 2)), smoothing=0)


def test_ppmi_rejects_zero_counts():
    with pytest.raises(AttentionError, match="no observations"):
        ppmi(np.zeros((2, 2)))


def test_embed_tokens_rows_are_unit_length(embedded):
    embeddings, vocab = embedded
    assert embeddings.shape[0] == len(vocab)
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0)


def test_embed_tokens_gives_distinct_rows(embedded):
    embeddings, _ = embedded
    assert not np.allclose(embeddings[0], embeddings[1])


def test_embed_tokens_is_deterministic(sentences):
    first, _ = embed_tokens(sentences)
    second, _ = embed_tokens(sentences)
    assert np.array_equal(first, second)


def test_embed_tokens_rejects_negative_noise(sentences):
    with pytest.raises(AttentionError, match="noise must be >= 0"):
        embed_tokens(sentences, noise=-0.1)


def test_positional_encoding_shape():
    encoding = positional_encoding(5, 8)
    assert encoding.shape == (5, 8)


def test_positional_encoding_first_position():
    encoding = positional_encoding(4, 6)
    assert encoding[0, 0] == 0.0
    assert encoding[0, 1] == pytest.approx(1.0)


def test_positional_encoding_rows_differ():
    encoding = positional_encoding(4, 6)
    assert not np.allclose(encoding[1], encoding[2])


def test_positional_encoding_handles_odd_dim():
    assert positional_encoding(3, 7).shape == (3, 7)


@pytest.mark.parametrize("length,dim,needle", [
    (0, 8, "length must be >= 1"),
    (3, 1, "dim must be >= 2"),
])
def test_positional_encoding_validates(length, dim, needle):
    with pytest.raises(AttentionError, match=needle):
        positional_encoding(length, dim)


def test_sentence_matrix_shape(first_matrix):
    assert first_matrix.shape == (6, 26)


def test_sentence_matrix_rejects_unknown_token():
    vocab = {"the": 0}
    embeddings = np.eye(1)
    with pytest.raises(AttentionError, match="unknown tokens"):
        sentence_matrix(Sentence("x", "the ghost"), vocab, embeddings)


def test_sentence_matrix_rejects_empty_sentence():
    with pytest.raises(AttentionError, match="no tokens"):
        sentence_matrix(Sentence("x", "..."), {"the": 0}, np.eye(1))


# --------------------------------------------------------------------------- #
# Attention maths
# --------------------------------------------------------------------------- #
def test_scaled_scores_matches_manual_product():
    query = np.array([[1.0, 0.0]])
    key = np.array([[1.0, 0.0], [0.0, 1.0]])
    scores = scaled_scores(query, key)
    assert scores.shape == (1, 2)
    # dot products are divided by sqrt(d_k) = sqrt(2)
    assert scores[0, 0] == pytest.approx(1.0 / math.sqrt(2))
    assert scores[0, 1] == pytest.approx(0.0)


def test_scaled_scores_rejects_width_mismatch():
    with pytest.raises(AttentionError, match="widths must match"):
        scaled_scores(np.zeros((2, 3)), np.zeros((2, 4)))


def test_scaled_scores_rejects_1d_input():
    with pytest.raises(AttentionError, match="must be 2-D"):
        scaled_scores(np.zeros(3), np.zeros((2, 3)))


def test_softmax_rows_sum_to_one():
    scores = np.array([[1.0, 2.0, 3.0], [0.5, -1.0, 4.0]])
    result = softmax(scores)
    assert np.allclose(result.sum(axis=1), 1.0)


def test_softmax_matches_naive_formula():
    scores = np.array([[0.1, 0.2, -0.3]])
    naive = np.exp(scores) / np.exp(scores).sum(axis=1, keepdims=True)
    assert np.allclose(softmax(scores), naive)


def test_softmax_is_numerically_stable():
    result = softmax(np.array([[1000.0, 1000.0, 1000.0]]))
    assert np.isfinite(result).all()
    assert np.allclose(result, 1.0 / 3.0)


def test_softmax_rejects_1d():
    with pytest.raises(AttentionError, match="must be 2-D"):
        softmax(np.zeros(3))


def test_softmax_rejects_empty():
    with pytest.raises(AttentionError, match="empty"):
        softmax(np.zeros((0, 3)))


def test_causal_mask_is_lower_triangular():
    mask = causal_mask(4)
    assert mask.shape == (4, 4)
    assert mask.dtype == bool
    assert mask[0, 3] is np.False_ or not mask[0, 3]
    assert mask[3, 0]


def test_causal_mask_diagonal_is_allowed():
    assert np.all(np.diag(causal_mask(5)))


def test_causal_mask_rejects_zero_length():
    with pytest.raises(AttentionError, match="length must be >= 1"):
        causal_mask(0)


def test_head_projections_shapes():
    heads = head_projections(dim=10, n_heads=3, d_head=4, seed=1)
    assert len(heads) == 3
    assert all(head["q"].shape == (10, 4) for head in heads)
    assert all(head["k"].shape == (10, 4) for head in heads)


def test_head_projections_are_deterministic():
    first = head_projections(8, 2, 4, seed=3)
    second = head_projections(8, 2, 4, seed=3)
    assert np.array_equal(first[0]["q"], second[0]["q"])


def test_head_projections_differ_between_heads():
    heads = head_projections(8, 2, 4, seed=3)
    assert not np.allclose(heads[0]["q"], heads[1]["q"])


@pytest.mark.parametrize("heads,d_head,needle", [
    (0, 4, "n_heads must be >= 1"),
    (2, 0, "d_head must be >= 1"),
])
def test_head_projections_validate(heads, d_head, needle):
    with pytest.raises(AttentionError, match=needle):
        head_projections(8, heads, d_head)


def test_multi_head_attention_shape(maps):
    assert maps.shape == (4, 6, 6)


def test_multi_head_attention_rows_sum_to_one(maps):
    assert np.allclose(maps.sum(axis=2), 1.0)


def test_multi_head_attention_is_non_negative(maps):
    assert (maps >= 0).all()


def test_multi_head_attention_is_finite(maps):
    assert np.isfinite(maps).all()


def test_multi_head_attention_is_deterministic(first_matrix):
    first = multi_head_attention(first_matrix, n_heads=3, seed=5)
    second = multi_head_attention(first_matrix, n_heads=3, seed=5)
    assert np.array_equal(first, second)


def test_multi_head_attention_seed_matters(first_matrix):
    first = multi_head_attention(first_matrix, n_heads=2, seed=5)
    other = multi_head_attention(first_matrix, n_heads=2, seed=6)
    assert not np.array_equal(first, other)


def test_multi_head_attention_causal_zeroes_the_future(first_matrix):
    maps = multi_head_attention(first_matrix, n_heads=2, seed=5, causal=True)
    upper = np.triu_indices(maps.shape[1], k=1)
    assert np.allclose(maps[:, upper[0], upper[1]], 0.0)
    assert np.allclose(maps.sum(axis=2), 1.0)


def test_multi_head_attention_rejects_1d():
    with pytest.raises(AttentionError, match="must be 2-D"):
        multi_head_attention(np.zeros(4))


def test_multi_head_attention_rejects_empty():
    with pytest.raises(AttentionError, match="empty"):
        multi_head_attention(np.zeros((0, 4)))


# --------------------------------------------------------------------------- #
# Interpretability
# --------------------------------------------------------------------------- #
def test_row_entropy_of_uniform_rows():
    matrix = np.full((3, 4), 0.25)
    assert row_entropy(matrix) == pytest.approx(2.0)


def test_row_entropy_of_one_hot_rows():
    matrix = np.eye(4)
    assert row_entropy(matrix) == pytest.approx(0.0)


def test_row_entropy_accepts_unnormalised_rows():
    matrix = np.array([[1.0, 1.0, 1.0, 1.0]])
    assert row_entropy(matrix) == pytest.approx(2.0)


def test_row_entropy_rejects_negative_weights():
    with pytest.raises(AttentionError, match="non-negative"):
        row_entropy(np.array([[1.0, -1.0]]))


def test_row_entropy_rejects_zero_rows():
    with pytest.raises(AttentionError, match="positive value"):
        row_entropy(np.zeros((2, 3)))


def test_row_entropy_rejects_1d():
    with pytest.raises(AttentionError, match="non-empty 2-D"):
        row_entropy(np.zeros(3))


def test_normalized_entropy_of_uniform_is_one():
    assert normalized_entropy(np.full((2, 8), 1 / 8)) == pytest.approx(1.0)


def test_normalized_entropy_needs_two_columns():
    with pytest.raises(AttentionError, match="at least two columns"):
        normalized_entropy(np.ones((3, 1)))


def test_head_diversity_of_identical_heads_is_zero():
    head = np.full((1, 4, 4), 0.25)
    assert head_diversity(np.repeat(head, 3, axis=0)) == pytest.approx(0.0)


def test_head_diversity_of_different_heads_is_positive():
    maps = np.stack([np.eye(4), np.full((4, 4), 0.25)])
    assert head_diversity(maps) > 0


def test_head_diversity_needs_two_heads():
    with pytest.raises(AttentionError, match="at least two heads"):
        head_diversity(np.zeros((1, 3, 3)))


def test_head_diversity_needs_3d():
    with pytest.raises(AttentionError, match=r"\(heads, rows, cols\)"):
        head_diversity(np.zeros((3, 3)))


def test_top_attended_returns_k_pairs(maps, sentences):
    tokens = sentences[0].tokens
    leaders = top_attended(maps[0], tokens, row=1, k=3)
    assert len(leaders) == 3
    assert all(token in tokens for token, _ in leaders)


def test_top_attended_is_sorted(maps, sentences):
    tokens = sentences[0].tokens
    weights = [weight for _, weight in
               top_attended(maps[0], tokens, row=0, k=4)]
    assert weights == sorted(weights, reverse=True)


def test_top_attended_clamps_k(maps, sentences):
    tokens = sentences[0].tokens
    assert len(top_attended(maps[0], tokens, row=0, k=99)) == len(tokens)


@pytest.mark.parametrize("row,k,needle", [
    (99, 2, "out of range"),
    (0, 0, "k must be >= 1"),
])
def test_top_attended_validates(maps, sentences, row, k, needle):
    with pytest.raises(AttentionError, match=needle):
        top_attended(maps[0], sentences[0].tokens, row=row, k=k)


def test_top_attended_rejects_token_mismatch(maps):
    with pytest.raises(AttentionError, match="tokens must match"):
        top_attended(maps[0], ["only"], row=0)


def test_top_attended_rejects_non_square():
    with pytest.raises(AttentionError, match="must be square"):
        top_attended(np.zeros((2, 3)), ["a", "b"], row=0)


def test_ascii_heatmap_rows(maps):
    lines = ascii_heatmap(maps[0])
    assert len(lines) == maps.shape[1]
    assert all(set(line) <= set(HEAT_CHARS) for line in lines)


def test_ascii_heatmap_label_is_first_line(maps):
    lines = ascii_heatmap(maps[0], label="head 0")
    assert lines[0] == "head 0"
    assert len(lines) == maps.shape[1] + 1


def test_ascii_heatmap_rejects_1d():
    with pytest.raises(AttentionError, match="must be 2-D"):
        ascii_heatmap(np.zeros(3))


def test_ascii_heatmap_rejects_empty():
    with pytest.raises(AttentionError, match="empty"):
        ascii_heatmap(np.zeros((0, 0)))


def test_ascii_heatmap_rejects_zero_matrix():
    with pytest.raises(AttentionError, match="positive value"):
        ascii_heatmap(np.zeros((2, 2)))


def test_analyse_reports_every_head(sentences, embedded):
    embeddings, vocab = embedded
    result = analyse(sentences[1], vocab, embeddings, n_heads=3, seed=2)
    assert result["heads"] == 3
    assert len(result["entropy"]) == 3
    assert result["maps"].shape == (3, len(result["tokens"]),
                                    len(result["tokens"]))


def test_analyse_entropy_within_bounds(sentences, embedded):
    embeddings, vocab = embedded
    result = analyse(sentences[2], vocab, embeddings, seed=1)
    ceiling = math.log2(len(result["tokens"]))
    assert all(0.0 <= value <= ceiling + 1e-9 for value in result["entropy"])


def test_to_dict_drops_maps(sentences, embedded):
    embeddings, vocab = embedded
    payload = to_dict(analyse(sentences[0], vocab, embeddings))
    assert "maps" not in payload
    json.dumps(payload)


# --------------------------------------------------------------------------- #
# Demo and CLI
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


def test_cli_analyses_the_store(capsys):
    assert main(["--texts", str(TEXTS), "--heads", "3"]) == 0
    out = capsys.readouterr().out
    assert "Vocabulary" in out
    assert "diversity" in out


def test_cli_selects_one_sentence(capsys):
    assert main(["--texts", str(TEXTS), "--sentence", "s2"]) == 0
    out = capsys.readouterr().out
    assert "s2" in out
    assert "s1" not in out


def test_cli_unknown_sentence(capsys):
    assert main(["--texts", str(TEXTS), "--sentence", "s99"]) == 2
    assert "no sentence with id" in capsys.readouterr().err


@pytest.mark.parametrize("heads", ["0", "17"])
def test_cli_validates_heads(heads, capsys):
    assert main(["--texts", str(TEXTS), "--heads", heads]) == 2
    assert "heads must be in 1..16" in capsys.readouterr().err


def test_cli_missing_store(tmp_path, capsys):
    assert main(["--texts", str(tmp_path / "nope.json")]) == 2
    assert "text store not found" in capsys.readouterr().err


def test_cli_json_export(tmp_path, capsys):
    out = tmp_path / "run.json"
    assert main(["--texts", str(TEXTS), "--heads", "2", "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["heads"] == 2
    assert len(payload["sentences"]) == 4
    assert "maps" not in payload["sentences"][0]
    assert capsys.readouterr().out == ""


def test_bundled_store_is_present():
    assert TEXTS_FILE.is_file()
    assert DEFAULT_HEADS == 4
