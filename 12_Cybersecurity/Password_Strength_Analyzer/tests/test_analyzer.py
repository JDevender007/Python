"""Tests for the password-strength lab: class arithmetic, penalties, integer time."""

from __future__ import annotations

import dataclasses
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import analyzer  # noqa: E402
import main as cli  # noqa: E402
from analyzer import (  # noqa: E402
    BANDS,
    CHARSET_SIZES,
    LEGACY_CHARSET,
    LEGACY_CRACK,
    LEGACY_SCORE,
    MAX_LENGTH,
    PENALTIES,
    RATES,
    AnalyzerError,
    Row,
    analyze,
    audit,
    band_of,
    build_rows,
    charset_size,
    check_password,
    crack_seconds,
    crack_times,
    detect_classes,
    divide_half_up,
    find_issues,
    format_crack_table,
    format_duration,
    format_millibits,
    guess_bits_of,
    has_keyboard_walk,
    has_numeric_sequence,
    has_run,
    has_triple,
    has_year,
    legacy_charset_size,
    load_rows,
    mask,
    measure,
    milli_bits_per_char,
    penalty_bits,
    render_rows,
    report,
    run_demo,
    score_of,
)


# --------------------------------------------------------------------------- #
# arithmetic and formatting
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "top,bottom,expected", [(10, 4, 3), (5, 2, 3), (1, 3, 0), (2, 3, 1), (-5, 2, -3)]
)
def test_divide_half_up(top, bottom, expected):
    assert divide_half_up(top, bottom) == expected


@pytest.mark.parametrize("bottom", [0, -1])
def test_divide_half_up_refuses_bad_denominators(bottom):
    with pytest.raises(AnalyzerError, match="denominator must be positive"):
        divide_half_up(1, bottom)


@pytest.mark.parametrize("bad", [True, 1.5, "2"])
def test_divide_half_up_refuses_non_integers(bad):
    with pytest.raises(AnalyzerError, match="must be an integer"):
        divide_half_up(bad, 2)


@pytest.mark.parametrize(
    "value,text", [(153_664, "153.664"), (4700, "4.700"), (0, "0.000"), (-1500, "-1.500")]
)
def test_format_millibits(value, text):
    assert format_millibits(value) == text


def test_milli_bits_per_char_pins_a_lowercase_alphabet():
    assert milli_bits_per_char(26) == 4700


def test_milli_bits_per_char_pins_the_full_ascii_alphabet():
    assert milli_bits_per_char(95) == 6570


def test_milli_bits_per_char_of_one_is_zero():
    assert milli_bits_per_char(1) == 0


def test_milli_bits_per_char_refuses_zero():
    with pytest.raises(AnalyzerError, match="must be positive"):
        milli_bits_per_char(0)


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", ["", "   ", "\t"])
def test_check_password_refuses_blank_text(bad):
    with pytest.raises(AnalyzerError, match="must not be empty"):
        check_password(bad)


def test_check_password_refuses_a_non_string():
    with pytest.raises(AnalyzerError, match="must be text"):
        check_password(12345)


def test_check_password_refuses_non_ascii():
    with pytest.raises(AnalyzerError, match="ASCII only"):
        check_password("caf\u00e9")


def test_check_password_refuses_an_over_long_secret():
    with pytest.raises(AnalyzerError, match="longer than 256"):
        check_password("a" * (MAX_LENGTH + 1))


def test_check_password_accepts_the_maximum_length():
    assert len(check_password("a" * MAX_LENGTH)) == MAX_LENGTH


def test_check_password_keeps_inner_spaces():
    assert check_password("correct horse") == "correct horse"


# --------------------------------------------------------------------------- #
# character classes
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "password,expected",
    [
        ("abc", ("lowercase",)),
        ("ABC", ("uppercase",)),
        ("123", ("digits",)),
        ("a!A1", ("lowercase", "uppercase", "digits", "symbols")),
        ("a b", ("lowercase", "symbols")),
        ("!!!!", ("symbols",)),
    ],
)
def test_detect_classes(password, expected):
    assert detect_classes(password) == expected


