"""CI pipeline simulator: DAG stages, matrix fan-out and failure propagation.

A pipeline is a set of stages with ``needs`` edges. A stage starts as
soon as every dependency has finished, so independent branches overlap;
the jobs of a matrix stage run in parallel, so a matrix stage costs one
job's runtime, not the sum.

Two failure policies are simulated:

* ``fail_fast=True``  - the first failed job aborts the run: stages that
  have not been dispatched yet are ``cancelled``;
* ``fail_fast=False`` - every job that is not blocked by a failed
  dependency still runs; unreachable stages are ``skipped``.

Timings are simulated but deterministic: a job costs ``stage.duration``
per attempt, and a retry re-runs the whole job. A failure can be ``hard``
(fails every attempt, up to ``retries + 1``) or ``flaky`` (fails the
first attempt and passes on the retry, degrading to a hard failure when
the stage has no retries).

Fully offline: local JSON/TOML in, a deterministic run report out.
"""

from __future__ import annotations

import json
import logging
import tomllib
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Mapping

LOG = logging.getLogger("pipeline")

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_CANCELLED = "cancelled"
STATUSES = (STATUS_SUCCESS, STATUS_FAILED, STATUS_SKIPPED, STATUS_CANCELLED)

FAIL_MODES = ("hard", "flaky")

MAX_STAGES = 64
MAX_MATRIX_JOBS = 64
MAX_DURATION = 3600
MAX_RETRIES = 5


class PipelineError(RuntimeError):
    """Raised for malformed pipelines, cycles and bad option values."""


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Stage:
    """One pipeline stage, optionally expanded into a matrix of jobs."""

    name: str
    needs: tuple[str, ...] = ()
    duration: int = 30
    retries: int = 0
    matrix: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @property
    def matrix_size(self) -> int:
        size = 1
        for _, values in self.matrix:
            size *= len(values)
        return size

    @property
    def is_matrix(self) -> bool:
        return bool(self.matrix)

    def job_names(self) -> tuple[str, ...]:
        """Concrete job labels: the stage name, or name[k=v,...]."""
        if not self.matrix:
            return (self.name,)
        keys = [key for key, _ in self.matrix]
        labels = []
        for combo in product(*(values for _, values in self.matrix)):
            suffix = ",".join(f"{key}={value}"
                              for key, value in zip(keys, combo))
            labels.append(f"{self.name}[{suffix}]")
        return tuple(labels)


@dataclass(frozen=True)
class Pipeline:
    """A named stage graph."""

    name: str
    stages: tuple[Stage, ...]

    def by_name(self) -> dict[str, Stage]:
        return {stage.name: stage for stage in self.stages}

    def stage(self, name: str) -> Stage:
        try:
            return self.by_name()[name]
        except KeyError:
            raise PipelineError(f"unknown stage {name!r}") from None

    def job_names(self) -> tuple[str, ...]:
        jobs: list[str] = []
        for stage in self.stages:
            jobs.extend(stage.job_names())
        return tuple(jobs)

    @property
    def job_count(self) -> int:
        return sum(stage.matrix_size for stage in self.stages)


# --------------------------------------------------------------------------- #
# Parsing and validation
# --------------------------------------------------------------------------- #
def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PipelineError(f"{label} must be a mapping, "
                            f"got {type(value).__name__}")
    return value


