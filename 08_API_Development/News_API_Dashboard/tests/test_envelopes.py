"""Tests for News_API_Dashboard: an empty list is not an answer, and a status
code is only half of the response."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                           # noqa: E402
import envelopes as module                                  # noqa: E402
from envelopes import (                                     # noqa: E402
    KINDS,
    LEGACY_ARTICLES,
    NOTE_LIMIT,
    RESPONSES_FILE,
    Article,
    Bundle,
    Outcome,
    Response,
    ResponseError,
    audit,
    classify,
    legacy_articles,
    legacy_of,
    legacy_read,
    parse_article,
    parse_responses,
    problems,
    read_all,
    read_bundle,
    run_demo,
)

BUNDLE, RESPONSES = read_all()
TEXT = RESPONSES_FILE.read_text(encoding="utf-8")


def an_article(title: str = "Rates hold steady", source: str = "wire") -> Article:
    return Article(title, source)


def an_outcome(name: str = "ok", status: int = 200, kind: str = "ok",
               rows=None, total: int | None = 3,
               note: str = "all of them arrived") -> Outcome:
    if rows is None:
        rows = (tuple(an_article() for _ in range(total or 0))
                if kind == "ok" else ())
    return Outcome(name, status, kind, tuple(rows), total, note)


def corrupted(outcome: Outcome, **fields) -> Outcome:
    """The same outcome with one field replaced, past the constructor.

    A negative control has to be an outcome that is wrong in exactly the way a
    check is looking for, and `Outcome` refuses to be built wrong on purpose --
    so the control is written straight over the frozen instance.
    """
    clone = object.__new__(Outcome)
    for field in ("name", "status", "kind", "rows", "total", "note"):
        object.__setattr__(clone, field,
                           fields.get(field, getattr(outcome, field)))
    return clone


def with_field(name: str, **fields) -> Bundle:
    """The real bundle with one named outcome's fields replaced."""
    return Bundle(tuple(corrupted(outcome, **fields)
                        if outcome.name == name else outcome
                        for outcome in BUNDLE.outcomes))


def a_response(name: str = "ok", status: int = 200,
               body: str = '{"articles": [], "totalResults": 0}') -> Response:
    return Response(name, status, body)


def a_body(articles, total=0, status="ok") -> str:
    return json.dumps({"status": status, "totalResults": total,
                       "articles": articles})


# --------------------------------------------------------------------------- #
# An article
# --------------------------------------------------------------------------- #
def test_an_article_holds_a_title_and_a_source():
    assert (an_article().title, an_article().source) == ("Rates hold steady",
                                                         "wire")


def test_an_article_prints_its_title_and_source():
    assert str(an_article()) == "Rates hold steady (wire)"


def test_an_article_with_no_source_prints_only_its_title():
    assert str(an_article(source="")) == "Rates hold steady"


def test_an_empty_title_is_refused():
    with pytest.raises(ResponseError, match="a title needs a value"):
        an_article(title="  ")


def test_a_title_that_is_not_text_is_refused():
    with pytest.raises(ResponseError, match="a title is text"):
        an_article(title=7)


def test_a_source_that_is_not_text_is_refused():
    with pytest.raises(ResponseError, match="a source is text"):
        an_article(source=7)


def test_an_article_row_is_read_from_a_title():
    assert parse_article({"title": "A"}).title == "A"


def test_an_article_row_keeps_its_source():
    assert parse_article({"title": "A", "source": "wire"}).source == "wire"


def test_an_article_row_reads_a_nested_source_object():
    assert parse_article({"title": "A", "source": {"name": "wire"}}).source \
        == "wire"


def test_an_article_row_with_no_source_is_read():
    assert parse_article({"title": "A"}).source == ""


def test_an_article_row_with_no_title_is_refused():
    with pytest.raises(ResponseError, match="carries no 'title'"):
        parse_article({"source": "wire"})


def test_an_article_row_that_is_not_an_object_is_refused():
    with pytest.raises(ResponseError, match="is a JSON object"):
        parse_article("A")


# --------------------------------------------------------------------------- #
# A response
# --------------------------------------------------------------------------- #
def test_a_response_holds_a_name_a_status_and_a_body():
    response = a_response()
    assert (response.name, response.status) == ("ok", 200)


