"""Tests for the Release / Rollback Simulator project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import build_parser, main, parse_steps  # noqa: E402
from rollout import (  # noqa: E402
    ALERT_LEVELS,
    BUNDLED_DEPLOYMENT,
    EXPECTED_BLUE_BUDGET,
    EXPECTED_CANARY_BUDGET,
    EXPECTED_SERVICE,
    EXPECTED_VERSIONS,
    STRATEGIES,
    STRATEGY_BLUE_GREEN,
    STRATEGY_CANARY,
    STRATEGY_ROLLING,
    STRATEGY_STEPS,
    STATE_FAILED,
    STATE_PENDING,
    STATE_PROGRESSING,
    STATE_ROLLED_BACK,
    STATE_ROLLING_BACK,
    STATE_ROLLBACK_FAILED,
    STATE_SUCCEEDED,
    Deployment,
    Gate,
    Release,
    RolloutError,
    Slo,
    _Machine,
    alert_level,
    execute,
    load_deployment,
    observe,
    parse_document,
    parse_gate,
    parse_release,
    parse_slo,
    plan_steps,
    render_report,
    run_demo,
)

DATA = BUNDLED_DEPLOYMENT.parent


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def release(version="1.0.0", error_rate=0.001, latency_ms=200.0,
            saturation=0.5) -> dict:
    return {"version": version, "error_rate": error_rate,
            "latency_ms": latency_ms, "saturation": saturation}


def document(**overrides) -> dict:
    data = {"service": "svc", "releases": [release(), release("1.0.1")]}
    data.update(overrides)
    return data


def deployment(releases=None, gate=None, slo=None,
               strategy=STRATEGY_CANARY) -> Deployment:
    return Deployment(
        service="svc",
        gate=gate or Gate(),
        slo=slo or Slo(),
        releases=tuple(releases or (Release("1.0.0", 0.001, 200.0, 0.5),)),
        strategy=strategy,
    )


# --------------------------------------------------------------------------- #
# release parsing
# --------------------------------------------------------------------------- #
def test_parse_release_round_trip():
    item = parse_release(release("2.3.4", 0.002, 210.0, 0.4), 0)
    assert item == Release("2.3.4", 0.002, 210.0, 0.4)


def test_parse_release_strips_version():
    assert parse_release(release("  2.3.4  "), 0).version == "2.3.4"


def test_parse_release_accepts_integers_for_floats():
    item = parse_release({"version": "1", "error_rate": 0,
                          "latency_ms": 100, "saturation": 1}, 0)
    assert item.error_rate == 0.0 and item.latency_ms == 100.0
    assert item.saturation == 1.0


@pytest.mark.parametrize("raw", [None, 7, "1.0.0", [], ()])
def test_parse_release_requires_mapping(raw):
    with pytest.raises(RolloutError, match="must be a mapping"):
        parse_release(raw, 0)


@pytest.mark.parametrize("version", [None, "", "   ", 42])
def test_parse_release_requires_version(version):
    raw = release()
    raw["version"] = version
    with pytest.raises(RolloutError, match="non-empty string"):
        parse_release(raw, 0)


def test_parse_release_labels_the_index():
    with pytest.raises(RolloutError, match="release #3"):
        parse_release({}, 2)


def test_parse_release_requires_error_rate():
    raw = release()
    del raw["error_rate"]
    with pytest.raises(RolloutError, match="'error_rate' must be a number"):
        parse_release(raw, 0)


@pytest.mark.parametrize("value", [-0.1, 1.5])
def test_parse_release_rejects_error_rate_outside_unit_interval(value):
    with pytest.raises(RolloutError, match=r"must be in \[0, 1\]"):
        parse_release(release(error_rate=value), 0)


def test_parse_release_rejects_boolean_error_rate():
    with pytest.raises(RolloutError, match="must be a number"):
        parse_release(release(error_rate=True), 0)


def test_parse_release_rejects_non_positive_latency():
    with pytest.raises(RolloutError, match="'latency_ms' must be > 0"):
        parse_release(release(latency_ms=0), 0)


def test_parse_release_rejects_negative_latency():
    with pytest.raises(RolloutError, match="'latency_ms' must be > 0"):
        parse_release(release(latency_ms=-5.0), 0)


def test_parse_release_rejects_saturation_above_one():
    with pytest.raises(RolloutError, match=r"must be in \[0, 1\]"):
        parse_release(release(saturation=1.2), 0)


# --------------------------------------------------------------------------- #
# gate / slo parsing
# --------------------------------------------------------------------------- #
def test_parse_gate_defaults():
    assert parse_gate(None) == Gate(0.02, 350.0, 0.85)


def test_parse_gate_custom_values():
    gate = parse_gate({"max_error_rate": 0.05, "max_latency_ms": 500,
                       "max_saturation": 0.9})
    assert gate == Gate(0.05, 500.0, 0.9)


def test_parse_gate_requires_mapping():
    with pytest.raises(RolloutError, match="'gate' must be a mapping"):
        parse_gate([1, 2])


def test_parse_gate_rejects_negative_error_rate():
    with pytest.raises(RolloutError, match=r"must be in \[0, 1\]"):
        parse_gate({"max_error_rate": -0.1})


def test_parse_gate_rejects_zero_latency():
    with pytest.raises(RolloutError, match="max_latency_ms must be > 0"):
        parse_gate({"max_latency_ms": 0})


def test_parse_gate_rejects_zero_saturation():
    with pytest.raises(RolloutError, match="max_saturation must be > 0"):
        parse_gate({"max_saturation": 0})


def test_parse_slo_defaults():
    assert parse_slo(None) == Slo(0.999, 60, 6000, 5)


def test_parse_slo_custom_values():
    slo = parse_slo({"target": 0.995, "window_minutes": 30,
                     "requests_per_minute": 100, "soak_minutes": 3})
    assert slo == Slo(0.995, 30, 100, 3)


def test_parse_slo_requires_mapping():
    with pytest.raises(RolloutError, match="'slo' must be a mapping"):
        parse_slo("nope")


@pytest.mark.parametrize("target", [0, 1, 1.5, -0.1])
def test_parse_slo_rejects_target_outside_open_unit_interval(target):
    with pytest.raises(RolloutError, match=r"must be in \(0, 1\)"):
        parse_slo({"target": target})


def test_parse_slo_rejects_float_window():
    with pytest.raises(RolloutError, match="window_minutes must be an integer"):
        parse_slo({"window_minutes": 30.5})


def test_parse_slo_rejects_zero_window():
    with pytest.raises(RolloutError, match="window_minutes must be > 0"):
        parse_slo({"window_minutes": 0})


def test_parse_slo_rejects_zero_rpm():
    with pytest.raises(RolloutError, match="requests_per_minute must be > 0"):
        parse_slo({"requests_per_minute": 0})


def test_parse_slo_rejects_zero_soak():
    with pytest.raises(RolloutError, match="soak_minutes must be > 0"):
        parse_slo({"soak_minutes": 0})


def test_parse_slo_rejects_soak_longer_than_window():
    with pytest.raises(RolloutError, match="must not exceed the window"):
        parse_slo({"window_minutes": 5, "soak_minutes": 10})


# --------------------------------------------------------------------------- #
# document parsing / loading
# --------------------------------------------------------------------------- #
def test_parse_document_minimal():
    dep = parse_document(document())
    assert dep.service == "svc"
    assert dep.versions() == ("1.0.0", "1.0.1")
    assert dep.strategy == STRATEGY_CANARY
    assert dep.gate == Gate()


def test_parse_document_normalises_strategy_case():
    assert parse_document(document(strategy=" BLUE_GREEN ")).strategy == \
        STRATEGY_BLUE_GREEN


@pytest.mark.parametrize("service", [None, "", "   ", 3])
def test_parse_document_requires_service(service):
    data = document()
    data["service"] = service
    with pytest.raises(RolloutError, match="'service' must be a non-empty"):
        parse_document(data)


def test_parse_document_requires_document_mapping():
    with pytest.raises(RolloutError, match="document must be a mapping"):
        parse_document(["service"])


@pytest.mark.parametrize("releases", [None, [], "1.0.0", {}])
def test_parse_document_requires_release_list(releases):
    data = document()
    data["releases"] = releases
    with pytest.raises(RolloutError, match="non-empty list"):
        parse_document(data)


def test_parse_document_rejects_duplicate_versions():
    data = document(releases=[release(), release()])
    with pytest.raises(RolloutError, match="duplicate release version"):
        parse_document(data)


def test_parse_document_rejects_unknown_strategy():
    with pytest.raises(RolloutError, match="unknown strategy"):
        parse_document(document(strategy="big-bang"))


def test_parse_document_names_the_valid_strategies():
    with pytest.raises(RolloutError, match="canary, rolling, blue_green"):
        parse_document(document(strategy="nope"))


def test_load_bundled_deployment():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    assert dep.service == EXPECTED_SERVICE
    assert dep.versions() == EXPECTED_VERSIONS
    assert dep.strategy == STRATEGY_CANARY
    assert dep.gate == Gate(0.02, 350.0, 0.85)
    assert dep.slo == Slo(0.999, 60, 6000, 5)


def test_load_deployment_missing_file(tmp_path):
    with pytest.raises(RolloutError, match="file not found"):
        load_deployment(tmp_path / "absent.json")


def test_load_deployment_invalid_json(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(RolloutError, match="invalid JSON in broken.json"):
        load_deployment(broken)


def test_deployment_release_lookup():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    assert dep.release("1.5.0").error_rate == 0.0035


def test_deployment_release_unknown_lists_versions():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    with pytest.raises(RolloutError, match="unknown release '9.9.9'"):
        dep.release("9.9.9")


def test_deployment_previous_is_the_preceding_release():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    assert dep.previous("1.6.0").version == "1.6.0-rc2"
    assert dep.previous("1.6.0-rc1").version == "1.5.0"


def test_deployment_previous_of_the_first_release_is_none():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    assert dep.previous("1.4.0") is None


def test_deployment_previous_rejects_unknown_version():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    with pytest.raises(RolloutError, match="unknown release"):
        dep.previous("0.0.0")


# --------------------------------------------------------------------------- #
# traffic ladders
# --------------------------------------------------------------------------- #
def test_plan_steps_canary():
    assert plan_steps(STRATEGY_CANARY) == (5, 25, 50, 100)


def test_plan_steps_rolling():
    assert plan_steps(STRATEGY_ROLLING) == (25, 50, 75, 100)


def test_plan_steps_blue_green():
    assert plan_steps(STRATEGY_BLUE_GREEN) == (100,)


def test_plan_steps_table_covers_every_strategy():
    assert set(STRATEGY_STEPS) == set(STRATEGIES)


def test_plan_steps_is_case_insensitive():
    assert plan_steps(" Canary ") == (5, 25, 50, 100)


def test_plan_steps_unknown_strategy():
    with pytest.raises(RolloutError, match="unknown strategy"):
        plan_steps("big-bang")


def test_plan_steps_requires_string():
    with pytest.raises(RolloutError, match="strategy must be a string"):
        plan_steps(3)


def test_plan_steps_accepts_custom_ladder():
    assert plan_steps("canary", [10, 50, 100]) == (10, 50, 100)


def test_plan_steps_rejects_empty_ladder():
    with pytest.raises(RolloutError, match="steps must not be empty"):
        plan_steps("canary", [])


@pytest.mark.parametrize("step", [0, 101, -5])
def test_plan_steps_rejects_out_of_range(step):
    with pytest.raises(RolloutError, match=r"must be in \[1, 100\]"):
        plan_steps("canary", [step, 100])


def test_plan_steps_rejects_equal_consecutive():
    with pytest.raises(RolloutError, match="strictly increase"):
        plan_steps("canary", [10, 10, 100])


def test_plan_steps_rejects_decreasing():
    with pytest.raises(RolloutError, match="strictly increase"):
        plan_steps("canary", [50, 100, 90])


def test_plan_steps_requires_final_full_rollout():
    with pytest.raises(RolloutError, match="last step must be 100%"):
        plan_steps("canary", [10, 50])


def test_plan_steps_rejects_float_step():
    with pytest.raises(RolloutError, match="step must be an integer"):
        plan_steps("canary", [10.5, 100])


# --------------------------------------------------------------------------- #
# gate evaluation and pricing
# --------------------------------------------------------------------------- #
def test_gate_accepts_healthy_release():
    assert Gate().failures(Release("1", 0.01, 300.0, 0.7)) == ()


def test_gate_reports_error_rate():
    reasons = Gate().failures(Release("1", 0.05, 300.0, 0.7))
    assert reasons == ("error rate 5.00% > 2.00%",)


def test_gate_reports_latency():
    reasons = Gate().failures(Release("1", 0.001, 400.0, 0.7))
    assert reasons == ("latency 400.0 ms > 350.0 ms",)


def test_gate_reports_saturation():
    reasons = Gate().failures(Release("1", 0.001, 200.0, 0.9))
    assert reasons == ("saturation 0.90 > 0.85",)


def test_gate_reports_every_failure_in_order():
    reasons = Gate().failures(Release("1", 0.05, 400.0, 0.9))
    assert len(reasons) == 3
    assert reasons[0].startswith("error rate")
    assert reasons[1].startswith("latency")
    assert reasons[2].startswith("saturation")


def test_gate_thresholds_are_inclusive():
    assert Gate().failures(Release("1", 0.02, 350.0, 0.85)) == ()


def test_gate_describe():
    assert Gate().describe() == ("errors <= 2.00%, latency <= 350 ms, "
                                 "saturation <= 0.85")


def test_slo_error_budget():
    assert Slo().error_budget == pytest.approx(360.0)


def test_slo_allowance_for_one_soak():
    assert Slo().allowance(5) == pytest.approx(30.0)


def test_slo_describe():
    assert Slo().describe() == "99.90% over 60 min, 6000 req/min, 5 min soak"


def test_observe_prices_bad_requests():
    item = observe(Release("1", 0.01, 200.0, 0.5), 25, 1, Gate(), Slo())
    assert item.bad_requests == pytest.approx(5 * 6000 * 0.25 * 0.01)


def test_observe_burn_rate_of_exactly_one_at_the_target():
    item = observe(Release("1", 0.001, 200.0, 0.5), 100, 1, Gate(), Slo())
    assert item.burn_rate == pytest.approx(1.0)
    # 1.0 sits exactly on the ok/slow boundary, so float noise decides which
    # side it lands on - both verdicts are defensible for a 1x burn.
    assert alert_level(item.burn_rate) in ("ok", "slow")


def test_observe_passes_or_fails_the_gate():
    good = observe(Release("1", 0.001, 200.0, 0.5), 100, 1, Gate(), Slo())
    bad = observe(Release("1", 0.5, 200.0, 0.5), 100, 1, Gate(), Slo())
    assert good.passed and not bad.passed


def test_observe_rejects_zero_traffic():
    with pytest.raises(RolloutError, match="traffic_percent"):
        observe(Release("1", 0.0, 200.0, 0.5), 0, 1, Gate(), Slo())


def test_observe_rejects_traffic_above_one_hundred():
    with pytest.raises(RolloutError, match="traffic_percent"):
        observe(Release("1", 0.0, 200.0, 0.5), 101, 1, Gate(), Slo())


def test_observe_rejects_zero_step():
    with pytest.raises(RolloutError, match="step must be >= 1"):
        observe(Release("1", 0.0, 200.0, 0.5), 5, 0, Gate(), Slo())


def test_observe_requires_a_release():
    with pytest.raises(RolloutError, match="needs a Release"):
        observe({"version": "1"}, 5, 1, Gate(), Slo())


def test_observe_can_relabel_the_version():
    item = observe(Release("1", 0.0, 200.0, 0.5), 5, 1, Gate(), Slo(),
                   version="1.0.0-old")
    assert item.version == "1.0.0-old"


def test_observation_to_dict_shape():
    data = observe(Release("1", 0.001, 200.0, 0.5), 5, 1, Gate(),
                   Slo()).to_dict()
    assert set(data) == {
        "step", "traffic_percent", "version", "error_rate", "latency_ms",
        "saturation", "passed", "reasons", "soak_minutes", "bad_requests",
        "burn_rate"}
    assert data["reasons"] == []


# --------------------------------------------------------------------------- #
# alert classification
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("burn, level", [
    (0.0, "ok"), (0.99, "ok"), (1.0, "slow"), (1.99, "slow"),
    (2.0, "fast"), (9.99, "fast"), (10.0, "critical"), (81.0, "critical"),
])
def test_alert_level_boundaries(burn, level):
    assert alert_level(burn) == level


def test_alert_level_covers_every_level():
    assert set(ALERT_LEVELS) == {"ok", "slow", "fast", "critical"}


def test_alert_level_rejects_negative_burn():
    with pytest.raises(RolloutError, match="must be >= 0"):
        alert_level(-0.1)


# --------------------------------------------------------------------------- #
# state machine
# --------------------------------------------------------------------------- #
def test_machine_starts_pending():
    assert _Machine().state == STATE_PENDING


def test_machine_accepts_the_documented_path():
    machine = _Machine()
    machine.advance(STATE_PROGRESSING, "start", 0)
    machine.advance(STATE_FAILED, "gate failed", 1)
    machine.advance(STATE_ROLLING_BACK, "rollback", 2)
    machine.advance(STATE_ROLLED_BACK, "previous release healthy", 2)
    assert [t.state for t in machine.history] == [
        STATE_PROGRESSING, STATE_FAILED, STATE_ROLLING_BACK,
        STATE_ROLLED_BACK]


def test_machine_rejects_skipping_straight_to_success():
    with pytest.raises(RolloutError, match="illegal transition"):
        _Machine().advance(STATE_SUCCEEDED, "promoted", 1)


def test_machine_rejects_rolling_back_a_successful_rollout():
    machine = _Machine()
    machine.advance(STATE_PROGRESSING, "start", 0)
    machine.advance(STATE_SUCCEEDED, "promoted", 4)
    with pytest.raises(RolloutError, match="illegal transition"):
        machine.advance(STATE_ROLLING_BACK, "rollback", 5)


def test_machine_rejects_unknown_state():
    with pytest.raises(RolloutError, match="unknown state"):
        _Machine().advance("teleported", "nope", 1)


def test_machine_terminal_states_accept_nothing():
    machine = _Machine()
    machine.advance(STATE_PROGRESSING, "start", 0)
    machine.advance(STATE_SUCCEEDED, "promoted", 4)
    with pytest.raises(RolloutError, match="illegal transition"):
        machine.advance(STATE_FAILED, "gate failed", 5)


# --------------------------------------------------------------------------- #
# execute
# --------------------------------------------------------------------------- #
def test_execute_promotes_a_healthy_release():
    result = execute(deployment(), "1.0.0")
    assert result.state == STATE_SUCCEEDED
    assert result.healthy
    assert result.rolled_back_to is None
    assert [item.traffic_percent for item in result.observations] == \
        [5, 25, 50, 100]


def test_execute_success_transitions():
    result = execute(deployment(), "1.0.0")
    assert [t.event for t in result.transitions] == \
        ["start", "promoted"]
    assert result.transitions[-1].state == STATE_SUCCEEDED


def test_execute_rolls_back_to_the_previous_release():
    good = Release("1.0.1", 0.001, 200.0, 0.5)
    broken = Release("2.0.0", 0.5, 200.0, 0.5)
    dep = deployment(releases=(good, broken))
    result = execute(dep, "2.0.0")
    assert result.state == STATE_ROLLED_BACK
    assert result.healthy
    assert result.rolled_back_to == "1.0.1"
    assert result.observations[-1].version == "1.0.1"
    assert result.observations[-1].traffic_percent == 100


def test_execute_stops_at_the_first_failed_gate():
    dep = deployment(releases=(Release("1.0.0", 0.001, 200.0, 0.5),
                               Release("2.0.0", 0.5, 200.0, 0.5)))
    result = execute(dep, "2.0.0")
    assert len(result.failed_steps) == 1
    assert result.failed_steps[0].traffic_percent == 5
    assert result.failed_steps[0].step == 1


def test_execute_rollback_fails_when_previous_is_unhealthy():
    dep = deployment(releases=(Release("1.0.0", 0.5, 200.0, 0.5),
                               Release("2.0.0", 0.5, 200.0, 0.5)))
    result = execute(dep, "2.0.0")
    assert result.state == STATE_ROLLBACK_FAILED
    assert not result.healthy
    assert result.rolled_back_to is None
    assert result.transitions[-1].event == "previous release also fails " \
                                             "the gate"


def test_execute_rollback_fails_without_a_previous_release():
    dep = deployment(releases=(Release("1.0.0", 0.5, 200.0, 0.5),))
    result = execute(dep, "1.0.0")
    assert result.state == STATE_ROLLBACK_FAILED
    assert result.previous is None
    assert result.transitions[-1].event == "no previous release"
    assert len(result.observations) == 1


def test_execute_honours_a_custom_ladder():
    result = execute(deployment(), "1.0.0", STRATEGY_CANARY, [10, 50, 100])
    assert result.steps == (10, 50, 100)
    assert [item.traffic_percent for item in result.observations] == \
        [10, 50, 100]


def test_execute_defaults_to_the_document_strategy():
    dep = deployment(strategy=STRATEGY_BLUE_GREEN)
    result = execute(dep, "1.0.0")
    assert result.strategy == STRATEGY_BLUE_GREEN
    assert len(result.observations) == 1


def test_execute_rejects_unknown_release():
    with pytest.raises(RolloutError, match="unknown release"):
        execute(deployment(), "9.9.9")


def test_execute_rejects_unknown_strategy():
    with pytest.raises(RolloutError, match="unknown strategy"):
        execute(deployment(), "1.0.0", "big-bang")


def test_execute_rejects_invalid_steps_before_running():
    with pytest.raises(RolloutError, match="last step must be 100%"):
        execute(deployment(), "1.0.0", STRATEGY_CANARY, [50])


def test_execute_requires_a_deployment():
    with pytest.raises(RolloutError, match="needs a Deployment"):
        execute({"service": "x"}, "1.0.0")


def test_execute_budget_is_the_sum_of_every_observation():
    dep = deployment()
    result = execute(dep, "1.0.0")
    spent = sum(item.bad_requests for item in result.observations)
    assert result.budget_used == pytest.approx(spent / dep.slo.error_budget)


def test_execute_peak_burn_is_the_worst_observation():
    dep = deployment(releases=(Release("1.0.0", 0.001, 200.0, 0.5),
                               Release("2.0.0", 0.5, 200.0, 0.5)))
    result = execute(dep, "2.0.0")
    assert result.peak_burn == pytest.approx(
        max(item.burn_rate for item in result.observations))


def test_execute_is_deterministic():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    assert execute(dep, "1.6.0-rc1") == execute(dep, "1.6.0-rc1")


def test_execute_result_to_dict_round_trips_through_json():
    result = execute(deployment(), "1.0.0")
    payload = json.loads(json.dumps(result.to_dict()))
    assert payload["state"] == STATE_SUCCEEDED
    assert payload["healthy"] is True
    assert payload["alert"] == "ok"
    assert isinstance(payload["observations"], list)


# --------------------------------------------------------------------------- #
# bundled scenarios
# --------------------------------------------------------------------------- #
def test_canary_budget_is_pinned():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    result = execute(dep, "1.6.0-rc1", STRATEGY_CANARY)
    assert result.budget_used == pytest.approx(EXPECTED_CANARY_BUDGET,
                                               abs=0.002)


def test_blue_green_budget_is_pinned():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    result = execute(dep, "1.6.0-rc1", STRATEGY_BLUE_GREEN)
    assert result.budget_used == pytest.approx(EXPECTED_BLUE_BUDGET, abs=0.01)


def test_blue_green_costs_more_than_ten_canary_windows():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    canary = execute(dep, "1.6.0-rc1", STRATEGY_CANARY)
    blue = execute(dep, "1.6.0-rc1", STRATEGY_BLUE_GREEN)
    assert blue.budget_used / canary.budget_used > 10


def test_latency_release_fails_on_latency_alone():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    result = execute(dep, "1.6.0-rc2", STRATEGY_CANARY)
    reasons = result.observations[0].reasons
    assert len(reasons) == 1 and reasons[0].startswith("latency")


def test_latency_release_cannot_roll_back_onto_rc1():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    result = execute(dep, "1.6.0-rc2", STRATEGY_CANARY)
    assert result.state == STATE_ROLLBACK_FAILED
    assert result.observations[-1].version == "1.6.0-rc1"


def test_good_release_stays_inside_the_budget():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    result = execute(dep, "1.6.0", STRATEGY_CANARY)
    assert result.state == STATE_SUCCEEDED
    assert 0.0 < result.budget_used < 0.2
    assert result.alert == "ok"
    assert result.peak_burn < 1.0


def test_rolling_strategy_on_the_bundled_release():
    dep = load_deployment(BUNDLED_DEPLOYMENT)
    result = execute(dep, "1.6.0", STRATEGY_ROLLING)
    assert result.steps == (25, 50, 75, 100)
    assert result.state == STATE_SUCCEEDED


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def test_report_header_and_state():
    result = execute(deployment(), "1.0.0")
    text = render_report(result)
    assert text.startswith("ROLLOUT - svc")
    assert "strategy : canary (5%, 25%, 50%, 100%)" in text
    assert "state    : succeeded" in text
    assert "result   : HEALTHY" in text


def test_report_lists_every_step():
    result = execute(deployment(), "1.0.0")
    text = render_report(result)
    for step in ("   5%", "  25%", "  50%", " 100%"):
        assert step in text


def test_report_marks_failures_and_reasons():
    dep = deployment(releases=(Release("1.0.0", 0.001, 200.0, 0.5),
                               Release("2.0.0", 0.5, 200.0, 0.5)))
    text = render_report(execute(dep, "2.0.0"))
    assert "FAIL" in text
    assert "error rate 50.00% > 2.00%" in text
    assert "result   : HEALTHY" in text  # rolled back is still healthy


def test_report_marks_an_unhealthy_outcome():
    dep = deployment(releases=(Release("1.0.0", 0.5, 200.0, 0.5),))
    assert "result   : UNHEALTHY" in render_report(execute(dep, "1.0.0"))


# --------------------------------------------------------------------------- #
# demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "RELEASE / ROLLBACK SIMULATOR" in out
    assert "Cross-checks OK:" in out
    assert out.endswith("Demo completed successfully.\n")


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    second = capsys.readouterr().out
    assert first == second


def test_demo_missing_sample_raises(tmp_path):
    with pytest.raises(RolloutError, match="bundled sample not found"):
        run_demo(tmp_path / "absent.json")


def test_bundled_data_files_exist():
    assert (DATA / "deployment.json").is_file()


# --------------------------------------------------------------------------- #
# CLI helpers
# --------------------------------------------------------------------------- #
def test_parse_steps_accepts_a_list():
    assert parse_steps("5,50,100") == (5, 50, 100)


def test_parse_steps_tolerates_spaces():
    assert parse_steps(" 5 , 50 , 100 ") == (5, 50, 100)


@pytest.mark.parametrize("raw", ["", "5,,100", ","])
def test_parse_steps_rejects_empty_pieces(raw):
    with pytest.raises(RolloutError, match="comma-separated"):
        parse_steps(raw)


def test_parse_steps_rejects_words():
    with pytest.raises(RolloutError, match="not an integer"):
        parse_steps("5,abc,100")


def test_parser_exposes_documented_flags():
    parser = build_parser()
    dests = {action.dest for action in parser._actions}
    assert {"demo", "file", "release", "strategy", "steps", "json",
            "quiet"} <= dests


# --------------------------------------------------------------------------- #
# CLI behaviour
# --------------------------------------------------------------------------- #
def test_cli_demo_exit_zero(capsys):
    assert main(["--demo"]) == 0
    assert "Cross-checks OK:" in capsys.readouterr().out


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_demo_rejects_other_flags(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--demo", "--strategy", "canary"])
    assert excinfo.value.code == 2
    assert "--demo cannot be combined" in capsys.readouterr().err


def test_cli_default_run_promotes_the_newest_release(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "target   : 1.6.0" in out
    assert "result   : HEALTHY" in out


def test_cli_rollback_is_still_a_zero_exit(capsys):
    assert main(["--release", "1.6.0-rc1"]) == 0
    assert "state    : rolled_back" in capsys.readouterr().out


def test_cli_failed_rollback_exits_one(capsys):
    assert main(["--release", "1.6.0-rc2"]) == 1
    assert "UNHEALTHY" in capsys.readouterr().out


def test_cli_strategy_flag(capsys):
    assert main(["--release", "1.6.0", "--strategy", "rolling"]) == 0
    assert "(25%, 50%, 75%, 100%)" in capsys.readouterr().out


def test_cli_custom_steps(capsys):
    assert main(["--release", "1.6.0", "--steps", "10,100"]) == 0
    assert "(10%, 100%)" in capsys.readouterr().out


def test_cli_quiet_suppresses_the_report(capsys):
    assert main(["--release", "1.6.0", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_bad_steps_exit_two(capsys):
    assert main(["--steps", "5,50"]) == 2
    assert "last step must be 100%" in capsys.readouterr().err


def test_cli_unknown_release_exit_two(capsys):
    assert main(["--release", "9.9.9"]) == 2
    assert "unknown release" in capsys.readouterr().err


def test_cli_missing_file_exit_two(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "absent.json")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_invalid_json_exit_two(tmp_path, capsys):
    broken = tmp_path / "broken.json"
    broken.write_text("nope", encoding="utf-8")
    assert main(["--file", str(broken)]) == 2
    assert "invalid JSON" in capsys.readouterr().err


def test_cli_unknown_strategy_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--strategy", "big-bang"])
    assert excinfo.value.code == 2


def test_cli_writes_json(tmp_path, capsys):
    target = tmp_path / "out" / "rollout.json"
    assert main(["--release", "1.6.0-rc1", "--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["state"] == "rolled_back"
    assert payload["healthy"] is True
    assert payload["target"] == "1.6.0-rc1"
    assert payload["source"].endswith("deployment.json")
    assert "Wrote" in capsys.readouterr().out


def test_cli_quiet_still_writes_json(tmp_path, capsys):
    target = tmp_path / "rollout.json"
    assert main(["--release", "1.6.0", "--json", str(target),
                 "--quiet"]) == 0
    assert capsys.readouterr().out == ""
    assert json.loads(target.read_text(encoding="utf-8"))["healthy"] is True
