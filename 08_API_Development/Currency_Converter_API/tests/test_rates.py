"""Tests for Currency_Converter_API: a rate is a ratio with a direction and a day,
converted in integers only, never at par."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                           # noqa: E402
import rates as module                                       # noqa: E402
from rates import (                                         # noqa: E402
    AMOUNTS_FILE,
    FRESH_DAYS,
    LEGACY_CONVERT,
    LEGACY_LOOKUP,
    QUOTE_FILE,
    READ_ON,
    Rate,
    RateError,
    Quote,
    Sheet,
    audit,
    convert,
    divide_half_up,
    legacy_convert,
    legacy_rate,
    legacy_table,
    money_text,
    parse_amounts,
    parse_sheet,
    problems,
    read_amounts,
    read_sheet,
    run_demo,
)

ON = date.fromisoformat(READ_ON)
QUOTE_TEXT = QUOTE_FILE.read_text(encoding="utf-8")
AMOUNTS_TEXT = AMOUNTS_FILE.read_text(encoding="utf-8")


def a_sheet() -> Sheet:
    return read_sheet()


def a_rate(base: str = "USD", quote: str = "EUR", numerator: int = 92,
           denominator: int = 100) -> Rate:
    return Rate(base, quote, numerator, denominator)


def raw_rate(numerator) -> Rate:
    """A Rate with the validation bypassed, so an audit can disagree."""
    rate = object.__new__(Rate)
    for name, value in (("base", "USD"), ("quote", "EUR"),
                        ("numerator", numerator), ("denominator", 100)):
        object.__setattr__(rate, name, value)
    return rate


class LyingPair(Rate):
    """A rate that prints itself as a different pair."""

    def text(self) -> str:
        return "USD/GBP = 79/100"


class DriftingInverse(Rate):
    """A rate whose inverse is not its own inverse."""

    def inverse(self) -> Rate:
        return Rate(self.quote, self.base, self.denominator + 1,
                    self.numerator)


def a_quote(day=None, base: str = "USD",
            rates: tuple[Rate, ...] = ()) -> Quote:
    return Quote(day if day is not None else date(2026, 11, 14), base,
                 rates if rates else (a_rate(),))


def a_sheet_from(quote: Quote,
                 exponents: tuple[tuple[str, int], ...] = (("USD", 2),
                                                          ("EUR", 2))) -> Sheet:
    return Sheet(quote, exponents)


# --------------------------------------------------------------------------- #
# Integer arithmetic
# --------------------------------------------------------------------------- #
def test_half_up_rounds_a_half_away_from_zero():
    assert divide_half_up(5, 2) == 3


def test_half_up_rounds_a_negative_half_away_from_zero():
    assert divide_half_up(-5, 2) == -3


def test_half_up_leaves_an_exact_division_alone():
    assert divide_half_up(9200, 100) == 92


def test_half_up_of_zero_is_zero():
    assert divide_half_up(0, 3) == 0


def test_round_is_not_half_up():
    assert round(2.5) == 2 and divide_half_up(5, 2) == 3


def test_round_of_2_675_is_below_the_tie():
    assert round(2.675, 2) == 2.67


def test_half_up_of_2_675_is_2_68():
    assert divide_half_up(2_675, 10) == 268


def test_a_divisor_of_zero_is_refused():
    with pytest.raises(RateError, match="must be positive"):
        divide_half_up(1, 0)


def test_a_numerator_that_is_not_whole_is_refused():
    with pytest.raises(RateError, match="a numerator is a whole"):
        divide_half_up(0.5, 2)


def test_a_bool_numerator_is_refused():
    with pytest.raises(RateError, match="a numerator is a whole"):
        divide_half_up(True, 2)


def test_a_divisor_that_is_not_whole_is_refused():
    with pytest.raises(RateError, match="a divisor is a whole"):
        divide_half_up(4, 2.0)


# --------------------------------------------------------------------------- #
# A rate
# --------------------------------------------------------------------------- #
def test_a_rate_holds_two_codes_and_two_numbers():
    rate = a_rate()
    assert (rate.base, rate.quote, rate.numerator, rate.denominator) == \
        ("USD", "EUR", 92, 100)


def test_a_rate_prints_its_ratio_exactly():
    assert a_rate().text() == "USD/EUR = 92/100"


def test_a_rates_pair_is_its_two_codes():
    assert a_rate().pair() == "USD/EUR"


def test_str_of_a_rate_is_its_ratio():
    assert str(a_rate()) == "USD/EUR = 92/100"


def test_a_rate_prints_as_a_decimal():
    assert a_rate().decimal_text() == "0.920000"


def test_a_rate_of_one_hundred_and_fifty_one_prints_as_a_decimal():
    assert a_rate(numerator=151, denominator=1).decimal_text() == "151.000000"


def test_a_third_prints_to_six_places():
    assert Rate("USD", "EUR", 1, 3).decimal_text() == "0.333333"


def test_a_rate_is_equal_to_itself():
    assert a_rate() == a_rate()


def test_two_directions_of_one_ratio_are_not_equal():
    assert a_rate() != a_rate().inverse()


def test_the_inverse_swaps_the_pair_and_the_numbers():
    inverse = a_rate().inverse()
    assert (inverse.base, inverse.quote, inverse.numerator,
            inverse.denominator) == ("EUR", "USD", 100, 92)


def test_inverting_twice_gives_the_rate_back():
    assert a_rate().inverse().inverse() == a_rate()


def test_a_rate_needs_two_currencies():
    with pytest.raises(RateError, match="needs two currencies"):
        Rate("USD", "USD", 92, 100)


def test_a_lower_case_code_is_refused():
    with pytest.raises(RateError, match="three upper-case letters"):
        Rate("usd", "EUR", 92, 100)


def test_a_two_letter_code_is_refused():
    with pytest.raises(RateError, match="three upper-case letters"):
        Rate("US", "EUR", 92, 100)


def test_a_four_letter_code_is_refused():
    with pytest.raises(RateError, match="three upper-case letters"):
        Rate("USDX", "EUR", 92, 100)


def test_a_code_that_is_not_text_is_refused():
    with pytest.raises(RateError, match="three letters"):
        Rate(840, "EUR", 92, 100)


def test_a_zero_rate_is_refused():
    with pytest.raises(RateError, match="has no inverse"):
        Rate("USD", "EUR", 0, 100)


def test_a_negative_rate_is_refused():
    with pytest.raises(RateError, match="must be positive"):
        Rate("USD", "EUR", -92, 100)


def test_a_zero_denominator_is_refused():
    with pytest.raises(RateError, match="denominator must be positive"):
        Rate("USD", "EUR", 92, 0)


def test_a_float_numerator_is_refused():
    with pytest.raises(RateError, match="a rate numerator is a whole number"):
        Rate("USD", "EUR", 0.92, 100)


# --------------------------------------------------------------------------- #
# Converting
# --------------------------------------------------------------------------- #
def test_a_hundred_dollars_is_ninety_two_euro():
    assert convert(a_rate(), 10_000, 2, 2) == 9_200


def test_the_inverse_takes_ninety_two_euro_back_to_a_hundred_dollars():
    assert convert(a_rate().inverse(), 9_200, 2, 2) == 10_000


def test_a_yen_rate_needs_the_exponent():
    assert convert(a_rate(numerator=151, denominator=1), 10_000, 2, 0) == 15_100


def test_a_yen_rate_without_the_exponent_would_be_a_hundredfold_out():
    assert convert(a_rate(numerator=151, denominator=1), 10_000, 2, 2) == \
        1_510_000


def test_a_higher_quote_exponent_scales_the_ratio_up():
    assert convert(a_rate(), 100, 2, 4) == 9_200


def test_a_conversion_rounds_half_up():
    assert convert(a_rate(), 6, 2, 2) == 6


def test_a_conversion_of_nothing_is_nothing():
    assert convert(a_rate(), 0, 2, 2) == 0


def test_a_negative_amount_converts_symmetrically():
    assert convert(a_rate(), -10_000, 2, 2) == -9_200


def test_a_conversion_needs_a_rate():
    with pytest.raises(RateError, match="needs a rate"):
        convert(0.92, 10_000, 2, 2)


def test_a_conversion_needs_a_whole_amount():
    with pytest.raises(RateError, match="an amount is a whole number"):
        convert(a_rate(), 100.5, 2, 2)


def test_a_conversion_needs_whole_exponents():
    with pytest.raises(RateError, match="an exponent is a whole number"):
        convert(a_rate(), 100, 2, "2")


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #
def test_two_places_print_a_dollar_amount():
    assert money_text(10_000, "USD", 2) == "100.00 USD"


def test_no_places_print_a_yen_amount():
    assert money_text(15_100, "JPY", 0) == "15,100 JPY"


def test_a_thousands_separator_appears_above_a_thousand():
    assert money_text(123_456_789, "USD", 2) == "1,234,567.89 USD"


def test_a_negative_amount_keeps_its_sign():
    assert money_text(-8_464, "USD", 2) == "-84.64 USD"


def test_three_places_print_a_dinar_amount():
    assert money_text(1_234_567, "KWD", 3) == "1,234.567 KWD"


def test_a_fraction_of_a_minor_unit_is_kept_visible():
    assert money_text(5, "USD", 2) == "0.05 USD"


def test_money_needs_a_whole_amount():
    with pytest.raises(RateError, match="an amount is a whole number"):
        money_text(100.0, "USD", 2)


def test_money_needs_a_code():
    with pytest.raises(RateError, match="three upper-case letters"):
        money_text(100, "usd", 2)


def test_money_refuses_five_decimal_places():
    with pytest.raises(RateError, match="cannot have 5 decimal places"):
        money_text(100, "USD", 5)


def test_money_refuses_a_negative_exponent():
    with pytest.raises(RateError, match="cannot have -1 decimal places"):
        money_text(100, "USD", -1)


# --------------------------------------------------------------------------- #
# A quote
# --------------------------------------------------------------------------- #
def test_a_quote_names_its_day_and_base():
    quote = a_quote()
    assert quote.as_of == date(2026, 11, 14) and quote.base == "USD"


def test_a_quote_holds_its_rates():
    assert len(a_sheet()) == 3


def test_a_quote_needs_a_day():
    with pytest.raises(RateError, match="names a day"):
        Quote("2026-11-14", "USD", (a_rate(),))


def test_a_quote_needs_at_least_one_rate():
    with pytest.raises(RateError, match="at least one rate"):
        Quote(date(2026, 11, 14), "USD", ())


def test_a_quote_refuses_a_bad_base():
    with pytest.raises(RateError, match="three upper-case letters"):
        Quote(date(2026, 11, 14), "usd", (a_rate(),))


def test_a_quote_refuses_two_rates_for_one_currency():
    with pytest.raises(RateError, match="share a quote currency"):
        Quote(date(2026, 11, 14), "USD", (a_rate(), a_rate()))


def test_a_quote_refuses_a_rate_from_another_base():
    with pytest.raises(RateError, match="based on USD, but it holds a rate"):
        Quote(date(2026, 11, 14), "USD", (Rate("EUR", "GBP", 79, 100),))


def test_for_currency_finds_a_rate():
    assert a_sheet().quote.for_currency("EUR") == a_rate()


def test_for_currency_finds_the_yen_rate():
    assert a_sheet().quote.for_currency("JPY").numerator == 151


def test_for_currency_refuses_the_base_currency():
    with pytest.raises(RateError, match="is the base currency"):
        a_sheet().quote.for_currency("USD")


def test_for_currency_refuses_a_currency_the_sheet_does_not_hold():
    with pytest.raises(RateError, match="holds no rate for CHF"):
        a_sheet().quote.for_currency("CHF")


def test_the_refusal_lists_the_currencies_it_does_hold():
    with pytest.raises(RateError, match="it holds EUR, GBP, JPY"):
        a_sheet().quote.for_currency("CHF")


def test_the_age_of_the_quote_is_counted_in_days():
    assert a_sheet().quote.age_days(ON) == 1


def test_the_age_of_a_quote_read_later():
    assert a_sheet().quote.age_days(date(2026, 12, 20)) == 36


def test_a_quote_has_no_age_before_it_was_quoted():
    with pytest.raises(RateError, match="has no age"):
        a_sheet().quote.age_days(date(2026, 11, 1))


def test_an_age_needs_a_day():
    with pytest.raises(RateError, match="a day is needed"):
        a_sheet().quote.age_days("2026-11-15")


def test_a_quote_read_on_its_limit_day_is_fresh():
    assert a_sheet().quote.is_stale(date(2026, 11, 21), FRESH_DAYS) is False


def test_a_quote_read_one_day_later_is_stale():
    assert a_sheet().quote.is_stale(date(2026, 11, 22), FRESH_DAYS) is True


def test_a_negative_limit_is_refused():
    with pytest.raises(RateError, match="a limit is a number of days"):
        a_sheet().quote.is_stale(ON, -1)


def test_a_quote_line_shows_the_pair_the_decimal_and_the_ratio():
    line = a_sheet().quote.lines()[0]
    assert line.startswith("USD/EUR")
    assert "0.920000" in line and "USD/EUR = 92/100" in line


# --------------------------------------------------------------------------- #
# A sheet
# --------------------------------------------------------------------------- #
def test_a_sheet_gives_each_currency_its_exponent():
    sheet = a_sheet()
    assert sheet.exponent("USD") == 2 and sheet.exponent("JPY") == 0


def test_a_sheet_refuses_a_currency_with_no_exponent():
    with pytest.raises(RateError, match="no exponent for CHF"):
        a_sheet().exponent("CHF")


def test_a_sheet_needs_a_quote():
    with pytest.raises(RateError, match="holds a quote"):
        Sheet(date(2026, 11, 14), (("USD", 2),))


def test_a_sheet_needs_an_exponent():
    with pytest.raises(RateError, match="exponent of every currency"):
        Sheet(a_quote(), ())


def test_a_sheet_refuses_two_exponents_for_one_code():
    with pytest.raises(RateError, match="share an exponent"):
        Sheet(a_quote(), (("USD", 2), ("USD", 2)))


def test_a_sheet_refuses_a_bad_exponent():
    with pytest.raises(RateError, match="cannot have 7 decimal places"):
        Sheet(a_quote(), (("USD", 7), ("EUR", 2)))


def test_a_sheet_needs_an_exponent_for_its_base():
    with pytest.raises(RateError, match="no exponent for its base"):
        Sheet(a_quote(), (("EUR", 2),))


def test_a_sheet_prints_an_amount():
    assert a_sheet().money(10_000, "USD") == "100.00 USD"


def test_a_sheet_converts_to_euro():
    assert a_sheet().convert(10_000, "EUR") == 9_200


def test_a_sheet_converts_to_yen():
    assert a_sheet().convert(10_000, "JPY") == 15_100


def test_a_sheet_converts_back_from_euro():
    assert a_sheet().convert_back(9_200, "EUR") == 10_000


def test_a_sheet_converts_back_from_yen():
    assert a_sheet().convert_back(15_100, "JPY") == 10_000


def test_a_sheet_converts_its_own_base_to_itself_never():
    with pytest.raises(RateError, match="is the base currency"):
        a_sheet().convert(10_000, "USD")


def test_the_drift_of_a_clean_amount_is_zero():
    assert a_sheet().drift(10_000, "EUR") == 0


def test_the_drift_of_six_cents_is_one():
    assert a_sheet().drift(6, "EUR") == 1


def test_a_sheet_reports_a_fresh_quote():
    assert a_sheet().fresh(ON).startswith("fresh")


def test_a_sheet_reports_a_stale_quote_with_its_age():
    line = a_sheet().fresh(date(2026, 12, 20))
    assert line.startswith("STALE") and "36 day(s) old" in line


def test_a_sheet_counts_its_rates():
    assert len(a_sheet()) == 3


# --------------------------------------------------------------------------- #
# The legacy pair
# --------------------------------------------------------------------------- #
def test_the_legacy_conversion_forward_is_right():
    assert legacy_convert(100.00, 0.92) == 92.0


def test_the_legacy_conversion_backwards_loses_money():
    assert legacy_convert(92.00, 0.92) == 84.64


def test_the_legacy_conversion_of_par_is_the_same_amount():
    assert legacy_convert(100.00, 1.0) == 100.00


def test_the_legacy_conversion_uses_bankers_rounding():
    assert legacy_convert(2.675, 1.0) == 2.67


def test_the_legacy_conversion_rounds_a_half_to_even():
    assert legacy_convert(0.125, 1.0) == 0.12


def test_half_up_of_the_same_eighth_is_up():
    assert divide_half_up(125, 10) == 13


def test_the_legacy_lookup_finds_a_rate_it_holds():
    assert legacy_rate({"EUR": 0.92}, "EUR") == 0.92


def test_the_legacy_lookup_answers_par_for_an_unknown_currency():
    assert legacy_rate({"EUR": 0.92}, "CHF") == 1.0


def test_the_legacy_table_is_one_float_per_currency():
    table = legacy_table(a_sheet())
    assert table == {"EUR": 0.92, "GBP": 0.79, "JPY": 151.0}


def test_the_legacy_lines_are_pinned():
    assert LEGACY_CONVERT == "return round(amount * rate, 2)"
    assert LEGACY_LOOKUP == "return rates.get(code, 1.0)"


# --------------------------------------------------------------------------- #
# Reading the sheet
# --------------------------------------------------------------------------- #
def test_parse_sheet_reads_the_bundled_text():
    sheet = parse_sheet(QUOTE_TEXT)
    assert sheet.quote.as_of == date(2026, 11, 14) and len(sheet) == 3


def test_parse_sheet_reads_four_exponents():
    assert len(parse_sheet(QUOTE_TEXT).exponents) == 4


def test_parse_sheet_skips_a_comment():
    text = ("as_of 2026-01-01\nexp USD 2\nexp EUR 2\n; note\nbase USD\n"
            "rate EUR 1 1\n")
    assert len(parse_sheet(text)) == 1


def test_parse_sheet_skips_a_blank_line():
    text = ("\nas_of 2026-01-01\nexp USD 2\nexp EUR 2\n\nbase USD\n"
            "rate EUR 1 1\n\n")
    assert len(parse_sheet(text)) == 1


def test_parse_sheet_reads_windows_line_endings():
    text = ("as_of 2026-01-01\r\nexp USD 2\r\nexp EUR 2\r\nbase USD\r\n"
            "rate EUR 1 1\r\n")
    assert len(parse_sheet(text)) == 1


def test_parse_sheet_refuses_a_sheet_with_no_day():
    with pytest.raises(RateError, match="names no day"):
        parse_sheet("base USD\nrate EUR 1 1\n")


def test_parse_sheet_refuses_a_sheet_with_no_base():
    with pytest.raises(RateError, match="names no base"):
        parse_sheet("as_of 2026-01-01\n")


def test_parse_sheet_refuses_a_day_that_is_not_a_day():
    with pytest.raises(RateError, match="is not a day written"):
        parse_sheet("as_of yesterday\nbase USD\n")


def test_parse_sheet_refuses_two_fields_after_as_of():
    with pytest.raises(RateError, match="as_of takes one day"):
        parse_sheet("as_of 2026-01-01 now\n")


def test_parse_sheet_refuses_two_fields_after_base():
    with pytest.raises(RateError, match="base takes one currency"):
        parse_sheet("base USD EUR\n")


def test_parse_sheet_refuses_a_short_exp_line():
    with pytest.raises(RateError, match="exp takes a code"):
        parse_sheet("exp USD\n")


def test_parse_sheet_refuses_a_short_rate_line():
    with pytest.raises(RateError, match="rate takes a code"):
        parse_sheet("as_of 2026-01-01\nbase USD\nrate EUR 92\n")


def test_parse_sheet_refuses_a_rate_of_text():
    with pytest.raises(RateError, match="a rate is two whole numbers"):
        parse_sheet("as_of 2026-01-01\nbase USD\nrate EUR 9x 100\n")


def test_parse_sheet_refuses_a_rate_before_the_base():
    with pytest.raises(RateError, match="a rate comes after the base"):
        parse_sheet("as_of 2026-01-01\nrate EUR 92 100\n")


def test_parse_sheet_refuses_an_unknown_line():
    with pytest.raises(RateError, match="is not as_of, base, exp or rate"):
        parse_sheet("as_of 2026-01-01\nsource EUR\n")


def test_parse_sheet_refuses_a_zero_rate():
    with pytest.raises(RateError, match="has no inverse"):
        parse_sheet("as_of 2026-01-01\nbase USD\nrate EUR 0 100\n")


def test_a_missing_sheet_is_refused(tmp_path):
    with pytest.raises(RateError, match="file not found"):
        module.read_sheet(tmp_path / "nope.txt")


def test_read_sheet_accepts_its_own_file(tmp_path):
    path = tmp_path / "quote.txt"
    path.write_bytes(b"as_of 2026-01-01\nbase USD\nexp USD 2\nexp EUR 2\n"
                     b"rate EUR 1 2\n")
    assert read_sheet(path).convert(100, "EUR") == 50


# --------------------------------------------------------------------------- #
# Reading the amounts
# --------------------------------------------------------------------------- #
def test_parse_amounts_reads_a_code_and_a_number():
    assert parse_amounts("EUR 10000\n") == ((10_000, "EUR"),)


def test_parse_amounts_reads_two_amounts():
    assert len(parse_amounts("EUR 1\nGBP 2\n")) == 2


def test_parse_amounts_skips_a_comment():
    assert len(parse_amounts("; note\nEUR 1\n")) == 1


def test_parse_amounts_skips_a_blank_line():
    assert len(parse_amounts("\nEUR 1\n\n")) == 1


def test_parse_amounts_reads_windows_line_endings():
    assert len(parse_amounts("EUR 1\r\nGBP 2\r\n")) == 2


def test_parse_amounts_refuses_one_field():
    with pytest.raises(RateError, match="an amount is a code and a whole"):
        parse_amounts("EUR\n")


def test_parse_amounts_refuses_an_amount_that_is_not_a_number():
    with pytest.raises(RateError, match="is not a whole number"):
        parse_amounts("EUR 1.00\n")


def test_parse_amounts_refuses_a_negative_amount():
    with pytest.raises(RateError, match="cannot be negative"):
        parse_amounts("EUR -1\n")


def test_parse_amounts_refuses_a_bad_code():
    with pytest.raises(RateError, match="three upper-case letters"):
        parse_amounts("eur 1\n")


def test_parse_amounts_refuses_a_list_with_no_amounts():
    with pytest.raises(RateError, match="holds no amounts"):
        parse_amounts("; nothing\n")


def test_a_missing_amount_list_is_refused(tmp_path):
    with pytest.raises(RateError, match="file not found"):
        module.read_amounts(tmp_path / "nope.txt")


def test_the_bundled_amounts_hold_four():
    assert len(read_amounts(AMOUNTS_FILE)) == 4


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every rate is a ratio of two positive whole numbers",
    "every rate prints and reads back to the same ratio",
    "inverting a rate twice gives the rate back",
    "the legacy conversion in the wrong direction loses money",
    "the legacy lookup answers par for an unknown currency",
    "round() is not half-up and the sheet is",
    "a larger amount never converts to a smaller one",
    "a quote older than its limit is stale, with its age",
    "every quote names the day it applies to",
]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(a_sheet(), ON)] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_sheet():
    assert problems(audit(a_sheet(), ON)) == []


def test_the_audit_is_repeatable():
    assert audit(a_sheet(), ON) == audit(a_sheet(), ON)


def test_the_audit_catches_a_fractional_rate():
    sheet = a_sheet_from(a_quote(rates=(raw_rate(0.92),)))
    assert CHECK_NAMES[0] in problems(audit(sheet, ON))


def test_the_audit_does_not_raise_on_a_broken_rate():
    sheet = a_sheet_from(a_quote(rates=(raw_rate("x"),)))
    assert len(audit(sheet, ON)) == 9


def test_the_audit_catches_a_rate_that_prints_another_pair():
    sheet = a_sheet_from(a_quote(rates=(LyingPair("USD", "EUR", 92, 100),)))
    assert CHECK_NAMES[1] in problems(audit(sheet, ON))


def test_the_audit_catches_an_inverse_that_is_not_its_own_inverse():
    sheet = a_sheet_from(a_quote(rates=(DriftingInverse("USD", "EUR", 92,
                                                        100),)))
    assert CHECK_NAMES[2] in problems(audit(sheet, ON))


def test_the_audit_catches_a_sheet_whose_direction_is_not_the_legacy_one():
    sheet = a_sheet_from(a_quote(rates=(a_rate(numerator=50),)))
    assert CHECK_NAMES[3] in problems(audit(sheet, ON))


def test_the_audit_catches_a_sheet_without_the_euro_rate():
    sheet = a_sheet_from(a_quote(rates=(a_rate(quote="GBP", numerator=79),)))
    assert CHECK_NAMES[4] in problems(audit(sheet, ON))


def test_the_audit_catches_a_rate_that_converts_backwards():
    sheet = a_sheet_from(a_quote(rates=(raw_rate(-92),)))
    assert CHECK_NAMES[6] in problems(audit(sheet, ON))


def test_the_audit_catches_a_quote_read_long_after_it_was_not_stale():
    assert CHECK_NAMES[7] in problems(
        audit(a_sheet(), date(2026, 12, 20)))


def test_the_audit_catches_a_quote_with_another_day():
    sheet = a_sheet_from(a_quote(day=date(2026, 1, 1)))
    assert CHECK_NAMES[8] in problems(audit(sheet, ON))


def test_eight_of_the_nine_checks_have_a_negative_control():
    """Check 6 pins round() and half-up against each other; it cannot be broken."""
    broken = [
        audit(a_sheet_from(a_quote(rates=(raw_rate(0.92),))), ON),
        audit(a_sheet_from(a_quote(rates=(LyingPair("USD", "EUR", 92, 100),))),
              ON),
        audit(a_sheet_from(a_quote(rates=(DriftingInverse("USD", "EUR", 92,
                                                         100),))), ON),
        audit(a_sheet_from(a_quote(rates=(a_rate(numerator=50),))), ON),
        audit(a_sheet_from(a_quote(rates=(a_rate(quote="GBP", numerator=79),))),
              ON),
        audit(a_sheet_from(a_quote(rates=(raw_rate(-92),))), ON),
        audit(a_sheet(), date(2026, 12, 20)),
        audit(a_sheet_from(a_quote(day=date(2026, 1, 1))), ON),
    ]
    caught = {name for checks in broken for name in problems(checks)}
    assert len(caught) == 8


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out and "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_legacy_pair(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "return round(amount * rate, 2)" in out
    assert "return rates.get(code, 1.0)" in out


def test_demo_shows_the_sheet(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "USD/EUR     0.920000   (USD/EUR = 92/100)" in out
    assert "USD 2  EUR 2  GBP 2  JPY 0" in out


def test_demo_shows_a_hundred_dollars_in_every_currency(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "92.00 EUR" in out and "15,100 JPY" in out


def test_demo_shows_the_legacy_wrong_direction(capsys):
    run_demo()
    assert "100.00 USD ->   92.00 EUR ->   84.64 USD" in \
        capsys.readouterr().out


def test_demo_shows_the_legacy_par_for_an_unknown_currency(capsys):
    run_demo()
    assert "100.00 CHF  (par, because get() defaults to 1.0)" in \
        capsys.readouterr().out


def test_demo_shows_both_roundings(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "round(2.675, 2)                = 2.67" in out
    assert "half-up of 2.675 to two places = 2.68" in out


def test_demo_shows_the_drift(capsys):
    run_demo()
    assert "6 USD cents ->   6 EUR cents ->   7 USD cents   drift +1" in \
        capsys.readouterr().out


def test_demo_shows_the_age_of_the_quote(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "fresh  quoted 2026-11-14, read 2026-11-15, 1 day(s) old" in out
    assert "STALE  quoted 2026-11-14, read 2026-12-20, 36 day(s) old" in out


def test_demo_shows_all_nine_checks(capsys):
    run_demo()
    assert "9/9 checks pass" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_reads_the_sheet(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "USD on 2026-11-14: 3 rate(s)" in out
    assert "15,100 JPY" in out


def test_cli_prints_the_legacy_conversion(capsys):
    assert cli.main([]) == 0
    assert "84.64 USD" in capsys.readouterr().out


def test_cli_converts_forward(capsys):
    assert cli.main(["--convert", "100.00 USD to EUR"]) == 0
    assert "100.00 USD -> 92.00 EUR" in capsys.readouterr().out


def test_cli_converts_backwards_through_the_inverse(capsys):
    assert cli.main(["--convert", "92.00 EUR to USD"]) == 0
    assert "92.00 EUR -> 100.00 USD" in capsys.readouterr().out


def test_cli_converts_yen_with_its_exponent(capsys):
    assert cli.main(["--convert", "15100 JPY to USD"]) == 0
    assert "15,100 JPY -> 100.00 USD" in capsys.readouterr().out


def test_cli_refuses_a_currency_it_does_not_hold(capsys):
    assert cli.main(["--convert", "100.00 USD to CHF"]) == 2
    assert "holds no rate for CHF" in capsys.readouterr().err


def test_cli_refuses_a_conversion_it_cannot_parse(capsys):
    assert cli.main(["--convert", "100 USD EUR"]) == 2
    assert "reads 'AMOUNT CODE to CODE'" in capsys.readouterr().err


def test_cli_refuses_an_amount_too_precise_for_the_currency(capsys):
    assert cli.main(["--convert", "1.234 USD to EUR"]) == 2
    assert "too precise" in capsys.readouterr().err


def test_cli_refuses_two_currencies_neither_of_which_is_the_base(capsys):
    assert cli.main(["--convert", "100.00 EUR to GBP"]) == 2
    assert "converts from USD or to it" in capsys.readouterr().err


def test_cli_refuses_the_base_to_itself(capsys):
    assert cli.main(["--convert", "100.00 USD to USD"]) == 2
    assert "needs no rate" in capsys.readouterr().err


def test_cli_refuses_a_day_it_cannot_read(capsys):
    assert cli.main(["--on", "yesterday"]) == 2
    assert "is not a day written YYYY-MM-DD" in capsys.readouterr().err


def test_cli_reads_a_stale_sheet_with_a_limit(capsys):
    assert cli.main(["--on", "2026-12-20"]) == 0
    assert "STALE" in capsys.readouterr().out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_writes_the_reading_as_json(tmp_path, capsys):
    target = tmp_path / "rates.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["as_of"] == "2026-11-14"
    assert payload["base"] == "USD"
    assert payload["age_days"] == 1 and payload["stale"] is False
    assert payload["rates"][0]["pair"] == "USD/EUR"
    assert payload["rates"][0]["inverse"] == "EUR/USD = 100/92"
    assert payload["exponents"]["JPY"] == 0
    assert payload["conversions"][2]["to"] == "15,100 JPY"
    assert payload["conversions"][2]["drift"] == 0
    assert payload["unknown_currency"]["legacy_rate"] == 1.0


def test_cli_json_records_the_wrong_direction(capsys, tmp_path):
    target = tmp_path / "rates.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    first = payload["conversions"][0]
    assert first["from"] == "100.00 USD"
    assert first["to"] == "92.00 EUR"
    assert first["legacy_to"] == 92.0
    assert first["legacy_back"] == 84.64


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_missing_sheet_exits_two(tmp_path, capsys):
    assert cli.main(["--quote", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_malformed_sheet_exits_two(tmp_path, capsys):
    path = tmp_path / "quote.txt"
    path.write_bytes(b"base USD\n")
    assert cli.main(["--quote", str(path)]) == 2
    assert "names no day" in capsys.readouterr().err


def test_cli_a_missing_amount_list_exits_two(tmp_path, capsys):
    assert cli.main(["--amounts", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err
