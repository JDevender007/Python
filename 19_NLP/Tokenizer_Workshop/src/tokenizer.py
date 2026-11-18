"""Tokenizer workshop: regex tokenization, normalization, stemming,
stopword removal, n-grams, and token statistics - fully offline.

Pure standard library. Loads a bundled text corpus and a bundled stopword
list from data/, runs a deterministic pipeline over them, and reports token
statistics. No network, no downloads, no model files - local files only.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

WORD_RE = re.compile(r"[a-z0-9]+(?:['\-][a-z0-9]+)*")
WHITESPACE_RE = re.compile(r"\s+")

# Fancy unicode characters folded to ASCII equivalents during normalization.
_CHAR_MAP = {
    "\u2018": "'",   # left single quote
    "\u2019": "'",   # right single quote
    "\u201c": '"',   # left double quote
    "\u201d": '"',   # right double quote
    "\u2013": "-",   # en dash
    "\u2014": "-",   # em dash
    "\u00a0": " ",   # non-breaking space
}

# Suffix rules applied in order; first match wins (simplified Porter-style).
# (suffix, replacement, minimum token length, must-not-end-with exclusions)
SUFFIX_RULES: tuple[tuple[str, str, int, tuple[str, ...]], ...] = (
    ("ational", "ate", 9, ()),
    ("tional", "tion", 8, ()),
    ("fulness", "ful", 9, ()),
    ("ousness", "ous", 9, ()),
    ("iveness", "ive", 9, ()),
    ("ement", "", 7, ()),
    ("ment", "", 6, ()),
    ("ness", "", 6, ()),
    ("ies", "y", 5, ()),
    ("sses", "ss", 6, ()),
    ("ches", "ch", 6, ()),
    ("shes", "sh", 6, ()),
    ("xes", "x", 5, ()),
    ("zes", "z", 5, ()),
    ("ing", "", 6, ()),
    ("ed", "", 5, ()),
    ("ly", "", 5, ()),
    ("s", "", 4, ("ss", "us", "is")),
)

DEFAULT_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus.txt"
DEFAULT_STOPWORDS = (Path(__file__).resolve().parent.parent / "data"
                     / "stopwords.txt")


class TokenError(RuntimeError):
    """Raised for invalid text, missing files, or bad tokenizer options."""


# --------------------------------------------------------------------------- #
# Normalization and tokenization
# --------------------------------------------------------------------------- #
def normalize(text: str) -> str:
    """NFKC-normalize, fold fancy quotes/dashes, lowercase, collapse spaces."""
    if not isinstance(text, str):
        raise TokenError(f"text must be a string, got {type(text).__name__}")
    folded = unicodedata.normalize("NFKC", text)
    for source, target in _CHAR_MAP.items():
        folded = folded.replace(source, target)
    folded = folded.lower()
    return WHITESPACE_RE.sub(" ", folded).strip()


def tokenize(text: str, min_length: int = 1,
             keep_numbers: bool = True) -> list[str]:
    """Split text into regex tokens (letters/digits with ' and - glue)."""
    if not isinstance(text, str):
        raise TokenError(f"text must be a string, got {type(text).__name__}")
    if not isinstance(min_length, int) or min_length < 1:
        raise TokenError(f"min_length must be >= 1, got {min_length!r}")
    tokens = WORD_RE.findall(normalize(text))
    return [t for t in tokens if len(t) >= min_length
            and (keep_numbers or not t.isdigit())]


# --------------------------------------------------------------------------- #
# Stopwords
# --------------------------------------------------------------------------- #
def load_stopwords(path: str | Path) -> frozenset[str]:
    """Load one lowercase alphabetic stopword per line."""
    source = Path(path)
    if not source.is_file():
        raise TokenError(f"stopword file not found: {source}")
    words: set[str] = set()
    for number, line in enumerate(source.read_text(
            encoding="utf-8").splitlines(), start=1):
        word = line.strip()
        if not word:
            continue
        if word != word.lower() or not word.isalpha():
            raise TokenError(
                f"stopword on line {number} ({word!r}) must be "
                f"lowercase alphabetic")
        words.add(word)
    if not words:
        raise TokenError(f"no stopwords found in {source.name}")
    return frozenset(words)


def remove_stopwords(tokens: list[str],
                     stopwords: frozenset[str] | set[str]) -> list[str]:
    """Drop stopwords, preserving the order of the remaining tokens."""
    if not stopwords:
        raise TokenError("stopwords must be a non-empty collection")
    for token in tokens:
        if not isinstance(token, str) or token == "":
            raise TokenError("tokens must be non-empty strings")
    stops = set(stopwords)
    return [t for t in tokens if t not in stops]


# --------------------------------------------------------------------------- #
# Stemming
# --------------------------------------------------------------------------- #
def stem(token: str) -> str:
    """Simplified rule-based suffix stemmer (first matching rule wins)."""
    if not isinstance(token, str) or not token.isalpha():
        raise TokenError(f"stem() expects an alphabetic token, "
                         f"got {token!r}")
    word = token.lower()
    for suffix, replacement, min_length, exclusions in SUFFIX_RULES:
        if len(word) < min_length or not word.endswith(suffix):
            continue
        if exclusions and word.endswith(exclusions):
            continue
        base = word[:len(word) - len(suffix)] + replacement
        # Collapse a doubled final consonant after a short vowel:
        # running -> runn -> run, stopped -> stopp -> stop (never 'ss'/'ll').
        if suffix in ("ing", "ed") and len(base) >= 3 \
                and base[-1] == base[-2] and base[-1] in "bdgmnprtd":
            base = base[:-1]
        return base if base else word
    return word


# --------------------------------------------------------------------------- #
# N-grams and statistics
# --------------------------------------------------------------------------- #
def _check_tokens(tokens: list[str]) -> None:
    for token in tokens:
        if not isinstance(token, str) or token == "":
            raise TokenError("tokens must be non-empty strings")


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    """Contiguous n-grams as tuples; empty list when n exceeds the length."""
    _check_tokens(tokens)
    if not isinstance(n, int) or n < 1:
        raise TokenError(f"n must be >= 1, got {n!r}")
    if n > len(tokens):
        return []
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def token_stats(tokens: list[str], top: int = 5) -> dict:
    """Deterministic summary statistics over a token list."""
    _check_tokens(tokens)
    if not isinstance(top, int) or top < 1:
        raise TokenError(f"top must be >= 1, got {top!r}")
    if not tokens:
        raise TokenError("no tokens to summarise")

    counts = Counter(tokens)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "total": len(tokens),
        "unique": len(counts),
        "avg_length": round(sum(len(t) for t in tokens) / len(tokens), 4),
        "longest": max(tokens, key=lambda t: (len(t), t)),
        "shortest": min(tokens, key=lambda t: (len(t), t)),
        "digit_tokens": sum(1 for t in tokens if t.isdigit()),
        "alpha_tokens": sum(1 for t in tokens if t.isalpha()),
        "top": ranked[:top],
    }


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
@dataclass
class TokenizeResult:
    """Everything the pipeline produced for one input text."""

    text: str
    normalized: str
    tokens: list[str]
    kept: list[str]
    removed: int
    stems: list[str]
    grams: list[tuple[str, ...]]
    stats: dict

    def to_dict(self) -> dict:
        return {
            "characters": len(self.text),
            "raw_tokens": len(self.tokens),
            "kept_tokens": len(self.kept),
            "stopwords_removed": self.removed,
            "unique_kept": len(set(self.kept)),
            "ngrams": len(self.grams),
            "n": len(self.grams[0]) if self.grams else 1,
            "stats": {k: v for k, v in self.stats.items() if k != "top"},
            "top_tokens": [{"token": t, "count": c}
                           for t, c in self.stats["top"]],
        }


