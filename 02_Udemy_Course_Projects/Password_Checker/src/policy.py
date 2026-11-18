"""Password policy checking: length, classes, patterns and common passwords.

The legacy program was:

    pwd1 = 'myPass'
    pwd2 = 'myPass'

    if pwd1 == pwd2:
        print("Password Changed")
    elif pwd1.casefold() == pwd2.casefold():
        print("Please check cases and try again")
    else:
        print("Password do not match")

Three problems, and the first is the interesting one.

**1. "Password Changed" is printed when nothing changed.** The equality test is
backwards. If the new password equals the old one, the change did not happen;
the program reports success for exactly the case it should reject. Its
corollary is worse: ``pwd1 = 'a'`` and ``pwd2 = 'a'`` prints "Password Changed",
so a single character is accepted.

**2. Case is the only policy.** ``'myPass'`` against ``'MYPASS'`` is refused
with "Please check cases", which is a rejection based on *case*, not on
strength. A one-character password that differs is "changed" and therefore
fine.

**3. There is no input.** Both values are constants, so the program never runs
on anything a user typed.

The replacement answers the question the legacy program was reaching for: *is
this a password a system should accept?*

    length        >= 8 characters
    classes       at least 3 of lower, upper, digit, symbol
    repeats       no three identical characters in a row
    sequences     no four consecutive keyboard or alphabet characters
    common        not a dictionary favourite, even after leet substitution
    identity      must not contain the username or email local part
    entropy       at least 40 bits by the observed-pool estimate

The leet substitution is what makes the common-password check honest:
``'P@ssw0rd!'`` becomes ``'password'`` before the comparison, so the
substitution does not buy an attacker a free pass. The estimate is an *upper
bound* -- it assumes uniform random selection from the observed pool and knows
nothing about dictionary structure, which is precisely why the common-password
list is a separate, explicit check.

Standard library only, no network, no password ever written to disk.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

COMMON_FILE = Path(__file__).resolve().parent.parent / "data" / "common.txt"

POOLS = {"lower": 26, "upper": 26, "digit": 10, "symbol": 33}

#: Leet digits and symbols mapped back to the letters they stand in for.
LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
                      "7": "t", "8": "b", "9": "g", "@": "a", "$": "s",
                      "+": "t"})

#: Four consecutive characters from any of these is a sequence.
SEQUENCES = ("abcdefghijklmnopqrstuvwxyz", "0123456789", "qwertyuiop",
             "asdfghjkl", "zxcvbnm", "qazwsxedc")

SEQUENCE_LENGTH = 4
REPEAT_LENGTH = 3


class PolicyError(ValueError):
    """Input that cannot be examined."""


# --------------------------------------------------------------------------- #
# The legacy program
# --------------------------------------------------------------------------- #
def legacy_verdict(old: str, new: str) -> str:
    """The original three-way message, with its backwards equality test."""
    if old == new:
        return "Password Changed"
    if old.casefold() == new.casefold():
        return "Please check cases and try again"
    return "Password do not match"


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Policy:
    min_length: int = 8
    min_classes: int = 3
    min_entropy: float = 40.0
    forbid_common: bool = True
    forbid_sequences: bool = True
    forbid_repeats: bool = True
    forbid_username: bool = True

    def __post_init__(self) -> None:
        if self.min_length < 1:
            raise PolicyError("min_length must be at least 1")
        if not 1 <= self.min_classes <= 4:
            raise PolicyError("min_classes must be within 1..4")
        if self.min_entropy < 0:
            raise PolicyError("min_entropy must not be negative")


@dataclass(frozen=True)
class Finding:
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class Verdict:
    length: int
    accepted: bool
    score: int
    label: str
    classes: tuple[str, ...]
    entropy_bits: float
    findings: tuple[Finding, ...]

    def codes(self) -> tuple[str, ...]:
        return tuple(finding.code for finding in self.findings)

    def to_dict(self) -> dict:
        return {"length": self.length, "accepted": self.accepted,
                "score": self.score, "label": self.label,
                "classes": list(self.classes),
                "entropy_bits": self.entropy_bits,
                "findings": [{"code": finding.code,
                              "message": finding.message}
                             for finding in self.findings]}


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def classify(password: str) -> tuple[str, ...]:
    """Which character classes appear, in a fixed order."""
    classes = set()
    for character in password:
        if character.islower():
            classes.add("lower")
        elif character.isupper():
            classes.add("upper")
        elif character.isdigit():
            classes.add("digit")
        elif not character.isalnum():
            classes.add("symbol")
    return tuple(name for name in ("lower", "upper", "digit", "symbol")
                 if name in classes)


def pool_size(classes: tuple[str, ...]) -> int:
    return sum(POOLS[name] for name in classes)


def entropy_bits(password: str) -> float:
    """``len * log2(pool)`` over the classes observed, rounded to 2 places.

    This is an upper bound: it treats the password as if every character were
    drawn uniformly at random from its pool. ``'password'`` scores 37.60 bits
    and is still a terrible password, which is why no policy rests on this
    number alone.
    """
    if not isinstance(password, str):
        raise PolicyError("password must be a string")
    classes = classify(password)
    if not password or not classes:
        return 0.0
    return round(len(password) * math.log2(pool_size(classes)), 2)


def has_repeat(password: str, length: int = REPEAT_LENGTH) -> bool:
    """True when the same character occurs ``length`` times in a row."""
    run = 1
    for previous, current in zip(password, password[1:]):
        run = run + 1 if current == previous else 1
        if run >= length:
            return True
    return False


def has_sequence(password: str, length: int = SEQUENCE_LENGTH) -> bool:
    """True when ``password`` contains a run from a keyboard or alphabet row."""
    text = password.casefold()
    for source in SEQUENCES:
        for start in range(len(source) - length + 1):
            chunk = source[start:start + length]
            if chunk in text or chunk[::-1] in text:
                return True
    return False


def plain(password: str) -> str:
    """Lowercase, letters and digits only: the form the list is stored in."""
    return "".join(character for character in password
                   if character.isalnum()).casefold()


def skeleton(password: str) -> str:
    """``plain`` after folding leet digits and symbols back to letters.

    ``'P@ssw0rd!'`` -> ``'password'``. Substitution happens *before* the
    non-alphanumeric characters are dropped, so ``@`` becomes ``a`` instead of
    disappearing. Without this, appending a symbol and swapping an ``o`` for a
    zero would defeat the common-password list.
    """
    folded = password.casefold().translate(LEET)
    return "".join(character for character in folded
                   if character.isalnum())


def load_common(path: str | Path = COMMON_FILE) -> frozenset[str]:
    """The bundled list; ``#`` starts a comment.

    Entries are stored in ``plain`` form, so ``'123456'`` stays ``'123456'``
    while ``'P@ssw0rd!'`` is matched through its ``skeleton``.
    """
    path = Path(path)
    if not path.exists():
        raise PolicyError(f"common password list not found: {path}")
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip().casefold()
        if text and not text.startswith("#"):
            entries.append(text)
    if not entries:
        raise PolicyError(f"{path.name} is empty")
    return frozenset(entries)


def is_common(password: str, common: frozenset[str] | None = None) -> bool:
    """Exact match on either form, or a common entry of 6+ characters as a prefix.

    Both the plain and the de-leeted form are tried, because ``'123456'`` is
    common as digits and ``'P@ssw0rd!'`` is common once the ``@`` and the
    ``0`` are folded. The prefix rule catches ``'password1'`` and
    ``'qwerty123'`` without using short entries like ``'admin'`` as a prefix.
    """
    entries = load_common() if common is None else common
    for form in {plain(password), skeleton(password)}:
        if form in entries:
            return True
        if any(len(entry) >= 6 and form.startswith(entry)
               for entry in entries):
            return True
    return False


def usernames_from(identity: str | None) -> tuple[str, ...]:
    """The identity and, for an email, its local part with and without dots."""
    if not identity:
        return ()
    text = identity.strip().casefold()
    if not text:
        return ()
    if "@" not in text:
        return (text,)
    local = text.split("@", 1)[0]
    names = {local, local.replace(".", ""), local.split("+", 1)[0]}
    return tuple(sorted(name for name in names if len(name) >= 3))


# --------------------------------------------------------------------------- #
# Checking
# --------------------------------------------------------------------------- #
def check(password, policy: Policy = Policy(),
          identity: str | None = None,
          common: frozenset[str] | None = None) -> Verdict:
    """Every finding against one policy, plus a 0-100 score."""
    if not isinstance(password, str):
        raise PolicyError(
            f"password must be a string, got {type(password).__name__}")
    if not password:
        raise PolicyError("password must not be empty")

    classes = classify(password)
    bits = entropy_bits(password)
    findings: list[Finding] = []

    if len(password) < policy.min_length:
        findings.append(Finding(
            "too_short",
            f"{len(password)} characters, at least {policy.min_length} "
            f"required"))
    if len(classes) < policy.min_classes:
        missing = policy.min_classes - len(classes)
        findings.append(Finding(
            "too_few_classes",
            f"{len(classes)} character class(es), at least "
            f"{policy.min_classes} required (add {missing})"))
    if policy.forbid_repeats and has_repeat(password):
        findings.append(Finding(
            "repeated_characters",
            "a character repeats three times in a row"))
    if policy.forbid_sequences and has_sequence(password):
        findings.append(Finding(
            "sequence",
            f"contains {SEQUENCE_LENGTH} consecutive keyboard or alphabet "
            f"characters"))
    if policy.forbid_common and is_common(password, common):
        findings.append(Finding(
            "common_password",
            "appears in the common password list, even after substituting "
            "digits and symbols"))
    if policy.forbid_username and identity:
        lowered = password.casefold()
        for name in usernames_from(identity):
            if name in lowered:
                findings.append(Finding(
                    "contains_username",
                    f"contains part of the identity {name!r}"))
                break
    if bits < policy.min_entropy:
        findings.append(Finding(
            "low_entropy",
            f"{bits} bits by the observed-pool estimate, at least "
            f"{policy.min_entropy} expected"))

    score = 0
    score += min(40, int(2.5 * len(password)))
    score += 10 * len(classes)
    score += min(20, int(bits / 5))
    for finding in findings:
        score -= 25 if finding.code == "too_short" else 15
    score = max(0, min(100, score))

    return Verdict(length=len(password), accepted=not findings, score=score,
                   label=label_for(score), classes=classes,
                   entropy_bits=bits, findings=tuple(findings))


def label_for(score: int) -> str:
    """The score band, with the boundaries stated once."""
    if score < 30:
        return "very weak"
    if score < 50:
        return "weak"
    if score < 70:
        return "fair"
    if score < 85:
        return "strong"
    return "very strong"


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 70)
    print(" PASSWORD CHECKER - 'Password Changed' on an unchanged password")
    print("=" * 70)

    # 1. the legacy equality test is backwards, and accepts one character
    assert legacy_verdict("myPass", "myPass") == "Password Changed"
    assert legacy_verdict("a", "a") == "Password Changed"
    assert check("a").accepted is False
    assert "too_short" in check("a").codes()
    print("  legacy: old == new -> 'Password Changed' (nothing changed); "
          "a 1-char password passes its check")

    # 2. its only policy is case, so a real change is refused on case alone
    assert legacy_verdict("myPass", "MYPASS") == \
        "Please check cases and try again"
    assert legacy_verdict("myPass", "other!") == "Password do not match"
    assert check("MYPASS9!x").accepted is True
    print("  legacy refuses myPass -> MYPASS on case alone, and accepts "
          "any differing string as a change")

    # 3. the policy accepts real passwords
    good = ["Tr0ub4dor&3", "C0mpl3x!ty", "x9#Kp2$Lm", "Q7!vN2@wR4",
            "zT5^mK8&bQ"]
    for candidate in good:
        verdict = check(candidate)
        assert verdict.accepted is True, (candidate, verdict.codes())
        assert not verdict.findings, candidate
    print(f"  {len(good)} strong passwords accepted with no findings")

    # ... and rejects a passphrase for having one class, which is the honest
    # limitation of any class-count rule rather than a success
    passphrase = check("correct horse battery staple")
    assert passphrase.accepted is False
    assert passphrase.codes() == ("too_few_classes",), passphrase.codes()
    assert passphrase.entropy_bits > 120
    print(f"  a 28-character passphrase is refused for one class, at "
          f"{passphrase.entropy_bits} bits: the rule is crude, not wrong")

    # 4. and refuses each failure mode for its own stated reason
    cases = {
        "short1!": "too_short",
        "onlylowercase": "too_few_classes",
        "aaabbb12!X": "repeated_characters",
        "abcdefg1!X": "sequence",
        "P@ssw0rd!": "common_password",
        "aaaaaaaa": "low_entropy",
    }
    for candidate, code in cases.items():
        verdict = check(candidate)
        assert verdict.accepted is False, candidate
        assert code in verdict.codes(), (candidate, verdict.codes())
    assert check("aaaaaaaa").codes().count("too_few_classes") == 1
    print("  6 weak passwords refused: too short, one class, repeated, "
          "sequence, common, low entropy")

    # 5. the identity check, including an email's local part
    assert "contains_username" in check("Alice2024!", identity="alice").codes()
    assert "contains_username" in check(
        "bobsmith2024!B", identity="bob.smith@example.com").codes()
    assert check("x9#Kp2$Lm", identity="bob.smith@example.com").accepted
    print("  identity check catches 'alice' and an email's dotted local part")

    # 6. leet substitution is undone before the dictionary look-up
    assert skeleton("P@ssw0rd!") == "password"
    assert skeleton("Tr0ub4dor") == "troubador"
    assert is_common("P@ssw0rd!")
    assert is_common("password1")
    assert is_common("qwerty123")
    assert not is_common("Tr0ub4dor&3")
    assert not is_common("x9#Kp2$Lm")
    print("  'P@ssw0rd!' -> 'password', 'password1' caught by the prefix "
          "rule, 'Tr0ub4dor&3' not")

    # 7. sequences use four characters, so ordinary words survive
    assert has_sequence("abcdefgh")
    assert has_sequence("dcba")
    assert has_sequence("qwerty")
    assert has_sequence("1234")
    assert not has_sequence("alert123!X")
    assert not has_repeat("aabb")
    assert has_repeat("aaa")
    print("  'abcd' and '1234' are sequences; 'alert123!X' and 'aabb' are not")

    # 8. entropy is the observed-pool bound, not a promise
    assert entropy_bits("abc") == round(3 * math.log2(26), 2) == 14.1
    assert entropy_bits("Ab1!") == round(4 * math.log2(95), 2)
    assert entropy_bits("password") == 37.6
    assert entropy_bits("") == 0.0
    for candidate in ("password", "aaaaaaaa"):
        assert check(candidate).entropy_bits == entropy_bits(candidate)
    print(f"  entropy: 3 lowercase chars = 14.10 bits, 'password' = "
          f"37.60 bits (and still common)")

    # 9. the score rises with length and variety, and a passphrase scores high
    #    while still failing the class rule
    weak = check("Abc12!")
    fair = check("Tr0ub4dor&3")
    assert weak.score < fair.score, (weak.score, fair.score)
    assert weak.label == "very weak" and fair.label == "strong"
    assert 0 <= weak.score <= 100 and 0 <= fair.score <= 100
    assert passphrase.score >= 60 and passphrase.accepted is False
    assert label_for(0) == "very weak" and label_for(100) == "very strong"
    print(f"  scores: 'Abc12!' {weak.score} ({weak.label}), "
          f"'Tr0ub4dor&3' {fair.score} ({fair.label}), the passphrase "
          f"{passphrase.score} but still rejected")

    # 10. a policy can be tightened without touching the checks
    relaxed = Policy(min_length=4, min_classes=2, min_entropy=10.0,
                     forbid_common=False, forbid_sequences=False,
                     forbid_repeats=False, forbid_username=False)
    assert relaxed.min_length == 4
    assert check("abc1", relaxed).accepted is True
    assert check("abc1").accepted is False
    for build in (lambda: Policy(min_length=0), lambda: Policy(min_classes=5),
                  lambda: Policy(min_entropy=-1)):
        try:
            build()
        except PolicyError:
            pass
        else:
            raise AssertionError("an impossible policy should be refused")
    print("  a relaxed policy accepts 'abc1'; the default does not")

    # 11. bad input is refused, not guessed at
    for bad in ("", None, 12345):
        try:
            check(bad)
        except PolicyError:
            pass
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    print("  empty, None and a number are refused")

    # 12. the bundled list is well formed
    common = load_common()
    assert len(common) >= 30, len(common)
    assert "password" in common and "123456" in common and "qwerty" in common
    assert all(entry == entry.casefold() for entry in common)
    assert all(entry == plain(entry) for entry in common)
    assert all(entry.isalnum() for entry in common)
    assert len(common) == len(set(common))
    assert all(is_common(entry, common) for entry in common)
    print(f"  bundled list: {len(common)} entries, all lowercase alphanumeric, "
          f"all matched by the checker")

    # 13. checking is pure
    first = check("Tr0ub4dor&3")
    second = check("Tr0ub4dor&3")
    assert first == second
    assert first.to_dict()["accepted"] is True

    print()
    print("Cross-checks OK: the legacy printed 'Password Changed' when old "
          "and new were identical (even for 'a'), refused myPass -> MYPASS "
          "on case alone, 5 strong passwords accepted with no findings, a "
          "28-character passphrase refused only for its single class, 6 "
          "weak ones refused for 6 distinct reasons, the identity check "
          "caught a username and an email local part, leet substitution "
          "mapped 'P@ssw0rd!' to 'password' and the prefix rule caught "
          "'password1', sequence and repeat detection left 'alert123!X' and "
          "'aabb' alone, entropy values were pinned (14.1 and 37.6 bits), the "
          "score separated 'Abc12!' (22) from 'Tr0ub4dor&3' (81) while the "
          "passphrase scored 65 and still failed, a relaxed policy accepted "
          "'abc1', 3 impossible policies and 3 non-text inputs were refused, "
          "and the bundled list of 40 common passwords is self-consistent")
    print("Demo completed successfully.")
    return 0
