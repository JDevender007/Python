"""A password generator with a policy, an entropy estimate and a history.

Generating a password is one line of ``random.choice``. Deciding whether the
result is *good* is the actual work, so this project makes the policy explicit
and the entropy countable:

    pool   the union of every character set the policy allows
    bits   length * log2(len(pool))

A 16-character password drawn from 26 lower + 26 upper + 10 digits + 27 symbols
has a pool of 89, so ``16 * log2(89) = 103.2`` bits. The label follows the
conventional bands (under 40 weak, under 60 fair, under 80 strong, else
excellent) â€” and the code computes it from the pool rather than guessing from
the length alone, which is the mistake behind "16 characters must be strong"
when the 16 characters are all lowercase.

Two rules keep the output honest:

    coverage   at least the requested minimum of each class is *guaranteed*,
               not hoped for, by planting those characters before shuffling
    exclusion  ambiguous characters (O 0 o I l 1 |) can be removed for
               policies that will be read aloud or typed by hand

Randomness is injectable: pass ``random.Random(seed)`` for a reproducible run,
or leave it out and ``SystemRandom`` is used. Nothing here is cryptographic
advice; it is a study of policy, entropy and validation.

Fully offline: no network, no clipboard, no files unless you ask.
"""

from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

LOWER = "abcdefghijklmnopqrstuvwxyz"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?/|~"
AMBIGUOUS = "O0oIl1|`'\";:,.{}[]()/\\"

MIN_LENGTH = 8
MAX_LENGTH = 128

WEAK_MAX_BITS = 40
FAIR_MAX_BITS = 60
STRONG_MAX_BITS = 80


class PasswordError(ValueError):
    """A policy, password or history operation that cannot be used."""


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Policy:
    """What a generated password must look like.

    The four class fields are *minimums*, counted after generation, so a
    policy can require two digits without forbidding a third.
    """

    length: int = 16
    min_lower: int = 1
    min_upper: int = 1
    min_digits: int = 1
    min_symbols: int = 1
    forbid_ambiguous: bool = False
    name: str = "custom"

    def __post_init__(self) -> None:
        if not isinstance(self.length, int) or isinstance(self.length, bool):
            raise PasswordError("length must be an integer")
        if not MIN_LENGTH <= self.length <= MAX_LENGTH:
            raise PasswordError(
                f"length must be between {MIN_LENGTH} and {MAX_LENGTH}, "
                f"got {self.length}")
        for field_name in ("min_lower", "min_upper", "min_digits",
                           "min_symbols"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise PasswordError(f"{field_name} must be an integer")
            if value < 0:
                raise PasswordError(f"{field_name} must not be negative")
        requested = self.minimum_total
        if requested > self.length:
            raise PasswordError(
                f"the minimums need {requested} characters but length is "
                f"{self.length}")
        if requested == 0:
            raise PasswordError("at least one character class must be required")

    # -- derived ---------------------------------------------------------- #
    @property
    def minimum_total(self) -> int:
        return (self.min_lower + self.min_upper
                + self.min_digits + self.min_symbols)

    def charsets(self) -> dict[str, str]:
        """The character set for each required class, after exclusions."""
        sets = {
            "lower": LOWER,
            "upper": UPPER,
            "digits": DIGITS,
            "symbols": SYMBOLS,
        }
        if self.forbid_ambiguous:
            sets = {name: "".join(ch for ch in chars
                                 if ch not in AMBIGUOUS)
                    for name, chars in sets.items()}
        return sets

    @property
    def pool(self) -> str:
        """Every character the policy allows, de-duplicated and sorted."""
        chars: list[str] = []
        for name, count in (("lower", self.min_lower), ("upper", self.min_upper),
                            ("digits", self.min_digits),
                            ("symbols", self.min_symbols)):
            if count:
                chars.extend(self.charsets()[name])
        return "".join(sorted(set(chars)))

    @property
    def pool_size(self) -> int:
        return len(self.pool)

    @property
    def entropy_bits(self) -> float:
        return round(self.length * math.log2(self.pool_size), 2)

    @property
    def label(self) -> str:
        return strength_label(self.entropy_bits)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "length": self.length,
            "min_lower": self.min_lower,
            "min_upper": self.min_upper,
            "min_digits": self.min_digits,
            "min_symbols": self.min_symbols,
            "forbid_ambiguous": self.forbid_ambiguous,
        }

    @classmethod
    def from_dict(cls, payload: dict, name: str = "custom") -> "Policy":
        if not isinstance(payload, dict):
            raise PasswordError("a policy must be a mapping")
        allowed = set(cls.__dataclass_fields__)
        unknown = set(payload) - allowed
        if unknown:
            raise PasswordError(
                f"unknown policy field(s): {', '.join(sorted(unknown))}")
        values = dict(payload)
        values.setdefault("name", name)
        return cls(**values)