def test_a_response_line_shows_the_status_and_the_body():
    assert a_response(body="{}").line() == "HTTP 200  {}"


def test_a_response_with_no_name_is_refused():
    with pytest.raises(ResponseError, match="a response name needs a value"):
        a_response(name=" ")


def test_a_status_below_a_hundred_is_refused():
    with pytest.raises(ResponseError, match="a status is at least 100"):
        a_response(status=99)


def test_a_status_above_five_ninety_nine_is_refused():
    with pytest.raises(ResponseError, match="a status is at most 599"):
        a_response(status=600)


def test_a_status_that_is_not_a_whole_number_is_refused():
    with pytest.raises(ResponseError, match="a status is a whole number"):
        a_response(status=200.0)


def test_a_body_that_is_not_text_is_refused():
    with pytest.raises(ResponseError, match="a body is text"):
        a_response(body={})


# --------------------------------------------------------------------------- #
# An outcome
# --------------------------------------------------------------------------- #
def test_an_outcome_holds_its_kind_and_its_rows():
    outcome = an_outcome()
    assert outcome.kind == "ok" and outcome.total == 3


def test_an_outcome_counts_its_rows():
    assert len(an_outcome(rows=(an_article(), ), total=1)) == 1


def test_an_outcome_is_ok_only_when_it_is():
    assert an_outcome().is_ok() is True
    assert an_outcome(kind="empty", rows=(), total=0).is_ok() is False


def test_an_outcome_with_rows_has_rows():
    assert an_outcome(rows=(an_article(),), total=1).has_rows() is True


def test_an_outcome_without_rows_has_none():
    assert an_outcome(kind="empty", rows=(), total=0).has_rows() is False


def test_a_partial_outcome_reports_its_shortfall():
    outcome = an_outcome(kind="partial", rows=(an_article(), an_article()),
                         total=20)
    assert outcome.shortfall() == 18


def test_an_ok_outcome_has_no_shortfall():
    assert an_outcome(rows=(an_article(),), total=1).shortfall() == 0


def test_an_error_outcome_with_no_total_has_no_shortfall():
    outcome = an_outcome(kind="error", rows=(), total=None)
    assert outcome.shortfall() == 0


def test_an_outcome_names_its_titles():
    outcome = an_outcome(rows=(an_article("A"), an_article("B")), total=2)
    assert outcome.titles() == ("A", "B")


def test_an_outcome_line_names_the_status_the_kind_and_the_note():
    outcome = an_outcome(rows=(an_article(),), total=1,
                         note="all 1 article(s) arrived")
    assert outcome.line() == ("ok             HTTP 200 ok         1/1   "
                              "all 1 article(s) arrived")


def test_an_outcome_sentence_is_one_line():
    outcome = an_outcome(rows=(an_article(),), total=1, note="fine")
    assert outcome.sentence() == ("ok: HTTP 200, ok, 1 article(s) of 1, fine")


def test_an_outcome_of_an_unknown_kind_is_refused():
    with pytest.raises(ResponseError, match="an outcome is one of"):
        an_outcome(kind="fine")


def test_an_outcome_with_no_note_is_refused():
    with pytest.raises(ResponseError, match="needs the sentence"):
        an_outcome(note="   ")


def test_an_outcome_with_more_rows_than_its_total_is_refused():
    with pytest.raises(ResponseError, match="reports a total of 1"):
        an_outcome(rows=(an_article(), an_article()), total=1)


def test_an_ok_outcome_needs_a_total():
    with pytest.raises(ResponseError, match="needs a total"):
        an_outcome(total=None)


def test_an_ok_outcome_whose_total_disagrees_is_refused():
    with pytest.raises(ResponseError, match="is ok but holds 0 of 3"):
        an_outcome(rows=(), total=3)


def test_an_empty_outcome_with_rows_is_refused():
    with pytest.raises(ResponseError, match="is empty but holds"):
        an_outcome(kind="empty", rows=(an_article(),), total=1)


def test_a_partial_outcome_with_every_row_is_refused():
    with pytest.raises(ResponseError, match="is partial but holds"):
        an_outcome(kind="partial", rows=(an_article(),), total=1)


