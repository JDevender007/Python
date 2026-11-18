"""Card numbers: Luhn checksum, brand detection and safe masked display.

The legacy program was four lines:

    cardno = (input())
    last_4_digits = cardno[-4:]
    space = ("XXXX XXXX XXXX XXXX" + ' ')
    print(space + last_4_digits)

Three things are wrong with it, and all three are silent.

**It leaks short input.** ``"123"[-4:]`` is ``"123"``, so a three-character
number is printed in full behind a row of placeholders.

**It claims a length it never checked.** The prefix is hard-coded to sixteen
``X``\\ s. An Amex card is fifteen digits, so the output describes twenty
digits of a fifteen-digit number; a Diners card is fourteen. The mask is a
picture of the number, not a redaction of it.

**It never validates.** No Luhn check, no brand, no length policy. A number
with one digit typed wrong is masked and presented as if it were fine.

This module separates the three concerns:

    digits()       normalise "4111-1111 1111 1111" -> "4111111111111111"
    luhn_sum()     the weighted total; a multiple of ten is Luhn-valid
    brand()        Visa / Mastercard / Amex / Discover / Diners / JCB
    length_ok()    the brand's own length policy
    mask()         reveal at most the last four digits, never all of them
    check()        all of the above as one verdict

Luhn validity on its own proves very little -- ``79927398713`` is Luhn-valid
and is not a card number of any brand at any allowed length. That case is in
the bundled data on purpose, and ``check()`` reports it as invalid.

Fully offline: no gateway, no network, no card ever leaves the process.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

BRANDS = ("Visa", "Mastercard", "Amex", "Discover", "Diners", "JCB", "Unknown")

#: Allowed lengths per brand, from each scheme's public rules.
LENGTHS: dict[str, tuple[int, ...]] = {
    "Visa": (13, 16, 19),
    "Mastercard": (16,),
    "Amex": (15,),
    "Discover": (16, 19),
    "Diners": (14,),
    "JCB": (16, 17, 18, 19),
    "Unknown": (),
}

#: Display grouping where the scheme publishes one; ``None`` means groups of 4.
GROUPING: dict[str, tuple[int, ...] | None] = {
    "Amex": (4, 6, 5),
    "Diners": (4, 6, 4),
}

#: How many trailing digits ``mask`` is allowed to reveal.
DEFAULT_REVEAL = 4
MAX_REVEAL = 6


class CardError(ValueError):
    """A card number that cannot be read at all."""


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #
def digits(number) -> str:
    """Keep only the decimal digits of ``number``.

    Spaces and hyphens are the separators people actually type, so they are
    dropped rather than rejected. Every other character is a mistake: a card
    number containing a letter is not a card number, and silently ignoring the
    letter would turn a typo into a valid-looking number.

    >>> digits("4111-1111 1111 1111")
    '4111111111111111'
    """
    if not isinstance(number, str):
        raise CardError(f"card number must be a string, got "
                        f"{type(number).__name__}")
    cleaned = number.strip()
    for separator in (" ", "-", "."):
        cleaned = cleaned.replace(separator, "")
    if not cleaned:
        raise CardError("card number is empty")
    bad = sorted({ch for ch in cleaned if not ch.isdigit()})
    if bad:
        raise CardError(f"card number contains non-digits: {''.join(bad)!r}")
    return cleaned


def try_digits(number) -> str:
    """``digits`` for callers that would rather see ``""`` than an exception."""
    try:
        return digits(number)
    except CardError:
        return ""


# --------------------------------------------------------------------------- #
# Luhn
# --------------------------------------------------------------------------- #
def luhn_sum(number) -> int:
    """The weighted digit total; Luhn-valid numbers land on a multiple of 10.

    Every second digit from the right is doubled and, if the result exceeds
    nine, reduced by nine (equivalent to adding its two digits). The check
    digit sits in a non-doubled position, which is why appending it can always
    make the total a multiple of ten.
    """
    text = digits(number)
    total = 0
    for index, character in enumerate(reversed(text)):
        value = int(character)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total


def luhn_valid(number) -> bool:
    """True when the Luhn checksum passes. Not a claim that the card exists."""
    try:
        return luhn_sum(number) % 10 == 0
    except CardError:
        return False


def check_digit(partial) -> str:
    """The digit that makes ``partial`` + digit Luhn-valid.

    Ten candidates at most, so a loop is the clearest correct implementation.
    """
    text = digits(partial)
    for candidate in "0123456789":
        if luhn_valid(text + candidate):
            return candidate
    raise CardError(f"no check digit fits {text!r}")     # unreachable in base 10


def with_check_digit(partial) -> str:
    """``partial`` with its Luhn check digit appended."""
    text = digits(partial)
    return text + check_digit(text)


def generate(prefix, length: int) -> str:
    """A deterministic Luhn-valid number of ``length`` starting with ``prefix``.

    Unused positions are filled with zero, so the same arguments always give
    the same number. Nothing random, nothing to reproduce.
    """
    text = digits(prefix)
    if not isinstance(length, int) or isinstance(length, bool):
        raise CardError("length must be an integer")
    if length < 2:
        raise CardError(f"length must be at least 2, got {length}")
    if len(text) >= length:
        raise CardError(f"prefix {text!r} already fills {len(text)} of "
                        f"{length} digits")
    body = text + "0" * (length - 1 - len(text))
    return with_check_digit(body)


# --------------------------------------------------------------------------- #
# Brand
# --------------------------------------------------------------------------- #
def brand(number) -> str:
    """Classify by issuer identification number; ``"Unknown"`` when no rule fits.

    The rules are prefix ranges published by the schemes. A brand match says
    nothing about length or checksum -- those are separate questions, answered
    separately, because conflating them is how a 14-digit Amex gets accepted.
    """
    text = try_digits(number)
    if not text:
        return "Unknown"

    def head(size: int) -> int:
        return int(text[:size]) if len(text) >= size else -1

    first = int(text[0])
    two, three, four, six = head(2), head(3), head(4), head(6)

    if first == 4:
        return "Visa"
    if 51 <= two <= 55 or 2221 <= four <= 2720:
        return "Mastercard"
    if two in (34, 37):
        return "Amex"
    if four == 6011 or two == 65 or 644 <= three <= 649 \
            or 622126 <= six <= 622925:
        return "Discover"
    if 300 <= three <= 305 or two in (36, 38):
        return "Diners"
    if 3528 <= four <= 3589:
        return "JCB"
    return "Unknown"


def length_ok(number) -> bool:
    """Does the number match its brand's allowed lengths?"""
    text = try_digits(number)
    if not text:
        return False
    allowed = LENGTHS.get(brand(text), ())
    return len(text) in allowed