def _parse_stage(raw: Any, index: int) -> Stage:
    label = f"stage #{index + 1}"
    data = _require_mapping(raw, label)

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise PipelineError(f"{label}: 'name' must be a non-empty string")
    name = name.strip()
    if not all(ch.isalnum() or ch in "._-" for ch in name):
        raise PipelineError(f"{label}: invalid stage name {name!r} "
                            f"(letters, digits, '.', '_' and '-' only)")

    needs_raw = data.get("needs", [])
    if not isinstance(needs_raw, (list, tuple)):
        raise PipelineError(f"{name}: 'needs' must be a list of stage names")
    needs: list[str] = []
    for item in needs_raw:
        if not isinstance(item, str) or not item.strip():
            raise PipelineError(f"{name}: every entry in 'needs' must be a "
                                f"non-empty string")
        needs.append(item.strip())
    if len(set(needs)) != len(needs):
        raise PipelineError(f"{name}: duplicate entry in 'needs'")
    if name in needs:
        raise PipelineError(f"{name}: a stage cannot need itself")

    duration = data.get("duration", 30)
    if isinstance(duration, bool) or not isinstance(duration, int):
        raise PipelineError(f"{name}: 'duration' must be an integer number "
                            f"of seconds, got {duration!r}")
    if not 0 <= duration <= MAX_DURATION:
        raise PipelineError(f"{name}: 'duration' must be in "
                            f"[0, {MAX_DURATION}], got {duration}")

    retries = data.get("retries", 0)
    if isinstance(retries, bool) or not isinstance(retries, int):
        raise PipelineError(f"{name}: 'retries' must be an integer, "
                            f"got {retries!r}")
    if not 0 <= retries <= MAX_RETRIES:
        raise PipelineError(f"{name}: 'retries' must be in "
                            f"[0, {MAX_RETRIES}], got {retries}")

    matrix_raw = data.get("matrix", {})
    matrix_data = _require_mapping(matrix_raw, f"{name}: 'matrix'")
    matrix: list[tuple[str, tuple[str, ...]]] = []
    seen_keys: set[str] = set()
    for key, values in matrix_data.items():
        if not isinstance(key, str) or not key.strip():
            raise PipelineError(f"{name}: matrix keys must be non-empty "
                                f"strings")
        key = key.strip()
        if key in seen_keys:
            raise PipelineError(f"{name}: duplicate matrix key {key!r}")
        seen_keys.add(key)
        if not isinstance(values, (list, tuple)) or not values:
            raise PipelineError(f"{name}: matrix '{key}' must be a non-empty "
                                f"list of values")
        labels = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value,
                                                         (str, int, float)):
                raise PipelineError(
                    f"{name}: matrix '{key}' values must be strings or "
                    f"numbers, got {value!r}")
            labels.append(str(value))
        if len(set(labels)) != len(labels):
            raise PipelineError(f"{name}: duplicate value in matrix "
                                f"'{key}'")
        matrix.append((key, tuple(labels)))

    total = 1
    for _, values in matrix:
        total *= len(values)
    if total > MAX_MATRIX_JOBS:
        raise PipelineError(f"{name}: matrix expands to {total} jobs "
                            f"(max {MAX_MATRIX_JOBS})")

    return Stage(name=name, needs=tuple(needs), duration=duration,
                 retries=retries, matrix=tuple(matrix))


def parse_pipeline_data(data: Mapping[str, Any]) -> Pipeline:
    """Validate a decoded pipeline document and build a Pipeline."""
    document = _require_mapping(data, "pipeline")
    name = document.get("name", "pipeline")
    if not isinstance(name, str) or not name.strip():
        raise PipelineError("'name' must be a non-empty string")

    raw_stages = document.get("stages")
    if not isinstance(raw_stages, (list, tuple)) or not raw_stages:
        raise PipelineError("'stages' must be a non-empty list")
    if len(raw_stages) > MAX_STAGES:
        raise PipelineError(f"too many stages: {len(raw_stages)} "
                            f"(max {MAX_STAGES})")

    stages = tuple(_parse_stage(raw, index)
                   for index, raw in enumerate(raw_stages))

    names = [stage.name for stage in stages]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise PipelineError(f"duplicate stage name(s): "
                            f"{', '.join(duplicates)}")

    known = set(names)
    for stage in stages:
        unknown = [need for need in stage.needs if need not in known]
        if unknown:
            raise PipelineError(f"{stage.name}: unknown dependency "
                                f"{unknown[0]!r}")

    pipeline = Pipeline(name=name.strip(), stages=stages)
    topological_order(pipeline)      # raises on a cycle
    return pipeline


def load_pipeline(path: str | Path) -> Pipeline:
    """Load a pipeline document: .toml via tomllib, otherwise JSON."""
    source = Path(path)
    if not source.is_file():
        raise PipelineError(f"file not found: {source}")
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise PipelineError(f"could not read {source.name}: {exc}") from exc

    if source.suffix.lower() == ".toml":
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise PipelineError(f"invalid TOML in {source.name}: {exc}") from exc
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PipelineError(f"invalid JSON in {source.name}: {exc}") from exc
    return parse_pipeline_data(data)


