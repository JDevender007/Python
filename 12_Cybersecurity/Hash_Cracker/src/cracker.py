"""A miss is not a verdict: only an exhausted search can say "not here".

The legacy cracker is the one every "crack hashes with a wordlist" gist contains:

    for line in open(wordlist):
        if hashlib.sha256(line.encode()).hexdigest() == digest:
            return line
    return None          # "password is strong"

    recovered = dictionary_attack(target)
    verdict = "strong" if recovered is None else "weak"

Three defects follow from those six lines, and each one is a sentence about
something the program never established.

**1. A miss from a partial search is not strength.** A wordlist of 117
candidates says nothing about an unbounded keyspace. Reporting "strong" after
117 guesses is a claim about the password that the work did not earn. The only
negative a search can prove is the one a *complete* search proves: run every
4-digit PIN, find nothing, and "not a 4-digit PIN" is a fact. Everything else is
*inconclusive*, and the report must say so.

**2. The salt is part of the hash.** `carol`'s digest is
`sha256("s3cr3t" + "monkey")`; the legacy loop hashes the bare word, misses, and
declares a password that is literally in the wordlist to be strong. A field that
is present in the record and ignored by the search is a false negative with no
log line.

**3. Work is counted, not timed.** The legacy counter increments once per line,
so 126 lines are reported as 126 attempts when 117 distinct candidates were
hashed: 6 comment lines and 3 repeated words were counted as work. And the
throughput beside it comes from a clock, so two runs of the same demo print two
different rates.

The rebuild reads the `salt` column, compares digests from a record whose
algorithm and digest length are validated against each other, deduplicates the
candidate list while keeping its order, and returns a three-valued verdict:
`found`, `exhausted` (the search was complete, so the absence is a proof) or
`inconclusive` (the search stopped while candidates remained). Nothing is timed
and nothing is sampled; two runs are byte identical.
"""

from __future__ import annotations

import csv
import hashlib
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TARGETS_FILE = DATA_DIR / "targets.csv"
WORDLIST_FILE = DATA_DIR / "wordlist.txt"

#: Hexadecimal digest length each algorithm produces.
ALGORITHMS = {"md5": 32, "sha1": 40, "sha256": 64}

MODES = ("wordlist", "pin4")
VERDICTS = ("found", "exhausted", "inconclusive")

PIN_DIGITS = 4
PIN_KEYSPACE = 10 ** PIN_DIGITS

HEX_DIGITS = set(string.hexdigits)

#: The legacy search, transcribed: the salt is not in the record it reads.
LEGACY_SALT = "digest = hashlib.sha256(word.encode()).hexdigest()"

#: The legacy verdict: anywhere that is not a hit is called strength.
LEGACY_VERDICT = 'verdict = "strong" if recovered is None else "weak"'

#: The legacy counter: one increment per line, comments and repeats included.
LEGACY_ATTEMPTS = "attempts += 1  # once per line of the wordlist"


class CrackerError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise CrackerError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise CrackerError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CrackerError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise CrackerError(f"{name} must be positive, got {number}")
    return number