def test_an_outcome_row_that_is_not_an_article_is_refused():
    with pytest.raises(ResponseError, match="a row is an article"):
        an_outcome(rows=("A",), total=1)


def test_the_kinds_are_five():
    assert KINDS == ("ok", "empty", "partial", "error", "malformed")


# --------------------------------------------------------------------------- #
# Classifying
# --------------------------------------------------------------------------- #
def test_a_full_page_of_articles_is_ok():
    body = a_body([{"title": "A"}, {"title": "B"}], total=2)
    outcome = classify(Response("ok", 200, body))
    assert outcome.kind == "ok" and len(outcome) == 2


def test_an_ok_outcome_says_how_many_arrived():
    body = a_body([{"title": "A"}], total=1)
    assert "all 1 article(s) arrived" in classify(Response("ok", 200,
                                                           body)).note


def test_an_empty_list_with_a_zero_total_is_empty():
    outcome = classify(Response("empty", 200, a_body([], total=0)))
    assert outcome.kind == "empty" and outcome.total == 0


def test_two_of_twenty_is_partial():
    body = a_body([{"title": "A"}, {"title": "B"}], total=20)
    outcome = classify(Response("part", 200, body))
    assert outcome.kind == "partial" and outcome.shortfall() == 18


def test_a_partial_outcome_keeps_the_rows_it_did_get():
    body = a_body([{"title": "A"}], total=3)
    assert classify(Response("part", 200, body)).titles() == ("A",)


def test_a_not_found_is_an_error():
    body = json.dumps({"status": "error", "message": "Nothing matches."})
    assert classify(Response("gone", 404, body)).kind == "error"


def test_a_not_found_keeps_its_message():
    body = json.dumps({"status": "error", "message": "Nothing matches."})
    assert "Nothing matches." in classify(Response("gone", 404, body)).note


def test_a_rate_limit_is_an_error():
    body = json.dumps({"status": "error", "message": "Slow down."})
    assert classify(Response("slow", 429, body)).kind == "error"


def test_a_rate_limit_keeps_its_message():
    body = json.dumps({"status": "error", "message": "Slow down."})
    assert "Slow down." in classify(Response("slow", 429, body)).note


def test_an_error_body_with_no_message_names_its_code():
    body = json.dumps({"status": "error", "code": "rateLimited"})
    note = classify(Response("slow", 429, body)).note
    assert "rateLimited" in note


def test_an_error_with_a_body_that_is_not_json_quotes_the_body():
    outcome = classify(Response("bad", 500, "<html>Down</html>"))
    assert outcome.kind == "error" and "Down" in outcome.note


def test_a_200_whose_body_says_error_is_an_error():
    body = json.dumps({"status": "error", "message": "Not satisfied."})
    outcome = classify(Response("proxy", 200, body))
    assert outcome.kind == "error" and "Not satisfied." in outcome.note


def test_a_200_with_a_broken_body_is_malformed():
    outcome = classify(Response("cut", 200, '{"articles": [{"title": "A'))
    assert outcome.kind == "malformed" and "not JSON" in outcome.note


def test_a_broken_body_names_the_character_it_stopped_at():
    outcome = classify(Response("cut", 200, '{"articles": ['))
    assert "at character" in outcome.note


def test_a_body_that_is_not_an_object_is_malformed():
    outcome = classify(Response("list", 200, "[1, 2]"))
    assert outcome.kind == "malformed" and "a JSON object" in outcome.note


def test_a_body_with_no_articles_key_is_malformed():
    body = json.dumps({"status": "ok", "totalResults": 0})
    outcome = classify(Response("none", 200, body))
    assert outcome.kind == "malformed" and "no 'articles' field" in outcome.note


def test_a_null_articles_field_is_malformed_not_empty():
    body = json.dumps({"status": "ok", "totalResults": 1, "articles": None})
    outcome = classify(Response("null", 200, body))
    assert outcome.kind == "malformed" and "null is not an empty list" in \
        outcome.note


def test_a_total_that_is_not_a_number_is_malformed():
    body = json.dumps({"status": "ok", "totalResults": "3", "articles": []})
    outcome = classify(Response("odd", 200, body))
    assert outcome.kind == "malformed" and "'totalResults'" in outcome.note


