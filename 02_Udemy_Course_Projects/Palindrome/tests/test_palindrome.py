"""Tests for Palindrome: normalisation, verdicts, runs, completion and CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from palindrome import (                                  # noqa: E402
    PHRASES_FILE,
    PalindromeError,
    check,
    complete,
    is_palindrome,
    legacy_output,
    load_phrases,
    longest_palindromic_prefix,
    longest_palindromic_substring,
    longest_palindromic_suffix,
    mirror,
    normalise,
    run_demo,
    split_phrases,
    stats,
)

PANAMA = "A man, a plan, a canal: Panama"


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #
def test_normalise_drops_spaces_and_punctuation():
    assert normalise(PANAMA) == "amanaplanacanalpanama"


def test_normalise_folds_case():
    assert normalise("RaceCar") == "racecar"


def test_normalise_keeps_digits():
    assert normalise("12321") == "12321"


def test_normalise_keeps_letters_and_digits_mixed():
    assert normalise("A1b2 B1a") == "a1b2b1a"


def test_normalise_of_blank_is_empty():
    assert normalise("") == ""


def test_normalise_of_punctuation_only_is_empty():
    assert normalise("!!! ... ,,") == ""


def test_normalise_uses_casefold_not_lower():
    # casefold turns the German sharp s into 'ss'; lower does not
    assert normalise("Stra\u00dfe") == "strasse"
    assert "Stra\u00dfe".lower() == "stra\u00dfe"


@pytest.mark.parametrize("bad", [None, 12321, ["a"], 3.5])
def test_normalise_refuses_non_text(bad):
    with pytest.raises(PalindromeError, match="must be a string"):
        normalise(bad)


# --------------------------------------------------------------------------- #
# The legacy program
# --------------------------------------------------------------------------- #
def test_legacy_output_of_python():
    assert legacy_output("python") == "pythonnohtyp"


def test_legacy_output_is_always_a_palindrome():
    for text in ("python", "abc", "racecars", "was it a car"):
        assert legacy_output(text) == legacy_output(text)[::-1]


def test_legacy_output_removes_spaces_before_doubling():
    # "a b" -> "ab" -> "abba", four characters, not five
    assert legacy_output("a b") == "abba"
    assert len(legacy_output("a b")) == 4


def test_legacy_output_of_a_palindrome_doubles_it_anyway():
    # the old program only used the palindrome branch on success, but the
    # failure branch itself has no idea what it was given
    assert legacy_output("racecar") == "racecarracecar"


def test_legacy_check_fails_on_the_panama_sentence():
    stripped = PANAMA.replace(" ", "").casefold()
    assert stripped != stripped[::-1]
    assert is_palindrome(PANAMA) is True


def test_legacy_check_would_accept_a_plain_palindrome():
    stripped = "racecar".replace(" ", "").casefold()
    assert stripped == stripped[::-1]


def test_legacy_output_refuses_non_text():
    with pytest.raises(PalindromeError, match="must be a string"):
        legacy_output(7)


# --------------------------------------------------------------------------- #
# Verdicts
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", [
    "racecar",
    "Taco cat",
    PANAMA,
    "12321",
    "Was it a car or a cat I saw?",
    "a",
    "11",
])
def test_is_palindrome_true(text):
    assert is_palindrome(text) is True


@pytest.mark.parametrize("text", [
    "python",
    "ab",
    "racecars",
    "almost a palindrome",
    "Taco cats",
])
def test_is_palindrome_false(text):
    assert is_palindrome(text) is False


@pytest.mark.parametrize("bad", ["", "   ", "!!!", "..."])
def test_is_palindrome_refuses_empty_input(bad):
    with pytest.raises(PalindromeError, match="no letters or digits"):
        is_palindrome(bad)


def test_is_palindrome_refuses_non_text():
    with pytest.raises(PalindromeError, match="must be a string"):
        is_palindrome(None)


def test_check_reports_the_cleaned_form():
    assert check("Racecar!")["cleaned"] == "racecar"


def test_check_reports_the_reverse():
    assert check("abc")["reversed"] == "cba"


def test_check_counts_the_cleaned_length():
    assert check(PANAMA)["length"] == 21


def test_check_keeps_the_raw_input():
    assert check("  Racecar!  ")["raw"] == "  Racecar!  "


def test_check_flags_a_palindrome():
    assert check("racecar")["palindrome"] is True


def test_check_flags_a_non_palindrome():
    verdict = check("racecars")
    assert verdict["palindrome"] is False
    assert verdict["cleaned"] == "racecars"
    assert verdict["reversed"] == "sracecar"


def test_check_refuses_empty_input():
    with pytest.raises(PalindromeError, match="no letters or digits"):
        check("!!")


def test_check_does_not_mutate_its_input():
    text = "Racecar!"
    check(text)
    assert text == "Racecar!"


# --------------------------------------------------------------------------- #
# Mirror
# --------------------------------------------------------------------------- #
def test_mirror_of_race_is_eight_characters():
    assert mirror("race") == "raceecar"


def test_mirror_is_a_palindrome():
    assert is_palindrome(mirror("race")) is True


def test_mirror_doubles_the_length():
    assert len(mirror("abcde")) == 10


def test_mirror_normalises_first():
    assert mirror("Race Car") == "racecarracecar"


def test_mirror_of_a_palindrome_is_a_double():
    assert mirror("racecar") == "racecar" + "racecar"


def test_mirror_refuses_empty_input():
    with pytest.raises(PalindromeError, match="no letters or digits"):
        mirror("  ")


# --------------------------------------------------------------------------- #
# Longest runs
# --------------------------------------------------------------------------- #
def test_longest_run_of_babad_is_bab():
    # 'bab' and 'aba' are both length 3; the earliest wins
    assert longest_palindromic_substring("babad") == "bab"


def test_longest_run_of_cbbd_is_bb():
    assert longest_palindromic_substring("cbbd") == "bb"


def test_longest_run_of_a_long_classic():
    assert longest_palindromic_substring("forgeeksskeegfor") == "geeksskeeg"


def test_longest_run_of_a_palindrome_is_the_whole_thing():
    assert longest_palindromic_substring("racecar") == "racecar"


def test_longest_run_of_a_single_character():
    assert longest_palindromic_substring("x") == "x"


def test_longest_run_of_no_palindrome_beyond_one_character():
    assert longest_palindromic_substring("abc") == "a"


def test_longest_run_ignores_case_and_punctuation():
    assert longest_palindromic_substring("A man, a plan, a canal: Panama") == \
        "amanaplanacanalpanama"


def test_longest_run_earliest_tie_is_stable():
    # 'aa' and 'aa' both length 2, but also 'aba'-style ties at length 3
    assert longest_palindromic_substring("abacabad") == "abacaba"


def test_longest_run_refuses_empty_input():
    with pytest.raises(PalindromeError, match="no letters or digits"):
        longest_palindromic_substring("!!")


def test_longest_suffix_of_abac_is_c():
    assert longest_palindromic_suffix("abac") == "c"


def test_longest_suffix_of_race_is_e():
    assert longest_palindromic_suffix("race") == "e"


def test_longest_suffix_of_a_palindrome_is_itself():
    assert longest_palindromic_suffix("abba") == "abba"


def test_longest_suffix_of_a_single_character():
    assert longest_palindromic_suffix("q") == "q"


def test_longest_suffix_picks_the_longest_not_the_first():
    # 'abba' at the end beats 'bb' inside it
    assert longest_palindromic_suffix("xabba") == "abba"


def test_longest_prefix_of_racecarx_is_racecar():
    assert longest_palindromic_prefix("racecarx") == "racecar"


def test_longest_prefix_of_abc_is_a():
    assert longest_palindromic_prefix("abc") == "a"


def test_longest_prefix_of_a_palindrome_is_itself():
    assert longest_palindromic_prefix("abba") == "abba"


def test_prefix_and_suffix_meet_on_a_palindrome():
    text = "racecar"
    assert longest_palindromic_prefix(text) == \
        longest_palindromic_suffix(text) == text


def test_longest_suffix_refuses_empty_input():
    with pytest.raises(PalindromeError, match="no letters or digits"):
        longest_palindromic_suffix("")


def test_longest_prefix_refuses_empty_input():
    with pytest.raises(PalindromeError, match="no letters or digits"):
        longest_palindromic_prefix("   ")


# --------------------------------------------------------------------------- #
# Completion
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text, expected", [
    ("race", "racecar"),
    ("ab", "aba"),
    ("abc", "abcba"),
    ("abac", "abacaba"),
    ("a", "a"),
    ("racecar", "racecar"),
    ("aba", "aba"),
    ("xyza", "xyzazyx"),
])
def test_complete(text, expected):
    assert complete(text) == expected


@pytest.mark.parametrize("text", ["race", "abc", "abac", "xyza", "ab"])
def test_completion_is_a_palindrome(text):
    assert is_palindrome(complete(text)) is True


@pytest.mark.parametrize("text", ["race", "abc", "abac", "xyza"])
def test_completion_starts_with_the_input(text):
    assert complete(text).startswith(normalise(text))


@pytest.mark.parametrize("text", ["race", "abc", "abac", "xyza"])
def test_completion_adds_the_measured_minimum(text):
    cleaned = normalise(text)
    suffix = longest_palindromic_suffix(cleaned)
    assert len(complete(text)) == 2 * len(cleaned) - len(suffix)


@pytest.mark.parametrize("text", ["race", "abc", "abac", "racecar"])
def test_completion_is_never_longer_than_the_mirror(text):
    assert len(complete(text)) <= len(mirror(text))


def test_completion_of_a_palindrome_adds_nothing():
    assert complete("racecar") == "racecar"
    assert len(complete("level")) == 5


def test_completion_is_idempotent():
    for text in ("race", "abc", "abac", "xyza"):
        once = complete(text)
        assert complete(once) == once


def test_completion_strictly_beats_the_mirror_for_race():
    assert len(complete("race")) == 7 < len(mirror("race")) == 8


def test_completion_normalises_the_output():
    assert complete("Race Car!") == "racecar"


def test_completion_refuses_empty_input():
    with pytest.raises(PalindromeError, match="no letters or digits"):
        complete(" ,, ")


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
def test_bundled_file_has_twenty_phrases():
    assert len(load_phrases()) == 20


def test_bundled_file_is_the_default_path():
    assert PHRASES_FILE.name == "phrases.txt"
    assert PHRASES_FILE.parent.name == "data"


def test_bundled_file_splits_ten_and_ten():
    yes, no = split_phrases(load_phrases())
    assert len(yes) == 10 and len(no) == 10


def test_every_bundled_palindrome_really_is_one():
    yes, _ = split_phrases(load_phrases())
    assert all(is_palindrome(phrase) for phrase in yes)


def test_no_bundled_other_is_a_palindrome():
    _, no = split_phrases(load_phrases())
    assert not any(is_palindrome(phrase) for phrase in no)


def test_bundled_longest_is_the_car_sentence():
    assert stats(load_phrases())["longest"] == \
        "Was it a car or a cat I saw?"


def test_bundled_longest_is_unique():
    phrases = load_phrases()
    lengths = [len(normalise(phrase)) for phrase in phrases]
    assert lengths.count(max(lengths)) == 1


def test_bundled_longest_normalises_to_nineteen_characters():
    assert stats(load_phrases())["longest_length"] == 19


def test_bundled_lines_with_comments_are_skipped(tmp_path):
    path = tmp_path / "fixture_phrases.txt"
    path.write_text("# comment\n\nracecar\n", encoding="utf-8")
    assert load_phrases(path) == ["racecar"]


def test_load_refuses_a_missing_file(tmp_path):
    with pytest.raises(PalindromeError, match="not found"):
        load_phrases(tmp_path / "nope.txt")


def test_load_refuses_a_file_of_only_comments(tmp_path):
    path = tmp_path / "p.txt"
    path.write_text("# nothing\n\n", encoding="utf-8")
    with pytest.raises(PalindromeError, match="no phrases"):
        load_phrases(path)


def test_split_preserves_order():
    yes, no = split_phrases(["bc", "aba", "cd", "racecar"])
    assert yes == ["aba", "racecar"]
    assert no == ["bc", "cd"]


def test_split_of_nothing_is_two_empty_lists():
    assert split_phrases([]) == ([], [])


def test_stats_counts_everything():
    summary = stats(["abba", "abc", "a"])
    assert summary["phrases"] == 3
    assert summary["palindromes"] == 2
    assert summary["others"] == 1


def test_stats_longest_uses_the_normalised_length():
    summary = stats(["A man, a plan, a canal: Panama", "abba"])
    assert summary["longest"] == "A man, a plan, a canal: Panama"
    assert summary["longest_length"] == 21
    assert summary["shortest_length"] == 4


def test_stats_of_nothing_uses_honest_nulls():
    assert stats([]) == {"phrases": 0, "palindromes": 0, "others": 0,
                         "longest": None, "longest_length": 0,
                         "shortest_length": 0}


# --------------------------------------------------------------------------- #
# Demo and CLI
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_mentions_the_legacy_string(capsys):
    run_demo()
    assert "pythonnohtyp" in capsys.readouterr().out


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_the_bundled_phrases(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "10 palindrome(s), 10 other(s)" in out
    assert "Racecar" in out


def test_cli_stats_mode(capsys):
    assert cli.main(["--stats"]) == 0
    out = capsys.readouterr().out
    assert "Was it a car or a cat I saw?" in out
    assert "19 chars" in out


def test_cli_check_a_palindrome(capsys):
    assert cli.main(["--check", "Taco cat"]) == 0
    out = capsys.readouterr().out
    assert "tacocat" in out and "palindrome" in out


def test_cli_check_a_non_palindrome(capsys):
    assert cli.main(["--check", "python"]) == 0
    out = capsys.readouterr().out
    assert "not a palindrome" in out


def test_cli_check_refuses_blank_and_exits_two(capsys):
    assert cli.main(["--check", "!!!"]) == 2
    assert "no letters or digits" in capsys.readouterr().err


def test_cli_complete(capsys):
    assert cli.main(["--complete", "race"]) == 0
    out = capsys.readouterr().out
    assert "racecar" in out and "3 character(s)" in out


def test_cli_mirror(capsys):
    assert cli.main(["--mirror", "race"]) == 0
    out = capsys.readouterr().out
    assert "raceecar" in out and "8" in out


def test_cli_longest(capsys):
    assert cli.main(["--longest", "forgeeksskeegfor"]) == 0
    out = capsys.readouterr().out
    assert "geeksskeeg" in out


def test_cli_longest_of_a_palindrome_says_whole(capsys):
    assert cli.main(["--longest", "racecar"]) == 0
    assert "(the whole phrase)" in capsys.readouterr().out


def test_cli_custom_file(tmp_path, capsys):
    path = tmp_path / "p.txt"
    path.write_text("abba\nabc\n", encoding="utf-8")
    assert cli.main(["--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "1 palindrome(s), 1 other(s)" in out


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.txt"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_json_payload(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "list"
    assert payload["palindromes"] == 10
    assert payload["stats"]["longest_length"] == 19


def test_cli_json_check(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--check", "Racecar", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "check"
    assert payload["result"]["palindrome"] is True


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--stats", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