def test_detect_classes_keeps_a_fixed_order():
    assert detect_classes("1aA!") == ("lowercase", "uppercase", "digits", "symbols")


def test_charset_size_sums_the_classes():
    assert charset_size(("lowercase", "uppercase")) == 52


def test_charset_size_of_all_four_classes_is_95():
    assert charset_size(CHARSET_SIZES) == 95


def test_charset_size_refuses_an_unknown_class():
    with pytest.raises(AnalyzerError, match="unknown character class"):
        charset_size(("hieroglyphs",))


def test_legacy_charset_size_multiplies_the_classes():
    assert legacy_charset_size(("lowercase", "uppercase")) == 676
    assert legacy_charset_size(("lowercase", "uppercase", "digits")) == 6_760
    assert legacy_charset_size(("lowercase", "uppercase", "digits", "symbols")) == 223_080


def test_legacy_charset_size_refuses_an_unknown_class():
    with pytest.raises(AnalyzerError, match="unknown character class"):
        legacy_charset_size(("runes",))


def test_charset_sizes_are_pinned():
    assert CHARSET_SIZES == {"lowercase": 26, "uppercase": 26, "digits": 10, "symbols": 33}


# --------------------------------------------------------------------------- #
# patterns
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", ["abcd", "dcba", "wxyz", "abcdX"])
def test_has_run_finds_four_ascending_or_descending_letters(text):
    assert has_run(text) is True


@pytest.mark.parametrize("text", ["abce", "acbd", "ab", "zyx"])
def test_has_run_allows_short_or_broken_letters(text):
    assert has_run(text) is False


def test_has_run_can_use_a_shorter_span():
    assert has_run("abc", minimum=3) is True


@pytest.mark.parametrize("text", ["0123", "9876", "abc1234"])
def test_has_numeric_sequence(text):
    assert has_numeric_sequence(text) is True


@pytest.mark.parametrize("text", ["012", "0246", "1a2b3c4"])
def test_has_numeric_sequence_refuses_short_or_broken_runs(text):
    assert has_numeric_sequence(text) is False


@pytest.mark.parametrize("text", ["qwerty", "asdf", "zxcvbn", "poiuy"])
def test_has_keyboard_walk(text):
    assert has_keyboard_walk(text) is True


@pytest.mark.parametrize("text", ["abcde", "horsey", "n0pe!"])
def test_has_keyboard_walk_refuses_ordinary_words(text):
    assert has_keyboard_walk(text) is False


def test_has_keyboard_walk_sees_three_keys():
    assert has_keyboard_walk("xqwex") is True


@pytest.mark.parametrize("text", ["2024", "Summer2024", "1900"])
def test_has_year(text):
    assert has_year(text) is True


@pytest.mark.parametrize("text", ["2124", "202", "3141"])
def test_has_year_refuses_other_numbers(text):
    assert has_year(text) is False


def test_has_year_accepts_a_longer_run_that_starts_with_a_century_prefix():
    assert has_year("20245") is True


@pytest.mark.parametrize("text", ["aaa", "xbbb", "zzzz"])
def test_has_triple(text):
    assert has_triple(text) is True


@pytest.mark.parametrize("text", ["aabb", "correct horse"])
def test_has_triple_refuses_pairs(text):
    assert has_triple(text) is False


def test_find_issues_lists_a_common_password_first():
    assert find_issues("password")[0] == "matches a common password"


def test_find_issues_prefers_the_common_list_over_the_dictionary():
    issues = find_issues("monkey")
    assert "matches a common password" in issues
    assert "contains a dictionary word" not in issues


def test_find_issues_finds_a_decorated_word():
    assert "contains a dictionary word" in find_issues("Password2024")


def test_find_issues_flags_a_single_trailing_symbol():
    assert "ends with a single symbol" in find_issues("hello!")