# --------------------------------------------------------------------------- #
# Formatting and masking
# --------------------------------------------------------------------------- #
def _group_sizes(text: str) -> tuple[int, ...]:
    """The display grouping for a digit string, based on brand and length."""
    sizes = GROUPING.get(brand(text))
    if sizes is not None and sum(sizes) == len(text):
        return sizes
    groups: list[int] = []
    remaining = len(text)
    while remaining > 4:
        groups.append(4)
        remaining -= 4
    groups.append(remaining)
    return tuple(groups)


def _group(text: str, sizes: tuple[int, ...]) -> str:
    parts: list[str] = []
    position = 0
    for size in sizes:
        if position >= len(text):
            break
        parts.append(text[position:position + size])
        position += size
    if position < len(text):                    # anything left over
        parts.append(text[position:])
    return " ".join(parts)


def format_number(number) -> str:
    """Space the digits the way the scheme prints them.

    >>> format_number("378282246310005")
    '3782 822463 10005'
    """
    text = digits(number)
    return _group(text, _group_sizes(text))


def mask(number, reveal: int = DEFAULT_REVEAL) -> str:
    """Replace all but the last ``reveal`` digits with ``*``.

    A number no longer than ``reveal`` is masked completely. The legacy slice
    ``number[-4:]`` returned the whole string in that case, which is how a
    short input ends up printed in full.
    """
    text = digits(number)
    if not isinstance(reveal, int) or isinstance(reveal, bool):
        raise CardError("reveal must be an integer")
    if reveal < 0:
        raise CardError(f"reveal must not be negative, got {reveal}")
    if reveal > MAX_REVEAL:
        raise CardError(f"reveal must be at most {MAX_REVEAL}, got {reveal}")
    if reveal == 0 or len(text) <= reveal:
        masked = "*" * len(text)
    else:
        masked = "*" * (len(text) - reveal) + text[-reveal:]
    return _group(masked, _group_sizes(text))


