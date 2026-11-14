"""Tests for Anagrams: normalisation, signatures, grouping, search and CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import anagram                                            # noqa: E402
import main as cli                                        # noqa: E402
from anagram import (                                     # noqa: E402
    AnagramError,
    anagram_pairs,
    difference,
    find_anagrams,
    group_anagrams,
    is_anagram,
    letter_counts,
    load_words,
    longest_group,
    normalize,
    run_demo,
    signature,
)

WORDS = load_words(PROJECT / "data" / "words.txt")


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #
def test_normalize_folds_case():
    assert normalize("ABC") == "abc"


def test_normalize_drops_spaces_and_punctuation():
    assert normalize("  Snooze   alarms ") == "snoozealarms"
    assert normalize("no more Z's") == "nomorezs"
    assert normalize("a-b_c.d!") == "abcd"


def test_normalize_drops_digits():
    assert normalize("abc123") == "abc"


def test_normalize_of_letter_free_text_is_empty():
    assert normalize("123 !!! ---") == ""


def test_normalize_rejects_non_text():
    with pytest.raises(AnagramError, match="text must be a string"):
        normalize(None)                                  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Signatures
# --------------------------------------------------------------------------- #
def test_signature_is_sorted_letters():
    assert signature("listen") == "eilnst"


def test_signature_ignores_order_and_case():
    assert signature("Listen") == signature("SILENT") == "eilnst"


def test_signature_of_the_classic_pair():
    assert signature("Snooze alarms") == signature("Alas, no more Z's") == \
        "aaelmnoorssz"


def test_signature_of_letter_free_text_is_empty():
    assert signature("123") == ""


def test_signature_is_stable_for_any_permutation():
    base = signature("triangle")
    for permutation in ("integral", "altering", "relating", "TRIANGLE"):
        assert signature(permutation) == base


# --------------------------------------------------------------------------- #
# is_anagram
# --------------------------------------------------------------------------- #
def test_is_anagram_true_for_a_real_pair():
    assert is_anagram("listen", "silent") is True


def test_is_anagram_ignores_punctuation_and_case():
    assert is_anagram("The Morse Code", "Here come dots") is True


def test_is_anagram_false_when_one_letter_is_missing():
    assert is_anagram("listen", "silen") is False


def test_is_anagram_false_when_one_letter_is_extra():
    assert is_anagram("listen", "silentt") is False


def test_is_anagram_false_for_different_letters():
    assert is_anagram("abc", "abd") is False


def test_is_anagram_false_for_two_empty_strings():
    assert is_anagram("", "") is False


def test_is_anagram_false_for_letter_free_input():
    assert is_anagram("123", "!!!") is False


def test_is_anagram_false_when_only_one_side_is_letterless():
    assert is_anagram("", "abc") is False
    assert is_anagram("abc", "123") is False


def test_is_anagram_symmetric():
    assert is_anagram("evil", "vile") == is_anagram("vile", "evil") is True


def test_is_anagram_compares_multiplicities_not_sets():
    # the original one-liner got this wrong: {a,b,c} == {a,b} by subset
    assert is_anagram("aabc", "abc") is False


# --------------------------------------------------------------------------- #
# Counts and differences
# --------------------------------------------------------------------------- #
def test_letter_counts_are_sorted():
    assert letter_counts("Banana") == {"a": 3, "b": 1, "n": 2}


def test_letter_counts_of_letter_free_text():
    assert letter_counts("123!") == {}


def test_difference_reports_a_missing_letter():
    assert difference("listen", "silentt") == {"t": -1}


def test_difference_cancels_shared_letters():
    assert difference("abc", "abd") == {"c": 1, "d": -1}


def test_difference_is_empty_for_anagrams():
    assert difference("evil", "vile") == {}


def test_difference_is_signed_and_symmetric():
    assert difference("abc", "abd") == {
        key: -value for key, value in difference("abd", "abc").items()}


# --------------------------------------------------------------------------- #
# Grouping
# --------------------------------------------------------------------------- #
def test_group_anagrams_keeps_only_real_groups():
    groups = group_anagrams(["listen", "silent", "banana"])
    assert groups == {"eilnst": ["listen", "silent"]}


def test_group_anagrams_sorts_members():
    groups = group_anagrams(["silent", "listen", "tinsel"])
    assert groups["eilnst"] == ["listen", "silent", "tinsel"]


def test_group_anagrams_sorts_keys():
    groups = group_anagrams(["stop", "pots", "evil", "veil", "gear", "rage"])
    assert list(groups) == ["aegr", "eilv", "opst"]


def test_group_anagrams_of_singletons_is_empty():
    assert group_anagrams(["banana", "python"]) == {}


def test_group_anagrams_of_an_empty_list_is_empty():
    assert group_anagrams([]) == {}


def test_group_anagrams_skips_letter_free_words():
    assert group_anagrams(["123", "!!!"]) == {}


def test_group_anagrams_rejects_a_non_list():
    with pytest.raises(AnagramError, match="words must be a list"):
        group_anagrams("listen")                         # type: ignore[arg-type]


def test_group_anagrams_rejects_non_text_words():
    with pytest.raises(AnagramError, match="each word must be a string"):
        group_anagrams(["listen", 7])                    # type: ignore[list-item]


def test_bundled_word_list_has_48_words():
    assert len(WORDS) == 48


def test_bundled_word_list_forms_six_groups():
    assert len(group_anagrams(WORDS)) == 6


def test_bundled_group_members_share_their_signature():
    for key, members in group_anagrams(WORDS).items():
        assert all(signature(word) == key for word in members)


def test_bundled_groups_do_not_reuse_a_word():
    seen = [word for members in group_anagrams(WORDS).values()
            for word in members]
    assert len(seen) == len({word.casefold() for word in seen})


def test_bundled_group_sizes():
    sizes = sorted(len(members) for members in group_anagrams(WORDS).values())
    assert sizes == [3, 3, 4, 4, 4, 5]


# --------------------------------------------------------------------------- #
# Search and pairs
# --------------------------------------------------------------------------- #
def test_find_anagrams_excludes_the_word_itself():
    assert find_anagrams("listen", ["silent", "tinsel", "enlist", "listens"]) \
        == ["enlist", "silent", "tinsel"]


def test_find_anagrams_is_case_insensitive_but_keeps_the_candidate():
    assert find_anagrams("Listen", ["SILENT", "listen", "banana"]) == ["SILENT"]


def test_find_anagrams_with_no_matches():
    assert find_anagrams("banana", WORDS) == []


def test_find_anagrams_rejects_letter_free_input():
    with pytest.raises(AnagramError, match="contains no letters"):
        find_anagrams("123", WORDS)


def test_anagram_pairs_are_unordered_and_distinct():
    pairs = anagram_pairs(WORDS)
    assert all(first != second for first, second in pairs)
    assert all((second, first) not in pairs for first, second in pairs)


def test_anagram_pairs_count_for_the_bundled_list():
    assert len(anagram_pairs(WORDS)) == 34


def test_anagram_pairs_are_sorted():
    pairs = anagram_pairs(WORDS)
    assert pairs[0] == ("ager", "gear")
    assert pairs[-1] == ("veil", "vile")
    assert pairs == sorted(pairs,
                           key=lambda pair: (pair[0].casefold(),
                                             pair[1].casefold()))


def test_anagram_pairs_pair_count_matches_the_groups():
    groups = group_anagrams(WORDS)
    expected = sum(len(members) * (len(members) - 1) // 2
                   for members in groups.values())
    assert len(anagram_pairs(WORDS)) == expected


def test_anagram_pairs_of_an_empty_list_is_empty():
    assert anagram_pairs([]) == []


def test_anagram_pairs_skips_letter_free_words():
    assert anagram_pairs(["123", "!!!"]) == []


# --------------------------------------------------------------------------- #
# Longest group
# --------------------------------------------------------------------------- #
def test_longest_group_returns_the_biggest():
    assert longest_group(group_anagrams(WORDS)) == \
        ["least", "slate", "stale", "steal", "tales"]


def test_longest_group_of_nothing_is_empty():
    assert longest_group({}) == []


def test_longest_group_breaks_ties_alphabetically():
    groups = {"b": ["bee"], "a": ["ace"], "c": ["cat"]}
    assert longest_group(groups) == ["ace"]


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_load_words_skips_comments_and_blank_lines(tmp_path):
    path = tmp_path / "w.txt"
    path.write_text("# a comment\n\nlisten\n  silent  \n", encoding="utf-8")
    assert load_words(path) == ["listen", "silent"]


def test_load_words_missing_file(tmp_path):
    with pytest.raises(AnagramError, match="file not found"):
        load_words(tmp_path / "nope.txt")


def test_load_words_empty_file(tmp_path):
    path = tmp_path / "w.txt"
    path.write_text("# only a comment\n\n", encoding="utf-8")
    with pytest.raises(AnagramError, match="contains no words"):
        load_words(path)


def test_word_list_constants_are_documented():
    assert anagram.MIN_WORD_LENGTH == 1


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


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_groups(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "48 words" in out
    assert "6 group(s)" in out
    assert "largest has 5 member(s)" in out


def test_cli_pairs(capsys):
    assert cli.main(["--pairs"]) == 0
    out = capsys.readouterr().out
    assert "34 unordered pair(s)" in out


def test_cli_check_true(capsys):
    assert cli.main(["--check", "listen", "silent"]) == 0
    out = capsys.readouterr().out
    assert "anagrams" in out
    assert "eilnst" in out


def test_cli_check_false(capsys):
    assert cli.main(["--check", "listen", "silen"]) == 0
    out = capsys.readouterr().out
    assert "not anagrams" in out


def test_cli_find(capsys):
    assert cli.main(["--find", "listen"]) == 0
    out = capsys.readouterr().out
    assert "3 match(es)" in out
    assert "enlist" in out


def test_cli_find_with_no_match(capsys):
    assert cli.main(["--find", "banana"]) == 0
    assert "0 match(es)" in capsys.readouterr().out


def test_cli_custom_file(tmp_path, capsys):
    path = tmp_path / "w.txt"
    path.write_text("listen\nsilent\nbanana\n", encoding="utf-8")
    assert cli.main(["--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "3 words" in out
    assert "1 group(s)" in out


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.txt"]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_letter_free_find_exits_two(capsys):
    assert cli.main(["--find", "123"]) == 2
    assert "contains no letters" in capsys.readouterr().err


def test_cli_json_groups(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "groups"
    assert payload["words"] == 48
    assert payload["largest"] == ["least", "slate", "stale", "steal", "tales"]


def test_cli_json_check(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--check", "evil", "vile", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["anagrams"] is True
    assert payload["first_signature"] == payload["second_signature"] == "eilv"


def test_cli_json_pairs(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--pairs", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "pairs"
    assert len(payload["pairs"]) == 34


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--find", "listen", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