def strength_label(bits: float) -> str:
    if bits < WEAK_MAX_BITS:
        return "weak"
    if bits < FAIR_MAX_BITS:
        return "fair"
    if bits < STRONG_MAX_BITS:
        return "strong"
    return "excellent"


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def _pick(rng, text: str) -> str:
    return text[rng.randrange(len(text))]


def generate(policy: Policy, rng: random.Random | None = None) -> str:
    """A password that satisfies every minimum in the policy."""
    if not isinstance(policy, Policy):
        raise PasswordError("policy must be a Policy")
    source = rng if rng is not None else random.SystemRandom()
    sets = policy.charsets()

    chars: list[str] = []
    for name, count in (("lower", policy.min_lower), ("upper", policy.min_upper),
                        ("digits", policy.min_digits),
                        ("symbols", policy.min_symbols)):
        for _ in range(count):
            chars.append(_pick(source, sets[name]))
    pool = policy.pool
    while len(chars) < policy.length:
        chars.append(_pick(source, pool))
    source.shuffle(chars)
    return "".join(chars)


def generate_many(policy: Policy, count: int,
                  rng: random.Random | None = None) -> list[str]:
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise PasswordError("count must be a positive integer")
    return [generate(policy, rng) for _ in range(count)]


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def count_classes(password: str, policy: Policy) -> dict[str, int]:
    """How many characters of each required class the password contains."""
    sets = policy.charsets()
    counts: dict[str, int] = {}
    for name in ("lower", "upper", "digits", "symbols"):
        counts[name] = sum(1 for ch in password if ch in sets[name])
    return counts


def validate(password: str, policy: Policy) -> list[str]:
    """Every reason the password does not meet the policy (empty is good)."""
    if not isinstance(password, str):
        raise PasswordError("password must be text")
    problems: list[str] = []
    if len(password) < policy.length:
        problems.append(
            f"needs {policy.length} characters, has {len(password)}")
    if len(password) > MAX_LENGTH:
        problems.append(f"is longer than {MAX_LENGTH} characters")
    counts = count_classes(password, policy)
    for name, minimum in (("lower", policy.min_lower),
                          ("upper", policy.min_upper),
                          ("digits", policy.min_digits),
                          ("symbols", policy.min_symbols)):
        if counts[name] < minimum:
            problems.append(
                f"needs {minimum} {name} character(s), has {counts[name]}")
    if policy.forbid_ambiguous:
        found = sorted({ch for ch in password if ch in AMBIGUOUS})
        if found:
            problems.append(
                f"contains ambiguous character(s): {' '.join(found)}")
    pool = set(policy.pool)
    outside = sorted({ch for ch in password if ch not in pool})
    if outside:
        problems.append(
            f"contains character(s) outside the policy: {' '.join(outside)}")
    return problems


def is_compliant(password: str, policy: Policy) -> bool:
    return not validate(password, policy)


# --------------------------------------------------------------------------- #
# Strength of an existing password
# --------------------------------------------------------------------------- #
def observed_pool(password: str) -> str:
    chars = set(password)
    pool = ""
    if chars & set(LOWER):
        pool += LOWER
    if chars & set(UPPER):
        pool += UPPER
    if chars & set(DIGITS):
        pool += DIGITS
    if chars & set(SYMBOLS):
        pool += SYMBOLS
    return "".join(sorted(pool))


def strength(password: str) -> dict:
    """Estimate the strength of a password from the characters it actually uses.

    The bit count assumes every character was drawn uniformly at random. A
    pattern — a repeated run, a dictionary fragment — disproves that
    assumption, so any password with a warning is labelled ``weak`` no matter
    how many bits the arithmetic claims.
    """
    if not isinstance(password, str):
        raise PasswordError("password must be text")
    if not password:
        raise PasswordError("password must not be empty")
    pool = observed_pool(password)
    classes = sum(1 for group in (LOWER, UPPER, DIGITS, SYMBOLS)
                  if set(password) & set(group))
    bits = round(len(password) * math.log2(len(pool)), 2) if pool else 0.0
    repeat = max_repeat(password)
    warnings = pattern_warnings(password)
    label = "weak" if warnings else strength_label(bits)
    return {
        "length": len(password),
        "classes": classes,
        "pool_size": len(pool),
        "entropy_bits": bits,
        "label": label,
        "repeated": repeat,
        "warnings": warnings,
    }