# --------------------------------------------------------------------------- #
# Graph order and depth
# --------------------------------------------------------------------------- #
def topological_order(pipeline: Pipeline) -> tuple[str, ...]:
    """Kahn's algorithm, resolving ties in declaration order (stable)."""
    position = {stage.name: index
                for index, stage in enumerate(pipeline.stages)}
    remaining = {stage.name: set(stage.needs) for stage in pipeline.stages}
    order: list[str] = []

    while remaining:
        ready = sorted((name for name, needs in remaining.items() if not needs),
                       key=lambda name: position[name])
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise PipelineError(f"dependency cycle among: {cycle}")
        for name in ready:
            order.append(name)
            del remaining[name]
        done = set(ready)
        for needs in remaining.values():
            needs -= done
    return tuple(order)


def dependency_depth(pipeline: Pipeline) -> dict[str, int]:
    """Longest chain of ``needs`` ending at each stage (0 = no needs)."""
    depth: dict[str, int] = {}
    for name in topological_order(pipeline):
        stage = pipeline.stage(name)
        depth[name] = 1 + max((depth[need] for need in stage.needs),
                             default=-1) if stage.needs else 0
    return depth


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class JobResult:
    """Outcome of one concrete job (one matrix cell, or a plain stage)."""

    job: str
    stage: str
    status: str
    attempts: int
    start: int | None
    finish: int | None
    duration: int
    detail: str

    @property
    def ran(self) -> bool:
        return self.start is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job": self.job,
            "stage": self.stage,
            "status": self.status,
            "attempts": self.attempts,
            "start": self.start,
            "finish": self.finish,
            "duration": self.duration,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Run:
    """The full simulated result of one pipeline execution."""

    pipeline: str
    fail_fast: bool
    order: tuple[str, ...]
    jobs: tuple[JobResult, ...]
    spans: tuple[tuple[str, int, int], ...]
    wall_time: int
    serial_time: int
    critical_path: tuple[str, ...] = ()

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in STATUSES}
        for job in self.jobs:
            counts[job.status] += 1
        return counts

    @property
    def success(self) -> bool:
        return all(job.status == STATUS_SUCCESS for job in self.jobs)

    def results_for(self, stage: str) -> tuple[JobResult, ...]:
        return tuple(job for job in self.jobs if job.stage == stage)

    def span(self, stage: str) -> tuple[int, int] | None:
        for name, start, finish in self.spans:
            if name == stage:
                return start, finish
        return None

    @property
    def speedup(self) -> float:
        if self.wall_time == 0:
            return 0.0
        return round(self.serial_time / self.wall_time, 2)

    @property
    def retries_used(self) -> int:
        # cancelled/skipped jobs have 0 attempts; they must not subtract
        return sum(max(0, job.attempts - 1) for job in self.jobs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline": self.pipeline,
            "fail_fast": self.fail_fast,
            "order": list(self.order),
            "jobs": [job.to_dict() for job in self.jobs],
            "status_counts": self.status_counts(),
            "wall_time": self.wall_time,
            "serial_time": self.serial_time,
            "speedup": self.speedup,
            "retries_used": self.retries_used,
            "success": self.success,
            "critical_path": list(self.critical_path),
            "spans": [{"stage": name, "start": start, "finish": finish}
                      for name, start, finish in self.spans],
        }


def job_attempts(stage: Stage, mode: str | None) -> tuple[int, bool]:
    """How many attempts run, and whether the job ends up passing."""
    limit = stage.retries + 1
    if mode is None:
        return 1, True
    if mode == "hard":
        return limit, False
    if mode == "flaky":
        # a flaky job needs a retry to pass; with retries=0 it is a failure
        return (2, True) if stage.retries >= 1 else (1, False)
    raise PipelineError(f"unknown failure mode {mode!r} "
                        f"(choose from {', '.join(FAIL_MODES)})")