def process(text: str, n: int = 2, stopwords: frozenset[str] | None = None,
            use_stopwords: bool = True, min_length: int = 1,
            keep_numbers: bool = True, top: int = 5) -> TokenizeResult:
    """Run the full pipeline: normalize -> tokenize -> stopwords -> stem."""
    normalized = normalize(text)
    tokens = tokenize(text, min_length=min_length,
                      keep_numbers=keep_numbers)
    if use_stopwords:
        stops = stopwords if stopwords is not None \
            else load_stopwords(DEFAULT_STOPWORDS)
        kept = remove_stopwords(tokens, stops)
    else:
        kept = list(tokens)
    stems = [stem(t) if t.isalpha() else t for t in kept]
    return TokenizeResult(
        text=text,
        normalized=normalized,
        tokens=tokens,
        kept=kept,
        removed=len(tokens) - len(kept),
        stems=stems,
        grams=ngrams(kept, n),
        stats=token_stats(tokens, top=top),
    )


def load_corpus(path: str | Path) -> str:
    """Load the bundled corpus as one text string (paragraphs joined)."""
    source = Path(path)
    if not source.is_file():
        raise TokenError(f"corpus file not found: {source}")
    lines = [line.strip() for line in
             source.read_text(encoding="utf-8").splitlines()]
    paragraphs = [line for line in lines if line]
    if not paragraphs:
        raise TokenError(f"no non-empty lines in {source.name}")
    return "\n".join(paragraphs)


