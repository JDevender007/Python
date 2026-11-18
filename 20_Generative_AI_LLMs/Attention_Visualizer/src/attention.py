"""Multi-head self-attention from scratch, with interpretable visualisations.

Each sentence is tokenised, embedded with a PPMI co-occurrence matrix (plus
a small deterministic offset so no row is empty), projected into query/key/
value subspaces for several heads, and scored with scaled dot-product
attention. The resulting attention maps are then measured (mean entropy,
normalised entropy, head diversity) and rendered as ASCII heat maps.

No deep-learning framework, no pretrained weights, no network - NumPy only,
with the bundled sentences in data/texts.json.

Public API
----------
load_texts            read the bundled sentence store
tokenize              lowercase alphabetic tokens
build_vocab           token -> id, ordered by frequency
cooccurrence          symmetric window co-occurrence counts
ppmi                  positive pointwise mutual information
embed_tokens          PPMI rows + deterministic offset, L2 normalised
positional_encoding   sinusoidal position vectors
sentence_matrix       token ids -> embedding matrix
scaled_scores         Q K^T / sqrt(d_k)
softmax               numerically stable row-wise softmax
causal_mask           lower-triangular mask
multi_head_attention  per-head attention maps
row_entropy           mean Shannon entropy of attention rows (bits)
head_diversity        how differently the heads behave
top_attended          highest-weight tokens for one row
ascii_heatmap         attention map as text
run_demo              offline demo with self-checks
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TEXTS_FILE = DATA_DIR / "texts.json"

DEFAULT_HEADS = 4
DEFAULT_D_MODEL = 32
DEFAULT_D_HEAD = 8
WINDOW = 2
NOISE = 0.10
REQUIRED_IDS = {"s1", "s2", "s3", "s4"}
TOKEN_RE = re.compile(r"[A-Za-z']+")
HEAT_CHARS = " .:-=+*#%@"


class AttentionError(RuntimeError):
    """Raised for invalid input, bad flags or corrupted bundled data."""


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@dataclass
class Sentence:
    id: str
    text: str

    @property
    def tokens(self) -> list[str]:
        return tokenize(self.text)

    def to_dict(self) -> dict:
        return {"id": self.id, "tokens": len(self.tokens)}


def load_texts(path: Path | str | None = None) -> list[Sentence]:
    target = Path(path) if path is not None else TEXTS_FILE
    if not target.is_file():
        raise AttentionError(f"text store not found: {target}")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AttentionError(f"text store is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or "sentences" not in payload:
        raise AttentionError("text store must be an object with 'sentences'")
    rows = payload["sentences"]
    if not isinstance(rows, list) or not rows:
        raise AttentionError("'sentences' must be a non-empty list")

    sentences: list[Sentence] = []
    seen: set[str] = set()
    for position, row in enumerate(rows, start=1):
        if isinstance(row, str):
            identifier, text = f"s{position}", row
        elif isinstance(row, dict):
            if "id" not in row or "text" not in row:
                raise AttentionError(f"entry {position} needs 'id' and 'text'")
            identifier, text = str(row["id"]), row["text"]
        else:
            raise AttentionError(f"entry {position} is not an object or string")
        if not isinstance(text, str) or not text.strip():
            raise AttentionError(f"entry {position} has empty text")
        if identifier in seen:
            raise AttentionError(f"duplicate sentence id: {identifier}")
        seen.add(identifier)
        sentences.append(Sentence(id=identifier, text=text))
    return sentences


def tokenize(text: str) -> list[str]:
    if not isinstance(text, str):
        raise AttentionError("text must be a string")
    return [match.lower() for match in TOKEN_RE.findall(text)]


def build_vocab(sentences: list[Sentence]) -> dict[str, int]:
    if not sentences:
        raise AttentionError("cannot build a vocabulary from no sentences")
    counts: dict[str, int] = {}
    for sentence in sentences:
        for token in sentence.tokens:
            counts[token] = counts.get(token, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return {token: index for index, (token, _) in enumerate(ordered)}


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def cooccurrence(sentences: list[Sentence], window: int = WINDOW
                 ) -> tuple[np.ndarray, dict[str, int]]:
    """Symmetric within-sentence co-occurrence counts."""
    if window < 1:
        raise AttentionError(f"window must be >= 1, got {window}")
    vocab = build_vocab(sentences)
    size = len(vocab)
    counts = np.zeros((size, size), dtype=np.float64)
    for sentence in sentences:
        ids = [vocab[token] for token in sentence.tokens]
        for position, centre in enumerate(ids):
            low = max(0, position - window)
            high = min(len(ids), position + window + 1)
            for other in range(low, high):
                if other != position:
                    counts[centre, ids[other]] += 1.0
    return counts, vocab


def ppmi(counts: np.ndarray, smoothing: float = 1.0) -> np.ndarray:
    """Positive PMI, with negative values clipped to zero."""
    if counts.ndim != 2 or counts.shape[0] != counts.shape[1]:
        raise AttentionError("counts must be a square matrix")
    if counts.shape[0] == 0:
        raise AttentionError("counts matrix is empty")
    if smoothing <= 0:
        raise AttentionError(f"smoothing must be > 0, got {smoothing}")
    total = float(counts.sum())
    if total <= 0:
        raise AttentionError("counts matrix has no observations")
    row = counts.sum(axis=1, keepdims=True)
    column = counts.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        pmi = np.log((counts * total) / (row * column))
    pmi = np.nan_to_num(pmi, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(pmi, 0.0, None)


def _token_noise(token: str, dim: int) -> np.ndarray:
    """Deterministic, platform-stable offset for a token."""
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big") % (2 ** 32)
    return np.random.default_rng(seed).standard_normal(dim) / math.sqrt(dim)


def embed_tokens(sentences: list[Sentence], window: int = WINDOW,
                 noise: float = NOISE) -> tuple[np.ndarray, dict[str, int]]:
    """PPMI rows plus a small deterministic offset, L2-normalised."""
    if noise < 0:
        raise AttentionError(f"noise must be >= 0, got {noise}")
    counts, vocab = cooccurrence(sentences, window=window)
    matrix = ppmi(counts)
    width = matrix.shape[1]
    tokens = [None] * len(vocab)
    for token, index in vocab.items():
        tokens[index] = token
    for index, token in enumerate(tokens):
        matrix[index] += noise * _token_noise(token, width)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms, vocab


def positional_encoding(length: int, dim: int) -> np.ndarray:
    """Classic sinusoidal position vectors."""
    if length < 1:
        raise AttentionError(f"length must be >= 1, got {length}")
    if dim < 2:
        raise AttentionError(f"dim must be >= 2, got {dim}")
    positions = np.arange(length)[:, None]
    half = dim // 2
    frequencies = np.exp(-math.log(10000.0) * np.arange(half) / dim)
    angles = positions * frequencies
    encoding = np.zeros((length, dim), dtype=np.float64)
    encoding[:, 0:2 * half:2] = np.sin(angles)
    encoding[:, 1:2 * half:2] = np.cos(angles)
    return encoding


def sentence_matrix(sentence: Sentence, vocab: dict[str, int],
                    embeddings: np.ndarray) -> np.ndarray:
    """Rows of the embedding matrix for one sentence."""
    tokens = sentence.tokens
    if not tokens:
        raise AttentionError(f"sentence {sentence.id} has no tokens")
    missing = sorted({token for token in tokens if token not in vocab})
    if missing:
        raise AttentionError(f"unknown tokens in {sentence.id}: {missing}")
    index = [vocab[token] for token in tokens]
    return embeddings[index]


# --------------------------------------------------------------------------- #
# Attention
# --------------------------------------------------------------------------- #
def scaled_scores(query: np.ndarray, key: np.ndarray) -> np.ndarray:
    """Q K^T / sqrt(d_k)."""
    if query.ndim != 2 or key.ndim != 2:
        raise AttentionError("query and key must be 2-D")
    if query.shape[1] != key.shape[1]:
        raise AttentionError("query and key widths must match")
    return query @ key.T / math.sqrt(query.shape[1])


def softmax(scores: np.ndarray) -> np.ndarray:
    """Row-wise softmax with the max subtracted for stability."""
    if scores.ndim != 2:
        raise AttentionError("scores must be 2-D")
    if scores.shape[0] == 0 or scores.shape[1] == 0:
        raise AttentionError("scores matrix is empty")
    shifted = scores - scores.max(axis=1, keepdims=True)
    exponentials = np.exp(shifted)
    return exponentials / exponentials.sum(axis=1, keepdims=True)


def causal_mask(length: int) -> np.ndarray:
    """Boolean lower-triangular mask (True = may attend)."""
    if length < 1:
        raise AttentionError(f"length must be >= 1, got {length}")
    return np.tril(np.ones((length, length), dtype=bool))


def head_projections(dim: int, n_heads: int, d_head: int, seed: int = 0
                     ) -> list[dict[str, np.ndarray]]:
    """Independent Q/K/V projections per head.

    Each entry is drawn from N(0, 2^2). Because the embeddings have unit
    rows, a query component then has variance 4, so ``Q K^T / sqrt(d_k)``
    has a spread of roughly 4 instead of collapsing to zero - which is
    what makes the softmax non-uniform and the heads distinguishable.
    """
    if n_heads < 1:
        raise AttentionError(f"n_heads must be >= 1, got {n_heads}")
    if d_head < 1:
        raise AttentionError(f"d_head must be >= 1, got {d_head}")
    rng = np.random.default_rng(seed)
    scale = 2.0
    heads = []
    for _ in range(n_heads):
        heads.append({
            "q": rng.standard_normal((dim, d_head)) * scale,
            "k": rng.standard_normal((dim, d_head)) * scale,
            "v": rng.standard_normal((dim, d_head)) * scale,
        })
    return heads


def multi_head_attention(embeddings: np.ndarray, n_heads: int = DEFAULT_HEADS,
                         d_head: int = DEFAULT_D_HEAD, seed: int = 0,
                         causal: bool = False) -> np.ndarray:
    """Return attention maps with shape (n_heads, tokens, tokens)."""
    if embeddings.ndim != 2:
        raise AttentionError("embeddings must be 2-D")
    length = embeddings.shape[0]
    if length < 1:
        raise AttentionError("embeddings are empty")
    heads = head_projections(embeddings.shape[1], n_heads, d_head, seed)
    mask = causal_mask(length) if causal else None
    maps = np.zeros((n_heads, length, length), dtype=np.float64)
    for index, head in enumerate(heads):
        query = embeddings @ head["q"]
        key = embeddings @ head["k"]
        scores = scaled_scores(query, key)
        if mask is not None:
            scores = np.where(mask, scores, -np.inf)
        maps[index] = softmax(scores)
    return maps


# --------------------------------------------------------------------------- #
# Interpretability
# --------------------------------------------------------------------------- #
def row_entropy(matrix: np.ndarray) -> float:
    """Mean Shannon entropy of the rows, in bits."""
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        raise AttentionError("matrix must be a non-empty 2-D array")
    if np.any(matrix < 0):
        raise AttentionError("attention weights must be non-negative")
    totals = matrix.sum(axis=1, keepdims=True)
    if np.any(totals <= 0):
        raise AttentionError("attention rows must sum to a positive value")
    probabilities = matrix / totals
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(probabilities > 0,
                         probabilities * np.log2(probabilities), 0.0)
    return float(-terms.sum(axis=1).mean())


def normalized_entropy(matrix: np.ndarray) -> float:
    """Mean entropy divided by log2(n) - 1.0 means a flat row."""
    if matrix.shape[1] < 2:
        raise AttentionError("need at least two columns to normalise")
    return row_entropy(matrix) / math.log2(matrix.shape[1])


def head_diversity(maps: np.ndarray) -> float:
    """1 - mean pairwise cosine similarity between flattened heads."""
    if maps.ndim != 3:
        raise AttentionError("maps must have shape (heads, rows, cols)")
    if maps.shape[0] < 2:
        raise AttentionError("need at least two heads for diversity")
    flat = maps.reshape(maps.shape[0], -1)
    norms = np.linalg.norm(flat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = flat / norms
    similarity = unit @ unit.T
    count = maps.shape[0]
    total = similarity.sum() - np.trace(similarity)
    return float(1.0 - total / (count * (count - 1)))


def top_attended(matrix: np.ndarray, tokens: list[str], row: int,
                 k: int = 3) -> list[tuple[str, float]]:
    """The k highest-weight tokens for one query position."""
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise AttentionError("matrix must be square")
    if len(tokens) != matrix.shape[0]:
        raise AttentionError("tokens must match the matrix size")
    if not 0 <= row < matrix.shape[0]:
        raise AttentionError(f"row {row} is out of range")
    if k < 1:
        raise AttentionError(f"k must be >= 1, got {k}")
    weights = matrix[row]
    order = np.argsort(-weights)[:min(k, len(tokens))]
    return [(tokens[index], float(weights[index])) for index in order]


def ascii_heatmap(matrix: np.ndarray, label: str = "") -> list[str]:
    """Render an attention map with ten intensity levels."""
    if matrix.ndim != 2:
        raise AttentionError("matrix must be 2-D")
    if matrix.size == 0:
        raise AttentionError("matrix is empty")
    highest = float(matrix.max())
    if highest <= 0:
        raise AttentionError("matrix must have a positive value")
    lines = [label] if label else []
    for row in matrix:
        cells = []
        for value in row:
            level = int(round((float(value) / highest) * (len(HEAT_CHARS) - 1)))
            cells.append(HEAT_CHARS[max(0, min(level, len(HEAT_CHARS) - 1))])
        lines.append("".join(cells))
    return lines


def analyse(sentence: Sentence, vocab: dict[str, int], embeddings: np.ndarray,
            n_heads: int = DEFAULT_HEADS, seed: int = 0) -> dict:
    """Attention summary for one sentence."""
    tokens = sentence.tokens
    matrix = sentence_matrix(sentence, vocab, embeddings)
    maps = multi_head_attention(matrix, n_heads=n_heads, seed=seed)
    entropies = [row_entropy(maps[head]) for head in range(n_heads)]
    return {
        "id": sentence.id,
        "tokens": tokens,
        "heads": n_heads,
        "entropy": [round(value, 4) for value in entropies],
        "diversity": round(head_diversity(maps), 4),
        "maps": maps,
    }


def to_dict(result: dict) -> dict:
    payload = {key: value for key, value in result.items() if key != "maps"}
    return json.loads(json.dumps(payload))


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    root = data_dir or DATA_DIR
    print("=" * 64)
    print(" ATTENTION VISUALIZER - offline demo")
    print(" Multi-head self-attention in NumPy, with ASCII heat maps.")
    print("=" * 64)

    sentences = load_texts(root / "texts.json")
    ids = {sentence.id for sentence in sentences}
    if not REQUIRED_IDS <= ids:
        raise AttentionError(f"bundled store is missing "
                             f"{sorted(REQUIRED_IDS - ids)}")
    for sentence in sentences:
        if len(sentence.tokens) < 4:
            raise AttentionError(f"sentence {sentence.id} is too short")

    embeddings, vocab = embed_tokens(sentences)
    print(f"\nCorpus          : {len(sentences)} sentences, "
          f"{sum(len(s.tokens) for s in sentences)} tokens, "
          f"vocabulary {len(vocab)}")
    print(f"Embeddings      : PPMI + offset, "
          f"{embeddings.shape[0]} x {embeddings.shape[1]}, "
          f"unit rows {np.allclose(np.linalg.norm(embeddings, axis=1), 1.0)}")

    # --- softmax must match a naive implementation --------------------- #
    probe = np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0]])
    naive = np.exp(probe) / np.exp(probe).sum(axis=1, keepdims=True)
    assert np.allclose(softmax(probe), naive)
    assert np.allclose(softmax(probe).sum(axis=1), 1.0)

    # --- attention maps ------------------------------------------------ #
    first = sentences[0]
    tokens = first.tokens
    matrix = sentence_matrix(first, vocab, embeddings)
    maps = multi_head_attention(matrix, n_heads=DEFAULT_HEADS, seed=7)
    assert maps.shape == (DEFAULT_HEADS, len(tokens), len(tokens))
    assert np.isfinite(maps).all()
    assert (maps >= 0).all()
    assert np.allclose(maps.sum(axis=2), 1.0)
    print(f"\nSentence        : {first.id} '{first.text}'")
    print(f"Tokens          : {len(tokens)} -> "
          f"attention maps {maps.shape[0]} heads of "
          f"{maps.shape[1]}x{maps.shape[2]}")

    entropies = [row_entropy(maps[head]) for head in range(DEFAULT_HEADS)]
    ceiling = math.log2(len(tokens))
    assert all(0.0 <= value <= ceiling + 1e-9 for value in entropies)
    assert max(entropies) < ceiling - 0.1, \
        "uniform attention - projections collapsed the scores"
    print("Entropy (bits)  : " + ", ".join(
        f"h{index}={value:.2f}" for index, value in enumerate(entropies))
        + f"  (uniform = {ceiling:.2f})")

    diversity = head_diversity(maps)
    assert -1e-9 <= diversity <= 1.0 + 1e-9
    assert diversity > 0.1, "heads are indistinguishable"
    print(f"Head diversity  : {diversity:.3f} "
          f"(1 - mean pairwise cosine)")

    # --- causal masking ------------------------------------------------ #
    causal = multi_head_attention(matrix, n_heads=2, seed=7, causal=True)
    upper = np.triu_indices(len(tokens), k=1)
    assert np.allclose(causal[:, upper[0], upper[1]], 0.0)
    assert np.allclose(causal.sum(axis=2), 1.0)
    print("Causal mask     : future positions receive exactly zero weight")

    # --- determinism --------------------------------------------------- #
    repeat = multi_head_attention(matrix, n_heads=DEFAULT_HEADS, seed=7)
    other = multi_head_attention(matrix, n_heads=DEFAULT_HEADS, seed=8)
    assert np.array_equal(maps, repeat), "attention is not deterministic"
    assert not np.array_equal(maps, other), "seed must change the maps"
    print("Deterministic   : same seed identical, different seed differs")

    # --- who attends to what ------------------------------------------- #
    row = min(2, len(tokens) - 1)
    leaders = top_attended(maps[0], tokens, row=row, k=3)
    assert len(leaders) == 3
    assert all(0.0 <= weight <= 1.0 for _, weight in leaders)
    print(f"\nTop attention for '{tokens[row]}' (head 0): " + ", ".join(
        f"{token} {weight:.2f}" for token, weight in leaders))

    print("\nAttention map (head 0, rows = queries, cols = keys):")
    for line in ascii_heatmap(maps[0], label=f"  tokens: {' '.join(tokens)}"):
        print("  " + line)

    # --- every sentence is analysable ---------------------------------- #
    for sentence in sentences:
        summary = analyse(sentence, vocab, embeddings, seed=11)
        assert len(summary["entropy"]) == DEFAULT_HEADS
        assert 0.0 <= summary["diversity"] <= 1.0
        assert summary["maps"].shape[0] == DEFAULT_HEADS

    print(f"\nCross-checks OK: {len(sentences)} sentences analysed, softmax "
          f"matches the naive formula, attention rows sum to 1, causal mask "
          f"exact, entropy within [0, {ceiling:.2f}], deterministic maps")
    print("Demo completed successfully.")
    return 0