def _validate_failures(pipeline: Pipeline,
                       failures: Mapping[str, str] | None) -> dict[str, str]:
    if failures is None:
        return {}
    if not isinstance(failures, Mapping):
        raise PipelineError("failures must be a mapping of stage/job -> mode")
    stages = {stage.name for stage in pipeline.stages}
    jobs = set(pipeline.job_names())
    resolved: dict[str, str] = {}
    for key, mode in failures.items():
        if key not in stages and key not in jobs:
            raise PipelineError(f"unknown stage or job in failures: {key!r}")
        if mode not in FAIL_MODES:
            raise PipelineError(f"unknown failure mode {mode!r} for {key!r} "
                                f"(choose from {', '.join(FAIL_MODES)})")
        resolved[key] = mode
    return resolved


def _detail(attempts: int, ok: bool, stage: Stage) -> str:
    if ok and attempts == 1:
        return "passed on the first attempt"
    if ok:
        return f"passed on attempt {attempts} of {stage.retries + 1}"
    return f"failed after {attempts} attempt(s)"


def critical_path(spans: Mapping[str, tuple[int, int]],
                  pipeline: Pipeline) -> tuple[str, ...]:
    """Longest dependency chain by actual span, walking back from the end."""
    best: dict[str, tuple[int, str | None]] = {}
    for name in topological_order(pipeline):
        if name not in spans:
            continue
        start, finish = spans[name]
        length = finish - start
        deps = [need for need in pipeline.stage(name).needs if need in best]
        if deps:
            previous = max(deps, key=lambda need: best[need][0])
            best[name] = (length + best[previous][0], previous)
        else:
            best[name] = (length, None)
    if not best:
        return ()
    node: str | None = max(best, key=lambda name: best[name][0])
    chain: list[str] = []
    while node is not None:
        chain.append(node)
        node = best[node][1]
    return tuple(reversed(chain))


