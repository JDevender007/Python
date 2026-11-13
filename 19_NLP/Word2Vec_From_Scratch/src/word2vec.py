"""Word2Vec (skip-gram with negative sampling) implemented in NumPy.

No gensim, no pre-trained vectors, no downloads: a deterministic bundled
corpus is expanded into (centre, context) pairs, negatives are drawn from
the unigram^0.75 noise distribution, and the embedding matrices are trained
with mini-batch SGD.

Public API
----------
generate_corpus            deterministic corpus text
bundle_corpus              write data/corpus.txt
tokenize                   lowercase word tokens
build_vocab                word -> id plus counts
generate_pairs             skip-gram training pairs
negative_table             unigram^0.75 sampling table
train_model                fit a Word2Vec embedding
Word2Vec                   similarity / most_similar / analogy helpers
run_demo                   offline demo (train + similarity + analogy)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CORPUS_FILE = DATA_DIR / "corpus.txt"

DIM = 32
WINDOW = 2
EPOCHS = 20
NEGATIVES = 5
LEARNING_RATE = 0.005
BATCH_SIZE = 256
SEED = 42
TOKEN_RE = re.compile(r"[a-z]+")


class Word2VecError(Exception):
    """Raised for invalid input, bad flags or corrupted bundled data."""


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #
_TEMPLATES = [
    "the king rules the kingdom with wisdom",
    "the queen rules the kingdom with wisdom",
    "the king governs the realm with justice",
    "the queen governs the realm with justice",
    "the prince will rule the kingdom one day",
    "the princess will rule the kingdom one day",
    "the king is a man of honour",
    "the queen is a woman of honour",
    "the prince is a boy of courage",
    "the princess is a girl of courage",
    "the man walks in the garden every morning",
    "the woman walks in the garden every morning",
    "the boy plays in the garden after school",
    "the girl plays in the garden after school",
    "the man works in the city",
    "the woman works in the city",
    "the king sits on the throne",
    "the queen sits on the throne",
    "paris is the capital of france",
    "tokyo is the capital of japan",
    "rome is the capital of italy",
    "berlin is the capital of germany",
    "madrid is the capital of spain",
    "london is the capital of england",
    "the dog barks at the cat",
    "the cat sleeps near the fire",
    "the horse runs across the field",
    "the bird sings in the tree",
    "the fish swims in the river",
    "the apple is a sweet fruit",
    "the banana is a sweet fruit",
    "the cherry is a small fruit",
    "the lemon is a sour fruit",
    "the sun rises in the east",
    "the moon shines at night",
    "the star shines at night",
    "the rain falls from the cloud",
    "the wind blows across the sea",
    "the sea is deep and blue",
    "the river runs to the sea",
    "the mountain is tall and cold",
    "the forest is green and quiet",
    "the city is loud and busy",
    "the village is small and quiet",
]


def generate_corpus() -> str:
    """Deterministic corpus: templates plus light repetition."""
    lines = []
    for repeat in range(6):
        for template in _TEMPLATES:
            lines.append(template)
    return "\n".join(lines) + "\n"


def bundle_corpus(data_dir: Path | None = None) -> Path:
    root = data_dir or DATA_DIR
    root.mkdir(parents=True, exist_ok=True)
    path = root / "corpus.txt"
    path.write_text(generate_corpus(), encoding="utf-8")
    return path


def load_corpus(path: Path | None = None) -> str:
    target = Path(path) if path is not None else CORPUS_FILE
    if not target.is_file():
        raise Word2VecError(f"corpus not found: {target}")
    text = target.read_text(encoding="utf-8")
    if not text.strip():
        raise Word2VecError(f"corpus is empty: {target.name}")
    return text


def tokenize(text: str) -> list[str]:
    """Lowercase alphabetic tokens."""
    if not isinstance(text, str):
        raise Word2VecError("text must be a string")
    return TOKEN_RE.findall(text.lower())


# --------------------------------------------------------------------------- #
# Vocabulary and pairs
# --------------------------------------------------------------------------- #
def build_vocab(tokens: list[str], min_count: int = 1
                ) -> tuple[dict[str, int], np.ndarray]:
    if min_count < 1:
        raise Word2VecError(f"min_count must be at least 1, got {min_count}")
    if not tokens:
        raise Word2VecError("cannot build a vocabulary from no tokens")
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    kept = sorted((word for word, n in counts.items() if n >= min_count),
                  key=lambda w: (-counts[w], w))
    if len(kept) < 2:
        raise Word2VecError("vocabulary needs at least two words")
    vocab = {word: index for index, word in enumerate(kept)}
    frequencies = np.array([counts[word] for word in kept], dtype=np.float64)
    return vocab, frequencies


def generate_pairs(ids: np.ndarray, window: int = WINDOW) -> np.ndarray:
    """Skip-gram (centre, context) pairs within ``window`` either side."""
    if window < 1:
        raise Word2VecError(f"window must be at least 1, got {window}")
    arr = np.asarray(ids)
    if arr.ndim != 1:
        raise Word2VecError(f"ids must be 1-D, got {arr.shape}")
    centres = []
    contexts = []
    for offset in range(1, window + 1):
        if arr.size <= offset:
            break
        centres.append(arr[:-offset])
        contexts.append(arr[offset:])
        centres.append(arr[offset:])
        contexts.append(arr[:-offset])
    if not centres:
        raise Word2VecError("corpus too short for the requested window")
    pairs = np.column_stack([np.concatenate(centres),
                             np.concatenate(contexts)])
    return pairs[pairs[:, 0] != pairs[:, 1]]


def negative_table(frequencies: np.ndarray, power: float = 0.75,
                   size: int = 100_000) -> np.ndarray:
    """Sampling table over word ids proportional to count^0.75."""
    counts = np.asarray(frequencies, dtype=np.float64)
    if counts.ndim != 1 or counts.size < 2:
        raise Word2VecError("frequencies must be a 1-D array of >= 2 counts")
    if np.any(counts < 0) or counts.sum() <= 0:
        raise Word2VecError("frequencies must be non-negative with a sum > 0")
    if size < 1:
        raise Word2VecError(f"table size must be positive, got {size}")
    weights = np.power(counts, power)
    weights /= weights.sum()
    cumulative = np.cumsum(weights)
    cumulative[-1] = 1.0
    grid = (np.arange(size) + 0.5) / size
    return np.searchsorted(cumulative, grid).astype(np.int64)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
@dataclass
class Word2Vec:
    words: list[str]
    vectors: np.ndarray
    losses: list[float]
    dim: int
    window: int
    negatives: int

    def _index(self, word: str) -> int:
        if word not in self.words:
            raise Word2VecError(f"word not in vocabulary: '{word}'")
        return self.words.index(word)

    def vector(self, word: str) -> np.ndarray:
        return self.vectors[self._index(word)]

    def similarity(self, first: str, second: str) -> float:
        a = self.vector(first)
        b = self.vector(second)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def _rank(self, target: np.ndarray, exclude: set[str],
              topn: int) -> list[tuple[str, float]]:
        norms = np.linalg.norm(self.vectors, axis=1)
        norms[norms == 0] = 1.0
        scores = (self.vectors @ target) / (norms * np.linalg.norm(target))
        order = np.argsort(scores)[::-1]
        results = []
        for idx in order:
            word = self.words[int(idx)]
            if word in exclude:
                continue
            results.append((word, round(float(scores[int(idx)]), 4)))
            if len(results) >= topn:
                break
        return results

    def most_similar(self, word: str, topn: int = 5
                     ) -> list[tuple[str, float]]:
        if topn < 1:
            raise Word2VecError(f"topn must be positive, got {topn}")
        return self._rank(self.vector(word), {word}, topn)

    def analogy(self, a: str, b: str, c: str, topn: int = 5
                ) -> list[tuple[str, float]]:
        target = self.vector(b) - self.vector(a) + self.vector(c)
        return self._rank(target, {a, b, c}, topn)

    def to_dict(self) -> dict:
        return {
            "vocab_size": len(self.words),
            "dim": self.dim,
            "window": self.window,
            "negatives": self.negatives,
            "epochs": len(self.losses),
            "loss_first": self.losses[0] if self.losses else None,
            "loss_last": self.losses[-1] if self.losses else None,
        }


def train_model(corpus: str, dim: int = DIM, window: int = WINDOW,
                epochs: int = EPOCHS, negatives: int = NEGATIVES,
                learning_rate: float = LEARNING_RATE, seed: int = SEED,
                min_count: int = 1) -> Word2Vec:
    """Fit skip-gram vectors with negative sampling using Adam.

    Dense Adam updates (the embedding tables are tiny) keep the step size
    scale-free, which makes mini-batch training stable without hand-tuned
    per-pair schedules.
    """
    if dim < 2:
        raise Word2VecError(f"dim must be at least 2, got {dim}")
    if epochs < 1:
        raise Word2VecError(f"epochs must be at least 1, got {epochs}")
    if negatives < 1:
        raise Word2VecError(f"negatives must be at least 1, got {negatives}")
    if not 0 < learning_rate < 10:
        raise Word2VecError(f"learning_rate must be in (0, 10), "
                            f"got {learning_rate}")
    tokens = tokenize(corpus)
    vocab, frequencies = build_vocab(tokens, min_count=min_count)
    ids = np.array([vocab[token] for token in tokens], dtype=np.int64)
    pairs = generate_pairs(ids, window)
    if pairs.size == 0:
        raise Word2VecError("no training pairs generated")
    table = negative_table(frequencies)

    rng = np.random.default_rng(seed)
    vocab_size = len(vocab)
    w_in = (rng.random((vocab_size, dim)) - 0.5) / np.sqrt(dim)
    w_out = np.zeros((vocab_size, dim), dtype=np.float64)
    losses: list[float] = []

    beta1, beta2, eps = 0.9, 0.999, 1e-8
    m_in = np.zeros_like(w_in)
    v_in = np.zeros_like(w_in)
    m_out = np.zeros_like(w_out)
    v_out = np.zeros_like(w_out)
    step = 0

    for _ in range(epochs):
        order = rng.permutation(pairs.shape[0])
        epoch_loss = 0.0
        batches = 0
        for start in range(0, pairs.shape[0], BATCH_SIZE):
            batch = pairs[order[start:start + BATCH_SIZE]]
            centre = batch[:, 0]
            context = batch[:, 1]
            batch_size = batch.shape[0]
            neg_ids = table[rng.integers(0, table.size,
                                         size=(batch_size, negatives))]

            v = w_in[centre]                       # (B, d)
            u_pos = w_out[context]                 # (B, d)
            u_neg = w_out[neg_ids]                 # (B, k, d)

            pos_score = np.einsum("bd,bd->b", v, u_pos)
            neg_score = np.einsum("bd,bkd->bk", v, u_neg)

            pos_prob = _sigmoid(pos_score)
            neg_prob = _sigmoid(neg_score)

            loss = (-np.log(np.clip(pos_prob, 1e-12, 1.0)).mean()
                    - np.log(np.clip(1.0 - neg_prob, 1e-12, 1.0)).mean())
            epoch_loss += float(loss)
            batches += 1

            # dL/dscore: positive term -> sigma(s) - 1, negative -> sigma(s)
            grad_pos = (pos_prob - 1.0)[:, None]           # (B, 1)
            grad_neg = neg_prob                            # (B, k)
            grad_v = grad_pos * u_pos + np.einsum(
                "bk,bkd->bd", grad_neg, u_neg)
            grad_out_pos = grad_pos * v                    # (B, d)
            grad_out_neg = grad_neg[:, :, None] * v[:, None, :]

            scale = 1.0 / batch_size
            g_in = np.zeros_like(w_in)
            g_out = np.zeros_like(w_out)
            np.add.at(g_in, centre, scale * grad_v)
            np.add.at(g_out, context, scale * grad_out_pos)
            np.add.at(g_out, neg_ids.ravel(),
                      scale * grad_out_neg.reshape(-1, dim))

            step += 1
            for param, grad, m, vv in ((w_in, g_in, m_in, v_in),
                                       (w_out, g_out, m_out, v_out)):
                m *= beta1
                m += (1.0 - beta1) * grad
                vv *= beta2
                vv += (1.0 - beta2) * grad * grad
                m_hat = m / (1.0 - beta1 ** step)
                v_hat = vv / (1.0 - beta2 ** step)
                param -= learning_rate * m_hat / (np.sqrt(v_hat) + eps)
        losses.append(round(epoch_loss / max(1, batches), 6))

    return Word2Vec(words=list(vocab), vectors=w_in, losses=losses,
                    dim=dim, window=window, negatives=negatives)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    root = data_dir or DATA_DIR
    print("=" * 64)
    print(" WORD2VEC FROM SCRATCH - offline demo")
    print(" Skip-gram + negative sampling, pure NumPy.")
    print("=" * 64)

    expected = generate_corpus()
    text = load_corpus(root / "corpus.txt")
    if text != expected:
        raise Word2VecError("bundled corpus does not match the generator")
    tokens = tokenize(text)
    vocab, frequencies = build_vocab(tokens)
    print(f"\nCorpus           : {len(tokens)} tokens, {len(vocab)} words "
          f"(bundled + verified)")

    model = train_model(text)
    print(f"Training         : dim={model.dim} window={model.window} "
          f"negatives={model.negatives} epochs={len(model.losses)}")
    print(f"Loss             : {model.losses[0]:.4f} -> "
          f"{model.losses[-1]:.4f}")
    assert model.losses[-1] < model.losses[0], "loss did not decrease"
    assert model.vectors.shape == (len(vocab), DIM)
    assert np.isfinite(model.vectors).all(), "vectors contain NaN/inf"

    # --- nearest neighbours ------------------------------------------- #
    neighbours = model.most_similar("king", topn=5)
    words = [word for word, _ in neighbours]
    assert words[0] in {"queen", "prince", "man", "woman"}, neighbours
    similar = model.similarity("king", "queen")
    unrelated = model.similarity("king", "banana")
    assert similar > unrelated + 0.1, (similar, unrelated)
    print(f"Most similar to 'king': {', '.join(words)}")
    print(f"cos(king, queen) = {similar:.3f} vs "
          f"cos(king, banana) = {unrelated:.3f}")

    # --- city similarity ----------------------------------------------- #
    assert model.similarity("paris", "tokyo") > \
        model.similarity("paris", "apple")
    print(f"cos(paris, tokyo) = "
          f"{model.similarity('paris', 'tokyo'):.3f} > "
          f"cos(paris, apple) = {model.similarity('paris', 'apple'):.3f}")

    # --- analogy -------------------------------------------------------- #
    result = model.analogy("man", "king", "woman", topn=5)
    ranked = [word for word, _ in result]
    assert "queen" in ranked, result
    print(f"analogy man : king :: woman : "
          f"{' / '.join(ranked)}  (queen found)")

    # --- negative sampling distribution -------------------------------- #
    table = negative_table(frequencies)
    empirical = np.bincount(table, minlength=len(vocab)) / table.size
    expected_dist = frequencies ** 0.75
    expected_dist /= expected_dist.sum()
    assert np.abs(empirical - expected_dist).max() < 0.01
    print(f"Negatives        : table matches count^0.75 "
          f"(max dev {np.abs(empirical - expected_dist).max():.4f})")

    # --- determinism / validation -------------------------------------- #
    again = train_model(text)
    assert np.allclose(again.vectors, model.vectors), \
        "training is not deterministic"
    assert again.losses == model.losses
    print("Deterministic    : identical vectors on a repeated run")
    try:
        model.similarity("king", "unicorn")
    except Word2VecError:
        print("Unknown word     : raises Word2VecError (as designed)")
    else:
        raise Word2VecError("unknown words must raise")

    print("\nCross-checks OK: loss decreased, neighbour ranking, city "
          "similarity, analogy found queen, negative table matches "
          "count^0.75, deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
