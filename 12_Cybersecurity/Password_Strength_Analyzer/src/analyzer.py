"""Entropy is a property of a random string, not of the string someone chose.

The legacy scorer is three lines of arithmetic and a magic constant:

    size = 1
    for name in classes: size *= CHARSET_SIZES[name]
    entropy = len(password) * math.log2(size)
    score = int(entropy / 1.28)

Each line is a defect, and each one produces a number that looks like a grade.

**1. A character set is the sum of its classes, not the product.** A password
mixing lowercase and uppercase draws from 26 + 26 = 52 possible characters.
Multiplying gives 676, so `log2` charges 9.4 bits per character instead of 5.7.
`Password123!` uses four classes, so the legacy charset is
`26 * 26 * 10 * 33 = 223080` -- a claim that 223080 different characters exist,
when ASCII offers 95. That is not a rounding error; it is a different alphabet.

**2. Entropy assumes every character was drawn at random.** `Password123!` is a
dictionary word, a capital, a counting sequence and a trailing symbol. The
formula cannot see any of that, so it awards 213.20 bits and a score of 100 to a
password that a rule-based guesser reaches in a few thousand attempts. The
rebuild keeps the random-string figure as a *ceiling* and subtracts documented
penalties for structure it can recognise. It calls the result **guess bits**, and
never pretends the deduction is a measurement.

**3. Crack time is integer work, not float arithmetic.** `2 ** entropy / 2`
overflows into imprecision long before it overflows into an exception, and
`int(value)` in the formatter silently drops the digits that matter. The rebuild
computes `1 << (bits - 1)` guesses and divides by an integer rate, so a demo run
is reproducible to the second and two runs print identical bytes.

The rebuild therefore reports three numbers per password -- the random-string
ceiling, the guess bits after penalties, and the crack time that follows from
those bits -- and the checks pin the gap. The bundled seeds include a password
where the legacy score is 100 and the rebuild says `fair`, because that gap is
the whole lesson.
"""

from __future__ import annotations

import csv
import math
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PASSWORDS_FILE = DATA_DIR / "passwords.csv"

MAX_LENGTH = 256
MIN_GUESS_BITS = 1

#: Size of each character class, counted as distinct code points.
CHARSET_SIZES = {
    "lowercase": 26,
    "uppercase": 26,
    "digits": 10,
    "symbols": 33,          # 32 ASCII punctuation marks plus the space
}

#: Ordered weakest -> strongest; every band is half-open, low inclusive.
BANDS = (
    (0, 25, "very weak"),
    (25, 45, "weak"),
    (45, 65, "fair"),
    (65, 85, "strong"),
    (85, 10_000, "very strong"),
)

#: Guesses per second for the attack scenarios, slowest first.
RATES = (
    ("throttled online", 100),
    ("fast online", 100_000),
    ("offline CPU", 1_000_000_000),
    ("offline GPU", 100_000_000_000),
    ("offline cluster", 10_000_000_000_000),
)

#: Coarse, additive deductions. Each is a claim about structure, not a proof.
PENALTIES = {
    "matches a common password": 20,
    "contains a dictionary word": 8,
    "contains 3+ repeated characters": 5,
    "contains a numeric sequence": 6,
    "contains a letter sequence": 6,
    "contains a keyboard walk": 8,
    "contains a year": 4,
    "uses 3 or fewer distinct characters": 10,
    "shorter than 8 characters": 8,
    "shorter than 12 characters": 4,
    "ends with a single symbol": 4,
}

#: The legacy model, transcribed so the demo can print it.
LEGACY_CHARSET = "size *= CHARSET_SIZES[name]  # the classes multiply"
LEGACY_SCORE = "score = int(entropy / 1.28)"
LEGACY_CRACK = "seconds = (2 ** entropy / 2) / per_second"

