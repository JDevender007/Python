"""Tests for IMDb_Movie_Scraper: a runtime is one quantity in one unit, not the
digits in the order the page happened to print them."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import durations as module                                   # noqa: E402
import main as cli                                           # noqa: E402
from durations import (                                      # noqa: E402
    BUDGET_MINUTES,
    LEGACY_RUNTIME,
    MINUTES_PER_HOUR,
    TITLES_FILE,
    Catalogue,
    Duration,
    DurationError,
    Element,
    Film,
    Marathon,
    Series,
    agrees,
    audit,
    legacy_minutes,
    parse_catalogue,
    parse_duration,
    parse_html,
    plan,
    problems,
    read_catalogue,
    run_demo,
)


def a_catalogue() -> Catalogue:
    return read_catalogue()


def a_show() -> Series:
    return a_catalogue().series[0]


def a_marathon() -> Marathon:
    return plan(a_catalogue().films, Duration(BUDGET_MINUTES))


def a_film(title: str = "Long One", runtime: int = 135) -> Film:
    return Film(title, Duration(runtime), "2020", "")


def raw_duration(minutes) -> Duration:
    """A Duration with the validation bypassed, so an audit can disagree."""
    duration = object.__new__(Duration)
    object.__setattr__(duration, "minutes", minutes)
    return duration


class BrokenPrinting(Duration):
    """A runtime that prints itself in a form that means something else."""

    def format(self) -> str:
        return "13h 5min"


# --------------------------------------------------------------------------- #
# A duration
# --------------------------------------------------------------------------- #
def test_a_duration_is_whole_minutes():
    assert Duration(135).minutes == 135


def test_a_duration_splits_into_hours_and_the_rest():
    assert (Duration(135).hours, Duration(135).rest) == (2, 15)


def test_a_duration_under_an_hour_has_no_hours():
    assert (Duration(45).hours, Duration(45).rest) == (0, 45)


def test_a_whole_number_of_hours_has_no_rest():
    assert (Duration(120).hours, Duration(120).rest) == (2, 0)


def test_a_duration_prints_hours_and_minutes():
    assert Duration(135).format() == "2h 15min"


def test_a_duration_under_an_hour_prints_only_minutes():
    assert Duration(45).format() == "45min"


def test_a_whole_number_of_hours_prints_without_minutes():
    assert Duration(120).format() == "2h"


def test_zero_prints_as_zero_minutes():
    assert Duration(0).format() == "0min"


def test_str_of_a_duration_is_its_printed_form():
    assert str(Duration(107)) == "1h 47min"


def test_a_duration_adds():
    assert Duration(60).plus(Duration(45)) == Duration(105)


def test_a_duration_multiplies_by_a_count():
    assert Duration(47).times(24) == Duration(1_128)


def test_a_duration_refuses_a_float():
    with pytest.raises(DurationError, match="whole number of minutes"):
        Duration(1.5)


def test_a_duration_refuses_a_bool():
    with pytest.raises(DurationError, match="whole number of minutes"):
        Duration(True)


def test_a_duration_refuses_a_negative_runtime():
    with pytest.raises(DurationError, match="cannot be negative"):
        Duration(-1)


def test_a_duration_refuses_a_float_count():
    with pytest.raises(DurationError, match="a count is a whole number"):
        Duration(10).times(2.0)


def test_a_duration_refuses_a_negative_count():
    with pytest.raises(DurationError, match="a count cannot be negative"):
        Duration(10).times(-1)


def test_durations_order_by_minutes():
    assert Duration(107) < Duration(135)


def test_an_hour_is_sixty_minutes():
    assert MINUTES_PER_HOUR == 60


# --------------------------------------------------------------------------- #
# Reading a runtime
# --------------------------------------------------------------------------- #
def test_a_bare_number_reads_as_minutes():
    assert parse_duration("135") == Duration(135)


def test_minutes_spelled_out_read():
    assert parse_duration("135 min") == Duration(135)


def test_minutes_in_full_read():
    assert parse_duration("135 minutes") == Duration(135)


def test_the_short_minute_suffix_reads():
    assert parse_duration("135m") == Duration(135)


def test_hours_and_minutes_are_added_not_concatenated():
    assert parse_duration("2h 15min") == Duration(135)


def test_hours_and_minutes_without_a_space_read():
    assert parse_duration("2h15min") == Duration(135)


def test_the_long_spelling_adds_the_same_way():
    assert parse_duration("2 hours 15 minutes") == Duration(135)


def test_a_comma_between_the_fields_reads():
    assert parse_duration("2h, 15min") == Duration(135)


def test_hours_alone_read():
    assert parse_duration("2h") == Duration(120)


def test_hours_alone_in_full_reads():
    assert parse_duration("2 hours") == Duration(120)


def test_a_runtime_under_an_hour_reads():
    assert parse_duration("45min") == Duration(45)


def test_an_hour_and_forty_seven_reads_as_one_hundred_and_seven():
    assert parse_duration("1h 47min") == Duration(107)


def test_surrounding_space_is_ignored():
    assert parse_duration("  2h 15min  ") == Duration(135)


def test_every_curious_text_that_reads_prints_back_to_itself():
    for text, _ in module.CURIOUS:
        try:
            runtime = parse_duration(text)
        except DurationError:
            continue
        assert parse_duration(runtime.format()) == runtime


def test_an_empty_runtime_is_refused():
    with pytest.raises(DurationError, match="the runtime text is empty"):
        parse_duration("   ")


def test_a_clock_form_is_refused_with_the_reason():
    with pytest.raises(DurationError, match="a clock form, not a runtime"):
        parse_duration("2:15")


def test_seconds_are_refused():
    with pytest.raises(DurationError, match="names seconds"):
        parse_duration("2h 15min 30s")


def test_a_minute_field_of_sixty_or_more_is_refused():
    with pytest.raises(DurationError, match="a minute field is below 60"):
        parse_duration("2h 75min")


def test_the_same_unit_twice_is_refused():
    with pytest.raises(DurationError, match="names the same unit twice"):
        parse_duration("2h 15h")


def test_text_with_no_units_and_no_number_is_refused():
    with pytest.raises(DurationError, match="no hours and no minutes"):
        parse_duration("long")


def test_a_stray_word_is_refused_by_name():
    with pytest.raises(DurationError, match="a runtime cannot hold"):
        parse_duration("2h 15min approx")


def test_a_negative_runtime_is_refused():
    with pytest.raises(DurationError, match="no hours and no minutes"):
        parse_duration("-5")


def test_parse_duration_refuses_something_that_is_not_text():
    with pytest.raises(DurationError, match="a runtime is text"):
        parse_duration(135)


# --------------------------------------------------------------------------- #
# The legacy conversion
# --------------------------------------------------------------------------- #
def test_the_legacy_reader_makes_two_hours_fifteen_into_215():
    assert legacy_minutes("2h 15min") == 215


def test_the_legacy_reader_makes_an_hour_forty_seven_into_147():
    assert legacy_minutes("1h 47min") == 147


def test_the_legacy_reader_reads_a_bare_number_correctly():
    assert legacy_minutes("135 min") == 135


def test_the_legacy_reader_reads_hours_alone_as_two():
    assert legacy_minutes("2h") == 2


def test_the_legacy_reader_concatenates_seconds_too():
    assert legacy_minutes("2h 15min 30s") == 21_530


def test_the_legacy_reader_answers_zero_for_nothing():
    assert legacy_minutes("") == 0 and legacy_minutes(None) == 0


def test_the_legacy_reader_never_raises():
    for text in ("", "h", "min", "2:15", "-"):
        assert isinstance(legacy_minutes(text), int)


def test_agrees_sees_that_a_bare_number_matches():
    assert agrees("135 min") is True


def test_agrees_sees_that_two_hours_fifteen_does_not():
    assert agrees("2h 15min") is False


def test_agrees_says_a_refused_text_does_not_agree():
    assert agrees("2:15") is False


# --------------------------------------------------------------------------- #
# Just enough DOM
# --------------------------------------------------------------------------- #
def test_a_tree_finds_an_element_by_class():
    page = parse_html('<span class="runtime">2h 15min</span>')
    assert page.find(cls="runtime").text() == "2h 15min"


def test_a_tree_finds_every_row():
    page = parse_html('<li class="row">a</li><li class="row">b</li>')
    assert len(page.find_all(cls="row")) == 2


def test_text_collapses_whitespace():
    page = parse_html("<p>\n  2h   15min \n</p>")
    assert page.find("p").text() == "2h 15min"


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
    assert parse_html("<div></div>").find(cls="runtime") is None


def test_classes_split_on_whitespace():
    assert Element("li", {"class": "row  series"}).classes() == ("row",
                                                                "series")


def test_parse_html_refuses_something_that_is_not_text():
    with pytest.raises(DurationError, match="a page is text"):
        parse_html(b"<div></div>")


# --------------------------------------------------------------------------- #
# Reading the page
# --------------------------------------------------------------------------- #
def test_the_page_holds_four_films():
    assert len(a_catalogue().films) == 4


def test_the_page_holds_one_series():
    assert len(a_catalogue().series) == 1


def test_the_hours_and_minutes_row_reads_as_135():
    assert a_catalogue().film("Long One").runtime == Duration(135)


def test_the_minutes_row_reads_as_135():
    assert a_catalogue().film("Long Two").runtime == Duration(135)


def test_the_two_spellings_are_the_same_runtime():
    catalogue = a_catalogue()
    assert catalogue.film("Long One").runtime == \
        catalogue.film("Long Two").runtime


def test_the_year_is_read():
    assert a_catalogue().film("Short One").year == "2019"


def test_a_film_with_no_runtime_is_unknown_with_a_note():
    film = a_catalogue().film("Unknown")
    assert film.runtime is None and "is empty" in film.note


def test_a_film_with_a_runtime_has_no_note():
    assert a_catalogue().film("Long One").note == ""


def test_a_film_line_shows_the_runtime():
    assert a_catalogue().film("Long One").line() == \
        "Long One       2h 15min  2020"


def test_a_minutes_line_shows_the_single_unit():
    assert a_catalogue().film("Short One").minutes_line() == \
        "Short One        107 min"


def test_an_unknown_minutes_line_shows_the_reason():
    line = a_catalogue().film("Unknown").minutes_line()
    assert line.lstrip().startswith("Unknown") and "?" in line


def test_known_runtimes_leaves_the_unknown_out():
    assert len(a_catalogue().known_runtimes()) == 3


def test_unknown_lists_the_film_with_no_runtime():
    assert a_catalogue().unknown()[0].title == "Unknown"


def test_the_series_reads_its_episode_count():
    show = a_show()
    assert (show.per_episode, show.episodes) == (Duration(47), 24)


def test_a_series_total_is_the_product():
    assert a_show().total() == Duration(1_128)


def test_a_series_line_shows_the_work():
    assert a_show().line() == "A Show        47min x 24  = 18h 48min"


def test_a_series_with_no_episode_count_has_no_total():
    show = Series("x", Duration(47), 0, "no count")
    assert show.total() is None


def test_a_series_with_no_runtime_has_no_total():
    show = Series("x", None, 24, "no runtime")
    assert show.total() is None


def test_a_catalogue_needs_a_title():
    with pytest.raises(DurationError, match="at least one title"):
        Catalogue((), ())


def test_a_catalogue_refuses_two_titles_with_one_name():
    film = a_film()
    with pytest.raises(DurationError, match="share a name"):
        Catalogue((film, film), ())


def test_film_refuses_a_title_that_is_not_on_the_page():
    with pytest.raises(DurationError, match="no film titled 'nope'"):
        a_catalogue().film("nope")


def test_a_page_with_no_rows_is_refused():
    with pytest.raises(DurationError, match="holds no titles"):
        parse_catalogue("<div></div>")


def test_a_runtime_that_cannot_be_read_is_a_note():
    catalogue = parse_catalogue('<li class="row film"><span class="title">x'
                                '</span><span class="runtime">2:15</span></li>')
    assert catalogue.film("x").runtime is None
    assert "clock form" in catalogue.film("x").note


def test_a_missing_page_is_refused(tmp_path):
    with pytest.raises(DurationError, match="file not found"):
        module.read_catalogue(tmp_path / "nope.html")


# --------------------------------------------------------------------------- #
# A marathon
# --------------------------------------------------------------------------- #
def test_the_plan_takes_the_films_that_fit_in_order():
    assert a_marathon().titles() == ("Long One", "Long Two")


def test_the_plan_total_is_the_sum_of_what_it_took():
    assert a_marathon().total() == Duration(270)


def test_the_plan_remaining_is_what_is_left():
    assert a_marathon().remaining() == Duration(30)


def test_the_plan_fits_its_budget():
    assert a_marathon().fits() is True


def test_the_plan_skips_a_film_that_does_not_fit():
    assert "Short One" not in a_marathon().titles()


def test_the_plan_skips_a_film_with_no_runtime():
    assert "Unknown" not in a_marathon().titles()


def test_the_plan_line_shows_used_and_left():
    assert a_marathon().line() == "2 film(s) of 5h: 4h 30min used, 30min left"


def test_a_budget_too_small_for_anything_plans_nothing():
    marathon = plan(a_catalogue().films, Duration(10))
    assert marathon.films == () and marathon.total() == Duration(0)


def test_a_plan_holding_a_film_with_no_runtime_has_no_total():
    marathon = Marathon(Duration(300), (a_film(), a_catalogue().film(
        "Unknown")))
    assert marathon.total() is None and marathon.remaining() is None


def test_a_plan_that_overspends_does_not_fit():
    marathon = Marathon(Duration(100), (a_film(),))
    assert marathon.fits() is False


def test_a_plan_that_overspends_has_no_remainder():
    assert Marathon(Duration(100), (a_film(),)).remaining() is None


def test_a_plan_that_overspends_says_so():
    assert Marathon(Duration(100), (a_film(),)).line().endswith("over budget")


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every runtime is a whole number of minutes",
    "every runtime prints and reads back to the same minutes",
    "the two spellings of 135 minutes are the same runtime",
    "the legacy reader makes 2h 15min into 215 minutes",
    "the legacy reader makes 1h 47min into 147 minutes",
    "the film whose runtime is missing is unknown, and no runtime is zero",
    "a series total is its episode count times its per-episode runtime",
    "the marathon never spends more than its budget",
    "the marathon never plans a film twice or without a runtime",
]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(a_catalogue(), a_show(),
                                      a_marathon())] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_page():
    assert problems(audit(a_catalogue(), a_show(), a_marathon())) == []


def test_the_audit_is_repeatable():
    assert audit(a_catalogue(), a_show(), a_marathon()) == audit(
        a_catalogue(), a_show(), a_marathon())


def test_the_audit_catches_half_a_minute():
    films = (replace(a_film(), runtime=raw_duration(135.5)),)
    catalogue = Catalogue(films, ())
    assert CHECK_NAMES[0] in problems(
        audit(catalogue, a_show(), a_marathon()))


def test_the_audit_does_not_raise_on_half_a_minute():
    films = (replace(a_film(), runtime=raw_duration(-0.5)),)
    catalogue = Catalogue(films, ())
    assert len(audit(catalogue, a_show(), a_marathon())) == 9


def test_the_audit_catches_a_runtime_that_prints_something_else():
    films = (replace(a_film(), runtime=BrokenPrinting(135)),)
    catalogue = Catalogue(films, ())
    assert CHECK_NAMES[1] in problems(
        audit(catalogue, a_show(), a_marathon()))


def test_the_audit_catches_the_two_spellings_disagreeing():
    catalogue = a_catalogue()
    films = tuple(replace(film, runtime=Duration(215))
                  if film.title == "Long Two" else film
                  for film in catalogue.films)
    assert CHECK_NAMES[2] in problems(
        audit(replace(catalogue, films=films), a_show(), a_marathon()))


def test_the_audit_catches_an_unknown_runtime_recorded_as_zero():
    catalogue = a_catalogue()
    films = tuple(replace(film, runtime=Duration(0))
                  if film.title == "Unknown" else film
                  for film in catalogue.films)
    assert CHECK_NAMES[5] in problems(
        audit(replace(catalogue, films=films), a_show(), a_marathon()))


def test_the_audit_catches_a_series_whose_total_is_not_the_product():
    show = Series("A Show", Duration(47), 24, "")
    broken = Series("A Show", Duration(47), 0, "no count")
    assert CHECK_NAMES[6] in problems(
        audit(a_catalogue(), broken, a_marathon()))


def test_the_audit_catches_a_marathon_that_overspends():
    marathon = Marathon(Duration(100), (a_film(),))
    assert CHECK_NAMES[7] in problems(
        audit(a_catalogue(), a_show(), marathon))


def test_the_audit_catches_a_marathon_that_plans_one_film_twice():
    film = a_film()
    marathon = Marathon(Duration(300), (film, film))
    assert CHECK_NAMES[8] in problems(
        audit(a_catalogue(), a_show(), marathon))


def test_six_of_the_nine_checks_have_a_negative_control():
    """Checks 3 and 4 pin the transcribed legacy lines; they cannot break."""
    catalogue = a_catalogue()
    broken = [
        audit(Catalogue((replace(a_film(), runtime=raw_duration(135.5)),), ()),
              a_show(), a_marathon()),
        audit(Catalogue((replace(a_film(),
                                 runtime=BrokenPrinting(135)),), ()),
              a_show(), a_marathon()),
        audit(replace(catalogue, films=tuple(
            replace(film, runtime=Duration(215))
            if film.title == "Long Two" else film
            for film in catalogue.films)), a_show(), a_marathon()),
        audit(catalogue, Series("A Show", Duration(47), 0, "no count"),
              a_marathon()),
        audit(catalogue, a_show(), Marathon(Duration(100), (a_film(),))),
        audit(catalogue, a_show(), Marathon(Duration(300),
                                            (a_film(), a_film()))),
    ]
    caught = {name for checks in broken for name in problems(checks)}
    assert len(caught) >= 6


# --------------------------------------------------------------------------- #
# The legacy lines
# --------------------------------------------------------------------------- #
def test_the_legacy_line_is_pinned():
    assert LEGACY_RUNTIME.startswith('cleaned = re.sub(r"[^\\d]"')
    assert "return 0" in LEGACY_RUNTIME


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


def test_demo_shows_the_legacy_line(capsys):
    run_demo()
    assert 'cleaned = re.sub(r"[^\\d]", "", value)' in capsys.readouterr().out


def test_demo_shows_two_hours_fifteen_read_two_ways(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "legacy    215     2h 15min    135 min" in out


def test_demo_shows_one_length_in_two_spellings(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "the same runtime: True" in out
    assert "it thinks they differ by 80 minutes" in out


def test_demo_shows_the_series_product(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "24 episodes of 47 minutes is 1,128 minutes" in out


def test_demo_shows_the_marathon(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "2 film(s) of 5h: 4h 30min used, 30min left" in out


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
    assert "4 film(s) on the page:" in out
    assert "Long One       2h 15min  2020" in out
    assert "A Show        47min x 24  = 18h 48min" in out
    assert "1,128 minutes in total" in out


def test_cli_reads_one_runtime(capsys):
    assert cli.main(["--runtime", "2h 15min"]) == 0
    out = capsys.readouterr().out
    assert "is 2h 15min = 135 minutes" in out
    assert "2 whole hour(s) and 15 minute(s)" in out
    assert "the legacy reader would have said 215" in out


def test_cli_accepts_a_budget(capsys):
    assert cli.main(["--budget", "2h"]) == 0
    assert "1 film(s) of 2h: 1h 47min used, 13min left" in \
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
    assert payload["films"][0]["runtime"] == 135
    assert payload["films"][0]["text"] == "2h 15min"
    assert payload["films"][3]["runtime"] is None
    assert payload["series"][0]["total"] == 1_128
    assert payload["marathon"]["films"] == ["Long One", "Long Two"]
    assert payload["marathon"]["remaining"] == 30


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_runtime_it_cannot_read_exits_two(capsys):
    assert cli.main(["--runtime", "2:15"]) == 2
    assert "clock form" in capsys.readouterr().err


def test_cli_a_budget_it_cannot_read_exits_two(capsys):
    assert cli.main(["--budget", "all day"]) == 2
    assert "no hours and no minutes" in capsys.readouterr().err


def test_cli_a_missing_page_exits_two(tmp_path, capsys):
    assert cli.main(["--page", str(tmp_path / "nope.html")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_audit_without_a_series_exits_two(tmp_path, capsys):
    path = tmp_path / "titles.html"
    path.write_bytes(b'<li class="row film"><span class="title">x</span>'
                     b'<span class="runtime">90 min</span></li>')
    assert cli.main(["--page", str(path), "--audit"]) == 2
    assert "no series to check" in capsys.readouterr().err
