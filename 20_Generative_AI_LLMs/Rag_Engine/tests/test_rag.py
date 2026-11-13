"""Tests for the RAG Engine project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from rag import (  # noqa: E402
    DEFAULT_TOP_K,
    DOCS_FILE,
    GOLD_QUERIES,
    HASH_DIM,
    MAX_TOP_K,
    REQUIRED_IDS,
    Document,
    HashingEmbedder,
    RagError,
    answer,
    build_index,
    cosine,
    evaluate,
    extract_answer,
    load_documents,
    run_demo,
    search,
    stem,
    stem_tokens,
    to_dict,
    tokenize,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORE = PROJECT_ROOT / "data" / "documents.jsonl"

SAMPLE = [
    Document(id="d-one", title="Alpha", text="Alpha handles the blue task. "
             "It is fast and simple."),
    Document(id="d-two", title="Beta", text="Beta handles the green task. "
             "It is slow but careful."),
]


@pytest.fixture(scope="module")
def documents() -> list[Document]:
    return load_documents(STORE)


@pytest.fixture(scope="module")
def index(documents):
    return build_index(documents)


# --------------------------------------------------------------------------- #
# Loading documents
# --------------------------------------------------------------------------- #
def test_load_documents_returns_every_row(documents):
    assert len(documents) == 9
    assert {doc.id for doc in documents} == REQUIRED_IDS


def test_load_documents_fields_are_populated(documents):
    for doc in documents:
        assert doc.id and doc.title and doc.text
        assert doc.sentences


def test_load_documents_missing_file(tmp_path):
    with pytest.raises(RagError, match="document store not found"):
        load_documents(tmp_path / "ghost.jsonl")


def test_load_documents_rejects_bad_json(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(RagError, match="not valid JSON"):
        load_documents(path)


def test_load_documents_rejects_missing_field(tmp_path):
    path = tmp_path / "short.jsonl"
    path.write_text(json.dumps({"id": "x", "title": "T"}) + "\n",
                    encoding="utf-8")
    with pytest.raises(RagError, match="missing"):
        load_documents(path)


def test_load_documents_rejects_duplicate_ids(tmp_path):
    row = {"id": "same", "title": "T", "text": "Some text here."}
    path = tmp_path / "dupe.jsonl"
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n",
                    encoding="utf-8")
    with pytest.raises(RagError, match="duplicate document id"):
        load_documents(path)


def test_load_documents_rejects_empty_text(tmp_path):
    row = {"id": "blank", "title": "T", "text": "   "}
    path = tmp_path / "blank.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(RagError, match="empty text"):
        load_documents(path)


def test_load_documents_rejects_empty_store(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("\n\n", encoding="utf-8")
    with pytest.raises(RagError, match="store is empty"):
        load_documents(path)


def test_load_documents_skips_blank_lines(tmp_path):
    row = {"id": "one", "title": "T", "text": "One sentence."}
    path = tmp_path / "mixed.jsonl"
    path.write_text(json.dumps(row) + "\n\n" + json.dumps(
        {"id": "two", "title": "U", "text": "Two sentence."}) + "\n",
        encoding="utf-8")
    assert len(load_documents(path)) == 2


def test_document_sentences_split_on_punctuation():
    doc = Document(id="d", title="T", text="One. Two! Three?")
    assert doc.sentences == ["One.", "Two!", "Three?"]


def test_document_to_dict_omits_text():
    doc = Document(id="d", title="T", text="Body.")
    assert doc.to_dict() == {"id": "d", "title": "T"}


# --------------------------------------------------------------------------- #
# Tokenisation and stemming
# --------------------------------------------------------------------------- #
def test_tokenize_lowercases_and_drops_stopwords():
    assert tokenize("The Kettle and the Lamp") == ["kettle", "lamp"]


def test_tokenize_keeps_digits():
    assert tokenize("version 3 of python") == ["version", "3", "python"]


def test_tokenize_empty_string():
    assert tokenize("") == []


def test_tokenize_rejects_non_string():
    with pytest.raises(RagError, match="text must be a string"):
        tokenize(None)


def test_tokenize_drops_all_stopwords():
    assert tokenize("the and of to") == []


@pytest.mark.parametrize("word,expected", [
    ("isolated", "isolat"),
    ("isolate", "isolat"),
    ("dependencies", "dependency"),
    ("decorators", "decorator"),
    ("testing", "test"),
])
def test_stem_collapses_common_suffixes(word, expected):
    assert stem(word) == expected


def test_stem_leaves_short_words_alone():
    assert stem("is") == "is"
    assert stem("dog") == "dog"


def test_stem_does_not_strip_double_s():
    assert stem("press").endswith("ss")


def test_stem_tokens_is_a_list_map():
    assert stem_tokens(["values", "wrapping"]) == ["valu", "wrapp"]


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def test_embedder_learns_idf_for_every_term():
    embedder = HashingEmbedder(dim=64).fit([["a", "b"], ["a", "c"]])
    assert set(embedder.idf) == {"a", "b", "c"}
    assert embedder.idf["a"] < embedder.idf["b"]


def test_embedder_rejects_empty_corpus():
    with pytest.raises(RagError, match="empty corpus"):
        HashingEmbedder(dim=64).fit([])


def test_embedder_rejects_tiny_dimension():
    with pytest.raises(RagError, match="dim must be at least 8"):
        HashingEmbedder(dim=4).fit([["a"]])


def test_embedder_vectors_are_unit_length():
    embedder = HashingEmbedder(dim=128).fit([["alpha", "beta", "gamma"]])
    vector = embedder.transform(["alpha", "beta"])
    norm = sum(value * value for value in vector) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-9)


def test_embedder_empty_tokens_gives_zero_vector():
    embedder = HashingEmbedder(dim=16).fit([["a"]])
    assert embedder.transform([]) == [0.0] * 16


def test_embedder_is_deterministic():
    first = HashingEmbedder(dim=64).fit([["a", "b", "c"]]).transform(["a", "b"])
    second = HashingEmbedder(dim=64).fit([["a", "b", "c"]]).transform(["a", "b"])
    assert first == second


def test_embedder_dimension_matches_request():
    embedder = HashingEmbedder(dim=32).fit([["a"]])
    assert len(embedder.transform(["a"])) == 32


def test_cosine_identical_vectors_is_one():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors_is_zero():
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_zero_vector_is_zero():
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_rejects_length_mismatch():
    with pytest.raises(RagError, match="same length"):
        cosine([1.0], [1.0, 2.0])


# --------------------------------------------------------------------------- #
# Index and retrieval
# --------------------------------------------------------------------------- #
def test_build_index_reports_size_and_vocabulary(index, documents):
    assert index.size == len(documents)
    assert index.vocabulary > 100
    assert len(index.vectors) == index.size


def test_build_index_uses_default_dimension(index):
    assert index.embedder.dim == HASH_DIM


def test_build_index_requires_documents():
    with pytest.raises(RagError, match="zero documents"):
        build_index([])


def test_search_returns_top_k(index):
    assert len(search(index, "python packages", top_k=2)) == 2


def test_search_defaults_to_three(index):
    assert len(search(index, "python packages")) == DEFAULT_TOP_K


def test_search_scores_are_sorted(index):
    scores = [score for _, score in search(index, "list comprehension", 5)]
    assert scores == sorted(scores, reverse=True)


def test_search_finds_the_right_document(index):
    assert search(index, "pytest fixtures", 1)[0][0].id == "doc-pytest"


def test_search_is_deterministic(index):
    first = search(index, "yield iterator", 4)
    assert first == search(index, "yield iterator", 4)


@pytest.mark.parametrize("query", ["", "   "])
def test_search_rejects_empty_query(index, query):
    with pytest.raises(RagError, match="query is empty"):
        search(index, query)


def test_search_rejects_stopword_only_query(index):
    with pytest.raises(RagError, match="no searchable tokens"):
        search(index, "the and of")


@pytest.mark.parametrize("top_k", [0, -1, MAX_TOP_K + 1])
def test_search_rejects_bad_top_k(index, top_k):
    with pytest.raises(RagError, match="top_k must be in"):
        search(index, "python", top_k=top_k)


# --------------------------------------------------------------------------- #
# Answering
# --------------------------------------------------------------------------- #
def test_extract_answer_returns_a_sentence_of_the_document():
    doc = Document(id="d", title="T",
                   text="First remark here. Second idea lives here.")
    assert extract_answer("second idea", doc) in doc.sentences


def test_extract_answer_prefers_overlap():
    doc = Document(id="d", title="T",
                   text="Cats sleep a lot. Generators yield lazily.")
    assert "yield" in extract_answer("generator yields", doc)


def test_extract_answer_rejects_stopword_query():
    doc = Document(id="d", title="T", text="Only one sentence.")
    with pytest.raises(RagError, match="no searchable tokens"):
        extract_answer("the of", doc)


def test_extract_answer_rejects_empty_document():
    doc = Document(id="d", title="T", text="")
    with pytest.raises(RagError, match="no usable sentences"):
        extract_answer("anything", doc)


def test_answer_cites_the_best_document(index):
    result = answer(index, "how do I isolate dependencies for a project")
    assert result["citations"][0] == "doc-venv"
    assert result["hits"][0]["id"] == "doc-venv"
    assert result["score"] > 0.2


def test_answer_quote_comes_from_the_cited_document(index, documents):
    result = answer(index, "parse command line flags")
    source = next(doc for doc in documents if doc.id == result["citations"][0])
    assert result["answer"] in source.text


def test_answer_lists_every_citation(index):
    result = answer(index, "decorator wraps a function", top_k=4)
    assert len(result["citations"]) == 4
    assert len(result["hits"]) == 4


def test_answer_unknown_query_has_no_citation(index):
    result = answer(index, "quantum chromodynamics lattice gauge")
    assert result["citations"] == [] or result["score"] < 0.5


def test_answer_is_json_serialisable(index):
    payload = to_dict(answer(index, "dictionary lookup"))
    json.dumps(payload)
    assert payload["query"] == "dictionary lookup"


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def test_evaluate_scores_every_gold_query(index):
    report = evaluate(index)
    assert report["queries"] == len(GOLD_QUERIES)
    assert len(report["rows"]) == len(GOLD_QUERIES)


def test_evaluate_retrieves_the_expected_document(index):
    report = evaluate(index)
    assert report["accuracy_at_1"] == 1.0
    assert report["mrr"] == 1.0


def test_evaluate_accepts_custom_gold(index):
    report = evaluate(index, {"doc-venv": "virtual environment"})
    assert report["queries"] == 1
    assert report["rows"][0]["rank"] == 1


def test_evaluate_records_top_hit(index):
    for row in evaluate(index)["rows"]:
        assert row["top"] == row["expected"]


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


def test_cli_answers_a_query(capsys):
    assert main(["--documents", str(STORE),
                 "--query", "virtual environment"]) == 0
    out = capsys.readouterr().out
    assert "doc-venv" in out
    assert "Answer" in out


@pytest.mark.parametrize("args,needle", [
    (["--top-k", "0"], "top_k must be in"),
    (["--top-k", str(MAX_TOP_K + 1)], "top_k must be in"),
    (["--query", "   "], "--query is required"),
])
def test_cli_validates_flags(args, needle, capsys):
    base = ["--documents", str(STORE)]
    query = [] if "--query" in args else ["--query", "python"]
    code = main(base + query + args)
    assert code == 2
    assert needle in capsys.readouterr().err


def test_cli_missing_query(capsys):
    assert main(["--documents", str(STORE)]) == 2
    assert "--query is required" in capsys.readouterr().err


def test_cli_missing_store(tmp_path, capsys):
    assert main(["--documents", str(tmp_path / "nope.jsonl"),
                 "--query", "python"]) == 2
    assert "document store not found" in capsys.readouterr().err


def test_cli_json_export(tmp_path, capsys):
    out = tmp_path / "result.json"
    assert main(["--documents", str(STORE), "--query", "pytest fixtures",
                 "--top-k", "3", "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["documents"] == 9
    assert payload["citations"][0] == "doc-pytest"
    assert payload["evaluation"] == 1.0
    assert capsys.readouterr().out == ""


def test_bundled_store_has_unique_ids(documents):
    ids = [doc.id for doc in documents]
    assert len(ids) == len(set(ids))
    assert DOCS_FILE.is_file()
