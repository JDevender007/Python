"""Offline hash cracking: dictionary, mutation, and bounded brute-force attacks.

Educational tool for recovering hashes you own (e.g. a forgotten password of
your own file). Everything runs locally against a bundled wordlist — there is
no network code. Never use this against hashes you are not authorized to test.
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import string
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

LOG = logging.getLogger("hash.cracker")

SUPPORTED_ALGOS: dict[str, Callable[[bytes], Any]] = {
    "md5": hashlib.md5,
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
}

DEFAULT_WORDLIST = Path(__file__).resolve().parent.parent / "data" / "wordlist.txt"

# Character sets for brute force, smallest first so short runs finish fast.
CHARSETS: dict[str, str] = {
    "digits": string.digits,
    "lower": string.ascii_lowercase,
    "lower_digits": string.ascii_lowercase + string.digits,
    "alnum": string.ascii_lowercase + string.ascii_uppercase + string.digits,
}


class CrackerError(RuntimeError):
    """Raised for unsupported algorithms and invalid inputs."""


@dataclass
class CrackResult:
    """Outcome of a cracking attempt."""

    found: bool
    plaintext: str = ""
    algo: str = ""
    mode: str = ""
    attempts: int = 0
    elapsed_s: float = 0.0
    candidates_per_s: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "plaintext": self.plaintext,
            "algo": self.algo,
            "mode": self.mode,
            "attempts": self.attempts,
            "elapsed_s": round(self.elapsed_s, 4),
            "candidates_per_s": round(self.candidates_per_s, 1),
            "notes": self.notes,
        }


def hash_text(text: str, algo: str = "sha256") -> str:
    """Hash a string and return the lowercase hex digest."""
    factory = SUPPORTED_ALGOS.get(algo)
    if factory is None:
        raise CrackerError(f"unsupported algorithm: {algo} (choose from {sorted(SUPPORTED_ALGOS)})")
    return factory(text.encode("utf-8")).hexdigest()


def verify(text: str, digest: str, algo: str = "sha256") -> bool:
    """Constant-time-ish comparison of a candidate against a digest."""
    import hmac

    return hmac.compare_digest(hash_text(text, algo), digest.lower())


def load_wordlist(path: str | Path | None = None) -> list[str]:
    """Load newline-delimited words, skipping blanks and comments."""
    source = Path(path) if path else DEFAULT_WORDLIST
    if not source.exists():
        raise CrackerError(f"wordlist not found: {source}")
    words: list[str] = []
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            words.append(stripped)
    if not words:
        raise CrackerError(f"wordlist is empty: {source}")
    return words


def mutations(word: str) -> Iterator[str]:
    """Yield common password mutations of a word (order matters)."""
    yield word
    lowered, lowered_cap = word.lower(), word.capitalize()
    if lowered != word:
        yield lowered
    if lowered_cap != word:
        yield lowered_cap
    yield word.upper()
    for suffix in ("1", "123", "1234", "!", "!1", "@", "#1", "2024", "2025", "2026"):
        yield lowered + suffix
        yield lowered_cap + suffix
    for prefix in ("1", "@", "#"):
        yield prefix + lowered
    # leet substitutions
    leet = lowered.translate(str.maketrans({"a": "@", "e": "3", "i": "1", "o": "0", "s": "$"}))
    if leet != lowered:
        yield leet
        yield leet + "!"


def brute_force_candidates(
    charset: str, max_length: int, min_length: int = 1
) -> Iterator[str]:
    """Generate every candidate from min_length to max_length characters."""
    if not charset:
        raise CrackerError("charset must not be empty")
    if max_length < min_length:
        raise CrackerError("max_length must be >= min_length")
    for length in range(min_length, max_length + 1):
        for combo in itertools.product(charset, repeat=length):
            yield "".join(combo)


def crack(
    digest: str,
    algo: str = "sha256",
    *,
    wordlist: str | Path | None = None,
    use_mutations: bool = True,
    charset: str | None = None,
    max_length: int = 4,
    min_length: int = 1,
    time_budget_s: float = 10.0,
    mode: str = "dictionary",
) -> CrackResult:
    """Try to recover the plaintext for `digest`.

    mode='dictionary'  - wordlist (+ optional mutations)
    mode='bruteforce'  - exhaustive over `charset` up to `max_length`
    mode='hybrid'      - dictionary first, then bounded brute force
    """
    if algo not in SUPPORTED_ALGOS:
        raise CrackerError(f"unsupported algorithm: {algo}")
    digest = digest.lower().strip()
    if not digest or any(c not in "0123456789abcdef" for c in digest):
        raise CrackerError("digest must be a non-empty hex string")
    if mode not in {"dictionary", "bruteforce", "hybrid"}:
        raise CrackerError(f"unknown mode: {mode}")

    started = time.perf_counter()
    attempts = 0
    notes: list[str] = []

    def attempt(candidate: str) -> bool:
        nonlocal attempts
        attempts += 1
        return verify(candidate, digest, algo)

    def budget_exceeded() -> bool:
        return (time.perf_counter() - started) > time_budget_s

    def try_wordlist() -> str | None:
        try:
            words = load_wordlist(wordlist)
        except CrackerError as exc:
            notes.append(str(exc))
            return None
        iterator = mutations_chain(words) if use_mutations else iter(words)
        for candidate in iterator:
            if attempt(candidate):
                return candidate
            if attempts % 500 == 0 and budget_exceeded():
                notes.append("dictionary stopped by time budget")
                return None
        return None

    def mutations_chain(words: list[str]) -> Iterator[str]:
        seen: set[str] = set()
        for word in words:
            for candidate in mutations(word):
                if candidate not in seen:
                    seen.add(candidate)
                    yield candidate

    def try_bruteforce() -> str | None:
        pool = charset or CHARSETS["lower"]
        for candidate in brute_force_candidates(pool, max_length, min_length):
            if attempt(candidate):
                return candidate
            if attempts % 2000 == 0 and budget_exceeded():
                notes.append(
                    f"brute force stopped by time budget after {attempts:,} attempts"
                )
                return None
        return None

    found: str | None = None
    if mode in {"dictionary", "hybrid"}:
        LOG.info("dictionary attack (%s)", algo)
        found = try_wordlist()
    if found is None and mode in {"bruteforce", "hybrid"}:
        LOG.info("brute force attack (%s, charset=%s, max_len=%s)",
                 algo, charset or "lower", max_length)
        found = try_bruteforce()

    elapsed = time.perf_counter() - started
    return CrackResult(
        found=found is not None,
        plaintext=found or "",
        algo=algo,
        mode=mode,
        attempts=attempts,
        elapsed_s=elapsed,
        candidates_per_s=attempts / elapsed if elapsed > 0 else 0.0,
        notes=notes,
    )


def render_result(result: CrackResult, digest: str) -> str:
    """Pretty text rendering used by the CLI and demo."""
    lines = [
        f"Digest   : {digest}",
        f"Algorithm: {result.algo}",
        f"Mode     : {result.mode}",
        f"Attempts : {result.attempts:,}",
        f"Elapsed  : {result.elapsed_s:.3f}s "
        f"({result.candidates_per_s:,.0f} candidates/s)",
    ]
    if result.found:
        lines.append(f"Recovered: {result.plaintext}")
    else:
        lines.append("Recovered: NOT FOUND")
    for note in result.notes:
        lines.append(f"Note     : {note}")
    return "\n".join(lines)


def run_demo() -> int:
    """Hash a few known secrets, then recover them offline."""
    print("=" * 56)
    print(" HASH CRACKER - offline demo")
    print(" Only crack hashes you own. Local wordlist, no network.")
    print("=" * 56)

    secrets = [
        ("sunshine", "sha256"),
        ("qwerty123", "md5"),
        ("Princess", "sha256"),
    ]

    print("\n[1] Dictionary attack (bundled wordlist + mutations)")
    for secret, algo in secrets:
        digest = hash_text(secret, algo)
        print(f"\n  secret is hidden; digest = {digest}")
        result = crack(digest, algo, mode="dictionary", time_budget_s=5.0)
        print("  " + render_result(result, digest).replace("\n", "\n  "))

    print("\n[2] Brute-force attack (digits, length <= 4)")
    secret = "4827"
    digest = hash_text(secret, "sha1")
    print(f"\n  secret is hidden; digest = {digest}")
    result = crack(digest, "sha1", mode="bruteforce", charset=CHARSETS["digits"],
                   max_length=4, time_budget_s=5.0)
    print("  " + render_result(result, digest).replace("\n", "\n  "))

    print("\n[3] Verify a candidate without cracking")
    print(f"  verify('sunshine') = {verify('sunshine', hash_text('sunshine'))}")
    print(f"  verify('wrongpass') = {verify('wrongpass', hash_text('sunshine'))}")

    print("\nDemo completed successfully.")
    return 0