def test_a_row_with_no_title_is_malformed():
    body = a_body([{"source": "wire"}], total=1)
    outcome = classify(Response("odd", 200, body))
    assert outcome.kind == "malformed" and "article 1" in outcome.note


def test_more_rows_than_the_total_is_malformed():
    body = a_body([{"title": "A"}, {"title": "B"}], total=1)
    outcome = classify(Response("odd", 200, body))
    assert outcome.kind == "malformed" and "reports a total of 1" in outcome.note


def test_a_partial_body_with_no_rows_still_reports_the_total():
    body = a_body([], total=5)
    outcome = classify(Response("part", 200, body))
    assert outcome.kind == "partial" and outcome.total == 5


def test_classifying_something_that_is_not_a_response_is_refused():
    with pytest.raises(ResponseError, match="needs a response"):
        classify("HTTP 200")


def test_a_three_digit_status_of_204_is_not_an_error():
    outcome = classify(Response("no-content", 204, a_body([], total=0)))
    assert outcome.kind == "empty"


# --------------------------------------------------------------------------- #
# The legacy reader
# --------------------------------------------------------------------------- #
def test_the_legacy_reader_returns_the_articles():
    assert legacy_articles({"articles": [1, 2]}) == [1, 2]


def test_the_legacy_reader_answers_empty_for_a_missing_key():
    assert legacy_articles({"totalResults": 0}) == []


def test_the_legacy_reader_answers_empty_for_a_rate_limit():
    assert legacy_articles({"status": "error", "code": "rateLimited"}) == []


def test_the_legacy_reader_answers_empty_for_a_not_found():
    assert legacy_articles({"message": "Nothing matches."}) == []


def test_the_legacy_reader_answers_empty_for_a_genuinely_empty_result():
    assert legacy_articles({"articles": [], "totalResults": 0}) == []


def test_the_legacy_reader_hands_back_none_for_a_null():
    assert legacy_articles({"articles": None}) is None


def test_the_legacy_reader_answers_empty_for_a_list_payload():
    assert legacy_articles([1, 2]) == []


def test_the_legacy_read_parses_a_body():
    assert legacy_read('{"articles": [1]}') == [1]


def test_the_legacy_read_raises_on_a_body_that_is_not_json():
    with pytest.raises(json.JSONDecodeError):
        legacy_read("<html>")


def test_the_legacy_lines_are_pinned():
    assert 'payload["articles"]' in LEGACY_ARTICLES
    assert "return []" in LEGACY_ARTICLES


def test_legacy_of_records_a_crash_rather_than_raising():
    assert legacy_of(("<html>", '{"articles": []}')) == ("crash", [])


def test_legacy_of_keeps_none_apart_from_empty():
    assert legacy_of(('{"articles": null}', '{"articles": []}')) == (None, [])


# --------------------------------------------------------------------------- #
# Reading the bundle
# --------------------------------------------------------------------------- #
def test_parse_responses_reads_the_ten_bodies():
    assert len(parse_responses(TEXT)) == 10


def test_parse_responses_reads_a_status():
    assert parse_responses(TEXT)[0].status == 200


def test_parse_responses_reads_a_rate_limit_status():
    assert parse_responses(TEXT)[3].status == 429


def test_parse_responses_keeps_a_multiline_body():
    body = parse_responses(TEXT)[0].body
    assert "\n" in body and body.startswith('{"status"')


def test_parse_responses_skips_a_comment():
    assert len(parse_responses("; note\n--- a\nHTTP 200\n{}\n")) == 1


def test_parse_responses_skips_a_blank_line():
    assert len(parse_responses("\n--- a\nHTTP 200\n{}\n\n")) == 1


def test_parse_responses_reads_windows_line_endings():
    text = "--- a\r\nHTTP 200\r\n{}\r\n--- b\r\nHTTP 500\r\n{}\r\n"
    assert len(parse_responses(text)) == 2


def test_parse_responses_refuses_a_body_before_a_header():
    with pytest.raises(ResponseError, match="before the first"):
        parse_responses("HTTP 200\n{}\n")


def test_parse_responses_refuses_a_header_with_no_name():
    with pytest.raises(ResponseError, match="needs a name"):
        parse_responses("---\nHTTP 200\n{}\n")


def test_parse_responses_refuses_a_block_with_no_status_line():
    with pytest.raises(ResponseError, match="has no status line"):
        parse_responses("--- a\n\n--- b\nHTTP 200\n{}\n")


