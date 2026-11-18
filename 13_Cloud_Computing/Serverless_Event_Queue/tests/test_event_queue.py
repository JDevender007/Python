"""Tests for the Serverless Event Queue project."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from event_queue import (  # noqa: E402
    DATA_DIR,
    LEGACY_ALARM,
    LEGACY_COUNT,
    LEGACY_DEDUP,
    LEGACY_REDRIVE,
    MAX_EVENTS,
    MAX_SECONDS,
    MAX_WORKERS,
    DeadLetter,
    Delivery,
    Event,
    QueueConfig,
    QueueError,
    Run,
    Snapshot,
    age_worst,
    audit,
    divide_half_up,
    legacy_alarm,
    legacy_dedup_hit,
    legacy_dropped,
    legacy_processed,
    load_document,
    measure,
    read_scenario,
    receipt_handle,
    render_dead,
    render_timeline,
    report,
    run_demo,
    scenario_from_document,
    simulate,
    stale_moment,
    validate_or_raise,
    validate_scenario,
)
from main import main  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def config(**overrides) -> QueueConfig:
    base = {"name": "orders-events", "visibility": 20, "max_receive": 3,
            "retention": 600, "workers": 2}
    base.update(overrides)
    return QueueConfig(**base)


def event(event_id: str = "evt-01", **overrides) -> Event:
    base = {"id": event_id, "kind": "order.created", "produced_at": 0, "process": 5}
    base.update(overrides)
    return Event(**base)


def bundled() -> tuple[QueueConfig, tuple[Event, ...]]:
    return read_scenario()


def write_scenario(tmp_path: Path, document: object) -> Path:
    target = tmp_path / "scenario.json"
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def document_for(events: list[dict], **queue) -> dict:
    policy = {"name": "orders-events", "visibility": 20, "max_receive": 3,
              "retention": 600, "workers": 2}
    policy.update(queue)
    return {"queue": policy, "events": events}


# --------------------------------------------------------------------------- #
# Integer arithmetic
# --------------------------------------------------------------------------- #
def test_divide_half_up_rounds_a_half_up():
    assert divide_half_up(1, 2) == 1


def test_divide_half_up_rounds_below_a_half_down():
    assert divide_half_up(1, 4) == 0


def test_divide_half_up_keeps_exact_ratios():
    assert divide_half_up(6, 3) == 2
    assert divide_half_up(0, 9) == 0


def test_divide_half_up_refuses_a_zero_divisor():
    with pytest.raises(QueueError, match="divisor must be positive"):
        divide_half_up(1, 0)


def test_divide_half_up_refuses_a_negative_dividend():
    with pytest.raises(QueueError, match="dividend must be non-negative"):
        divide_half_up(-1, 2)


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
def test_an_event_knows_which_attempts_fail():
    item = event(failures=(1, 3))
    assert item.fails(1) is True
    assert item.fails(2) is False
    assert item.fails(3) is True


def test_an_event_reports_itself_as_a_dict():
    assert event(failures=(2,)).to_dict() == {
        "id": "evt-01",
        "kind": "order.created",
        "produced_at": 0,
        "process": 5,
        "failures": [2],
    }


def test_an_event_is_frozen():
    item = event()
    with pytest.raises(Exception):
        item.process = 9  # type: ignore[misc]


def test_a_config_reports_itself_as_a_dict():
    assert config().to_dict() == {
        "name": "orders-events",
        "visibility": 20,
        "max_receive": 3,
        "retention": 600,
        "workers": 2,
    }


def test_a_config_is_frozen():
    policy = config()
    with pytest.raises(Exception):
        policy.visibility = 30  # type: ignore[misc]


def test_a_first_delivery_is_not_a_duplicate():
    assert Delivery("evt-01", 1, 0, 0, 5, "success").duplicate is False


def test_a_second_delivery_is_a_duplicate():
    assert Delivery("evt-01", 2, 1, 5, 9, "success").duplicate is True


def test_a_delivery_reports_itself_as_a_dict():
    assert Delivery("evt-01", 2, 1, 5, 9, "failure").to_dict() == {
        "event": "evt-01",
        "attempt": 2,
        "worker": 1,
        "started": 5,
        "finished": 9,
        "outcome": "failure",
        "duplicate": True,
    }


def test_a_dead_letter_reports_itself_as_a_dict():
    assert DeadLetter("evt-05", 3, 98, "max_receive").to_dict() == {
        "event": "evt-05",
        "attempts": 3,
        "at": 98,
        "reason": "max_receive",
    }


def test_a_snapshot_reports_itself_as_a_dict():
    assert Snapshot(5, 3, 2, 5, 5).to_dict() == {
        "at": 5,
        "visible": 3,
        "inflight": 2,
        "backlog": 5,
        "oldest_age": 5,
    }


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_read_scenario_loads_the_bundled_policy():
    policy, events = bundled()
    assert policy.name == "orders-events"
    assert policy.visibility == 20
    assert policy.max_receive == 3
    assert policy.workers == 2


def test_read_scenario_loads_ten_events():
    assert len(bundled()[1]) == 10


def test_read_scenario_keeps_the_event_order(): 
    ids = [item.id for item in bundled()[1]]
    assert ids[:3] == ["evt-01", "evt-02", "evt-03"]


def test_read_scenario_reads_an_explicit_path(tmp_path):
    target = write_scenario(
        tmp_path,
        document_for([{"id": "evt-01", "kind": "order.created", "produced_at": 0,
                       "process": 5}]),
    )
    policy, events = read_scenario(target)
    assert policy.name == "orders-events"
    assert events[0].process == 5


def test_read_scenario_refuses_a_missing_file(tmp_path):
    with pytest.raises(QueueError, match="scenario not found: absent.json"):
        read_scenario(tmp_path / "absent.json")


def test_load_document_refuses_non_ascii_bytes(tmp_path):
    target = tmp_path / "bad.json"
    target.write_bytes(b'{"queue": {"name": "caf\xc3\xa9"}}')
    with pytest.raises(QueueError, match="bad.json is not ASCII text"):
        load_document(target)


def test_load_document_names_the_line_of_broken_json(tmp_path):
    target = tmp_path / "broken.json"
    target.write_text('{"queue": {},}', encoding="utf-8")
    with pytest.raises(QueueError, match="broken.json is not valid JSON: line 1"):
        load_document(target)


def test_load_document_refuses_a_list_root(tmp_path):
    target = tmp_path / "list.json"
    target.write_text("[]", encoding="utf-8")
    with pytest.raises(QueueError, match="a scenario root must be a mapping"):
        load_document(target)


def test_scenario_from_document_survives_a_missing_queue():
    policy, events = scenario_from_document({"events": []})
    assert policy.name == ""
    assert events == ()


def test_scenario_from_document_survives_a_non_mapping_queue():
    policy, _ = scenario_from_document({"queue": [], "events": []})
    assert policy.visibility == 0


def test_scenario_from_document_ignores_non_object_events():
    _, events = scenario_from_document({"events": ["evt-01", 4, None]})
    assert events == ()


def test_scenario_from_document_turns_a_boolean_process_into_zero():
    _, events = scenario_from_document(
        {"events": [{"id": "evt-01", "kind": "a.b", "process": True}]}
    )
    assert events[0].process == 0


def test_scenario_from_document_sorts_and_deduplicates_failures():
    _, events = scenario_from_document(
        {"events": [{"id": "evt-01", "kind": "a.b", "process": 5,
                     "failures": [2, 1, 2, 0, -1]}]}
    )
    assert events[0].failures == (1, 2)


def test_scenario_from_document_ignores_a_non_list_failures_field():
    _, events = scenario_from_document(
        {"events": [{"id": "evt-01", "kind": "a.b", "process": 5, "failures": 1}]}
    )
    assert events[0].failures == ()


def test_scenario_from_document_ignores_failure_text():
    _, events = scenario_from_document(
        {"events": [{"id": "evt-01", "kind": "a.b", "process": 5,
                     "failures": ["1", 2]}]}
    )
    assert events[0].failures == (2,)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_the_bundled_scenario_validates():
    policy, events = bundled()
    assert validate_scenario(policy, events) == []


def test_a_bad_queue_name_is_reported():
    problems = validate_scenario(config(name="Orders Events"), (event(),))
    assert "$.queue.name: a lowercase slug is required" in problems


def test_a_zero_visibility_timeout_is_reported():
    problems = validate_scenario(config(visibility=0), (event(),))
    assert any("$.queue.visibility" in item for item in problems)


def test_the_visibility_cap_is_inclusive():
    assert validate_scenario(config(visibility=MAX_SECONDS), (event(),)) == []


def test_a_visibility_timeout_above_the_cap_is_reported():
    problems = validate_scenario(config(visibility=MAX_SECONDS + 1), (event(),))
    assert any("$.queue.visibility" in item for item in problems)


def test_a_zero_max_receive_is_reported():
    problems = validate_scenario(config(max_receive=0), (event(),))
    assert any("$.queue.max_receive" in item for item in problems)


def test_a_max_receive_above_ten_is_reported():
    problems = validate_scenario(config(max_receive=11), (event(),))
    assert any("$.queue.max_receive" in item for item in problems)


def test_a_zero_retention_is_reported():
    problems = validate_scenario(config(retention=0), (event(),))
    assert any("$.queue.retention" in item for item in problems)


def test_a_zero_worker_count_is_reported():
    problems = validate_scenario(config(workers=0), (event(),))
    assert any("$.queue.workers" in item for item in problems)


def test_the_worker_cap_is_inclusive():
    assert validate_scenario(config(workers=MAX_WORKERS), (event(),)) == []


def test_a_worker_count_above_the_cap_is_reported():
    problems = validate_scenario(config(workers=MAX_WORKERS + 1), (event(),))
    assert any("$.queue.workers" in item for item in problems)


def test_an_empty_event_list_is_reported():
    problems = validate_scenario(config(), ())
    assert "$.events: a non-empty array is required" in problems


def test_too_many_events_are_reported():
    events = tuple(event(f"evt-{index:02d}") for index in range(MAX_EVENTS + 1))
    problems = validate_scenario(config(), events)
    assert any(f"at most {MAX_EVENTS} events" in item for item in problems)


def test_a_bad_event_id_is_reported():
    problems = validate_scenario(config(), (event("Evt-01"),))
    assert any("$.events[0].id" in item for item in problems)


def test_a_duplicate_event_id_is_reported():
    problems = validate_scenario(config(), (event(), event()))
    assert any("duplicate event 'evt-01'" in item for item in problems)


def test_a_bad_event_kind_is_reported():
    problems = validate_scenario(config(), (event(kind="Order Created"),))
    assert any("$.events[0].kind" in item for item in problems)


def test_a_negative_produced_at_is_reported():
    problems = validate_scenario(config(), (event(produced_at=-1),))
    assert any("$.events[0].produced_at" in item for item in problems)


def test_a_zero_process_time_is_reported():
    problems = validate_scenario(config(), (event(process=0),))
    assert any("$.events[0].process" in item for item in problems)


def test_a_failure_outside_the_budget_is_reported():
    problems = validate_scenario(config(max_receive=3), (event(failures=(4,)),))
    assert any("outside the max_receive budget" in item for item in problems)


def test_a_failure_within_the_budget_is_accepted():
    assert validate_scenario(config(max_receive=3), (event(failures=(3,)),)) == []


def test_problems_accumulate_instead_of_stopping_at_the_first():
    problems = validate_scenario(config(name="Bad", workers=0), (event(process=0),))
    assert len(problems) >= 3


def test_validate_or_raise_names_the_problem_count():
    with pytest.raises(QueueError, match=r"invalid scenario \(2 problem"):
        validate_or_raise(config(name="Bad"), ())


def test_validate_or_raise_accepts_the_bundled_scenario():
    assert validate_or_raise(*bundled()) is None


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
def test_simulate_refuses_an_invalid_scenario():
    with pytest.raises(QueueError, match="invalid scenario"):
        simulate(config(workers=0), (event(),))


def test_one_fast_event_finishes_at_its_process_time():
    run = simulate(config(workers=1), (event(process=5),))
    assert run.deliveries == (Delivery("evt-01", 1, 0, 0, 5, "success"),)
    assert run.ended_at == 5


def test_two_workers_start_two_events_at_once():
    events = (event("evt-01", process=5), event("evt-02", process=5))
    run = simulate(config(), events)
    assert [(item.event, item.worker, item.started) for item in run.deliveries] == [
        ("evt-01", 0, 0),
        ("evt-02", 1, 0),
    ]


def test_one_worker_serialises_two_events():
    events = (event("evt-01", process=5), event("evt-02", process=5))
    run = simulate(config(workers=1), events)
    assert [(item.event, item.started, item.finished) for item in run.deliveries] == [
        ("evt-01", 0, 5),
        ("evt-02", 5, 10),
    ]


def test_one_worker_cannot_duplicate_a_slow_message():
    run = simulate(config(workers=1, visibility=5), (event(process=12),))
    assert run.delivered == 1
    assert run.duplicates == 0


def test_two_workers_duplicate_a_message_slower_than_visibility():
    run = simulate(config(workers=2, visibility=5), (event(process=12),))
    assert run.attempts_of("evt-01") == 2
    assert [item.started for item in run.deliveries_of("evt-01")] == [0, 5]


def test_a_visibility_timeout_above_the_process_time_never_duplicates():
    run = simulate(config(workers=2, visibility=60), (event(process=12),))
    assert run.duplicates == 0


def test_a_failed_attempt_is_retried_after_the_visibility_timeout():
    run = simulate(
        config(workers=1, visibility=20, max_receive=3),
        (event(process=5, failures=(1,)),),
    )
    assert [(item.attempt, item.started, item.outcome) for item in run.deliveries] == [
        (1, 0, "failure"),
        (2, 20, "success"),
    ]


def test_a_message_is_dead_lettered_after_its_budget():
    run = simulate(
        config(workers=1, visibility=10, max_receive=2),
        (event(process=5, failures=(1, 2)),),
    )
    assert run.attempts_of("evt-01") == 2
    assert [(item.event, item.attempts, item.reason) for item in run.dead] == [
        ("evt-01", 2, "max_receive")
    ]


def test_a_dead_lettered_event_is_not_applied():
    run = simulate(
        config(workers=1, visibility=10, max_receive=1),
        (event(process=5, failures=(1,)),),
    )
    assert run.dead[0].reason == "max_receive"
    assert run.distinct_applied == 0


def test_a_message_can_expire_from_retention():
    events = (
        event("evt-01", process=30),
        event("evt-02", process=30),
        event("evt-03", process=5),
    )
    run = simulate(config(workers=1, retention=45), events)
    assert [(item.event, item.reason) for item in run.dead] == [("evt-03", "retention")]


def test_a_retention_expiry_keeps_the_attempt_count():
    events = (
        event("evt-01", process=30),
        event("evt-02", process=30),
        event("evt-03", process=5),
    )
    run = simulate(config(workers=1, retention=45), events)
    assert run.dead[0].attempts == 0


def test_a_late_event_is_not_in_the_backlog_before_it_arrives():
    events = (event("evt-01", process=5), event("evt-02", process=5, produced_at=100))
    run = simulate(config(workers=1), events)
    assert run.timeline[0].backlog == 1


def test_deliveries_are_recorded_in_start_order_per_worker():
    run = simulate(*bundled())
    assert [item.event for item in run.deliveries[:2]] == ["evt-01", "evt-02"]


def test_the_bundled_slow_event_is_delivered_twice():
    run = simulate(*bundled())
    assert run.attempts_of("evt-03") == 2


def test_the_bundled_slow_event_succeeds_both_times():
    run = simulate(*bundled())
    assert [item.outcome for item in run.deliveries_of("evt-03")] == ["success", "success"]


def test_the_bundled_transient_failure_recovers():
    run = simulate(*bundled())
    assert [(item.attempt, item.outcome) for item in run.deliveries_of("evt-04")] == [
        (1, "failure"),
        (2, "success"),
    ]


def test_the_bundled_poison_event_exhausts_three_attempts():
    run = simulate(*bundled())
    assert [item.attempt for item in run.deliveries_of("evt-05")] == [1, 2, 3]


def test_the_bundled_run_totals_are_pinned():
    run = simulate(*bundled())
    assert (run.delivered, run.distinct_delivered, run.duplicates) == (14, 10, 4)


def test_the_bundled_run_applies_nine_events_and_dead_letters_one():
    run = simulate(*bundled())
    assert (run.distinct_applied, len(run.dead), run.settled) == (9, 1, 10)


def test_the_bundled_run_has_ten_successes_and_four_failures():
    run = simulate(*bundled())
    assert (len(run.successes), len(run.failures)) == (10, 4)


def test_the_bundled_run_repeats_exactly_one_side_effect():
    run = simulate(*bundled())
    assert run.repeated_effects == 1


def test_the_bundled_run_ends_at_252_seconds():
    assert simulate(*bundled()).ended_at == 252


def test_the_bundled_dead_letter_is_pinned():
    run = simulate(*bundled())
    assert run.dead == (DeadLetter("evt-05", 3, 98, "max_receive"),)


def test_peak_visible_is_smaller_than_peak_backlog():
    run = simulate(*bundled())
    assert (run.peak_visible, run.peak_backlog) == (5, 7)


def test_peak_age_is_eighty_three_seconds():
    assert simulate(*bundled()).peak_age == 83


def test_the_final_snapshot_is_empty():
    run = simulate(*bundled())
    assert run.final == Snapshot(252, 0, 0, 0, 0)


def test_the_timeline_records_a_moment_with_no_visible_message():
    run = simulate(*bundled())
    assert any(item.visible == 0 and item.backlog > 0 for item in run.timeline)


def test_a_run_reports_the_slow_event_twice_in_its_dict():
    body = simulate(*bundled()).to_dict()
    slow = [item for item in body["deliveries"] if item["event"] == "evt-03"]
    assert len(slow) == 2
    assert all(item["duplicate"] is False for item in slow[:1])
    assert slow[1]["duplicate"] is True


def test_the_run_totals_dict_is_pinned():
    totals = simulate(*bundled()).to_dict()["totals"]
    assert totals == {
        "events": 10,
        "delivered": 14,
        "distinct_delivered": 10,
        "duplicates": 4,
        "successes": 10,
        "failures": 4,
        "distinct_applied": 9,
        "repeated_effects": 1,
        "dead": 1,
    }


def test_attempts_of_an_unknown_event_is_zero():
    assert simulate(*bundled()).attempts_of("evt-99") == 0


def test_simulate_is_deterministic():
    first = simulate(*bundled())
    second = simulate(*bundled())
    assert first.deliveries == second.deliveries
    assert first.timeline == second.timeline


# --------------------------------------------------------------------------- #
# Legacy comparisons
# --------------------------------------------------------------------------- #
def test_the_legacy_counter_counts_every_successful_handler():
    run = simulate(*bundled())
    assert legacy_processed(run) == 10


def test_the_legacy_counter_overcounts_distinct_events():
    run = simulate(*bundled())
    assert legacy_processed(run) > run.distinct_applied


def test_the_legacy_alarm_fires_on_a_deep_visible_queue():
    assert legacy_alarm(Snapshot(0, 5, 0, 5, 0)) is True


def test_the_legacy_alarm_is_silent_when_nothing_is_visible():
    assert legacy_alarm(Snapshot(63, 0, 0, 1, 63)) is False


def test_the_legacy_alarm_ignores_in_flight_messages():
    assert legacy_alarm(Snapshot(5, 0, 2, 5, 5)) is False


def test_the_legacy_alarm_threshold_is_inclusive():
    assert legacy_alarm(Snapshot(0, 2, 0, 2, 0)) is False
    assert legacy_alarm(Snapshot(0, 3, 0, 3, 0)) is True


def test_the_legacy_delete_policy_loses_both_failing_events():
    _, events = bundled()
    assert legacy_dropped(events) == ("evt-04", "evt-05")


def test_the_legacy_delete_policy_keeps_a_clean_event():
    assert legacy_dropped((event(),)) == ()


def test_a_receipt_handle_is_unique_per_delivery():
    first = Delivery("evt-01", 1, 0, 0, 5, "success")
    second = Delivery("evt-01", 2, 1, 5, 9, "success")
    assert receipt_handle(first) != receipt_handle(second)


def test_a_receipt_handle_names_the_attempt_and_worker():
    assert receipt_handle(Delivery("evt-01", 2, 1, 5, 9, "success")) == "rh-evt-01-2-1"


def test_the_handle_check_stops_no_duplicates():
    run = simulate(*bundled())
    assert legacy_dedup_hit(run, receipt_handle) == 0


def test_a_constant_handle_would_stop_the_duplicates():
    run = simulate(*bundled())
    assert legacy_dedup_hit(run, lambda item: item.event) >= run.duplicates


def test_age_worst_returns_the_oldest_moment():
    run = simulate(*bundled())
    assert age_worst(run).oldest_age == 83


def test_stale_moment_returns_none_for_a_generous_limit():
    assert stale_moment(simulate(*bundled()), 1000) is None


def test_stale_moment_finds_the_first_sixty_second_backlog():
    moment = stale_moment(simulate(*bundled()), 60)
    assert moment is not None
    assert (moment.at, moment.oldest_age) == (63, 63)


# --------------------------------------------------------------------------- #
# Measurement and the JSON report
# --------------------------------------------------------------------------- #
def test_measure_pins_the_bundled_totals():
    measured = measure()
    run = measured["run"]
    assert (run.delivered, run.duplicates, len(run.dead)) == (14, 4, 1)


def test_measure_pins_the_worst_moment():
    worst = measure()["worst"]
    assert (worst.at, worst.visible, worst.backlog, worst.oldest_age) == (83, 0, 1, 83)


def test_measure_pins_the_stale_moment():
    stale = measure()["stale"]
    assert stale is not None
    assert (stale.at, stale.visible, stale.oldest_age) == (63, 0, 63)


def test_measure_pins_the_legacy_figures():
    measured = measure()
    assert measured["legacy_processed"] == 10
    assert measured["legacy_dropped"] == ("evt-04", "evt-05")
    assert measured["legacy_handle_repeats"] == 0


def test_measure_pins_the_average_age():
    assert measure()["average_age"] == 31


def test_measure_accepts_an_explicit_path(tmp_path):
    target = write_scenario(
        tmp_path,
        document_for([{"id": "evt-01", "kind": "a.b", "produced_at": 0,
                       "process": 5}], workers=1),
    )
    assert measure(target)["run"].delivered == 1


def test_report_is_json_safe():
    body = json.loads(json.dumps(report(measure())))
    assert body["queue"]["name"] == "orders-events"
    assert body["totals"]["duplicates"] == 4


def test_report_keeps_the_deliveries_as_dicts():
    body = report(measure())
    assert body["deliveries"][0]["event"] == "evt-01"
    assert isinstance(body["deliveries"][0], dict)


def test_report_keeps_the_timeline():
    body = report(measure())
    assert body["timeline"][0]["visible"] == 5


def test_report_keeps_the_alert_block():
    alerts = report(measure())["alerts"]
    assert alerts["worst"]["oldest_age"] == 83
    assert alerts["stale"]["at"] == 63
    assert alerts["legacy_dropped"] == ["evt-04", "evt-05"]


def test_report_has_no_dataclass_left():
    text = json.dumps(report(measure()))
    assert "Event(" not in text
    assert "Delivery(" not in text


def test_measure_is_deterministic_across_calls():
    first = measure()
    second = measure()
    assert first["run"].deliveries == second["run"].deliveries
    assert first["worst"] == second["worst"]


# --------------------------------------------------------------------------- #
# Audit and its negative controls
# --------------------------------------------------------------------------- #
def test_audit_reports_fifteen_checks_and_all_pass():
    results = audit(measure())
    assert len(results) == 15
    assert [name for name, okay in results if not okay] == []


def test_every_audit_check_has_a_name():
    assert all(isinstance(name, str) and name for name, _ in audit(measure()))


def test_a_single_worker_flips_the_duplicate_check():
    policy, events = bundled()
    results = dict(audit(measure(), read=lambda: (config(workers=1), events)))
    assert results["at_least_once_delivers_more_than_it_receives"] is False
    assert results["a_slow_handler_is_redelivered_while_it_still_runs"] is False


def test_a_longer_visibility_timeout_flips_the_slow_check():
    _, events = bundled()
    results = dict(audit(measure(), read=lambda: (config(visibility=60), events)))
    assert results["a_slow_handler_is_redelivered_while_it_still_runs"] is False


def test_a_smaller_budget_flips_the_dead_letter_check():
    _, events = bundled()
    results = dict(audit(measure(), read=lambda: (config(max_receive=2), events)))
    assert results["an_exhausted_budget_lands_in_the_dead_letter_queue"] is False


def test_a_truncated_scenario_flips_the_pinned_checks():
    results = dict(audit(measure(), read=lambda: (config(), (event(),))))
    assert results["every_event_is_either_applied_or_dead_lettered"] is False
    assert results["the_scenario_reads_and_validates"] is False


def test_a_raising_reader_fails_checks_instead_of_raising():
    def explode():
        raise RuntimeError("disk gone")

    results = dict(audit(measure(), read=explode))
    assert results["the_scenario_reads_and_validates"] is False
    assert any(value is False for value in results.values())


def test_a_doctored_run_flips_the_pinned_total():
    def doctored(policy, events):
        run = simulate(policy, events)
        return replace(run, deliveries=run.deliveries[:5])

    results = dict(audit(measure(), run=doctored))
    assert results["at_least_once_delivers_more_than_it_receives"] is False


def test_a_tampered_delivery_flips_the_determinism_check():
    measured = measure()
    measured["run"] = replace(measured["run"], deliveries=())
    results = dict(audit(measured))
    assert results["the_rebuild_is_deterministic"] is False


def test_a_tampered_worst_moment_flips_the_age_check():
    measured = measure()
    measured["worst"] = Snapshot(83, 0, 1, 1, 200)
    results = dict(audit(measured))
    assert results["a_small_depth_can_hide_a_stale_backlog"] is False


def test_a_tampered_event_list_flips_the_settled_check():
    measured = measure()
    measured["events"] = ()
    results = dict(audit(measured))
    assert results["every_event_is_either_applied_or_dead_lettered"] is False


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def test_render_timeline_has_a_header_and_a_rule():
    lines = render_timeline(simulate(*bundled())).splitlines()
    assert "Visible" in lines[0]
    assert set(lines[1]) == {"-"}


def test_render_timeline_has_one_row_per_snapshot():
    run = simulate(*bundled())
    assert len(render_timeline(run).splitlines()) == len(run.timeline) + 2


def test_render_dead_says_the_queue_is_empty_for_a_clean_run():
    run = simulate(config(workers=1), (event(),))
    assert render_dead(run) == "Dead-letter queue: empty"


def test_render_dead_names_every_dead_letter():
    text = render_dead(simulate(*bundled()))
    assert "evt-05" in text
    assert "max_receive" in text


def test_run_demo_returns_zero_and_ends_with_the_two_contract_lines(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.rstrip("\n").splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical_across_runs(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    second = capsys.readouterr().out
    assert first == second


def test_run_demo_prints_the_four_legacy_shortcuts(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert LEGACY_COUNT in out
    assert LEGACY_ALARM in out
    assert LEGACY_REDRIVE in out
    assert LEGACY_DEDUP in out


def test_run_demo_prints_the_pinned_pairs(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "delivered at 5s by worker 0 and again at 26s by worker 1" in out
    assert "10 successes for 9 distinct events" in out
    assert "15/15 checks pass" in out


def test_run_demo_names_the_dead_letter(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "evt-05  attempts 3  at 98s" in out


def test_run_demo_reports_the_depth_alarm_missing_the_worst_moment(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "stays silent at the worst one" in out


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #
def test_cli_demo_returns_zero():
    assert main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_demo_quiet_is_silent_on_a_broken_scenario(tmp_path, capsys):
    broken = tmp_path / "absent.json"
    assert main(["--demo", "--quiet", "--file", str(broken)]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_audit_returns_zero_and_prints_pass_lines(capsys):
    assert main(["--audit"]) == 0
    assert "PASS  a_receipt_handle_cannot_identify_a_duplicate" in capsys.readouterr().out


def test_cli_writes_a_json_report(tmp_path):
    target = tmp_path / "nested" / "report.json"
    assert main(["--json", str(target)]) == 0
    body = json.loads(target.read_text(encoding="utf-8"))
    assert body["totals"]["duplicates"] == 4


def test_cli_prints_the_delivery_table(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "deliveries: 14 | duplicates: 4 | dead-lettered: 1" in out
    assert "evt-03" in out


def test_cli_prints_the_dead_letter_line(capsys):
    assert main([]) == 0
    assert "dead-letter  evt-05  attempts 3  at 98s" in capsys.readouterr().out


def test_cli_refuses_a_missing_scenario_with_exit_two(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "absent.json")]) == 2
    assert "error: scenario not found" in capsys.readouterr().err


def test_cli_refuses_an_invalid_scenario_with_exit_two(tmp_path, capsys):
    target = write_scenario(
        tmp_path,
        document_for([{"id": "evt-01", "kind": "a.b", "produced_at": 0,
                       "process": 0}]),
    )
    assert main(["--file", str(target)]) == 2
    assert "invalid scenario" in capsys.readouterr().err


def test_cli_accepts_an_explicit_scenario(tmp_path, capsys):
    target = write_scenario(
        tmp_path,
        document_for([{"id": "evt-01", "kind": "a.b", "produced_at": 0,
                       "process": 5}], workers=1),
    )
    assert main(["--file", str(target)]) == 0
    assert "events: 1 | deliveries: 1" in capsys.readouterr().out


def test_cli_quiet_without_demo_prints_nothing(capsys):
    assert main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_the_bundled_scenario_is_ascii():
    raw = (DATA_DIR / "scenario.json").read_bytes()
    assert all(byte < 128 for byte in raw)


def test_the_data_directory_matches_the_scenario_file():
    from event_queue import SCENARIO_FILE

    assert SCENARIO_FILE.parent == DATA_DIR
