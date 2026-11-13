"""Tests for the CI Pipeline Simulator project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pipeline import (  # noqa: E402
    BUNDLED_JSON,
    BUNDLED_TOML,
    DATA_DIR,
    EXPECTED_CLEAN_WALL,
    FAIL_MODES,
    MAX_RETRIES,
    MAX_STAGES,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    STATUSES,
    JobResult,
    Pipeline,
    PipelineError,
    Stage,
    critical_path,
    dependency_depth,
    job_attempts,
    load_pipeline,
    parse_pipeline_data,
    render_report,
    run_demo,
    simulate,
    topological_order,
)
from main import build_parser, main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _stage(name, **kwargs):
    return Stage(name=name, **kwargs)


def _linear() -> Pipeline:
    """checkout -> build -> test, plus an independent docs stage."""
    return Pipeline("linear", (
        _stage("checkout", duration=10),
        _stage("build", needs=("checkout",), duration=20),
        _stage("test", needs=("build",), duration=30),
        _stage("docs", needs=("checkout",), duration=5),
    ))


def _matrix() -> Pipeline:
    return Pipeline("matrix", (
        _stage("checkout", duration=5),
        _stage("unit", needs=("checkout",), duration=40, retries=1,
               matrix=(("python", ("3.11", "3.12")), ("os", ("a", "b")))),
    ))


def _doc(**overrides) -> dict:
    base = {"stages": [{"name": "solo", "duration": 10}]}
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Parsing and validation
# --------------------------------------------------------------------------- #
def test_parse_minimal_document():
    pipeline = parse_pipeline_data(_doc())
    assert pipeline.name == "pipeline"
    assert pipeline.stages == (Stage("solo", duration=10),)


def test_parse_keeps_the_document_name():
    assert parse_pipeline_data(_doc(name="  ci  ")).name == "ci"


def test_parse_rejects_a_non_mapping_document():
    with pytest.raises(PipelineError, match="pipeline must be a mapping"):
        parse_pipeline_data(["stages"])


def test_parse_rejects_a_bad_name():
    with pytest.raises(PipelineError, match="'name' must be a non-empty"):
        parse_pipeline_data(_doc(name=""))


def test_parse_rejects_missing_stages():
    with pytest.raises(PipelineError, match="'stages' must be a non-empty"):
        parse_pipeline_data({"name": "x"})


def test_parse_rejects_an_empty_stage_list():
    with pytest.raises(PipelineError, match="'stages' must be a non-empty"):
        parse_pipeline_data({"stages": []})


def test_parse_rejects_too_many_stages():
    stages = [{"name": f"s{index}"} for index in range(MAX_STAGES + 1)]
    with pytest.raises(PipelineError, match="too many stages"):
        parse_pipeline_data({"stages": stages})


def test_parse_rejects_a_non_mapping_stage():
    with pytest.raises(PipelineError, match="stage #1 must be a mapping"):
        parse_pipeline_data({"stages": ["checkout"]})


@pytest.mark.parametrize("raw", [{}, {"name": ""}, {"name": 7}])
def test_parse_rejects_a_stage_without_a_name(raw):
    with pytest.raises(PipelineError, match="'name' must be a non-empty"):
        parse_pipeline_data({"stages": [raw]})


def test_parse_rejects_an_invalid_stage_name():
    with pytest.raises(PipelineError, match="invalid stage name"):
        parse_pipeline_data({"stages": [{"name": "build all"}]})


def test_parse_rejects_needs_that_are_not_a_list():
    with pytest.raises(PipelineError, match="'needs' must be a list"):
        parse_pipeline_data({"stages": [{"name": "a", "needs": "b"}]})


def test_parse_rejects_a_blank_need():
    with pytest.raises(PipelineError, match="every entry in 'needs'"):
        parse_pipeline_data({"stages": [{"name": "a", "needs": ["  "]}]})


def test_parse_rejects_duplicate_needs():
    with pytest.raises(PipelineError, match="duplicate entry in 'needs'"):
        parse_pipeline_data({"stages": [
            {"name": "a"}, {"name": "b", "needs": ["a", "a"]}]})


def test_parse_rejects_a_self_dependency():
    with pytest.raises(PipelineError, match="cannot need itself"):
        parse_pipeline_data({"stages": [{"name": "a", "needs": ["a"]}]})


@pytest.mark.parametrize("duration", ["30", 1.5, True, -1, 3601])
def test_parse_rejects_bad_durations(duration):
    with pytest.raises(PipelineError, match="'duration' must be"):
        parse_pipeline_data({"stages": [{"name": "a",
                                         "duration": duration}]})


@pytest.mark.parametrize("retries", ["1", 1.5, True, -1,
                                     MAX_RETRIES + 1])
def test_parse_rejects_bad_retry_counts(retries):
    with pytest.raises(PipelineError, match="'retries' must be"):
        parse_pipeline_data({"stages": [{"name": "a",
                                         "retries": retries}]})


def test_parse_rejects_a_non_mapping_matrix():
    with pytest.raises(PipelineError, match="'matrix' must be a mapping"):
        parse_pipeline_data({"stages": [{"name": "a", "matrix": ["py"]}]})


def test_parse_rejects_an_empty_matrix_axis():
    with pytest.raises(PipelineError, match="must be a non-empty list"):
        parse_pipeline_data({"stages": [
            {"name": "a", "matrix": {"python": []}}]})


def test_parse_rejects_bad_matrix_values():
    with pytest.raises(PipelineError, match="strings or numbers"):
        parse_pipeline_data({"stages": [
            {"name": "a", "matrix": {"python": [None]}}]})


def test_parse_rejects_duplicate_matrix_values():
    with pytest.raises(PipelineError, match="duplicate value in matrix"):
        parse_pipeline_data({"stages": [
            {"name": "a", "matrix": {"os": ["linux", "linux"]}}]})


def test_parse_rejects_an_oversized_matrix():
    values = [str(index) for index in range(65)]
    with pytest.raises(PipelineError, match="expands to 65 jobs"):
        parse_pipeline_data({"stages": [
            {"name": "a", "matrix": {"x": values}}]})


def test_parse_rejects_duplicate_stage_names():
    with pytest.raises(PipelineError, match="duplicate stage name"):
        parse_pipeline_data({"stages": [{"name": "a"}, {"name": "a"}]})


def test_parse_rejects_an_unknown_dependency():
    with pytest.raises(PipelineError, match="unknown dependency 'ghost'"):
        parse_pipeline_data({"stages": [
            {"name": "a", "needs": ["ghost"]}]})


def test_parse_rejects_a_cycle():
    with pytest.raises(PipelineError, match="dependency cycle"):
        parse_pipeline_data({"stages": [
            {"name": "a", "needs": ["b"]},
            {"name": "b", "needs": ["a"]},
        ]})


def test_parse_coerces_numeric_matrix_values_to_strings():
    pipeline = parse_pipeline_data({"stages": [
        {"name": "shard", "matrix": {"shard": [1, 2]}}]})
    assert pipeline.stage("shard").job_names() == (
        "shard[shard=1]", "shard[shard=2]")


def test_load_bundled_json():
    pipeline = load_pipeline(BUNDLED_JSON)
    assert pipeline.name == "demo"
    assert len(pipeline.stages) == 7


def test_bundled_formats_are_equivalent():
    assert load_pipeline(BUNDLED_JSON) == load_pipeline(BUNDLED_TOML)


def test_bundled_paths_live_in_data():
    assert BUNDLED_JSON.parent == BUNDLED_TOML.parent == DATA_DIR \
        == PROJECT_ROOT / "data"


def test_load_missing_file(tmp_path):
    with pytest.raises(PipelineError, match="file not found"):
        load_pipeline(tmp_path / "nope.json")


def test_load_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(PipelineError, match="invalid JSON"):
        load_pipeline(path)


def test_load_invalid_toml(tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text("[stages\nbroken", encoding="utf-8")
    with pytest.raises(PipelineError, match="invalid TOML"):
        load_pipeline(path)


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def test_plain_stage_has_one_job_named_after_it():
    assert Stage("build").job_names() == ("build",)


def test_matrix_size_is_the_product():
    assert _matrix().stage("unit").matrix_size == 4


def test_matrix_job_labels_are_cartesian_in_order():
    assert _matrix().stage("unit").job_names() == (
        "unit[python=3.11,os=a]",
        "unit[python=3.11,os=b]",
        "unit[python=3.12,os=a]",
        "unit[python=3.12,os=b]",
    )


def test_is_matrix_flag():
    assert _matrix().stage("unit").is_matrix
    assert not _matrix().stage("checkout").is_matrix


def test_job_count_sums_every_stage():
    assert _linear().job_count == 4
    assert _matrix().job_count == 5


def test_job_names_are_unique_across_the_pipeline():
    jobs = load_pipeline(BUNDLED_JSON).job_names()
    assert len(jobs) == len(set(jobs))


def test_by_name_and_stage_lookup():
    pipeline = _linear()
    assert pipeline.by_name()["docs"].duration == 5
    assert pipeline.stage("build").duration == 20


def test_unknown_stage_lookup():
    with pytest.raises(PipelineError, match="unknown stage 'ghost'"):
        _linear().stage("ghost")


def test_stage_is_frozen():
    with pytest.raises(Exception):
        _linear().stages[0].duration = 99


# --------------------------------------------------------------------------- #
# Order and depth
# --------------------------------------------------------------------------- #
def test_order_respects_every_edge():
    pipeline = load_pipeline(BUNDLED_JSON)
    order = topological_order(pipeline)
    position = {name: index for index, name in enumerate(order)}
    for stage in pipeline.stages:
        for need in stage.needs:
            assert position[need] < position[stage.name]


def test_order_contains_every_stage_once():
    pipeline = load_pipeline(BUNDLED_JSON)
    order = topological_order(pipeline)
    assert len(order) == len(pipeline.stages)
    assert set(order) == set(pipeline.by_name())


def test_order_is_stable():
    pipeline = load_pipeline(BUNDLED_JSON)
    assert topological_order(pipeline) == topological_order(pipeline)


def test_order_breaks_ties_in_declaration_order():
    pipeline = Pipeline("ties", (_stage("z"), _stage("a"), _stage("m")))
    assert topological_order(pipeline) == ("z", "a", "m")


def test_order_of_a_two_node_chain():
    pipeline = Pipeline("chain", (_stage("second", needs=("first",)),
                                  _stage("first")))
    assert topological_order(pipeline) == ("first", "second")


def test_order_rejects_a_cycle():
    cycle = Pipeline("cycle", (_stage("a", needs=("b",)),
                               _stage("b", needs=("a",))))
    with pytest.raises(PipelineError, match="dependency cycle among: a, b"):
        topological_order(cycle)


def test_order_rejects_a_self_loop():
    with pytest.raises(PipelineError, match="dependency cycle"):
        topological_order(Pipeline("loop", (_stage("a", needs=("a",)),)))


def test_dependency_depth_of_the_bundled_graph():
    assert dependency_depth(load_pipeline(BUNDLED_JSON)) == {
        "checkout": 0, "lint": 1, "unit": 1, "integration": 2,
        "docs": 1, "package": 3, "deploy": 4}


def test_dependency_depth_of_a_linear_chain():
    assert dependency_depth(_linear()) == {
        "checkout": 0, "build": 1, "test": 2, "docs": 1}


# --------------------------------------------------------------------------- #
# Retry policy
# --------------------------------------------------------------------------- #
def test_no_failure_runs_one_attempt():
    assert job_attempts(Stage("a", duration=10), None) == (1, True)


def test_hard_failure_uses_every_attempt():
    stage = Stage("a", duration=10, retries=2)
    assert job_attempts(stage, "hard") == (3, False)


def test_flaky_failure_passes_on_the_retry():
    stage = Stage("a", duration=10, retries=1)
    assert job_attempts(stage, "flaky") == (2, True)


def test_flaky_without_retries_fails_outright():
    stage = Stage("a", duration=10, retries=0)
    assert job_attempts(stage, "flaky") == (1, False)


def test_unknown_failure_mode_is_rejected():
    with pytest.raises(PipelineError, match="unknown failure mode"):
        job_attempts(Stage("a"), "sometimes")


def test_fail_modes_constant():
    assert set(FAIL_MODES) == {"hard", "flaky"}


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
def test_clean_run_succeeds():
    run = simulate(load_pipeline(BUNDLED_JSON))
    assert run.success
    assert run.status_counts() == {STATUS_SUCCESS: 12, STATUS_FAILED: 0,
                                   STATUS_SKIPPED: 0, STATUS_CANCELLED: 0}


def test_clean_run_timings():
    run = simulate(load_pipeline(BUNDLED_JSON))
    assert run.wall_time == EXPECTED_CLEAN_WALL
    assert run.serial_time == 360
    assert run.speedup == pytest.approx(360 / 130, abs=0.01)


def test_wall_time_is_the_latest_finish():
    run = simulate(load_pipeline(BUNDLED_JSON))
    assert run.wall_time == max(finish for _, _, finish in run.spans)


def test_critical_path_of_the_clean_run():
    run = simulate(load_pipeline(BUNDLED_JSON))
    assert run.critical_path == ("checkout", "unit", "integration",
                                 "package", "deploy")


def test_critical_path_of_a_linear_chain():
    run = simulate(_linear())
    assert run.critical_path == ("checkout", "build", "test")


def test_critical_path_is_empty_when_nothing_ran():
    pipeline = Pipeline("never", (_stage("a", duration=10),))
    spans: dict[str, tuple[int, int]] = {}
    assert critical_path(spans, pipeline) == ()


def test_matrix_jobs_start_together_and_cost_one_span():
    run = simulate(_matrix())
    unit = run.results_for("unit")
    assert len(unit) == 4
    assert {job.start for job in unit} == {5}
    assert {job.finish for job in unit} == {45}
    assert run.span("unit") == (5, 45)
    assert sum(job.duration for job in unit) == 160


def test_independent_stages_overlap():
    run = simulate(_linear())
    # docs starts with build, not after test
    assert run.span("docs") == (10, 15)
    assert run.span("build") == (10, 30)
    assert run.wall_time == 60


def test_no_retries_in_a_clean_run():
    assert simulate(load_pipeline(BUNDLED_JSON)).retries_used == 0


def test_flaky_stage_retries_and_adds_time():
    run = simulate(load_pipeline(BUNDLED_JSON), {"unit": "flaky"})
    assert run.success
    assert run.retries_used == 4
    assert run.span("unit") == (12, 102)
    assert all(job.attempts == 2 for job in run.results_for("unit"))


def test_hard_failure_reports_every_attempt():
    pipeline = Pipeline("p", (_stage("only", duration=10, retries=2),))
    run = simulate(pipeline, {"only": "hard"})
    job = run.jobs[0]
    assert job.status == STATUS_FAILED
    assert job.attempts == 3
    assert job.duration == 30
    assert not run.success


def test_fail_fast_cancels_undispatched_stages():
    run = simulate(load_pipeline(BUNDLED_JSON),
                   {"integration": "hard"}, fail_fast=True)
    counts = run.status_counts()
    assert counts[STATUS_FAILED] == 1
    assert counts[STATUS_CANCELLED] == 4
    assert counts[STATUS_SKIPPED] == 0
    assert run.results_for("integration")[1].status == STATUS_CANCELLED
    assert run.results_for("package")[0].status == STATUS_CANCELLED


def test_continue_mode_skips_instead_of_cancelling():
    run = simulate(load_pipeline(BUNDLED_JSON),
                   {"integration": "hard"}, fail_fast=False)
    counts = run.status_counts()
    assert counts[STATUS_FAILED] == 3
    assert counts[STATUS_SKIPPED] == 2
    assert counts[STATUS_CANCELLED] == 0
    assert run.results_for("deploy")[0].status == STATUS_SKIPPED


def test_cancelled_stages_have_no_span():
    run = simulate(load_pipeline(BUNDLED_JSON),
                   {"integration": "hard"}, fail_fast=True)
    assert run.span("package") is None
    assert run.span("integration") == (57, 87)


def test_cancelled_jobs_do_not_subtract_from_retries_used():
    run = simulate(load_pipeline(BUNDLED_JSON),
                   {"unit": "flaky", "integration": "hard"}, fail_fast=True)
    assert run.retries_used == 4


def test_status_counts_always_add_up():
    pipeline = load_pipeline(BUNDLED_JSON)
    for failures, fail_fast in ((None, True), ({"unit": "hard"}, True),
                                ({"unit": "hard"}, False),
                                ({"deploy": "hard"}, False)):
        run = simulate(pipeline, failures, fail_fast=fail_fast)
        assert sum(run.status_counts().values()) == pipeline.job_count
        assert len(run.jobs) == pipeline.job_count


def test_results_for_filters_by_stage():
    run = simulate(load_pipeline(BUNDLED_JSON))
    assert len(run.results_for("unit")) == 4
    assert run.results_for("ghost") == ()


def test_simulation_is_deterministic():
    pipeline = load_pipeline(BUNDLED_JSON)
    assert simulate(pipeline) == simulate(pipeline)
    assert simulate(pipeline, {"unit": "flaky"}, fail_fast=False) == \
        simulate(pipeline, {"unit": "flaky"}, fail_fast=False)


def test_simulate_requires_a_pipeline():
    with pytest.raises(PipelineError, match="needs a Pipeline"):
        simulate({"stages": []})


def test_simulate_requires_a_bool_policy():
    with pytest.raises(PipelineError, match="fail_fast must be a bool"):
        simulate(_linear(), fail_fast="yes")


def test_failure_keys_may_name_a_single_job():
    pipeline = load_pipeline(BUNDLED_JSON)
    run = simulate(pipeline, {"integration[shard=2]": "hard"},
                   fail_fast=False)
    statuses = [job.status for job in run.results_for("integration")]
    assert statuses == [STATUS_SUCCESS, STATUS_FAILED, STATUS_SUCCESS]


def test_unknown_failure_target_is_rejected():
    with pytest.raises(PipelineError, match="unknown stage or job"):
        simulate(_linear(), {"ghost": "hard"})


def test_unknown_failure_mode_is_rejected_by_simulate():
    with pytest.raises(PipelineError, match="unknown failure mode"):
        simulate(_linear(), {"build": "sometimes"})


def test_failures_must_be_a_mapping():
    with pytest.raises(PipelineError, match="failures must be a mapping"):
        simulate(_linear(), [("build", "hard")])


def test_job_result_ran_flag():
    ran = JobResult("build", "build", STATUS_SUCCESS, 1, 0, 10, 10, "ok")
    skipped = JobResult("test", "test", STATUS_SKIPPED, 0, None, None, 0, "-")
    assert ran.ran and not skipped.ran


def test_run_to_dict_shape():
    payload = simulate(load_pipeline(BUNDLED_JSON)).to_dict()
    assert set(payload) >= {"pipeline", "fail_fast", "order", "jobs",
                            "status_counts", "wall_time", "serial_time",
                            "speedup", "retries_used", "success",
                            "critical_path", "spans"}
    assert payload["status_counts"][STATUS_SUCCESS] == 12
    assert len(payload["jobs"]) == 12
    assert payload["success"] is True


def test_job_result_to_dict_shape():
    payload = simulate(_linear()).jobs[0].to_dict()
    assert set(payload) == {"job", "stage", "status", "attempts", "start",
                            "finish", "duration", "detail"}


def test_statuses_constant_is_complete():
    counts = simulate(_linear()).status_counts()
    assert set(counts) == set(STATUSES)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_report_contains_the_tables_and_summary():
    text = render_report(simulate(load_pipeline(BUNDLED_JSON)))
    assert "CI PIPELINE - demo" in text
    assert "order :" in text
    assert "policy: fail-fast" in text
    assert "Stage timeline" in text
    assert "Summary:" in text
    assert "Critical  :" in text
    assert "Result    : PASS" in text


def test_report_marks_a_failed_run():
    text = render_report(simulate(load_pipeline(BUNDLED_JSON),
                                  {"integration": "hard"}))
    assert "Result    : FAIL" in text
    assert "policy: fail-fast" in text
    assert STATUS_CANCELLED in text


def test_report_shows_the_continue_policy():
    text = render_report(simulate(load_pipeline(BUNDLED_JSON), None,
                                  fail_fast=False))
    assert "policy: continue on failure" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK:" in out
    assert "Demo completed successfully." in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    assert capsys.readouterr().out == first


def test_run_demo_prints_three_runs(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert out.count("CI PIPELINE - demo") == 3


def test_run_demo_missing_bundle(tmp_path):
    with pytest.raises(PipelineError, match="bundled sample not found"):
        run_demo(tmp_path / "nope.json")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_demo_rejects_failures():
    with pytest.raises(SystemExit) as exc:
        main(["--demo", "--fail", "unit=hard"])
    assert exc.value.code == 2


def test_cli_demo_rejects_json():
    with pytest.raises(SystemExit) as exc:
        main(["--demo", "--json", "x.json"])
    assert exc.value.code == 2


def test_cli_default_run_passes(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "Result    : PASS" in out
    assert "Order:" in out


def test_cli_toml_file(capsys):
    assert main(["--file", str(BUNDLED_TOML), "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_failure_exits_one(capsys):
    assert main(["--fail", "integration=hard", "--quiet"]) == 1
    assert capsys.readouterr().out == ""


def test_cli_no_fail_fast_flag(capsys):
    assert main(["--fail", "integration=hard", "--no-fail-fast"]) == 1
    out = capsys.readouterr().out
    assert "policy: continue on failure" in out


def test_cli_flaky_failure_still_passes():
    assert main(["--fail", "unit=flaky", "--quiet"]) == 0


def test_cli_json_output(tmp_path):
    out_json = tmp_path / "run.json"
    assert main(["--json", str(out_json), "--quiet"]) == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status_counts"][STATUS_SUCCESS] == 12
    assert payload["source"].endswith("pipeline.json")
    assert payload["stage_count"] == 7
    assert payload["dependency_depth"]["deploy"] == 4
    assert payload["critical_path"][0] == "checkout"


def test_cli_save_writes_the_report(tmp_path):
    target = tmp_path / "out" / "report.txt"
    assert main(["--save", str(target), "--quiet"]) == 0
    text = target.read_text(encoding="utf-8")
    assert "CI PIPELINE - demo" in text
    assert text.endswith("\n")


def test_cli_quiet_suppresses_everything(capsys):
    assert main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.json")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_bad_fail_format():
    with pytest.raises(SystemExit) as exc:
        main(["--fail", "unit"])
    assert exc.value.code == 2


def test_cli_bad_fail_mode():
    with pytest.raises(SystemExit) as exc:
        main(["--fail", "unit=sometimes"])
    assert exc.value.code == 2


def test_cli_duplicate_fail_entry():
    with pytest.raises(SystemExit) as exc:
        main(["--fail", "unit=hard", "--fail", "unit=flaky"])
    assert exc.value.code == 2


def test_build_parser_defaults():
    args = build_parser().parse_args(["--demo"])
    assert args.file is None
    assert args.fail is None
    assert not args.no_fail_fast
    assert not args.quiet
