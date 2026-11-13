"""Tests for the Pythonic Toolkit project."""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from toolkit import (  # noqa: E402
    RECIPE_NAMES,
    RECORDS,
    RECORD_SPEC,
    BlockStats,
    CacheInfo,
    Point,
    Reading,
    Tally,
    ToolkitError,
    ValidationError,
    cached,
    check_record,
    check_value,
    chunked,
    flatten,
    load_records,
    record_summary,
    retry,
    run_demo,
    run_recipe,
    sliding_window,
    capture_stdout,
    temp_directory,
    timed,
    timed_block,
    validate,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _records_json(tmp_path: Path, payload, name: str = "records.json") -> Path:
    path = tmp_path / name
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Runtime validation core
# --------------------------------------------------------------------------- #
def test_check_value_plain_type():
    check_value("name", "Ada", str)
    with pytest.raises(ValidationError, match="name must be str"):
        check_value("name", 7, str)


def test_check_value_ranges():
    check_value("age", 36, {"type": int, "min": 0, "max": 150})
    with pytest.raises(ValidationError, match="age must be >= 0"):
        check_value("age", -1, {"type": int, "min": 0, "max": 150})
    with pytest.raises(ValidationError, match="age must be <= 150"):
        check_value("age", 151, {"type": int, "min": 0, "max": 150})


def test_check_value_choices_and_tuple_types():
    check_value("unit", "ms", {"type": str, "choices": ("ms", "s")})
    with pytest.raises(ValidationError, match="unit must be one of"):
        check_value("unit", "hr", {"type": str, "choices": ("ms", "s")})
    check_value("score", 91.5, (int, float))
    with pytest.raises(ValidationError, match="score must be int or float"):
        check_value("score", "A+", (int, float))


def test_check_value_bool_is_not_int():
    with pytest.raises(ValidationError, match="age must be int"):
        check_value("age", True, {"type": int})
    with pytest.raises(ValidationError, match="count must be int"):
        check_value("count", True, int)


def test_check_value_unsupported_spec():
    with pytest.raises(ToolkitError, match="unsupported spec"):
        check_value("x", 1, "not-a-spec")


def test_check_record_structure():
    with pytest.raises(ValidationError, match="record must be a dict"):
        check_record("nope", RECORD_SPEC)
    with pytest.raises(ValidationError, match="missing field"):
        check_record({"name": "Ada"}, RECORD_SPEC)


# --------------------------------------------------------------------------- #
# Decorator: timed
# --------------------------------------------------------------------------- #
def test_timed_records_result_and_elapsed():
    @timed
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5
    assert isinstance(add.last_elapsed, float)
    assert add.last_elapsed >= 0.0


def test_timed_preserves_metadata():
    @timed
    def documented() -> None:
        """docstring here"""

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "docstring here"


def test_timed_records_on_exception():
    @timed
    def boom() -> None:
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        boom()
    assert boom.last_elapsed >= 0.0


# --------------------------------------------------------------------------- #
# Decorator: retry
# --------------------------------------------------------------------------- #
def test_retry_recovers_from_transient_failures():
    calls: list[int] = []

    @retry(times=4, exceptions=RuntimeError)
    def flaky() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("transient")
        return "ok"

    assert flaky() == "ok"
    assert len(calls) == 3
    assert flaky.attempts == 3


def test_retry_exhaustion_raises_last_error():
    @retry(times=2, exceptions=ValueError)
    def always() -> None:
        raise ValueError("always fails")

    with pytest.raises(ValueError, match="always fails"):
        always()
    assert always.attempts == 2


def test_retry_passes_through_unlisted_exceptions():
    calls: list[int] = []

    @retry(times=3, exceptions=RuntimeError)
    def wrong_kind() -> None:
        calls.append(1)
        raise KeyError("not caught")

    with pytest.raises(KeyError):
        wrong_kind()
    assert len(calls) == 1
    assert wrong_kind.attempts == 1


def test_retry_rejects_bad_times_and_delay():
    with pytest.raises(ToolkitError, match="times must be an int >= 1"):
        retry(times=0)
    with pytest.raises(ToolkitError, match="delay must be >= 0"):
        retry(times=1, delay=-0.5)


def test_retry_rejects_bad_exceptions():
    with pytest.raises(ToolkitError, match="exception class or tuple"):
        retry(exceptions="not-a-class")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Decorator: cached
# --------------------------------------------------------------------------- #
def test_cached_counts_hits_and_misses():
    calls: list[int] = []

    @cached()
    def double(n: int) -> int:
        calls.append(n)
        return n * 2

    assert [double(n) for n in (1, 2, 1, 2, 1)] == [2, 4, 2, 4, 2]
    assert len(calls) == 2          # only two real computations
    info = double.cache_info()
    assert isinstance(info, CacheInfo)
    assert info.hits == 3 and info.misses == 2 and info.maxsize == 128


def test_cached_cache_clear_resets():
    @cached()
    def triple(n: int) -> int:
        return n * 3

    triple(4)
    triple(4)
    triple.cache_clear()
    info = triple.cache_info()
    assert info.hits == 0 and info.misses == 0
    triple(4)
    assert triple.cache_info().misses == 1


def test_cached_evicts_oldest_beyond_maxsize():
    @cached(maxsize=2)
    def square(n: int) -> int:
        return n * n

    square(1), square(2), square(3)
    assert square.cache_info().misses == 3
    square(1)                      # 1 was evicted, so it recomputes
    assert square.cache_info().misses == 4
    square(3)
    assert square.cache_info().hits >= 1


def test_cached_rejects_bad_maxsize():
    with pytest.raises(ToolkitError, match="maxsize must be an int >= 1"):
        cached(maxsize=0)


def test_cached_bypasses_unhashable_arguments():
    @cached()
    def total(values: list[int]) -> int:
        return sum(values)

    assert total([1, 2, 3]) == 6
    assert total([1, 2, 3]) == 6
    assert total.cache_info().misses == 0   # never entered the store


# --------------------------------------------------------------------------- #
# Decorator: validate
# --------------------------------------------------------------------------- #
def test_validate_passes_valid_calls_through():
    @validate(age={"type": int, "min": 0, "max": 150})
    def voter(age: int) -> bool:
        return age >= 18

    assert voter(30) is True


def test_validate_rejects_type_and_range():
    @validate(age={"type": int, "min": 0, "max": 150})
    def voter(age: int) -> bool:
        return age >= 18

    with pytest.raises(ValidationError, match="age must be int"):
        voter("old")  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="age must be >= 0"):
        voter(-1)


