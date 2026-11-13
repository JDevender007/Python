"""Password strength analysis: entropy, patterns, and crack-time estimates.

The analyzer is purely local: passwords are processed in memory, never stored,
logged, or transmitted. Use it to harden your own credentials.
"""

from __future__ import annotations

import math
import re
import string
from dataclasses import asdict, dataclass
from typing import Any

# A small bundled list of the most common passwords (offline, no downloads).
COMMON_PASSWORDS = {
    "123456", "123456789", "qwerty", "password", "12345", "12345678",
    "111111", "1234567", "sunshine", "qwerty123", "1q2w3e4r", "iloveyou",
    "princess", "admin", "welcome", "monkey", "login", "abc123",
    "password1", "123123", "000000", "letmein", "master", "hello",
    "freedom", "whatever", "trustno1", "dragon", "baseball", "football",
    "starwars", "michael", "shadow", "superman", "batman", "passw0rd",
    "p@ssw0rd", "qwertyuiop", "asdfghjkl", "zxcvbnm", "1qaz2wsx",
}

# Ordered weakest -> strongest, cut off at the first matching label.
LABELS = (
    (0, 20, "very weak"),
    (20, 40, "weak"),
    (40, 60, "fair"),
    (60, 80, "strong"),
    (80, 101, "very strong"),
)

# Assumed attack rates (guesses per second) for offline hash cracking.
DEFAULT_RATES: dict[str, float] = {
    "online_slow": 1_000,          # throttled online login
    "online_fast": 100_000,        # fast online service
    "offline_slow": 1_000_000_000,         # 1 GH/s, CPU
    "offline_fast": 100_000_000_000,       # 100 GH/s, GPU rig
    "offline_rig": 10_000_000_000_000,     # 10 TH/s, big rig
}

CHARSET_SIZES = {
    "lowercase": 26,
    "uppercase": 26,
    "digits": 10,
    "symbols": 33,
    "unicode": 100_000,
}


@dataclass
class PasswordReport:
    """Full analysis of one password."""

    length: int
    score: int                 # 0-100
    label: str
    entropy_bits: float
    charset_size: int
    classes_used: list[str]
    issues: list[str]
    crack_times: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_classes(password: str) -> list[str]:
    """Return which character classes the password draws from."""
    classes: list[str] = []
    if re.search(r"[a-z]", password):
        classes.append("lowercase")
    if re.search(r"[A-Z]", password):
        classes.append("uppercase")
    if re.search(r"[0-9]", password):
        classes.append("digits")
    if any(ch in string.punctuation or ch == " " for ch in password):
        classes.append("symbols")  # 32 ASCII punctuation chars + space = 33
    if any(ord(ch) > 127 for ch in password):
        classes.append("unicode")
    return classes


def charset_size(classes: list[str]) -> int:
    """Total number of distinct characters available given the classes."""
    size = 1
    for name in classes:
        size *= CHARSET_SIZES[name]
    return size


def calculate_entropy(password: str) -> tuple[float, int]:
    """Shannon-free guessing entropy: length * log2(charset).

    Returns (entropy_bits, charset_size).
    """
    classes = detect_classes(password)
    if not classes:
        return 0.0, 0
    size = charset_size(classes)
    entropy = len(password) * math.log2(size) if size > 1 else 0.0
    return round(entropy, 2), size


def _has_letter_run(text: str, minimum: int = 4) -> bool:
    """True when `minimum`+ consecutive alphabet letters ascend or descend."""
    for direction in (1, -1):
        run = 1
        for i in range(1, len(text)):
            if ord(text[i]) - ord(text[i - 1]) == direction:
                run += 1
                if run >= minimum:
                    return True
            else:
                run = 1
    return False