def test_find_issues_does_not_flag_two_symbols():
    assert "ends with a single symbol" not in find_issues("hello!!")


def test_find_issues_flags_a_trailing_symbol_only_at_the_end():
    assert "ends with a single symbol" not in find_issues("he!llo")


def test_find_issues_flags_short_passwords():
    assert "shorter than 8 characters" in find_issues("abc")
    assert "shorter than 12 characters" not in find_issues("abc")


def test_find_issues_flags_eleven_characters_as_short():
    assert "shorter than 12 characters" in find_issues("Tr0ub4dor&3")


def test_find_issues_flags_a_tiny_alphabet():
    assert "uses 3 or fewer distinct characters" in find_issues("aaaa")


def test_find_issues_lists_each_issue_once():
    issues = find_issues("aaaaaaaaaaaa")
    assert len(issues) == len(set(issues))


def test_find_issues_is_empty_for_a_passphrase():
    assert find_issues("correct horse battery staple") == []


def test_penalty_bits_sums_the_documented_values():
    assert penalty_bits(["contains a year", "shorter than 12 characters"]) == 8


def test_penalty_bits_refuses_an_undocumented_issue():
    with pytest.raises(AnalyzerError, match="no penalty is documented"):
        penalty_bits(["smells wrong"])


def test_every_penalty_is_positive():
    assert all(value > 0 for value in PENALTIES.values())


def test_guess_bits_subtract_the_penalties():
    assert guess_bits_of(52, ["contains a year", "contains a keyboard walk"]) == 40


def test_guess_bits_never_fall_below_one():
    assert guess_bits_of(10, ["matches a common password"]) == 1


def test_guess_bits_refuse_a_zero_ceiling():
    with pytest.raises(AnalyzerError, match="must be positive"):
        guess_bits_of(0, [])


# --------------------------------------------------------------------------- #
# bands and score
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "bits,name",
    [(0, "very weak"), (24, "very weak"), (25, "weak"), (44, "weak"), (45, "fair"),
     (64, "fair"), (65, "strong"), (84, "strong"), (85, "very strong"), (500, "very strong")],
)
def test_band_of_is_half_open(bits, name):
    assert band_of(bits) == name


@pytest.mark.parametrize("bits", [-1, 10_000])
def test_band_of_refuses_bits_outside_every_band(bits):
    with pytest.raises(AnalyzerError, match="no band covers"):
        band_of(bits)


def test_bands_are_contiguous_and_half_open():
    assert BANDS[0][0] == 0
    assert all(low < high for low, high, _ in BANDS)
    assert all(
        earlier[1] == later[0] for earlier, later in zip(BANDS, BANDS[1:])
    )


def test_score_is_the_bits_capped_at_one_hundred():
    assert score_of(59) == 59
    assert score_of(100) == 100
    assert score_of(165) == 100


def test_score_refuses_zero_bits():
    with pytest.raises(AnalyzerError, match="must be positive"):
        score_of(0)


# --------------------------------------------------------------------------- #
# measuring one password
# --------------------------------------------------------------------------- #
def test_analyze_pins_the_decorated_word():
    row = analyze("decorated", "Password2024")
    assert row.length == 12
    assert row.charset == 62
    assert row.legacy_charset == 6_760
    assert row.random_bits == 71
    assert row.legacy_bits == 153
    assert row.penalties == 12
    assert row.guess_bits == 59
    assert row.score == 59
    assert row.label_band == "fair"
    assert row.issues == ("contains a dictionary word", "contains a year")


def test_analyze_pins_the_common_password():
    row = analyze("password", "password")
    assert row.random_bits == 38
    assert row.guess_bits == 14
    assert row.label_band == "very weak"


def test_analyze_keeps_the_legacy_figure_above_the_random_ceiling():
    row = analyze("decorated", "Password2024")
    assert row.legacy_bits > row.random_bits