def legacy_mask(number) -> str:
    """The original program's output, kept so the bug can be demonstrated."""
    return "XXXX XXXX XXXX XXXX " + str(number)[-4:]


# --------------------------------------------------------------------------- #
# Verdict
# --------------------------------------------------------------------------- #
def check(number) -> dict:
    """Everything known about one number, as one dict.

    ``valid`` requires all three independent conditions: a recognised brand,
    a length the brand allows, and a passing Luhn checksum. Any one of them
    alone is weak, and the bundled data contains a number that satisfies only
    the checksum.
    """
    text = digits(number)
    detected = brand(text)
    checksum_ok = luhn_valid(text)
    length_ok_ = len(text) in LENGTHS.get(detected, ())
    return {
        "digits": text,
        "length": len(text),
        "brand": detected,
        "luhn": checksum_ok,
        "length_ok": length_ok_,
        "valid": detected != "Unknown" and length_ok_ and checksum_ok,
        "formatted": format_number(text),
        "masked": mask(text),
    }


def describe(number) -> str:
    """One line, safe to print: the masked number and why it did or did not pass."""
    info = check(number)
    if info["valid"]:
        return f"{info['masked']}  {info['brand']}  valid"
    reasons: list[str] = []
    if info["brand"] == "Unknown":
        reasons.append("unknown brand")
    if not info["length_ok"]:
        reasons.append(f"length {info['length']} not allowed for "
                       f"{info['brand']}")
    if not info["luhn"]:
        reasons.append("Luhn checksum failed")
    return f"{info['masked']}  {info['brand']}  invalid: " + ", ".join(reasons)


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "cards.csv"


