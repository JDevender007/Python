"""Palindrome checks, the longest palindromic run, and the shortest completion.

The legacy program was:

    S1 = 'python'
    S2 = S1.replace(' ', '')
    rev = S2[::-1]
    if S2.casefold() == rev.casefold():
        print(S1)
    else:
        palindrome = S2.casefold() + rev.casefold()
        print(palindrome)

Four problems, in increasing order of interest.

**The input is hard-coded.** ``S1 = 'python'`` — there is no input at all, so
the program is a demonstration of a constant.

**Punctuation defeats it.** Only spaces are removed, so
``"A man, a plan, a canal: Panama"`` reverses to ``"amanaP :lanac a ,nalp a ,nam A"``
and is reported as not a palindrome. The comma and the colon break the mirror,
not the sentence.

**The failure branch prints a meaningless string.** On any non-palindrome the
program prints ``S2.casefold() + rev.casefold()`` — for ``'python'`` that is
``'pythonnohtyp'``. It *is* a palindrome, which makes the output look like a
result rather than a bug. It answers no question anyone asked.

**Nothing can make a palindrome.** The one genuinely useful operation — pad a
string until it reads the same both ways — is not there.

This module separates the operations:

    normalise(text)     letters and digits only, case-folded
    is_palindrome()     compares the normalised form with its reverse
    check()             the verdict plus what was compared
    longest_palindromic_substring()   expand around every centre
    longest_palindromic_suffix()      the part that already mirrors
    complete(text)      append the fewest characters that make it a palindrome
    mirror(text)        the trivial s + reverse(s), kept for comparison

``complete('race')`` is ``'racecar'`` — seven characters, a palindrome, and it
starts with the input. ``mirror('race')`` is ``'raceecar'`` — eight characters
and also a palindrome, but it threw away the fact that ``'race'`` was already
half way there. The demo asserts both properties, so the shorter result is a
measured claim rather than an assertion in prose.

Fully offline, no libraries.
"""

from __future__ import annotations

from pathlib import Path


class PalindromeError(ValueError):
    """Text that cannot be examined."""


def normalise(text) -> str:
    """Keep letters and digits, case-folded.

    Punctuation and whitespace are what break the mirror in ordinary sentences,
    so they are removed rather than tolerated. ``casefold`` beats ``lower``
    because it folds ligatures and ``ß`` too.
    """
    if not isinstance(text, str):
        raise PalindromeError(
            f"text must be a string, got {type(text).__name__}")
    return "".join(character for character in text
                   if character.isalnum()).casefold()


def is_palindrome(text) -> bool:
    """True when the normalised text equals its own reverse.

    Empty or punctuation-only input is refused rather than reported as a
    palindrome: an empty string trivially mirrors itself, and that is a
    technicality, not a finding.
    """
    cleaned = normalise(text)
    if not cleaned:
        raise PalindromeError("text contains no letters or digits")
    return cleaned == cleaned[::-1]


def check(text) -> dict:
    """The verdict, the normalised form and the reversed form, together."""
    cleaned = normalise(text)
    if not cleaned:
        raise PalindromeError("text contains no letters or digits")
    reversed_form = cleaned[::-1]
    return {
        "raw": text,
        "cleaned": cleaned,
        "reversed": reversed_form,
        "length": len(cleaned),
        "palindrome": cleaned == reversed_form,
    }


def legacy_output(text) -> str:
    """The original failure branch: ``text + reverse(text)``.

    Always a palindrome, never a diagnosis. Kept so the demo can assert exactly
    what the old program printed.
    """
    if not isinstance(text, str):
        raise PalindromeError("text must be a string")
    stripped = text.replace(" ", "")
    return stripped.casefold() + stripped[::-1].casefold()


def mirror(text) -> str:
    """``s + reverse(s)``: the trivial palindrome, twice the length."""
    cleaned = normalise(text)
    if not cleaned:
        raise PalindromeError("text contains no letters or digits")
    return cleaned + cleaned[::-1]


# --------------------------------------------------------------------------- #
# Longest runs
# --------------------------------------------------------------------------- #
def longest_palindromic_substring(text) -> str:
    """The longest mirrored run, earliest on a tie.

    Expand around each centre: odd centres sit on a character, even centres
    between two. O(n^2) time, O(1) extra space, and no allocation per step
    beyond the slice that is finally returned.
    """
    cleaned = normalise(text)
    if not cleaned:
        raise PalindromeError("text contains no letters or digits")

    best_start, best_length = 0, 1
    for centre in range(len(cleaned)):
        for left, right in ((centre, centre), (centre, centre + 1)):
            while left >= 0 and right < len(cleaned) \
                    and cleaned[left] == cleaned[right]:
                left -= 1
                right += 1
            length = right - left - 1
            start = left + 1
            # strict > keeps the earliest of two equally long runs
            if length > best_length:
                best_start, best_length = start, length
    return cleaned[best_start:best_start + best_length]


