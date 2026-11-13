"""Text summarizer: TF-IDF extractive sentence ranking - fully offline.

Splits an article into sentences with a rule-based splitter, scores every
sentence by its cosine similarity to the document TF-IDF centroid, and keeps
the top-ranked sentences as the summary. Compression metrics and top-term
coverage are reported. Local files only - no network, no downloads.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_ARTICLES = Path(__file__).resolve().parent.parent / "data" / "articles.json"
MIN_ARTICLE_CHARS = 150

# Abbreviations whose final dot is not a sentence boundary.
_ABBREVIATIONS = ("mr", "mrs", "ms", "dr", "prof", "st", "jr", "sr",
                  "no", "vs", "etc", "inc", "lld", "fig")
_ABBR_RE = re.compile(
    r"\b(" + "|".join(re.escape(a) for a in _ABBREVIATIONS) + r")\.",
    re.IGNORECASE)
_MULTI_ABBR_RE = re.compile(r"\b(e\.g|i\.e|u\.s|a\.d)\.", re.IGNORECASE)
_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-z]+|\d+")
_PROTECT = "\x00"


class SummaryError(RuntimeError):
    """Raised for missing files, bad schemas, and invalid summarizer options."""


# --------------------------------------------------------------------------- #
# Sentence splitting and tokenization
# --------------------------------------------------------------------------- #
def split_sentences(text: str) -> list[str]:
    """Rule-based splitter: punctuation boundaries, abbreviations protected."""
    if not isinstance(text, str):
        raise SummaryError(
            f"text must be a string, got {type(text).__name__}")
    if not text.strip():
        raise SummaryError("text must not be empty")

    protected = _ABBR_RE.sub(
        lambda m: m.group(1) + _PROTECT, text)
    protected = _MULTI_ABBR_RE.sub(
        lambda m: m.group(1) + _PROTECT, protected)
    parts = _BOUNDARY_RE.split(protected)
    sentences = [p.replace(_PROTECT, ".").strip() for p in parts]
    sentences = [s for s in sentences if s]
    if not sentences:
        raise SummaryError("no sentences found in the text")
    return sentences


def tokenize(text: str) -> list[str]:
    """Lowercase word/number tokens for TF-IDF."""
    return _WORD_RE.findall(text.lower())


# --------------------------------------------------------------------------- #
# TF-IDF and sentence scoring
# --------------------------------------------------------------------------- #
def build_tfidf(sentences: list[str]) -> tuple[np.ndarray, list[str]]:
    """L2-normalised sentence x vocabulary TF-IDF matrix (smooth idf)."""
    if not sentences:
        raise SummaryError("need at least one sentence")
    for sentence in sentences:
        if not isinstance(sentence, str) or not sentence.strip():
            raise SummaryError("sentences must be non-empty strings")

    documents = [tokenize(s) for s in sentences]
    vocabulary = sorted({word for doc in documents for word in doc})
    if not vocabulary:
        raise SummaryError("no words found in the text")
    index = {word: i for i, word in enumerate(vocabulary)}

    counts = np.zeros((len(documents), len(vocabulary)), dtype=float)
    for row, doc in enumerate(documents):
        for word in doc:
            counts[row, index[word]] += 1.0

    n_docs = float(len(documents))
    document_frequency = (counts > 0).sum(axis=0).astype(float)
    idf = np.log((1.0 + n_docs) / (1.0 + document_frequency)) + 1.0
    totals = counts.sum(axis=1, keepdims=True)
    tf_idf = (counts / np.maximum(totals, 1.0)) * idf

    norms = np.linalg.norm(tf_idf, axis=1, keepdims=True)
    return tf_idf / np.maximum(norms, 1e-12), vocabulary


def score_sentences(matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of each row (sentence) with the document centroid."""
    if matrix.size == 0:
        raise SummaryError("empty TF-IDF matrix")
    centroid = matrix.mean(axis=0)
    norm = float(np.linalg.norm(centroid))
    if norm < 1e-12:
        return np.zeros(matrix.shape[0])
    return matrix @ centroid / norm


