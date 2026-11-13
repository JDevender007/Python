"""A retrieval-augmented answering engine with no external services.

Documents are chunked into sentences, embedded with a deterministic
hashing TF-IDF vectoriser, and searched by cosine similarity. The best
retrieved passage is turned into an extractive answer with citations.
No network, no embeddings API, no model downloads.

Public API
----------
load_documents       read a JSONL document store
tokenize             lowercase word tokens
HashingEmbedder      deterministic hashed TF-IDF vectors
build_index          embed every document
search               cosine top-k retrieval
extract_answer       best-matching sentence from a document
answer               retrieve + extract + cite
evaluate             accuracy@1 / MRR over gold queries
run_demo             offline demo with self-checks
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCS_FILE = DATA_DIR / "documents.jsonl"

DEFAULT_TOP_K = 3
MAX_TOP_K = 9
HASH_DIM = 4096
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for",
    "from", "has", "in", "into", "is", "it", "its", "of", "on", "or", "so",
    "that", "the", "their", "then", "there", "these", "they", "this", "to",
    "use", "was", "were", "when", "which", "with", "you", "your",
}
TOKEN_RE = re.compile(r"[a-z0-9]+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
REQUIRED_IDS = {
    "doc-venv", "doc-pip", "doc-pytest", "doc-listcomp", "doc-decorators",
    "doc-generators", "doc-dicts", "doc-args", "doc-exceptions",
}
GOLD_QUERIES = {
    "doc-venv": "isolate project dependencies virtual environment activate",
    "doc-pip": "install pinned package versions requirements file",
    "doc-pytest": "test discovery fixtures assert raises exception",
    "doc-listcomp": "build a list from an iterable in one expression",
    "doc-decorators": "add behaviour without editing the function body",
    "doc-generators": "yield values lazily one at a time",
    "doc-dicts": "key value mapping lookup default",
    "doc-args": "parse command line flags positional arguments",
    "doc-exceptions": "catch an error and raise a custom one",
}


class RagError(Exception):
    """Raised for invalid input, bad flags or corrupted bundled data."""


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
@dataclass
class Document:
    id: str
    title: str
    text: str

    @property
    def sentences(self) -> list[str]:
        return [chunk.strip() for chunk in SENTENCE_RE.split(self.text)
                if chunk.strip()]

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title}


def load_documents(path: Path | str | None = None) -> list[Document]:
    target = Path(path) if path is not None else DOCS_FILE
    if not target.is_file():
        raise RagError(f"document store not found: {target}")
    documents: list[Document] = []
    seen: set[str] = set()
    for number, line in enumerate(target.read_text(encoding="utf-8")
                                  .splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RagError(f"line {number} is not valid JSON: {exc}") from exc
        missing = {"id", "title", "text"} - set(row)
        if missing:
            raise RagError(f"line {number} is missing {sorted(missing)}")
        if row["id"] in seen:
            raise RagError(f"duplicate document id: {row['id']}")
        if not row["text"].strip():
            raise RagError(f"document {row['id']} has empty text")
        seen.add(row["id"])
        documents.append(Document(id=row["id"], title=row["title"],
                                  text=row["text"]))
    if not documents:
        raise RagError(f"document store is empty: {target.name}")
    return documents


def tokenize(text: str) -> list[str]:
    if not isinstance(text, str):
        raise RagError("text must be a string")
    return [token for token in TOKEN_RE.findall(text.lower())
            if token not in STOPWORDS]


def stem(token: str) -> str:
    """Tiny suffix stripper so ``isolate``/``isolated`` and plurals agree.

    Deliberately crude: retrieval only needs the forms inside one document
    store to collapse, not linguistically correct lemmas.
    """
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        token = token[:-3] + "y"
    elif token.endswith("sses"):
        token = token[:-2]
    elif token.endswith("s") and not token.endswith(("ss", "us", "is")):
        token = token[:-1]
    if token.endswith("ing") and len(token) > 5:
        token = token[:-3]
    elif token.endswith("ed") and len(token) > 4:
        token = token[:-2]
    if token.endswith("e") and len(token) > 4:
        token = token[:-1]
    return token


def stem_tokens(tokens: list[str]) -> list[str]:
    return [stem(token) for token in tokens]


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def _bucket(token: str, dim: int) -> tuple[int, float]:
    """Stable hash -> (index, sign). md5 keeps this identical everywhere."""
    digest = hashlib.md5(token.encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "big") % dim
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return index, sign


@dataclass
class HashingEmbedder:
    """Hashed TF-IDF vectors: no vocabulary, no downloads, fully stable."""

    dim: int = HASH_DIM
    idf: dict[str, float] = field(default_factory=dict)

    def fit(self, corpus: list[list[str]]) -> "HashingEmbedder":
        if not corpus:
            raise RagError("cannot fit on an empty corpus")
        if self.dim < 8:
            raise RagError(f"dim must be at least 8, got {self.dim}")
        document_frequency: dict[str, int] = {}
        for tokens in corpus:
            for token in set(tokens):
                document_frequency[token] = document_frequency.get(token, 0) + 1
        total = len(corpus)
        self.idf = {token: math.log((1.0 + total) / (1.0 + df)) + 1.0
                    for token, df in document_frequency.items()}
        return self

    def transform(self, tokens: list[str]) -> list[float]:
        if not tokens:
            return [0.0] * self.dim
        vector = [0.0] * self.dim
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        for token, count in counts.items():
            tf = count / len(tokens)
            weight = tf * self.idf.get(token, 1.0)
            index, sign = _bucket(token, self.dim)
            vector[index] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise RagError("vectors must have the same length")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# --------------------------------------------------------------------------- #
# Index and retrieval
# --------------------------------------------------------------------------- #
@dataclass
class Index:
    documents: list[Document]
    embedder: HashingEmbedder
    vectors: list[list[float]]

    @property
    def size(self) -> int:
        return len(self.documents)

    @property
    def vocabulary(self) -> int:
        return len(self.embedder.idf)


def build_index(documents: list[Document], dim: int = HASH_DIM) -> Index:
    if not documents:
        raise RagError("cannot index zero documents")
    corpus = [stem_tokens(tokenize(f"{doc.title} {doc.text}"))
              for doc in documents]
    embedder = HashingEmbedder(dim=dim).fit(corpus)
    vectors = [embedder.transform(tokens) for tokens in corpus]
    return Index(documents=documents, embedder=embedder, vectors=vectors)


def search(index: Index, query: str, top_k: int = DEFAULT_TOP_K
           ) -> list[tuple[Document, float]]:
    if not query.strip():
        raise RagError("query is empty")
    if not 1 <= top_k <= MAX_TOP_K:
        raise RagError(f"top_k must be in 1..{MAX_TOP_K}, got {top_k}")
    tokens = stem_tokens(tokenize(query))
    if not tokens:
        raise RagError("query has no searchable tokens")
    query_vector = index.embedder.transform(tokens)
    scored = [(document, cosine(query_vector, vector))
              for document, vector in zip(index.documents, index.vectors)]
    scored.sort(key=lambda pair: (-pair[1], pair[0].id))
    return scored[:top_k]


# --------------------------------------------------------------------------- #
# Answering
# --------------------------------------------------------------------------- #
def extract_answer(query: str, document: Document) -> str:
    """Sentence in ``document`` with the highest query-token overlap."""
    query_tokens = set(stem_tokens(tokenize(query)))
    if not query_tokens:
        raise RagError("query has no searchable tokens")
    best_sentence = ""
    best_score = -1.0
    for sentence in document.sentences:
        tokens = set(stem_tokens(tokenize(sentence)))
        overlap = len(tokens & query_tokens)
        score = overlap / (1.0 + math.log(1.0 + len(tokens)))
        if score > best_score:
            best_score = score
            best_sentence = sentence
    if not best_sentence:
        raise RagError(f"document {document.id} has no usable sentences")
    return best_sentence


def answer(index: Index, query: str, top_k: int = DEFAULT_TOP_K) -> dict:
    """Retrieve, extract the supporting sentence, and cite the sources."""
    hits = search(index, query, top_k)
    best_doc, best_score = hits[0]
    if best_score <= 0:
        return {"query": query, "answer": None, "score": 0.0,
                "citations": [], "hits": []}
    passage = extract_answer(query, best_doc)
    return {
        "query": query,
        "answer": passage,
        "score": round(best_score, 4),
        "citations": [doc.id for doc, _ in hits],
        "hits": [{"id": doc.id, "title": doc.title, "score": round(score, 4)}
                 for doc, score in hits],
    }


def evaluate(index: Index, gold: dict[str, str] | None = None) -> dict:
    """Accuracy@1 and mean reciprocal rank over the gold query set."""
    pairs = gold or GOLD_QUERIES
    correct = 0
    reciprocal = 0.0
    rows = []
    for expected, query in pairs.items():
        hits = search(index, query, top_k=min(MAX_TOP_K, len(index.documents)))
        ranked = [doc.id for doc, _ in hits]
        rank = ranked.index(expected) + 1 if expected in ranked else None
        if rank == 1:
            correct += 1
        if rank:
            reciprocal += 1.0 / rank
        rows.append({"query": query, "expected": expected, "rank": rank,
                     "top": ranked[0]})
    return {
        "queries": len(pairs),
        "accuracy_at_1": round(correct / len(pairs), 4),
        "mrr": round(reciprocal / len(pairs), 4),
        "rows": rows,
    }


def to_dict(result: dict) -> dict:
    return json.loads(json.dumps(result))


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    root = data_dir or DATA_DIR
    print("=" * 64)
    print(" RAG ENGINE - offline demo")
    print(" Hashed TF-IDF retrieval + extractive answers, no services.")
    print("=" * 64)

    documents = load_documents(root / "documents.jsonl")
    ids = {doc.id for doc in documents}
    if not REQUIRED_IDS <= ids:
        raise RagError(f"bundled store is missing {sorted(REQUIRED_IDS - ids)}")
    for doc in documents:
        if len(doc.sentences) < 2:
            raise RagError(f"document {doc.id} has too little text")
    print(f"\nDocuments       : {len(documents)} loaded "
          f"({len(ids)} unique ids, bundled + validated)")

    index = build_index(documents)
    print(f"Index           : {index.size} docs, "
          f"{index.vocabulary} terms, dim {index.embedder.dim}")

    # --- retrieval quality --------------------------------------------- #
    report = evaluate(index)
    assert report["accuracy_at_1"] == 1.0, report["rows"]
    assert report["mrr"] == 1.0
    print(f"Retrieval       : accuracy@1 {report['accuracy_at_1']:.0%}, "
          f"MRR {report['mrr']:.2f} over {report['queries']} gold queries")

    # --- an answer with citations -------------------------------------- #
    result = answer(index, "how do I isolate dependencies for a project")
    assert result["citations"][0] == "doc-venv", result
    assert result["score"] > 0.2, result
    assert result["answer"] and result["answer"] in \
        next(doc.text for doc in documents if doc.id == "doc-venv")
    print(f"\nQuery           : {result['query']}")
    print(f"Answer          : {result['answer']}")
    print(f"Citations       : {', '.join(result['citations'])}")

    # --- ranking order and score bounds -------------------------------- #
    hits = search(index, "parse command line arguments", top_k=5)
    scores = [score for _, score in hits]
    assert scores == sorted(scores, reverse=True)
    assert all(-1.0 <= score <= 1.0001 for score in scores)
    assert hits[0][0].id == "doc-args", [doc.id for doc, _ in hits]
    print("Ranking         : " + ", ".join(
        f"{doc.id}={score:.3f}" for doc, score in hits[:3]))

    # --- determinism ---------------------------------------------------- #
    again = build_index(documents)
    assert again.vectors == index.vectors, "embeddings are not deterministic"
    assert search(again, "decorator wraps a function", 3) == \
        search(index, "decorator wraps a function", 3)
    print("Deterministic   : rebuilt index produces identical vectors")

    # --- empty / unknown handling --------------------------------------- #
    for bad in ("", "   "):
        try:
            search(index, bad)
        except RagError:
            pass
        else:
            raise RagError("empty queries must raise")
    unknown = answer(index, "quantum chromodynamics lattice gauge")
    assert unknown["citations"] == [] or unknown["score"] < 0.5
    print(f"Guard rails     : empty query rejected, out-of-domain score "
          f"{unknown['score']:.3f}")

    print(f"\nCross-checks OK: 9 documents validated, accuracy@1 100% on gold "
          f"queries, citation-first answering, monotone scores, "
          f"deterministic index")
    print("\nDemo completed successfully.")
    return 0