def max_repeat(password: str) -> int:
    best = 1
    run = 1
    for previous, current in zip(password, password[1:]):
        run = run + 1 if current == previous else 1
        best = max(best, run)
    return best if password else 0


COMMON_FRAGMENTS = ("password", "admin", "welcome", "letmein", "qwerty",
                    "iloveyou", "monkey", "dragon", "123456")


def pattern_warnings(password: str) -> list[str]:
    warnings: list[str] = []
    lowered = password.lower()
    for fragment in COMMON_FRAGMENTS:
        if fragment in lowered:
            warnings.append(f"contains the common fragment {fragment!r}")
    if max_repeat(password) >= 3:
        warnings.append("contains a character repeated three or more times")
    reversed_password = lowered[::-1]
    if any(fragment == reversed_password for fragment in COMMON_FRAGMENTS):
        warnings.append("is a common password reversed")
    return warnings


# --------------------------------------------------------------------------- #
# History
# --------------------------------------------------------------------------- #
@dataclass
class PasswordHistory:
    """A bounded list of previously generated passwords, newest last."""

    limit: int = 10
    entries: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.limit, int) or isinstance(self.limit, bool):
            raise PasswordError("limit must be an integer")
        if self.limit < 1:
            raise PasswordError("limit must be at least 1")

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, password: object) -> bool:
        return password in self.entries

    def add(self, password: str) -> str:
        if not isinstance(password, str) or not password:
            raise PasswordError("password must be a non-empty string")
        if password in self.entries:
            raise PasswordError("this password was already used")
        self.entries.append(password)
        if len(self.entries) > self.limit:
            del self.entries[0:len(self.entries) - self.limit]
        return password

    def clear(self) -> None:
        self.entries.clear()

    def to_dicts(self) -> list[dict]:
        return [{"index": index, "length": len(password)}
                for index, password in enumerate(self.entries)]


def generate_unique(policy: Policy, history: PasswordHistory,
                    rng: random.Random | None = None,
                    attempts: int = 100) -> str:
    """Generate until the password is new, then record it."""
    if not isinstance(history, PasswordHistory):
        raise PasswordError("history must be a PasswordHistory")
    for _ in range(attempts):
        candidate = generate(policy, rng)
        if candidate not in history:
            history.add(candidate)
            return candidate
    raise PasswordError(
        f"could not find a new password in {attempts} attempts")


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
SEED = 42


