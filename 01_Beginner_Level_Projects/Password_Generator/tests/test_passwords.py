"""Tests for Password_Generator: policy, generation, validation, history."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                       # noqa: E402
import passwords                                         # noqa: E402
from passwords import (                                   # noqa: E402
    AMBIGUOUS,
    DIGITS,
    LOWER,
    SYMBOLS,
    UPPER,
    PasswordError,
    PasswordHistory,
    Policy,
    count_classes,
    generate,
    generate_many,
    generate_unique,
    is_compliant,
    max_repeat,
    observed_pool,
    pattern_warnings,
    run_demo,
    strength,
    strength_label,
    validate,
)


def standard() -> Policy:
    return Policy(name="standard")


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #
def test_default_policy_shape():
    policy = standard()
    assert policy.length == 16
    assert policy.minimum_total == 4
    assert policy.pool_size == 88
    assert policy.entropy_bits == 103.35
    assert policy.label == "excellent"


def test_pool_is_the_union_of_required_classes():
    only_lower = Policy(min_upper=0, min_digits=0, min_symbols=0)
    assert only_lower.pool == "".join(sorted(LOWER))


def test_pool_ignores_classes_with_zero_minimum():
    digits_only = Policy(length=8, min_lower=0, min_upper=0,
                         min_digits=8, min_symbols=0)
    assert digits_only.pool == "".join(sorted(DIGITS))


def test_forbid_ambiguous_removes_characters():
    clean = Policy(forbid_ambiguous=True)
    assert not set(clean.pool) & set(AMBIGUOUS)
    assert clean.pool_size < Policy().pool_size


@pytest.mark.parametrize("length", [7, 0, -1, 129])
def test_length_bounds(length):
    with pytest.raises(PasswordError, match="between 8 and 128"):
        Policy(length=length)


def test_length_must_be_an_integer():
    with pytest.raises(PasswordError, match="length must be an integer"):
        Policy(length="16")                              # type: ignore[arg-type]
    with pytest.raises(PasswordError, match="length must be an integer"):
        Policy(length=True)                             # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["min_lower", "min_upper", "min_digits",
                                   "min_symbols"])
def test_minimums_must_not_be_negative(field):
    with pytest.raises(PasswordError, match="must not be negative"):
        Policy(**{field: -1})


def test_minimums_must_fit_inside_the_length():
    with pytest.raises(PasswordError, match="but length is 8"):
        Policy(length=8, min_digits=9)


def test_at_least_one_class_is_required():
    with pytest.raises(PasswordError, match="at least one character class"):
        Policy(min_lower=0, min_upper=0, min_digits=0, min_symbols=0)


def test_policy_is_frozen():
    with pytest.raises(Exception):
        standard().length = 20                          # type: ignore[misc]


def test_policy_json_round_trip():
    policy = Policy(name="custom", length=20, min_digits=2)
    again = Policy.from_dict(json.loads(json.dumps(policy.to_dict())))
    assert again == policy


def test_policy_from_dict_defaults_the_name():
    policy = Policy.from_dict({"length": 12})
    assert policy.name == "custom"


def test_policy_from_dict_rejects_unknown_fields():
    with pytest.raises(PasswordError, match="unknown policy field"):
        Policy.from_dict({"colour": "blue"})


def test_policy_from_dict_rejects_non_mapping():
    with pytest.raises(PasswordError, match="must be a mapping"):
        Policy.from_dict([1, 2])                         # type: ignore[arg-type]


def test_charsets_have_the_expected_sizes():
    sets = standard().charsets()
    assert [len(sets[name]) for name in ("lower", "upper", "digits",
                                         "symbols")] == [26, 26, 10, 26]


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def test_generated_password_has_the_right_length():
    assert len(generate(standard(), random.Random(1))) == 16
    assert len(generate(Policy(length=32), random.Random(1))) == 32


def test_same_seed_gives_the_same_password():
    assert generate(standard(), random.Random(9)) == \
        generate(standard(), random.Random(9))


def test_different_seeds_differ():
    assert generate(standard(), random.Random(9)) != \
        generate(standard(), random.Random(10))


def test_generation_meets_every_minimum_repeatedly():
    rng = random.Random(11)
    for _ in range(100):
        counts = count_classes(generate(standard(), rng), standard())
        assert counts == {name: max(count, 1) for name, count in counts.items()}
        assert counts["lower"] >= 1 and counts["upper"] >= 1
        assert counts["digits"] >= 1 and counts["symbols"] >= 1


def test_minimums_are_minimums_not_exact_counts():
    policy = Policy(length=12, min_lower=2, min_upper=2, min_digits=2,
                    min_symbols=2)
    counts = count_classes(generate(policy, random.Random(3)), policy)
    assert all(value >= 2 for value in counts.values())
    assert sum(counts.values()) == 12


def test_ambiguous_characters_are_excluded():
    policy = Policy(length=20, forbid_ambiguous=True)
    rng = random.Random(5)
    for _ in range(100):
        assert not set(generate(policy, rng)) & set(AMBIGUOUS)


def test_only_characters_from_the_pool_are_used():
    policy = Policy(length=10, min_lower=0, min_upper=0, min_digits=10,
                    min_symbols=0)
    password = generate(policy, random.Random(2))
    assert set(password) <= set(DIGITS)


def test_generate_requires_a_policy():
    with pytest.raises(PasswordError, match="policy must be a Policy"):
        generate({"length": 16})                         # type: ignore[arg-type]


def test_generate_many_counts():
    values = generate_many(standard(), 5, random.Random(4))
    assert len(values) == 5
    assert len(set(values)) == 5


def test_generate_many_rejects_bad_count():
    with pytest.raises(PasswordError, match="positive integer"):
        generate_many(standard(), 0)


def test_generation_without_a_rng_uses_system_randomness():
    password = generate(standard())
    assert is_compliant(password, standard())


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_compliant_generated_password_has_no_problems():
    assert validate(generate(standard(), random.Random(1)), standard()) == []


def test_validation_reports_every_problem_at_once():
    problems = validate("short", standard())
    assert len(problems) == 4
    assert any("needs 16 characters" in p for p in problems)
    assert any("upper" in p for p in problems)
    assert any("digits" in p for p in problems)
    assert any("symbols" in p for p in problems)


def test_validation_reports_ambiguous_characters():
    policy = Policy(length=8, forbid_ambiguous=True)
    problems = validate("OOOOOOOO", policy)
    assert any("ambiguous" in p for p in problems)


def test_validation_reports_characters_outside_the_policy():
    policy = Policy(length=8, min_lower=0, min_upper=0, min_digits=8,
                    min_symbols=0)
    problems = validate("1234abcd", policy)
    assert any("outside the policy" in p for p in problems)


def test_validation_rejects_too_long_passwords():
    problems = validate("aA1!" * 40, standard())
    assert any("longer than 128" in p for p in problems)


def test_validation_rejects_non_text():
    with pytest.raises(PasswordError, match="password must be text"):
        validate(12345, standard())                      # type: ignore[arg-type]


def test_is_compliant_shortcut():
    assert is_compliant(generate(standard(), random.Random(1)), standard())
    assert not is_compliant("short", standard())


def test_count_classes_counts_each_set():
    assert count_classes("aA1!", standard()) == {"lower": 1, "upper": 1,
                                                 "digits": 1, "symbols": 1}


# --------------------------------------------------------------------------- #
# Strength
# --------------------------------------------------------------------------- #
def test_strength_labels_at_the_boundaries():
    assert strength_label(39.9) == "weak"
    assert strength_label(40) == "fair"
    assert strength_label(59.9) == "fair"
    assert strength_label(60) == "strong"
    assert strength_label(79.9) == "strong"
    assert strength_label(80) == "excellent"


def test_strength_uses_the_observed_pool():
    report = strength("abcdefgh")
    assert report["pool_size"] == 26
    assert report["classes"] == 1
    assert report["entropy_bits"] == 37.6
    assert report["label"] == "weak"


def test_strength_of_a_mixed_password():
    report = strength("CorrectHorse9!")
    assert report["length"] == 14
    assert report["classes"] == 4
    assert report["pool_size"] == 88
    assert report["label"] == "excellent"
    assert report["warnings"] == []


def test_strength_caps_repeated_characters():
    report = strength("aaaaaaaaaaaaaaaa")
    assert report["repeated"] == 16
    assert report["label"] == "weak"
    assert report["warnings"]


def test_strength_rejects_empty_and_non_text():
    with pytest.raises(PasswordError, match="must not be empty"):
        strength("")
    with pytest.raises(PasswordError, match="must be text"):
        strength(None)                                   # type: ignore[arg-type]


def test_observed_pool_detects_each_class():
    assert set(observed_pool("aA1!")) == set(LOWER) | set(UPPER) | \
        set(DIGITS) | set(SYMBOLS)
    assert observed_pool("abc") == "".join(sorted(LOWER))


def test_max_repeat():
    assert max_repeat("") == 0
    assert max_repeat("abc") == 1
    assert max_repeat("aaab") == 3
    assert max_repeat("abbbbbc") == 5


def test_pattern_warnings_common_fragment():
    warnings = pattern_warnings("PassWord123!")
    assert any("common fragment" in w for w in warnings)


def test_pattern_warnings_repeats():
    assert any("repeated three" in w for w in pattern_warnings("aaabbb123!"))


def test_pattern_warnings_reversed():
    assert any("reversed" in w for w in pattern_warnings("drowssap"))


def test_pattern_warnings_empty_for_random_password():
    assert pattern_warnings("v7#Kq2@Lm9") == []


# --------------------------------------------------------------------------- #
# History
# --------------------------------------------------------------------------- #
def test_history_starts_empty():
    history = PasswordHistory()
    assert len(history) == 0
    assert "anything" not in history


def test_history_add_and_contains():
    history = PasswordHistory()
    history.add("secret-one")
    assert "secret-one" in history
    assert len(history) == 1


def test_history_rejects_reuse():
    history = PasswordHistory()
    history.add("secret-one")
    with pytest.raises(PasswordError, match="already used"):
        history.add("secret-one")


def test_history_rejects_empty_passwords():
    with pytest.raises(PasswordError, match="non-empty string"):
        PasswordHistory().add("")


def test_history_is_bounded():
    history = PasswordHistory(limit=3)
    for value in ("a", "b", "c", "d"):
        history.add(value)
    assert history.entries == ["b", "c", "d"]


def test_history_limit_must_be_positive():
    with pytest.raises(PasswordError, match="at least 1"):
        PasswordHistory(limit=0)


def test_history_clear():
    history = PasswordHistory()
    history.add("x")
    history.clear()
    assert len(history) == 0


def test_history_to_dicts_never_leaks_the_password():
    history = PasswordHistory()
    history.add("secret-one")
    assert history.to_dicts() == [{"index": 0, "length": 10}]


def test_generate_unique_adds_to_history():
    history = PasswordHistory()
    password = generate_unique(standard(), history, random.Random(1))
    assert password in history
    assert len(history) == 1


def test_generate_unique_never_repeats():
    history = PasswordHistory(limit=5)
    rng = random.Random(2)
    values = [generate_unique(standard(), history, rng) for _ in range(5)]
    assert len(set(values)) == 5


def test_generate_unique_requires_a_history():
    with pytest.raises(PasswordError, match="must be a PasswordHistory"):
        generate_unique(standard(), [])                  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Bundled policies
# --------------------------------------------------------------------------- #
def test_bundled_policies_load():
    policies = cli.load_policies(None)
    assert set(policies) == {"standard", "strong", "memorable", "pin"}
    assert policies["standard"].length == 16
    assert policies["pin"].pool == "".join(sorted(DIGITS))


def test_bundled_policies_are_all_usable():
    for policy in cli.load_policies(None).values():
        assert is_compliant(generate(policy, random.Random(1)), policy)


def test_bundled_policies_reject_unknown_fields(tmp_path):
    path = tmp_path / "p.json"
    path.write_text('{"standard": {"length": 16, "colour": "blue"}}',
                    encoding="utf-8")
    with pytest.raises(PasswordError, match="unknown policy field"):
        cli.load_policies(path)


def test_load_policies_missing_file(tmp_path):
    with pytest.raises(PasswordError, match="file not found"):
        cli.load_policies(tmp_path / "nope.json")


def test_load_policies_bad_json(tmp_path):
    path = tmp_path / "p.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(PasswordError, match="not valid JSON"):
        cli.load_policies(path)


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


def test_cli_generates_one_password(capsys):
    assert cli.main(["--seed", "42"]) == 0
    out = capsys.readouterr().out
    assert "policy standard" in out
    assert "103.35 bits" in out


def test_cli_seed_is_reproducible(capsys):
    cli.main(["--seed", "42"])
    first = capsys.readouterr().out
    cli.main(["--seed", "42"])
    assert capsys.readouterr().out == first


def test_cli_count(capsys):
    assert cli.main(["--seed", "1", "--count", "3"]) == 0
    out = capsys.readouterr().out
    lines = [line.strip() for line in out.splitlines() if line.startswith("  ")
             and "policy" not in line]
    assert len(lines) == 3


def test_cli_strong_policy(capsys):
    assert cli.main(["--policy", "strong", "--seed", "1"]) == 0
    assert "policy strong" in capsys.readouterr().out


def test_cli_unknown_policy_exits_two(capsys):
    assert cli.main(["--policy", "nope"]) == 2
    assert "unknown policy" in capsys.readouterr().err


def test_cli_length_override(capsys):
    assert cli.main(["--length", "24", "--seed", "1"]) == 0
    assert "24 chars" in capsys.readouterr().out


def test_cli_no_symbols(capsys):
    assert cli.main(["--no-symbols", "--seed", "1"]) == 0
    assert "policy standard" in capsys.readouterr().out


def test_cli_no_ambiguous(capsys):
    assert cli.main(["--no-ambiguous", "--seed", "1"]) == 0
    out = capsys.readouterr().out
    password = [line.strip() for line in out.splitlines()
                if line.startswith("  ") and "policy" not in line][0]
    assert not set(password) & set(AMBIGUOUS)


def test_cli_check_mode(capsys):
    assert cli.main(["--check", "CorrectHorse9!"]) == 0
    out = capsys.readouterr().out
    assert "excellent" in out


def test_cli_check_mode_reports_warnings(capsys):
    assert cli.main(["--check", "password123"]) == 0
    out = capsys.readouterr().out
    assert "warning:" in out


def test_cli_json_never_contains_the_password(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--seed", "42", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["length"] == 16
    assert payload["count"] == 1
    assert "passwords" not in payload


def test_cli_bad_length_exits_two(capsys):
    assert cli.main(["--length", "4"]) == 2
    assert "between 8 and 128" in capsys.readouterr().err


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--seed", "42", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_choose_policy_returns_the_named_policy_unchanged():
    policies = cli.load_policies(None)

    class Args:
        policy = "standard"
        length = None
        no_symbols = False
        no_ambiguous = False

    assert cli.choose_policy(Args(), policies) is policies["standard"]
