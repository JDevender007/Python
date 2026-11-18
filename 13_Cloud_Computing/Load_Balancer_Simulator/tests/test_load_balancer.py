"""Tests for the Load Balancer Simulator project."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from load_balancer import (  # noqa: E402
    DATA_DIR,
    LEGACY_ACTIVE,
    LEGACY_CHOOSE,
    LEGACY_FAIRNESS,
    LEGACY_SHARE,
    MAX_BACKENDS,
    MAX_REQUESTS,
    MAX_WEIGHT,
    MAX_WORK,
    POLICIES,
    Backend,
    Request,
    Run,
    Scenario,
    ScenarioError,
    apportion_permille,
    audit,
    capacity_verdict,
    ceil_div,
    divide_half_up,
    jain_permille,
    legacy_fairness,
    legacy_shares,
    legacy_verdict,
    load_document,
    max_load_permille,
    measure,
    read_scenario,
    render_run,
    report,
    run_demo,
    scenario_from_document,
    simulate,
    spread,
    validate_or_raise,
    validate_scenario,
)
from main import main  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def scenario(backends: int = 3, requests: int = 12, work: int = 4) -> Scenario:
    names = ["alpha", "beta", "gamma", "delta"][:backends]
    weights = [1, 2, 1, 1][:backends]
    return Scenario(
        "test",
        tuple(Backend(name, weight) for name, weight in zip(names, weights)),
        tuple(Request(f"r{index:02d}", work) for index in range(1, requests + 1)),
    )


def write_scenario(tmp_path: Path, document: object) -> Path:
    target = tmp_path / "scenario.json"
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Integer arithmetic
# --------------------------------------------------------------------------- #
def test_divide_half_up_rounds_a_half_away_from_zero():
    assert divide_half_up(1, 2) == 1


def test_divide_half_up_rounds_below_a_half_down():
    assert divide_half_up(1, 4) == 0


def test_divide_half_up_rounds_above_a_half_up():
    assert divide_half_up(2, 3) == 1
    assert divide_half_up(5, 2) == 3


def test_divide_half_up_keeps_exact_ratios():
    assert divide_half_up(6, 2) == 3
    assert divide_half_up(0, 7) == 0


def test_divide_half_up_refuses_a_zero_divisor():
    with pytest.raises(ScenarioError, match="divisor must be positive"):
        divide_half_up(1, 0)


def test_divide_half_up_refuses_a_negative_dividend():
    with pytest.raises(ScenarioError, match="dividend must be non-negative"):
        divide_half_up(-1, 2)


def test_ceil_div_rounds_up_any_remainder():
    assert ceil_div(5, 2) == 3
    assert ceil_div(1, 3) == 1


def test_ceil_div_keeps_exact_multiples():
    assert ceil_div(4, 2) == 2
    assert ceil_div(0, 4) == 0


def test_ceil_div_refuses_a_zero_divisor():
    with pytest.raises(ScenarioError, match="divisor must be positive"):
        ceil_div(1, 0)


def test_jain_of_equal_counts_is_one_thousand():
    assert jain_permille([4, 4, 4]) == 1000


def test_jain_of_the_weighted_split_is_889():
    assert jain_permille([3, 6, 3]) == 889


def test_jain_of_a_single_backend_is_perfect():
    assert jain_permille([12]) == 1000


def test_jain_of_a_collapsed_distribution_is_333():
    assert jain_permille([12, 0, 0]) == 333


def test_jain_of_all_zeroes_is_zero():
    assert jain_permille([0, 0, 0]) == 0


def test_jain_refuses_an_empty_sequence():
    with pytest.raises(ScenarioError, match="non-negative values"):
        jain_permille([])


def test_jain_refuses_a_negative_value():
    with pytest.raises(ScenarioError, match="non-negative values"):
        jain_permille([1, -1])


def test_apportioned_equal_thirds_sum_to_one_thousand():
    assert apportion_permille([4, 4, 4]) == [334, 333, 333]


def test_apportioned_weighted_split_is_exact():
    assert apportion_permille([3, 6, 3]) == [250, 500, 250]


def test_apportionment_gives_the_remainder_to_the_first_of_equal_parts():
    assert apportion_permille([1, 1, 1]) == [334, 333, 333]


def test_apportionment_of_zeroes_is_zeroes():
    assert apportion_permille([0, 0, 0]) == [0, 0, 0]


def test_apportionment_of_one_winner_is_unanimous():
    assert apportion_permille([5, 0, 0]) == [1000, 0, 0]


@pytest.mark.parametrize("parts", [[1], [1, 1], [2, 3, 5], [7, 0, 2, 1], [4, 4, 4, 4]])
def test_apportionment_always_sums_to_one_thousand(parts):
    assert sum(apportion_permille(parts)) == 1000


def test_apportionment_refuses_a_negative_part():
    with pytest.raises(ScenarioError, match="non-negative parts"):
        apportion_permille([1, -1])


def test_legacy_float_shares_sum_to_99_9_for_equal_counts():
    shares = legacy_shares([4, 4, 4])
    assert shares == [33.3, 33.3, 33.3]
    assert round(sum(shares), 1) == 99.9


def test_legacy_float_shares_of_a_collapse_are_one_hundred():
    assert legacy_shares([12, 0, 0]) == [100.0, 0.0, 0.0]


def test_legacy_float_shares_of_zeroes_are_zero():
    assert legacy_shares([0, 0]) == [0.0, 0.0]


def test_spread_is_zero_for_equal_counts():
    assert spread([4, 4, 4]) == 0


def test_spread_is_the_gap_between_largest_and_smallest():
    assert spread([3, 6, 3]) == 3
    assert spread([12, 0, 0]) == 12


def test_spread_of_nothing_is_zero():
    assert spread([]) == 0


def test_legacy_verdict_is_perfect_only_for_equal_counts():
    assert legacy_verdict([4, 4, 4]) == "perfect"
    assert legacy_verdict([3, 6, 3]) == "uneven"


@pytest.mark.parametrize(
    "load,verdict",
    [(1000, "balanced"), (1050, "balanced"), (1051, "acceptable"),
     (1250, "acceptable"), (1251, "overloaded"), (4000, "overloaded")],
)
def test_capacity_verdict_bands(load, verdict):
    assert capacity_verdict(load) == verdict


# --------------------------------------------------------------------------- #
# Records and documents
# --------------------------------------------------------------------------- #
def test_backend_reports_itself_as_a_dict():
    assert Backend("alpha", 2).to_dict() == {"name": "alpha", "weight": 2}


def test_request_reports_itself_as_a_dict():
    assert Request("r1", 4).to_dict() == {"name": "r1", "work": 4}


def test_a_backend_is_frozen():
    backend = Backend("alpha", 1)
    with pytest.raises(Exception):
        backend.weight = 2  # type: ignore[misc]


def test_load_document_reads_the_bundled_scenario():
    document = load_document(DATA_DIR / "scenario.json")
    assert document["name"] == "three-tier"
    assert len(document["backends"]) == 3


def test_load_document_refuses_a_missing_file(tmp_path):
    with pytest.raises(ScenarioError, match="scenario not found: nope.json"):
        load_document(tmp_path / "nope.json")


def test_load_document_refuses_non_ascii_bytes(tmp_path):
    target = tmp_path / "bad.json"
    target.write_bytes(b'{"name": "thr\xc3\xa9e"}')
    with pytest.raises(ScenarioError, match="bad.json is not ASCII text"):
        load_document(target)


def test_load_document_names_the_line_of_broken_json(tmp_path):
    target = tmp_path / "broken.json"
    target.write_text('{"name": "x",}', encoding="utf-8")
    with pytest.raises(ScenarioError, match="broken.json is not valid JSON: line 1"):
        load_document(target)


def test_load_document_refuses_a_list_root(tmp_path):
    target = tmp_path / "list.json"
    target.write_text("[]", encoding="utf-8")
    with pytest.raises(ScenarioError, match="a scenario root must be a mapping"):
        load_document(target)


def test_read_scenario_builds_the_bundled_records():
    built = read_scenario()
    assert [backend.name for backend in built.backends] == ["alpha", "beta", "gamma"]
    assert [backend.weight for backend in built.backends] == [1, 2, 1]
    assert len(built.requests) == 12


def test_read_scenario_reads_an_explicit_path(tmp_path):
    target = write_scenario(
        tmp_path,
        {"name": "mini", "backends": [{"name": "alpha", "weight": 1}],
         "requests": [{"name": "r1", "work": 2}]},
    )
    built = read_scenario(target)
    assert built.name == "mini"
    assert built.requests[0].work == 2


def test_scenario_from_document_ignores_a_non_list_backends_field():
    built = scenario_from_document({"name": "x", "backends": {}, "requests": []})
    assert built.backends == ()


def test_scenario_from_document_ignores_non_object_entries():
    built = scenario_from_document(
        {"name": "x", "backends": ["alpha"], "requests": [1, 2]}
    )
    assert built.backends == ()
    assert built.requests == ()


def test_scenario_from_document_turns_a_boolean_weight_into_zero():
    built = scenario_from_document(
        {"name": "x", "backends": [{"name": "alpha", "weight": True}], "requests": []}
    )
    assert built.backends[0].weight == 0


def test_scenario_from_document_turns_a_text_weight_into_zero():
    built = scenario_from_document(
        {"name": "x", "backends": [{"name": "alpha", "weight": "2"}], "requests": []}
    )
    assert built.backends[0].weight == 0


def test_the_bundled_scenario_validates():
    assert validate_scenario(read_scenario()) == []


def test_a_bad_scenario_name_is_reported():
    broken = replace(scenario(), name="Three Tier")
    assert "$.name: a lowercase slug is required" in validate_scenario(broken)


def test_an_empty_backend_list_is_reported():
    broken = Scenario("test", (), scenario().requests)
    assert any("non-empty array" in item for item in validate_scenario(broken))


def test_too_many_backends_are_reported():
    backends = tuple(Backend(f"b{index:02d}", 1) for index in range(MAX_BACKENDS + 1))
    assert any(f"at most {MAX_BACKENDS}" in item for item in validate_scenario(
        Scenario("test", backends, scenario().requests)
    ))


def test_a_bad_backend_name_is_reported():
    broken = replace(scenario(), backends=(Backend("Alpha", 1),))
    assert any("$.backends[0].name" in item for item in validate_scenario(broken))


def test_a_duplicate_backend_name_is_reported():
    broken = replace(scenario(), backends=(Backend("alpha", 1), Backend("alpha", 2)))
    assert any("duplicate backend 'alpha'" in item for item in validate_scenario(broken))


def test_a_zero_weight_is_reported():
    broken = replace(scenario(), backends=(Backend("alpha", 0),))
    assert any("$.backends[0].weight" in item for item in validate_scenario(broken))


def test_a_weight_above_the_cap_is_reported():
    broken = replace(scenario(), backends=(Backend("alpha", MAX_WEIGHT + 1),))
    assert any("$.backends[0].weight" in item for item in validate_scenario(broken))


def test_the_weight_cap_is_inclusive():
    assert validate_scenario(
        Scenario("test", (Backend("alpha", MAX_WEIGHT),), (Request("r1", 1),))
    ) == []


def test_an_empty_request_list_is_reported():
    broken = replace(scenario(), requests=())
    assert any("$.requests: a non-empty array" in item for item in validate_scenario(broken))


def test_too_many_requests_are_reported():
    requests = tuple(Request(f"r{index}", 1) for index in range(MAX_REQUESTS + 1))
    assert any(f"at most {MAX_REQUESTS}" in item for item in validate_scenario(
        Scenario("test", (Backend("alpha", 1),), requests)
    ))


def test_an_empty_request_name_is_reported():
    broken = replace(scenario(), requests=(Request("", 4),))
    assert any("$.requests[0].name" in item for item in validate_scenario(broken))


def test_a_duplicate_request_name_is_reported():
    broken = replace(scenario(), requests=(Request("r1", 4), Request("r1", 4)))
    assert any("duplicate request 'r1'" in item for item in validate_scenario(broken))


def test_a_zero_work_unit_is_reported():
    broken = replace(scenario(), requests=(Request("r1", 0),))
    assert any("$.requests[0].work" in item for item in validate_scenario(broken))


def test_a_work_value_above_the_cap_is_reported():
    broken = replace(scenario(), requests=(Request("r1", MAX_WORK + 1),))
    assert any("$.requests[0].work" in item for item in validate_scenario(broken))


def test_the_work_cap_is_inclusive():
    assert validate_scenario(
        Scenario("test", (Backend("alpha", 1),), (Request("r1", MAX_WORK),))
    ) == []


def test_validate_or_raise_names_the_problem_count():
    broken = Scenario("Bad Name", (), ())
    with pytest.raises(ScenarioError, match=r"invalid scenario \(3 problem"):
        validate_or_raise(broken)


def test_validate_or_raise_accepts_the_bundled_scenario():
    assert validate_or_raise(read_scenario()) is None


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
def test_simulate_refuses_an_unknown_policy():
    with pytest.raises(ScenarioError, match="unknown policy 'magic'"):
        simulate(scenario(), "magic")


def test_simulate_refuses_an_invalid_scenario():
    with pytest.raises(ScenarioError, match="invalid scenario"):
        simulate(Scenario("test", (Backend("alpha", 0),), (Request("r1", 4),)), "round_robin")


def test_round_robin_serves_equal_counts():
    run = simulate(scenario(), "round_robin")
    assert run.counts == (4, 4, 4)


def test_round_robin_ignores_capacity_and_overloads_the_small_backend():
    run = simulate(scenario(), "round_robin")
    assert run.work == (16, 16, 16)
    assert run.max_load == 1333
    assert run.jain_capacity == 926


def test_round_robin_makespan_is_sixteen_ticks():
    assert simulate(scenario(), "round_robin").makespan == 16


def test_round_robin_total_completion_is_one_hundred():
    assert simulate(scenario(), "round_robin").total_finish == 100


def test_smooth_weighted_matches_the_weight_ratio():
    run = simulate(scenario(), "smooth_weighted")
    assert run.counts == (3, 6, 3)


def test_smooth_weighted_places_beta_first():
    placements = simulate(scenario(), "smooth_weighted").placements
    assert [item.backend for item in placements[:4]] == ["beta", "alpha", "gamma", "beta"]


def test_smooth_weighted_reaches_a_balanced_load():
    run = simulate(scenario(), "smooth_weighted")
    assert run.work == (12, 24, 12)
    assert run.max_load == 1000
    assert run.jain_capacity == 1000


def test_least_load_matches_the_weight_ratio():
    run = simulate(scenario(), "least_load")
    assert run.counts == (3, 6, 3)


def test_least_load_places_beta_first_and_again_third():
    placements = simulate(scenario(), "least_load").placements
    assert [item.backend for item in placements[:3]] == ["beta", "alpha", "beta"]


def test_least_load_shortens_the_makespan_to_twelve():
    run = simulate(scenario(), "least_load")
    assert run.makespan == 12
    assert run.total_finish == 90


def test_two_policies_agree_on_counts_but_not_on_placements():
    weighted = simulate(scenario(), "smooth_weighted")
    least = simulate(scenario(), "least_load")
    assert weighted.counts == least.counts
    assert weighted.placements != least.placements


def test_legacy_least_connections_sends_every_request_to_the_first_backend():
    run = simulate(scenario(), "legacy_least_connections")
    assert run.counts == (12, 0, 0)
    assert run.work == (48, 0, 0)


def test_legacy_samples_are_always_zero():
    run = simulate(scenario(), "legacy_least_connections")
    assert len(run.samples) == 12
    assert set(run.samples) == {(0, 0, 0)}


def test_legacy_makespan_is_forty_eight_ticks():
    assert simulate(scenario(), "legacy_least_connections").makespan == 48


def test_legacy_total_completion_is_three_hundred_and_twelve():
    assert simulate(scenario(), "legacy_least_connections").total_finish == 312


def test_legacy_jain_scores_are_both_333():
    run = simulate(scenario(), "legacy_least_connections")
    assert run.jain_counts == 333
    assert run.jain_capacity == 333


def test_finish_ticks_follow_the_weighted_queue():
    run = simulate(scenario(), "least_load")
    assert run.finishes[0] == (4, 8, 12)
    assert run.finishes[1] == (2, 4, 6, 8, 10, 12)
    assert run.finishes[2] == (4, 8, 12)


def test_every_request_is_placed_once_and_in_order():
    run = simulate(scenario(), "least_load")
    assert [item.request for item in run.placements] == [
        f"r{index:02d}" for index in range(1, 13)
    ]


def test_a_request_finishes_at_the_ceiling_of_its_queue():
    run = simulate(scenario(), "least_load")
    for index, ticks in enumerate(run.finishes):
        remaining = 0
        for tick in ticks:
            remaining += 4
            assert tick == ceil_div(remaining, run.weights[index])


def test_run_shares_are_apportioned_permille():
    assert simulate(scenario(), "round_robin").shares == (334, 333, 333)


def test_run_reports_itself_as_a_json_safe_dict():
    body = simulate(scenario(), "least_load").to_dict()
    assert body["policy"] == "least_load"
    assert body["counts"] == [3, 6, 3]
    assert body["max_load"] == 1000
    assert body["placements"][0] == {"request": "r01", "backend": "beta", "finish": 2}


def test_max_load_permille_of_a_single_backend_is_one_thousand():
    single = Scenario("test", (Backend("alpha", 3),), (Request("r1", 4), Request("r2", 4)))
    assert max_load_permille(simulate(single, "round_robin")) == 1000


def test_max_load_permille_of_an_empty_run_is_zero():
    empty = Run("round_robin", ("alpha",), (0,), (0,), ((),), ())
    assert max_load_permille(empty) == 0


def test_legacy_fairness_calls_equal_counts_perfect_but_overloaded():
    result = legacy_fairness(simulate(scenario(), "round_robin"))
    assert result["spread"] == 0
    assert result["verdict"] == "perfect"
    assert result["load_verdict"] == "overloaded"
    assert result["max_load"] == 1333


def test_legacy_fairness_accepts_the_weighted_split():
    result = legacy_fairness(simulate(scenario(), "smooth_weighted"))
    assert result["spread"] == 3
    assert result["verdict"] == "uneven"
    assert result["load_verdict"] == "balanced"


def test_all_four_policies_are_present():
    assert POLICIES == (
        "round_robin",
        "smooth_weighted",
        "legacy_least_connections",
        "least_load",
    )


# --------------------------------------------------------------------------- #
# Measurement and the JSON report
# --------------------------------------------------------------------------- #
def test_measure_returns_four_runs():
    assert set(measure()["runs"]) == set(POLICIES)


def test_measure_keeps_the_bundled_scenario():
    assert measure()["scenario"].name == "three-tier"


def test_measure_pins_the_round_robin_run():
    run = measure()["runs"]["round_robin"]
    assert run.counts == (4, 4, 4)
    assert run.makespan == 16


def test_measure_pins_the_legacy_run():
    run = measure()["runs"]["legacy_least_connections"]
    assert run.counts == (12, 0, 0)
    assert run.samples[0] == (0, 0, 0)


def test_measure_keeps_float_shares_for_the_comparison():
    measured = measure()
    assert measured["float_shares"]["round_robin"] == [33.3, 33.3, 33.3]
    assert measured["float_totals"]["round_robin"] == 99.9


def test_measure_is_deterministic_across_calls():
    first = measure()
    second = measure()
    assert first["runs"]["least_load"] == second["runs"]["least_load"]
    assert first["float_totals"] == second["float_totals"]


def test_report_is_json_safe():
    body = json.loads(json.dumps(report(measure())))
    assert body["scenario"] == "three-tier"
    assert body["runs"]["least_load"]["counts"] == [3, 6, 3]


def test_report_holds_records_as_lists_of_scalars():
    body = report(measure())
    assert body["backends"][0] == {"name": "alpha", "weight": 1}
    assert body["requests"][0] == {"name": "r01", "work": 4}


def test_report_keeps_every_run():
    assert set(report(measure())["runs"]) == set(POLICIES)


# --------------------------------------------------------------------------- #
# Audit and its negative controls
# --------------------------------------------------------------------------- #
def test_audit_reports_fifteen_checks_and_all_pass():
    results = audit(measure())
    assert len(results) == 15
    assert [name for name, okay in results if not okay] == []


def test_every_audit_check_has_a_name():
    assert all(isinstance(name, str) and name for name, _ in audit(measure()))


def test_a_different_scenario_flips_the_weight_check():
    flat = Scenario(
        "flat",
        (Backend("alpha", 1), Backend("beta", 1), Backend("gamma", 1)),
        scenario().requests,
    )
    results = dict(audit(measure(), read=lambda: flat))
    assert results["a_weight_is_capacity_not_a_count"] is False
    assert results["least_load_splits_work_by_capacity"] is False


def test_a_six_request_scenario_flips_the_count_checks():
    shorter = scenario(requests=6)
    results = dict(audit(measure(), read=lambda: shorter))
    assert results["round_robin_serves_equal_counts"] is False
    assert results["the_bundled_scenario_is_pinned"] is False


def test_a_doctored_legacy_run_flips_the_counter_check():
    def doctored(built: Scenario, policy: str) -> Run:
        run = simulate(built, policy)
        if policy == "legacy_least_connections":
            return replace(run, counts=(6, 6, 0))
        return run

    results = dict(audit(measure(), run=doctored))
    assert results["the_in_flight_counter_is_always_zero"] is False


def test_a_raising_reader_fails_checks_instead_of_raising():
    def explode() -> Scenario:
        raise RuntimeError("disk gone")

    results = dict(audit(measure(), read=explode))
    assert any(value is False for value in results.values())
    assert results["the_scenario_reads_and_validates"] is False


def test_a_tampered_round_robin_count_flips_the_chained_check():
    measured = measure()
    measured["runs"]["round_robin"] = replace(
        measured["runs"]["round_robin"], counts=(5, 4, 3)
    )
    results = dict(audit(measured))
    assert results["round_robin_serves_equal_counts"] is False


def test_a_tampered_makespan_flips_the_makespan_check():
    measured = measure()
    measured["runs"]["least_load"] = replace(
        measured["runs"]["least_load"], finishes=((16,), (16,), (16,))
    )
    results = dict(audit(measured))
    assert results["the_broken_counter_costs_the_makespan"] is False


def test_a_tampered_placement_flips_the_determinism_check():
    measured = measure()
    measured["runs"]["least_load"] = replace(
        measured["runs"]["least_load"], placements=()
    )
    results = dict(audit(measured))
    assert results["the_rebuild_is_deterministic"] is False


# --------------------------------------------------------------------------- #
# The demo contract
# --------------------------------------------------------------------------- #
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


def test_run_demo_prints_the_legacy_shortcuts(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert LEGACY_ACTIVE in out
    assert LEGACY_CHOOSE in out
    assert LEGACY_FAIRNESS in out
    assert LEGACY_SHARE in out


def test_run_demo_prints_the_pinned_pairs(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "samples: (0, 0, 0) every time" in out
    assert "334 + 333 + 333 = 1000" in out
    assert "15/15 checks pass" in out


def test_run_demo_reports_the_legacy_collapse(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "all 12 requests go to alpha: counts 12/0/0" in out


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


def test_cli_audit_returns_zero_and_prints_pass_lines(capsys):
    assert main(["--audit"]) == 0
    assert "PASS  the_in_flight_counter_is_always_zero" in capsys.readouterr().out


def test_cli_writes_a_json_report(tmp_path):
    target = tmp_path / "nested" / "report.json"
    assert main(["--json", str(target)]) == 0
    body = json.loads(target.read_text(encoding="utf-8"))
    assert body["runs"]["least_load"]["makespan"] == 12


def test_cli_prints_all_four_tables_by_default(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    for policy in POLICIES:
        assert f"Policy   : {policy}" in out


def test_cli_prints_only_the_named_policy(capsys):
    assert main(["--policy", "least_load"]) == 0
    out = capsys.readouterr().out
    assert "Policy   : least_load" in out
    assert "Policy   : round_robin" not in out


def test_cli_refuses_a_missing_scenario_with_exit_two(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "absent.json")]) == 2
    assert "error: scenario not found" in capsys.readouterr().err


def test_cli_refuses_an_invalid_scenario_with_exit_two(tmp_path, capsys):
    target = write_scenario(
        tmp_path,
        {"name": "bad", "backends": [{"name": "alpha", "weight": 0}],
         "requests": [{"name": "r1", "work": 4}]},
    )
    assert main(["--file", str(target)]) == 2
    assert "invalid scenario" in capsys.readouterr().err


def test_cli_accepts_an_explicit_scenario(tmp_path, capsys):
    target = write_scenario(
        tmp_path,
        {"name": "mini", "backends": [{"name": "alpha", "weight": 1}],
         "requests": [{"name": "r1", "work": 4}]},
    )
    assert main(["--file", str(target), "--policy", "least_load"]) == 0
    assert "Policy   : least_load" in capsys.readouterr().out


def test_cli_quiet_without_demo_prints_nothing(capsys):
    assert main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_the_bundled_scenario_is_ascii():
    raw = (DATA_DIR / "scenario.json").read_bytes()
    assert all(byte < 128 for byte in raw)
