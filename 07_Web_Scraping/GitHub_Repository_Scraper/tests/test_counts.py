"""Tests for GitHub_Repository_Scraper: a displayed count is a measurement
with a step, not the digits left after deleting the letters."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import counts as module                                      # noqa: E402
import main as cli                                           # noqa: E402
from counts import (                                         # noqa: E402
    HISTORY_FILE,
    LEGACY_CLEAN,
    LEGACY_MAGNITUDE,
    LISTING_FILE,
    Count,
    CountError,
    Element,
    History,
    Listing,
    Repo,
    Sample,
    agrees,
    audit,
    format_gain,
    gain,
    legacy_clean_number,
    legacy_magnitude,
    parse_count,
    parse_history,
    parse_html,
    parse_listing,
    problems,
    read_history,
    read_listing,
    relation,
    run_demo,
)


def a_listing() -> Listing:
    return read_listing()


def a_history() -> History:
    return read_history()


def raw_count(amount, resolution: int = 1) -> Count:
    """A Count with the validation bypassed, so an audit can disagree with it."""
    count = object.__new__(Count)
    object.__setattr__(count, "amount", amount)
    object.__setattr__(count, "resolution", resolution)
    return count


def broken_history(samples) -> History:
    history = object.__new__(History)
    object.__setattr__(history, "samples", tuple(samples))
    return history


# --------------------------------------------------------------------------- #
# A count
# --------------------------------------------------------------------------- #
def test_an_exact_count_is_an_amount_and_a_step_of_one():
    count = Count(1_234)
    assert (count.amount, count.resolution, count.exact) == (1_234, 1, True)


def test_a_count_with_a_step_is_not_exact():
    assert Count(2_300, 100).exact is False


def test_the_interval_of_an_exact_count_is_the_number_itself():
    count = Count(1_234)
    assert (count.low(), count.high()) == (1_234, 1_234)


def test_the_interval_of_a_suffixed_count_straddles_the_printed_figure():
    count = Count(2_300, 100)
    assert (count.low(), count.high()) == (2_250, 2_350)


def test_could_be_accepts_a_number_inside_the_interval():
    assert Count(2_300, 100).could_be(2_304) is True


def test_could_be_refuses_a_number_outside_the_interval():
    assert Count(2_300, 100).could_be(2_400) is False


def test_could_be_on_an_exact_count_is_equality():
    assert Count(1_234).could_be(1_234) is True
    assert Count(1_234).could_be(1_235) is False


def test_could_be_refuses_a_float():
    with pytest.raises(CountError, match="a count is a whole number"):
        Count(2_300, 100).could_be(2_304.0)


def test_an_exact_count_prints_grouped():
    assert Count(1_234_567).format() == "1,234,567"


def test_a_count_in_thousands_prints_one_decimal():
    assert Count(2_300, 100).format() == "2.3k"


def test_a_count_in_whole_thousands_prints_no_decimal():
    assert Count(12_000, 1_000).format() == "12k"


def test_a_count_in_millions_prints_one_decimal():
    assert Count(1_200_000, 100_000).format() == "1.2m"


def test_a_count_in_billions_prints_one_decimal():
    assert Count(3_400_000_000, 100_000_000).format() == "3.4b"


def test_a_small_exact_count_prints_in_full():
    assert Count(999).format() == "999"


def test_str_of_a_count_is_its_printed_form():
    assert str(Count(2_300, 100)) == "2.3k"


def test_a_count_refuses_a_negative_amount():
    with pytest.raises(CountError, match="cannot be negative"):
        Count(-1)


def test_a_count_refuses_a_float_amount():
    with pytest.raises(CountError, match="amount is a whole number"):
        Count(2.0)


def test_a_count_refuses_a_bool_amount():
    with pytest.raises(CountError, match="amount is a whole number"):
        Count(True)


def test_a_count_refuses_a_step_below_one():
    with pytest.raises(CountError, match="a resolution is at least 1"):
        Count(100, 0)


def test_a_count_refuses_a_float_step():
    with pytest.raises(CountError, match="resolution is a whole number"):
        Count(100, 10.0)


# --------------------------------------------------------------------------- #
# Reading a count
# --------------------------------------------------------------------------- #
def test_a_plain_integer_reads_exactly():
    count = parse_count("999")
    assert (count.amount, count.resolution) == (999, 1)


def test_a_grouped_integer_reads_exactly():
    count = parse_count("1,234")
    assert (count.amount, count.resolution) == (1_234, 1)


def test_a_grouped_million_reads_exactly():
    assert parse_count("12,345,678").amount == 12_345_678


def test_one_decimal_in_thousands_is_a_step_of_a_hundred():
    count = parse_count("2.3k")
    assert (count.amount, count.resolution) == (2_300, 100)


def test_one_decimal_in_millions_is_a_step_of_a_hundred_thousand():
    count = parse_count("1.2m")
    assert (count.amount, count.resolution) == (1_200_000, 100_000)


def test_a_whole_thousand_is_a_step_of_a_thousand():
    count = parse_count("12k")
    assert (count.amount, count.resolution) == (12_000, 1_000)


def test_a_billion_suffix_reads():
    assert parse_count("3.4b").amount == 3_400_000_000


def test_an_uppercase_suffix_reads_the_same():
    assert parse_count("2.3K").amount == parse_count("2.3k").amount


def test_trailing_space_is_ignored():
    assert parse_count("  2.3k  ").amount == 2_300


def test_every_curious_text_that_reads_prints_back_to_itself():
    for text, _ in module.CURIOUS:
        try:
            count = parse_count(text)
        except CountError:
            continue
        back = parse_count(count.format())
        assert (back.amount, back.resolution) == (count.amount,
                                                  count.resolution)


def test_an_empty_text_is_refused():
    with pytest.raises(CountError, match="the count text is empty"):
        parse_count("   ")


def test_a_suffix_with_no_digits_is_refused():
    with pytest.raises(CountError, match="no digits in 'k'"):
        parse_count("k")


def test_a_decimal_without_a_suffix_is_refused():
    with pytest.raises(CountError, match="the page prints a whole number"):
        parse_count("12.5")


def test_two_decimals_with_a_suffix_are_refused():
    with pytest.raises(CountError, match="at most one decimal place"):
        parse_count("2.34k")


def test_a_badly_grouped_number_is_refused():
    with pytest.raises(CountError, match="exactly three digits"):
        parse_count("12,34")


def test_grouping_and_a_suffix_together_are_refused():
    with pytest.raises(CountError, match="names a magnitude"):
        parse_count("1,2k")


def test_a_zero_before_a_suffix_is_refused():
    with pytest.raises(CountError, match="at least one of its magnitude"):
        parse_count("0.9k")


def test_a_negative_count_is_refused_by_the_character_rule():
    with pytest.raises(CountError, match="cannot hold '-'"):
        parse_count("-5")


def test_a_letter_in_the_middle_is_refused():
    with pytest.raises(CountError, match="cannot hold 'x'"):
        parse_count("2x3")


def test_parse_count_refuses_something_that_is_not_text():
    with pytest.raises(CountError, match="a count is text"):
        parse_count(2_300)


# --------------------------------------------------------------------------- #
# Comparing two counts
# --------------------------------------------------------------------------- #
def test_two_equal_exact_counts_are_the_same():
    assert relation(Count(1_234), Count(1_234)) == "same"


def test_two_unequal_exact_counts_are_different():
    assert relation(Count(1_234), Count(1_300)) == "different"


def test_an_estimate_and_an_exact_count_inside_it_are_indistinguishable():
    assert relation(parse_count("2.3k"), parse_count("2,304")) == \
        "indistinguishable"


def test_an_estimate_and_a_larger_exact_count_are_fewer():
    assert relation(parse_count("2.3k"), parse_count("5,000")) == "fewer"


def test_an_estimate_and_a_smaller_exact_count_are_more():
    assert relation(parse_count("2.3k"), parse_count("900")) == "more"


def test_two_estimates_that_do_not_overlap_are_ordered():
    assert relation(parse_count("1.2k"), parse_count("9.9k")) == "fewer"


def test_two_estimates_that_overlap_are_indistinguishable():
    assert relation(parse_count("2.3k"), parse_count("2.3k")) == \
        "indistinguishable"


def test_a_gain_between_two_exact_counts_is_a_point():
    assert gain(Count(100), Count(250)) == (150, 150)


def test_a_gain_between_two_estimates_is_wider_than_the_difference():
    low, high = gain(parse_count("1.8k"), parse_count("2.5k"))
    assert low < 700 < high


def test_a_gain_can_be_negative_at_its_low_end_when_the_counts_overlap():
    low, high = gain(parse_count("2.3k"), parse_count("2.3k"))
    assert low < 0 < high


def test_a_point_gain_prints_with_a_sign():
    assert format_gain((150, 150)) == "+150"


def test_an_interval_gain_prints_both_ends():
    assert format_gain((600, 800)) == "+600 to +800"


def test_a_negative_gain_prints_with_its_sign():
    assert format_gain((-900, -700)) == "-900 to -700"


# --------------------------------------------------------------------------- #
# The legacy conversions
# --------------------------------------------------------------------------- #
def test_the_legacy_cleaner_reads_2_3k_as_23():
    assert legacy_clean_number("2.3k") == 23


def test_the_legacy_cleaner_reads_1_2m_as_12():
    assert legacy_clean_number("1.2m") == 12


def test_the_legacy_cleaner_reads_a_grouped_number_correctly():
    assert legacy_clean_number("1,234") == 1_234


def test_the_legacy_cleaner_reads_an_empty_text_as_zero():
    assert legacy_clean_number("") == 0 and legacy_clean_number(None) == 0


def test_the_legacy_cleaner_reads_a_symbol_only_text_as_zero():
    assert legacy_clean_number("k") == 0


def test_the_legacy_magnitude_truncates_the_decimal():
    assert legacy_magnitude("2.9k") == 2_000


def test_the_legacy_magnitude_multiplies_everything_by_a_thousand():
    assert legacy_magnitude("12") == 12_000


def test_the_legacy_magnitude_reads_nothing_as_zero():
    assert legacy_magnitude("") == 0 and legacy_magnitude(None) == 0


def test_agrees_sees_that_a_plain_number_matches():
    assert agrees("1,234") is True


def test_agrees_sees_that_a_suffixed_count_does_not():
    assert agrees("2.3k") is False


def test_agrees_says_a_refused_text_does_not_agree():
    assert agrees("") is False


# --------------------------------------------------------------------------- #
# Just enough DOM
# --------------------------------------------------------------------------- #
def test_a_tree_finds_an_element_by_class():
    page = parse_html('<span class="stars">2.3k</span>')
    assert page.find(cls="stars").text() == "2.3k"


def test_a_tree_finds_an_element_by_tag():
    page = parse_html("<ul><li>a</li><li>b</li></ul>")
    assert len(page.find_all("li")) == 2


def test_text_collapses_whitespace():
    page = parse_html("<p>\n 2.3k \n</p>")
    assert page.find("p").text() == "2.3k"


def test_entities_are_decoded():
    page = parse_html("<p>a &amp; b</p>")
    assert page.find("p").text() == "a & b"


def test_a_void_element_is_not_a_parent():
    page = parse_html("<div>a<br>b</div>")
    assert page.find("div").text() == "ab"


def test_a_comment_is_dropped():
    page = parse_html("<div><!-- note -->x</div>")
    assert page.find("div").text() == "x"


def test_a_missing_element_finds_nothing():
    assert parse_html("<div></div>").find(cls="stars") is None


def test_a_self_closing_tag_is_a_child_but_not_a_parent():
    page = parse_html('<div><img src="a.png"/><span>1</span></div>')
    assert page.find("div").text() == "1"


def test_classes_split_on_whitespace():
    element = Element("li", {"class": "repo  public"})
    assert element.classes() == ("repo", "public")


def test_parse_html_refuses_something_that_is_not_text():
    with pytest.raises(CountError, match="a page is text"):
        parse_html(b"<div></div>")


# --------------------------------------------------------------------------- #
# Reading the listing
# --------------------------------------------------------------------------- #
def test_the_page_holds_five_repositories():
    assert len(a_listing()) == 5


def test_the_names_are_in_page_order():
    assert a_listing().names() == ("price-lab", "counts-lab", "big-lab",
                                   "quiet-lab", "tiny-lab")


def test_the_suffixed_star_count_is_not_exact():
    assert a_listing().get("price-lab").stars.exact is False


def test_the_grouped_star_count_is_exact():
    assert a_listing().get("counts-lab").stars.amount == 2_304


def test_a_suffixed_fork_count_reads_as_a_step():
    assert a_listing().get("big-lab").forks.resolution == 1_000


def test_a_zero_fork_count_is_a_real_answer():
    assert a_listing().get("tiny-lab").forks.amount == 0


def test_a_repository_with_no_stars_says_why():
    repo = a_listing().get("quiet-lab")
    assert repo.stars is None and "is empty" in repo.note


def test_the_language_is_read():
    assert a_listing().get("big-lab").language == "Go"


def test_a_repository_line_shows_its_stars_and_forks():
    assert a_listing().get("tiny-lab").line() == \
        "tiny-lab              999 stars       0 forks  Shell"


def test_an_exact_star_line_says_exact():
    assert a_listing().get("counts-lab").star_line() == \
        "counts-lab          2,304  exact"


def test_a_suffixed_star_line_shows_the_interval():
    line = a_listing().get("price-lab").star_line()
    assert "2.3k" in line and "between 2,250 and 2,350" in line


def test_a_missing_star_line_prints_a_question_mark():
    assert a_listing().get("quiet-lab").star_line().lstrip().startswith(
        "quiet-lab")


def test_a_listing_refuses_an_empty_page():
    with pytest.raises(CountError, match="no repository rows"):
        parse_listing("<div></div>")


def test_a_listing_needs_a_repository():
    with pytest.raises(CountError, match="at least one repository"):
        Listing(())


def test_a_listing_refuses_two_repositories_with_one_name():
    repo = Repo("x", Count(1), Count(2), "Go", "")
    with pytest.raises(CountError, match="share a name"):
        Listing((repo, repo))


def test_get_refuses_a_name_that_is_not_on_the_page():
    with pytest.raises(CountError, match="no repository named 'nope'"):
        a_listing().get("nope")


def test_a_missing_listing_file_is_refused(tmp_path):
    with pytest.raises(CountError, match="file not found"):
        module.read_listing(tmp_path / "nope.html")


def test_a_star_count_that_cannot_be_read_is_a_note():
    listing = parse_listing('<li class="repo"><a class="name">x</a>'
                            '<span class="stars">many</span></li>')
    assert listing.get("x").stars is None
    assert "cannot hold 'm'" in listing.get("x").note


# --------------------------------------------------------------------------- #
# A history
# --------------------------------------------------------------------------- #
def test_the_bundled_history_holds_five_samples():
    assert len(a_history()) == 5


def test_the_history_is_in_tick_order():
    assert [sample.at for sample in a_history().samples] == [0, 1, 2, 3, 4]


def test_the_first_and_last_samples_are_the_ends():
    history = a_history()
    assert history.first().count.amount == 1_800
    assert history.last().count.amount == 2_500


def test_the_gain_is_an_interval():
    assert a_history().gained() == (600, 800)


def test_a_history_line_shows_the_interval():
    assert a_history().lines()[0] == \
        "t=0       1.8k  between 1,750 and 1,850"


def test_a_history_needs_a_sample():
    with pytest.raises(CountError, match="at least one sample"):
        History(())


def test_a_history_refuses_samples_out_of_order():
    with pytest.raises(CountError, match="not in tick order"):
        History((Sample(2, Count(1)), Sample(1, Count(2))))


def test_a_history_refuses_two_samples_on_one_tick():
    with pytest.raises(CountError, match="share a tick"):
        History((Sample(1, Count(1)), Sample(1, Count(2))))


def test_a_history_reads_two_columns():
    assert parse_history("0\t999\n1\t1.1k\n").last().count.amount == 1_100


def test_a_comment_line_is_skipped():
    assert len(parse_history("; a note\n0\t999\n")) == 1


def test_a_blank_line_is_skipped():
    assert len(parse_history("\n\n0\t999\n\n")) == 1


def test_a_line_without_a_tab_is_refused():
    with pytest.raises(CountError, match="line 1: expected a tick"):
        parse_history("0 999\n")


def test_a_tick_that_is_not_a_number_is_refused():
    with pytest.raises(CountError, match="is not a whole tick"):
        parse_history("one\t999\n")


def test_a_history_with_no_samples_is_refused():
    with pytest.raises(CountError, match="holds no samples"):
        parse_history("; nothing\n")


def test_windows_line_endings_are_read():
    assert len(parse_history("0\t999\r\n1\t1.1k\r\n")) == 2


def test_a_missing_history_file_is_refused(tmp_path):
    with pytest.raises(CountError, match="file not found"):
        module.read_history(tmp_path / "nope.txt")


def test_the_bundled_files_are_pinned_on_disk():
    assert LISTING_FILE.read_text(encoding="utf-8").count('class="repo"') == 5
    assert HISTORY_FILE.read_text(encoding="utf-8").count("\t") == 5


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every count is a whole, non-negative number of items",
    "every count prints and reads back to the same amount and step",
    "every step is one of the steps the page prints",
    "a count printed with a suffix is at least one of its magnitude",
    "the legacy cleaner reads 2.3k as 23, not 2,300",
    "the legacy cleaner reads 1.2m as 12, not 1,200,000",
    "int() turns 2.9k into 2,000 and loses 900 stars",
    "the two counts the page could not distinguish say so",
    "the history is in tick order and its gain contains the difference",
]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(a_listing(), a_history())] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_files():
    assert problems(audit(a_listing(), a_history())) == []


def test_the_audit_is_repeatable():
    assert audit(a_listing(), a_history()) == audit(a_listing(), a_history())


def test_the_audit_catches_a_fractional_count():
    history = broken_history((Sample(0, raw_count(1.5)),))
    assert CHECK_NAMES[0] in problems(audit(a_listing(), history))


def test_the_audit_does_not_raise_on_a_fractional_count():
    history = broken_history((Sample(0, raw_count(-0.5)),))
    assert len(audit(a_listing(), history)) == 9


def test_the_audit_catches_a_count_that_does_not_print_back():
    history = broken_history((Sample(0, raw_count(2_349, 100)),))
    assert CHECK_NAMES[1] in problems(audit(a_listing(), history))


def test_the_audit_catches_a_step_the_page_never_prints():
    history = broken_history((Sample(0, raw_count(2_300, 7)),))
    assert CHECK_NAMES[2] in problems(audit(a_listing(), history))


def test_the_audit_catches_a_suffixed_count_below_its_magnitude():
    history = broken_history((Sample(0, raw_count(500, 1_000)),))
    assert CHECK_NAMES[3] in problems(audit(a_listing(), history))


def test_the_audit_catches_two_counts_that_no_longer_overlap():
    repos = tuple(replace(repo, stars=Count(5_000, 1))
                  if repo.name == "counts-lab" else repo
                  for repo in a_listing().repos)
    listing = replace(a_listing(), repos=repos)
    assert CHECK_NAMES[7] in problems(audit(listing, a_history()))


def test_the_audit_catches_a_history_out_of_order():
    history = broken_history((Sample(2, Count(2_500, 100)),
                              Sample(1, Count(1_800, 100))))
    assert CHECK_NAMES[8] in problems(audit(a_listing(), history))


def test_six_of_the_nine_checks_have_a_negative_control():
    """Checks 4, 5 and 6 pin the transcribed legacy lines; they cannot break."""
    broken = [
        audit(a_listing(), broken_history((Sample(0, raw_count(1.5)),))),
        audit(a_listing(), broken_history((Sample(0, raw_count(2_349, 100)),))),
        audit(a_listing(), broken_history((Sample(0, raw_count(2_300, 7)),))),
        audit(a_listing(), broken_history((Sample(0, raw_count(500, 1_000)),))),
        audit(replace(a_listing(), repos=tuple(
            replace(repo, stars=Count(5_000, 1))
            if repo.name == "counts-lab" else repo
            for repo in a_listing().repos)), a_history()),
        audit(a_listing(), broken_history((Sample(2, Count(2_500, 100)),
                                           Sample(1, Count(1_800, 100))))),
    ]
    caught = {name for checks in broken for name in problems(checks)}
    assert len(caught) == 6


# --------------------------------------------------------------------------- #
# The legacy lines
# --------------------------------------------------------------------------- #
def test_the_legacy_lines_are_pinned():
    assert LEGACY_CLEAN.startswith('cleaned = re.sub(r"[^\\d]"')
    assert "return 0" in LEGACY_CLEAN
    assert LEGACY_MAGNITUDE.startswith('number = value.rstrip("kmb")')


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
    assert 'cleaned = re.sub(r"[^\\d]", "", value)' in out
    assert 'number = value.rstrip("kmb")' in out


def test_demo_shows_two_and_a_half_k_twice(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "legacy         23       2.3k  step 100" in out


def test_demo_shows_the_interval_the_page_printed(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "between 2,250 and 2,350" in out
    assert "indistinguishable" in out


def test_demo_shows_the_gain_as_a_range(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "gained from the first sample to the last: +600 to +800" in out


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
    assert "5 repositories on the page" in out
    assert "price-lab            2.3k stars     128 forks  Python" in out
    assert "gained from the first sample to the last: +600 to +800" in out


def test_cli_reads_one_count(capsys):
    assert cli.main(["--count", "2.3k"]) == 0
    out = capsys.readouterr().out
    assert "is 2.3k = 2,300 items" in out
    assert "printed in steps of 100, so anywhere between 2,250 and 2,350" in out


def test_cli_says_when_a_count_is_exact(capsys):
    assert cli.main(["--count", "1,234"]) == 0
    assert "every digit was printed, so the figure is exact" in \
        capsys.readouterr().out


def test_cli_compares_two_counts(capsys):
    assert cli.main(["--compare", "2.3k", "2,304"]) == 0
    out = capsys.readouterr().out
    assert "2.3k is indistinguishable 2,304" in out
    assert "the page never printed enough digits to separate them" in out


def test_cli_compares_two_exact_counts(capsys):
    assert cli.main(["--compare", "10", "250"]) == 0
    out = capsys.readouterr().out
    assert "10 is different 250" in out
    assert "the second is +240 from the first" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_writes_the_json(tmp_path, capsys):
    target = tmp_path / "reading.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["listing"][0]["stars"]["amount"] == 2_300
    assert payload["listing"][0]["stars"]["step"] == 100
    assert payload["listing"][1]["stars"]["step"] == 1
    assert payload["listing"][3]["stars"] is None
    assert payload["gained"] == [600, 800]


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_count_it_cannot_read_exits_two(capsys):
    assert cli.main(["--count", "many"]) == 2
    assert "cannot hold 'm'" in capsys.readouterr().err


def test_cli_a_comparison_it_cannot_read_exits_two(capsys):
    assert cli.main(["--compare", "2.3k", "lots"]) == 2
    assert "cannot hold 'l'" in capsys.readouterr().err


def test_cli_a_missing_listing_exits_two(tmp_path, capsys):
    assert cli.main(["--listing", str(tmp_path / "nope.html")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_malformed_history_exits_two(tmp_path, capsys):
    path = tmp_path / "history.txt"
    path.write_bytes(b"0 999\n")
    assert cli.main(["--history", str(path)]) == 2
    assert "expected a tick" in capsys.readouterr().err