def test_analyze_leaves_a_passphrase_unpenalised():
    row = analyze("passphrase", "correct horse battery staple")
    assert row.penalties == 0
    assert row.guess_bits == row.random_bits == 165
    assert row.score == 100
    assert row.label_band == "very strong"


def test_analyze_charges_a_repeated_character_password():
    row = analyze("repeats", "aaaaaaaaaaaa")
    assert row.random_bits == 56
    assert row.penalties == 15
    assert row.guess_bits == 41
    assert row.label_band == "weak"


def test_analyze_pins_the_keyboard_walk():
    row = analyze("qwerty2024", "qwerty2024")
    assert row.random_bits == 52
    assert row.penalties == 16
    assert row.guess_bits == 36
    assert row.issues == (
        "contains a keyboard walk",
        "contains a year",
        "shorter than 12 characters",
    )


def test_analyze_trims_a_label():
    assert analyze("  one  ", "abcdefgh").label == "one"


def test_analyze_refuses_a_blank_label():
    with pytest.raises(AnalyzerError, match="must not be empty"):
        analyze("  ", "abcdefgh")


def test_analyze_refuses_a_blank_password():
    with pytest.raises(AnalyzerError):
        analyze("one", "")


def test_a_row_is_frozen():
    row = analyze("one", "abcdefgh")
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.guess_bits = 1  # type: ignore[misc]


def test_a_row_masks_itself():
    assert analyze("one", "abcdefgh").masked == "******** (8 chars)"


def test_a_row_exposes_its_crack_times():
    assert set(analyze("one", "abcdefgh").crack_seconds) == {name for name, _ in RATES}


def test_mask_keeps_the_length_and_hides_the_text():
    assert mask("abc") == "*** (3 chars)"


def test_mask_caps_the_asterisks_at_twenty_four():
    assert mask("a" * 30) == "*" * 24 + " (30 chars)"


def test_mask_refuses_a_blank_password():
    with pytest.raises(AnalyzerError):
        mask("")


# --------------------------------------------------------------------------- #
# crack time
# --------------------------------------------------------------------------- #
def test_crack_seconds_is_half_the_keyspace():
    assert crack_seconds(20, 1) == 1 << 19


def test_crack_seconds_truncates_toward_zero():
    assert crack_seconds(3, 1000) == 0


@pytest.mark.parametrize("bits", [0, 1])
def test_one_bit_or_less_is_instant(bits):
    assert crack_seconds(bits, 1) == 0


def test_crack_seconds_refuses_a_zero_rate():
    with pytest.raises(AnalyzerError, match="rate must be positive"):
        crack_seconds(10, 0)


def test_crack_seconds_returns_an_integer():
    assert isinstance(crack_seconds(60, 3), int)


def test_crack_times_covers_every_rate_in_order():
    table = crack_times(30)
    assert list(table) == [name for name, _ in RATES]
    assert all(value >= 0 for value in table.values())


def test_crack_times_are_monotonic_in_attack_rate():
    values = list(crack_times(60).values())
    assert all(later <= earlier for earlier, later in zip(values, values[1:]))


@pytest.mark.parametrize(
    "seconds,text",
    [
        (0, "instantly"),
        (1, "1 second"),
        (59, "59 seconds"),
        (60, "1 minute"),
        (3600, "1 hour"),
        (86_400, "1 day"),
        (31_557_600, "1 year"),
        (3_155_760_000, "1 century"),
        (7_200, "2 hours"),
    ],
)
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text


def test_format_duration_switches_to_an_order_of_magnitude():
    assert format_duration(10 ** 20) == "10^10 centuries"


def test_format_duration_refuses_a_negative_count():
    with pytest.raises(AnalyzerError):
        format_duration(-1)


def test_format_crack_table_lists_every_rate():
    table = format_crack_table(analyze("one", "abcdefgh"))
    assert table.count("\n") == len(RATES) - 1
    assert "throttled online" in table
    assert "offline cluster" in table


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def test_load_rows_reads_the_bundled_seed():
    rows = load_rows()
    assert [row.label for row in rows] == [
        "password", "decorated", "leet", "passphrase", "repeats", "qwerty2024"
    ]