def simulate(pipeline: Pipeline, failures: Mapping[str, str] | None = None,
             fail_fast: bool = True) -> Run:
    """Run the pipeline with deterministic simulated timings."""
    if not isinstance(pipeline, Pipeline):
        raise PipelineError("simulate() needs a Pipeline")
    if not isinstance(fail_fast, bool):
        raise PipelineError(f"fail_fast must be a bool, got {fail_fast!r}")
    order = topological_order(pipeline)
    plan = _validate_failures(pipeline, failures)

    results: list[JobResult] = []
    stage_status: dict[str, str] = {}
    spans: list[tuple[str, int, int]] = []
    finish_of: dict[str, int] = {}
    aborted = False

    for name in order:
        stage = pipeline.stage(name)
        blocked = [need for need in stage.needs
                   if stage_status.get(need) != STATUS_SUCCESS]

        if aborted or blocked:
            status = STATUS_CANCELLED if aborted else STATUS_SKIPPED
            detail = ("cancelled by fail-fast" if aborted
                      else f"skipped: dependency {blocked[0]!r} did not "
                           f"succeed")
            for job in stage.job_names():
                results.append(JobResult(job, name, status, 0, None, None,
                                         0, detail))
            stage_status[name] = status
            continue

        # a stage starts as soon as its dependencies have all finished
        start = max((finish_of[need] for need in stage.needs), default=0)
        finish = start
        stage_failed = False
        for job in stage.job_names():
            if aborted:
                results.append(JobResult(job, name, STATUS_CANCELLED, 0,
                                         None, None, 0,
                                         "cancelled by fail-fast"))
                continue
            mode = plan.get(job) or plan.get(name)
            attempts, ok = job_attempts(stage, mode)
            spent = attempts * stage.duration
            finish = max(finish, start + spent)
            status = STATUS_SUCCESS if ok else STATUS_FAILED
            results.append(JobResult(job, name, status, attempts, start,
                                     start + spent, spent,
                                     _detail(attempts, ok, stage)))
            if not ok:
                stage_failed = True
                if fail_fast:
                    aborted = True

        finish_of[name] = finish
        spans.append((name, start, finish))
        stage_status[name] = STATUS_FAILED if stage_failed else STATUS_SUCCESS

    span_map = {name: (start, finish) for name, start, finish in spans}
    return Run(
        pipeline=pipeline.name,
        fail_fast=fail_fast,
        order=order,
        jobs=tuple(results),
        spans=tuple(spans),
        wall_time=max((finish for _, _, finish in spans), default=0),
        serial_time=sum(job.duration for job in results),
        critical_path=critical_path(span_map, pipeline),
    )


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def render_report(run: Run) -> str:
    """Align a run into a job table, a stage timeline and a summary."""
    counts = run.status_counts()
    mode = "fail-fast" if run.fail_fast else "continue on failure"
    lines = [
        f"CI PIPELINE - {run.pipeline}",
        "=" * 78,
        "order : " + " -> ".join(run.order),
        f"policy: {mode}",
        "",
        f"  {'job':<38}{'status':<11}{'tries':>6}{'start':>7}{'finish':>8}",
        "  " + "-" * 68,
    ]
    for job in run.jobs:
        start = "-" if job.start is None else str(job.start)
        finish = "-" if job.finish is None else str(job.finish)
        lines.append(f"  {job.job:<38}{job.status:<11}{job.attempts:>6}"
                     f"{start:>7}{finish:>8}")

    lines += ["", "Stage timeline",
              f"  {'stage':<18}{'start':>7}{'finish':>8}{'span':>7}"
              f"{'jobs':>6}  status",
              "  " + "-" * 60]
    for name, start, finish in run.spans:
        jobs = run.results_for(name)
        lines.append(f"  {name:<18}{start:>7}{finish:>8}{finish - start:>7}"
                     f"{len(jobs):>6}  {jobs[0].status}")
    for name in run.order:
        if run.span(name) is None:
            jobs = run.results_for(name)
            lines.append(f"  {name:<18}{'-':>7}{'-':>8}{'-':>7}"
                         f"{len(jobs):>6}  {jobs[0].status}")

    lines += [
        "",
        "Summary: " + " | ".join(f"{status} {counts[status]}"
                                 for status in STATUSES),
        f"Wall time : {run.wall_time} s "
        f"(serial {run.serial_time} s, speed-up {run.speedup}x)",
        "Critical  : " + (" -> ".join(run.critical_path) or "(none)"),
        f"Retries   : {run.retries_used}",
        f"Result    : {'PASS' if run.success else 'FAIL'}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Bundled data and the offline demo
# --------------------------------------------------------------------------- #
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUNDLED_JSON = DATA_DIR / "pipeline.json"
BUNDLED_TOML = DATA_DIR / "pipeline.toml"

# Values asserted by the demo; both formats must reproduce them exactly.
EXPECTED_JOBS = 12
EXPECTED_DEPTH = {"checkout": 0, "lint": 1, "unit": 1, "integration": 2,
                  "docs": 1, "package": 3, "deploy": 4}
EXPECTED_MATRIX = {"unit": 4, "integration": 3}
# checkout 12 + unit 45 + integration 30 + package 25 + deploy 18
EXPECTED_CLEAN_WALL = 130
EXPECTED_CLEAN_SERIAL = 360      # sum of every job duration, no parallelism
EXPECTED_FAILFAST_WALL = 132     # checkout 12 + unit 90 (retry) + integration 30
EXPECTED_CONTINUE_WALL = 132     # the same three stages dominate
EXPECTED_FAILFAST_COUNTS = {STATUS_SUCCESS: 7, STATUS_FAILED: 1,
                            STATUS_SKIPPED: 0, STATUS_CANCELLED: 4}
EXPECTED_CONTINUE_COUNTS = {STATUS_SUCCESS: 7, STATUS_FAILED: 3,
                            STATUS_SKIPPED: 2, STATUS_CANCELLED: 0}


def _check_order(pipeline: Pipeline, order: tuple[str, ...]) -> None:
    position = {name: index for index, name in enumerate(order)}
    for stage in pipeline.stages:
        for need in stage.needs:
            assert position[need] < position[stage.name], (
                f"{need} must come before {stage.name}")


def run_demo(json_path: Path | None = None,
             toml_path: Path | None = None) -> int:
    """Parse both bundled formats, simulate three runs and assert them."""
    print("=" * 78)
    print(" CI PIPELINE SIMULATOR - offline demo")
    print(" DAG stages, matrix fan-out, fail-fast vs continue, retries.")
    print("=" * 78)

    json_source = json_path or BUNDLED_JSON
    toml_source = toml_path or BUNDLED_TOML
    for path in (json_source, toml_source):
        if not path.is_file():
            raise PipelineError(f"bundled sample not found: {path}")

    pipeline = load_pipeline(json_source)
    twin = load_pipeline(toml_source)

    # 1. the two formats describe the same pipeline
    assert pipeline == twin, "JSON and TOML pipelines differ"
    assert pipeline.job_count == EXPECTED_JOBS, \
        f"expected {EXPECTED_JOBS} jobs, got {pipeline.job_count}"

    order = topological_order(pipeline)
    # 2. every edge points forward in the order
    _check_order(pipeline, order)
    # 3. the order is stable across calls
    assert topological_order(pipeline) == order, "topological order is not stable"
    # 4. dependency depth matches the hand-computed graph
    depth = dependency_depth(pipeline)
    assert depth == EXPECTED_DEPTH, f"depth changed: {depth}"
    # 5. matrix fan-out is the product of its dimensions
    matrix_sizes = {stage.name: stage.matrix_size for stage in pipeline.stages}
    for name, expected in EXPECTED_MATRIX.items():
        assert matrix_sizes[name] == expected, \
            f"{name}: {matrix_sizes[name]} jobs, expected {expected}"
    assert len(set(pipeline.job_names())) == EXPECTED_JOBS, \
        "job labels are not unique"

    # 6. a cycle is rejected (negative control for the order check)
    cycle = Pipeline("cycle", (
        Stage("a", needs=("b",)),
        Stage("b", needs=("a",)),
    ))
    try:
        topological_order(cycle)
    except PipelineError:
        pass
    else:
        raise AssertionError("a two-node cycle was not rejected")

    # --- run 1: everything passes ----------------------------------------- #
    clean = simulate(pipeline)
    clean_counts = clean.status_counts()
    assert clean_counts[STATUS_SUCCESS] == EXPECTED_JOBS, \
        f"clean run has failures: {clean_counts}"
    assert clean.success, "clean run should pass"
    assert clean.wall_time == EXPECTED_CLEAN_WALL, \
        f"clean wall time {clean.wall_time} != {EXPECTED_CLEAN_WALL}"
    assert clean.serial_time == EXPECTED_CLEAN_SERIAL, \
        f"clean serial time {clean.serial_time} != {EXPECTED_CLEAN_SERIAL}"
    # 7. matrix jobs share their start time and cost one span, not N
    unit_span = clean.span("unit")
    assert unit_span == (12, 57), f"unit span changed: {unit_span}"
    unit_jobs = clean.results_for("unit")
    assert len({job.start for job in unit_jobs}) == 1, \
        "matrix jobs did not start together"
    unit_cost = sum(job.duration for job in unit_jobs)
    assert unit_cost == 4 * 45, f"unit job cost changed: {unit_cost}"
    assert (unit_span[1] - unit_span[0]) < unit_cost, \
        "parallel matrix saved no time"
    # 8. the wall clock equals the latest finish, and the critical path is
    #    exactly the chain that dominates: checkout -> unit -> integration
    #    -> package -> deploy
    assert clean.wall_time == max(finish for _, _, finish in clean.spans), \
        "wall time is not the latest stage finish"
    assert clean.critical_path == ("checkout", "unit", "integration",
                                   "package", "deploy"), \
        f"critical path changed: {clean.critical_path}"
    chain = sum(clean.span(name)[1] - clean.span(name)[0]
                for name in clean.critical_path)
    assert chain == clean.wall_time, \
        f"critical path spends {chain} s, wall clock says {clean.wall_time}"

    print()
    print(render_report(clean))

    # --- run 2: a flaky matrix stage and a hard-failing shard ------------- #
    failures = {"unit": "flaky", "integration": "hard"}
    fast = simulate(pipeline, failures, fail_fast=True)
    fast_counts = fast.status_counts()
    # 9. the flaky stage passes on its retry: 4 extra attempts, +45 s each
    assert fast.span("unit") == (12, 102), \
        f"retry timing changed: {fast.span('unit')}"
    assert fast.retries_used == 4, \
        f"expected 4 retries, got {fast.retries_used}"
    assert all(job.attempts == 2 for job in fast.results_for("unit")), \
        "a flaky unit job did not retry exactly once"
    # 10. fail-fast cancels what has not been dispatched: the remaining
    #     shards plus everything downstream. The independent docs branch was
    #     dispatched before the failure, so it still completes.
    assert fast_counts == EXPECTED_FAILFAST_COUNTS, \
        f"fail-fast counts changed: {fast_counts}"
    assert fast.wall_time == EXPECTED_FAILFAST_WALL, \
        f"fail-fast wall time {fast.wall_time}"
    assert not fast.success, "a run with a failed job is not a success"
    assert fast.results_for("docs")[0].status == STATUS_SUCCESS, \
        "docs was dispatched before the failure and should have finished"
    assert fast.span("package") is None, \
        "a cancelled stage must not have a span"
    assert fast.results_for("integration")[0].status == STATUS_FAILED
    assert [job.status for job in fast.results_for("integration")] == \
        [STATUS_FAILED, STATUS_CANCELLED, STATUS_CANCELLED], \
        "only the shards that had not started should be cancelled"

    print()
    print(render_report(fast))

    # --- run 3: the same failures, but continue on failure ---------------- #
    slow = simulate(pipeline, failures, fail_fast=False)
    slow_counts = slow.status_counts()
    # 11. without fail-fast, the independent branch completes and the shards
    #     all run; only the stages blocked by the failure are skipped
    assert slow_counts == EXPECTED_CONTINUE_COUNTS, \
        f"continue counts changed: {slow_counts}"
    assert slow.wall_time == EXPECTED_CONTINUE_WALL, \
        f"continue wall time {slow.wall_time}"
    assert slow.results_for("docs")[0].status == STATUS_SUCCESS, \
        "docs should still run with fail-fast off"
    assert slow_counts[STATUS_CANCELLED] == 0, \
        "continue mode must not cancel anything"
    assert [job.status for job in slow.results_for("package")] == \
        [STATUS_SKIPPED], "package should be skipped, not cancelled"

    print()
    print(render_report(slow))

    # 12. the two policies disagree on exactly the jobs that had not been
    #     dispatched when the failure happened
    fast_map = {job.job: job.status for job in fast.jobs}
    slow_map = {job.job: job.status for job in slow.jobs}
    differing = {name for name in fast_map if fast_map[name] != slow_map[name]}
    assert differing == {"integration[shard=2]", "integration[shard=3]",
                         "package", "deploy"}, \
        f"unexpected policy difference: {sorted(differing)}"
    # 13. counts always add up to the number of jobs
    for run in (clean, fast, slow):
        assert sum(run.status_counts().values()) == EXPECTED_JOBS, \
            "status counts do not add up"
        assert len(run.jobs) == EXPECTED_JOBS, "job list length changed"

    # 14. simulation is deterministic
    assert simulate(pipeline, failures, fail_fast=True) == fast, \
        "fail-fast run is not deterministic"
    assert simulate(pipeline, failures, fail_fast=False) == slow, \
        "continue run is not deterministic"

    # 15. a flaky failure without retries degrades to a hard failure
    brittle = Pipeline("brittle", (Stage("only", duration=10, retries=0),))
    attempts, ok = job_attempts(brittle.stage("only"), "flaky")
    assert attempts == 1 and not ok, \
        "flaky without retries should fail outright"

    print()
    print(f"Cross-checks OK: both formats parse to the same "
          f"{EXPECTED_JOBS}-job pipeline, topological order respects every "
          f"edge and is stable, dependency depth matches "
          f"{max(EXPECTED_DEPTH.values())} levels, matrix fan-out is 4x3, a "
          f"two-node cycle is rejected, the clean run takes "
          f"{clean.wall_time} s against {clean.serial_time} s serial, its "
          f"critical path is "
          f"{' -> '.join(clean.critical_path)} and sums to the wall clock, "
          f"matrix jobs share a start and cost one span, 4 flaky retries add "
          f"45 s each, fail-fast cancels 4 undispatched jobs while continue "
          f"runs and fails them, the independent docs branch completes under "
          f"both policies, the two policies differ on exactly 4 jobs, status "
          f"counts always total {EXPECTED_JOBS}, deterministic "
          f"re-simulation, and flaky without retries fails outright")
    print("\nDemo completed successfully.")
    return 0
