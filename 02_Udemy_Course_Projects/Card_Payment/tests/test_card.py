"""Tests for Card_Payment: normalisation, Luhn, brand, length, mask and CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import card                                               # noqa: E402
import main as cli                                        # noqa: E402
from card import (                                        # noqa: E402
    BRANDS,
    DEFAULT_REVEAL,
    LENGTHS,
    MAX_REVEAL,
    CardError,
    brand,
    check,
    check_digit,
    describe,
    digits,
    format_number,
    generate,
    legacy_mask,
    length_ok,
    load_cards,
    luhn_sum,
    luhn_valid,
    mask,
    run_demo,
    try_digits,
    with_check_digit,
)

DATA = PROJECT / "data" / "cards.csv"


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #
def test_digits_of_a_plain_number():
    assert digits("4111111111111111") == "4111111111111111"


def test_digits_drops_spaces():
    assert digits("4111 1111 1111 1111") == "4111111111111111"


def test_digits_drops_hyphens():
    assert digits("4111-1111-1111-1111") == "4111111111111111"


def test_digits_drops_dots():
    assert digits("4111.1111.1111.1111") == "4111111111111111"


def test_digits_strips_surrounding_whitespace():
    assert digits("  4111111111111111  ") == "4111111111111111"


def test_digits_of_empty_string_raises():
    with pytest.raises(CardError, match="is empty"):
        digits("")


def test_digits_of_separators_only_raises():
    with pytest.raises(CardError, match="is empty"):
        digits(" - . ")


def test_digits_of_letters_raises():
    with pytest.raises(CardError, match="non-digits"):
        digits("4111-abcd")


def test_digits_error_names_the_bad_characters():
    with pytest.raises(CardError, match="'xy'"):
        digits("4111xy")


def test_digits_of_an_integer_raises():
    with pytest.raises(CardError, match="must be a string"):
        digits(4111111111111111)                          # type: ignore[arg-type]


def test_digits_of_none_raises():
    with pytest.raises(CardError, match="must be a string"):
        digits(None)                                      # type: ignore[arg-type]


def test_try_digits_returns_empty_instead_of_raising():
    assert try_digits("nope") == ""
    assert try_digits(None) == ""
    assert try_digits("4111 1111") == "41111111"


# --------------------------------------------------------------------------- #
# Luhn
# --------------------------------------------------------------------------- #
def test_luhn_sum_of_a_visa():
    assert luhn_sum("4111111111111111") == 30


def test_luhn_sum_of_a_mastercard():
    assert luhn_sum("5555555555554444") == 60


def test_luhn_sum_of_an_amex():
    assert luhn_sum("378282246310005") == 60


def test_luhn_sum_of_the_classic_example():
    assert luhn_sum("79927398713") == 70


def test_luhn_sum_changes_by_one_when_the_last_digit_changes():
    assert luhn_sum("4111111111111112") == 31


def test_luhn_sum_of_empty_raises():
    with pytest.raises(CardError, match="is empty"):
        luhn_sum("")


def test_luhn_valid_accepts_a_real_number():
    assert luhn_valid("4111111111111111") is True


def test_luhn_valid_rejects_one_changed_digit():
    assert luhn_valid("4111111111111112") is False


def test_luhn_valid_ignores_separators():
    assert luhn_valid("4111 1111-1111.1111") is True


def test_luhn_valid_of_empty_is_false_not_an_error():
    assert luhn_valid("") is False


def test_luhn_valid_of_letters_is_false_not_an_error():
    assert luhn_valid("abcd") is False


def test_luhn_valid_accepts_a_number_of_no_brand():
    # the checksum alone proves almost nothing
    assert luhn_valid("79927398713") is True


# --------------------------------------------------------------------------- #
# Check digit
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("partial, expected", [
    ("411111111111111", "1"),
    ("555555555555444", "4"),
    ("37828224631000", "5"),
    ("601111111111111", "7"),
    ("3056930902590", "4"),
    ("353011133330000", "0"),
])
def test_check_digit_matches_the_published_digit(partial, expected):
    assert check_digit(partial) == expected


@pytest.mark.parametrize("partial", ["4", "1234", "7992739871",
                                     "37828224631000"])
def test_check_digit_completes_a_valid_number(partial):
    assert luhn_valid(partial + check_digit(partial)) is True


def test_check_digit_of_empty_raises():
    with pytest.raises(CardError, match="is empty"):
        check_digit("")


def test_with_check_digit_appends_exactly_one_digit():
    completed = with_check_digit("411111111111111")
    assert completed == "4111111111111111"
    assert len(completed) == 16


def test_with_check_digit_leaves_the_prefix_intact():
    assert with_check_digit("37828224631000").startswith("37828224631000")


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def test_generate_sixteen_digits():
    assert generate("4111", 16) == "4111000000000008"


def test_generate_thirteen_digits():
    assert generate("4111", 13) == "4111000000001"


def test_generate_is_deterministic():
    assert generate("4111", 16) == generate("4111", 16)


def test_generate_different_lengths_differ():
    assert generate("4111", 16) != generate("4111", 13)


@pytest.mark.parametrize("length", [13, 15, 16, 19])
def test_generate_produces_a_luhn_valid_number(length):
    assert luhn_valid(generate("4111", length)) is True


def test_generate_keeps_the_prefix():
    assert generate("3782", 15).startswith("3782")


def test_generate_rejects_a_prefix_that_fills_the_length():
    with pytest.raises(CardError, match="already fills"):
        generate("4111111111111111", 16)


def test_generate_rejects_a_length_below_two():
    with pytest.raises(CardError, match="at least 2"):
        generate("4", 1)


def test_generate_rejects_a_non_integer_length():
    with pytest.raises(CardError, match="must be an integer"):
        generate("4111", "16")                            # type: ignore[arg-type]


def test_generate_rejects_a_boolean_length():
    with pytest.raises(CardError, match="must be an integer"):
        generate("4111", True)                            # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Brand
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("number, expected", [
    ("4111111111111111", "Visa"),
    ("4111111111111", "Visa"),
    ("5555555555554444", "Mastercard"),
    ("5100000000000000", "Mastercard"),
    ("2221000000000009", "Mastercard"),
    ("2720000000000000", "Mastercard"),
    ("378282246310005", "Amex"),
    ("340000000000000", "Amex"),
    ("6011111111111117", "Discover"),
    ("6500000000000000", "Discover"),
    ("6440000000000000", "Discover"),
    ("30569309025904", "Diners"),
    ("36000000000000", "Diners"),
    ("3530111333300000", "JCB"),
    ("3589000000000000", "JCB"),
])
def test_brand_classifies(number, expected):
    assert brand(number) == expected


@pytest.mark.parametrize("number", ["", "123", "abcdef", "2721000000000000",
                                    "3527000000000000", "9999999999999999"])
def test_brand_returns_unknown_when_no_rule_fits(number):
    assert brand(number) == "Unknown"


def test_brand_ignores_separators():
    assert brand("4111 1111 1111 1111") == "Visa"


def test_brand_of_a_two_digit_prefix_does_not_crash():
    assert brand("41") == "Visa"
    assert brand("4") == "Visa"


def test_brand_of_empty_is_unknown_not_an_error():
    assert brand("") == "Unknown"


def test_brands_tuple_is_documented():
    assert BRANDS[0] == "Visa" and BRANDS[-1] == "Unknown"


# --------------------------------------------------------------------------- #
# Length policy
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("number", ["4111111111111111", "4111111111111",
                                    "378282246310005", "30569309025904",
                                    "6011111111111117", "3530111333300000"])
def test_length_ok_accepts_allowed_lengths(number):
    assert length_ok(number) is True


@pytest.mark.parametrize("number", ["555555555555444",     # 15-digit MC
                                    "3782822463100050",    # 16-digit Amex
                                    "3056930902590",       # 13-digit Diners
                                    "411",                 # 3-digit Visa
                                    "123"])
def test_length_ok_rejects_disallowed_lengths(number):
    assert length_ok(number) is False


def test_length_ok_of_empty_is_false():
    assert length_ok("") is False


def test_lengths_table_covers_every_brand():
    assert set(LENGTHS) == set(BRANDS)


# --------------------------------------------------------------------------- #
# Formatting and masking
# --------------------------------------------------------------------------- #
def test_format_number_of_an_amex_uses_four_six_five():
    assert format_number("378282246310005") == "3782 822463 10005"


def test_format_number_of_a_diners_uses_four_six_four():
    assert format_number("30569309025904") == "3056 930902 5904"


def test_format_number_of_a_sixteen_digit_card_uses_fours():
    assert format_number("4111111111111111") == "4111 1111 1111 1111"


def test_format_number_of_a_thirteen_digit_card():
    assert format_number("4111111111111") == "4111 1111 1111 1"


def test_format_number_ignores_separators():
    assert format_number("4111-1111 1111.1111") == "4111 1111 1111 1111"


def test_format_number_of_empty_raises():
    with pytest.raises(CardError):
        format_number("")


def test_mask_of_a_sixteen_digit_card():
    assert mask("4111111111111111") == "**** **** **** 1111"


def test_mask_of_an_amex_keeps_fifteen_positions():
    masked = mask("378282246310005")
    assert masked == "**** ****** *0005"
    assert len(masked.replace(" ", "")) == 15


def test_mask_of_a_diners_keeps_fourteen_positions():
    masked = mask("30569309025904")
    assert masked == "**** ****** 5904"
    assert len(masked.replace(" ", "")) == 14


def test_mask_of_a_short_number_reveals_nothing():
    assert mask("123") == "***"


def test_mask_of_four_digits_reveals_nothing():
    assert mask("1234") == "****"


def test_mask_of_five_digits():
    assert mask("12345") == "*234 5"


def test_mask_with_reveal_two():
    assert mask("4111111111111111", reveal=2) == "**** **** **** **11"


def test_mask_with_reveal_zero_reveals_nothing():
    assert mask("4111111111111111", reveal=0) == "**** **** **** ****"


def test_mask_rejects_a_negative_reveal():
    with pytest.raises(CardError, match="must not be negative"):
        mask("4111111111111111", reveal=-1)


def test_mask_rejects_a_reveal_above_the_maximum():
    with pytest.raises(CardError, match=f"at most {MAX_REVEAL}"):
        mask("4111111111111111", reveal=MAX_REVEAL + 1)


def test_mask_rejects_a_non_integer_reveal():
    with pytest.raises(CardError, match="must be an integer"):
        mask("4111111111111111", reveal="4")              # type: ignore[arg-type]


def test_mask_rejects_empty_input():
    with pytest.raises(CardError, match="is empty"):
        mask("")


@pytest.mark.parametrize("number", ["4111111111111111", "378282246310005",
                                    "30569309025904", "6011111111111117",
                                    "3530111333300000"])
def test_mask_never_contains_the_whole_number(number):
    assert digits(number) not in mask(number)


@pytest.mark.parametrize("number", ["4111111111111111", "378282246310005",
                                    "30569309025904"])
def test_mask_shows_exactly_four_digits(number):
    assert sum(ch.isdigit() for ch in mask(number)) == 4


def test_default_reveal_is_four():
    assert DEFAULT_REVEAL == 4


def test_legacy_mask_reproduces_the_original_output():
    assert legacy_mask("4111111111111111") == "XXXX XXXX XXXX XXXX 1111"


def test_legacy_mask_leaks_a_short_number():
    assert legacy_mask("123") == "XXXX XXXX XXXX XXXX 123"


# --------------------------------------------------------------------------- #
# check
# --------------------------------------------------------------------------- #
def test_check_of_a_valid_visa():
    info = check("4111111111111111")
    assert info["brand"] == "Visa"
    assert info["length"] == 16
    assert info["luhn"] is True
    assert info["length_ok"] is True
    assert info["valid"] is True


def test_check_of_a_failed_checksum():
    info = check("4111111111111112")
    assert info["luhn"] is False
    assert info["valid"] is False


def test_check_of_a_luhn_valid_unknown_number():
    info = check("79927398713")
    assert info["luhn"] is True
    assert info["brand"] == "Unknown"
    assert info["length_ok"] is False
    assert info["valid"] is False


def test_check_of_a_wrong_length():
    info = check("3782822463100050")
    assert info["brand"] == "Amex"
    assert info["length"] == 16
    assert info["length_ok"] is False
    assert info["valid"] is False


def test_check_reports_the_normalised_digits():
    assert check("4111 1111 1111 1111")["digits"] == "4111111111111111"


def test_check_carries_the_formatted_and_masked_forms():
    info = check("378282246310005")
    assert info["formatted"] == "3782 822463 10005"
    assert info["masked"] == "**** ****** *0005"


def test_check_keys_are_stable():
    assert set(check("4111111111111111")) == {
        "digits", "length", "brand", "luhn", "length_ok", "valid",
        "formatted", "masked"}


def test_check_rejects_empty():
    with pytest.raises(CardError, match="is empty"):
        check("")


# --------------------------------------------------------------------------- #
# describe
# --------------------------------------------------------------------------- #
def test_describe_of_a_valid_card_ends_with_valid():
    assert describe("4111111111111111").endswith("valid")


def test_describe_names_a_failed_checksum():
    assert "Luhn checksum failed" in describe("4111111111111112")


def test_describe_names_an_unknown_brand():
    assert "unknown brand" in describe("79927398713")


def test_describe_names_a_bad_length():
    assert "not allowed" in describe("555555555555444")


def test_describe_never_prints_the_full_number():
    text = describe("4111111111111111")
    assert "4111111111111111" not in text
    assert "**** **** **** 1111" in text


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
def test_data_file_exists():
    assert DATA.is_file()


def test_load_cards_reads_every_row():
    assert len(load_cards()) == 17


def test_load_cards_brand_claims_agree():
    assert all(record["brand_agrees"] for record in load_cards())


def test_load_cards_luhn_claims_agree():
    assert all(record["luhn_agrees"] for record in load_cards())


def test_load_cards_counts_nine_valid():
    assert sum(1 for record in load_cards() if record["valid"]) == 9


def test_load_cards_includes_every_brand():
    found = {record["brand"] for record in load_cards()}
    assert found == {"Visa", "Mastercard", "Amex", "Discover", "Diners",
                     "JCB", "Unknown"}


def test_load_cards_keeps_the_notes():
    notes = [record["note"] for record in load_cards()]
    assert any("legacy leak" in note for note in notes)


def test_load_cards_of_a_missing_file(tmp_path):
    with pytest.raises(CardError, match="not found"):
        load_cards(tmp_path / "nope.csv")


def test_load_cards_rejects_a_short_row(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("number,brand,luhn,note\n4111,Visa,yes\n", encoding="utf-8")
    with pytest.raises(CardError, match="line 2"):
        load_cards(path)


def test_load_cards_rejects_a_wrong_header(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("4111111111111111,Visa,yes,note\n", encoding="utf-8")
    with pytest.raises(CardError, match="unexpected header"):
        load_cards(path)


def test_load_cards_rejects_a_header_only_file(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("number,brand,luhn,note\n", encoding="utf-8")
    with pytest.raises(CardError, match="no cards"):
        load_cards(path)


def test_load_cards_skips_comments_and_blank_lines(tmp_path):
    path = tmp_path / "ok.csv"
    path.write_text("# a comment\n\nnumber,brand,luhn,note\n"
                    "4111111111111111,Visa,yes,one\n", encoding="utf-8")
    records = load_cards(path)
    assert len(records) == 1 and records[0]["valid"] is True


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


def test_demo_never_prints_a_full_card_number(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "4111111111111111" not in out


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_the_bundled_cards(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "17 card(s): 9 valid, 8 rejected" in out
    assert "**** **** **** 1111" in out


def test_cli_list_hides_full_numbers(capsys):
    assert cli.main([]) == 0
    assert "4111111111111111" not in capsys.readouterr().out


def test_cli_check_valid(capsys):
    assert cli.main(["--check", "4111111111111111"]) == 0
    out = capsys.readouterr().out
    assert "valid" in out
    assert "luhn sum   30" in out


def test_cli_check_invalid(capsys):
    assert cli.main(["--check", "4111111111111112"]) == 0
    out = capsys.readouterr().out
    assert "Luhn checksum failed" in out
    assert "luhn sum   31" in out


def test_cli_check_with_separators(capsys):
    assert cli.main(["--check", "4111 1111 1111 1111"]) == 0
    assert "valid" in capsys.readouterr().out


def test_cli_check_rejects_letters(capsys):
    assert cli.main(["--check", "4111-abcd"]) == 2
    assert "non-digits" in capsys.readouterr().err


def test_cli_mask(capsys):
    assert cli.main(["--mask", "378282246310005"]) == 0
    out = capsys.readouterr().out
    assert "**** ****** *0005" in out
    assert "15 digit(s), last 4 shown" in out


def test_cli_mask_with_reveal(capsys):
    assert cli.main(["--mask", "4111111111111111", "--reveal", "2"]) == 0
    assert "**** **** **** **11" in capsys.readouterr().out


def test_cli_mask_reveal_out_of_range(capsys):
    assert cli.main(["--mask", "4111111111111111", "--reveal", "9"]) == 2
    assert "at most 6" in capsys.readouterr().err


def test_cli_generate(capsys):
    assert cli.main(["--generate", "4111", "16"]) == 0
    out = capsys.readouterr().out
    assert "4111000000000008" in out
    assert "Luhn yes" in out


def test_cli_generate_with_a_full_prefix_exits_two(capsys):
    assert cli.main(["--generate", "4111111111111111", "16"]) == 2
    assert "already fills" in capsys.readouterr().err


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.csv"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_json_list(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "list"
    assert payload["count"] == 17
    assert payload["valid"] == 9 and payload["invalid"] == 8


def test_cli_json_check(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--check", "4111111111111111", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["luhn_sum"] == 30
    assert payload["brand"] == "Visa"


def test_cli_json_generate(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--generate", "4111", "13", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["number"] == "4111000000001"
    assert payload["length"] == 13


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--check", "4111111111111111", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_custom_file(tmp_path, capsys):
    path = tmp_path / "one.csv"
    path.write_text("number,brand,luhn,note\n"
                    "378282246310005,Amex,yes,one\n", encoding="utf-8")
    assert cli.main(["--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "1 card(s): 1 valid, 0 rejected" in out


def test_module_exposes_its_data_path():
    assert card.DATA_FILE.name == "cards.csv"