def test_validate_checks_defaulted_arguments():
    @validate(age={"type": int, "min": 0})
    def voter(age: int = -5) -> bool:
        return age >= 18

    with pytest.raises(ValidationError, match="age must be >= 0"):
        voter()


def test_validate_rejects_unknown_parameter():
    with pytest.raises(ToolkitError, match="unknown parameter"):
        validate(bogus_param=int)(lambda: 1)


# --------------------------------------------------------------------------- #
# Context managers
# --------------------------------------------------------------------------- #
def test_temp_directory_lifecycle():
    with temp_directory() as tmp:
        probe = tmp / "file.txt"
        probe.write_text("x", encoding="utf-8")
        assert probe.is_file()
        kept = tmp
    assert not kept.exists()


def test_temp_directory_removed_on_error():
    seen: list[Path] = []
    with pytest.raises(ValueError):
        with temp_directory() as tmp:
            seen.append(tmp)
            raise ValueError("boom")
    assert not seen[0].exists()


def test_capture_stdout():
    with capture_stdout() as buffer:
        print("hello")
        print("world")
    lines = buffer.getvalue().splitlines()
    assert lines == ["hello", "world"]


def test_timed_block_measures_and_labels():
    with timed_block("render") as stats:
        sum(range(10_000))
    assert isinstance(stats, BlockStats)
    assert stats.label == "render"
    assert stats.elapsed >= 0.0


# --------------------------------------------------------------------------- #
# Generators / iterators
# --------------------------------------------------------------------------- #
def test_chunked_partitions_exactly():
    chunks = list(chunked(range(10), 4))
    assert chunks == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]]
    assert [x for c in chunks for x in c] == list(range(10))


def test_chunked_is_lazy():
    consumed: list[int] = []

    def source():
        for i in range(100):
            consumed.append(i)
            yield i

    stream = chunked(source(), 5)
    assert next(stream) == [0, 1, 2, 3, 4]
    assert len(consumed) == 5      # only one chunk pulled from the source


def test_chunked_rejects_bad_size():
    with pytest.raises(ToolkitError, match="chunk size must be an int >= 1"):
        list(chunked([1, 2], 0))


def test_flatten_deeply_nested():
    assert list(flatten([1, [2, [3, [4, [5]]]], (6, 7)])) == \
        [1, 2, 3, 4, 5, 6, 7]
    assert list(flatten("single")) == ["single"]