# --------------------------------------------------------------------------- #
# Report and demo
# --------------------------------------------------------------------------- #
def render_report(result: TokenizeResult) -> str:
    """Human-readable pipeline report used by the CLI and the demo."""
    stats = result.stats
    top_text = "  ".join(f"{word}({count})"
                         for word, count in result.stats["top"])
    sample = list(zip(result.kept[:8], result.stems[:8]))
    lines = [
        "TOKENIZER WORKSHOP (regex tokens, stems, n-grams)",
        "=" * 68,
        f"Input          : {len(result.text)} characters, "
        f"{len(result.normalized)} normalized",
        f"Raw tokens     : {len(result.tokens)} "
        f"({stats['unique']} unique)",
        f"After stopwords: {len(result.kept)} "
        f"({result.removed} removed)",
        f"N-grams         : {len(result.grams)} "
        f"(n={len(result.grams[0]) if result.grams else 1})",
        f"Avg length     : {stats['avg_length']}  "
        f"longest '{stats['longest']}'  digits {stats['digit_tokens']}",
        "",
        f"Top tokens: {top_text}",
        "",
        "Token -> stem:",
    ]
    lines += [f"  {token:<14} -> {st}" for token, st in sample]
    return "\n".join(lines)


def run_demo(corpus_path: str | Path | None = None,
             stopwords_path: str | Path | None = None) -> int:
    """Tokenize the bundled corpus - fully offline."""
    print("=" * 68)
    print(" TOKENIZER WORKSHOP - offline demo")
    print(" Bundled corpus + stopwords; pure Python; no network.")
    print("=" * 68)

    source = Path(corpus_path) if corpus_path else DEFAULT_CORPUS
    stops_source = Path(stopwords_path) if stopwords_path else DEFAULT_STOPWORDS
    if not source.is_file():
        raise TokenError(f"bundled corpus not found: {source}")

    text = load_corpus(source)
    stops = load_stopwords(stops_source)
    result = process(text, n=2, stopwords=stops)
    print()
    print(render_report(result))

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(result.tokens) > 10, "corpus tokenized too thinly"
    assert result.removed > 0, "no stopwords were removed"
    assert len(result.grams) == len(result.kept) - 1, \
        "bigram count must be len(tokens) - 1"
    assert result.tokens == tokenize(text), "tokenization not deterministic"
    assert all(s and len(s) <= len(t)
               for t, s in zip(result.kept, result.stems)), \
        "stems must be non-empty and never longer than the token"
    assert stem("running") == "run", "stem(running) != run"
    assert stem("cats") == "cat", "stem(cats) != cat"
    assert stem("studies") == "study", "stem(studies) != study"

    stats = result.stats
    assert stats["unique"] <= stats["total"]
    assert stats["top"][0][1] == max(Counter(result.tokens).values()), \
        "top token must hold the maximum count"
    assert [w for w, _ in stats["top"]] == sorted(
        [w for w, _ in stats["top"]],
        key=lambda w: (-Counter(result.tokens)[w], w)), \
        "top tokens must be count-sorted then alphabetical"

    again = process(text, n=2, stopwords=stops)
    assert again.to_dict() == result.to_dict(), "pipeline not deterministic"

    print(f"\nCross-checks OK: {len(result.tokens)} tokens, "
          f"{result.removed} stopwords removed, {len(result.grams)} bigrams, "
          f"{len(set(result.stems))} unique stems, deterministic re-run")
    print("Demo completed successfully.")
    return 0