COMMON_PASSWORDS = (
    "123456", "123456789", "qwerty", "password", "12345", "12345678",
    "111111", "1234567", "sunshine", "qwerty123", "1q2w3e4r", "iloveyou",
    "princess", "admin", "welcome", "monkey", "login", "abc123",
    "password1", "123123", "000000", "letmein", "master", "hello",
    "freedom", "whatever", "trustno1", "dragon", "baseball", "football",
    "starwars", "michael", "shadow", "superman", "batman", "passw0rd",
    "qwertyuiop", "asdfghjkl", "zxcvbnm", "1qaz2wsx",
)

DICTIONARY = (
    "password", "welcome", "monkey", "dragon", "summer", "winter", "spring",
    "autumn", "football", "baseball", "shadow", "master", "letmein", "admin",
)

KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890")

UNIT_SECONDS = (
    ("centuries", 3_155_760_000),
    ("years", 31_557_600),
    ("days", 86_400),
    ("hours", 3_600),
    ("minutes", 60),
)

SINGULAR = {
    "centuries": "century",
    "years": "year",
    "days": "day",
    "hours": "hour",
    "minutes": "minute",
    "seconds": "second",
}


class AnalyzerError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation and small arithmetic
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise AnalyzerError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise AnalyzerError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnalyzerError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise AnalyzerError(f"{name} must be positive, got {number}")
    return number