def test_sliding_window_values_and_validation():
    assert list(sliding_window("abcde", 3)) == [
        ("a", "b", "c"), ("b", "c", "d"), ("c", "d", "e")]
    assert list(sliding_window([1, 2], 9)) == []
    with pytest.raises(ToolkitError, match="window width must be an int >= 1"):
        list(sliding_window([1, 2], -1))


# --------------------------------------------------------------------------- #
# Class idioms
# --------------------------------------------------------------------------- #
def test_point_is_frozen_and_computes():
    origin, target = Point(0.0, 0.0), Point(3.0, 4.0)
    assert origin.distance_to(target) == 5.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        origin.x = 1.0  # type: ignore[misc]


def test_point_has_slots_no_dict():
    point = Point(1.0, 2.0)
    assert not hasattr(point, "__dict__")
    with pytest.raises(AttributeError):
        point.z = 3.0  # type: ignore[misc]


def test_reading_post_init_validation():
    reading = Reading(name="latency", value=12)
    assert reading.value == 12.0 and isinstance(reading.value, float)
    assert reading.scaled(2) == 24.0
    with pytest.raises(ValidationError, match="reading name"):
        Reading(name="", value=1.0)
    with pytest.raises(ValidationError, match="reading value must be a number"):
        Reading(name="x", value=True)  # type: ignore[arg-type]


def test_tally_slots_contract():
    tally = Tally()
    assert tally.count == 0
    tally.bump(2)
    assert tally.bump(3) == 5
    with pytest.raises(AttributeError):
        tally.extra = "nope"  # type: ignore[attr-defined]
    with pytest.raises(ValidationError, match="step must be an int >= 1"):
        tally.bump(0)
    tally.reset()
    assert tally.count == 0


# --------------------------------------------------------------------------- #
# Bundled records
# --------------------------------------------------------------------------- #
def test_load_bundled_records_and_summary():
    records = load_records()
    assert len(records) == 5
    assert RECORDS.parent == PROJECT_ROOT / "data"
    summary = record_summary(records)
    assert summary["count"] == 5
    assert summary["mean_age"] == pytest.approx(49.6)
    assert summary["max_score"] == 97.0


def test_load_missing_file(tmp_path):
    with pytest.raises(ToolkitError, match="file not found"):
        load_records(tmp_path / "nope.json")


def test_load_malformed_json(tmp_path):
    with pytest.raises(ToolkitError, match="could not parse"):
        load_records(_records_json(tmp_path, "{oops"))


def test_load_shape_errors(tmp_path):
    with pytest.raises(ToolkitError, match="JSON array"):
        load_records(_records_json(tmp_path, {"name": "Ada"}))
    with pytest.raises(ToolkitError, match="no records"):
        load_records(_records_json(tmp_path, []))


def test_load_invalid_record_reports_index(tmp_path):
    bad = [{"name": "Ada", "age": 200, "score": 50.0}]
    with pytest.raises(ValidationError, match="record 0: age must be <= 150"):
        load_records(_records_json(tmp_path, bad))


# --------------------------------------------------------------------------- #
# Recipes
# --------------------------------------------------------------------------- #
def test_run_recipe_every_name():
    for name in RECIPE_NAMES:
        line = run_recipe(name)
        assert isinstance(line, str)
        assert name.split("-")[0] in line


def test_run_recipe_rejects_unknown_first():
    with pytest.raises(ToolkitError, match="unknown recipe"):
        run_recipe("knitting")


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "5 records" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_cli_list_recipes(capsys):
    assert main(["--list"]) == 0
    assert capsys.readouterr().out.strip().splitlines() == list(RECIPE_NAMES)


def test_cli_run_recipe(capsys):
    assert main(["--run", "generators"]) == 0
    out = capsys.readouterr().out
    assert "generators" in out and "Done." in out


def test_cli_run_unknown_exits_two(capsys):
    assert main(["--run", "knitting"]) == 2
    assert "unknown recipe" in capsys.readouterr().err


def test_cli_file_valid(capsys):
    assert main(["--file", str(RECORDS)]) == 0
    assert "OK: 5 valid records" in capsys.readouterr().out


def test_cli_file_errors_exit_two(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.json")]) == 2
    assert "file not found" in capsys.readouterr().err
    bad = tmp_path / "bad.json"
    bad.write_text('[{"name": "Ada", "age": -5, "score": 50}]',
                   encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "record 0: age must be >= 0" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_cli_mutually_exclusive_actions(capsys):
    with pytest.raises(SystemExit):
        main(["--demo", "--file", str(RECORDS)])


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""
