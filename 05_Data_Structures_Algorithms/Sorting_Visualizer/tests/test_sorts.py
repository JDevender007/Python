"""Tests for Sorting_Visualizer: a counter's name is a claim."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
from sorts import (                                           # noqa: E402
    ALGORITHMS,
    LEGACY_LINE,
    LEGACY_MERGE_BRANCH,
    STABLE,
    VALUES,
    Frame,
    Item,
    Result,
    SortError,
    Tracer,
    audit,
    bubble_sort,
    heap_sort,
    insertion_sort,
    inversions,
    items_from_keys,
    legacy_label,
    legacy_merge_swaps,
    legacy_merge_writes,
    merge_sort,
    problems,
    quick_sort,
    read_values,
    run_demo,
    selection_sort,
    sorted_keys,
)

SAMPLE = (5, 2, 9, 2, 7, 1, 9, 4, 3, 6, 1, 8)


def sample():
    return items_from_keys(SAMPLE)


def a_values(folder: Path, text: str) -> Path:
    path = folder / "values.txt"
    path.write_bytes(text.encode("utf-8"))
    return path


# --------------------------------------------------------------------------- #
# Item
# --------------------------------------------------------------------------- #
def test_an_item_keeps_its_key_and_label():
    item = Item(7, "#03")
    assert (item.key, item.label, item.sort_key) == (7, "#03", 7)


def test_an_item_refuses_a_float_key():
    with pytest.raises(SortError, match="a key must be an integer"):
        Item(7.5, "x")


def test_an_item_refuses_a_boolean_key():
    with pytest.raises(SortError, match="a key must be an integer"):
        Item(True, "x")


def test_an_item_refuses_an_empty_label():
    with pytest.raises(SortError, match="a label must be a non-empty string"):
        Item(1, "")


def test_an_item_refuses_a_non_text_label():
    with pytest.raises(SortError):
        Item(1, 5)


def test_an_item_prints_key_then_label():
    assert str(Item(4, "#02")) == "4:#02"


def test_two_items_with_the_same_key_are_not_equal():
    assert Item(4, "#01") != Item(4, "#02")


def test_items_order_by_key_first():
    assert Item(1, "#09") < Item(2, "#01")


# --------------------------------------------------------------------------- #
# Making items
# --------------------------------------------------------------------------- #
def test_items_from_keys_labels_each_position():
    assert [item.label for item in items_from_keys([3, 1])] == ["#00", "#01"]


def test_sorted_keys_is_plain_sorted():
    assert sorted_keys([3, 1, 2]) == (1, 2, 3)


# --------------------------------------------------------------------------- #
# inversions
# --------------------------------------------------------------------------- #
def test_a_sorted_sequence_has_no_inversions():
    assert inversions([1, 2, 3, 4]) == 0


def test_a_reversed_sequence_is_fully_inverted():
    assert inversions([4, 3, 2, 1]) == 6


def test_equal_values_are_never_inversions():
    assert inversions([2, 2, 2]) == 0


def test_inversions_count_pairs_not_positions():
    assert inversions([2, 1, 1, 0]) == 5


def test_the_bundled_inversion_count_is_pinned():
    assert inversions(SAMPLE) == 32


# --------------------------------------------------------------------------- #
# read_values
# --------------------------------------------------------------------------- #
def test_read_values_refuses_a_missing_file(tmp_path):
    with pytest.raises(SortError, match="values file not found"):
        read_values(tmp_path / "nope.txt")


def test_read_values_reads_one_integer_per_line(tmp_path):
    path = a_values(tmp_path, "3\n1\n2\n")
    assert [item.key for item in read_values(path)] == [3, 1, 2]


def test_read_values_labels_by_position_not_by_line(tmp_path):
    path = a_values(tmp_path, "# a comment\n3\n\n1\n")
    assert [item.label for item in read_values(path)] == ["#01", "#02"]


def test_read_values_skips_comments_and_blank_lines(tmp_path):
    path = a_values(tmp_path, "# head\n\n4\n")
    assert len(read_values(path)) == 1


def test_read_values_refuses_a_word(tmp_path):
    path = a_values(tmp_path, "3\nfive\n")
    with pytest.raises(SortError, match="'five' is not an integer"):
        read_values(path)


def test_read_values_names_the_line_of_a_bad_value(tmp_path):
    path = a_values(tmp_path, "3\nx\n")
    with pytest.raises(SortError, match="values.txt:2"):
        read_values(path)


def test_read_values_of_an_empty_file_is_empty(tmp_path):
    path = a_values(tmp_path, "")
    assert read_values(path) == ()


def test_read_values_accepts_negative_and_spaced_ints(tmp_path):
    path = a_values(tmp_path, "  -5  \n+3\n")
    assert [item.key for item in read_values(path)] == [-5, 3]


def test_read_values_of_the_bundled_file_is_pinned():
    items = read_values()
    assert [item.key for item in items] == list(SAMPLE)
    assert len(items) == 12


def test_the_bundled_values_file_has_twelve_short_lines():
    assert VALUES.read_bytes().count(b"\n") == 12


# --------------------------------------------------------------------------- #
# Tracer
# --------------------------------------------------------------------------- #
def test_a_tracer_starts_with_one_frame():
    trace = Tracer(sample())
    assert len(trace.frames) == 1 and trace.frames[0].data == SAMPLE


def test_a_tracer_starts_with_zero_counters():
    trace = Tracer(sample())
    assert (trace.comparisons, trace.writes, trace.swaps) == (0, 0, 0)


def test_compare_counts_and_answers():
    trace = Tracer(items_from_keys([1, 2]))
    assert trace.compare(0, 1) is True and trace.comparisons == 1


def test_compare_is_false_when_the_left_is_larger():
    trace = Tracer(items_from_keys([2, 1]))
    assert trace.compare(0, 1) is False


def test_a_write_counts_one_placement():
    trace = Tracer(items_from_keys([1, 2]))
    trace.write(0, 9, "#99")
    assert (trace.data, trace.labels, trace.writes) == ([9, 2], ["#99", "#01"], 1)


def test_a_swap_counts_two_writes_and_one_swap():
    trace = Tracer(items_from_keys([1, 2]))
    trace.swap(0, 1)
    assert (trace.data, trace.writes, trace.swaps) == ([2, 1], 2, 1)


def test_swapping_a_position_with_itself_is_not_a_swap():
    trace = Tracer(items_from_keys([1, 2]))
    trace.swap(1, 1)
    assert (trace.writes, trace.swaps, len(trace.frames)) == (0, 0, 1)


def test_a_swap_moves_the_labels_with_the_keys():
    trace = Tracer(items_from_keys([5, 1]))
    trace.swap(0, 1)
    assert trace.labels == ["#01", "#00"]


def test_a_frame_records_the_counters_at_that_moment():
    trace = Tracer(items_from_keys([1, 2]))
    trace.compare(0, 1)
    trace.swap(0, 1)
    assert trace.frames[-1] == Frame((2, 1), 1, 2)


def test_a_frame_is_frozen():
    frame = Frame((1,), 0, 0)
    with pytest.raises(Exception):
        frame.writes = 3                            # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Every algorithm: the basic contract
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_every_algorithm_sorts_the_bundled_values(name):
    result = ALGORITHMS[name](sample())
    assert result.is_sorted() and result.keys == sorted_keys(SAMPLE)


@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_every_algorithm_keeps_every_item(name):
    result = ALGORITHMS[name](sample())
    assert result.is_permutation() and len(result.order) == 12


@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_every_algorithm_handles_an_empty_input(name):
    result = ALGORITHMS[name](())
    assert result.order == () and result.comparisons == 0


@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_every_algorithm_handles_one_item(name):
    result = ALGORITHMS[name](items_from_keys([7]))
    assert result.keys == (7,) and result.writes == 0


@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_every_algorithm_handles_a_sorted_input(name):
    result = ALGORITHMS[name](items_from_keys([1, 2, 3, 4]))
    assert result.is_sorted()


@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_every_algorithm_handles_a_reversed_input(name):
    result = ALGORITHMS[name](items_from_keys([4, 3, 2, 1]))
    assert result.keys == (1, 2, 3, 4)


@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_every_algorithm_handles_all_equal_keys(name):
    result = ALGORITHMS[name](items_from_keys([3, 3, 3]))
    assert result.is_sorted() and result.is_permutation()


@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_every_algorithm_keeps_the_first_frame_as_the_input(name):
    result = ALGORITHMS[name](sample())
    assert result.frames[0].data == SAMPLE


@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_the_last_frame_of_every_algorithm_matches_its_counters(name):
    result = ALGORITHMS[name](sample())
    assert result.frames[-1].comparisons == result.comparisons
    assert result.frames[-1].writes == result.writes


@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_the_last_frame_holds_the_sorted_keys(name):
    result = ALGORITHMS[name](sample())
    assert result.frames[-1].data == sorted_keys(SAMPLE)


@pytest.mark.parametrize("name", sorted(ALGORITHMS))
def test_every_algorithm_writes_at_least_twice_its_swaps(name):
    result = ALGORITHMS[name](sample())
    assert result.writes >= 2 * result.swaps


# --------------------------------------------------------------------------- #
# The pinned counts for the bundled values
# --------------------------------------------------------------------------- #
def test_bubble_counts_are_pinned():
    result = bubble_sort(sample())
    assert (result.comparisons, result.writes, result.swaps) == (65, 64, 32)
    assert len(result.frames) == 34


def test_insertion_counts_are_pinned():
    result = insertion_sort(sample())
    assert (result.comparisons, result.writes, result.swaps) == (41, 41, 0)
    assert len(result.frames) == 42


def test_selection_counts_are_pinned():
    result = selection_sort(sample())
    assert (result.comparisons, result.writes, result.swaps) == (66, 18, 9)
    assert len(result.frames) == 11


def test_merge_counts_are_pinned():
    result = merge_sort(sample())
    assert (result.comparisons, result.writes, result.swaps) == (31, 44, 0)
    assert len(result.frames) == 45


def test_quick_counts_are_pinned():
    result = quick_sort(sample())
    assert (result.comparisons, result.writes, result.swaps) == (36, 24, 12)
    assert len(result.frames) == 14


def test_heap_counts_are_pinned():
    result = heap_sort(sample())
    assert (result.comparisons, result.writes, result.swaps) == (50, 64, 32)
    assert len(result.frames) == 33


# --------------------------------------------------------------------------- #
# The properties each algorithm is chosen for
# --------------------------------------------------------------------------- #
def test_selection_sort_never_swaps_more_than_n_minus_one_times():
    for keys in ([4, 3, 2, 1], [1, 2, 3, 4], list(SAMPLE)):
        result = selection_sort(items_from_keys(keys))
        assert result.swaps <= len(keys) - 1


def test_selection_sort_on_a_fully_reversed_input_swaps_half_the_positions():
    result = selection_sort(items_from_keys([5, 4, 3, 2, 1]))
    assert result.swaps == 2


def test_selection_sort_on_a_sorted_input_swaps_nothing():
    assert selection_sort(items_from_keys([1, 2, 3, 4])).swaps == 0


def test_merge_sort_never_swaps():
    assert merge_sort(sample()).swaps == 0


def test_merge_sort_writes_every_element_of_every_merge():
    result = merge_sort(items_from_keys([4, 3, 2, 1]))
    assert result.writes == 8 and result.swaps == 0


def test_insertion_sort_never_swaps_either():
    assert insertion_sort(sample()).swaps == 0


def test_insertion_sort_on_a_sorted_input_compares_once_per_item():
    assert insertion_sort(items_from_keys([1, 2, 3, 4])).comparisons == 3


def test_bubble_sort_on_a_sorted_input_compares_n_minus_one_times():
    assert bubble_sort(items_from_keys(list(range(12)))).comparisons == 11


def test_bubble_sort_on_a_reversed_input_compares_n_n_minus_one_over_two():
    result = bubble_sort(items_from_keys(list(range(12, 0, -1))))
    assert result.comparisons == 66


def test_quick_sort_on_a_sorted_input_costs_n_n_minus_one_over_two():
    result = quick_sort(items_from_keys(list(range(12))))
    assert result.comparisons == 66


def test_quick_sort_beats_its_worst_case_on_the_bundled_input():
    assert quick_sort(sample()).comparisons < 66


def test_selection_sort_always_compares_the_same_number_of_times():
    counts = {selection_sort(items_from_keys(keys)).comparisons
              for keys in ([1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [3, 1, 5, 2, 4])}
    assert counts == {10}


# --------------------------------------------------------------------------- #
# Stability
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", STABLE)
def test_the_stable_algorithms_are_stable(name):
    assert ALGORITHMS[name](sample()).is_stable()


@pytest.mark.parametrize("name", [n for n in ALGORITHMS if n not in STABLE])
def test_the_unstable_algorithms_separate_equal_keys(name):
    assert not ALGORITHMS[name](sample()).is_stable()


def test_stability_is_measured_on_far_apart_duplicates():
    items = items_from_keys([2, 2, 1])
    assert selection_sort(items).is_stable() is False


def test_a_merge_sort_keeps_equal_keys_in_input_order():
    items = items_from_keys([2, 1, 2])
    assert merge_sort(items).labels == ("#01", "#00", "#02")


def test_stability_of_a_sequence_without_duplicates_is_trivially_true():
    assert heap_sort(items_from_keys([3, 1, 2])).is_stable()


# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #
def test_a_result_exposes_its_keys_and_labels():
    result = merge_sort(sample())
    assert result.keys == sorted_keys(SAMPLE) and len(result.labels) == 12


def test_a_result_summary_holds_every_number():
    summary = merge_sort(sample()).summary()
    assert summary == {"algorithm": "merge", "items": 12, "comparisons": 31,
                       "writes": 44, "swaps": 0, "frames": 45,
                       "sorted": True, "permutation": True, "stable": True}


def test_a_result_dict_holds_the_order_and_the_frames():
    payload = merge_sort(sample()).to_dict()
    assert payload["order"][0] == "1:#05"
    assert len(payload["frames"]) == 45
    assert payload["frames"][0] == [list(SAMPLE), 0, 0]


def test_a_result_is_frozen():
    result = merge_sort(sample())
    with pytest.raises(Exception):
        result.comparisons = 0                      # type: ignore[misc]


# --------------------------------------------------------------------------- #
# The legacy counter
# --------------------------------------------------------------------------- #
def test_the_legacy_line_and_label_are_pinned():
    assert LEGACY_LINE == "swaps += 1"
    assert legacy_label() == "swaps"
    assert "swaps += 1" in LEGACY_MERGE_BRANCH


def test_the_legacy_counter_counts_placements():
    assert legacy_merge_writes(sample()) == 44


def test_the_honest_swap_count_of_merge_sort_is_zero():
    assert legacy_merge_swaps(sample()) == 0


def test_the_legacy_counter_agrees_with_this_merge_sort_write_count():
    assert legacy_merge_writes(sample()) == merge_sort(sample()).writes


def test_the_legacy_counter_is_not_a_swap_count():
    result = merge_sort(sample())
    assert legacy_merge_writes(sample()) != result.swaps


def test_the_legacy_counter_of_an_empty_input_is_zero():
    assert legacy_merge_writes(()) == 0


def test_the_legacy_counter_of_one_item_is_zero():
    assert legacy_merge_writes(items_from_keys([4])) == 0


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def all_results():
    return [ALGORITHMS[name](sample()) for name in ALGORITHMS]


def test_the_audit_holds_eight_named_checks():
    assert [name for name, _ in audit(all_results())] == [
        "every result is sorted",
        "every result is a permutation of its input",
        "every result keeps the item count",
        "no result reports fewer than zero comparisons",
        "a swap costs two writes, so writes >= 2 * swaps",
        "the last frame agrees with the final counters",
        "the first frame is the untouched input",
        "only the stable three are stable"]


def test_the_audit_passes_on_the_six_real_results():
    assert problems(all_results()) == []


def test_the_audit_catches_an_unsorted_result():
    results = all_results()
    object.__setattr__(results[0], "order", tuple(reversed(results[0].order)))
    assert "every result is sorted" in problems(results)


def test_the_audit_catches_a_lost_item():
    results = all_results()
    object.__setattr__(results[0], "order", results[0].order[:-1])
    assert "every result is a permutation of its input" in problems(results)


def test_the_audit_catches_a_duplicated_item():
    results = all_results()
    order = results[0].order
    object.__setattr__(results[0], "order", order[:-1] + (order[0],))
    assert "every result is a permutation of its input" in problems(results)


def test_the_audit_catches_a_short_result():
    results = all_results()
    object.__setattr__(results[0], "original", results[0].original[:-1])
    assert "every result keeps the item count" in problems(results)


def test_the_audit_catches_a_negative_counter():
    results = all_results()
    object.__setattr__(results[0], "comparisons", -1)
    assert "no result reports fewer than zero comparisons" in problems(results)


def test_the_audit_catches_a_swap_cheaper_than_its_writes():
    results = all_results()
    object.__setattr__(results[0], "swaps", 10 ** 6)
    assert problems(results) == ["a swap costs two writes, so writes >= "
                                 "2 * swaps"]


def test_the_audit_catches_a_stale_last_frame():
    results = all_results()
    object.__setattr__(results[0], "comparisons",
                       results[0].comparisons + 1)
    assert problems(results) == ["the last frame agrees with the final "
                                 "counters"]


def test_the_audit_catches_a_stale_first_frame():
    results = all_results()
    object.__setattr__(results[0], "frames",
                       (Frame((9, 9), 0, 0),) + results[0].frames[1:])
    assert problems(results) == ["the first frame is the untouched input"]


def test_the_audit_catches_a_stability_claim_that_is_wrong():
    results = all_results()
    selection = next(r for r in results if r.algorithm == "selection")
    object.__setattr__(selection, "algorithm", "bubble")
    assert problems(results) == ["only the stable three are stable"]


def test_the_audit_is_repeatable():
    results = all_results()
    assert audit(results) == audit(results)


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
    assert all(ord(c) < 128 for c in capsys.readouterr().out)


def test_demo_shows_the_inversions(capsys):
    run_demo()
    assert "32 inversions to begin with" in capsys.readouterr().out


def test_demo_shows_the_six_rows(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "bubble               65       64      32      yes       34" in out
    assert "merge                31       44       0      yes       45" in out


def test_demo_names_the_legacy_label(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "called 'swaps'" in out and "writes\n" not in out


def test_demo_shows_that_merge_swaps_zero_times(capsys):
    run_demo()
    assert "merge sort really swaps 0 times" in capsys.readouterr().out


def test_demo_shows_the_worst_case(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "already-sorted 12: 66 comparisons (n(n-1)/2 = 66)" in out


def test_demo_shows_the_eight_checks(capsys):
    run_demo()
    assert "8/8 checks pass" in capsys.readouterr().out


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


def test_cli_prints_the_table(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "12 items, 32 inversions" in out
    assert "selection             66      18      9      no      11" in out


def test_cli_sort_merge_prints_one_row(capsys):
    assert cli.main(["--sort", "merge"]) == 0
    out = capsys.readouterr().out
    assert "merge                 31      44      0     yes      45" in out
    assert "bubble" not in out


def test_cli_compare_prints_the_legacy_number(capsys):
    assert cli.main(["--compare"]) == 0
    out = capsys.readouterr().out
    assert "the legacy label is 'swaps'" in out
    assert "swaps 0 times and writes 44 placements" in out


def test_cli_worst_runs_quick_sort_on_sorted_input(capsys):
    assert cli.main(["--worst"]) == 0
    assert "already-sorted input: 66 comparisons" in capsys.readouterr().out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 8 and "FAIL" not in out


def test_cli_json_writes_every_result(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["results"]) == 6
    assert payload["results"][0]["algorithm"] == "bubble"
    assert payload["stable"] == ["bubble", "insertion", "merge"]


def test_cli_json_creates_directories(tmp_path, capsys):
    target = tmp_path / "a" / "b" / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    assert target.is_file()


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_reads_another_values_file(tmp_path, capsys):
    path = a_values(tmp_path, "3\n1\n2\n")
    assert cli.main(["--values", str(path)]) == 0
    out = capsys.readouterr().out
    assert "3 items" in out


def test_cli_missing_values_exits_two(tmp_path, capsys):
    assert cli.main(["--values", str(tmp_path / "nope.txt")]) == 2
    assert "values file not found" in capsys.readouterr().err


def test_cli_a_bad_value_exits_two(tmp_path, capsys):
    path = a_values(tmp_path, "1\nx\n")
    assert cli.main(["--values", str(path)]) == 2
    assert "is not an integer" in capsys.readouterr().err


def test_cli_an_empty_file_exits_two(tmp_path, capsys):
    path = a_values(tmp_path, "# nothing\n")
    assert cli.main(["--values", str(path)]) == 2
    assert "no integers" in capsys.readouterr().err


def test_cli_a_two_item_file_sorts(capsys, tmp_path):
    path = a_values(tmp_path, "2\n1\n")
    assert cli.main(["--values", str(path), "--sort", "heap"]) == 0
    assert "2 items" in capsys.readouterr().out
