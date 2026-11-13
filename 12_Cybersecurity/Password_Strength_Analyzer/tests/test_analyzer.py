"""Tests for the Password Strength Analyzer project."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from analyzer import (  # noqa: E402
    analyze,
    calculate_entropy,
    detect_classes,
    estimate_crack_times,
    find_patterns,
    format_duration,
    mask,
    render_report,
    score_from_entropy,
)
from main import main  # noqa: E402


# --------------------------------------------------------------------------- #
# Class detection
# --------------------------------------------------------------------------- #
def test_detect_classes_full_mix():
    classes = detect_classes("Ab3!")
    assert set(classes) == {"lowercase", "uppercase", "digits", "symbols"}


def test_detect_classes_dollar_is_symbol():
    assert "symbols" in detect_classes("pa$$word")


def test_detect_classes_space_is_symbol():
    assert "symbols" in detect_classes("correct horse")


def test_detect_classes_lower_only():
    assert detect_classes("abcdef") == ["lowercase"]


def test_detect_classes_unicode():
    assert "unicode" in detect_classes("café")


def test_detect_classes_empty():
    assert detect_classes("") == []


# --------------------------------------------------------------------------- #
# Entropy and scoring
# --------------------------------------------------------------------------- #
def test_entropy_increases_with_length():
    short, _ = calculate_entropy("abcdef")
    long, _ = calculate_entropy("abcdefghijkl")
    assert long > short


def test_entropy_increases_with_charset():
    lower_only, size_lower = calculate_entropy("abcdefgh")
    mixed, size_mixed = calculate_entropy("Abcd1234")
    assert size_mixed > size_lower
    assert mixed > lower_only


def test_entropy_of_empty():
    entropy, size = calculate_entropy("")
    assert entropy == 0.0 and size == 0


def test_score_labels():
    # score = entropy / 1.28, labels cut at score 20/40/60/80
    assert score_from_entropy(0) == (0, "very weak")
    assert score_from_entropy(26)[1] == "weak"      # score 20
    assert score_from_entropy(64)[1] == "fair"      # score 50
    assert score_from_entropy(89)[1] == "strong"    # score 69
    score, label = score_from_entropy(200)
    assert score == 100 and label == "very strong"


# --------------------------------------------------------------------------- #
# Pattern detection
# --------------------------------------------------------------------------- #
def test_common_password_flagged():
    issues = find_patterns("password")
    assert "matches a common password" in issues
    assert "shorter than 8 characters" in find_patterns("login")  # also common


def test_numeric_sequence_flagged():
    assert "contains a numeric sequence" in find_patterns("abc12345")


def test_letter_sequence_flagged():
    assert "contains a letter sequence" in find_patterns("mnopqrst")


def test_repeat_flagged():
    assert "contains 3+ repeated characters" in find_patterns("aaaB1!")


def test_year_flagged():
    assert "contains a year" in find_patterns("event2024!")


def test_keyboard_walk_flagged():
    issues = find_patterns("Qwerty1!")
    assert any("keyboard walk" in issue for issue in issues)


def test_short_password_flagged():
    assert "shorter than 8 characters" in find_patterns("Ab1!")


def test_clean_password_has_no_pattern_issues():
    assert find_patterns("Vx7#qLm9@wRt2") == []


def test_low_variety_flagged():
    assert "uses 3 or fewer distinct characters" in find_patterns("aaaaaaa")


# --------------------------------------------------------------------------- #
# Crack-time estimation
# --------------------------------------------------------------------------- #
def test_format_duration():
    assert format_duration(0.5) == "instantly"
    assert "seconds" in format_duration(30)
    assert "minutes" in format_duration(300)
    assert "years" in format_duration(31_536_000 * 50)


def test_crack_times_zero_entropy():
    times = estimate_crack_times(0)
    assert all(v == "instantly" for v in times.values())


def test_crack_times_monotonic_with_rate():
    times = estimate_crack_times(60, rates={"slow": 1_000, "fast": 1_000_000})
    # faster attacker -> shorter (lexicographic check is fragile, so parse words)
    assert "instantly" not in times.values()
    assert times["fast"] != times["slow"]


# --------------------------------------------------------------------------- #
# Full analysis
# --------------------------------------------------------------------------- #
def test_analyze_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        analyze("")


def test_analyze_weak_common_password():
    report = analyze("password")
    assert report.score <= 20
    assert report.label == "very weak"
    assert "matches a common password" in report.issues


def test_analyze_strong_password():
    report = analyze("G7$zqL!vNn2@wQe")
    assert report.score >= 80
    assert report.label == "very strong"
    assert report.issues == []
    assert report.length == 15


def test_analyze_long_but_trivial_capped():
    # long, but only repeated chars -> must not score as strong
    report = analyze("aaaaaaaaaaaaaaaaaaaa")
    assert report.score <= 30


def test_report_to_dict_shape():
    report = analyze("Tr0ub4dor&3")
    payload = report.to_dict()
    for key in ("length", "score", "label", "entropy_bits", "classes_used",
                "issues", "crack_times"):
        assert key in payload


def test_render_report_sections():
    report = analyze("password")
    text = render_report(report, password="password")
    assert "Score" in text
    assert "•" in text  # masked, never the raw password
    assert "password" not in text.splitlines()[0]  # first line is the mask
    assert "Estimated time to crack" in text


def test_mask_hides_content():
    assert mask("hunter2") == "••••••• (7 chars)"
    assert mask("") == "(empty)"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "very weak" in out


def test_cli_strong_password_exits_zero(capsys):
    assert main(["--password", "G7$zqL!vNn2@wQe"]) == 0
    assert "very strong" in capsys.readouterr().out


def test_cli_weak_password_exits_three(capsys):
    assert main(["--password", "password"]) == 3


def test_cli_no_action_errors(capsys):
    with pytest.raises(SystemExit):
        main([])
    assert "--demo" in capsys.readouterr().err


def test_cli_empty_password(capsys):
    assert main(["--password", ""]) == 2
    assert "empty" in capsys.readouterr().err


def test_cli_stdin(capsys, monkeypatch):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO("G7$zqL!vNn2@wQe\n"))
    assert main(["--stdin"]) == 0


def test_cli_json_output_parses(capsys):
    import json

    assert main(["--password", "G7$zqL!vNn2@wQe", "--json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{"):])
    assert payload["score"] >= 80
    assert payload["password_masked"].startswith("•")


def test_cli_bad_rate(capsys):
    assert main(["--password", "Abc123!xyz", "--rate", "0"]) == 2
    assert "positive" in capsys.readouterr().err


def test_cli_custom_rate(capsys):
    assert main(["--password", "Abc123!xyz9", "--rate", "1000"]) == 0
    assert "custom" in capsys.readouterr().out
