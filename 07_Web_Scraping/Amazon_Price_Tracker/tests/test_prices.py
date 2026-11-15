"""Tests for Amazon_Price_Tracker: a price is money, not characters left over
after deleting everything that is not a digit or a dot."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
import prices as module                                       # noqa: E402
from prices import (                                          # noqa: E402
    BUY_BOX,
    CODES,
    LIST_BOX,
    LEGACY_CHANGE,
    LEGACY_CLEAN,
    OFFER_FILE,
    SYMBOLS,
    WATCH_FILE,
    Element,
    Money,
    Offer,
    PriceError,
    Sample,
    Watch,
    agrees,
    audit,
    change_bp,
    divide_half_up,
    format_bp,
    is_range,
    label_for,
    legacy_clean_price,
    legacy_offer_price,
    legacy_percentage_change,
    parse_amount,
    parse_html,
    parse_offer,
    parse_price,
    parse_range,
    parse_watch,
    problems,
    read_offer_page,
    read_watch,
    run_demo,
)


def a_page() -> str:
    return read_offer_page()


def an_offer() -> Offer:
    return parse_offer(a_page())


def a_watch() -> Watch:
    return read_watch()


def raw_money(cents, currency: str = "USD") -> Money:
    """A Money with the validation bypassed, so an audit can disagree with it."""
    money = object.__new__(Money)
    object.__setattr__(money, "cents", cents)
    object.__setattr__(money, "currency", currency)
    return money


def broken_watch(samples) -> Watch:
    """A Watch with the validation bypassed, so an audit can disagree with it."""
    watch = object.__new__(Watch)
    object.__setattr__(watch, "samples", tuple(samples))
    return watch


class LowestBaseline(Watch):
    """A watch whose change is measured from its lowest price, not its first."""

    def change(self):
        return change_bp(self.lowest().price, self.last().price)


class FirstAsLowest(Watch):
    """A watch that names its first sample the lowest, without looking."""

    def lowest(self):
        return self.first()


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #
def test_money_is_cents_and_a_currency():
    money = Money(129_900)
    assert money.cents == 129_900 and money.currency == "USD"


def test_money_prints_grouped_with_two_decimals():
    assert Money(129_900).format() == "$1,299.00"


def test_money_prints_a_negative_amount_with_the_sign_in_front():
    assert Money(-129_900).format() == "-$1,299.00"


def test_money_prints_a_small_amount_with_a_leading_zero():
    assert Money(5).format() == "$0.05"


def test_money_prints_zero():
    assert Money(0).format() == "$0.00"


def test_a_non_dollar_currency_prints_its_code():
    assert Money(129_900, "EUR").format() == "EUR 1,299.00"


def test_a_symbol_that_is_not_ascii_is_printed_as_a_code():
    assert label_for("GBP") == "GBP "


def test_the_dollar_symbol_is_printed_as_a_symbol():
    assert label_for("USD") == "$"


def test_an_unknown_currency_is_printed_as_its_code():
    assert Money(100, "CHF").format() == "CHF 1.00"


def test_money_orders_by_cents():
    assert Money(100) < Money(200)


def test_money_adds_when_the_currencies_agree():
    assert Money(100).plus(Money(250)) == Money(350)


def test_money_subtracts_into_a_negative_amount():
    assert Money(100).minus(Money(150)).cents == -50


def test_money_refuses_to_add_two_currencies():
    with pytest.raises(PriceError, match="cannot combine USD with EUR"):
        Money(100).plus(Money(100, "EUR"))


def test_money_refuses_a_float_number_of_cents():
    with pytest.raises(PriceError, match="whole number of cents"):
        Money(1.0)


def test_money_refuses_a_bool_as_cents():
    with pytest.raises(PriceError, match="whole number of cents"):
        Money(True)


def test_money_refuses_a_currency_that_is_not_three_letters():
    with pytest.raises(PriceError, match="three capital letters"):
        Money(100, "EU")


def test_money_refuses_a_lowercase_currency():
    with pytest.raises(PriceError, match="three capital letters"):
        Money(100, "usd")


def test_the_symbol_table_maps_every_symbol_to_a_known_code():
    assert set(SYMBOLS.values()) <= set(CODES)


def test_str_of_money_is_its_printed_form():
    assert str(Money(1_299_900)) == "$12,999.00"


# --------------------------------------------------------------------------- #
# Rounding
# --------------------------------------------------------------------------- #
def test_half_up_rounds_a_half_away_from_zero():
    assert divide_half_up(1, 2) == 1


def test_half_up_rounds_a_negative_half_away_from_zero():
    assert divide_half_up(-1, 2) == -1


def test_half_up_rounds_the_middle_of_an_eighth_up():
    assert divide_half_up(2548, 8) == 319


def test_half_up_rounds_a_negative_middle_down():
    assert divide_half_up(-2548, 8) == -319


def test_half_up_truncates_below_the_half():
    assert divide_half_up(7, 2) == 4 and divide_half_up(5, 2) == 3


def test_half_up_is_exact_for_a_whole_multiple():
    assert divide_half_up(1200, 3) == 400


def test_half_up_refuses_a_zero_denominator():
    with pytest.raises(PriceError, match="divide by zero"):
        divide_half_up(1, 0)


def test_round_would_have_rounded_a_half_to_even():
    """The reason this lab does not use `round`: 2548/8 is 318.5."""
    assert round(318.5) == 318 and divide_half_up(2548, 8) == 319


# --------------------------------------------------------------------------- #
# Ranges
# --------------------------------------------------------------------------- #
def test_a_hyphen_between_two_amounts_is_a_range():
    assert is_range("$1,299.00 - $1,399.00") is True


def test_an_en_dash_is_a_range():
    assert is_range("$1,299.00 \u2013 $1,399.00") is True


def test_the_word_to_is_a_range():
    assert is_range("$1,299.00 to $1,399.00") is True


def test_a_plain_price_is_not_a_range():
    assert is_range("$1,299.00") is False


def test_a_euro_price_with_a_dot_group_is_not_a_range():
    assert is_range("1.299,00 EUR") is False


def test_is_range_refuses_text():
    with pytest.raises(PriceError, match="a price is text"):
        is_range(1299)


def test_parse_range_reads_both_ends():
    low, high = parse_range("$1,299.00 - $1,399.00")
    assert (low.cents, high.cents) == (129_900, 139_900)


def test_parse_range_refuses_a_single_price():
    with pytest.raises(PriceError, match="this is not a range"):
        parse_range("$1,299.00")


# --------------------------------------------------------------------------- #
# Reading an amount
# --------------------------------------------------------------------------- #
def test_a_plain_price_reads():
    assert parse_price("$1,299.00").cents == 129_900


def test_a_price_without_decimals_reads_as_whole_dollars():
    assert parse_price("$1,299").cents == 129_900


def test_a_euro_price_reads_by_its_last_separator():
    money = parse_price("1.299,00 EUR")
    assert money.cents == 129_900 and money.currency == "EUR"


def test_the_same_money_written_the_american_way_reads_the_same():
    assert parse_price("1,299.00 USD").cents == parse_price(
        "1.299,00 EUR").cents


def test_a_space_can_group_thousands():
    assert parse_price("$1 299.00").cents == 129_900


def test_one_decimal_means_fifty_cents():
    assert parse_price("$18.5").cents == 1_850


def test_a_single_dot_with_three_digits_is_a_thousand_separator():
    """The rule, stated: `1.299` is 1299, not 1.299 of a dollar."""
    assert parse_price("1.299").cents == 129_900


def test_a_single_dot_with_two_digits_is_a_decimal_point():
    assert parse_price("1.29").cents == 129


def test_a_single_comma_with_two_digits_is_a_decimal_comma():
    assert parse_price("12,50").cents == 1_250


def test_two_grouping_separators_read_as_millions():
    assert parse_price("$1.299.000,00").cents == 129_900_000


def test_a_currency_code_sets_the_currency():
    assert parse_price("USD 12").currency == "USD"


def test_no_currency_marker_means_dollars():
    assert parse_price("12.00").currency == "USD"


def test_a_zero_price_is_a_real_answer():
    money = parse_price("$0.00")
    assert money.cents == 0 and money.format() == "$0.00"


def test_an_empty_price_is_refused():
    with pytest.raises(PriceError, match="the price text is empty"):
        parse_price("   ")


def test_a_price_with_no_digits_is_refused():
    with pytest.raises(PriceError, match="no digits in"):
        parse_price("$")


def test_a_letter_in_a_price_is_refused_by_name():
    with pytest.raises(PriceError, match="a price cannot hold 'a'"):
        parse_price("$12a00")


def test_a_range_is_refused_as_a_price():
    with pytest.raises(PriceError, match="this is a range, not a price"):
        parse_price("$1,299.00 - $1,399.00")


def test_three_decimals_are_refused():
    with pytest.raises(PriceError, match="has 3 decimals"):
        parse_price("$1,299.005")


def test_a_group_that_is_not_three_digits_is_refused():
    with pytest.raises(PriceError, match="the group '34' is not three digits"):
        parse_price("$12,34.00")


def test_a_price_ending_at_its_separator_is_refused():
    with pytest.raises(PriceError, match="the group '' is not three digits"):
        parse_price("12.")


def test_two_currency_symbols_are_refused():
    with pytest.raises(PriceError, match="two currency symbols"):
        parse_price("$12 \u20ac")


def test_two_different_currencies_are_refused():
    with pytest.raises(PriceError, match="two currencies"):
        parse_price("$12 EUR")


def test_parse_price_refuses_something_that_is_not_text():
    with pytest.raises(PriceError, match="a price is text"):
        parse_price(1299)


def test_parse_amount_returns_cents_and_a_code():
    assert parse_amount("$1,299.00") == (129_900, "USD")


# --------------------------------------------------------------------------- #
# The legacy functions
# --------------------------------------------------------------------------- #
def test_the_legacy_cleaner_reads_a_plain_price():
    assert legacy_clean_price("$1,299.00") == 1299.0


def test_the_legacy_cleaner_drops_the_comma_and_keeps_the_dot():
    assert legacy_clean_price("$1,299.00") == 1299.0


def test_the_legacy_cleaner_misreads_a_euro_price_by_a_thousand():
    assert legacy_clean_price("1.299,00 EUR") == pytest.approx(1.299)


def test_the_legacy_cleaner_answers_zero_for_a_range():
    assert legacy_clean_price("$1,299.00 - $1,399.00") == 0.0


def test_the_legacy_cleaner_answers_zero_for_nothing():
    assert legacy_clean_price("") == 0.0 and legacy_clean_price(None) == 0.0


def test_the_legacy_cleaner_never_raises():
    for text in ("", "$", "abc", "$1-$2", "\u20ac"):
        assert isinstance(legacy_clean_price(text), float)


def test_the_legacy_percentage_of_a_zero_baseline_is_zero():
    assert legacy_percentage_change(0.0, 1299.0) == 0.0


def test_the_legacy_percentage_is_a_float():
    assert legacy_percentage_change(100.0, 90.0) == pytest.approx(-10.0)


def test_agrees_sees_that_the_plain_price_matches():
    assert agrees("$1,299.00") is True


def test_agrees_sees_that_the_euro_price_does_not():
    assert agrees("1.299,00 EUR") is False


def test_agrees_says_a_refused_text_does_not_agree():
    assert agrees("$1,299.00 - $1,399.00") is False


# --------------------------------------------------------------------------- #
# A change
# --------------------------------------------------------------------------- #
def test_a_drop_is_negative_basis_points():
    assert change_bp(Money(139_900), Money(129_900)) == -715


def test_a_rise_is_positive_basis_points():
    assert change_bp(Money(129_900), Money(139_900)) == 770


def test_an_unknown_old_price_gives_no_change():
    assert change_bp(None, Money(129_900)) is None


def test_an_unknown_new_price_gives_no_change():
    assert change_bp(Money(129_900), None) is None


def test_the_same_price_is_a_change_of_zero():
    assert change_bp(Money(129_900), Money(129_900)) == 0


def test_a_zero_baseline_is_refused_with_a_sentence():
    with pytest.raises(PriceError, match="cannot be a baseline"):
        change_bp(Money(0), Money(129_900))


def test_two_currencies_cannot_be_compared():
    with pytest.raises(PriceError, match="cannot compare USD with EUR"):
        change_bp(Money(100), Money(200, "EUR"))


def test_a_change_prints_as_a_percentage():
    assert format_bp(-715) == "-7.15%" and format_bp(770) == "+7.70%"


def test_an_unknown_change_prints_as_unknown():
    assert format_bp(None) == "unknown"


def test_a_change_of_zero_prints_with_a_plus():
    assert format_bp(0) == "+0.00%"


# --------------------------------------------------------------------------- #
# Just enough DOM
# --------------------------------------------------------------------------- #
def test_a_tree_finds_an_element_by_tag():
    page = parse_html("<div><p>hello</p></div>")
    assert page.find("p").text() == "hello"


def test_a_tree_finds_an_element_by_id():
    page = parse_html('<div id="a"><p>x</p></div><div id="b"><p>y</p></div>')
    assert page.find(id="b").text() == "y"


def test_a_tree_finds_every_element_with_a_class():
    page = parse_html('<span class="a-offscreen">1</span>'
                      '<span class="a-offscreen">2</span>')
    assert len(page.find_all(cls="a-offscreen")) == 2


def test_classes_are_split_on_whitespace():
    element = Element("span", {"class": "a-price  a-text-price"})
    assert element.classes() == ("a-price", "a-text-price")


def test_text_collapses_whitespace_and_strips():
    page = parse_html("<h1>\n   Studio   Headphones \n</h1>")
    assert page.find("h1").text() == "Studio Headphones"


def test_text_reads_nested_elements():
    page = parse_html("<div>a<span>b</span>c</div>")
    assert page.find("div").text() == "abc"


def test_entities_are_decoded():
    page = parse_html("<p>tom &amp; jerry</p>")
    assert page.find("p").text() == "tom & jerry"


def test_a_void_element_is_not_a_parent():
    page = parse_html("<div>a<br>b<span>c</span></div>")
    assert page.find("div").text() == "abc"


def test_a_mismatched_end_tag_closes_back_to_the_named_tag():
    page = parse_html("<div><p>a</div>")
    assert page.find("div").text() == "a"


def test_a_comment_is_dropped():
    page = parse_html("<div><!-- a note --><p>x</p></div>")
    assert page.find("div").text() == "x"


def test_a_missing_element_finds_nothing():
    assert parse_html("<div></div>").find("p") is None


def test_parse_html_refuses_something_that_is_not_text():
    with pytest.raises(PriceError, match="a page is text"):
        parse_html(b"<div></div>")


# --------------------------------------------------------------------------- #
# Reading the page
# --------------------------------------------------------------------------- #
def test_the_page_says_what_the_title_is():
    assert an_offer().title == "Studio Headphones - over-ear, wired"


def test_the_buy_box_is_the_price_being_asked():
    assert an_offer().price == Money(129_900)


def test_the_first_offscreen_is_the_list_price():
    assert legacy_offer_price(a_page()) == 1399.0


def test_the_list_price_is_read_as_a_list_price():
    assert an_offer().list_price == Money(139_900)


def test_the_buy_box_is_not_the_first_match():
    assert an_offer().price.cents != int(legacy_offer_price(a_page()) * 100)


def test_the_availability_is_read():
    assert an_offer().availability == "In Stock"


def test_a_clean_offer_has_no_note():
    assert an_offer().note == ""


def test_the_discount_is_measured_from_the_list_price():
    assert an_offer().discount_bp() == -715


def test_an_offer_without_a_list_price_has_no_discount():
    offer = replace(an_offer(), list_price=None)
    assert offer.discount_bp() is None


def test_an_offer_without_a_price_has_no_discount():
    offer = replace(an_offer(), price=None, list_price=Money(100))
    assert offer.discount_bp() is None


def test_a_page_without_a_buy_box_says_why_the_price_is_unknown():
    offer = parse_offer("<div><h1>Thing</h1></div>")
    assert offer.price is None and "no such element" in offer.note


def test_a_buy_box_with_no_digits_says_why():
    offer = parse_offer('<div><span class="priceToPay">see price in cart'
                        '</span></div>')
    assert offer.price is None and "cannot hold" in offer.note


def test_a_buy_box_holding_a_range_says_so():
    offer = parse_offer('<span class="priceToPay">$1,299.00 - $1,399.00'
                        '</span>')
    assert offer.price is None and "range" in offer.note


def test_an_offer_prints_its_price_when_it_has_one():
    assert an_offer().line() == \
        "   $1,299.00  Studio Headphones - over-ear, wired"


def test_an_offer_prints_a_question_mark_when_it_has_none():
    offer = replace(an_offer(), price=None, note="the element is empty")
    assert offer.line().lstrip().startswith("?  Studio Headphones")


def test_a_page_without_a_title_reads_an_empty_title():
    assert parse_offer('<span class="priceToPay">$5.00</span>').title == ""


def test_the_buy_box_and_list_box_names_are_what_the_page_uses():
    page = a_page()
    assert f'class="{BUY_BOX}"' in page and LIST_BOX in page


def test_a_missing_page_is_refused(tmp_path):
    with pytest.raises(PriceError, match="file not found"):
        read_offer_page(tmp_path / "nope.html")


# --------------------------------------------------------------------------- #
# A watch
# --------------------------------------------------------------------------- #
def test_the_bundled_watch_holds_five_samples():
    assert len(a_watch()) == 5


def test_the_watch_is_in_tick_order():
    assert [sample.at for sample in a_watch().samples] == [0, 1, 2, 3, 4]


def test_the_first_and_last_samples_are_the_ends():
    watch = a_watch()
    assert watch.first().price == Money(139_900)
    assert watch.last().price == Money(129_900)


def test_the_lowest_sample_is_the_minimum():
    assert a_watch().lowest().price == Money(124_900)
    assert a_watch().lowest().at == 3


def test_the_change_is_measured_from_the_first_sample():
    assert a_watch().change() == -715


def test_the_samples_at_or_below_a_target():
    assert len(a_watch().below(Money(125_000))) == 1


def test_the_first_sample_at_or_below_a_target():
    assert a_watch().first_below(Money(125_000)).at == 3


def test_no_sample_below_a_target_that_is_never_reached():
    assert a_watch().first_below(Money(100)) is None


def test_a_watch_prints_one_line_per_sample():
    assert a_watch().lines()[0] == "t=0   $1,399.00"
    assert a_watch().lines()[-1] == "t=4   $1,299.00"


def test_a_watch_needs_a_sample():
    with pytest.raises(PriceError, match="at least one sample"):
        Watch(())


def test_a_watch_refuses_samples_out_of_order():
    with pytest.raises(PriceError, match="not in tick order"):
        Watch((Sample(0, Money(100)), Sample(2, Money(100)),
               Sample(1, Money(100))))


def test_a_watch_refuses_two_samples_on_one_tick():
    with pytest.raises(PriceError, match="share a tick"):
        Watch((Sample(1, Money(100)), Sample(1, Money(200))))


# --------------------------------------------------------------------------- #
# Reading a watch
# --------------------------------------------------------------------------- #
def test_a_watch_is_read_from_two_columns():
    assert parse_watch("0\t$10.00\n1\t$9.00\n").last().price == Money(900)


def test_a_comment_line_is_skipped():
    assert len(parse_watch("; a note\n0\t$10.00\n")) == 1


def test_a_blank_line_is_skipped():
    assert len(parse_watch("\n\n0\t$10.00\n\n")) == 1


def test_a_line_without_a_tab_is_refused():
    with pytest.raises(PriceError, match="line 1: expected a tick"):
        parse_watch("0 $10.00\n")


def test_a_tick_that_is_not_a_number_is_refused():
    with pytest.raises(PriceError, match="is not a whole tick"):
        parse_watch("one\t$10.00\n")


def test_a_price_that_cannot_be_read_names_its_line():
    with pytest.raises(PriceError, match="the price text is empty"):
        parse_watch("0\t\n")


def test_a_watch_with_no_samples_is_refused():
    with pytest.raises(PriceError, match="holds no samples"):
        parse_watch("; nothing\n")


def test_windows_line_endings_are_read():
    assert len(parse_watch("0\t$10.00\r\n1\t$9.00\r\n")) == 2


def test_a_missing_watch_file_is_refused(tmp_path):
    with pytest.raises(PriceError, match="file not found"):
        read_watch(tmp_path / "nope.txt")


def test_the_bundled_files_are_pinned_on_disk():
    assert OFFER_FILE.read_text(encoding="utf-8").count("a-offscreen") == 2
    assert WATCH_FILE.read_text(encoding="utf-8").count("\t") == 5


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every amount is a whole number of cents, never a float",
    "every amount prints and reads back to the same cents",
    "no price the page stated is recorded as zero",
    "the legacy cleaner reads the plain price correctly",
    "the legacy cleaner misreads the euro price by 1000x",
    "the buy box price is not the first .a-offscreen on the page",
    "the list price is never below the price being asked",
    "the watch is in tick order and its lowest is the minimum",
    "the reported change is measured from the first sample",
]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(an_offer(), a_watch(), a_page())] == \
        CHECK_NAMES


def test_the_audit_passes_on_the_bundled_page():
    assert problems(audit(an_offer(), a_watch(), a_page())) == []


def test_the_audit_is_repeatable():
    assert audit(an_offer(), a_watch(), a_page()) == audit(
        an_offer(), a_watch(), a_page())


def test_the_audit_catches_half_a_cent():
    watch = broken_watch((Sample(0, raw_money(1.5)),))
    assert CHECK_NAMES[0] in problems(audit(an_offer(), watch, a_page()))


def test_the_audit_does_not_raise_on_half_a_cent():
    watch = broken_watch((Sample(0, raw_money(-0.25)),))
    assert len(audit(an_offer(), watch, a_page())) == 9


def test_the_audit_catches_an_amount_that_does_not_read_back():
    watch = broken_watch((Sample(0, Money(100, "US1")),))
    assert CHECK_NAMES[1] in problems(audit(an_offer(), watch, a_page()))


def test_the_audit_catches_a_price_recorded_as_zero():
    offer = replace(an_offer(), price=Money(0))
    assert CHECK_NAMES[2] in problems(audit(offer, a_watch(), a_page()))


def test_the_audit_catches_a_buy_box_read_as_the_list_price():
    offer = replace(an_offer(), price=Money(139_900))
    assert CHECK_NAMES[5] in problems(audit(offer, a_watch(), a_page()))


def test_the_audit_catches_a_list_price_below_the_buy_box():
    offer = replace(an_offer(), list_price=Money(100))
    assert CHECK_NAMES[6] in problems(audit(offer, a_watch(), a_page()))


def test_the_audit_catches_a_watch_out_of_order():
    reversed_watch = broken_watch(tuple(reversed(a_watch().samples)))
    assert CHECK_NAMES[7] in problems(
        audit(an_offer(), reversed_watch, a_page()))


def test_the_audit_catches_a_lowest_that_is_not_the_minimum():
    watch = FirstAsLowest(a_watch().samples)
    assert CHECK_NAMES[7] in problems(audit(an_offer(), watch, a_page()))


def test_the_audit_catches_a_change_measured_from_the_lowest():
    watch = LowestBaseline(a_watch().samples)
    assert CHECK_NAMES[8] in problems(audit(an_offer(), watch, a_page()))


def test_seven_of_the_nine_checks_have_a_negative_control():
    """Checks 3 and 4 pin the transcribed legacy lines and cannot be broken."""
    broken = [
        audit(an_offer(), broken_watch((Sample(0, raw_money(1.5)),)),
              a_page()),
        audit(an_offer(), broken_watch((Sample(0, Money(100, "US1")),)),
              a_page()),
        audit(replace(an_offer(), price=Money(0)), a_watch(), a_page()),
        audit(replace(an_offer(), price=Money(139_900)), a_watch(), a_page()),
        audit(replace(an_offer(), list_price=Money(100)), a_watch(), a_page()),
        audit(an_offer(), FirstAsLowest(a_watch().samples), a_page()),
        audit(an_offer(), LowestBaseline(a_watch().samples), a_page()),
    ]
    caught = {name for checks in broken for name in problems(checks)}
    assert len(caught) == 7


# --------------------------------------------------------------------------- #
# The legacy lines
# --------------------------------------------------------------------------- #
def test_the_legacy_lines_are_pinned():
    assert module.LEGACY_CLEAN.startswith('cleaned = re.sub(r"[^\\d.]"')
    assert "return 0.0" in module.LEGACY_CLEAN
    assert module.LEGACY_CHANGE.startswith("if old_price <= 0:")


def test_the_curious_texts_are_all_ascii():
    assert all(ord(character) < 128
               for text, _ in module.CURIOUS for character in text)


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


def test_demo_shows_the_legacy_lines(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert 'cleaned = re.sub(r"[^\\d.]", "", value)' in out
    assert "if old_price <= 0:" in out


def test_demo_shows_the_euro_price_read_two_ways(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "'1.299,00 EUR'" in out
    assert "EUR 1,299.00   129900 cents" in out


def test_demo_shows_the_range_and_the_empty_text_refused(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "this is a range, not a price" in out
    assert "the price text is empty" in out


def test_demo_shows_the_buy_box_and_the_first_match(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "the first .a-offscreen on the page says $1,399.00" in out
    assert "the buy box (priceToPay) says $1,299.00" in out


def test_demo_shows_the_watch_and_the_lowest(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "lowest $1,249.00 at t=3" in out
    assert "from the first sample to the last: -7.15%" in out


def test_demo_shows_that_unknown_is_not_zero(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "change_bp(None, last)       = unknown" in out
    assert "legacy_percentage_change(0.0, 1299.0) = 0.0 -- 'no change'" in out


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


def test_cli_reads_the_bundled_page(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "  Studio Headphones - over-ear, wired" in out
    assert "  the buy box says $1,299.00" in out
    assert "  the first .a-offscreen says $1,399.00" in out
    assert "  lowest $1,249.00 at t=3" in out


def test_cli_reads_one_price(capsys):
    assert cli.main(["--price", "1.299,00 EUR"]) == 0
    out = capsys.readouterr().out
    assert "is EUR 1,299.00 = 129900 cents of EUR" in out
    assert "the legacy cleaner says 1.2990" in out


def test_cli_reads_a_range(capsys):
    assert cli.main(["--range", "$1,299.00 - $1,399.00"]) == 0
    assert "is a range from $1,299.00 to $1,399.00" in \
        capsys.readouterr().out


def test_cli_reports_the_days_below_a_target(capsys):
    assert cli.main(["--target", "$1,250.00"]) == 0
    assert "at or below $1,250.00: 1 day(s), first at t=3" in \
        capsys.readouterr().out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_writes_the_json(tmp_path, capsys):
    target = tmp_path / "reading.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["buy_box"]["cents"] == 129_900
    assert payload["first_offscreen"] == pytest.approx(1399.0)
    assert payload["list_price"] == 139_900
    assert payload["change"] == -715
    assert len(payload["watch"]) == 5


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_price_it_cannot_read_exits_two(capsys):
    assert cli.main(["--price", "$1,299.00 - $1,399.00"]) == 2
    assert "this is a range" in capsys.readouterr().err


def test_cli_a_range_it_cannot_read_exits_two(capsys):
    assert cli.main(["--range", "$5.00"]) == 2
    assert "this is not a range" in capsys.readouterr().err


def test_cli_a_missing_page_exits_two(tmp_path, capsys):
    assert cli.main(["--page", str(tmp_path / "nope.html")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_malformed_watch_exits_two(tmp_path, capsys):
    path = tmp_path / "watch.txt"
    path.write_bytes(b"0 $10.00\n")
    assert cli.main(["--watch", str(path)]) == 2
    assert "expected a tick" in capsys.readouterr().err


def test_cli_a_target_it_cannot_read_exits_two(capsys):
    assert cli.main(["--target", "cheap"]) == 2
    assert "cannot hold 'c'" in capsys.readouterr().err