# --------------------------------------------------------------------------- #
# Article loading
# --------------------------------------------------------------------------- #
def load_articles(path: str | Path) -> list[dict]:
    """Load and validate a JSON list of {'title', 'text'} articles."""
    source = Path(path)
    if not source.is_file():
        raise SummaryError(f"article file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SummaryError(f"could not parse {source.name}: {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise SummaryError(
            f"expected a non-empty JSON list of articles in {source.name}")

    articles: list[dict] = []
    for position, item in enumerate(payload):
        if not isinstance(item, dict):
            raise SummaryError(
                f"article {position} must be an object with title and text")
        title = item.get("title")
        text = item.get("text")
        if not isinstance(title, str) or not title.strip():
            raise SummaryError(
                f"article {position}: 'title' must be a non-empty string")
        if not isinstance(text, str) or not text.strip():
            raise SummaryError(
                f"article {position}: 'text' must be a non-empty string")
        if len(text.strip()) < MIN_ARTICLE_CHARS:
            raise SummaryError(
                f"article {position}: 'text' must be at least "
                f"{MIN_ARTICLE_CHARS} characters")
        articles.append({"title": title.strip(), "text": text})
    return articles


# --------------------------------------------------------------------------- #
# Summarization
# --------------------------------------------------------------------------- #
@dataclass
class SummaryResult:
    """Extractive summary plus scores and compression metrics."""

    title: str
    sentences: list[str]
    selected: list[int]
    scores: list[float]
    summary: str
    ratio: float
    top_terms: list[str]
    retained_terms: list[str]
    original_chars: int
    summary_chars: int

    @property
    def sentences_total(self) -> int:
        return len(self.sentences)

    @property
    def sentences_kept(self) -> int:
        return len(self.selected)

    @property
    def compression(self) -> float:
        if self.original_chars == 0:
            return 0.0
        return self.summary_chars / self.original_chars

    @property
    def coverage(self) -> float:
        if not self.top_terms:
            return 1.0
        return len(self.retained_terms) / len(self.top_terms)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "ratio": self.ratio,
            "sentences_total": self.sentences_total,
            "sentences_kept": self.sentences_kept,
            "compression": round(self.compression, 4),
            "compression_factor": round(
                self.original_chars / max(self.summary_chars, 1), 4),
            "coverage": round(self.coverage, 4),
            "top_terms": list(self.top_terms),
            "retained_terms": list(self.retained_terms),
            "selected": list(self.selected),
            "summary": self.summary,
        }


def summarize(text: str, ratio: float = 0.4,
              title: str = "Untitled") -> SummaryResult:
    """Rank sentences by centroid cosine and keep the top ceil(ratio * n)."""
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)):
        raise SummaryError(
            f"ratio must be a number in (0, 1], got {ratio!r}")
    if not 0.0 < ratio <= 1.0:
        raise SummaryError(f"ratio must be in (0, 1], got {ratio}")
    if not isinstance(title, str) or not title.strip():
        raise SummaryError("title must be a non-empty string")

    sentences = split_sentences(text)
    matrix, vocabulary = build_tfidf(sentences)
    scores = score_sentences(matrix)

    n = len(sentences)
    keep = max(1, min(n, math.ceil(float(ratio) * n)))
    ranking = sorted(range(n), key=lambda i: (-float(scores[i]), i))
    selected = sorted(ranking[:keep])
    summary = " ".join(sentences[i] for i in selected)

    # Top document terms by mean tf-idf weight (ties alphabetical).
    weights = matrix.mean(axis=0)
    order = sorted(range(len(vocabulary)),
                   key=lambda j: (-float(weights[j]), vocabulary[j]))
    top_terms = [vocabulary[j] for j in order[:10]]
    retained = set(tokenize(summary))
    retained_terms = [t for t in top_terms if t in retained]

    original_chars = len(text.strip())
    summary_chars = len(summary)
    return SummaryResult(
        title=title.strip(),
        sentences=sentences,
        selected=selected,
        scores=[float(s) for s in scores],
        summary=summary,
        ratio=float(ratio),
        top_terms=top_terms,
        retained_terms=retained_terms,
        original_chars=original_chars,
        summary_chars=summary_chars,
    )