def load_cards(path: str | Path = DATA_FILE) -> list[dict]:
    """Read ``number,brand,luhn,note`` rows and recompute every field.

    The file's own claims are kept next to the computed ones so the demo can
    assert that they agree; trusting the file would make the check circular.
    """
    path = Path(path)
    if not path.exists():
        raise CardError(f"card file not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    header = None
    records: list[dict] = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = [field.strip() for field in stripped.split(",")]
        if header is None:
            header = fields
            if header != ["number", "brand", "luhn", "note"]:
                raise CardError(f"unexpected header in {path.name}: {header}")
            continue
        if len(fields) != 4:
            raise CardError(f"{path.name} line {number}: expected 4 fields, "
                            f"got {len(fields)}")
        claimed_number, claimed_brand, claimed_luhn, note = fields
        computed = check(claimed_number.replace(" ", ""))
        records.append({
            "number": claimed_number,
            "claimed_brand": claimed_brand,
            "claimed_luhn": claimed_luhn == "yes",
            "note": note,
            **computed,
            "brand_agrees": computed["brand"] == claimed_brand,
            "luhn_agrees": computed["luhn"] == (claimed_luhn == "yes"),
        })
    if not records:
        raise CardError(f"{path.name} contains no cards")
    return records


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 70)
    print(" CARD PAYMENT - Luhn, brand, length policy, masked display")
    print("=" * 70)

    # 1. the legacy bug: short input is printed in full
    assert legacy_mask("123") == "XXXX XXXX XXXX XXXX 123"
    assert mask("123") == "***"
    print("  legacy mask leaked '123' in full; mask() returns "
          f"{mask('123')!r}")

    # 2. empty and lettered input are refused rather than half-masked
    for bad, needle in (("", "is empty"), ("4111-abcd", "non-digits"),
                        (None, "must be a string"), (4111111111111111,
                                                     "must be a string")):
        try:
            digits(bad)
        except CardError as exc:
            assert needle in str(exc), (bad, str(exc))
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    assert try_digits("nope") == ""
    assert luhn_valid("nope") is False

    # 3. separators are dropped, so spaced and dashed forms are identical
    assert digits("4111 1111 1111 1111") == "4111111111111111"
    assert digits("4111-1111-1111-1111") == "4111111111111111"
    assert mask("4111 1111 1111 1111") == mask("4111111111111111")
    print(f"  spaced, dashed and plain forms all mask to "
          f"{mask('4111-1111-1111-1111')!r}")

    # 4. Luhn: a valid number, its weighted total, and a one-digit change
    assert luhn_sum("4111111111111111") == 30
    assert luhn_valid("4111111111111111") is True
    assert luhn_sum("4111111111111112") == 31
    assert luhn_valid("4111111111111112") is False
    assert luhn_sum("79927398713") == 70      # the classic worked example
    print(f"  Luhn totals 30 vs 31 for a card and the same card with one "
          f"digit changed")

    # 5. the check digit is recoverable, and corrupting it is detectable
    prefixes = {"411111111111111": "1", "555555555555444": "4",
                "37828224631000": "5", "601111111111111": "7",
                "3056930902590": "4", "353011133330000": "0"}
    for partial, expected in prefixes.items():
        assert check_digit(partial) == expected, partial
        completed = with_check_digit(partial)
        assert luhn_valid(completed) is True
        wrong = completed[:-1] + str((int(completed[-1]) + 1) % 10)
        assert luhn_valid(wrong) is False
    print(f"  {len(prefixes)} prefixes regenerated their published check digit; "
          f"flipping it fails Luhn")

    # 6. generate() is deterministic and valid at the requested length
    generated = generate("4111", 16)
    assert generated == "4111000000000008", generated
    assert len(generated) == 16 and generated.startswith("4111")
    assert luhn_valid(generated) is True
    assert generate("4111", 16) == generate("4111", 16)
    assert generate("4111", 13) == "4111000000001"
    assert luhn_valid(generate("4111", 13)) is True
    print(f"  generate('4111', 16) -> {generated} (valid, repeatable)")

    # 7. brand detection across the six schemes
    expected_brands = {
        "4111111111111111": "Visa",
        "5555555555554444": "Mastercard",
        "2221000000000009": "Mastercard",
        "378282246310005": "Amex",
        "6011111111111117": "Discover",
        "30569309025904": "Diners",
        "3530111333300000": "JCB",
        "79927398713": "Unknown",
        "123": "Unknown",
    }
    for number, expected in expected_brands.items():
        assert brand(number) == expected, (number, brand(number))
    print(f"  {len(expected_brands)} prefixes classified, including 2221-2720 "
          f"Mastercard and unknown")

    # 8. the length policy is separate from the checksum
    assert length_ok("4111111111111111") is True
    assert length_ok("4111111111111") is True          # Visa 13
    assert length_ok("378282246310005") is True        # Amex 15
    assert length_ok("30569309025904") is True         # Diners 14
    assert length_ok("555555555555444") is False       # 15-digit Mastercard
    assert length_ok("3782822463100050") is False      # 16-digit Amex

    luhn_only = check("79927398713")
    assert luhn_only["luhn"] is True
    assert luhn_only["brand"] == "Unknown"
    assert luhn_only["length_ok"] is False
    assert luhn_only["valid"] is False
    print("  79927398713 passes Luhn yet fails brand and length, so valid "
          "is False")

    # 9. masking reveals at most four digits, at the brand's true length
    assert mask("4111111111111111") == "**** **** **** 1111"
    assert mask("378282246310005") == "**** ****** *0005"
    assert mask("30569309025904") == "**** ****** 5904"
    assert mask("123") == "***"
    # five digits: groups are four from the left, so the tail splits
    assert mask("12345") == "*234 5"
    assert mask("4111111111111111", reveal=2) == "**** **** **** **11"
    for number in ("4111111111111111", "378282246310005", "30569309025904",
                   "123"):
        shown = sum(ch.isdigit() for ch in mask(number))
        expected_shown = 4 if len(number) > 4 else 0
        assert shown == expected_shown, (number, mask(number))
    print(f"  masks {mask('4111111111111111')!r} / "
          f"{mask('378282246310005')!r} / {mask('30569309025904')!r}")

    # 10. reveal bounds are enforced, not merely documented
    for bad, needle in ((-1, "not be negative"), (7, "at most 6"),
                        ("4", "must be an integer")):
        try:
            mask("4111111111111111", reveal=bad)
        except CardError as exc:
            assert needle in str(exc), (bad, str(exc))
        else:
            raise AssertionError(f"reveal={bad!r} should have been refused")
    assert mask("4111111111111111", reveal=0) == "**** **** **** ****"
    assert mask("4111", reveal=0) == "****"

    # 11. formatting follows each scheme's published grouping
    assert format_number("378282246310005") == "3782 822463 10005"
    assert format_number("30569309025904") == "3056 930902 5904"
    assert format_number("4111111111111111") == "4111 1111 1111 1111"
    assert format_number("4111111111111") == "4111 1111 1111 1"

    # 12. check() agrees with the pieces it is built from
    info = check("4111111111111111")
    assert info["brand"] == "Visa" and info["luhn"] is True
    assert info["length_ok"] is True and info["valid"] is True
    assert info["digits"] == "4111111111111111"
    assert info["masked"] == "**** **** **** 1111"
    assert describe("4111111111111111").endswith("valid")
    assert "Luhn checksum failed" in describe("4111111111111112")
    print(f"  {describe('4111111111111112')}")

    # 13. the bundled file loads, and every claim in it agrees with the code
    cards = load_cards()
    assert len(cards) == 17, len(cards)
    assert all(card["brand_agrees"] for card in cards), \
        [card["number"] for card in cards if not card["brand_agrees"]]
    assert all(card["luhn_agrees"] for card in cards), \
        [card["number"] for card in cards if not card["luhn_agrees"]]
    valid = [card for card in cards if card["valid"]]
    assert len(valid) == 9, [card["number"] for card in valid]
    assert sorted({card["brand"] for card in valid}) == \
        ["Amex", "Diners", "Discover", "JCB", "Mastercard", "Visa"]
    assert [card["number"] for card in cards if card["brand"] == "Unknown"] == \
        ["79927398713", "123"]
    print(f"  {len(cards)} bundled rows, {len(valid)} valid, "
          f"{len(cards) - len(valid)} rejected, all claims agree")

    # 14. no masked line in the file contains a whole number
    for card in cards:
        plain = card["digits"]
        assert plain not in card["masked"]
        if len(plain) > 4:
            assert card["masked"].count("*") == len(plain) - 4

    # 15. a malformed file is reported with its line number
    with tempfile.TemporaryDirectory(prefix="card-") as folder:
        path = Path(folder) / "bad.csv"
        path.write_text("number,brand,luhn,note\n4111,x,y\n", encoding="utf-8")
        try:
            load_cards(path)
        except CardError as exc:
            assert "line 2" in str(exc), str(exc)
        else:
            raise AssertionError("a short row should have been refused")
        path.write_text("4111111111111111,Visa,yes\n", encoding="utf-8")
        try:
            load_cards(path)
        except CardError as exc:
            assert "unexpected header" in str(exc), str(exc)
        else:
            raise AssertionError("a missing header should have been refused")

        missing = Path(folder) / "nope.csv"
        try:
            load_cards(missing)
        except CardError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("a missing file should have been refused")

    print()
    print("Cross-checks OK: the legacy mask leaked short input while mask() "
          "returns '***', four malformed inputs refused, separators dropped, "
          "Luhn totals 30 vs 31 for one changed digit, 6 published check "
          "digits regenerated and then broken on purpose, a repeatable "
          "generate(), 9 prefixes classified into 6 brands plus unknown, "
          "the length policy rejecting a 15-digit Mastercard and a 16-digit "
          "Amex while accepting Visa 13, a Luhn-valid unknown-brand number "
          "reported invalid, masks revealing at most 4 digits at the true "
          "length, reveal bounds enforced, 4 published groupings, and 17 "
          "bundled rows whose brand and checksum claims all agree")
    print("Demo completed successfully.")
    return 0