def find_patterns(password: str) -> list[str]:
    """Detect sequences, repeats, keyboard walks, and years."""
    issues: list[str] = []
    lower = password.lower()

    if lower in COMMON_PASSWORDS:
        issues.append("matches a common password")

    if re.search(r"(.)\1{2,}", password):
        issues.append("contains 3+ repeated characters")

    if re.search(r"(?:0123|1234|2345|3456|4567|5678|6789|9876|8765|7654|6543|5432|4321|3210)", password):
        issues.append("contains a numeric sequence")

    if _has_letter_run(lower):
        issues.append("contains a letter sequence")

    keyboard_rows = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890")
    for row in keyboard_rows:
        for i in range(len(row) - 2):
            fragment = row[i:i + 3]
            if fragment in lower or fragment[::-1] in lower:
                issues.append("contains a keyboard walk (e.g. qwerty/azwsx)")
                break
        else:
            continue
        break

    if re.search(r"(19|20)\d{2}", password):
        issues.append("contains a year")

    if len(password) < 8:
        issues.append("shorter than 8 characters")
    elif len(password) < 12:
        issues.append("shorter than 12 characters")

    if len(set(password)) <= 3 and len(password) >= 4:
        issues.append("uses 3 or fewer distinct characters")

    # de-duplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            unique.append(issue)
    return unique


def format_duration(seconds: float) -> str:
    """Human-friendly duration for huge crack times."""
    if seconds < 1:
        return "instantly"
    units = (
        ("centuries", 31_536_000_000),
        ("years", 31_536_000),
        ("days", 86_400),
        ("hours", 3_600),
        ("minutes", 60),
        ("seconds", 1),
    )
    for name, width in units:
        if seconds >= width:
            value = seconds / width
            if value >= 100:
                return f"about {int(value):,} {name}"
            if value >= 10:
                return f"about {int(value)} {name}"
            return f"about {value:.1f} {name}"
    return "instantly"


def estimate_crack_times(entropy_bits: float, rates: dict[str, float] | None = None) -> dict[str, str]:
    """Estimate time to exhaustive search at several attack rates."""
    table = rates or DEFAULT_RATES
    times: dict[str, str] = {}
    for name, per_second in table.items():
        if entropy_bits <= 0:
            times[name] = "instantly"
            continue
        combinations = 2 ** entropy_bits
        # assume half the keyspace on average
        seconds = (combinations / 2) / per_second
        times[name] = format_duration(seconds)
    return times


def score_from_entropy(entropy_bits: float) -> tuple[int, str]:
    """Map entropy to a 0-100 score and a human label."""
    score = max(0, min(100, int(entropy_bits / 1.28)))
    for low, high, label in LABELS:
        if low <= score < high:
            return score, label
    return score, "very strong"


def analyze(password: str, rates: dict[str, float] | None = None) -> PasswordReport:
    """Run the full analysis and return a structured report."""
    if password == "":
        raise ValueError("password must not be empty")

    entropy, size = calculate_entropy(password)
    classes = detect_classes(password)
    issues = find_patterns(password)
    score, label = score_from_entropy(entropy)

    # hard caps for weak inputs so a long but trivial password doesn't rate "strong"
    if "matches a common password" in issues:
        score = min(score, 15)
        label = "very weak"
    elif len(set(password)) <= 3 and len(password) >= 4:
        score = min(score, 25)
        label = "weak"
    elif issues and score > 75:
        score = 75
        label = "strong"

    return PasswordReport(
        length=len(password),
        score=score,
        label=label,
        entropy_bits=entropy,
        charset_size=size,
        classes_used=classes,
        issues=issues,
        crack_times=estimate_crack_times(entropy, rates),
    )


def mask(password: str) -> str:
    """Render a password safely for display: keep length, hide content."""
    if not password:
        return "(empty)"
    return "•" * min(len(password), 24) + f" ({len(password)} chars)"


def render_report(report: PasswordReport, password: str | None = None) -> str:
    """Pretty text rendering used by the CLI and demo."""
    lines: list[str] = []
    if password is not None:
        lines.append(f"Password : {mask(password)}")
    lines.append(f"Length   : {report.length}")
    lines.append(f"Classes  : {', '.join(report.classes_used) or 'none'}")
    lines.append(f"Charset  : {report.charset_size:,} distinct characters")
    lines.append(f"Entropy  : {report.entropy_bits} bits")
    lines.append(f"Score    : {report.score}/100 ({report.label})")

    if report.issues:
        lines.append("Issues   :")
        for issue in report.issues:
            lines.append(f"  - {issue}")
    else:
        lines.append("Issues   : none detected")

    lines.append("Estimated time to crack (exhaustive search):")
    for scenario, duration in report.crack_times.items():
        lines.append(f"  {scenario:<14}: {duration}")
    return "\n".join(lines)