def test_parse_responses_refuses_a_first_line_that_is_not_a_status():
    with pytest.raises(ResponseError, match="not 'HTTP <status>'"):
        parse_responses("--- a\nGET 200\n{}\n")


def test_parse_responses_refuses_a_status_that_is_not_a_number():
    with pytest.raises(ResponseError, match="where the status belongs"):
        parse_responses("--- a\nHTTP ok\n{}\n")


def test_parse_responses_refuses_a_block_with_no_body():
    with pytest.raises(ResponseError, match="has no body"):
        parse_responses("--- a\nHTTP 200\n\n--- b\nHTTP 200\n{}\n")


def test_parse_responses_refuses_a_bundle_with_no_responses():
    with pytest.raises(ResponseError, match="holds no responses"):
        parse_responses("; nothing\n")


def test_a_missing_bundle_is_refused(tmp_path):
    with pytest.raises(ResponseError, match="file not found"):
        module.read_all(tmp_path / "nope.txt")


def test_read_all_returns_the_bundle_and_the_responses(tmp_path):
    path = tmp_path / "responses.txt"
    path.write_bytes(b"--- a\nHTTP 200\n{\"articles\": [], "
                     b"\"totalResults\": 0}\n")
    bundle, responses = read_all(path)
    assert len(bundle) == 1 and len(responses) == 1


# --------------------------------------------------------------------------- #
# A bundle
# --------------------------------------------------------------------------- #
def test_the_bundle_holds_ten_outcomes():
    assert len(BUNDLE) == 10


def test_one_response_is_ok():
    assert len(BUNDLE.of_kind("ok")) == 1


def test_one_response_is_a_legitimate_empty_result():
    assert len(BUNDLE.of_kind("empty")) == 1


def test_one_response_is_partial():
    assert len(BUNDLE.of_kind("partial")) == 1


def test_four_responses_are_errors():
    assert len(BUNDLE.of_kind("error")) == 4


def test_three_responses_are_malformed():
    assert len(BUNDLE.of_kind("malformed")) == 3


def test_the_bundle_counts_every_kind():
    assert BUNDLE.counts() == {"ok": 1, "empty": 1, "partial": 1,
                               "error": 4, "malformed": 3}


def test_by_name_finds_a_response():
    assert BUNDLE.by_name("not-found").status == 404


def test_by_name_refuses_a_name_that_is_not_there():
    with pytest.raises(ResponseError, match="no response named"):
        BUNDLE.by_name("nope")


def test_of_kind_refuses_a_kind_that_is_not_one():
    with pytest.raises(ResponseError, match="a kind is one of"):
        BUNDLE.of_kind("fine")


def test_only_the_outcomes_with_rows_have_them():
    assert len(BUNDLE.with_rows()) == 2


def test_the_bundle_lines_are_one_per_response():
    assert len(BUNDLE.lines()) == 10


def test_a_bundle_needs_a_response():
    with pytest.raises(ResponseError, match="needs at least one"):
        Bundle(())


def test_a_bundle_refuses_two_responses_with_one_name():
    with pytest.raises(ResponseError, match="share a name"):
        Bundle((an_outcome(), an_outcome(rows=(an_article(),), total=1)))


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every outcome names a status and a kind",
    "the five empty lists are five different facts",
    "a 404 keeps the sentence that explains it",
    "a 429 keeps its message too",
    "a 200 whose body says error is an error",
    "a genuinely empty result is empty, not an error",
    "a partial answer reports the shortfall it has",
    "three malformed bodies carry three different reasons",
    "the legacy reader answers five empty lists and one None",
    "the legacy reader crashes on two bodies",
    "every outcome with rows reports a total that holds them",
]


def real_checks():
    return audit(BUNDLE, RESPONSES)


def test_the_audit_holds_eleven_named_checks():
    assert [name for name, _ in real_checks()] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_responses():
    assert problems(real_checks()) == []


def test_the_audit_is_repeatable():
    assert real_checks() == real_checks()


