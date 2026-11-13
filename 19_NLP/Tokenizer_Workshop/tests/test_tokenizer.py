"""Tests for the Tokenizer Workshop project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tokenizer import (  # noqa: E402
    DEFAULT_CORPUS,
    DEFAULT_STOPWORDS,
    SUFFIX_RULES,
    TokenError,
    TokenizeResult,
    load_corpus,
    load_stopwords,
    ngrams,
    normalize,
    process,
    remove_stopwords,
    render_report,
    run_demo,
    stem,
    token_stats,
    tokenize,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Normalization and tokenization
# --------------------------------------------------------------------------- #
def test_normalize_lowercases_collapses_and_handles_empty():
    assert normalize("  Hello   WORLD\there ") == "hello world here"
    assert normalize("   ") == ""
    assert normalize("plain") == "plain"


def test_normalize_folds_fancy_unicode():
    assert normalize("it\u2019s a \u201cquote\u201d \u2014 ok") == \
        "it's a \"quote\" - ok"


def test_normalize_and_tokenize_reject_non_string():
    with pytest.raises(TokenError, match="must be a string"):
        normalize(123)
    with pytest.raises(TokenError, match="must be a string"):
        tokenize(None)


def test_tokenize_basic_words():
    assert tokenize("The cat sat.") == ["the", "cat", "sat"]
    assert tokenize("") == []
    assert tokenize("   !!? ") == []


def test_tokenize_keeps_apostrophes_and_hyphens():
    assert tokenize("don't try state-of-the-art") == \
        ["don't", "try", "state-of-the-art"]


def test_tokenize_number_handling():
    text = "about 42 items in 2025"
    assert "42" in tokenize(text)
    assert tokenize(text, keep_numbers=False) == ["about", "items", "in"]


def test_tokenize_min_length_filters_and_rejects_bad_values():
    assert tokenize("a an ant", min_length=2) == ["an", "ant"]
    assert tokenize("a an ant", min_length=3) == ["ant"]
    with pytest.raises(TokenError, match="min_length must be >= 1"):
        tokenize("hi", min_length=0)


# --------------------------------------------------------------------------- #
# Stopwords
# --------------------------------------------------------------------------- #
def test_load_stopwords_bundled():
    stops = load_stopwords(DEFAULT_STOPWORDS)
    assert len(stops) >= 100
    assert {"the", "of", "and"} <= stops
    assert all(w == w.lower() and w.isalpha() for w in stops)


def test_load_stopwords_missing_file(tmp_path):
    with pytest.raises(TokenError, match="stopword file not found"):
        load_stopwords(tmp_path / "nope.txt")


def test_load_stopwords_rejects_bad_entries(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("\n\n", encoding="utf-8")
    with pytest.raises(TokenError, match="no stopwords found"):
        load_stopwords(empty)

    upper = tmp_path / "upper.txt"
    upper.write_text("the\nAnd\n", encoding="utf-8")
    with pytest.raises(TokenError, match="lowercase alphabetic"):
        load_stopwords(upper)


def test_remove_stopwords_keeps_order():
    tokens = ["the", "quick", "of", "fox"]
    kept = remove_stopwords(tokens, {"the", "of"})
    assert kept == ["quick", "fox"]
    assert remove_stopwords(tokens, {"zebra"}) == tokens


def test_remove_stopwords_rejects_empty_stops():
    with pytest.raises(TokenError, match="non-empty"):
        remove_stopwords(["a"], set())


# --------------------------------------------------------------------------- #
# Stemming
# --------------------------------------------------------------------------- #
def test_stem_known_words():
    expected = {
        "running": "run",
        "cats": "cat",
        "studies": "study",
        "cities": "city",
        "walked": "walk",
        "quickly": "quick",
        "happiness": "happi",
        "classes": "class",
        "class": "class",
        "national": "nation",
        "agreements": "agreement",
        "RUNNING": "run",
    }
    for token, want in expected.items():
        assert stem(token) == want, f"stem({token!r})"


def test_stem_collapses_doubles_but_never_ss():
    assert stem("stopped") == "stop"
    assert stem("calling") == "call"
    assert stem("processed") == "process"


def test_stem_never_lengthens_token():
    for word in ["running", "cats", "studies", "walked", "quickly",
                 "tokenizer", "language", "dictionaries", "verbs"]:
        assert stem(word)
        assert len(stem(word)) <= len(word)


def test_stem_rejects_bad_tokens():
    with pytest.raises(TokenError, match="alphabetic token"):
        stem("")
    with pytest.raises(TokenError, match="alphabetic token"):
        stem("cat2")
    with pytest.raises(TokenError, match="alphabetic token"):
        stem(42)


def test_suffix_rules_are_ordered_and_valid():
    assert SUFFIX_RULES, "suffix rules must not be empty"
    seen: set[str] = set()
    for suffix, replacement, min_length, exclusions in SUFFIX_RULES:
        assert suffix and suffix not in seen
        seen.add(suffix)
        assert isinstance(replacement, str)
        assert min_length >= len(suffix)
        assert all(isinstance(e, str) and e for e in exclusions)


# --------------------------------------------------------------------------- #
# N-grams
# --------------------------------------------------------------------------- #
def test_ngrams_sizes():
    assert ngrams(["a", "b", "c"], 2) == [("a", "b"), ("b", "c")]
    assert ngrams(["a", "b", "c"], 3) == [("a", "b", "c")]
    assert ngrams(["a", "b"], 1) == [("a",), ("b",)]


def test_ngrams_n_larger_than_tokens_returns_empty():
    assert ngrams(["a", "b"], 5) == []


def test_ngrams_rejects_bad_n():
    with pytest.raises(TokenError, match="n must be >= 1"):
        ngrams(["a"], 0)


def test_ngrams_rejects_empty_token():
    with pytest.raises(TokenError, match="non-empty strings"):
        ngrams(["a", ""], 2)


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def test_token_stats_counts():
    stats = token_stats(["the", "cat", "the", "dog"], top=1)
    assert stats["total"] == 4
    assert stats["unique"] == 3
    assert stats["top"] == [("the", 2)]
    assert stats["longest"] == "the"  # length tie broken alphabetically


def test_token_stats_top_sorted_by_count_then_alphabet():
    stats = token_stats(["b", "a", "c", "a", "b", "d"], top=4)
    assert stats["top"] == [("a", 2), ("b", 2), ("c", 1), ("d", 1)]


def test_token_stats_lengths_and_digit_counts():
    stats = token_stats(["ab", "12", "xyz"])
    assert stats["avg_length"] == pytest.approx(7 / 3, abs=0.001)
    assert stats["digit_tokens"] == 1
    assert stats["alpha_tokens"] == 2
    assert stats["longest"] == "xyz"
    assert stats["shortest"] == "12"  # '1' sorts before 'a'


def test_token_stats_rejects_bad_inputs():
    with pytest.raises(TokenError, match="top must be >= 1"):
        token_stats(["a"], top=0)
    with pytest.raises(TokenError, match="no tokens"):
        token_stats([])


# --------------------------------------------------------------------------- #
# Bundled corpus
# --------------------------------------------------------------------------- #
def test_load_corpus_bundled():
    text = load_corpus(DEFAULT_CORPUS)
    assert len(text) > 1500
    assert text == text.strip()
    assert len(text.splitlines()) >= 10


def test_load_corpus_missing_file(tmp_path):
    with pytest.raises(TokenError, match="corpus file not found"):
        load_corpus(tmp_path / "nope.txt")


def test_load_corpus_blank_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("\n  \n", encoding="utf-8")
    with pytest.raises(TokenError, match="no non-empty lines"):
        load_corpus(path)


def test_bundled_corpus_supports_the_demo_assertions():
    text = load_corpus(DEFAULT_CORPUS).lower()
    stops = load_stopwords(DEFAULT_STOPWORDS)
    tokens = tokenize(text)
    assert len(tokens) > 100
    assert any(t in stops for t in tokens), "corpus needs stopwords"
    assert "running" in tokens and "cats" in tokens and "studies" in tokens


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def test_process_fields():
    result = process("The cats are running quickly.", n=2)
    assert isinstance(result, TokenizeResult)
    assert result.normalized == "the cats are running quickly."
    assert result.removed == len(result.tokens) - len(result.kept)
    assert "the" not in result.kept
    assert "running" in result.kept
    assert len(result.grams) == max(len(result.kept) - 1, 0)
    assert result.stems[result.kept.index("running")] == "run"


def test_process_is_deterministic_and_serializable():
    text = load_corpus(DEFAULT_CORPUS)
    first = process(text, n=3)
    second = process(text, n=3)
    assert first.to_dict() == second.to_dict()
    assert first.grams == second.grams
    payload = json.loads(json.dumps(first.to_dict()))
    assert payload["n"] == 3
    assert isinstance(payload["top_tokens"], list)


def test_process_without_stopwords_keeps_everything():
    result = process("the cat of the dog", use_stopwords=False)
    assert result.kept == result.tokens
    assert result.removed == 0


def test_process_rejects_empty_text():
    with pytest.raises(TokenError, match="no tokens"):
        process("")


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections():
    report = render_report(process("The quick brown fox jumps."))
    assert "TOKENIZER WORKSHOP" in report
    assert "Raw tokens" in report
    assert "Top tokens" in report
    assert "Token -> stem:" in report


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK:" in out
    assert "stopwords removed" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_corpus(tmp_path):
    with pytest.raises(TokenError, match="bundled corpus"):
        run_demo(corpus_path=tmp_path / "nope.txt")


def test_run_demo_accepts_custom_bundled_files(tmp_path):
    corpus = tmp_path / "corpus.txt"
    corpus.write_text("The dogs are running quickly while the cats chase "
                      "small mice in the garden.\n", encoding="utf-8")
    stops = tmp_path / "stops.txt"
    stops.write_text("are\n", encoding="utf-8")
    assert run_demo(corpus_path=corpus, stopwords_path=stops) == 0


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


def test_cli_file_mode(capsys):
    assert main(["--file", str(DEFAULT_CORPUS)]) == 0
    out = capsys.readouterr().out
    assert "TOKENIZER WORKSHOP" in out and "Done." in out


def test_cli_text_mode(capsys):
    assert main(["--text", "The cats are running quickly"]) == 0
    assert "After stopwords" in capsys.readouterr().out


def test_cli_text_with_options(capsys):
    assert main(["--text", "the 7 cats", "--n", "2", "--no-stopwords",
                 "--drop-numbers", "--top", "3", "--quiet"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_cli_json_output(tmp_path):
    payload_path = tmp_path / "stats.json"
    assert main(["--text", "one two two three", "--json",
                 str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["raw_tokens"] == 4
    assert payload["unique_kept"] == 3


def test_cli_missing_file_returns_two(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.txt"), "--quiet"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_text_and_file_conflict():
    with pytest.raises(SystemExit) as excinfo:
        main(["--file", "x.txt", "--text", "hello"])
    assert excinfo.value.code == 2


def test_cli_empty_text_fails_fast(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--text", "   "])
    assert excinfo.value.code == 2
    assert "not be empty" in capsys.readouterr().err


def test_cli_bad_flags_fail_fast(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--text", "hello", "--n", "0"])
    assert excinfo.value.code == 2
    assert "--n must be >= 1" in capsys.readouterr().err

    with pytest.raises(SystemExit) as excinfo:
        main(["--text", "hello", "--min-length", "-1"])
    assert excinfo.value.code == 2
    assert "--min-length must be >= 1" in capsys.readouterr().err


def test_cli_requires_an_action(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
    assert "--demo --file --text" in capsys.readouterr().err


def test_project_ships_bundled_data():
    assert DEFAULT_CORPUS.is_file()
    assert DEFAULT_STOPWORDS.is_file()
    assert DEFAULT_CORPUS.parent == PROJECT_ROOT / "data"