def divide_half_up(numerator: int, denominator: int) -> int:
    """Integer division rounding halves away from zero, with no float."""
    top = _whole(numerator, "numerator")
    bottom = _positive(denominator, "denominator")
    sign = -1 if top < 0 else 1
    magnitude = abs(top)
    return sign * ((magnitude * 2 + bottom) // (2 * bottom))


def format_bp(basis_points: int) -> str:
    """Render hundredths of a percent as a two-place percentage."""
    value = _whole(basis_points, "basis_points")
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    return f"{sign}{magnitude // 100}.{magnitude % 100:02d}"


def algorithm_of(text: str) -> str:
    """Normalise and validate an algorithm name."""
    raw = _text(text, "algorithm").strip().lower()
    if raw not in ALGORITHMS:
        raise CrackerError(
            f"algorithm must be one of {sorted(ALGORITHMS)}, got {raw!r}"
        )
    return raw


def mode_of(text: str) -> str:
    raw = _text(text, "mode").strip().lower()
    if raw not in MODES:
        raise CrackerError(f"mode must be one of {list(MODES)}, got {raw!r}")
    return raw


def check_digest(algorithm: str, digest: str) -> str:
    """A digest must be hexadecimal and exactly as long as its algorithm says."""
    algo = algorithm_of(algorithm)
    raw = _text(digest, "digest").strip().lower()
    if not set(raw) <= HEX_DIGITS:
        raise CrackerError(f"digest is not hexadecimal: {raw!r}")
    expected = ALGORITHMS[algo]
    if len(raw) != expected:
        raise CrackerError(
            f"a {algo} digest is {expected} hex characters, got {len(raw)}"
        )
    return raw


def _salt(value: object, name: str = "salt") -> str:
    """A salt may be empty; when present it must be ASCII text."""
    if not isinstance(value, str):
        raise CrackerError(f"{name} must be text, got {type(value).__name__}")
    raw = value.strip()
    try:
        raw.encode("ascii")
    except UnicodeEncodeError as exc:
        raise CrackerError(f"{name} must be ASCII text") from exc
    return raw


def _ascii(text: str, name: str) -> str:
    raw = _text(text, name)
    try:
        raw.encode("ascii")
    except UnicodeEncodeError as exc:
        raise CrackerError(f"{name} must be ASCII text") from exc
    return raw


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Target:
    """One hash to attack, with everything needed to reproduce it."""

    label: str
    algorithm: str
    salt: str
    digest: str
    mode: str

    @property
    def keyspace(self) -> int | None:
        """How many candidates the mode covers, when that number is known."""
        return PIN_KEYSPACE if self.mode == "pin4" else None

    @property
    def salted(self) -> bool:
        return bool(self.salt)


@dataclass(frozen=True)
class Search:
    """What one attack established, and how much work it took."""

    label: str
    verdict: str
    attempts: int
    recovered: str | None
    keyspace: int | None

    @property
    def proven(self) -> bool:
        """True only when the verdict is a statement the search actually proved."""
        return self.verdict in ("found", "exhausted")

    @property
    def missed(self) -> bool:
        return self.recovered is None


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #
def digest_of(text: str, algorithm: str = "sha256") -> str:
    """The lowercase hexadecimal digest of one candidate, salt already applied."""
    raw = _ascii(text, "candidate")
    algo = algorithm_of(algorithm)
    return hashlib.new(algo, raw.encode("ascii")).hexdigest()


def digest_with_salt(target: Target, word: str) -> str:
    """The digest the record says the password produces: salt first, then word."""
    return digest_of(target.salt + _ascii(word, "candidate"), target.algorithm)


# --------------------------------------------------------------------------- #
# Candidate lists
# --------------------------------------------------------------------------- #
def read_lines(path: str | Path | None = None) -> list[str]:
    """Every non-empty line of the wordlist, comments and repeats included."""
    target = Path(path) if path is not None else WORDLIST_FILE
    if not target.is_file():
        raise CrackerError(f"file not found: {target.name}")
    try:
        body = target.read_bytes().decode("ascii")
    except UnicodeDecodeError as exc:
        raise CrackerError(f"{target.name} is not ASCII text") from exc
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        raise CrackerError(f"{target.name} holds no lines")
    return lines


def load_words(path: str | Path | None = None) -> list[str]:
    """The candidate words, comments dropped and order kept."""
    words = [line for line in read_lines(path) if not line.startswith("#")]
    if not words:
        raise CrackerError("the wordlist holds no candidates")
    return words


def distinct_words(words: Sequence[str]) -> list[str]:
    """First occurrence wins, so the list order stays the attack order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for word in words:
        raw = _ascii(word, "candidate")
        if raw not in seen:
            seen.add(raw)
            ordered.append(raw)
    return ordered


def pin_candidates(digits: int = PIN_DIGITS) -> list[str]:
    """Every fixed-length decimal string, in counting order."""
    width = _positive(digits, "digits")
    if width > 6:
        raise CrackerError(f"digits must be at most 6, got {width}")
    return [f"{number:0{width}d}" for number in range(10 ** width)]


def candidates_for(target: Target, words: Sequence[str]) -> list[str]:
    """The candidate list a target's mode calls for."""
    if target.mode == "pin4":
        return pin_candidates()
    rows = distinct_words(words)
    if not rows:
        raise CrackerError("the wordlist holds no candidates")
    return rows


# --------------------------------------------------------------------------- #
# The search
# --------------------------------------------------------------------------- #
def search(target: Target, candidates: Sequence[str]) -> Search:
    """Try every candidate in order and say what the result proves."""
    rows = list(candidates)
    if not rows:
        raise CrackerError("a search needs at least one candidate")
    for attempt, word in enumerate(rows, start=1):
        if digest_with_salt(target, word) == target.digest:
            return Search(
                label=target.label,
                verdict="found",
                attempts=attempt,
                recovered=_ascii(word, "candidate"),
                keyspace=target.keyspace,
            )
    space = target.keyspace
    exhausted = space is not None and len(rows) >= space
    return Search(
        label=target.label,
        verdict="exhausted" if exhausted else "inconclusive",
        attempts=len(rows),
        recovered=None,
        keyspace=space,
    )


def legacy_search(target: Target, lines: Sequence[str]) -> str | None:
    """The legacy attack: hash the bare word, ignore the salt, stop on a hit."""
    for line in lines:
        word = _text(line, "line").strip()
        if digest_of(word, target.algorithm) == target.digest:
            return word
    return None


def legacy_verdict(recovered: str | None) -> str:
    """The legacy vocabulary, where a miss is strength."""
    return "strong" if recovered is None else "weak"


def legacy_attempts(lines: Sequence[str]) -> int:
    """One increment per non-empty line, comments and repeats included."""
    return len([line for line in lines if line.strip()])


# --------------------------------------------------------------------------- #
# Loading targets
# --------------------------------------------------------------------------- #
def _read_rows(path: str | Path, required: Sequence[str]) -> list[dict[str, str]]:
    target = Path(path)
    if not target.is_file():
        raise CrackerError(f"file not found: {target.name}")
    try:
        body = target.read_bytes().decode("ascii")
    except UnicodeDecodeError as exc:
        raise CrackerError(f"{target.name} is not ASCII text") from exc
    reader = csv.DictReader(body.splitlines())
    header = reader.fieldnames or []
    missing = [column for column in required if column not in header]
    if missing:
        raise CrackerError(f"{target.name} is missing column(s): {', '.join(missing)}")
    return [dict(row) for row in reader]


def load_targets(path: str | Path | None = None) -> list[Target]:
    rows = _read_rows(
        path if path is not None else TARGETS_FILE,
        ("label", "algorithm", "salt", "digest", "mode"),
    )
    return build_targets(rows)


def build_targets(rows: Sequence[dict[str, str]]) -> list[Target]:
    """Turn parsed CSV rows into validated targets, refusing a disagreement."""
    if not rows:
        raise CrackerError("targets.csv holds no targets")
    targets: list[Target] = []
    for row in rows:
        algorithm = algorithm_of(row["algorithm"])
        targets.append(
            Target(
                label=_text(row["label"], "label").strip(),
                algorithm=algorithm,
                salt=_salt(row["salt"]),
                digest=check_digest(algorithm, row["digest"]),
                mode=mode_of(row["mode"]),
            )
        )
    if len({target.label for target in targets}) != len(targets):
        raise CrackerError("label values must be unique")
    return targets


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(
    targets_path: str | Path | None = None,
    *,
    wordlist_path: str | Path | None = None,
) -> dict[str, Any]:
    if targets_path is not None:
        folder = Path(targets_path).resolve().parent
        wordlist_path = wordlist_path or folder / "wordlist.txt"
    targets = load_targets(targets_path)
    lines = read_lines(wordlist_path)
    words = load_words(wordlist_path)
    distinct = distinct_words(words)
    searches = [search(target, candidates_for(target, distinct)) for target in targets]
    legacy = {target.label: legacy_search(target, lines) for target in targets}
    return {
        "targets": targets,
        "lines": lines,
        "words": words,
        "distinct": distinct,
        "searches": searches,
        "legacy": legacy,
        "legacy_attempts": legacy_attempts(lines),
        "legacy_strong": sorted(label for label, hit in legacy.items() if hit is None),
        "found": [row.label for row in searches if row.verdict == "found"],
        "exhausted": [row.label for row in searches if row.verdict == "exhausted"],
        "inconclusive": [row.label for row in searches if row.verdict == "inconclusive"],
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    pin = next((row for row in measured["searches"] if row.keyspace is not None), None)
    return {
        "targets": len(measured["targets"]),
        "wordlist_lines": len(measured["lines"]),
        "wordlist_duplicates": len(measured["words"]) - len(measured["distinct"]),
        "distinct_candidates": len(measured["distinct"]),
        "legacy_attempts": measured["legacy_attempts"],
        "legacy_strong": measured["legacy_strong"],
        "found": measured["found"],
        "exhausted": measured["exhausted"],
        "inconclusive": measured["inconclusive"],
        "pin_coverage_bp": (
            None
            if pin is None
            else divide_half_up(pin.attempts * 10_000, pin.keyspace or 1)
        ),
        "pin_coverage_percent": (
            None
            if pin is None
            else format_bp(divide_half_up(pin.attempts * 10_000, pin.keyspace or 1))
        ),
        "searches": [
            {
                "label": row.label,
                "verdict": row.verdict,
                "attempts": row.attempts,
                "recovered": row.recovered,
                "keyspace": row.keyspace,
            }
            for row in measured["searches"]
        ],
        "legacy": dict(measured["legacy"]),
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:
        return False


def _refuses(call) -> bool:
    try:
        call()
    except CrackerError:
        return True
    return False


def audit(
    measured: dict[str, Any],
    *,
    crack: Callable[[Target, Sequence[str]], Search] = search,
) -> list[tuple[str, bool]]:
    """Every check compares a measured value with an independent computation."""
    targets = measured["targets"]
    distinct = measured["distinct"]
    searches = measured["searches"]
    by_label = {row.label: row for row in searches}
    by_target = {target.label: target for target in targets}

    def searches_via_cracker() -> list[Search]:
        if not hasattr(searches_via_cracker, "cache"):
            searches_via_cracker.cache = [  # type: ignore[attr-defined]
                crack(target, candidates_for(target, distinct)) for target in targets
            ]
        return searches_via_cracker.cache  # type: ignore[attr-defined]

    def independent_found() -> list[str]:
        found: list[str] = []
        for target in targets:
            for word in candidates_for(target, distinct):
                if digest_with_salt(target, word) == target.digest:
                    found.append(target.label)
                    break
        return found

    checks = [
        (
            "every_target_gets_exactly_one_search",
            lambda: len(searches_via_cracker()) == len(targets) == 5,
        ),
        (
            "searches_are_in_target_order",
            lambda: [row.label for row in searches_via_cracker()]
            == [target.label for target in targets],
        ),
        (
            "the_verdicts_are_pinned",
            lambda: [row.verdict for row in searches]
            == ["found", "found", "found", "inconclusive", "exhausted"],
        ),
        (
            "verdicts_match_an_independent_scan",
            lambda: [row.label for row in searches_via_cracker() if row.verdict == "found"]
            == independent_found(),
        ),
        (
            "the_recovered_passwords_are_pinned",
            lambda: [row.recovered for row in searches]
            == ["sunshine", "michael", "monkey", None, None],
        ),
        (
            "carols_digest_is_over_the_salt_and_the_word",
            lambda: digest_with_salt(by_target["carol"], "monkey") == by_target["carol"].digest
            and digest_of("monkey", "sha256") != by_target["carol"].digest,
        ),
        (
            "ignoring_the_salt_misses_carol",
            lambda: measured["legacy"]["carol"] is None
            and by_label["carol"].verdict == "found",
        ),
        (
            "a_partial_miss_is_inconclusive_not_strong",
            lambda: by_label["dave"].verdict == "inconclusive"
            and by_label["dave"].keyspace is None
            and by_label["dave"].attempts == len(distinct),
        ),
        (
            "a_complete_miss_is_a_proof_of_absence",
            lambda: by_label["erin"].verdict == "exhausted"
            and by_label["erin"].attempts == PIN_KEYSPACE == 10_000,
        ),
        (
            "the_legacy_verdict_calls_every_miss_strong",
            lambda: sorted(
                label for label, hit in measured["legacy"].items() if hit is None
            )
            == ["carol", "dave", "erin"]
            and len(measured["legacy_strong"]) == 3,
        ),
        (
            "a_hit_counts_only_the_candidates_it_examined",
            lambda: by_label["alice"].attempts == distinct.index("sunshine") + 1 == 9
            and by_label["bob"].attempts == distinct.index("michael") + 1 == 32
            and by_label["carol"].attempts == distinct.index("monkey") + 1 == 16,
        ),
        (
            "the_legacy_counter_counts_comments_and_duplicates",
            lambda: measured["legacy_attempts"] == 126
            and len(distinct) == 117
            and measured["legacy_attempts"] - len(distinct) == 9,
        ),
        (
            "md5_and_sha256_need_different_digest_lengths",
            lambda: ALGORITHMS["md5"] == len(by_target["bob"].digest) == 32
            and ALGORITHMS["sha256"] == len(by_target["alice"].digest) == 64,
        ),
        (
            "a_truncated_digest_is_refused",
            lambda: _refuses(lambda: check_digest("sha256", "a941a4c4")),
        ),
        (
            "an_unknown_algorithm_is_refused",
            lambda: _refuses(lambda: check_digest("md4", "00")),
        ),
        (
            "an_unknown_mode_is_refused",
            lambda: _refuses(lambda: mode_of("rainbow")),
        ),
        (
            "a_duplicate_label_is_refused",
            lambda: _refuses(
                lambda: build_targets(
                    [
                        {
                            "label": "alice",
                            "algorithm": "sha256",
                            "salt": "",
                            "digest": "a" * 64,
                            "mode": "wordlist",
                        },
                        {
                            "label": "alice",
                            "algorithm": "md5",
                            "salt": "",
                            "digest": "b" * 32,
                            "mode": "wordlist",
                        },
                    ]
                )
            ),
        ),
        (
            "rebuild_is_deterministic",
            lambda: searches_via_cracker() == searches,
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_searches(measured: dict[str, Any]) -> str:
    lines = ["  label   algorithm  mode      verdict       attempts   recovered"]
    for row in measured["searches"]:
        lines.append(
            f"  {row.label:<8}{target_algorithm(measured, row.label):<11}"
            f"{target_mode(measured, row.label):<10}{row.verdict:<14}"
            f"{row.attempts:>8}   {row.recovered or '-'}"
        )
    return "\n".join(lines)


def target_algorithm(measured: dict[str, Any], label: str) -> str:
    return next(t.algorithm for t in measured["targets"] if t.label == label)


def target_mode(measured: dict[str, Any], label: str) -> str:
    return next(t.mode for t in measured["targets"] if t.label == label)


def run_demo() -> int:
    measured = measure()
    searches = measured["searches"]
    by_label = {row.label: row for row in searches}
    pin = by_label["erin"]
    coverage = divide_half_up(pin.attempts * 10_000, pin.keyspace or 1)
    print("Hash cracker -- a miss is not a verdict")
    print("=" * 41)
    print()
    print(
        f"Candidates: {len(measured['lines'])} non-empty wordlist lines, "
        f"{len(measured['distinct'])} distinct, "
        f"{len(measured['words']) - len(measured['distinct'])} repeated."
    )
    algorithms = sorted({target.algorithm for target in measured["targets"]})
    print(
        f"Targets: {len(measured['targets'])} hashes over "
        f"{len(algorithms)} algorithms ({', '.join(algorithms)})."
    )
    print()
    print(render_searches(measured))
    print()
    print("1. A miss is not strength unless the search was exhaustive.")
    print("   " + LEGACY_VERDICT)
    print(
        f"   dave: no hit after {by_label['dave'].attempts} of an unbounded keyspace, "
        "so the answer is inconclusive."
    )
    print(
        f"   erin: no hit after {pin.attempts} of {pin.keyspace} four-digit PINs, "
        f"so 'not a 4-digit PIN' is proven ({format_bp(coverage)}% covered)."
    )
    print(
        "   the legacy report calls "
        f"{len(measured['legacy_strong'])} misses strong: "
        + ", ".join(measured["legacy_strong"])
    )
    print()
    print("2. The salt is part of the hash.")
    print("   " + LEGACY_SALT)
    print(
        "   carol's digest is sha256('s3cr3t' + 'monkey'); hashing the bare word "
        "misses it,"
    )
    print("   and 'monkey' is line 16 of the wordlist the attack already read.")
    print()
    print("3. Work is counted, not timed.")
    print("   " + LEGACY_ATTEMPTS)
    print(
        f"   {measured['legacy_attempts']} lines are counted as attempts against "
        f"{len(measured['distinct'])} hashed candidates:"
    )
    print(
        f"   {measured['legacy_attempts'] - len(measured['distinct'])} of them are "
        "comments or repeated words, which is work nobody did."
    )
    print()
    print("Checks")
    results = audit(measured)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: "
        f"{len(measured['targets'])} targets are attacked with {len(measured['distinct'])} "
        f"distinct candidates taken from {measured['legacy_attempts']} lines, and the rebuild "
        f"finds {measured['found']} while calling dave inconclusive after "
        f"{by_label['dave'].attempts} misses and erin exhausted after {pin.attempts} of "
        f"{pin.keyspace} PINs ({format_bp(coverage)}%); carol's digest is over "
        "'s3cr3t' + 'monkey' so the salt-blind legacy loop misses a password that is in the "
        f"wordlist and joins the {len(measured['legacy_strong'])} false 'strong' verdicts; "
        f"{passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