def test_load_rows_refuses_a_missing_file(tmp_path):
    with pytest.raises(AnalyzerError, match="file not found"):
        load_rows(tmp_path / "nope.csv")


def test_load_rows_refuses_non_ascii_bytes(tmp_path):
    path = tmp_path / "passwords.csv"
    path.write_bytes(b"label,password\none,ab\xffcd\n")
    with pytest.raises(AnalyzerError, match="not ASCII text"):
        load_rows(path)


def test_load_rows_refuses_a_missing_column(tmp_path):
    path = tmp_path / "passwords.csv"
    path.write_text("label,secret\none,abcdefgh\n", encoding="ascii")
    with pytest.raises(AnalyzerError, match="missing column"):
        load_rows(path)


def test_build_rows_refuses_an_empty_table():
    with pytest.raises(AnalyzerError, match="holds no rows"):
        build_rows([])


def test_build_rows_refuses_a_duplicate_label():
    with pytest.raises(AnalyzerError, match="must be unique"):
        build_rows(
            [
                {"label": "same", "password": "abcdefgh"},
                {"label": "same", "password": "ijklmnop"},
            ]
        )


def test_build_rows_refuses_a_row_without_a_password():
    with pytest.raises(AnalyzerError):
        build_rows([{"label": "one", "password": ""}])


def test_build_rows_measures_each_password():
    rows = build_rows([{"label": "one", "password": "abcdefgh"}, {"label": "two", "password": "abc"}])
    assert [row.length for row in rows] == [8, 3]


def test_measure_pins_the_seed():
    measured = measure()
    assert measured["count"] == 6
    assert measured["weakest"].label == "password"
    assert measured["strongest"].label == "passphrase"
    assert measured["total_issues"] == 10


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "Row(" not in text
    assert payload["count"] == 6
    assert payload["rows"][1]["label"] == "decorated"
    assert payload["rows"][1]["charset"] == 62
    assert payload["rows"][1]["guess_bits"] == 59
    assert payload["rows"][1]["band"] == "fair"


def test_report_keeps_the_legacy_numbers():
    rows = {row["label"]: row for row in report(measure())["rows"]}
    assert rows["decorated"]["legacy_charset"] == 6_760
    assert rows["decorated"]["legacy_bits"] == 153
    assert rows["leet"]["legacy_charset"] == 223_080


def test_render_rows_shows_every_password():
    rendered = render_rows(measure())
    assert rendered.count("\n") == 6
    assert "decorated" in rendered
    assert "very strong" in rendered
    assert "6,760" not in rendered  # the table shows the raw integer


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_audit_passes_every_check():
    results = audit(measure())
    assert len(results) == 26
    assert all(ok for _, ok in results)


def test_audit_names_are_unique():
    names = [name for name, _ in audit(measure())]
    assert len(names) == len(set(names))


def test_audit_negative_control_with_the_legacy_product():
    def legacy(label, password):
        raw = check_password(password)
        classes = detect_classes(raw)
        issues = find_issues(raw)
        charset = legacy_charset_size(classes)
        bits = divide_half_up(milli_bits_per_char(charset) * len(raw), 1000)
        return Row(
            label=label,
            text=raw,
            classes=classes,
            charset=charset,
            legacy_charset=charset,
            random_bits=bits,
            legacy_bits=bits,
            guess_bits=bits,
            score=score_of(bits),
            label_band=band_of(bits),
            issues=tuple(issues),
            penalties=0,
        )

    results = dict(audit(measure(), interpret=legacy))
    assert results["the_true_charset_sums_the_classes"] is False
    assert results["the_guess_bits_are_pinned"] is False
    assert results["rebuild_is_deterministic"] is False
    assert results["the_same_charset_matches_an_independent_sum"] is True