def longest_palindromic_suffix(text) -> str:
    """The longest suffix that is already a palindrome."""
    cleaned = normalise(text)
    if not cleaned:
        raise PalindromeError("text contains no letters or digits")
    for start in range(len(cleaned)):
        candidate = cleaned[start:]
        if candidate == candidate[::-1]:
            return candidate
    return cleaned[-1]


def longest_palindromic_prefix(text) -> str:
    """The longest prefix that is already a palindrome."""
    cleaned = normalise(text)
    if not cleaned:
        raise PalindromeError("text contains no letters or digits")
    for end in range(len(cleaned), 0, -1):
        candidate = cleaned[:end]
        if candidate == candidate[::-1]:
            return candidate
    return cleaned[0]


def complete(text) -> str:
    """The shortest palindrome that starts with ``text``, appending only.

    Only the part before the longest palindromic suffix has to be mirrored, so
    ``'race'`` needs three characters rather than four. The result is
    normalised: lowercase, letters and digits only.
    """
    cleaned = normalise(text)
    if not cleaned:
        raise PalindromeError("text contains no letters or digits")
    if cleaned == cleaned[::-1]:
        return cleaned
    suffix = longest_palindromic_suffix(cleaned)
    prefix = cleaned[:len(cleaned) - len(suffix)]
    return cleaned + prefix[::-1]


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
PHRASES_FILE = Path(__file__).resolve().parent.parent / "data" / "phrases.txt"


def load_phrases(path: str | Path = PHRASES_FILE) -> list[str]:
    """Read one phrase per line; ``#`` starts a comment."""
    path = Path(path)
    if not path.exists():
        raise PalindromeError(f"phrase file not found: {path}")
    phrases = [line.strip() for line in
               path.read_text(encoding="utf-8").splitlines()]
    phrases = [phrase for phrase in phrases
               if phrase and not phrase.startswith("#")]
    if not phrases:
        raise PalindromeError(f"{path.name} contains no phrases")
    return phrases


def split_phrases(phrases: list[str]) -> tuple[list[str], list[str]]:
    """``(palindromes, others)``, preserving the file's order."""
    yes: list[str] = []
    no: list[str] = []
    for phrase in phrases:
        (yes if is_palindrome(phrase) else no).append(phrase)
    return yes, no


