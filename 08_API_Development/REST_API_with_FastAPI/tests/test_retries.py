"""Tests for REST_API_with_FastAPI: a retried POST is a second POST unless it
carries a key the server can dedupe on."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                           # noqa: E402
import retries as module                                    # noqa: E402
from retries import (                                       # noqa: E402
    BACKOFF_CAP,
    LEGACY_POST,
    MAX_TRIES,
    ORDER_FILE,
    OUTCOMES,
    SCENARIOS,
    TRIES,
    Order,
    Reply,
    RetryError,
    Run,
    Server,
    Store,
    Token,
    audit,
    backoff_delays,
    legacy_post,
    offset_for,
    parse_order,
    post_with_key,
    problems,
    read_order,
    run_demo,
    run_pair,
    script_for,
    start_for,
)

ORDER, TOKEN, NOW = read_order()
KEY = "order-7f3a"


def a_token(issued: int = 0, lifetime: int = 60) -> Token:
    return Token(issued, lifetime)


def an_order(quantity: int = 3, unit_cents: int = 4499) -> Order:
    return Order(quantity, unit_cents)


def a_reply(status: int = 201, order_id: int | None = 1,
            detail: str = "the order was created") -> Reply:
    return Reply(status, order_id, detail)


def a_run(mode: str = "keyed", outcome: str = "created",
          order_id: int | None = 1, replies=None, waited: int = 0,
          rows: int = 1) -> Run:
    return Run(mode, outcome, order_id,
               tuple(replies) if replies is not None else (a_reply(),),
               waited, rows)


def corrupted_run(run: Run, **fields) -> Run:
    """The same run with one field replaced, past the constructor."""
    clone = object.__new__(Run)
    for field in ("mode", "outcome", "order_id", "replies", "waited", "rows"):
        object.__setattr__(clone, field,
                           fields.get(field, getattr(run, field)))
    return clone


def demo_runs() -> dict[str, tuple[Run, Run]]:
    """Both loops over every scenario, exactly as the demo makes them."""
    runs = {}
    for name, script, offset in SCENARIOS:
        start = start_for(TOKEN, NOW, offset)
        runs[name] = run_pair(ORDER, TOKEN, NOW, script, start)
    return runs


def real_checks():
    return audit(demo_runs(), ORDER, backoff_delays(MAX_TRIES), Store)


# --------------------------------------------------------------------------- #
# A token
# --------------------------------------------------------------------------- #
def test_a_token_holds_an_issue_time_and_a_lifetime():
    assert (a_token().issued, a_token().lifetime) == (0, 60)


def test_a_token_expires_when_its_lifetime_runs_out():
    assert a_token().expires_at() == 60


def test_a_token_is_valid_at_the_second_it_was_issued():
    assert a_token().valid_at(0) is True


def test_a_token_is_valid_one_second_before_it_expires():
    assert a_token().valid_at(59) is True


def test_a_token_is_not_valid_at_the_second_it_expires():
    assert a_token().valid_at(60) is False


def test_a_token_is_not_valid_before_it_was_issued():
    assert a_token(issued=10, lifetime=5).valid_at(9) is False


def test_a_token_reports_the_seconds_it_has_left():
    assert a_token().remaining_at(15) == 45


def test_a_token_with_no_time_left_reports_zero_rather_than_negative():
    assert a_token().remaining_at(90) == 0


def test_a_token_line_names_both_ends_of_its_window():
    assert a_token().line() == "token good from 0 to 59 (60 second(s))"


def test_a_negative_issue_time_is_refused():
    with pytest.raises(RetryError, match="an issue time is at least 0"):
        a_token(issued=-1)


def test_a_lifetime_of_zero_is_refused():
    with pytest.raises(RetryError, match="a lifetime is at least 1"):
        a_token(lifetime=0)


def test_a_lifetime_that_is_not_a_whole_number_is_refused():
    with pytest.raises(RetryError, match="a lifetime is a whole number"):
        a_token(lifetime=60.0)


def test_a_moment_that_is_not_a_whole_number_is_refused():
    with pytest.raises(RetryError, match="a moment is a whole number"):
        a_token().valid_at(1.5)


# --------------------------------------------------------------------------- #
# An order
# --------------------------------------------------------------------------- #
def test_an_order_multiplies_quantity_by_a_unit_price_in_cents():
    assert an_order().total_cents() == 13497


def test_an_order_line_is_whole_numbers_only():
    assert an_order().line() == "3 x 4499 cents = 13497 cents"


def test_a_quantity_of_zero_is_refused():
    with pytest.raises(RetryError, match="a quantity is at least 1"):
        an_order(quantity=0)


def test_a_negative_unit_price_is_refused():
    with pytest.raises(RetryError, match="a unit price is at least 0"):
        an_order(unit_cents=-1)


def test_a_unit_price_that_is_not_a_whole_number_is_refused():
    with pytest.raises(RetryError, match="a unit price is a whole number"):
        an_order(unit_cents=44.99)


# --------------------------------------------------------------------------- #
# A reply
# --------------------------------------------------------------------------- #
def test_a_reply_holds_a_status_an_id_and_a_sentence():
    reply = a_reply()
    assert (reply.status, reply.order_id) == (201, 1)


def test_a_201_is_a_creation():
    assert a_reply().created() is True


def test_a_504_is_not_a_creation():
    assert a_reply(504, None, "no answer").created() is False


def test_a_reply_with_no_order_id_prints_a_dash():
    assert a_reply(504, None, "no answer").line() == \
        "HTTP 504 id=- no answer"


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_a_server_side_failure_is_worth_retrying(status):
    assert a_reply(status, None, "later").retryable() is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422])
def test_a_client_side_failure_is_final(status):
    assert a_reply(status, None, "no").retryable() is False


def test_a_creation_is_not_worth_retrying():
    assert a_reply().retryable() is False


def test_a_status_below_a_hundred_is_refused():
    with pytest.raises(RetryError, match="a status is at least 100"):
        a_reply(99, None, "no")


def test_a_status_above_five_ninety_nine_is_refused():
    with pytest.raises(RetryError, match="a status is at most 599"):
        a_reply(600, None, "no")


def test_an_order_id_of_zero_is_refused():
    with pytest.raises(RetryError, match="an order id is at least 1"):
        a_reply(201, 0, "created")


def test_a_reply_with_no_sentence_is_refused():
    with pytest.raises(RetryError, match="sentence that says why"):
        a_reply(201, 1, "   ")


# --------------------------------------------------------------------------- #
# A store
# --------------------------------------------------------------------------- #
def test_a_store_creates_the_first_order_under_id_one():
    store = Store()
    assert store.create(an_order()) == (1, True)


def test_a_store_counts_its_rows():
    store = Store()
    store.create(an_order())
    store.create(an_order())
    assert len(store) == 2


def test_a_repeated_key_returns_the_first_row_and_creates_nothing():
    store = Store()
    first, made = store.create(an_order(), KEY)
    again, made_again = store.create(an_order(), KEY)
    assert (first, made, again, made_again) == (1, True, 1, False)


def test_a_repeated_key_leaves_one_row_behind():
    store = Store()
    store.create(an_order(), KEY)
    store.create(an_order(), KEY)
    assert len(store) == 1


def test_a_different_key_makes_a_different_order():
    store = Store()
    first, _ = store.create(an_order(), "key-one")
    second, _ = store.create(an_order(), "key-two")
    assert first != second and len(store) == 2


def test_a_store_with_no_key_never_dedupes():
    store = Store()
    store.create(an_order())
    store.create(an_order())
    assert len(store) == 2


def test_a_store_names_the_keys_it_holds():
    store = Store()
    store.create(an_order(), KEY)
    assert store.keys() == (KEY,)


def test_a_store_returns_the_rows_it_holds():
    store = Store()
    store.create(an_order())
    assert store.rows() == (an_order(),)


def test_a_store_finds_an_order_by_its_id():
    store = Store()
    store.create(an_order(quantity=9))
    assert store.order(1).quantity == 9


def test_a_store_refuses_an_id_it_never_gave_out():
    with pytest.raises(RetryError, match="there is no order 2"):
        Store().order(2)


def test_a_store_refuses_a_row_that_is_not_an_order():
    with pytest.raises(RetryError, match="a store holds orders"):
        Store().create("order")


def test_an_empty_key_is_refused():
    with pytest.raises(RetryError, match="a key needs a value"):
        Store().create(an_order(), "  ")


def test_a_key_with_a_space_is_refused():
    with pytest.raises(RetryError, match="a key is one word"):
        Store().create(an_order(), "order 7f3a")


def test_a_key_that_is_not_text_is_refused():
    with pytest.raises(RetryError, match="a key is text"):
        Store().create(an_order(), 7)


# --------------------------------------------------------------------------- #
# A server
# --------------------------------------------------------------------------- #
def test_a_server_answers_201_and_creates_the_order():
    server = Server(Store(), TOKEN, ("ok",))
    reply = server.post(an_order(), None, 0)
    assert reply.status == 201 and reply.order_id == 1


def test_a_server_counts_every_request_it_answers():
    server = Server(Store(), TOKEN, ("ok", "ok"))
    server.post(an_order(), None, 0)
    server.post(an_order(), None, 0)
    assert server.requests == 2


def test_a_timeout_creates_nothing():
    server = Server(Store(), TOKEN, ("timeout",))
    reply = server.post(an_order(), None, 0)
    assert reply.status == 504 and len(server.store) == 0


def test_a_commit_then_timeout_creates_the_order_and_loses_the_answer():
    server = Server(Store(), TOKEN, ("commit-then-timeout",))
    reply = server.post(an_order(), None, 0)
    assert reply.status == 504 and reply.order_id is None
    assert len(server.store) == 1


def test_a_commit_then_timeout_under_a_key_creates_one_row():
    server = Server(Store(), TOKEN, ("commit-then-timeout", "ok"))
    server.post(an_order(), KEY, 0)
    reply = server.post(an_order(), KEY, 0)
    assert reply.status == 201 and reply.order_id == 1
    assert len(server.store) == 1


def test_a_second_commit_under_the_same_key_says_the_write_was_already_made():
    server = Server(Store(), TOKEN, ("commit-then-timeout",
                                     "commit-then-timeout"))
    server.post(an_order(), KEY, 0)
    reply = server.post(an_order(), KEY, 0)
    assert "already committed under this key" in reply.detail


def test_an_unavailable_service_answers_503():
    server = Server(Store(), TOKEN, ("unavailable",))
    assert server.post(an_order(), None, 0).status == 503


def test_the_script_can_ask_for_a_rejection():
    server = Server(Store(), TOKEN, ("unauthorized",))
    assert server.post(an_order(), None, 0).status == 401


def test_the_token_is_checked_before_the_script():
    server = Server(Store(), TOKEN, ("ok",))
    reply = server.post(an_order(), None, 60)
    assert reply.status == 401 and server.seen == ["expired"]


def test_an_expired_token_names_the_moment_it_expired():
    server = Server(Store(), TOKEN, ("ok",))
    assert "expired at 60" in server.post(an_order(), None, 61).detail


def test_a_script_that_runs_out_falls_back_to_ok():
    server = Server(Store(), TOKEN, ("ok",))
    server.post(an_order(), None, 0)
    assert server.post(an_order(), None, 0).status == 201


def test_a_server_needs_a_store():
    with pytest.raises(RetryError, match="a server needs a store"):
        Server("store", TOKEN, ("ok",))


def test_a_server_needs_a_token():
    with pytest.raises(RetryError, match="a server needs a token"):
        Server(Store(), "token", ("ok",))


def test_a_script_with_no_attempts_is_refused():
    with pytest.raises(RetryError, match="at least one attempt"):
        Server(Store(), TOKEN, ())


def test_a_script_step_the_lab_does_not_know_is_refused():
    with pytest.raises(RetryError, match="attempt 1 is one of"):
        Server(Store(), TOKEN, ("maybe",))


def test_a_server_remembers_what_each_attempt_met():
    server = Server(Store(), TOKEN, ("timeout", "ok"))
    server.post(an_order(), None, 0)
    server.post(an_order(), None, 0)
    assert server.seen == ["timeout", "ok"]


# --------------------------------------------------------------------------- #
# The waits
# --------------------------------------------------------------------------- #
def test_one_try_waits_for_nothing():
    assert backoff_delays(1) == ()


def test_two_tries_wait_once():
    assert backoff_delays(2) == (1,)


def test_three_tries_wait_twice_and_the_wait_doubles():
    assert backoff_delays(3) == (1, 2)


def test_five_tries_double_up_to_the_cap():
    assert backoff_delays(5) == (1, 2, 4, 8)


def test_the_cap_stops_the_wait_from_growing():
    assert backoff_delays(5, base=2, cap=3) == (2, 3, 3, 3)


def test_the_waits_are_the_same_every_time():
    assert backoff_delays(4) == backoff_delays(4)


def test_a_try_count_of_zero_is_refused():
    with pytest.raises(RetryError, match="a try count is at least 1"):
        backoff_delays(0)


def test_more_tries_than_the_lab_allows_is_refused():
    with pytest.raises(RetryError, match="at most 5 tries"):
        backoff_delays(MAX_TRIES + 1)


def test_a_base_wait_of_zero_is_refused():
    with pytest.raises(RetryError, match="a base wait is at least 1"):
        backoff_delays(3, base=0)


def test_a_cap_below_the_base_is_refused():
    with pytest.raises(RetryError, match="below the base wait"):
        backoff_delays(3, base=4, cap=2)


# --------------------------------------------------------------------------- #
# The legacy loop
# --------------------------------------------------------------------------- #
def test_the_legacy_loop_retries_a_timeout_and_lands():
    server = Server(Store(), TOKEN, ("timeout", "timeout", "ok"))
    run = legacy_post(server, an_order(), TRIES, 0)
    assert run.statuses() == (504, 504, 201) and run.outcome == "created"


def test_the_legacy_loop_creates_a_second_order_after_a_lost_answer():
    server = Server(Store(), TOKEN, ("commit-then-timeout", "ok"))
    run = legacy_post(server, an_order(), TRIES, 0)
    assert run.rows == 2 and len(server.store) == 2


def test_the_legacy_loop_answers_the_second_id_after_a_lost_answer():
    server = Server(Store(), TOKEN, ("commit-then-timeout", "ok"))
    assert legacy_post(server, an_order(), TRIES, 0).order_id == 2


def test_the_legacy_loop_gives_up_after_three_unavailable_answers():
    server = Server(Store(), TOKEN, ("unavailable",) * 3)
    run = legacy_post(server, an_order(), TRIES, 0)
    assert run.outcome == "gave-up" and run.order_id is None
    assert run.attempts() == 3 and run.rows == 0


def test_the_legacy_loop_retries_an_expired_token_three_times():
    server = Server(Store(), TOKEN, ("ok",) * 3)
    run = legacy_post(server, an_order(), TRIES, 60)
    assert run.statuses() == (401, 401, 401) and \
        run.outcome == "unauthorized"


def test_the_legacy_loop_never_waits():
    server = Server(Store(), TOKEN, ("unavailable",) * 3)
    assert legacy_post(server, an_order(), TRIES, 0).waited == 0


def test_the_legacy_loop_leaves_a_committed_order_it_never_saw():
    server = Server(Store(), TOKEN, ("timeout", "commit-then-timeout",
                                     "unavailable"))
    run = legacy_post(server, an_order(), TRIES, 0)
    assert run.outcome == "gave-up" and run.rows == 1 and \
        len(server.store) == 1


def test_the_legacy_loop_refuses_a_try_count_of_zero():
    with pytest.raises(RetryError, match="a try count is at least 1"):
        legacy_post(Server(Store(), TOKEN, ("ok",)), an_order(), 0, 0)


# --------------------------------------------------------------------------- #
# The keyed loop
# --------------------------------------------------------------------------- #
def test_the_keyed_loop_creates_one_order_after_a_lost_answer():
    server = Server(Store(), TOKEN, ("commit-then-timeout", "ok"))
    run = post_with_key(server, an_order(), KEY, TRIES, 0)
    assert run.rows == 1 and run.order_id == 1 and \
        run.outcome == "created"


def test_the_keyed_loop_returns_the_id_the_lost_answer_had():
    server = Server(Store(), TOKEN, ("commit-then-timeout", "ok"))
    run = post_with_key(server, an_order(), KEY, TRIES, 0)
    assert run.statuses() == (504, 201)


def test_the_keyed_loop_waits_between_attempts():
    server = Server(Store(), TOKEN, ("unavailable",) * 3)
    run = post_with_key(server, an_order(), KEY, TRIES, 0)
    assert run.waited == 3


def test_the_keyed_loop_stops_at_the_first_401():
    server = Server(Store(), TOKEN, ("ok",) * 3)
    run = post_with_key(server, an_order(), KEY, TRIES, 60)
    assert run.attempts() == 1 and run.outcome == "unauthorized"


def test_the_keyed_loop_gives_up_after_the_last_try():
    server = Server(Store(), TOKEN, ("unavailable",) * 3)
    run = post_with_key(server, an_order(), KEY, TRIES, 0)
    assert run.outcome == "gave-up" and run.order_id is None and \
        run.attempts() == 3


def test_the_keyed_loop_would_still_hold_the_order_it_committed():
    server = Server(Store(), TOKEN, ("timeout", "commit-then-timeout",
                                     "unavailable"))
    run = post_with_key(server, an_order(), KEY, TRIES, 0)
    assert run.rows == 1 and len(server.store) == 1


def test_the_keyed_loop_needs_a_key():
    with pytest.raises(RetryError, match="a key needs a value"):
        post_with_key(Server(Store(), TOKEN, ("ok",)), an_order(), " ", 1, 0)


def test_the_keyed_loop_refuses_a_try_count_of_zero():
    with pytest.raises(RetryError, match="a try count is at least 1"):
        post_with_key(Server(Store(), TOKEN, ("ok",)), an_order(), KEY, 0, 0)


def test_a_single_try_that_times_out_gives_up_at_once():
    server = Server(Store(), TOKEN, ("timeout", "ok"))
    run = post_with_key(server, an_order(), KEY, 1, 0)
    assert run.attempts() == 1 and run.waited == 0


# --------------------------------------------------------------------------- #
# A run
# --------------------------------------------------------------------------- #
def test_a_run_counts_its_attempts():
    run = a_run(replies=(a_reply(), a_reply()))
    assert run.attempts() == 2 and len(run) == 2


def test_a_run_names_its_statuses():
    run = a_run(replies=(a_reply(504, None, "no"), a_reply()))
    assert run.statuses() == (504, 201)


def test_a_run_names_its_last_reply():
    run = a_run(replies=(a_reply(504, None, "no"), a_reply()))
    assert run.last().status == 201


def test_a_run_line_names_the_mode_the_outcome_and_the_rows():
    run = a_run(replies=(a_reply(504, None, "no"), a_reply()), waited=1)
    line = run.line()
    assert line.startswith("keyed") and "created" in line
    assert "id=1" in line and "rows=1" in line and line.endswith("504 201")


def test_a_run_of_an_unknown_mode_is_refused():
    with pytest.raises(RetryError, match="a run is legacy or keyed"):
        a_run(mode="retry")


def test_a_run_of_an_unknown_outcome_is_refused():
    with pytest.raises(RetryError, match="a run ends"):
        a_run(outcome="stuck")


def test_a_run_with_no_attempts_is_refused():
    with pytest.raises(RetryError, match="at least one attempt"):
        a_run(replies=())


def test_a_run_that_created_something_needs_an_order_id():
    with pytest.raises(RetryError, match="has an order id"):
        a_run(order_id=None)


def test_a_negative_wait_is_refused():
    with pytest.raises(RetryError, match="a wait is at least 0"):
        a_run(waited=-1)


# --------------------------------------------------------------------------- #
# Reading the bundle
# --------------------------------------------------------------------------- #
def test_the_bundle_reads_the_order():
    assert ORDER.line() == "3 x 4499 cents = 13497 cents"


def test_the_bundle_reads_the_token():
    assert (TOKEN.issued, TOKEN.lifetime) == (0, 60)


def test_the_bundle_reads_the_moment_the_loop_starts():
    assert NOW == 0


def test_parse_order_skips_a_comment():
    text = "; note\nquantity 1\nunit-cents 1\nissued 0\nlifetime 5\nnow 0\n"
    assert parse_order(text)[0].quantity == 1


def test_parse_order_reads_windows_line_endings():
    text = "quantity 1\r\nunit-cents 1\r\nissued 0\r\nlifetime 5\r\nnow 0\r\n"
    assert parse_order(text)[2] == 0


def test_parse_order_refuses_a_line_of_three_fields():
    with pytest.raises(RetryError, match="a name and a value"):
        parse_order("quantity 1 2\n")


def test_parse_order_refuses_a_setting_it_does_not_know():
    with pytest.raises(RetryError, match="is not a setting"):
        parse_order("colour 3\n")


def test_parse_order_refuses_a_setting_given_twice():
    with pytest.raises(RetryError, match="is set twice"):
        parse_order("quantity 1\nquantity 2\n")


def test_parse_order_refuses_a_value_that_is_not_a_number():
    with pytest.raises(RetryError, match="takes a whole number"):
        parse_order("quantity three\n")


def test_parse_order_refuses_a_bundle_that_leaves_a_setting_out():
    with pytest.raises(RetryError, match="does not set 'issued'"):
        parse_order("quantity 1\nunit-cents 1\n")


def test_a_missing_bundle_is_refused(tmp_path):
    with pytest.raises(RetryError, match="file not found"):
        read_order(tmp_path / "nope.txt")


def test_read_order_accepts_its_own_file(tmp_path):
    path = tmp_path / "order.txt"
    path.write_bytes(b"quantity 2\nunit-cents 500\nissued 3\nlifetime 4\n"
                     b"now 5\n")
    order, token, now = read_order(path)
    assert order.total_cents() == 1000 and token.issued == 3 and now == 5


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #
def test_every_scenario_is_a_name_a_script_and_a_start():
    assert len(SCENARIOS) == 5 and len(SCENARIOS[0]) == 3


def test_script_for_reads_the_flaky_script():
    assert script_for("flaky") == ("timeout", "timeout", "ok")


def test_script_for_refuses_a_name_the_lab_does_not_hold():
    with pytest.raises(RetryError, match="no scenario named"):
        script_for("nope")


def test_offset_for_reads_the_expired_token_marker():
    assert offset_for("expired-token") is None


def test_offset_for_reads_a_zero_offset():
    assert offset_for("flaky") == 0


def test_a_marked_scenario_starts_past_the_token_expiry():
    assert start_for(TOKEN, 0, None) == 60


def test_an_offset_scenario_starts_that_many_seconds_later():
    assert start_for(TOKEN, 0, 5) == 5


def test_every_scripted_outcome_is_one_the_lab_knows():
    for name, script, _ in SCENARIOS:
        for step in script:
            assert step in OUTCOMES


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "the legacy loop creates two rows for one committed order",
    "the keyed loop creates one row for the same script",
    "a lost answer still leaves the order in the store",
    "a timeout is worth retrying and the third attempt lands",
    "an expired token fails every attempt",
    "the keyed loop stops at the first fatal status",
    "the waits grow, are capped and never vary",
    "the legacy loop waits nothing and the keyed loop does",
    "a repeated key returns the row the first attempt made",
    "a different key creates a different order",
    "every run counts the attempts it made",
]


def test_the_audit_holds_eleven_named_checks():
    assert [name for name, _ in real_checks()] == CHECK_NAMES


def test_the_audit_passes_on_the_demo_runs():
    assert problems(real_checks()) == []


def test_the_audit_is_repeatable():
    assert real_checks() == real_checks()


def test_the_audit_catches_a_legacy_run_that_created_one_row():
    runs = demo_runs()
    legacy, keyed = runs["commit-then-timeout"]
    runs["commit-then-timeout"] = (corrupted_run(legacy, rows=1), keyed)
    checks = audit(runs, ORDER, backoff_delays(MAX_TRIES), Store)
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_a_keyed_run_that_created_two_rows():
    runs = demo_runs()
    legacy, keyed = runs["commit-then-timeout"]
    runs["commit-then-timeout"] = (legacy, corrupted_run(keyed, rows=2))
    checks = audit(runs, ORDER, backoff_delays(MAX_TRIES), Store)
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_a_silent_run_that_created_two_rows():
    runs = demo_runs()
    legacy, keyed = runs["commit-then-silence"]
    runs["commit-then-silence"] = (corrupted_run(legacy, rows=2), keyed)
    checks = audit(runs, ORDER, backoff_delays(MAX_TRIES), Store)
    assert CHECK_NAMES[2] in problems(checks)


def test_the_audit_catches_a_flaky_run_that_never_landed():
    runs = demo_runs()
    legacy, keyed = runs["flaky"]
    stuck = corrupted_run(legacy, replies=(a_reply(503, None, "unavailable"),))
    runs["flaky"] = (stuck, keyed)
    checks = audit(runs, ORDER, backoff_delays(MAX_TRIES), Store)
    assert CHECK_NAMES[3] in problems(checks)


def test_the_audit_catches_an_expired_token_tried_once():
    runs = demo_runs()
    legacy, keyed = runs["expired-token"]
    once = corrupted_run(legacy, replies=(a_reply(401, None, "expired"),))
    runs["expired-token"] = (once, keyed)
    checks = audit(runs, ORDER, backoff_delays(MAX_TRIES), Store)
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_a_keyed_run_that_retried_a_401():
    runs = demo_runs()
    legacy, keyed = runs["expired-token"]
    three = corrupted_run(keyed,
                          replies=(a_reply(401, None, "expired"),) * 3)
    runs["expired-token"] = (legacy, three)
    checks = audit(runs, ORDER, backoff_delays(MAX_TRIES), Store)
    assert CHECK_NAMES[5] in problems(checks)


def test_the_audit_catches_waits_that_stop_growing():
    checks = audit(demo_runs(), ORDER, (1, 2, 4, 4), Store)
    assert CHECK_NAMES[6] in problems(checks)


def test_the_audit_catches_a_legacy_run_that_waited():
    runs = demo_runs()
    legacy, keyed = runs["unavailable"]
    runs["unavailable"] = (corrupted_run(legacy, waited=1), keyed)
    checks = audit(runs, ORDER, backoff_delays(MAX_TRIES), Store)
    assert CHECK_NAMES[7] in problems(checks)


def seeded_store():
    """A factory whose store already holds the key a check wants to try."""
    store = Store()
    store.create(ORDER, "demo-key")
    return store


def test_the_audit_catches_a_store_that_already_holds_the_key():
    """A store that is not empty cannot show a first attempt creating anything."""
    checks = audit(demo_runs(), ORDER, backoff_delays(MAX_TRIES),
                   seeded_store)
    caught = problems(checks)
    assert CHECK_NAMES[8] in caught and CHECK_NAMES[9] in caught


def test_the_audit_catches_a_run_that_created_more_rows_than_it_tried():
    runs = demo_runs()
    legacy, keyed = runs["flaky"]
    runs["flaky"] = (legacy, corrupted_run(keyed, rows=9))
    checks = audit(runs, ORDER, backoff_delays(MAX_TRIES), Store)
    assert CHECK_NAMES[10] in problems(checks)


def test_every_check_has_a_negative_control():
    """Eleven broken inputs, and every check is named by at least one of them."""
    def broken(name, index, **fields):
        runs = demo_runs()
        pair = list(runs[name])
        pair[index] = corrupted_run(pair[index], **fields)
        runs[name] = tuple(pair)
        return audit(runs, ORDER, backoff_delays(MAX_TRIES), Store)

    caught = set()
    caught |= set(problems(broken("commit-then-timeout", 0, rows=1)))
    caught |= set(problems(broken("commit-then-timeout", 1, rows=2)))
    caught |= set(problems(broken("commit-then-silence", 0, rows=2)))
    caught |= set(problems(broken("flaky", 0,
                                  replies=(a_reply(503, None, "no"),))))
    caught |= set(problems(broken("expired-token", 0,
                                  replies=(a_reply(401, None, "no"),))))
    caught |= set(problems(broken("expired-token", 1,
                                  replies=(a_reply(401, None, "no"),) * 3)))
    caught |= set(problems(audit(demo_runs(), ORDER, (1, 2, 4, 4), Store)))
    caught |= set(problems(broken("unavailable", 0, waited=1)))
    caught |= set(problems(audit(demo_runs(), ORDER,
                                 backoff_delays(MAX_TRIES), seeded_store)))
    caught |= set(problems(broken("flaky", 1, rows=9)))
    assert caught == set(CHECK_NAMES)


def test_the_audit_fails_closed_when_the_runs_are_missing():
    checks = audit({}, ORDER, backoff_delays(MAX_TRIES), Store)
    caught = problems(checks)
    assert CHECK_NAMES[0] in caught and CHECK_NAMES[10] in caught
    assert len(caught) == 8


def test_the_audit_fails_closed_when_one_pair_is_missing():
    runs = demo_runs()
    del runs["flaky"]
    checks = audit(runs, ORDER, backoff_delays(MAX_TRIES), Store)
    assert CHECK_NAMES[3] in problems(checks)


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


def test_demo_shows_the_legacy_loop(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "RETRY LAB" in out and 'client.post("/orders", payload)' in out


def test_demo_shows_the_order_and_the_token(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "3 x 4499 cents = 13497 cents" in out
    assert "token good from 0 to 59 (60 second(s))" in out


def test_demo_counts_the_rows_each_loop_left(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "the legacy loop left 4 row(s)" in out
    assert "the keyed loop left 3 row(s)" in out


def test_demo_shows_the_repeated_key_at_the_store(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "key order-7f3a -> id 1 (created=True)" in out
    assert "key order-7f3a -> id 1 (created=False)" in out


def test_demo_shows_the_waits(capsys):
    run_demo()
    assert "3 tries -> (1, 2)   5 tries -> (1, 2, 4, 8)" in \
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


def test_cli_runs_every_scenario(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    for name, _, _ in SCENARIOS:
        assert name in out
    assert "the legacy loop left 4 row(s); the keyed loop left 3" in out


def test_cli_runs_one_scenario(capsys):
    assert cli.main(["--scenario", "unavailable"]) == 0
    out = capsys.readouterr().out
    assert "unavailable" in out and "flaky" not in out


def test_cli_backoff_prints_every_schedule(capsys):
    assert cli.main(["--backoff"]) == 0
    out = capsys.readouterr().out
    assert "1 try/tries: ()" in out and "5 try/tries: (1, 2, 4, 8)" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 11 and "FAIL" not in out


def test_cli_one_scenario_cannot_satisfy_the_audit(capsys):
    assert cli.main(["--scenario", "flaky", "--audit"]) == 1
    out, err = capsys.readouterr()
    assert "FAIL" in out and "check(s) failed" in err


def test_cli_writes_the_runs_as_json(tmp_path, capsys):
    target = tmp_path / "runs.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    legacy = payload["runs"]["commit-then-timeout"]["legacy"]
    keyed = payload["runs"]["commit-then-timeout"]["keyed"]
    assert legacy["rows"] == 2 and keyed["rows"] == 1
    assert legacy["order_id"] == 2 and keyed["order_id"] == 1
    assert keyed["statuses"] == [504, 201] and keyed["waited"] == 1
    assert payload["runs"]["expired-token"]["legacy"]["statuses"] == \
        [401, 401, 401]
    assert payload["starts"]["expired-token"] == 60
    assert payload["order"]["total_cents"] == 13497
    assert payload["token"]["expires_at"] == 60
    assert payload["backoff"]["5"] == [1, 2, 4, 8]


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_refuses_a_try_count_of_zero(capsys):
    assert cli.main(["--tries", "0"]) == 2
    assert "a try count is between 1 and 5" in capsys.readouterr().err


def test_cli_refuses_a_try_count_above_the_limit(capsys):
    assert cli.main(["--tries", "6"]) == 2
    assert "a try count is between 1 and 5" in capsys.readouterr().err


def test_cli_refuses_a_scenario_it_does_not_hold(capsys):
    assert cli.main(["--scenario", "nope"]) == 2
    assert "no scenario named" in capsys.readouterr().err


def test_cli_refuses_a_key_with_a_space(capsys):
    assert cli.main(["--key", "order 7f3a"]) == 2
    assert "a key is one word" in capsys.readouterr().err


def test_cli_a_missing_bundle_exits_two(tmp_path, capsys):
    assert cli.main(["--order", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_malformed_bundle_exits_two(tmp_path, capsys):
    path = tmp_path / "order.txt"
    path.write_bytes(b"colour 3\n")
    assert cli.main(["--order", str(path)]) == 2
    assert "is not a setting" in capsys.readouterr().err
