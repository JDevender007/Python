"""A listing is sorted by value, compared without case, and confined to its root.

The legacy explorer did three things in three innocent-looking lines:

    names = [p.name for p in Path(path).iterdir()]
    names.sort()
    return [Path(path) / name for name in names]

**1. `names.sort()` compares text, so `file10` comes before `file2`.** Every digit is a
character, and `"1" < "2"`, so a folder with ten files is listed 1, 10, 2, 20. A person
reads those numbers as numbers, and a listing that does not is wrong in a way that gets
worse as the folder grows.

**2. A bare `sort()` compares by code point, so `Zebra.txt` precedes `apple.txt`.** Every
capital letter sorts before every lower-case letter, so the folder looks shuffled to
anyone reading it. Case-insensitive comparison is the fix, and `str.lower()` is *not* the
same comparison as `str.casefold()`: casefold maps the German sharp s to `ss`, so the two
spellings of the same word compare equal instead of one sorting after the other.

**3. `Path(root) / name` is not confinement.** It honours `..`, so
`data/site` + `../secret.txt` is `data/secret.txt`; and an absolute name replaces the root
entirely. A guard written as `str(path).startswith(str(root))` then says that
`data/site-other/x.txt` is *inside* `data/site`, because a string prefix is not a directory
prefix.

**4. A byte count is not a float.** `f"{size / 1024:.1f} KB"` prints a 1280-byte file as
`1.2 KB` (banker's rounding on the double) where half-up says `1.3 KB`, and it prints a
one-byte file as `1.0 B`, a tenth of a byte that does not exist.

So this module keeps a natural key (digit runs compared as numbers), a case-blind sort whose
ties are broken by the raw name so the order is total, a `confine()` that resolves the join
lexically and refuses anything that is not under the root, and a `format_size()` built from
integer tenths. The legacy paths are kept beside them, executable, so every claim above is
reproduced with a number.

The demonstration is offline: one bundled listing of thirteen entries.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LISTING_FILE = DATA_DIR / "listing.txt"

#: The legacy listing, transcribed -- and executable.
LEGACY_LISTING = ('names = [entry.name for entry in Path(path).iterdir()]\n'
                  'names.sort()\n'
                  'return [Path(path) / name for name in names]')

#: The legacy guard, transcribed: a string prefix is not a directory prefix.
LEGACY_CONTAINS = "return str(target).startswith(str(root))"

#: The units a size is shown in, in increasing order.
UNITS = ("B", "KB", "MB", "GB", "TB")

#: The two kinds of entry a listing holds.
KINDS = ("file", "dir")

#: The separator a bundle line uses.
FIELD = "|"

#: The name a hidden entry starts with.
HIDDEN_PREFIX = "."


class ExplorerError(Exception):
    """A name, a listing, a root or a size that cannot be honoured, and why."""


# --------------------------------------------------------------------------- #
# Integer arithmetic
# --------------------------------------------------------------------------- #
def divide_half_up(numerator: int, denominator: int) -> int:
    """`numerator / denominator` rounded half-up, from integers only."""
    for value, name in ((numerator, "a numerator"), (denominator, "a denominator")):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ExplorerError(f"{name} is a whole number, got {value!r}")
    if denominator <= 0:
        raise ExplorerError(f"a denominator is positive, got {denominator}")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return sign * quotient


def _whole(value, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ExplorerError(f"{name} is a whole number, got {value!r}")
    return value


def _text(value, name: str) -> str:
    if not isinstance(value, str):
        raise ExplorerError(f"{name} is text, got {type(value).__name__}")
    if not value.strip():
        raise ExplorerError(f"{name} is text, and not blank")
    return value


# --------------------------------------------------------------------------- #
# A size
# --------------------------------------------------------------------------- #
def format_size(size: int) -> str:
    """`1280 -> "1.3 KB"`, `1 -> "1 B"` -- tenths rounded half-up, from integers."""
    _whole(size, "a size")
    if size < 0:
        raise ExplorerError(f"a size is not negative, got {size}")
    if size < 1024:
        return f"{size} B"
    unit = 1024
    index = 1
    while index + 1 < len(UNITS) and size >= unit * 1024:
        unit *= 1024
        index += 1
    tenths = divide_half_up(size * 10, unit)
    whole, part = divmod(tenths, 10)
    if part:
        return f"{whole}.{part} {UNITS[index]}"
    return f"{whole} {UNITS[index]}"


def legacy_format_size(size: int) -> str:
    """`f"{value:.1f}"` on a float that is divided once per unit -- the old display."""
    value = float(size)
    for unit in UNITS:
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


# --------------------------------------------------------------------------- #
# Names
# --------------------------------------------------------------------------- #
DIGITS = re.compile(r"(\d+)")


def natural_key(name: str) -> tuple:
    """A sort key whose digit runs compare as numbers: `file2` before `file10`.

    The key is a tuple of `(0, number)` and `(1, text)` parts, taken from the
    case-folded name, so `file2` and `FILE2` compare equal here -- the raw name is
    the caller's tiebreak, which is what makes the order total.
    """
    _text(name, "a name")
    folded = name.casefold()
    parts = []
    for piece in DIGITS.split(folded):
        if not piece:
            continue
        if piece.isdigit():
            parts.append((0, int(piece)))
        else:
            parts.append((1, piece))
    return tuple(parts)


def sort_names(names) -> list[str]:
    """Case-blind, natural order, with the raw name breaking every tie."""
    held = list(names)
    for name in held:
        _text(name, "a name")
    return sorted(held, key=lambda name: (natural_key(name), name))


def legacy_sort_names(names) -> list[str]:
    """`names.sort()` -- code points, so digits are characters and caps come first."""
    held = list(names)
    return sorted(held)


def is_hidden(name: str) -> bool:
    """A leading dot: the Unix convention, which is what a portable listing can know."""
    _text(name, "a name")
    return name.startswith(HIDDEN_PREFIX)


# --------------------------------------------------------------------------- #
# An entry
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Entry:
    """One line of a listing: a name, whether it is a file or a directory, its size."""

    name: str
    kind: str
    size: int

    def __post_init__(self) -> None:
        _text(self.name, "a name")
        if "/" in self.name or "\\" in self.name:
            raise ExplorerError(f"a name holds no separator, got {self.name!r}")
        if self.kind not in KINDS:
            raise ExplorerError(f"a kind is {KINDS}, got {self.kind!r}")
        _whole(self.size, "a size")
        if self.size < 0:
            raise ExplorerError(f"a size is not negative, got {self.size}")

    def is_dir(self) -> bool:
        return self.kind == "dir"

    def hidden(self) -> bool:
        return is_hidden(self.name)

    def shown_size(self) -> str:
        return format_size(self.size)

    def legacy_size(self) -> str:
        return legacy_format_size(self.size)

    def line(self) -> str:
        mark = "d" if self.is_dir() else "-"
        return f"{mark} {self.name:<16} {self.shown_size():>8}"


def sort_entries(entries) -> tuple[Entry, ...]:
    """Directories first, then natural order -- a case-blind comparison, no ties."""
    held = list(entries)
    for entry in held:
        if not isinstance(entry, Entry):
            raise ExplorerError(f"a listing holds entries, got {entry!r}")
    return tuple(sorted(held, key=lambda entry: (not entry.is_dir(),
                                                 natural_key(entry.name),
                                                 entry.name)))


def legacy_sort_entries(entries) -> tuple[Entry, ...]:
    """The old key: `(is_file, name.lower())` -- which is not a natural order."""
    held = list(entries)
    return tuple(sorted(held, key=lambda entry: (entry.kind == "file",
                                                 entry.name.lower())))


def visible(entries) -> tuple[Entry, ...]:
    """The listing as shown by default: hidden names are left out."""
    return tuple(entry for entry in sort_entries(entries) if not entry.hidden())


def hidden(entries) -> tuple[Entry, ...]:
    """Only the hidden names, in the same order."""
    return tuple(entry for entry in sort_entries(entries) if entry.hidden())


# --------------------------------------------------------------------------- #
# Reading the bundle
# --------------------------------------------------------------------------- #
def parse_listing(text: str) -> tuple[Entry, ...]:
    """Read `name | kind | bytes` per line; `;` introduces a comment."""
    entries: list[Entry] = []
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        body = line.split(";", 1)[0].strip()
        if not body:
            continue
        fields = [field.strip() for field in body.split(FIELD)]
        if len(fields) != 3:
            raise ExplorerError(f"line {number}: three fields are needed -- a "
                                f"name, a kind and a size -- got {len(fields)}")
        name, kind, size_text = fields
        try:
            size = int(size_text)
        except ValueError:
            raise ExplorerError(f"line {number}: {size_text!r} is not a whole "
                                f"number of bytes") from None
        try:
            entries.append(Entry(name, kind, size))
        except ExplorerError as error:
            raise ExplorerError(f"line {number}: {error}") from None
    if not entries:
        raise ExplorerError("a listing needs at least one entry")
    names = [entry.name for entry in entries]
    if len(names) != len(set(names)):
        raise ExplorerError("a listing's names are distinct, so one can be named")
    return tuple(entries)


def read_listing(path=None) -> tuple[Entry, ...]:
    target = Path(LISTING_FILE if path is None else path)
    if not target.is_file():
        raise ExplorerError(f"file not found: {target}")
    return parse_listing(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Confinement
# --------------------------------------------------------------------------- #
def _base_text(root: str) -> str:
    return os.path.normpath(_text(root, "a root")).replace(os.sep, "/")


def confine(root: str, name: str) -> str:
    """`root` joined with `name`, normalised, or a refusal when it is not inside.

    The check is on the *normalised* join, so `docs/../notes.txt` is allowed (it
    lands on `notes.txt`) and `../secret.txt` is not. The rule is a directory
    prefix -- `base + "/"` -- not a string prefix, so `data/site-other` is outside
    `data/site` no matter how the two strings compare.
    """
    base = _base_text(root)
    _text(name, "a name")
    if "\x00" in name:
        raise ExplorerError("a name holds no null byte")
    if Path(name).drive or name[0] in ("/", "\\"):
        raise ExplorerError(f"{name!r} is absolute: a listing name is relative "
                            f"to the root")
    joined = os.path.normpath(os.path.join(base, name)).replace(os.sep, "/")
    if joined != base and not joined.startswith(base + "/"):
        raise ExplorerError(f"{name!r} leaves {base!r}")
    return joined


def is_confined(root: str, name: str) -> bool:
    """`True` when `confine` would accept the name."""
    try:
        confine(root, name)
    except ExplorerError:
        return False
    return True


def legacy_join(root: str, name: str):
    """`Path(root) / name` -- `..` is honoured and an absolute name replaces the root."""
    return Path(root) / name


def legacy_normalised(root: str, name: str) -> str:
    """The legacy join, normalised, as text -- where it actually points."""
    return os.path.normpath(str(legacy_join(root, name))).replace(os.sep, "/")


def legacy_contains(root: str, target: str) -> bool:
    """`str(target).startswith(str(root))` -- the guard that says a sibling is inside."""
    return str(target).startswith(str(root))


def contains(root: str, target: str) -> bool:
    """`target` is `root` or below it, compared as path parts."""
    base = _base_text(root)
    other = os.path.normpath(_text(target, "a target")).replace(os.sep, "/")
    return other == base or other.startswith(base + "/")


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(measured: dict, entries) -> list[tuple[str, bool]]:
    """Eleven checks, re-derived from what the demo measured or freshly built."""
    def at(name: str):
        if name not in measured:
            raise ExplorerError(f"no measurement named {name!r}")
        return measured[name]

    def digits_compare_as_numbers() -> bool:
        return at("natural") == ["file1.txt", "file2.txt", "file10.txt",
                                 "file20.txt"]

    def the_legacy_sort_compares_digits_as_characters() -> bool:
        return at("legacy") == ["file1.txt", "file10.txt", "file2.txt",
                                "file20.txt"] and at("legacy") != at("natural")

    def a_listing_ignores_case() -> bool:
        return at("folded") == ["apple.txt", "Banana.txt", "Zebra.txt"] and \
            at("folded_legacy") == ["Banana.txt", "Zebra.txt", "apple.txt"]

    def a_casefold_tie_is_broken_by_the_raw_name() -> bool:
        tie = at("tie")
        return tie == ["STRASSE", "Stra\u00dfe"] and \
            [name.casefold() for name in tie] == ["strasse", "strasse"]

    def a_sort_never_loses_or_invents_a_name() -> bool:
        return sorted(at("bundle_sorted")) == sorted(at("bundle_names")) and \
            len(at("bundle_sorted")) == len(at("bundle_names"))

    def a_hidden_name_is_left_out_until_it_is_asked_for() -> bool:
        shown = at("visible")
        kept = at("hidden")
        return all(not is_hidden(name) for name in shown) and \
            all(is_hidden(name) for name in kept) and \
            sorted(shown + kept) == sorted(at("bundle_names"))

    def dot_dot_cannot_leave_the_root() -> bool:
        return at("escape_refused") is True and \
            at("legacy_escape") == "data/secret.txt"

    def an_absolute_name_is_refused() -> bool:
        return at("absolute_refused") is True and \
            at("absolute_legacy_kept") is True

    def a_sibling_with_the_same_prefix_is_outside() -> bool:
        return at("prefix_trap") == "outside" and \
            at("legacy_prefix_trap") == "inside"

    def dot_dot_that_stays_inside_is_allowed() -> bool:
        return at("inside_dotdot") == "data/site/notes.txt"

    def a_size_is_tenths_rounded_half_up_and_bytes_have_none() -> bool:
        return at("size_1280") == "1.3 KB" and \
            at("legacy_size_1280") == "1.2 KB" and \
            at("size_1") == "1 B" and at("legacy_size_1") == "1.0 B"

    checks = [
        ("digits compare as numbers", digits_compare_as_numbers),
        ("the legacy sort compares digits as characters",
         the_legacy_sort_compares_digits_as_characters),
        ("a listing ignores case", a_listing_ignores_case),
        ("a casefold tie is broken by the raw name",
         a_casefold_tie_is_broken_by_the_raw_name),
        ("a sort never loses or invents a name",
         a_sort_never_loses_or_invents_a_name),
        ("a hidden name is left out until it is asked for",
         a_hidden_name_is_left_out_until_it_is_asked_for),
        ("dot dot cannot leave the root", dot_dot_cannot_leave_the_root),
        ("an absolute name is refused", an_absolute_name_is_refused),
        ("a sibling with the same prefix is outside",
         a_sibling_with_the_same_prefix_is_outside),
        ("dot dot that stays inside is allowed",
         dot_dot_that_stays_inside_is_allowed),
        ("a size is tenths rounded half up and bytes have none",
         a_size_is_tenths_rounded_half_up_and_bytes_have_none),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def measure(entries) -> dict:
    """Every number the audit is allowed to read, measured once."""
    measured: dict = {}
    numbers = ["file1.txt", "file2.txt", "file10.txt", "file20.txt"]
    measured["natural"] = sort_names(numbers)
    measured["legacy"] = legacy_sort_names(numbers)

    words = ["Zebra.txt", "apple.txt", "Banana.txt"]
    measured["folded"] = sort_names(words)
    measured["folded_legacy"] = legacy_sort_names(words)

    measured["tie"] = sort_names(["Stra\u00dfe", "STRASSE"])

    names = [entry.name for entry in sort_entries(entries)]
    measured["bundle_names"] = names
    measured["bundle_sorted"] = names
    measured["visible"] = [entry.name for entry in visible(entries)]
    measured["hidden"] = [entry.name for entry in hidden(entries)]

    measured["escape_refused"] = not is_confined("data/site", "../secret.txt")
    measured["legacy_escape"] = legacy_normalised("data/site", "../secret.txt")
    measured["absolute_refused"] = not is_confined("data/site", "/etc/passwd")
    measured["absolute_legacy_kept"] = str(legacy_join("data/site",
                                                       "/etc/passwd")) != ""
    measured["prefix_trap"] = ("inside" if contains("data/site",
                                                    "data/site-other/x.txt")
                               else "outside")
    measured["legacy_prefix_trap"] = ("inside" if legacy_contains(
        "data/site", "data/site-other/x.txt") else "outside")
    measured["inside_dotdot"] = confine("data/site", "docs/../notes.txt")

    measured["size_1280"] = format_size(1280)
    measured["legacy_size_1280"] = legacy_format_size(1280)
    measured["size_1"] = format_size(1)
    measured["legacy_size_1"] = legacy_format_size(1)
    return measured


def run_demo() -> int:
    entries = read_listing()
    measured = measure(entries)

    print("=" * 78)
    print(" FILE LAB - sort() is not a listing order, and a join is not confinement")
    print("=" * 78)

    print("\n  the legacy listing, transcribed:")
    for line in LEGACY_LISTING.split("\n"):
        print(f"    {line}")

    shown = visible(entries)
    old = legacy_sort_entries(entries)
    old = tuple(entry for entry in old if not entry.hidden())
    print(f"\n  {len(entries)} entries, {len(shown)} shown, "
          f"{len(measured['hidden'])} hidden:")
    print(f"    {'here':<18} {'the legacy sort':<18} size")
    for here, there in zip(shown, old):
        mark = "  <-" if here.name != there.name else ""
        print(f"    {here.name:<18} {there.name:<18} "
              f"{here.shown_size():>8}{mark}")
    disagreements = sum(1 for left, right in zip(shown, old)
                        if left.name != right.name)
    print(f"\n    {disagreements} of {len(shown)} positions disagree")

    print("\n  a digit is a character to sort(), and a number to a reader:")
    print(f"    sort():      {', '.join(measured['legacy'])}")
    print(f"    by value:    {', '.join(measured['natural'])}")

    print("\n  and a capital letter is less than every lower-case one:")
    print(f"    sort():      {', '.join(measured['folded_legacy'])}")
    print(f"    casefold():  {', '.join(measured['folded'])}")
    print(f"    'STRASSE' and its sharp-s spelling both casefold to 'strasse',")
    print(f"    so the raw name decides, and the order stays total")

    print("\n  a hidden name is a convention, not a fact:")
    print(f"    shown:   {', '.join(measured['visible'])}")
    print(f"    hidden:  {', '.join(measured['hidden'])}")

    print("\n  joining is not confining:")
    print(f"    data/site + '../secret.txt' -> refused: "
          f"{measured['escape_refused']}")
    print(f"    the legacy join lands on:    {measured['legacy_escape']}")
    print(f"    data/site + '/etc/passwd'   -> refused: "
          f"{measured['absolute_refused']}")
    print(f"    data/site-other/x.txt is {measured['prefix_trap']} data/site "
          f"here, and {measured['legacy_prefix_trap']} to startswith()")
    print(f"    data/site + 'docs/../notes.txt' -> "
          f"{measured['inside_dotdot']}")
    print(f"    the guard, transcribed: {LEGACY_CONTAINS}")

    print("\n  a size is tenths, and bytes have no tenth:")
    print(f"    1280 bytes -> {measured['size_1280']} here, "
          f"{measured['legacy_size_1280']} from a float")
    print(f"    1 byte     -> {measured['size_1']} here, "
          f"{measured['legacy_size_1']} from a float")

    checks = audit(measured, entries)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(entries)} entries, {disagreements} of {len(shown)} positions "
          f"differ under the legacy sort, file2 and file10 swap places, "
          f"'Zebra.txt' sorts after 'apple.txt' only once case is folded, "
          f"'../secret.txt' is refused here and lands on "
          f"{measured['legacy_escape']} under the legacy join, "
          f"data/site-other is {measured['prefix_trap']} to a path comparison "
          f"and {measured['legacy_prefix_trap']} to a string one, 1280 bytes is "
          f"{measured['size_1280']} not {measured['legacy_size_1280']}, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
