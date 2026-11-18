"""Anagram detection done properly: normalise, sign, group, search.

An anagram is not "the same letters in a different order" as a string
comparison -- it is an equality between *multisets of letters*. Removing the
punctuation and folding the case turns

    "Snooze alarms"      and     "Alas, no more Z's"

into the same multiset, which is exactly why the city of snooze alarms and the
lament about missing Zs are anagrams. The original one-liner that compared
``S1.count(ch)`` for every character of ``S1`` only checked one direction, so it
called pairs "anagrams" when ``S1`` simply had fewer of some letter.

The canonical form here is a sorted string of the letters (a *signature*), which
makes grouping a dictionary lookup instead of an O(n^2) pairwise comparison:

    signature("listen") == "eilnst" == signature("silent")

Fully offline: bundled words in, groups out.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

MIN_WORD_LENGTH = 1


class AnagramError(ValueError):
    """Text that cannot be analysed."""


def normalize(text: str) -> str:
    """Keep letters only, case-folded. Spaces, digits and punctuation go."""
    if not isinstance(text, str):
        raise AnagramError("text must be a string")
    return "".join(ch for ch in text.casefold() if ch.isalpha())


def signature(text: str) -> str:
    """The sorted letters of the text -- equal signatures mean anagram."""
    return "".join(sorted(normalize(text)))


def is_anagram(first: str, second: str) -> bool:
    """True when both texts have the same letters in the same multiplicities.

    Two empty (or letter-free) strings are *not* anagrams: with nothing to
    compare, "equal" would be a technicality rather than a finding.
    """
    left, right = signature(first), signature(second)
    if not left or not right:
        return False
    return left == right


def letter_counts(text: str) -> dict[str, int]:
    return dict(sorted(Counter(normalize(text)).items()))


def difference(first: str, second: str) -> dict[str, int]:
    """Signed letter surplus: positive means ``first`` has more of that letter."""
    left = Counter(normalize(first))
    right = Counter(normalize(second))
    keys = sorted(set(left) | set(right))
    return {key: left.get(key, 0) - right.get(key, 0)
            for key in keys if left.get(key, 0) != right.get(key, 0)}


def group_anagrams(words: list[str]) -> dict[str, list[str]]:
    """Group words by signature, keeping only groups with two or more members."""
    if not isinstance(words, list):
        raise AnagramError("words must be a list")
    buckets: dict[str, list[str]] = {}
    for word in words:
        if not isinstance(word, str):
            raise AnagramError("each word must be a string")
        key = signature(word)
        if len(key) < MIN_WORD_LENGTH:
            continue
        buckets.setdefault(key, []).append(word.strip())
    return {key: sorted(values, key=str.casefold)
            for key, values in sorted(buckets.items())
            if len(values) > 1}


def find_anagrams(word: str, candidates: list[str]) -> list[str]:
    """Every candidate that is an anagram of ``word``, excluding itself."""
    key = signature(word)
    if not key:
        raise AnagramError(f"{word!r} contains no letters")
    hits = [candidate for candidate in candidates
            if candidate.casefold() != word.casefold()
            and signature(candidate) == key]
    return sorted(hits, key=str.casefold)


def anagram_pairs(words: list[str]) -> list[tuple[str, str]]:
    """All unordered pairs of distinct words that are anagrams, sorted."""
    cleaned = [word for word in words if isinstance(word, str)]
    buckets: dict[str, list[str]] = {}
    for word in cleaned:
        key = signature(word)
        if key:
            buckets.setdefault(key, []).append(word)
    pairs: list[tuple[str, str]] = []
    for values in buckets.values():
        ordered = sorted(set(values), key=str.casefold)
        for index, first in enumerate(ordered):
            for second in ordered[index + 1:]:
                if first.casefold() != second.casefold():
                    pairs.append((first, second))
    return sorted(pairs, key=lambda pair: (pair[0].casefold(), pair[1].casefold()))


def longest_group(groups: dict[str, list[str]]) -> list[str]:
    """The group with the most members; ties go to the alphabetically first."""
    if not groups:
        return []
    return min(groups.values(), key=lambda values: (-len(values),
                                                    values[0].casefold()))


def load_words(path: Path | str) -> list[str]:
    source = Path(path)
    if not source.exists():
        raise AnagramError(f"file not found: {source}")
    lines = source.read_text(encoding="utf-8").splitlines()
    words = [line.strip() for line in lines
             if line.strip() and not line.strip().startswith("#")]
    if not words:
        raise AnagramError(f"{source.name} contains no words")
    return words


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
WORD_FILE = Path(__file__).resolve().parent.parent / "data" / "words.txt"


def run_demo() -> int:
    print("=" * 70)
    print(" ANAGRAMS - normalise, sign, group, search")
    print("=" * 70)

    # 1. the pair from the original exercise really is an anagram
    first, second = "Snooze alarms", "Alas, no more Z's"
    assert is_anagram(first, second)
    assert signature(first) == signature(second) == "aaelmnoorssz"
    print(f"  {first!r} and {second!r} share {signature(first)}")

    # 2. the signature ignores case, spaces, apostrophes and commas
    assert normalize("  Snooze   alarms ") == "snoozealarms"
    assert normalize("no more Z's") == "nomorezs"
    assert signature("A man, a plan, a canal: Panama") == \
        signature("AmanaplanacanalPanama")
    assert signature("The Morse Code") == signature("Here come dots")

    # 3. negative control: one letter short is not an anagram
    assert not is_anagram("listen", "silentt")
    assert not is_anagram("listen", "silen")
    assert difference("listen", "silentt") == {"t": -1}
    assert difference("abc", "abd") == {"c": 1, "d": -1}   # a and b cancel

    # 4. empty input is refused rather than called equal
    assert not is_anagram("", "")
    assert not is_anagram("123", "!!!")
    try:
        find_anagrams("123", [])
    except AnagramError as exc:
        assert "contains no letters" in str(exc)
    else:
        raise AssertionError("letter-free input should be refused")

    # 5. a classic group is found and ordered
    assert find_anagrams("listen", ["silent", "tinsel", "enlist", "listens"]) \
        == ["enlist", "silent", "tinsel"]
    assert find_anagrams("Listen", ["SILENT", "listen", "banana"]) == ["SILENT"]

    # 6. the bundled word list groups as documented
    words = load_words(WORD_FILE)
    assert len(words) == 48
    groups = group_anagrams(words)
    assert len(groups) == 6, groups
    assert longest_group(groups) == ["least", "slate", "stale", "steal", "tales"]
    assert groups["eilnst"] == ["enlist", "listen", "silent", "tinsel"]
    print(f"  {len(words)} words -> {len(groups)} groups; biggest "
          f"{len(longest_group(groups))} members")

    # 7. every group really shares its signature, and no word appears twice
    seen: list[str] = []
    for key, members in groups.items():
        assert all(signature(word) == key for word in members), key
        seen.extend(members)
    assert len(seen) == len(set(word.casefold() for word in seen))

    # 8. pairs are unordered, distinct and sorted
    pairs = anagram_pairs(words)
    assert len(pairs) == 34, len(pairs)
    assert pairs[0] == ("ager", "gear"), pairs[0]
    assert all(first_ != second_ for first_, second_ in pairs)

    # 9. grouping is stable and independent of the input order
    shuffled = list(reversed(words))
    assert group_anagrams(shuffled) == groups

    # 10. one-word and empty inputs are handled without inventing groups
    assert group_anagrams(["banana"]) == {}
    assert group_anagrams([]) == {}
    assert anagram_pairs([]) == []

    print()
    print("Cross-checks OK: the original snooze/alarms pair signed as "
          "aaelmnoorssz, 3 normalisation cases, 3 negative controls with a "
          "signed difference, letter-free input refused, listen found 3 of 4 "
          "candidates, 48 words into 6 verified groups with a 5-member "
          "largest, 34 unordered pairs, order-independent grouping, empty "
          "inputs safe")
    print("Demo completed successfully.")
    return 0