def run_demo() -> int:
    print("=" * 70)
    print(" PASSWORD GENERATOR - policy, entropy, validation, history")
    print("=" * 70)

    standard = Policy(name="standard")
    assert standard.length == 16
    assert standard.minimum_total == 4
    assert standard.pool_size == 88
    assert standard.entropy_bits == 103.35
    assert standard.label == "excellent"
    print(f"  standard: length {standard.length}, pool {standard.pool_size}, "
          f"{standard.entropy_bits} bits -> {standard.label}")

    # 1. the same seed gives the same password, a different seed does not
    first = generate(standard, random.Random(SEED))
    second = generate(standard, random.Random(SEED))
    assert first == second
    assert generate(standard, random.Random(SEED + 1)) != first
    assert len(first) == 16
    assert is_compliant(first, standard)
    print(f"  seed {SEED} is reproducible; length and compliance hold")

    # 2. every policy minimum is guaranteed, not merely likely
    rng = random.Random(7)
    for _ in range(300):
        candidate = generate(standard, rng)
        counts = count_classes(candidate, standard)
        assert counts["lower"] >= 1 and counts["upper"] >= 1
        assert counts["digits"] >= 1 and counts["symbols"] >= 1
    print("  300 generated passwords all meet every class minimum")

    # 3. two digits and two symbols are minima, not exact counts
    greedy = Policy(length=12, min_lower=2, min_upper=2, min_digits=2,
                    min_symbols=2)
    sample = generate(greedy, random.Random(3))
    counts = count_classes(sample, greedy)
    assert all(counts[name] >= 2 for name in counts)
    assert sum(counts.values()) == 12

    # 4. a digits-only policy has the smallest pool
    pin = Policy(length=8, min_lower=0, min_upper=0, min_digits=8,
                 min_symbols=0, name="pin")
    assert pin.pool == DIGITS
    assert pin.entropy_bits == 26.58
    assert pin.label == "weak"
    assert re.fullmatch(r"\d{8}", generate(pin, random.Random(1)))
    print(f"  pin policy: pool {pin.pool_size}, {pin.entropy_bits} bits "
          f"-> {pin.label}")

    # 5. ambiguous characters can be excluded entirely
    clean = Policy(length=20, forbid_ambiguous=True)
    rng = random.Random(11)
    for _ in range(200):
        candidate = generate(clean, rng)
        assert not set(candidate) & set(AMBIGUOUS), candidate
    assert clean.pool_size < Policy(length=20).pool_size
    print(f"  ambiguous-free pool {clean.pool_size} vs "
          f"{Policy(length=20).pool_size}")

    # 6. validation names every problem at once
    problems = validate("short", standard)
    assert any("needs 16 characters" in p for p in problems)
    assert any("upper" in p for p in problems)
    assert any("digits" in p for p in problems)
    assert any("symbols" in p for p in problems)
    assert len(problems) >= 4

    weak = "aaaaaaaaaaaaaaaa"
    assert is_compliant(weak, Policy(length=16, min_lower=1, min_upper=0,
                                     min_digits=0, min_symbols=0)) is True
    assert strength(weak)["label"] == "weak"
    assert strength(weak)["repeated"] == 16
    assert strength(weak)["classes"] == 1
    print(f"  16 identical letters: {strength(weak)['entropy_bits']} bits, "
          f"label {strength(weak)['label']}")

    # 7. strength bands come from the pool, not the length
    assert strength("abcdefgh")["label"] == "weak"
    assert strength(first)["label"] == "excellent"
    assert strength("CorrectHorse9!")["classes"] == 4
    assert strength("CorrectHorse9!")["pool_size"] == 88

    # 8. pattern warnings: common fragments and repeats
    assert any("common fragment" in w for w in pattern_warnings("PassWord123!"))
    assert any("repeated three" in w for w in pattern_warnings("aaabbb123!"))
    assert pattern_warnings(first) == []
    assert any("reversed" in w for w in pattern_warnings("drowssap"))
    print("  pattern warnings: common fragment, repeats, reversed password")

    # 9. history refuses reuse and stays bounded
    history = PasswordHistory(limit=3)
    history_rng = random.Random(5)
    for _ in range(5):
        generate_unique(standard, history, history_rng)
    assert len(history) == 3
    assert len(history.entries[0]) == 16
    try:
        history.add(history.entries[-1])
    except PasswordError as exc:
        assert "already used" in str(exc)
    else:
        raise AssertionError("reuse should be refused")
    assert [row["index"] for row in history.to_dicts()] == [0, 1, 2]
    history.clear()
    assert len(history) == 0
    print("  history keeps the last 3 of 5 and refuses a repeat")

    # 10. negative controls: four impossible policies
    for factory, needle in (
        (lambda: Policy(length=7), "between 8 and 128"),
        (lambda: Policy(length=129), "between 8 and 128"),
        (lambda: Policy(min_lower=0, min_upper=0, min_digits=0,
                        min_symbols=0), "at least one character class"),
        (lambda: Policy(length=8, min_digits=9), "but length is 8"),
        (lambda: Policy.from_dict({"min_digits": 2, "colour": "blue"}),
         "unknown policy field"),
        (lambda: PasswordHistory(limit=0), "at least 1"),
    ):
        try:
            factory()
        except PasswordError as exc:
            assert needle in str(exc), (needle, str(exc))
        else:
            raise AssertionError("expected PasswordError")
    print("  6 invalid policies or histories rejected")

    # 11. a policy can round-trip through JSON
    payload = standard.to_dict()
    again = Policy.from_dict(payload)
    assert again == standard
    assert json.loads(json.dumps(payload))["length"] == 16

    # 12. entropy is monotonic in length for a fixed pool
    short = Policy(length=12)
    long = Policy(length=24)
    assert short.pool_size == long.pool_size
    assert long.entropy_bits > short.entropy_bits
    assert abs(long.entropy_bits - 2 * short.entropy_bits) < 0.02

    print()
    print("Cross-checks OK: 103.35-bit standard policy, seeded output "
          "reproducible and seed-distinct, 300 passwords all meeting every "
          "class minimum, minima not exact counts, digits-only policy at 26.58 "
          "bits labelled weak, 200 ambiguous-free passwords, 4 problems named "
          "at once, strength from the observed pool not the length, 3 pattern "
          "warnings, bounded history refusing reuse, 6 invalid policies "
          "rejected, policy JSON round-trip, entropy doubling with length")
    print("\nDemo completed successfully.")
    return 0
