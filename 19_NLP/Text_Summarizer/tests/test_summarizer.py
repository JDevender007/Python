"""Tests for the Text Summarizer project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from summarizer import (  # noqa: E402
    DEFAULT_ARTICLES,
    MIN_ARTICLE_CHARS,
    SummaryError,
    SummaryResult,
    build_tfidf,
    load_articles,
    render_report,
    run_demo,
    score_sentences,
    split_sentences,
    summarize,
    tokenize,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent

NINE_SENTENCES = (
    "The orchestra tuned carefully before the concert. "
    "Rain drummed against the old roof all evening. "
    "Nobody in the audience noticed the leak at first. "
    "A violinist smiled at the cellist across the stage. "
    "The conductor raised both arms and the hall went silent. "
    "Musicians played a melody none of them had rehearsed. "
    "Somewhere backstage a door banged in the wind. "
    "Critics later called the performance unforgettable. "
    "By midnight the rain had stopped over the city."
)


# --------------------------------------------------------------------------- #
# Sentence splitting and tokenization
# --------------------------------------------------------------------------- #
def test_split_sentences_basic():
    assert split_sentences("One. Two! Three?") == \
        ["One.", "Two!", "Three?"]


def test_split_sentences_protects_abbreviations():
    text = "Dr. Alvarez spoke loudly. Everyone heard her."
    assert split_sentences(text) == ["Dr. Alvarez spoke loudly.",
                                     "Everyone heard her."]
    text = "Use fruit, e.g. apples every day. Then stop."
    assert split_sentences(text) == ["Use fruit, e.g. apples every day.",
                                     "Then stop."]


def test_split_sentences_never_emits_empty_sentences():
    text = "Hello world!!  How are you?   Fine."
    sentences = split_sentences(text)
    assert sentences == ["Hello world!!", "How are you?", "Fine."]
    assert all(sentences)


def test_split_sentences_single_sentence_and_newlines():
    assert split_sentences("just words no punctuation") == \
        ["just words no punctuation"]
    assert split_sentences("First one.\n\nSecond one.") == \
        ["First one.", "Second one."]


def test_split_sentences_rejects_bad_input():
    with pytest.raises(SummaryError, match="must be a string"):
        split_sentences(None)
    with pytest.raises(SummaryError, match="must not be empty"):
        split_sentences("   ")


def test_tokenize_words_and_numbers():
    assert tokenize("Hello WORLD 42 & the") == ["hello", "world", "42",
                                                "the"]


# --------------------------------------------------------------------------- #
# TF-IDF and scoring
# --------------------------------------------------------------------------- #
def test_tfidf_shape_and_sorted_vocabulary():
    matrix, vocabulary = build_tfidf(["red fish", "blue whale"])
    assert vocabulary == ["blue", "fish", "red", "whale"]
    assert matrix.shape == (2, 4)


def test_tfidf_idf_formula_and_normalisation():
    matrix, vocabulary = build_tfidf(["a a b", "b c"])
    assert vocabulary == ["a", "b", "c"]
    n_docs, df_a, df_b, df_c = 2, 1, 2, 1
    idf = [math.log((1 + n_docs) / (1 + df)) + 1.0
           for df in (df_a, df_b, df_c)]
    tf0 = np.array([2 / 3, 1 / 3, 0.0])
    expected = tf0 * np.array(idf)
    expected /= np.linalg.norm(expected)
    assert np.allclose(matrix[0], expected)


def test_tfidf_rows_are_unit_norm():
    matrix, _ = build_tfidf(["alpha beta gamma", "beta delta",
                             "gamma delta epsilon"])
    norms = np.linalg.norm(matrix, axis=1)
    assert np.allclose(norms, 1.0)


def test_tfidf_rejects_bad_inputs():
    with pytest.raises(SummaryError, match="at least one sentence"):
        build_tfidf([])
    with pytest.raises(SummaryError, match="non-empty strings"):
        build_tfidf(["ok", ""])
    with pytest.raises(SummaryError, match="no words found"):
        build_tfidf(["!!! ... ?!"])


def test_score_sentences_prefers_central_sentence():
    sentences = ["the cat sat on the mat", "the cat sat",
                 "zebra xyzq frobnicated"]
    scores = score_sentences(build_tfidf(sentences)[0])
    assert np.all(np.isfinite(scores))
    assert float(scores[2]) < max(float(scores[0]), float(scores[1]))


def test_score_sentences_ties_and_empty_matrix():
    matrix, _ = build_tfidf(["red fish", "red fish"])
    scores = score_sentences(matrix)
    assert float(scores[0]) == float(scores[1])
    with pytest.raises(SummaryError, match="empty TF-IDF matrix"):
        score_sentences(np.zeros((0, 3)))


# --------------------------------------------------------------------------- #
# Article loading
# --------------------------------------------------------------------------- #
def test_load_bundled_articles():
    articles = load_articles(DEFAULT_ARTICLES)
    assert len(articles) == 3
    assert [a["title"] for a in articles] == [
        "The Voyager Missions", "How Coffee Is Grown",
        "The Birth of the World Wide Web"]
    assert all(len(a["text"]) >= MIN_ARTICLE_CHARS for a in articles)


def test_load_articles_missing_file(tmp_path):
    with pytest.raises(SummaryError, match="article file not found"):
        load_articles(tmp_path / "nope.json")


def test_load_articles_bad_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SummaryError, match="could not parse"):
        load_articles(path)


def test_load_articles_rejects_non_list(tmp_path):
    path = tmp_path / "obj.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(SummaryError, match="non-empty JSON list"):
        load_articles(path)


def test_load_articles_schema_validation(tmp_path):
    cases = [
        ("[123]", "must be an object"),
        ('[{"title": " ", "text": "x"}]', "title"),
        ('[{"title": "t", "text": " "}]', "text"),
        (json.dumps([{"title": "t", "text": "too short"}]),
         f"at least {MIN_ARTICLE_CHARS}"),
    ]
    for payload, expected in cases:
        path = tmp_path / "case.json"
        path.write_text(payload, encoding="utf-8")
        with pytest.raises(SummaryError, match=expected):
            load_articles(path)


# --------------------------------------------------------------------------- #
# Summarization
# --------------------------------------------------------------------------- #
def test_summarize_basic_invariants():
    result = summarize(NINE_SENTENCES, ratio=0.4, title="Orchestra")
    assert isinstance(result, SummaryResult)
    assert result.sentences_total == 9
    assert result.sentences_kept == math.ceil(0.4 * 9) == 4
    assert result.selected == sorted(set(result.selected))
    assert result.summary == " ".join(result.sentences[i]
                                      for i in result.selected)
    assert all(sentence in NINE_SENTENCES for sentence in
               [result.sentences[i] for i in result.selected])


def test_summarize_ratio_one_selects_everything():
    result = summarize(NINE_SENTENCES, ratio=1.0)
    assert result.selected == list(range(9))


def test_summarize_tiny_ratio_selects_the_best_sentence():
    result = summarize(NINE_SENTENCES, ratio=0.01)
    assert result.selected == [int(np.argmax(result.scores))]


def test_summarize_rejects_bad_ratio_and_title():
    with pytest.raises(SummaryError, match="ratio must be a number"):
        summarize(NINE_SENTENCES, ratio="high")
    with pytest.raises(SummaryError, match=r"ratio must be in \(0, 1\]"):
        summarize(NINE_SENTENCES, ratio=0)
    with pytest.raises(SummaryError, match=r"ratio must be in \(0, 1\]"):
        summarize(NINE_SENTENCES, ratio=1.5)
    with pytest.raises(SummaryError, match="title must be"):
        summarize(NINE_SENTENCES, title="  ")


def test_summarize_metrics_are_consistent():
    result = summarize(NINE_SENTENCES, ratio=0.3, title="T")
    payload = json.loads(json.dumps(result.to_dict()))
    assert payload["sentences_kept"] == 3
    assert 0.0 < payload["compression"] < 1.0
    assert payload["compression_factor"] > 1.0
    assert 0.0 <= payload["coverage"] <= 1.0
    assert payload["retained_terms"] == [
        t for t in payload["top_terms"]
        if t in set(tokenize(payload["summary"]))]
    assert 0 < len(payload["top_terms"]) <= 10


def test_summarize_is_deterministic():
    first = summarize(NINE_SENTENCES, ratio=0.5, title="T")
    second = summarize(NINE_SENTENCES, ratio=0.5, title="T")
    assert first.selected == second.selected
    assert first.summary == second.summary
    assert first.scores == second.scores


def test_render_report_sections():
    report = render_report(summarize(NINE_SENTENCES, title="Orchestra"))
    assert "ARTICLE: Orchestra" in report
    assert "Sentence scores" in report
    assert "Compression" in report or "compression" in report
    assert "Summary:" in report


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK:" in out
    assert out.count("ARTICLE:") == 3


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_articles(tmp_path):
    with pytest.raises(SummaryError, match="bundled articles"):
        run_demo(articles_path=tmp_path / "nope.json")


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


def test_cli_file_all_articles(capsys):
    assert main(["--file", str(DEFAULT_ARTICLES), "--quiet"]) == 0
    assert main(["--file", str(DEFAULT_ARTICLES)]) == 0
    out = capsys.readouterr().out
    assert out.count("ARTICLE:") == 3
    assert "Done." in out


def test_cli_file_with_index(capsys):
    assert main(["--file", str(DEFAULT_ARTICLES), "--index", "1",
                 "--ratio", "0.5"]) == 0
    out = capsys.readouterr().out
    assert "ARTICLE: How Coffee Is Grown" in out
    assert "Voyager" not in out.split("Summary:")[0].replace(
        "ARTICLE: How Coffee Is Grown", "")


def test_cli_index_out_of_range_returns_two(capsys):
    assert main(["--file", str(DEFAULT_ARTICLES), "--index", "9",
                 "--quiet"]) == 2
    assert "out of range" in capsys.readouterr().err


def test_cli_index_negative_fails_fast(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--file", str(DEFAULT_ARTICLES), "--index", "-1"])
    assert excinfo.value.code == 2
    assert "--index must be >= 0" in capsys.readouterr().err


def test_cli_text_mode(capsys):
    assert main(["--text", NINE_SENTENCES, "--ratio", "0.3"]) == 0
    out = capsys.readouterr().out
    assert "ARTICLE: Inline text" in out
    assert "Summary:" in out


def test_cli_text_empty_fails_fast(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--text", "  "])
    assert excinfo.value.code == 2
    assert "not be empty" in capsys.readouterr().err


def test_cli_bad_ratio_fails_fast(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--text", "Hi there.", "--ratio", "0"])
    assert excinfo.value.code == 2
    assert "--ratio must be in (0, 1]" in capsys.readouterr().err


def test_cli_demo_rejects_ratio_and_index(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--demo", "--ratio", "0.5"])
    assert excinfo.value.code == 2
    assert "not --demo" in capsys.readouterr().err


def test_cli_missing_file_returns_two(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.json"), "--quiet"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_json_output(tmp_path):
    payload_path = tmp_path / "summary.json"
    assert main(["--file", str(DEFAULT_ARTICLES), "--index", "0",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["title"] == "The Voyager Missions"
    assert payload["sentences_kept"] == 4


def test_cli_text_and_file_conflict():
    with pytest.raises(SystemExit) as excinfo:
        main(["--file", "x.json", "--text", "hello"])
    assert excinfo.value.code == 2


def test_cli_requires_an_action(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
    assert "--demo --file --text" in capsys.readouterr().err


def test_project_ships_bundled_data():
    assert DEFAULT_ARTICLES.is_file()
    assert DEFAULT_ARTICLES.parent == PROJECT_ROOT / "data"
