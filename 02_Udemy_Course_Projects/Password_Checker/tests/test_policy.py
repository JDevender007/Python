"""Tests for Password_Checker: legacy verdicts, policy, patterns and CLI."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from policy import (                                      # noqa: E402
    COMMON_FILE,
    REPEAT_LENGTH,
    SEQUENCE_LENGTH,
    Finding,
    Policy,
    PolicyError,
    Verdict,
    check,
    classify,
    entropy_bits,
    has_repeat,
    has_sequence,
    is_common,
    label_for,
    legacy_verdict,
    load_common,
    plain,
    pool_size,
    run_demo,
    skeleton,
    usernames_from,
)

STRONG = ["Tr0ub4dor&3", "C0mpl3x!ty", "x9#Kp2$Lm", "Q7!vN2@wR4",
          "zT5^mK8&bQ"]
RELAXED = Policy(min_length=4, min_classes=2, min_entropy=10.0,
                 forbid_common=False, forbid_sequences=False,
                 forbid_repeats=False, forbid_username=False)


# --------------------------------------------------------------------------- #
# The legacy program
# --------------------------------------------------------------------------- #
def test_legacy_says_changed_when_nothing_changed():
    assert legacy_verdict("myPass", "myPass") == "Password Changed"


def test_legacy_accepts_a_single_character():
    assert legacy_verdict("a", "a") == "Password Changed"


def test_legacy_refuses_a_case_only_difference():
    assert legacy_verdict("myPass", "MYPASS") == \
        "Please check cases and try again"


def test_legacy_says_do_not_match_otherwise():
    assert legacy_verdict("myPass", "other!") == "Password do not match"


def test_legacy_case_branch_fires_before_the_else():
    # 'Abc' vs 'ABC' differs in case only, so the elif wins
    assert legacy_verdict("Abc", "ABC") != "Password do not match"


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def test_classify_one_class():
    assert classify("abc") == ("lower",)


def test_classify_all_four_in_order():
    assert classify("aA1!") == ("lower", "upper", "digit", "symbol")


def test_classify_ignores_duplicates():
    assert classify("aA1!aA1!") == ("lower", "upper", "digit", "symbol")


def test_classify_of_the_empty_string():
    assert classify("") == ()


def test_classify_treats_space_as_a_symbol():
    assert classify("a b") == ("lower", "symbol")


def test_pool_size_of_one_class():
    assert pool_size(("lower",)) == 26


def test_pool_size_of_all_classes():
    assert pool_size(("lower", "upper", "digit", "symbol")) == 95


def test_pool_size_of_nothing():
    assert pool_size(()) == 0


# --------------------------------------------------------------------------- #
# Entropy
# --------------------------------------------------------------------------- #
def test_entropy_of_three_lowercase_characters():
    assert entropy_bits("abc") == 14.1


def test_entropy_of_four_classes():
    assert entropy_bits("Ab1!") == round(4 * math.log2(95), 2)


def test_entropy_of_a_common_word():
    assert entropy_bits("password") == 37.6


def test_entropy_of_the_empty_string_is_zero():
    assert entropy_bits("") == 0.0


def test_entropy_grows_with_length():
    assert entropy_bits("abcdef") > entropy_bits("abc")


def test_entropy_grows_with_the_pool():
    assert entropy_bits("aA1!") > entropy_bits("aaaa")


def test_entropy_is_rounded_to_two_places():
    value = entropy_bits("abcdefg")
    assert value == round(value, 2)


def test_entropy_refuses_non_text():
    with pytest.raises(PolicyError, match="must be a string"):
        entropy_bits(None)


# --------------------------------------------------------------------------- #
# Patterns
# --------------------------------------------------------------------------- #
def test_repeat_of_three_is_flagged():
    assert has_repeat("aaa") is True


def test_repeat_of_two_is_not():
    assert has_repeat("aabb") is False


def test_repeat_anywhere_in_a_longer_password():
    assert has_repeat("xyzzzab") is True


def test_repeat_with_a_custom_length():
    assert has_repeat("aabb", length=2) is True


def test_repeat_of_one_is_always_true():
    assert has_repeat("abc", length=1) is True


def test_sequence_forward():
    assert has_sequence("abcdefgh") is True


def test_sequence_reversed():
    assert has_sequence("dcba") is True


def test_sequence_of_digits():
    assert has_sequence("xx1234") is True


def test_sequence_on_the_keyboard():
    assert has_sequence("qwerty") is True


def test_sequence_needs_four_characters():
    assert has_sequence("alert123!X") is False


def test_sequence_with_a_custom_length_of_three():
    assert has_sequence("alert123!X", length=3) is True


def test_sequence_of_three_is_not_a_default_sequence():
    assert has_sequence("abc") is False


def test_no_sequence_in_a_random_looking_password():
    assert has_sequence("x9#Kp2$Lm") is False


def test_sequence_length_constant():
    assert SEQUENCE_LENGTH == 4 and REPEAT_LENGTH == 3


# --------------------------------------------------------------------------- #
# Leet and common passwords
# --------------------------------------------------------------------------- #
def test_skeleton_folds_the_classic_substitutions():
    assert skeleton("P@ssw0rd!") == "password"


def test_skeleton_of_a_plain_word():
    assert skeleton("Tr0ub4dor") == "troubador"


def test_skeleton_drops_non_alphanumerics():
    assert skeleton(" a-b_c ") == "abc"


def test_skeleton_of_digits():
    assert skeleton("123456") == "i2eas6"


def test_plain_keeps_digits_but_drops_symbols():
    assert plain("Pass-W0rd!") == "passw0rd"


def test_plain_of_the_empty_string():
    assert plain("") == ""


def test_common_password_is_recognised():
    assert is_common("password") is True


def test_common_password_after_leet_substitution():
    assert is_common("P@ssw0rd!") is True


def test_common_password_by_prefix():
    assert is_common("password1") is True


def test_common_digits_are_recognised():
    assert is_common("123456") is True


def test_a_strong_password_is_not_common():
    assert is_common("Tr0ub4dor&3") is False


def test_a_random_password_is_not_common():
    assert is_common("x9#Kp2$Lm") is False


def test_prefix_rule_needs_six_characters():
    # 'admin' is five characters, so it matches exactly but is not a prefix
    assert is_common("admin", frozenset({"admin"})) is True
    assert is_common("adminxyz", frozenset({"admin"})) is False


def test_prefix_rule_matches_six_characters():
    assert is_common("secretxyz", frozenset({"secret"})) is True


def test_common_accepts_an_injected_set():
    assert is_common("hunter2", frozenset({"hunter2"})) is True
    assert is_common("hunter2", frozenset({"password"})) is False


def test_bundled_common_list_is_lowercase_alphanumeric():
    common = load_common()
    assert all(entry == entry.casefold() for entry in common)
    assert all(entry.isalnum() for entry in common)


def test_bundled_common_list_has_forty_entries():
    assert len(load_common()) == 40


def test_bundled_common_list_is_a_set_of_forty():
    common = load_common()
    assert isinstance(common, frozenset) and len(set(common)) == 40


def test_bundled_common_list_contains_the_expected_words():
    common = load_common()
    assert {"password", "123456", "qwerty", "letmein", "changeme"} <= common


def test_every_bundled_entry_matches_itself():
    common = load_common()
    assert all(is_common(entry, common) for entry in common)


def test_common_list_path_is_the_bundled_file():
    assert COMMON_FILE.name == "common.txt"
    assert COMMON_FILE.parent.name == "data"


def test_load_common_refuses_a_missing_file(tmp_path):
    with pytest.raises(PolicyError, match="not found"):
        load_common(tmp_path / "nope.txt")


def test_load_common_refuses_an_empty_file(tmp_path):
    path = tmp_path / "c.txt"
    path.write_text("# only a comment\n\n", encoding="utf-8")
    with pytest.raises(PolicyError, match="empty"):
        load_common(path)


def test_load_common_skips_comments_and_blank_lines(tmp_path):
    path = tmp_path / "c.txt"
    path.write_text("# list\n\nPassword\nqwerty\n", encoding="utf-8")
    assert load_common(path) == frozenset({"password", "qwerty"})


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
def test_usernames_from_nothing():
    assert usernames_from(None) == ()
    assert usernames_from("") == ()
    assert usernames_from("   ") == ()


def test_usernames_from_a_plain_username():
    assert usernames_from("Alice") == ("alice",)


def test_usernames_from_an_email_include_the_dotted_local_part():
    names = usernames_from("bob.smith@example.com")
    assert "bob.smith" in names and "bobsmith" in names


def test_usernames_from_a_plus_address():
    assert "bob" in usernames_from("bob+tag@example.com")


def test_usernames_from_drop_parts_shorter_than_three():
    assert usernames_from("ab@example.com") == ()


# --------------------------------------------------------------------------- #
# Policy validation
# --------------------------------------------------------------------------- #
def test_default_policy_values():
    policy = Policy()
    assert policy.min_length == 8 and policy.min_classes == 3
    assert policy.min_entropy == 40.0


def test_policy_refuses_zero_length():
    with pytest.raises(PolicyError, match="at least 1"):
        Policy(min_length=0)


def test_policy_refuses_too_many_classes():
    with pytest.raises(PolicyError, match="within 1..4"):
        Policy(min_classes=5)


def test_policy_refuses_zero_classes():
    with pytest.raises(PolicyError, match="within 1..4"):
        Policy(min_classes=0)


def test_policy_refuses_negative_entropy():
    with pytest.raises(PolicyError, match="must not be negative"):
        Policy(min_entropy=-1)


def test_policy_is_frozen():
    with pytest.raises(Exception):
        Policy().min_length = 4                              # type: ignore[misc]


# --------------------------------------------------------------------------- #
# check()
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("candidate", STRONG)
def test_strong_passwords_are_accepted(candidate):
    verdict = check(candidate)
    assert verdict.accepted is True, verdict.codes()
    assert verdict.findings == ()


def test_accepted_verdict_reports_its_length():
    assert check("Tr0ub4dor&3").length == 11


def test_accepted_verdict_reports_four_classes():
    assert check("Tr0ub4dor&3").classes == ("lower", "upper", "digit",
                                            "symbol")


def test_accepted_verdict_has_no_findings():
    assert check("Tr0ub4dor&3").codes() == ()


def test_score_is_within_bounds():
    for candidate in STRONG + ["a", "aaaaaaaa", "P@ssw0rd!"]:
        assert 0 <= check(candidate).score <= 100


def test_score_and_label_agree():
    verdict = check("Tr0ub4dor&3")
    assert verdict.label == label_for(verdict.score)


@pytest.mark.parametrize("candidate, code", [
    ("short1!", "too_short"),
    ("alllowercase", "too_few_classes"),
    ("aaabbb12!X", "repeated_characters"),
    ("abcdefg1!X", "sequence"),
    ("P@ssw0rd!", "common_password"),
    ("aaaaaaaa", "low_entropy"),
])
def test_each_failure_mode_has_its_code(candidate, code):
    verdict = check(candidate)
    assert verdict.accepted is False
    assert code in verdict.codes(), verdict.codes()


def test_a_short_password_is_only_flagged_for_length():
    assert check("Ab1!xyz").codes() == ("too_short",)


def test_a_long_lowercase_word_is_flagged_for_classes_only():
    assert check("onlylowercase").codes() == ("too_few_classes",)


def test_a_repeat_is_reported_once():
    assert check("aaabbb12!X").codes().count("repeated_characters") == 1


def test_multiple_findings_are_all_reported():
    codes = check("aaaaaaaa").codes()
    assert "repeated_characters" in codes
    assert "too_few_classes" in codes
    assert "low_entropy" in codes


def test_a_passphrase_fails_the_class_rule():
    verdict = check("correct horse battery staple")
    assert verdict.accepted is False
    assert verdict.codes() == ("too_few_classes",)
    assert verdict.entropy_bits > 120


def test_identity_containment_is_flagged():
    assert "contains_username" in check("Alice2024!", identity="alice").codes()


def test_identity_check_is_case_insensitive():
    assert "contains_username" in check("ALICE2024!", identity="alice").codes()


def test_identity_check_uses_the_email_local_part():
    codes = check("bobsmith2024!B",
                  identity="bob.smith@example.com").codes()
    assert "contains_username" in codes


def test_identity_check_ignores_unrelated_names():
    assert check("x9#Kp2$Lm",
                 identity="bob.smith@example.com").accepted is True


def test_identity_is_ignored_when_absent():
    assert check("Alice2024!").accepted is True


def test_a_relaxed_policy_accepts_a_short_password():
    assert check("abc1", RELAXED).accepted is True


def test_the_default_policy_refuses_that_password():
    assert check("abc1").accepted is False


def test_an_injected_common_set_is_used():
    verdict = check("Tr0ub4dor&3", common=frozenset({"troubador"}))
    assert "common_password" in verdict.codes()


def test_sequence_and_repeat_rules_can_be_disabled():
    policy = Policy(forbid_sequences=False, forbid_repeats=False)
    codes = check("aaabcdefgh1!X", policy).codes()
    assert "sequence" not in codes and "repeated_characters" not in codes


def test_common_rule_can_be_disabled():
    policy = Policy(forbid_common=False)
    assert "common_password" not in check("P@ssw0rd!", policy).codes()


def test_identity_rule_can_be_disabled():
    policy = Policy(forbid_username=False)
    assert "contains_username" not in check("Alice2024!", policy,
                                            "alice").codes()


def test_check_refuses_an_empty_password():
    with pytest.raises(PolicyError, match="must not be empty"):
        check("")


@pytest.mark.parametrize("bad", [None, 12345, ["a"]])
def test_check_refuses_non_text(bad):
    with pytest.raises(PolicyError, match="must be a string"):
        check(bad)


def test_check_is_pure():
    assert check("Tr0ub4dor&3") == check("Tr0ub4dor&3")


def test_verdict_dict_has_no_password():
    payload = check("Tr0ub4dor&3").to_dict()
    assert "Tr0ub4dor&3" not in json.dumps(payload)
    assert payload["label"] == "strong"


def test_verdict_dict_lists_findings():
    payload = check("P@ssw0rd!").to_dict()
    assert payload["findings"][0]["code"] == "common_password"
    assert payload["accepted"] is False


def test_finding_string_includes_its_code():
    finding = Finding("too_short", "too short")
    assert str(finding) == "too_short: too short"


# --------------------------------------------------------------------------- #
# Labels
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("score, label", [
    (0, "very weak"), (29, "very weak"), (30, "weak"), (49, "weak"),
    (50, "fair"), (69, "fair"), (70, "strong"), (84, "strong"),
    (85, "very strong"), (100, "very strong"),
])
def test_label_boundaries(score, label):
    assert label_for(score) == label


def test_weak_and_strong_scores_are_ordered():
    assert check("Abc12!").score < check("Tr0ub4dor&3").score


def test_the_weak_example_is_labelled_very_weak():
    assert check("Abc12!").label == "very weak"


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


def test_demo_mentions_the_legacy_verdict(capsys):
    run_demo()
    assert "Password Changed" in capsys.readouterr().out


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_check_accepts_a_strong_password(capsys):
    assert cli.main(["--check", "Tr0ub4dor&3"]) == 0
    out = capsys.readouterr().out
    assert "accepted" in out
    assert "81/100 (strong)" in out


def test_cli_check_rejects_a_weak_password(capsys):
    assert cli.main(["--check", "P@ssw0rd!"]) == 1
    out = capsys.readouterr().out
    assert "rejected" in out and "common_password" in out


def test_cli_check_reports_the_identity_finding(capsys):
    assert cli.main(["--check", "Alice2024!", "--identity", "alice"]) == 1
    assert "contains_username" in capsys.readouterr().out


def test_cli_relaxed_policy_accepts_a_short_password(capsys):
    assert cli.main(["--check", "abc1", "--policy", "relaxed"]) == 0
    assert "accepted" in capsys.readouterr().out


def test_cli_strict_policy_rejects_a_default_pass(capsys):
    assert cli.main(["--check", "Tr0ub4dor&3", "--policy", "strict"]) == 1
    assert "rejected" in capsys.readouterr().out


def test_cli_min_length_override(capsys):
    assert cli.main(["--check", "Abc12!", "--min-length", "6"]) == 1
    out = capsys.readouterr().out
    assert "low_entropy" in out


def test_cli_min_classes_override(capsys):
    assert cli.main(["--check", "onlylowercase", "--min-classes", "1"]) == 0
    assert "accepted" in capsys.readouterr().out


def test_cli_list_common(capsys):
    assert cli.main(["--list-common"]) == 0
    out = capsys.readouterr().out
    assert "password" in out and "40 entries" in out


def test_cli_legacy_equal(capsys):
    assert cli.main(["--legacy", "myPass:myPass"]) == 0
    out = capsys.readouterr().out
    assert "Password Changed" in out
    assert "nothing changed" in out


def test_cli_legacy_case_only(capsys):
    assert cli.main(["--legacy", "myPass:MYPASS"]) == 0
    assert "Please check cases" in capsys.readouterr().out


def test_cli_legacy_different(capsys):
    assert cli.main(["--legacy", "myPass:other!"]) == 0
    assert "do not match" in capsys.readouterr().out


def test_cli_legacy_malformed_exits_two(capsys):
    assert cli.main(["--legacy", "nocolon"]) == 2
    assert "expected OLD:NEW" in capsys.readouterr().err


def test_cli_with_no_action_exits_two(capsys):
    assert cli.main([]) == 2
    assert "is required" in capsys.readouterr().err


def test_cli_refuses_an_empty_password(capsys):
    assert cli.main(["--check", ""]) == 2
    assert "must not be empty" in capsys.readouterr().err


def test_cli_json_check(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--check", "Tr0ub4dor&3", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "check"
    assert payload["verdict"]["accepted"] is True
    assert payload["verdict"]["score"] == 81


def test_cli_json_list_common(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--list-common", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["count"] == 40


def test_cli_quiet_check_prints_nothing(capsys):
    assert cli.main(["--check", "Tr0ub4dor&3", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
