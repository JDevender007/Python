"""POS tagger: bigram HMM + Viterbi decoding on a bundled tagged corpus.

Trains initial/transition/emission log-probabilities with add-k smoothing
from a CoNLL-style corpus (one ``word<TAB>tag`` per line, blank line between
sentences), decodes the best tag sequence with the Viterbi algorithm, and
reports token accuracy against a most-frequent-tag baseline. Local files
only - no network, no downloads, no external taggers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus.txt"
MIN_SENTENCES = 20
UNK = "<UNK>"

TAGS: frozenset[str] = frozenset({
    "CC", "CD", "DT", "IN", "JJ", "MD", "NN", "NNS", "PRP", "RB",
    "TO", "VB", "VBD", "VBG", "VBP", "VBZ", "WP", "WRB", ",", ".",
})

LOG = logging.getLogger("pos_tagger")


class TaggerError(RuntimeError):
    """Raised for malformed corpora, bad options, and empty inputs."""


# --------------------------------------------------------------------------- #
# Corpus loading
# --------------------------------------------------------------------------- #
def load_corpus(path: str | Path) -> list[list[tuple[str, str]]]:
    """Parse a CoNLL-style tagged corpus into sentences of (word, tag)."""
    source = Path(path)
    if not source.is_file():
        raise TaggerError(f"corpus file not found: {source}")

    sentences: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    for number, line in enumerate(source.read_text(
            encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            if current:
                sentences.append(current)
                current = []
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise TaggerError(
                f"line {number}: expected 'word<TAB>tag', got {line!r}")
        word, tag = parts
        if not word or not word.strip():
            raise TaggerError(f"line {number}: empty word")
        if tag not in TAGS:
            raise TaggerError(
                f"unknown tag {tag!r} on line {number} "
                f"(expected one of: {', '.join(sorted(TAGS))})")
        current.append((word, tag))
    if current:
        sentences.append(current)

    if not sentences:
        raise TaggerError(f"no sentences in {source.name}")
    if len(sentences) < MIN_SENTENCES:
        raise TaggerError(
            f"need at least {MIN_SENTENCES} sentences, "
            f"got {len(sentences)}")
    return sentences


def split_corpus(sentences: list[list[tuple[str, str]]],
                 ratio: float = 0.8) -> tuple[list, list]:
    """Chronological train/test split of the sentence list."""
    if not 0.0 < ratio < 1.0:
        raise TaggerError(f"ratio must be in (0, 1), got {ratio}")
    if len(sentences) < 2:
        raise TaggerError("need at least 2 sentences to split")
    cut = max(1, min(len(sentences) - 1, int(round(len(sentences) * ratio))))
    return sentences[:cut], sentences[cut:]


def corpus_stats(sentences: list[list[tuple[str, str]]]) -> dict:
    """Sentence/token/word/tag counts for reporting."""
    if not sentences:
        raise TaggerError("no sentences to summarise")
    words = {w for s in sentences for w, _ in s}
    tags = {t for s in sentences for _, t in s}
    return {"sentences": len(sentences),
            "tokens": sum(len(s) for s in sentences),
            "words": len(words), "tags": len(tags)}


# --------------------------------------------------------------------------- #
# HMM training
# --------------------------------------------------------------------------- #
@dataclass
class HmmModel:
    """Smoothed bigram HMM with log-probability tables."""

    tags: tuple[str, ...]
    tag_index: dict[str, int]
    words: tuple[str, ...]
    word_index: dict[str, int]
    initial: np.ndarray        # (T,)
    transition: np.ndarray     # (T, T)
    emission: np.ndarray       # (T, V+1) - last column is <UNK>
    unigram_counts: dict[str, dict[str, int]]
    majority_tag: str

    @property
    def unk_index(self) -> int:
        return len(self.words)

    def tag_text(self, text: str) -> list[tuple[str, str]]:
        """Tag a raw whitespace-tokenized sentence -> [(word, tag), ...]."""
        words = split_words(text)
        tags = viterbi(self, words)
        return list(zip(words, tags))


def split_words(text: str) -> list[str]:
    """Whitespace-tokenize a raw sentence for tagging."""
    if not isinstance(text, str):
        raise TaggerError(
            f"sentence must be a string, got {type(text).__name__}")
    words = text.split()
    if not words:
        raise TaggerError("sentence must not be empty")
    return words


def train_hmm(sentences: list[list[tuple[str, str]]],
              alpha: float = 0.1) -> HmmModel:
    """Add-k smoothed initial/transition/emission estimates in log space."""
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) \
            or not np.isfinite(alpha) or alpha <= 0:
        raise TaggerError(f"alpha must be > 0, got {alpha!r}")
    if not sentences:
        raise TaggerError("need at least one training sentence")

    tags = tuple(sorted(TAGS))
    tag_index = {tag: i for i, tag in enumerate(tags)}
    t_count = len(tags)

    counts: dict[str, int] = {}
    unigram: dict[str, dict[str, int]] = {}
    for sentence in sentences:
        if not sentence:
            raise TaggerError("training sentences must not be empty")
        for word, tag in sentence:
            if not isinstance(word, str) or not word:
                raise TaggerError("training words must be non-empty strings")
            if tag not in tag_index:
                raise TaggerError(f"unknown tag in training data: {tag!r}")
            counts[word] = counts.get(word, 0) + 1
            unigram.setdefault(word, {})
            unigram[word][tag] = unigram[word].get(tag, 0) + 1

    words = tuple(sorted(counts))
    word_index = {w: i for i, w in enumerate(words)}
    v_count = len(words)

    initial = np.zeros(t_count, dtype=float)
    transition = np.zeros((t_count, t_count), dtype=float)
    emission = np.zeros((t_count, v_count + 1), dtype=float)

    for sentence in sentences:
        first_tag = sentence[0][1]
        initial[tag_index[first_tag]] += 1.0
        emission[tag_index[first_tag],
                 word_index[sentence[0][0]]] += 1.0
        for (w_prev, t_prev), (w_cur, t_cur) in zip(sentence, sentence[1:]):
            transition[tag_index[t_prev], tag_index[t_cur]] += 1.0
            emission[tag_index[t_cur], word_index[w_cur]] += 1.0

    n_sentences = float(len(sentences))
    initial = np.log((initial + alpha) / (n_sentences + alpha * t_count))
    totals = transition.sum(axis=1, keepdims=True)
    transition = np.log((transition + alpha) / (totals + alpha * t_count))
    emit_totals = emission.sum(axis=1, keepdims=True)
    emission = np.log((emission + alpha)
                      / (emit_totals + alpha * (v_count + 1)))

    tag_totals: dict[str, int] = {}
    for word, by_tag in unigram.items():
        for tag, n in by_tag.items():
            tag_totals[tag] = tag_totals.get(tag, 0) + n
    majority = max(sorted(tag_totals), key=lambda t: tag_totals[t])

    model = HmmModel(
        tags=tags, tag_index=tag_index, words=words,
        word_index=word_index, initial=initial,
        transition=transition, emission=emission,
        unigram_counts=unigram, majority_tag=majority)
    LOG.info("trained HMM: %d tags, %d words, %d sentences",
             t_count, v_count, len(sentences))
    return model


# --------------------------------------------------------------------------- #
# Viterbi decoding
# --------------------------------------------------------------------------- #
def viterbi(model: HmmModel, words: list[str]) -> list[str]:
    """Highest-probability tag sequence for ``words`` (log-space DP)."""
    if not words:
        raise TaggerError("need at least one word to tag")
    for word in words:
        if not isinstance(word, str) or not word:
            raise TaggerError("words must be non-empty strings")
        if word != word.strip() or any(c.isspace() for c in word):
            raise TaggerError(f"word {word!r} must not contain whitespace")

    # The bundled corpus is lowercase, so lookup falls back to the
    # lowered form before resorting to <UNK>.
    indices: list[int] = []
    for word in words:
        column = model.word_index.get(word)
        if column is None:
            column = model.word_index.get(word.lower(), model.unk_index)
        indices.append(column)
    delta = model.initial + model.emission[:, indices[0]]
    back: list[np.ndarray] = []
    for column in indices[1:]:
        scores = delta[:, None] + model.transition   # [previous, current]
        back.append(np.argmax(scores, axis=0))
        delta = np.max(scores, axis=0) + model.emission[:, column]

    path = [int(np.argmax(delta))]
    for pointers in reversed(back):
        path.append(int(pointers[path[-1]]))
    path.reverse()
    return [model.tags[i] for i in path]


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def evaluate(model: HmmModel,
             sentences: list[list[tuple[str, str]]]) -> dict:
    """Token accuracy plus per-tag precision/recall on tagged sentences."""
    if not sentences:
        raise TaggerError("no sentences to evaluate")

    correct = total = 0
    tp: dict[str, int] = {t: 0 for t in model.tags}
    fp: dict[str, int] = {t: 0 for t in model.tags}
    fn: dict[str, int] = {t: 0 for t in model.tags}
    for sentence in sentences:
        gold = [tag for _, tag in sentence]
        predicted = viterbi(model, [w for w, _ in sentence])
        if len(predicted) != len(gold):
            raise TaggerError("prediction length mismatch")
        for want, got in zip(gold, predicted):
            total += 1
            if want == got:
                correct += 1
                tp[want] += 1
            else:
                fp[got] += 1
                fn[want] += 1

    per_tag: dict[str, dict] = {}
    for tag in model.tags:
        precision = tp[tag] / (tp[tag] + fp[tag]) if tp[tag] + fp[tag] \
            else 0.0
        recall = tp[tag] / (tp[tag] + fn[tag]) if tp[tag] + fn[tag] else 0.0
        f1 = 2 * precision * recall / (precision + recall) \
            if precision + recall else 0.0
        per_tag[tag] = {"precision": round(precision, 4),
                        "recall": round(recall, 4),
                        "f1": round(f1, 4),
                        "support": tp[tag] + fn[tag]}
    return {"accuracy": correct / total, "correct": correct,
            "tokens": total, "tags": per_tag}


def baseline_accuracy(model: HmmModel,
                      test: list[list[tuple[str, str]]]) -> float:
    """Most-frequent-tag baseline (unknown words fall back to majority)."""
    if not test:
        raise TaggerError("no sentences to evaluate")
    correct = total = 0
    for sentence in test:
        for word, gold in sentence:
            by_tag = model.unigram_counts.get(word)
            if by_tag:
                guess = max(sorted(by_tag), key=lambda t: by_tag[t])
            else:
                guess = model.majority_tag
            correct += guess == gold
            total += 1
    return correct / total


# --------------------------------------------------------------------------- #
# Report and demo
# --------------------------------------------------------------------------- #
def render_report(stats: dict, split: tuple[int, int], baseline: float,
                  result: dict, sample: list[tuple[str, str]]) -> str:
    """Human-readable training/evaluation report."""
    accuracy = result["accuracy"]
    train_n, test_n = split
    lines = [
        "POS TAGGER (bigram HMM + Viterbi)",
        "=" * 68,
        f"Corpus     : {stats['sentences']} sentences, {stats['tokens']} "
        f"tokens, {stats['words']} distinct words, {stats['tags']} tags",
        f"Split      : {train_n} train / {test_n} test (chronological)",
        f"Baseline   : most-frequent-tag accuracy {baseline:.3f}",
        f"HMM        : Viterbi accuracy {accuracy:.3f} "
        f"({accuracy - baseline:+.3f} vs baseline, "
        f"{result['correct']}/{result['tokens']} tokens)",
        "",
        "Per-tag metrics (precision / recall / F1 / support):",
    ]
    for tag in sorted(result["tags"]):
        row = result["tags"][tag]
        if row["support"] == 0:
            continue
        lines.append(f"  {tag:<4} {row['precision']:.3f} "
                     f"{row['recall']:.3f} {row['f1']:.3f} "
                     f"{row['support']:>5}")
    lines += ["", "Sample tagging:", "  " + "  ".join(
        f"{word}/{tag}" for word, tag in sample)]
    return "\n".join(lines)


def run_demo(corpus_path: str | Path | None = None,
             ratio: float = 0.8) -> int:
    """Train on the bundled tagged corpus - fully offline."""
    print("=" * 68)
    print(" POS TAGGER - offline demo")
    print(" Bundled CoNLL corpus; bigram HMM + Viterbi; no network.")
    print("=" * 68)

    source = Path(corpus_path) if corpus_path else DEFAULT_CORPUS
    if not source.is_file():
        raise TaggerError(f"bundled corpus not found: {source}")

    sentences = load_corpus(source)
    stats = corpus_stats(sentences)
    train, test = split_corpus(sentences, ratio)
    model = train_hmm(train)
    result = evaluate(model, test)
    baseline = baseline_accuracy(model, test)

    sample_text = "Where does the dog sleep"
    sample = model.tag_text(sample_text)
    print()
    print(render_report(stats, (len(train), len(test)), baseline, result,
                        sample))

    # --- cross-checks the demo asserts ----------------------------------- #
    assert stats["sentences"] >= 500, "bundled corpus too small"
    assert stats["tokens"] >= 3000, "not enough training tokens"
    assert len(train) + len(test) == stats["sentences"]
    assert 0.0 <= baseline <= 1.0
    assert result["accuracy"] >= 0.88, "Viterbi accuracy below 0.88"
    assert result["accuracy"] >= baseline, "HMM must beat its baseline"
    assert result["tokens"] == sum(len(s) for s in test)
    assert sum(row["support"] for row in result["tags"].values()) == \
        result["tokens"], "per-tag supports must sum to test tokens"
    for word, tag in sample:
        assert tag in TAGS, "predictor emitted an unknown tag"
    assert sample == [("Where", "WRB"), ("does", "VBZ"), ("the", "DT"),
                      ("dog", "NN"), ("sleep", "VB")], \
        f"sample tagging changed: {sample}"

    again = train_hmm(train)
    assert np.array_equal(again.initial, model.initial), \
        "training not deterministic"
    assert viterbi(again, [w for w, _ in sample]) == \
        [t for _, t in sample], "decoding not deterministic"

    unseen = viterbi(model, ["zzz", "qqq"])
    assert len(unseen) == 2 and all(t in TAGS for t in unseen), \
        "unknown words must still decode"

    print(f"\nCross-checks OK: accuracy {result['accuracy']:.3f} >= "
          f"baseline {baseline:.3f} and >= 0.88, "
          f"{result['tokens']} test tokens accounted for, "
          "sample tagging exact, unknown words decode, deterministic")
    print("Demo completed successfully.")
    return 0