def test_the_audit_catches_an_outcome_of_no_kind():
    checks = audit(with_field("ok", kind="fine"), RESPONSES)
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_two_empty_lists_with_one_note():
    flat = Bundle(tuple(
        corrupted(outcome, note="it did not arrive")
        if outcome.name in ("rate-limited", "not-found") else outcome
        for outcome in BUNDLE.outcomes))
    assert CHECK_NAMES[1] in problems(audit(flat, RESPONSES))


def test_the_audit_catches_a_404_that_lost_its_message():
    flat = with_field("not-found", note="HTTP 404, and no message")
    assert CHECK_NAMES[2] in problems(audit(flat, RESPONSES))


def test_the_audit_catches_a_rate_limit_with_no_message():
    flat = with_field("rate-limited", note="HTTP 429")
    assert CHECK_NAMES[3] in problems(audit(flat, RESPONSES))


def test_the_audit_catches_a_200_error_body_taken_as_a_success():
    flat = with_field("proxy-200-error", kind="empty", total=0, rows=(),
                      note="nothing matched")
    assert CHECK_NAMES[4] in problems(audit(flat, RESPONSES))


def test_the_audit_catches_an_empty_result_called_an_error():
    flat = with_field("empty", kind="error", total=None, note="no articles")
    assert CHECK_NAMES[5] in problems(audit(flat, RESPONSES))


def test_the_audit_catches_a_partial_answer_with_the_wrong_total():
    flat = with_field("partial", total=3)
    assert CHECK_NAMES[6] in problems(audit(flat, RESPONSES))


def test_the_audit_catches_three_malformed_bodies_with_one_reason():
    flat = Bundle(tuple(
        corrupted(outcome, note="it could not be read")
        if outcome.kind == "malformed" else outcome
        for outcome in BUNDLE.outcomes))
    assert CHECK_NAMES[7] in problems(audit(flat, RESPONSES))


def test_the_audit_catches_a_legacy_answer_with_no_empty_list():
    assert CHECK_NAMES[8] in problems(audit(BUNDLE, (RESPONSES[0],)))


def test_the_audit_catches_a_bundle_of_parseable_bodies_only():
    parseable = tuple(response for response in RESPONSES
                      if response.name not in ("server-error", "truncated"))
    assert CHECK_NAMES[9] in problems(audit(BUNDLE, parseable))


def test_the_audit_catches_an_outcome_with_rows_beyond_its_total():
    flat = with_field("ok", total=2)
    assert CHECK_NAMES[10] in problems(audit(flat, RESPONSES))


def test_every_check_has_a_negative_control():
    """Eleven broken bundles, and every check is named by at least one of them."""
    flat_notes = Bundle(tuple(
        corrupted(outcome, note="it did not arrive")
        if outcome.name in ("rate-limited", "not-found") else outcome
        for outcome in BUNDLE.outcomes))
    flat_malformed = Bundle(tuple(
        corrupted(outcome, note="it could not be read")
        if outcome.kind == "malformed" else outcome
        for outcome in BUNDLE.outcomes))
    parseable = tuple(response for response in RESPONSES
                      if response.name not in ("server-error", "truncated"))

    broken = [
        (with_field("ok", kind="fine"), RESPONSES),
        (flat_notes, RESPONSES),
        (with_field("not-found", note="HTTP 404, and no message"), RESPONSES),
        (with_field("rate-limited", note="HTTP 429"), RESPONSES),
        (with_field("proxy-200-error", kind="empty", total=0, rows=(),
                    note="nothing matched"), RESPONSES),
        (with_field("empty", kind="error", total=None, note="no articles"),
         RESPONSES),
        (with_field("partial", total=3), RESPONSES),
        (flat_malformed, RESPONSES),
        (BUNDLE, (RESPONSES[0],)),
        (BUNDLE, parseable),
        (with_field("ok", total=2), RESPONSES),
    ]
    caught = {name for bundle, responses in broken
              for name in problems(audit(bundle, responses))}
    assert caught == set(CHECK_NAMES)


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


def test_demo_shows_the_legacy_reader(capsys):
    run_demo()
    assert 'payload["articles"]' in capsys.readouterr().out


def test_demo_shows_the_ok_row(capsys):
    run_demo()
    assert "ok             HTTP 200 ok         3/3" in capsys.readouterr().out


def test_demo_shows_the_partial_row(capsys):
    run_demo()
    assert "partial    2/20" in capsys.readouterr().out