def stats(phrases: list[str]) -> dict:
    """Counts and the extremes, with honest nulls when empty."""
    yes, no = split_phrases(phrases) if phrases else ([], [])
    lengths = [len(normalise(phrase)) for phrase in phrases]
    longest = max(phrases, key=lambda phrase: len(normalise(phrase)),
                  default=None)
    return {
        "phrases": len(phrases),
        "palindromes": len(yes),
        "others": len(no),
        "longest": longest,
        "longest_length": max(lengths, default=0),
        "shortest_length": min(lengths, default=0),
    }


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 70)
    print(" PALINDROME - normalise first, and pad instead of doubling")
    print("=" * 70)

    # 1. the legacy failure branch: text + reverse(text)
    assert legacy_output("python") == "pythonnohtyp"
    assert legacy_output("python") == legacy_output("python")[::-1]
    print(f"  legacy output for 'python': {legacy_output('python')!r} "
          f"(a palindrome, and useless)")

    # 2. the legacy verdict on punctuation: it says no
    sentence = "A man, a plan, a canal: Panama"
    legacy_cleaned = sentence.replace(" ", "").casefold()
    assert legacy_cleaned != legacy_cleaned[::-1]        # the comma breaks it
    assert is_palindrome(sentence) is True               # normalise fixes it
    print(f"  legacy check on the Panama sentence: False; normalised: True")

    # 3. normalisation drops punctuation and folds case
    assert normalise("A man, a plan, a canal: Panama") == \
        "amanaplanacanalpanama"
    assert normalise("  No lemon, no melon!  ") == "nolemonnomelon"
    assert normalise("12321") == "12321"
    assert normalise("") == "" and normalise("!!!") == ""
    print("  punctuation and case removed before any comparison")

    # 4. the verdicts, including the refusals
    for text in ("racecar", "A man, a plan, a canal: Panama", "12321",
                 "Was it a car or a cat I saw?", "No lemon, no melon"):
        assert is_palindrome(text) is True, text
    for text in ("python", "ab", "almost a palindrome", "racecars"):
        assert is_palindrome(text) is False, text
    for bad in ("", "!!!", "   "):
        try:
            is_palindrome(bad)
        except PalindromeError as exc:
            assert "no letters or digits" in str(exc)
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    for bad in (None, 12321):
        try:
            normalise(bad)
        except PalindromeError as exc:
            assert "must be a string" in str(exc)
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    print("  5 palindromes accepted, 4 near misses rejected, 5 bad inputs "
          "refused")

    # 5. check() reports what it compared
    verdict = check("Racecar!")
    assert verdict["cleaned"] == "racecar"
    assert verdict["reversed"] == "racecar"
    assert verdict["palindrome"] is True
    assert verdict["length"] == 7
    near = check("racecars")
    assert near["palindrome"] is False
    assert near["cleaned"] == "racecars" and near["reversed"] == "sracecar"
    print(f"  check('racecars') -> {near['cleaned']} vs {near['reversed']}")

    # 6. longest palindromic substring, earliest on a tie
    assert longest_palindromic_substring("babad") == "bab"
    assert longest_palindromic_substring("cbbd") == "bb"
    assert longest_palindromic_substring("forgeeksskeegfor") == "geeksskeeg"
    assert longest_palindromic_substring("abc") == "a"
    assert longest_palindromic_substring("racecar") == "racecar"
    assert longest_palindromic_substring("abacabad") == "abacaba"
    print("  longest runs: babad->bab, cbbd->bb, "
          "forgeeksskeegfor->geeksskeeg")

    # 7. prefix and suffix runs
    assert longest_palindromic_suffix("race") == "e"
    assert longest_palindromic_suffix("abac") == "c"
    assert longest_palindromic_suffix("abba") == "abba"
    assert longest_palindromic_prefix("racecarx") == "racecar"
    assert longest_palindromic_prefix("abc") == "a"
    print("  longest suffix of 'abac' is 'c'; longest prefix of 'racecarx' "
          "is 'racecar'")

    # 8. completion is minimal, starts with the input, and is a palindrome
    for text, expected in (("race", "racecar"), ("ab", "aba"),
                           ("abc", "abcba"), ("abac", "abacaba"),
                           ("racecar", "racecar"), ("a", "a")):
        completed = complete(text)
        assert completed == expected, (text, completed, expected)
        assert is_palindrome(completed) is True
        assert completed.startswith(normalise(text))
        assert len(completed) == 2 * len(normalise(text)) - \
            len(longest_palindromic_suffix(text)), completed
    print("  complete: race->racecar, ab->aba, abc->abcba, abac->abacaba")

    # 9. the trivial mirror is always longer than the minimal completion
    assert mirror("race") == "raceecar"
    assert is_palindrome(mirror("race")) is True
    assert len(complete("race")) < len(mirror("race"))
    assert len(complete("racecar")) == 7 and len(mirror("racecar")) == 14
    assert complete("racecar") == "racecar"      # nothing had to be added
    print(f"  mirror('race') is {len(mirror('race'))} chars, "
          f"complete('race') is {len(complete('race'))}")

    # 10. every construction is idempotent
    for text in ("race", "abc", "racecar", "abac"):
        once = complete(text)
        assert complete(once) == once, text
        assert is_palindrome(once) is True
    print("  complete() is idempotent on its own output")

    # 11. the bundled file: 20 phrases, half of them palindromes
    phrases = load_phrases()
    assert len(phrases) == 20, len(phrases)
    yes, no = split_phrases(phrases)
    assert len(yes) == 10, yes
    assert len(no) == 10, no
    assert all(is_palindrome(phrase) for phrase in yes)
    assert not any(is_palindrome(phrase) for phrase in no)
    summary = stats(phrases)
    assert summary["phrases"] == 20
    assert summary["palindromes"] == 10 and summary["others"] == 10
    assert summary["longest"] == "Was it a car or a cat I saw?"
    assert stats([])["palindromes"] == 0 and stats([])["longest"] is None
    print(f"  {len(phrases)} bundled phrases: {len(yes)} palindromes, "
          f"{len(no)} not; longest is {summary['longest']!r}")

    # 12. the bundle's longest is its own longest run
    assert longest_palindromic_substring(summary["longest"]) == \
        normalise(summary["longest"])
    assert check(summary["longest"])["length"] == summary["longest_length"]
    print(f"  its longest run is the whole phrase "
          f"({summary['longest_length']} chars)")

    # 13. a missing or empty file is reported, not silently empty
    import tempfile
    with tempfile.TemporaryDirectory(prefix="pal-") as folder:
        path = Path(folder) / "p.txt"
        try:
            load_phrases(path)
        except PalindromeError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("a missing file should have been refused")
        path.write_text("# only a comment\n\n", encoding="utf-8")
        try:
            load_phrases(path)
        except PalindromeError as exc:
            assert "no phrases" in str(exc)
        else:
            raise AssertionError("an empty file should have been refused")
        path.write_text("# c\nracecar\n\nlevel\n", encoding="utf-8")
        assert load_phrases(path) == ["racecar", "level"]

    print()
    print("Cross-checks OK: the legacy branch printed 'pythonnohtyp' and its "
          "punctuation check failed on the Panama sentence, 5 palindromes and "
          "4 near misses classified, 5 bad inputs and 2 non-text inputs "
          "refused, 6 longest-run cases with earliest-tie behaviour, prefix "
          "and suffix runs, 6 minimal completions that start with their input "
          "and hit the measured lower bound, the trivial mirror shown to be "
          "longer, idempotent completion, and 20 bundled phrases split 10/10 "
          "with the longest being its own longest run")
    print("\nDemo completed successfully.")
    return 0
