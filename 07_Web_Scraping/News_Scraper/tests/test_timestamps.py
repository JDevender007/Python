"""Tests for News_Scraper: a timestamp is an instant in UTC, a relative phrase
is measured from a supplied reading time, and an unreadable date never becomes
"now"."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                           # noqa: E402
import timestamps as module                                  # noqa: E402
from timestamps import (                                     # noqa: E402
    FEED_FILE,
    LEGACY_AGE,
    LEGACY_FALLBACK,
    MONTHS,
    READ_AT,
    Article,
    Feed,
    Moment,
    TimeError,
    audit,
    legacy_age,
    legacy_fallback,
    parse_feed,
    parse_timestamp,
    problems,
    read_feed,
    reading_time,
    run_demo,
)

UTC = timezone.utc


def now() -> Moment:
    return reading_time()


def a_feed() -> Feed:
    return read_feed()


def a_moment(text: str = "2026-11-14T09:30:00Z") -> Moment:
    return parse_timestamp(text)


def raw_moment(epoch) -> Moment:
    """A Moment with the validation bypassed, so an audit can disagree."""
    moment = object.__new__(Moment)
    object.__setattr__(moment, "epoch", epoch)
    return moment


class WrongISO(Moment):
    """An instant that prints itself as a different instant."""

    def iso(self) -> str:
        return "2019-03-01T00:00:00Z"


def an_article(identifier: str = "iso",
               printed: str = "2026-11-14T09:30:00Z",
               moment: Moment | None = None, note: str = "") -> Article:
    return Article(identifier, "A title", printed,
                   a_moment(printed) if moment is None else moment, note)


# --------------------------------------------------------------------------- #
# An instant
# --------------------------------------------------------------------------- #
def test_a_moment_is_whole_seconds():
    assert Moment(1_700_000_000).epoch == 1_700_000_000


def test_a_moment_prints_iso_8601_in_utc():
    assert a_moment().iso() == "2026-11-14T09:30:00Z"


def test_a_moment_prints_for_a_person():
    assert a_moment().human() == "14 Nov 2026 09:30 UTC"


def test_str_of_a_moment_is_its_iso_form():
    assert str(a_moment()) == "2026-11-14T09:30:00Z"


def test_a_moment_orders_by_its_instant():
    assert a_moment("2026-11-14T09:30:00Z") < a_moment("2026-11-15T09:30:00Z")


def test_two_writings_of_one_instant_are_equal():
    left = a_moment("2026-11-15T13:00:00+02:00")
    right = a_moment("2026-11-15T11:00:00Z")
    assert left == right


def test_a_moment_refuses_a_float_epoch():
    with pytest.raises(TimeError, match="whole number of seconds"):
        Moment(1.5)


def test_a_moment_refuses_a_bool_epoch():
    with pytest.raises(TimeError, match="whole number of seconds"):
        Moment(True)


def test_the_age_of_an_instant_is_measured_from_the_reading_time():
    assert a_moment().age_seconds(now()) == 95_400


def test_the_age_of_the_reading_time_itself_is_zero():
    assert now().age_seconds(now()) == 0


def test_an_instant_after_the_reading_time_has_no_age():
    with pytest.raises(TimeError, match="has no age yet"):
        a_moment("2026-11-16T00:00:00Z").age_seconds(now())


def test_an_age_needs_an_instant_not_a_datetime():
    with pytest.raises(TimeError, match="measured from an instant"):
        a_moment().age_seconds(datetime(2026, 11, 15))


def test_under_a_minute_is_just_now():
    assert Moment(1_000).age_text(Moment(1_059)) == "just now"


def test_a_minute_is_a_minute():
    assert Moment(1_000).age_text(Moment(1_060)) == "1 min ago"


def test_under_an_hour_counts_minutes():
    assert Moment(1_000).age_text(Moment(1_000 + 3_599)) == "59 min ago"


def test_an_hour_counts_hours():
    assert Moment(1_000).age_text(Moment(1_000 + 3_600)) == "1 h ago"


def test_under_a_day_counts_hours():
    assert Moment(1_000).age_text(Moment(1_000 + 86_399)) == "23 h ago"


def test_a_day_counts_days():
    assert Moment(1_000).age_text(Moment(1_000 + 86_400)) == "1 d ago"


def test_two_thousand_days_counts_days():
    assert Moment(0).age_text(Moment(86_400 * 2_000)) == "2000 d ago"


# --------------------------------------------------------------------------- #
# Reading a timestamp
# --------------------------------------------------------------------------- #
def test_iso_with_z_reads():
    expected = int(datetime(2026, 11, 15, 11, 0, tzinfo=UTC).timestamp())
    assert a_moment("2026-11-15T11:00:00Z").epoch == expected


def test_iso_with_an_offset_reads():
    assert a_moment("2026-11-15T13:00:00+02:00") == \
        a_moment("2026-11-15T11:00:00Z")


def test_iso_with_a_negative_offset_reads():
    assert a_moment("2026-11-15T06:00:00-05:00") == \
        a_moment("2026-11-15T11:00:00Z")


def test_iso_with_a_space_and_a_zone_reads():
    assert a_moment("2026-11-15 11:00:00+00:00") == \
        a_moment("2026-11-15T11:00:00Z")


def test_prose_with_a_named_zone_reads():
    assert a_moment("15 Nov 2026 12:00 UTC") == a_moment("2026-11-15T12:00:00Z")


def test_prose_with_an_offset_reads():
    assert a_moment("13 Nov 2026 18:05 +02:00") == \
        a_moment("2026-11-13T16:05:00Z")


def test_prose_with_seconds_reads():
    assert a_moment("13 Nov 2026 18:05:30 +02:00") == \
        a_moment("2026-11-13T16:05:30Z")


def test_prose_on_a_single_digit_day_reads():
    assert a_moment("1 Mar 2019 00:00 UTC") == a_moment("2019-03-01T00:00:00Z")


def test_hours_ago_is_measured_from_the_reading_time():
    assert a_moment_relative("3 hours ago") == \
        a_moment("2026-11-15T09:00:00Z")


def test_one_hour_ago_is_not_plural():
    assert a_moment_relative("1 hour ago") == \
        a_moment("2026-11-15T11:00:00Z")


def test_minutes_ago_read():
    assert a_moment_relative("20 minutes ago") == \
        a_moment("2026-11-15T11:40:00Z")


def test_weeks_ago_read():
    assert a_moment_relative("2 weeks ago") == \
        a_moment("2026-11-01T12:00:00Z")


def test_seconds_ago_read():
    assert a_moment_relative("1 second ago") == \
        a_moment("2026-11-15T11:59:59Z")


def test_a_relative_phrase_is_case_insensitive():
    assert a_moment_relative("3 Hours Ago") == \
        a_moment_relative("3 hours ago")


def test_yesterday_is_one_day_before_the_reading_time():
    assert a_moment_relative("yesterday") == a_moment("2026-11-14T12:00:00Z")


def test_just_now_is_the_reading_time():
    assert a_moment_relative("just now") == now()


def test_every_curious_text_that_reads_prints_and_parses_back():
    for text, _ in module.CURIOUS:
        try:
            moment = parse_timestamp(text, now())
        except TimeError:
            continue
        assert parse_timestamp(moment.iso()) == moment


def test_an_empty_timestamp_is_refused():
    with pytest.raises(TimeError, match="the timestamp text is empty"):
        parse_timestamp("   ")


def test_a_relative_phrase_needs_a_reading_time():
    with pytest.raises(TimeError, match="needs the moment"):
        parse_timestamp("3 hours ago")


def test_yesterday_needs_a_reading_time():
    with pytest.raises(TimeError, match="needs the moment"):
        parse_timestamp("yesterday")


def test_just_now_needs_a_reading_time():
    with pytest.raises(TimeError, match="needs the moment"):
        parse_timestamp("just now")


def test_a_wall_clock_with_no_zone_is_refused():
    with pytest.raises(TimeError, match="has no zone"):
        parse_timestamp("2026-11-15 10:00:00")


def test_an_iso_value_with_no_zone_is_refused():
    with pytest.raises(TimeError, match="has no zone"):
        parse_timestamp("2026-11-15T10:00:00")


def test_a_day_on_its_own_is_refused():
    with pytest.raises(TimeError, match="names a day"):
        parse_timestamp("2026-11-15")


def test_a_clock_on_its_own_is_refused():
    with pytest.raises(TimeError, match="names a clock"):
        parse_timestamp("09:30")


def test_a_clock_with_seconds_on_its_own_is_refused():
    with pytest.raises(TimeError, match="names a clock"):
        parse_timestamp("09:30:15")


def test_an_iso_shaped_value_that_is_not_a_date_is_refused():
    with pytest.raises(TimeError, match="starts like an ISO date"):
        parse_timestamp("2026-13-45T00:00:00Z")


def test_a_prose_date_that_does_not_exist_is_refused():
    with pytest.raises(TimeError, match="is not a date"):
        parse_timestamp("32 Nov 2026 09:00 UTC")


def test_a_month_this_lab_does_not_know_is_refused():
    with pytest.raises(TimeError, match="is not a month"):
        parse_timestamp("15 Foo 2026 09:00 UTC")


def test_an_unknown_unit_is_refused():
    with pytest.raises(TimeError, match="neither ISO 8601"):
        parse_timestamp("2 fortnights ago", now())


def test_prose_with_no_zone_is_refused():
    with pytest.raises(TimeError, match="neither ISO 8601"):
        parse_timestamp("13 Nov 2026 18:05")


def test_parse_timestamp_refuses_something_that_is_not_text():
    with pytest.raises(TimeError, match="a timestamp is text"):
        parse_timestamp(1_700_000_000)


def test_the_months_are_the_twelve_abbreviations():
    assert len(MONTHS) == 12 and MONTHS[10] == "Nov"


def a_moment_relative(text: str) -> Moment:
    return parse_timestamp(text, now())


# --------------------------------------------------------------------------- #
# The legacy pair
# --------------------------------------------------------------------------- #
def test_the_legacy_parser_reads_its_one_format():
    parsed = legacy_fallback("2026-11-15 10:00:00")
    assert parsed == datetime(2026, 11, 15, 10, 0)


def test_the_legacy_parser_returns_now_for_a_phrase():
    assert legacy_fallback("3 hours ago") > datetime(2020, 1, 1)


def test_the_legacy_parser_returns_now_for_nothing():
    assert legacy_fallback("") > datetime(2020, 1, 1)


def test_the_legacy_parser_returns_now_for_none():
    assert legacy_fallback(None) > datetime(2020, 1, 1)


def test_the_legacy_parser_has_no_zone():
    assert legacy_fallback("2026-11-15 10:00:00").tzinfo is None


def test_the_legacy_age_across_a_missing_zone_is_zero():
    aware = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    naive = datetime(2026, 11, 14, 9, 30)
    assert legacy_age(aware, naive) == 0


def test_the_legacy_age_of_two_aware_datetimes_is_the_difference():
    aware = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    earlier = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)
    assert legacy_age(aware, earlier) == 10_800.0


def test_the_legacy_lines_are_pinned():
    assert LEGACY_FALLBACK.startswith("try:")
    assert "datetime.now()" in LEGACY_FALLBACK
    assert "except TypeError" in LEGACY_AGE
    assert "return 0" in LEGACY_AGE


# --------------------------------------------------------------------------- #
# A feed
# --------------------------------------------------------------------------- #
def test_the_feed_holds_eight_articles():
    assert len(a_feed().articles) == 8


def test_the_feed_is_read_at_the_bundled_moment():
    assert a_feed().read_at == now()
    assert str(a_feed().read_at) == READ_AT


def test_six_articles_have_an_instant():
    assert len(a_feed().known()) == 6


def test_two_articles_have_no_instant():
    assert [article.id for article in a_feed().unknown()] == ["naive", "empty"]


def test_the_naive_article_says_why():
    assert "has no zone" in a_feed().get("naive").note


def test_the_empty_article_says_why():
    assert "is empty" in a_feed().get("empty").note


def test_an_unknown_article_prints_unknown():
    assert a_feed().get("naive").line(now()).lstrip().startswith("naive")


def test_a_note_line_prints_the_text_and_the_reason():
    line = a_feed().get("empty").note_line()
    assert "the timestamp text is empty" in line and "''" in line


def test_the_feed_is_ordered_newest_first_by_instant():
    assert [article.id for article in a_feed().order()] == [
        "iso2", "hours", "yesterday", "iso", "prose", "old"]


def test_the_newest_article_by_instant_is_iso2():
    assert a_feed().newest().id == "iso2"


def test_the_newest_article_by_text_is_something_else():
    by_text = sorted(a_feed().known(),
                     key=lambda article: article.printed)[-1]
    assert by_text.id == "yesterday"


def test_the_feed_is_not_in_file_order():
    assert a_feed().articles[0].id == "iso"
    assert a_feed().order()[0].id == "iso2"


def test_a_feed_line_shows_the_instant_the_age_and_the_title():
    line = a_feed().lines()[0]
    assert line.startswith("iso2")
    assert "2026-11-15T11:00:00Z" in line
    assert "1 h ago" in line
    assert line.endswith("Late result")


def test_the_oldest_line_counts_days():
    assert "2816 d ago" in a_feed().lines()[-1]


def test_every_known_age_is_non_negative():
    assert all(article.moment.age_seconds(now()) >= 0
               for article in a_feed().known())


def test_no_article_is_newer_than_the_reading_time():
    assert all(article.moment.epoch <= now().epoch
               for article in a_feed().known())


def test_get_refuses_an_id_that_is_not_on_the_page():
    with pytest.raises(TimeError, match="no article with id 'nope'"):
        a_feed().get("nope")


def test_a_feed_needs_an_article():
    with pytest.raises(TimeError, match="at least one article"):
        Feed(now(), ())


def test_a_feed_needs_an_instant_to_be_read_at():
    with pytest.raises(TimeError, match="read at an instant"):
        Feed(datetime(2026, 11, 15), (an_article(),))


def test_a_feed_refuses_two_articles_with_one_id():
    article = an_article()
    with pytest.raises(TimeError, match="share an id"):
        Feed(now(), (article, article))


def test_a_feed_can_hold_only_unknown_articles():
    feed = Feed(now(), (Article("x", "x", "", None, "empty"),))
    assert feed.known() == () and feed.newest() is None


def test_the_bundled_file_holds_eight_rows():
    rows = [line for line in FEED_FILE.read_text(encoding="utf-8").split("\n")
            if line.strip() and not line.lstrip().startswith(";")]
    assert len(rows) == 8


# --------------------------------------------------------------------------- #
# Reading the file
# --------------------------------------------------------------------------- #
def test_parse_feed_reads_three_columns():
    feed = parse_feed("a\tA title\t2026-11-15T11:00:00Z\n", now())
    assert feed.articles[0].id == "a"
    assert feed.articles[0].moment == a_moment("2026-11-15T11:00:00Z")


def test_parse_feed_keeps_a_bad_timestamp_as_a_note():
    feed = parse_feed("a\tA title\t09:30\n", now())
    assert feed.articles[0].moment is None
    assert "names a clock" in feed.articles[0].note


def test_parse_feed_skips_a_comment():
    assert len(parse_feed("; note\na\tA\t2026-11-15T11:00:00Z\n", now())) == 1


def test_parse_feed_skips_a_blank_line():
    assert len(parse_feed("\n\na\tA\t2026-11-15T11:00:00Z\n\n", now())) == 1


def test_parse_feed_reads_windows_line_endings():
    text = "a\tA\t2026-11-15T11:00:00Z\r\nb\tB\tyesterday\r\n"
    assert len(parse_feed(text, now())) == 2


def test_parse_feed_refuses_a_line_with_two_fields():
    with pytest.raises(TimeError, match="line 1: expected an id"):
        parse_feed("a\tA title\n", now())


def test_parse_feed_numbers_the_bad_line():
    with pytest.raises(TimeError, match="line 3: expected an id"):
        parse_feed("a\tA\t2026-11-15T11:00:00Z\nb\tB\tyesterday\nc\tC\n",
                   now())


def test_parse_feed_refuses_a_feed_with_no_rows():
    with pytest.raises(TimeError, match="holds no articles"):
        parse_feed("; nothing\n", now())


def test_a_missing_feed_is_refused(tmp_path):
    with pytest.raises(TimeError, match="file not found"):
        module.read_feed(tmp_path / "nope.txt")


def test_read_feed_accepts_its_own_reading_time(tmp_path):
    path = tmp_path / "feed.txt"
    path.write_bytes(b"a\tA\t3 hours ago\n")
    feed = read_feed(path, a_moment("2026-11-15T00:00:00Z"))
    assert feed.articles[0].moment == a_moment("2026-11-14T21:00:00Z")


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every instant is a whole number of seconds",
    "every instant prints as ISO 8601 and reads back to itself",
    "a relative phrase is measured from the supplied moment",
    "the legacy fallback makes an unreadable date look new",
    "the legacy age turns a missing zone into zero seconds",
    "a wall clock with no zone is refused",
    "the feed is ordered by the instant, not by the printed text",
    "an unknown timestamp is unknown and not the epoch",
    "no article is newer than the moment it was read",
]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(a_feed())] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_feed():
    assert problems(audit(a_feed())) == []


def test_the_audit_is_repeatable():
    assert audit(a_feed()) == audit(a_feed())


def test_the_audit_catches_half_a_second():
    feed = Feed(now(), (an_article(moment=raw_moment(1.5)),))
    assert CHECK_NAMES[0] in problems(audit(feed))


def test_the_audit_does_not_raise_on_a_fractional_instant():
    feed = Feed(now(), (an_article(moment=raw_moment(-0.5)),))
    assert len(audit(feed)) == 9


def test_the_audit_catches_an_instant_that_prints_something_else():
    feed = Feed(now(), (an_article(moment=WrongISO(1_763_204_400)),))
    assert CHECK_NAMES[1] in problems(audit(feed))


def test_the_audit_catches_a_reader_that_ignores_the_supplied_moment():
    fixed = now()
    feed = a_feed()
    assert CHECK_NAMES[2] in problems(
        audit(feed, clock=lambda text, moment: parse_timestamp(text, fixed)))


def test_the_audit_catches_a_feed_whose_text_order_is_the_instant_order():
    feed = Feed(now(), (an_article(),))
    assert CHECK_NAMES[6] in problems(audit(feed))


def test_the_audit_catches_a_feed_with_no_unknown_row():
    feed = Feed(now(), (an_article(),))
    assert CHECK_NAMES[7] in problems(audit(feed))


def test_the_audit_catches_an_article_from_the_future():
    feed = Feed(now(), (an_article(
        printed="2026-11-20T00:00:00Z"),))
    assert CHECK_NAMES[8] in problems(audit(feed))


def test_six_of_the_nine_checks_have_a_negative_control():
    """Checks 4, 5 and 6 pin the transcribed legacy lines and the parser."""
    fixed = now()
    broken = [
        audit(Feed(now(), (an_article(moment=raw_moment(1.5)),))),
        audit(Feed(now(), (an_article(moment=WrongISO(1_763_204_400)),))),
        audit(a_feed(), clock=lambda text, moment: parse_timestamp(text,
                                                                   fixed)),
        audit(Feed(now(), (an_article(),))),
        audit(Feed(now(), (an_article(printed="2026-11-20T00:00:00Z"),))),
    ]
    caught = {name for checks in broken for name in problems(checks)}
    assert len(caught) == 6


# --------------------------------------------------------------------------- #
# The curious texts
# --------------------------------------------------------------------------- #
def test_the_curious_texts_are_all_ascii():
    assert all(ord(character) < 128
               for text, _ in module.CURIOUS for character in text)


def test_the_curious_table_holds_thirteen_texts():
    assert len(module.CURIOUS) == 13


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
    assert 'datetime.strptime(value, "%Y-%m-%d %H:%M:%S")' in out
    assert "return datetime.now()" in out
    assert "except TypeError" in out


def test_demo_shows_the_reading_time(capsys):
    run_demo()
    assert "the page is read at 2026-11-15T12:00:00Z" in \
        capsys.readouterr().out


def test_demo_shows_the_hours_phrase_read_from_the_reading_time(capsys):
    run_demo()
    assert "2026-11-15T09:00:00Z   3 h ago" in capsys.readouterr().out


def test_demo_shows_the_two_orders_disagreeing(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "by the instant: iso2" in out
    assert "by the text:    yesterday" in out
    assert "the same article: False" in out


def test_demo_shows_the_legacy_age_as_zero(capsys):
    run_demo()
    assert "legacy_age(aware, naive) = 0.0 s" in capsys.readouterr().out


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


def test_cli_reads_the_bundled_feed(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "read at 2026-11-15T12:00:00Z: 8 article(s)" in out
    assert "2026-11-15T11:00:00Z" in out
    assert "newest by instant: iso2" in out
    assert "newest by text:    yesterday" in out


def test_cli_reads_one_timestamp(capsys):
    assert cli.main(["--timestamp", "2026-11-15T11:00:00Z"]) == 0
    out = capsys.readouterr().out
    assert "'2026-11-15T11:00:00Z' is 2026-11-15T11:00:00Z" in out
    assert "that is 1 h ago" in out


def test_cli_resolves_a_relative_phrase_against_the_reading_time(capsys):
    assert cli.main(["--timestamp", "3 hours ago"]) == 0
    assert "2026-11-15T09:00:00Z" in capsys.readouterr().out


def test_cli_accepts_its_own_reading_time(capsys):
    assert cli.main(["--at", "2026-11-15T00:00:00Z", "--timestamp",
                     "3 hours ago"]) == 0
    assert "2026-11-14T21:00:00Z" in capsys.readouterr().out


def test_cli_a_timestamp_it_cannot_read_exits_two(capsys):
    assert cli.main(["--timestamp", "09:30"]) == 2
    assert "names a clock" in capsys.readouterr().err


def test_cli_a_reading_time_it_cannot_read_exits_two(capsys):
    assert cli.main(["--at", "midnight"]) == 2
    assert "neither ISO 8601" in capsys.readouterr().err


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_writes_the_reading_as_json(tmp_path, capsys):
    target = tmp_path / "reading.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["read_at"] == READ_AT
    assert payload["order"] == ["iso2", "hours", "yesterday", "iso", "prose",
                               "old"]
    assert payload["unknown"] == ["naive", "empty"]
    assert payload["articles"][2]["age"] == "3 h ago"
    assert payload["articles"][3]["moment"] is None
    assert "has no zone" in payload["articles"][3]["note"]


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_missing_feed_exits_two(tmp_path, capsys):
    assert cli.main(["--feed", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_malformed_feed_exits_two(tmp_path, capsys):
    path = tmp_path / "feed.txt"
    path.write_bytes(b"a\tA title\n")
    assert cli.main(["--feed", str(path)]) == 2
    assert "expected an id" in capsys.readouterr().err