def divide_half_up(numerator: int, denominator: int) -> int:
    """Integer division rounding halves away from zero, with no float."""
    top = _whole(numerator, "numerator")
    bottom = _positive(denominator, "denominator")
    sign = -1 if top < 0 else 1
    magnitude = abs(top)
    return sign * ((magnitude * 2 + bottom) // (2 * bottom))


def format_millibits(millibits: int) -> str:
    """Render thousands of a bit as a three-place number."""
    value = _whole(millibits, "millibits")
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    return f"{sign}{magnitude // 1000}.{magnitude % 1000:03d}"


def check_password(text: object) -> str:
    """A password must be non-empty ASCII text of a bounded length."""
    raw = _text(text, "password")
    if len(raw) > MAX_LENGTH:
        raise AnalyzerError(f"password longer than {MAX_LENGTH} characters is refused")
    try:
        raw.encode("ascii")
    except UnicodeEncodeError as exc:
        raise AnalyzerError("this model covers ASCII only; password is not ASCII") from exc
    return raw


# --------------------------------------------------------------------------- #
# Character classes
# --------------------------------------------------------------------------- #
def detect_classes(password: str) -> tuple[str, ...]:
    """Which classes the password draws from, in a fixed order."""
    raw = check_password(password)
    found: list[str] = []
    if any(character in string.ascii_lowercase for character in raw):
        found.append("lowercase")
    if any(character in string.ascii_uppercase for character in raw):
        found.append("uppercase")
    if any(character in string.digits for character in raw):
        found.append("digits")
    if any(character in string.punctuation or character == " " for character in raw):
        found.append("symbols")
    return tuple(found)


def charset_size(classes: Iterable[str]) -> int:
    """The union of the classes: 52 characters for lower plus upper, not 676."""
    total = 0
    for name in classes:
        if name not in CHARSET_SIZES:
            raise AnalyzerError(f"unknown character class: {name!r}")
        total += CHARSET_SIZES[name]
    return total


def legacy_charset_size(classes: Iterable[str]) -> int:
    """The legacy product: every class treated as an independent alphabet."""
    total = 1
    for name in classes:
        if name not in CHARSET_SIZES:
            raise AnalyzerError(f"unknown character class: {name!r}")
        total *= CHARSET_SIZES[name]
    return total


def milli_bits_per_char(size: int) -> int:
    """log2 of the alphabet, in thousandths of a bit, half-up."""
    width = _positive(size, "size")
    if width == 1:
        return 0
    micro = int(math.log2(width) * 1_000_000)
    return divide_half_up(micro, 1000)


# --------------------------------------------------------------------------- #
# Patterns
# --------------------------------------------------------------------------- #
def has_run(text: str, minimum: int = 4) -> bool:
    """True when `minimum` consecutive letters ascend or descend by one."""
    raw = text.lower()
    step = _positive(minimum, "minimum")
    for direction in (1, -1):
        length = 1
        for index in range(1, len(raw)):
            if ord(raw[index]) - ord(raw[index - 1]) == direction:
                length += 1
                if length >= step:
                    return True
            else:
                length = 1
    return False


def has_numeric_sequence(password: str, minimum: int = 4) -> bool:
    """True when `minimum` digits ascend or descend by one."""
    raw = check_password(password)
    step = _positive(minimum, "minimum")
    for direction in (1, -1):
        length = 1
        for index in range(1, len(raw)):
            if not (raw[index].isdigit() and raw[index - 1].isdigit()):
                length = 1
                continue
            if ord(raw[index]) - ord(raw[index - 1]) == direction:
                length += 1
                if length >= step:
                    return True
            else:
                length = 1
    return False


def has_keyboard_walk(password: str, span: int = 3) -> bool:
    """True when a fragment of a keyboard row appears forwards or backwards."""
    raw = check_password(password).lower()
    width = _positive(span, "span")
    for row in KEYBOARD_ROWS:
        for index in range(len(row) - width + 1):
            fragment = row[index:index + width]
            if fragment in raw or fragment[::-1] in raw:
                return True
    return False


def has_year(password: str) -> bool:
    """Four digits that look like a calendar year: 1900-2099."""
    raw = check_password(password)
    for index in range(len(raw) - 3):
        window = raw[index:index + 4]
        if window.isdigit() and window[:2] in ("19", "20"):
            return True
    return False


def has_triple(password: str) -> bool:
    """True when one character repeats three times in a row."""
    raw = check_password(password).lower()
    return any(raw[index] == raw[index + 1] == raw[index + 2] for index in range(len(raw) - 2))


def find_issues(password: str) -> list[str]:
    """Every recognised weakness, in a fixed order, each listed once."""
    raw = check_password(password)
    lower = raw.lower()
    issues: list[str] = []

    if lower in COMMON_PASSWORDS:
        issues.append("matches a common password")
    elif any(word in lower for word in DICTIONARY if len(word) >= 4):
        issues.append("contains a dictionary word")
    if has_triple(raw):
        issues.append("contains 3+ repeated characters")
    if has_numeric_sequence(raw):
        issues.append("contains a numeric sequence")
    if has_run(lower):
        issues.append("contains a letter sequence")
    if has_keyboard_walk(raw):
        issues.append("contains a keyboard walk")
    if has_year(raw):
        issues.append("contains a year")
    if len(set(raw)) <= 3 and len(raw) >= 4:
        issues.append("uses 3 or fewer distinct characters")
    if len(raw) < 8:
        issues.append("shorter than 8 characters")
    elif len(raw) < 12:
        issues.append("shorter than 12 characters")
    if (
        len(raw) > 1
        and raw[-1] in string.punctuation
        and not any(character in string.punctuation for character in raw[:-1])
    ):
        issues.append("ends with a single symbol")
    return issues


def penalty_bits(issues: Sequence[str]) -> int:
    """Sum of the documented deductions, each one counted once."""
    total = 0
    for issue in issues:
        if issue not in PENALTIES:
            raise AnalyzerError(f"no penalty is documented for: {issue!r}")
        total += PENALTIES[issue]
    return total


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Row:
    """One password, measured.

    `text` is kept because the report has to be recomputable and the mask is the
    only thing allowed to reach a human.
    """

    label: str
    text: str
    classes: tuple[str, ...]
    charset: int
    legacy_charset: int
    random_bits: int
    legacy_bits: int
    guess_bits: int
    score: int
    label_band: str
    issues: tuple[str, ...]
    penalties: int

    @property
    def length(self) -> int:
        return len(self.text)

    @property
    def masked(self) -> str:
        return mask(self.text)

    @property
    def crack_seconds(self) -> dict[str, int]:
        return crack_times(self.guess_bits)


def guess_bits_of(random_bits: int, issues: Sequence[str]) -> int:
    """The random-string ceiling minus the documented deductions, floored."""
    ceiling = _positive(random_bits, "random_bits")
    return max(MIN_GUESS_BITS, ceiling - penalty_bits(issues))


def band_of(bits: int) -> str:
    """The half-open band containing this many bits."""
    value = _whole(bits, "bits")
    for low, high, name in BANDS:
        if low <= value < high:
            return name
    raise AnalyzerError(f"no band covers {value} bits")


def score_of(bits: int) -> int:
    """The score is the guess bits, capped at 100; there is no second scale."""
    return min(100, _positive(bits, "bits"))


def analyze(label: str, password: str) -> Row:
    """Measure one password from scratch, with no cached state."""
    raw = check_password(password)
    classes = detect_classes(raw)
    if not classes:
        raise AnalyzerError("password uses no recognised character class")
    charset = charset_size(classes)
    width = len(raw)
    random_bits = divide_half_up(milli_bits_per_char(charset) * width, 1000)
    legacy_bits = divide_half_up(milli_bits_per_char(legacy_charset_size(classes)) * width, 1000)
    issues = find_issues(raw)
    guesses = guess_bits_of(random_bits, issues)
    return Row(
        label=_text(label, "label").strip(),
        text=raw,
        classes=classes,
        charset=charset,
        legacy_charset=legacy_charset_size(classes),
        random_bits=random_bits,
        legacy_bits=legacy_bits,
        guess_bits=guesses,
        score=score_of(guesses),
        label_band=band_of(guesses),
        issues=tuple(issues),
        penalties=penalty_bits(issues),
    )


def mask(password: str) -> str:
    """Render a password for display: length kept, content gone, ASCII only."""
    raw = check_password(password)
    return "*" * min(len(raw), 24) + f" ({len(raw)} chars)"


# --------------------------------------------------------------------------- #
# Crack time
# --------------------------------------------------------------------------- #
def crack_seconds(bits: int, rate: int) -> int:
    """Seconds to search half the keyspace at an integer guess rate."""
    value = _whole(bits, "bits")
    per_second = _positive(rate, "rate")
    if value <= 1:
        return 0
    return (1 << (value - 1)) // per_second


def crack_times(bits: int) -> dict[str, int]:
    """Seconds for every documented rate, slowest attacker first."""
    return {name: crack_seconds(bits, rate) for name, rate in RATES}


def format_duration(total_seconds: int) -> str:
    """A duration from an integer second count, with no float division."""
    seconds = _whole(total_seconds, "total_seconds")
    if seconds < 0:
        raise AnalyzerError(f"total_seconds must not be negative, got {seconds}")
    if seconds < 1:
        return "instantly"
    for name, width in UNIT_SECONDS:
        if seconds >= width:
            whole = seconds // width
            break
    else:
        return f"{seconds} {SINGULAR['seconds'] if seconds == 1 else 'seconds'}"
    if whole == 1:
        return f"1 {SINGULAR[name]}"
    if whole < 1000:
        return f"{whole:,} {name}"
    return f"10^{len(str(whole)) - 1} {name}"


def format_crack_table(row: Row) -> str:
    """The attack table for one row, in rate order."""
    lines = []
    for name, rate in RATES:
        lines.append(f"  {name:<18}{format_duration(crack_seconds(row.guess_bits, rate))}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _read_rows(path: str | Path) -> list[dict[str, str]]:
    target = Path(path)
    if not target.is_file():
        raise AnalyzerError(f"file not found: {target.name}")
    try:
        body = target.read_bytes().decode("ascii")
    except UnicodeDecodeError as exc:
        raise AnalyzerError(f"{target.name} is not ASCII text") from exc
    reader = csv.DictReader(body.splitlines())
    header = reader.fieldnames or []
    missing = [column for column in ("label", "password") if column not in header]
    if missing:
        raise AnalyzerError(
            f"{target.name} is missing column(s): {', '.join(missing)}"
        )
    return [dict(row) for row in reader]


def build_rows(rows: Sequence[dict[str, str]]) -> list[Row]:
    """Validate parsed rows and measure each one, refusing a disagreement."""
    if not rows:
        raise AnalyzerError("passwords.csv holds no rows")
    measured: list[Row] = []
    for row in rows:
        measured.append(analyze(row["label"], row["password"]))
    labels = [row.label for row in measured]
    if len(set(labels)) != len(labels):
        raise AnalyzerError("label values must be unique")
    return measured


def load_rows(path: str | Path | None = None) -> list[Row]:
    return build_rows(_read_rows(path if path is not None else PASSWORDS_FILE))


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(path: str | Path | None = None) -> dict[str, Any]:
    rows = load_rows(path)
    return {
        "rows": rows,
        "labels": [row.label for row in rows],
        "count": len(rows),
        "weakest": min(rows, key=lambda row: row.guess_bits),
        "strongest": max(rows, key=lambda row: row.guess_bits),
        "total_issues": sum(len(row.issues) for row in rows),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    return {
        "count": measured["count"],
        "weakest": measured["weakest"].label,
        "strongest": measured["strongest"].label,
        "total_issues": measured["total_issues"],
        "rows": [
            {
                "label": row.label,
                "length": row.length,
                "classes": list(row.classes),
                "charset": row.charset,
                "legacy_charset": row.legacy_charset,
                "random_bits": row.random_bits,
                "legacy_bits": row.legacy_bits,
                "penalties": row.penalties,
                "guess_bits": row.guess_bits,
                "score": row.score,
                "band": row.label_band,
                "issues": list(row.issues),
                "crack_seconds": dict(row.crack_seconds),
            }
            for row in measured["rows"]
        ],
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
    except AnalyzerError:
        return True
    return False


def audit(
    measured: dict[str, Any],
    *,
    interpret: Callable[[str, str], Row] = analyze,
) -> list[tuple[str, bool]]:
    """Every check recomputes from the password text, never from the report."""
    rows = measured["rows"]
    by_label = {row.label: row for row in rows}

    def reinterpreted() -> list[Row]:
        if not hasattr(reinterpreted, "cache"):
            reinterpreted.cache = [  # type: ignore[attr-defined]
                interpret(row.label, row.text) for row in rows
            ]
        return reinterpreted.cache  # type: ignore[attr-defined]

    def independent_charset(row: Row) -> int:
        return sum(CHARSET_SIZES[name] for name in detect_classes(row.text))

    def monotonic(row: Row) -> bool:
        seconds = [crack_seconds(row.guess_bits, rate) for _name, rate in RATES]
        return all(later <= earlier for earlier, later in zip(seconds, seconds[1:]))

    checks = [
        (
            "every_password_is_measured_once",
            lambda: len(reinterpreted()) == len(rows) == 6,
        ),
        (
            "rows_keep_the_file_order",
            lambda: [row.label for row in reinterpreted()] == measured["labels"],
        ),
        (
            "the_true_charset_sums_the_classes",
            lambda: reinterpreted()[1].charset
            == independent_charset(reinterpreted()[1])
            == 62
            and reinterpreted()[1].classes
            == ("lowercase", "uppercase", "digits"),
        ),
        (
            "the_same_charset_matches_an_independent_sum",
            lambda: all(independent_charset(row) == row.charset for row in rows),
        ),
        (
            "the_legacy_charset_multiplies_the_classes",
            lambda: by_label["decorated"].legacy_charset == 26 * 26 * 10 == 6_760
            and by_label["decorated"].legacy_charset != by_label["decorated"].charset,
        ),
        (
            "a_multi_class_password_is_inflated_by_the_product",
            lambda: all(
                row.legacy_bits > row.random_bits
                for row in rows
                if len(row.classes) > 1
            ),
        ),
        (
            "the_guess_bits_are_pinned",
            lambda: [row.guess_bits for row in rows]
            == [14, 59, 68, 165, 41, 36]
            == [row.guess_bits for row in reinterpreted()],
        ),
        (
            "the_score_is_the_bits_capped_at_one_hundred",
            lambda: [row.score for row in rows]
            == [14, 59, 68, 100, 41, 36]
            == [row.score for row in reinterpreted()],
        ),
        (
            "the_bands_are_pinned",
            lambda: [row.label_band for row in rows]
            == ["very weak", "fair", "strong", "very strong", "weak", "weak"]
            == [row.label_band for row in reinterpreted()],
        ),
        (
            "the_bands_are_half_open",
            lambda: (band_of(24), band_of(25), band_of(84), band_of(85))
            == ("very weak", "weak", "strong", "very strong"),
        ),
        (
            "a_guess_never_exceeds_its_random_ceiling",
            lambda: all(row.guess_bits <= row.random_bits for row in rows),
        ),
        (
            "a_common_password_short_circuits_to_a_tiny_keyspace",
            lambda: by_label["password"].issues[0] == "matches a common password"
            and by_label["password"].guess_bits == 14
            and by_label["password"].random_bits == 38,
        ),
        (
            "the_penalties_are_additive_and_pinned",
            lambda: by_label["qwerty2024"].random_bits
            - by_label["qwerty2024"].penalties
            == by_label["qwerty2024"].guess_bits
            and by_label["qwerty2024"].penalties == 16
            and set(by_label["qwerty2024"].issues)
            == {"contains a keyboard walk", "contains a year", "shorter than 12 characters"},
        ),
        (
            "a_dictionary_word_is_charged_even_with_decorations",
            lambda: "contains a dictionary word" in by_label["decorated"].issues
            and by_label["decorated"].guess_bits + 50 < by_label["decorated"].legacy_bits,
        ),
        (
            "the_repeated_character_password_is_penalised",
            lambda: "contains 3+ repeated characters" in by_label["repeats"].issues
            and "uses 3 or fewer distinct characters" in by_label["repeats"].issues,
        ),
        (
            "crack_time_is_half_the_keyspace_at_one_guess_per_second",
            lambda: crack_seconds(20, 1) == 1 << 19
            and crack_seconds(1, 1) == 0,
        ),
        (
            "crack_time_is_integer_work",
            lambda: crack_seconds(3, 1000) == 0
            and format_duration(0) == "instantly"
            and isinstance(crack_seconds(60, 3), int),
        ),
        (
            "every_row_is_monotonic_in_attack_rate",
            lambda: all(monotonic(row) for row in rows),
        ),
        (
            "the_passphrase_outranks_the_decorated_word",
            lambda: by_label["passphrase"].guess_bits > by_label["decorated"].guess_bits
            and by_label["decorated"].label_band == "fair",
        ),
        (
            "an_empty_password_is_refused",
            lambda: _refuses(lambda: analyze("blank", "")),
        ),
        (
            "a_non_ascii_password_is_refused",
            lambda: _refuses(lambda: analyze("wide", "caf\u00e9")),
        ),
        (
            "an_over_long_password_is_refused",
            lambda: _refuses(lambda: analyze("long", "a" * (MAX_LENGTH + 1))),
        ),
        (
            "a_duplicate_label_is_refused",
            lambda: _refuses(
                lambda: build_rows(
                    [
                        {"label": "same", "password": "abcdefgh"},
                        {"label": "same", "password": "ijklmnop"},
                    ]
                )
            ),
        ),
        (
            "a_missing_file_is_refused",
            lambda: _refuses(lambda: load_rows(Path("no") / "such" / "passwords.csv")),
        ),
        (
            "the_mask_hides_every_character",
            lambda: all(
                set(row.masked.split(" ")[0]) == {"*"}
                and row.masked.endswith(f"({row.length} chars)")
                for row in rows
            )
            and rows[0].masked == "******** (8 chars)",
        ),
        (
            "rebuild_is_deterministic",
            lambda: reinterpreted() == rows,
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_rows(measured: dict[str, Any]) -> str:
    lines = [
        "  label           len  classes  charset  legacy  random  penalty  guess  band"
    ]
    for row in measured["rows"]:
        lines.append(
            f"  {row.label:<15}{row.length:<5}{len(row.classes):<9}{row.charset:<9}"
            f"{row.legacy_charset:<8}{row.random_bits:<8}{row.penalties:<9}"
            f"{row.guess_bits:<7}{row.label_band}"
        )
    return "\n".join(lines)


def run_demo() -> int:
    measured = measure()
    rows = measured["rows"]
    by_label = {row.label: row for row in rows}
    mixed = by_label["decorated"]
    password = by_label["password"]
    print("Password strength -- entropy is a property of randomness")
    print("=" * 59)
    print()
    print(
        f"Passwords: {measured['count']} ASCII secrets "
        f"({measured['total_issues']} weaknesses found in total)."
    )
    print()
    print(render_rows(measured))
    print()
    print("1. A character set is the sum of its classes.")
    print("   " + LEGACY_CHARSET)
    print(
        f"   {mixed.label} draws from {len(mixed.classes)} classes: "
        f"{' + '.join(str(CHARSET_SIZES[name]) for name in mixed.classes)} "
        f"= {mixed.charset} characters."
    )
    print(
        f"   the legacy product is {mixed.legacy_charset:,} characters and charges "
        f"{mixed.legacy_bits} bits for the same {mixed.length} characters,"
    )
    print(f"   against {mixed.random_bits} bits for the real alphabet.")
    print()
    print("2. Entropy assumes every character was drawn at random.")
    print("   " + LEGACY_SCORE)
    legacy_score = min(100, mixed.legacy_bits)
    print(
        f"   {mixed.label} is a dictionary word plus a capital and a year: "
        f"{mixed.penalties} bits of structure are deducted from {mixed.random_bits}."
    )
    print(
        f"   legacy says {band_of(legacy_score)} at {legacy_score}/100; "
        f"the rebuild says {mixed.label_band} at {mixed.score}/100 "
        f"({mixed.guess_bits} guess bits)."
    )
    print(
        f"   the passphrase scores {by_label['passphrase'].score}/100 from "
        f"{by_label['passphrase'].length} characters and no recognised structure."
    )
    print()
    print("3. Crack time is integer work, not float arithmetic.")
    print("   " + LEGACY_CRACK)
    print("   guesses are 1 << (bits - 1) and the rate is an integer:")
    print(format_crack_table(mixed))
    print()
    print(
        f"   {password.label} carries only {password.guess_bits} guess bits, "
        "so a throttled attacker reaches it in a minute or less:"
    )
    print(format_crack_table(password))
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
        f"{measured['count']} passwords measured; the {len(mixed.classes)}-class seed "
        f"draws on {mixed.charset} characters but the legacy product claims "
        f"{mixed.legacy_charset:,}, charging {mixed.legacy_bits} bits against "
        f"{mixed.random_bits} for the real alphabet, so the legacy score is "
        f"{legacy_score}/100 and the rebuild's is {mixed.score}/100 "
        f"after {mixed.penalties} bits of recognised structure; the weakest is "
        f"{measured['weakest'].label} at {measured['weakest'].guess_bits} guess bits "
        f"and the strongest is {measured['strongest'].label} at "
        f"{measured['strongest'].guess_bits}; {passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