def test_audit_negative_control_reader_that_raises():
    def broken(label, password):
        raise AnalyzerError("boom")

    results = dict(audit(measure(), interpret=broken))
    assert results["every_password_is_measured_once"] is False
    assert results["rebuild_is_deterministic"] is False


def test_audit_detects_a_tampered_guess_count():
    measured = measure()
    rows = list(measured["rows"])
    rows[1] = dataclasses.replace(rows[1], guess_bits=99)
    measured["rows"] = rows
    results = dict(audit(measured))
    assert results["the_guess_bits_are_pinned"] is False
    assert results["rebuild_is_deterministic"] is False
    assert results["the_penalties_are_additive_and_pinned"] is True


def test_audit_detects_a_tampered_charset():
    measured = measure()
    rows = list(measured["rows"])
    rows[1] = dataclasses.replace(rows[1], charset=6760)
    measured["rows"] = rows
    results = dict(audit(measured))
    assert results["the_same_charset_matches_an_independent_sum"] is False


def test_audit_detects_a_tampered_issue_list():
    measured = measure()
    rows = list(measured["rows"])
    rows[4] = dataclasses.replace(rows[4], issues=())
    measured["rows"] = rows
    assert dict(audit(measured))["the_repeated_character_password_is_penalised"] is False


# --------------------------------------------------------------------------- #
# demo and CLI
# --------------------------------------------------------------------------- #
def test_the_legacy_snippets_are_kept_as_text():
    assert "size *=" in LEGACY_CHARSET
    assert "1.28" in LEGACY_SCORE
    assert "2 ** entropy" in LEGACY_CRACK


def test_run_demo_returns_zero_and_ends_with_the_contract(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    second = capsys.readouterr().out
    assert first == second


def test_demo_prints_the_pinned_numbers(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "Passwords: 6 ASCII secrets (10 weaknesses found in total)." in out
    assert "decorated draws from 3 classes: 26 + 26 + 10 = 62 characters." in out
    assert "the legacy product is 6,760 characters" in out
    assert "against 71 bits for the real alphabet." in out
    assert "legacy says very strong at 100/100" in out
    assert "the rebuild says fair at 59/100" in out
    assert "26/26 checks pass" in out
    assert "FAIL " not in out


def test_demo_writes_nothing_to_stderr():
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        run_demo()
    assert err.getvalue() == ""


def test_demo_output_is_ascii(capsys):
    run_demo()
    assert capsys.readouterr().out.isascii()


def test_cli_demo_exits_zero():
    assert cli.main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_json_writes_a_report(tmp_path):
    destination = tmp_path / "report.json"
    assert cli.main(["--json", str(destination)]) == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["weakest"] == "password"
    assert payload["rows"][1]["band"] == "fair"


def test_cli_json_creates_the_parent_folder(tmp_path):
    destination = tmp_path / "nested" / "deep" / "report.json"
    assert cli.main(["--json", str(destination)]) == 0
    assert destination.is_file()


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such/passwords.csv"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_duplicate_label_exits_two(tmp_path, capsys):
    path = tmp_path / "passwords.csv"
    path.write_text("label,password\nsame,abcdefgh\nsame,ijklmnop\n", encoding="ascii")
    assert cli.main(["--file", str(path)]) == 2
    assert "must be unique" in capsys.readouterr().err


def test_cli_non_ascii_password_exits_two(tmp_path, capsys):
    path = tmp_path / "passwords.csv"
    path.write_bytes(b"label,password\none,caf\xc3\xa9\n")
    assert cli.main(["--file", str(path)]) == 2
    assert "ASCII" in capsys.readouterr().err


def test_cli_prints_the_summary(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "weakest password (14 bits), strongest passphrase (165 bits)" in out


def test_cli_quiet_json_still_writes(tmp_path):
    destination = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(destination)]) == 0
    assert destination.is_file()


def test_module_audit_is_exposed():
    assert analyzer.audit is audit