def test_demo_shows_the_five_empty_lists(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert ("5 bodies came back as exactly []: empty, rate-limited, "
            "not-found, no-articles, proxy-200-error") in out


def test_demo_shows_the_five_facts_behind_one_list(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "the five facts behind one []" in out
    assert "Nothing matches your query." in out


def test_demo_shows_the_null_as_none(capsys):
    run_demo()
    assert "null-articles  None, which is not a list" in \
        capsys.readouterr().out


def test_demo_shows_the_crash(capsys):
    run_demo()
    assert "server-error   json.loads raised before it could answer" in \
        capsys.readouterr().out


def test_demo_shows_all_eleven_checks(capsys):
    run_demo()
    assert "11/11 checks pass" in capsys.readouterr().out


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


def test_cli_lists_every_response(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "10 response(s): 1 ok, 1 empty, 1 partial, 4 error, 3 malformed" in out
    assert "not-found" in out


def test_cli_names_the_legacy_empty_lists(capsys):
    assert cli.main([]) == 0
    assert "answers exactly [] for 5 of them" in capsys.readouterr().out


def test_cli_filters_by_kind(capsys):
    assert cli.main(["--kind", "error"]) == 0
    out = capsys.readouterr().out
    assert "rate-limited" in out and "truncated" not in out


def test_cli_reads_one_response_by_name(capsys):
    assert cli.main(["--name", "partial"]) == 0
    out = capsys.readouterr().out
    assert "2 article(s) of 20" in out


def test_cli_an_error_response_exits_two(capsys):
    assert cli.main(["--name", "not-found"]) == 2
    assert "Nothing matches your query." in capsys.readouterr().out


def test_cli_an_unknown_name_exits_two(capsys):
    assert cli.main(["--name", "nope"]) == 2
    assert "no response named" in capsys.readouterr().err


def test_cli_classifies_one_body(capsys):
    body = a_body([{"title": "A"}], total=1)
    assert cli.main(["--body", body]) == 0
    out = capsys.readouterr().out
    assert "ok" in out and "the legacy reader answers" in out


def test_cli_classifies_a_body_with_its_status(capsys):
    assert cli.main(["--body", "<html>", "--status", "500"]) == 2
    assert "HTTP 500" in capsys.readouterr().out


def test_cli_a_body_that_cannot_be_read_exits_two(capsys):
    assert cli.main(["--body", '{"articles": null}']) == 2
    assert "null is not an empty list" in capsys.readouterr().err


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 11 and "FAIL" not in out


def test_cli_writes_the_outcomes_as_json(tmp_path, capsys):
    target = tmp_path / "outcomes.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["counts"] == {"ok": 1, "empty": 1, "partial": 1,
                                 "error": 4, "malformed": 3}
    assert payload["outcomes"][0]["kind"] == "ok"
    assert payload["outcomes"][0]["titles"] == ["Rates hold steady",
                                                "Chips rally again",
                                                "Oil slips on supply"]
    assert payload["outcomes"][2]["shortfall"] == 18
    assert payload["outcomes"][3]["status"] == 429
    assert payload["outcomes"][4]["note"].endswith("Nothing matches your query.")
    legacy = {row["name"]: row for row in payload["legacy"]}
    assert legacy["empty"]["value"] == []
    assert legacy["null-articles"]["value"] is None
    assert legacy["server-error"]["crashed"] is True


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_missing_bundle_exits_two(tmp_path, capsys):
    assert cli.main(["--responses", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_malformed_bundle_exits_two(tmp_path, capsys):
    path = tmp_path / "responses.txt"
    path.write_bytes(b"--- a\nGET 200\n{}\\n")
    assert cli.main(["--responses", str(path)]) == 2
    assert "not 'HTTP <status>'" in capsys.readouterr().err


def test_cli_an_audit_that_fails_exits_one(tmp_path, capsys):
    path = tmp_path / "responses.txt"
    path.write_bytes(b'--- ok\nHTTP 200\n{"status": "ok", "totalResults": 1, '
                     b'"articles": [{"title": "A"}]}\n')
    assert cli.main(["--responses", str(path), "--audit"]) == 1
    out, err = capsys.readouterr()
    assert "FAIL" in out and "check(s) failed" in err
