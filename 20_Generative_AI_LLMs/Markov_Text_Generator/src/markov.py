"""Markov chain text generation with variable order and backoff.

The model is built from a bundled corpus: for every order-n context the
successor counts are stored, generation samples from those counts, and
perplexity is measured with add-one smoothing plus unigram backoff.
Pure standard library - no network, no downloads.

Public API
----------
generate_corpus      deterministic bundled corpus text
bundle_corpus        write data/corpus.txt
load_corpus          read a corpus file
tokenize             word tokens
build_model          order-n transition counts
most_likely          highest-count successor for a context
generate_text        sampled continuation
perplexity           smoothed cross-entropy in bits/word
transition_report    top transitions for display
run_demo             offline demo with self-checks
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CORPUS_FILE = DATA_DIR / "corpus.txt"

MIN_ORDER = 1
MAX_ORDER = 3
DEFAULT_ORDER = 2
DEFAULT_LENGTH = 40
TOKEN_RE = re.compile(r"[A-Za-z']+|[.,!?;]")
SENTENCE_END = (".", "!", "?")


class MarkovError(Exception):
    """Raised for invalid input, bad flags or corrupted bundled data."""


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #
_SUBJECTS = ["gardener", "butterfly", "kettle", "spade", "pepper", "rose",
             "willow", "compost", "beehive", "ladder", "fountain", "gate"]
_ADJECTIVES = ["patient", "golden", "drowsy", "crooked", "tiny", "fragrant",
               "busy", "early", "quiet", "green"]
_VERBS = ["watered", "shimmered", "wandered", "answered", "tumbled", "waited",
          "planted", "slept", "carried", "rested"]
_PLACES = ["garden", "path", "noon", "rain", "soil", "hedge", "orchard",
           "meadow", "window", "cellar"]


def generate_corpus() -> str:
    """Deterministic corpus (~100 sentences) built from word lists."""
    lines: list[str] = []
    for i in range(100):
        subject = _SUBJECTS[i % len(_SUBJECTS)]
        adjective = _ADJECTIVES[(i * 3) % len(_ADJECTIVES)]
        verb = _VERBS[(i * 7) % len(_VERBS)]
        place = _PLACES[(i * 5) % len(_PLACES)]
        if i % 4 == 0:
            lines.append(f"The {adjective} {subject} {verb} in the {place}.")
        elif i % 4 == 1:
            lines.append(f"The {subject} {verb} while the {place} waited.")
        elif i % 4 == 2:
            lines.append(f"After the {place} the {adjective} {subject} "
                         f"{verb} again.")
        else:
            lines.append(f"By the {place} the {subject} {verb} and the "
                         f"{adjective} {place} answered.")
    return "\n".join(lines) + "\n"


def bundle_corpus(data_dir: Path | None = None) -> Path:
    root = data_dir or DATA_DIR
    root.mkdir(parents=True, exist_ok=True)
    path = root / "corpus.txt"
    path.write_text(generate_corpus(), encoding="utf-8")
    return path


def load_corpus(path: Path | str | None = None) -> str:
    target = Path(path) if path is not None else CORPUS_FILE
    if not target.is_file():
        raise MarkovError(f"corpus not found: {target}")
    text = target.read_text(encoding="utf-8")
    if not text.strip():
        raise MarkovError(f"corpus is empty: {target.name}")
    return text


def tokenize(text: str) -> list[str]:
    """Words plus sentence punctuation, lowercased."""
    if not isinstance(text, str):
        raise MarkovError("text must be a string")
    return [token.lower() for token in TOKEN_RE.findall(text)]


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
@dataclass
class MarkovModel:
    order: int
    counts: dict[tuple[str, ...], Counter] = field(default_factory=dict)
    vocab: Counter = field(default_factory=Counter)
    starts: list[tuple[str, ...]] = field(default_factory=list)

    @property
    def states(self) -> int:
        return len(self.counts)

    @property
    def transitions(self) -> int:
        return sum(len(counter) for counter in self.counts.values())

    def successors(self, context: tuple[str, ...]) -> Counter:
        return self.counts.get(context, Counter())

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "states": self.states,
            "transitions": self.transitions,
            "vocab_size": len(self.vocab),
            "top": [[list(k), v] for k, v in self.top_transitions(5)],
        }

    def top_transitions(self, limit: int = 10
                        ) -> list[tuple[tuple[str, ...], int]]:
        rows = [(context, sum(counter.values()))
                for context, counter in self.counts.items()]
        rows.sort(key=lambda row: (-row[1], row[0]))
        return rows[:limit]


def build_model(tokens: list[str], order: int = DEFAULT_ORDER) -> MarkovModel:
    """Count every order-n context -> successor transition."""
    if not MIN_ORDER <= order <= MAX_ORDER:
        raise MarkovError(f"order must be in {MIN_ORDER}..{MAX_ORDER}, "
                          f"got {order}")
    if not isinstance(tokens, list) or not tokens:
        raise MarkovError("cannot build a model from no tokens")
    if len(tokens) <= order:
        raise MarkovError(f"corpus needs more than {order} tokens")
    model = MarkovModel(order=order)
    model.vocab.update(tokens)
    for index in range(len(tokens) - order):
        context = tuple(tokens[index:index + order])
        successor = tokens[index + order]
        model.counts.setdefault(context, Counter())[successor] += 1
        clean = all(token.isalpha() for token in context)
        if clean and (index == 0 or tokens[index - 1] in SENTENCE_END):
            model.starts.append(context)
    if not model.starts:
        model.starts = [tuple(sorted(model.counts)[0])]
    return model


def most_likely(model: MarkovModel, context: tuple[str, ...]
                ) -> str | None:
    """Highest-count successor, or None when the context is unknown."""
    counter = model.successors(tuple(context))
    if not counter:
        return None
    best = max(counter.items(), key=lambda item: (item[1], item[0]))
    return best[0]


def _sample(counter: Counter, rng: random.Random) -> str:
    words = list(counter)
    weights = [counter[word] for word in words]
    return rng.choices(words, weights=weights, k=1)[0]


def generate_text(model: MarkovModel, length: int = DEFAULT_LENGTH,
                  seed: int = 0,
                  start: tuple[str, ...] | None = None) -> list[str]:
    """Sample ``length`` tokens, backing off to a fresh start when stuck."""
    if length < 1:
        raise MarkovError(f"length must be at least 1, got {length}")
    if not model.counts:
        raise MarkovError("model has no transitions")

    rng = random.Random(seed)
    if start is not None:
        context = tuple(start)
        if len(context) != model.order:
            raise MarkovError(f"start context must have {model.order} "
                              f"words, got {len(context)}")
    else:
        context = rng.choice(model.starts or list(model.counts))

    output = list(context)
    while len(output) < length:
        counter = model.successors(context)
        if not counter:
            context = rng.choice(model.starts or list(model.counts))
            output.extend(context)
            continue
        word = _sample(counter, rng)
        output.append(word)
        context = tuple(output[-model.order:])
    return output[:length]


def detokenize(tokens: list[str]) -> str:
    """Join tokens into readable text (no space before punctuation)."""
    out = ""
    for token in tokens:
        if token in (".", ",", "!", "?", ";"):
            out += token
        elif not out:
            out = token
        else:
            out += " " + token
    if out:
        out = out[0].upper() + out[1:]
    return out


def perplexity(model: MarkovModel, tokens: list[str]) -> float:
    """Add-one smoothed bits/word, with unigram backoff for unseen states."""
    if not tokens:
        raise MarkovError("cannot score an empty token list")
    vocab_size = len(model.vocab)
    if vocab_size == 0:
        raise MarkovError("model has an empty vocabulary")
    total = 0.0
    scored = 0
    for index in range(model.order, len(tokens)):
        context = tuple(tokens[index - model.order:index])
        target = tokens[index]
        counter = model.counts.get(context)
        if counter:
            numerator = counter.get(target, 0) + 1
            denominator = sum(counter.values()) + vocab_size
        else:
            numerator = model.vocab.get(target, 0) + 1
            denominator = sum(model.vocab.values()) + vocab_size
        total -= math.log2(numerator / denominator)
        scored += 1
    if not scored:
        raise MarkovError("token list too short to score")
    return round(2.0 ** (total / scored), 4)


def transition_report(model: MarkovModel, limit: int = 6) -> list[str]:
    """Readable top-transition lines for the console report."""
    lines = []
    for context, count in model.top_transitions(limit):
        counter = model.successors(context)
        top = ", ".join(f"{word} x{n}" for word, n in counter.most_common(3))
        lines.append(f"  {' '.join(context):<22} -> {top}  (total {count})")
    return lines


def to_dict(model: MarkovModel, generated: list[str] | None = None) -> dict:
    payload = model.to_dict()
    if generated is not None:
        payload["generated"] = detokenize(generated)
        payload["tokens"] = len(generated)
    return json.loads(json.dumps(payload))


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    root = data_dir or DATA_DIR
    print("=" * 64)
    print(" MARKOV TEXT GENERATOR - offline demo")
    print(" Order-n transition counts, backoff sampling, perplexity.")
    print("=" * 64)

    expected = generate_corpus()
    text = load_corpus(root / "corpus.txt")
    if text != expected:
        raise MarkovError("bundled corpus does not match the generator")
    tokens = tokenize(text)
    print(f"\nCorpus          : {len(tokens)} tokens, "
          f"{len(set(tokens))} distinct (bundled + verified)")

    models = {order: build_model(tokens, order) for order in (1, 2, 3)}
    for order, model in models.items():
        assert model.states > 0 and model.transitions > 0
        naive = Counter()
        for index in range(len(tokens) - order):
            naive[(tuple(tokens[index:index + order]),
                   tokens[index + order])] += 1
        assert sum(model.successors(context).get(word, 0)
                   for (context, word) in naive) == sum(naive.values())
        print(f"Order {order}         : {model.states} states, "
              f"{model.transitions} transitions")

    # most_likely must agree with an independent recount
    bigram = models[2]
    best_context = max(bigram.counts, key=lambda c: sum(bigram.counts[c].values()))
    recount: Counter = Counter()
    for index in range(len(tokens) - 2):
        if tuple(tokens[index:index + 2]) == best_context:
            recount[tokens[index + 2]] += 1
    expected_word = max(recount.items(), key=lambda item: (item[1], item[0]))[0]
    assert most_likely(bigram, best_context) == expected_word
    print(f"Most likely     : {' '.join(best_context)} -> {expected_word} "
          f"(x{recount[expected_word]})")

    # generation
    first = generate_text(bigram, length=30, seed=7)
    second = generate_text(bigram, length=30, seed=7)
    other = generate_text(bigram, length=30, seed=8)
    assert first == second, "sampling is not deterministic"
    assert first != other, "seed must change the sample"
    assert len(first) == 30
    assert set(first) <= set(tokens), "generated an out-of-vocabulary token"
    print(f"\nSample (seed 7) : {detokenize(first)}")

    # fixed start context is honoured
    context = next(context for context in sorted(bigram.counts)
                   if all(token.isalpha() for token in context))
    fixed = generate_text(bigram, length=12, seed=1, start=context)
    assert tuple(fixed[:2]) == context
    print(f"Fixed start     : {' '.join(context)} -> {detokenize(fixed)}")

    # a higher order must fit the training text better than a unigram
    scores = {order: perplexity(model, tokens)
              for order, model in models.items()}
    assert scores[2] < scores[1], f"bigrams should beat unigrams: {scores}"
    print("Perplexity      : " + ", ".join(
        f"order{o}={v:.2f}" for o, v in scores.items()) + " bits/word")

    # known transitions survive
    assert most_likely(models[1], ("the",)) in models[1].successors(("the",))
    assert all(count == 1 or count > 0
               for counter in models[1].counts.values()
               for count in counter.values())

    print("\nTop transitions (order 2):")
    for line in transition_report(bigram):
        print(line)

    print(f"\nCross-checks OK: corpus verified, order 1-3 model counts match a "
          f"naive recount, deterministic sampling, fixed start honoured, "
          f"perplexity {scores[2]:.2f} bits/word")
    print("\nDemo completed successfully.")
    return 0