# --------------------------------------------------------------------------- #
# Report and demo
# --------------------------------------------------------------------------- #
def render_report(result: SummaryResult) -> str:
    """Human-readable report used by the CLI and the demo."""
    lines = [
        f"ARTICLE: {result.title}",
        "-" * 68,
        f"Original : {result.sentences_total} sentences, "
        f"{result.original_chars} chars",
        f"Summary  : {result.sentences_kept} sentences, "
        f"{result.summary_chars} chars "
        f"(compression {result.compression:.2f}, "
        f"{result.original_chars / max(result.summary_chars, 1):.1f}x)",
        f"Coverage : {len(result.retained_terms)}/{len(result.top_terms)} "
        f"top terms retained ({result.coverage:.0%})",
        "",
        "Sentence scores (selected marked *):",
    ]
    selected = set(result.selected)
    for index, score in enumerate(result.scores):
        marker = "*" if index in selected else " "
        snippet = result.sentences[index][:58]
        lines.append(f" {marker} {score:.4f}  [{index}] {snippet}")
    lines += ["", "Summary:", result.summary]
    return "\n".join(lines)


def run_demo(articles_path: str | Path | None = None) -> int:
    """Summarize every bundled article - fully offline."""
    print("=" * 68)
    print(" TEXT SUMMARIZER - offline demo")
    print(" Bundled articles; TF-IDF centroid ranking; no network.")
    print("=" * 68)

    source = Path(articles_path) if articles_path else DEFAULT_ARTICLES
    if not source.is_file():
        raise SummaryError(f"bundled articles not found: {source}")
    articles = load_articles(source)
    print(f"\nLoaded {len(articles)} articles from {source.name}")

    results = []
    for article in articles:
        result = summarize(article["text"], ratio=0.4,
                           title=article["title"])
        results.append(result)
        print()
        print(render_report(result))

    # --- cross-checks the demo asserts ----------------------------------- #
    for result, article in zip(results, articles):
        assert 0 < result.sentences_kept < result.sentences_total, \
            "a ratio of 0.4 must keep a proper subset"
        assert result.selected == sorted(set(result.selected)), \
            "selected indices must be sorted and unique"
        assert all(0 <= i < result.sentences_total for i in result.selected)
        assert result.summary == " ".join(
            result.sentences[i] for i in result.selected), \
            "summary must be the selected sentences verbatim"
        assert all(s in article["text"] for s in
                   [result.sentences[i] for i in result.selected]), \
            "selected sentences must appear in the source article"
        assert 0.0 < result.compression < 1.0, "compression out of range"
        assert 0.0 <= result.coverage <= 1.0, "coverage out of range"
        assert result.coverage >= 0.6, "summary lost too many top terms"
        best_index = int(np.argmax(result.scores))
        assert best_index in result.selected, \
            "the best-scored sentence must be selected"
        again = summarize(article["text"], ratio=0.4,
                          title=article["title"])
        assert again.selected == result.selected, "not deterministic"

    # ratio = 1 keeps everything, ratio tiny keeps exactly one
    full = summarize(articles[0]["text"], ratio=1.0)
    assert full.selected == list(range(full.sentences_total))
    one = summarize(articles[0]["text"], ratio=0.01)
    assert len(one.selected) == 1
    assert one.selected[0] == int(np.argmax(one.scores))

    print("\nCross-checks OK: "
          f"{len(results)} articles summarized, subsets sorted and verbatim, "
          "compression < 1, coverage >= 0.6, best sentences selected, "
          "deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
