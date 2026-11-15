"""Tests for Binary_Search_Visualizer: a search returns an index into the array
it searched."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
from search import (                                          # noqa: E402
    LEGACY_RETURN,
    LEGACY_SORT,
    NUMBERS,
    PRECONDITION,
    Probe,
    Result,
    SearchError,
    audit,
    audit_pairs,
    binary_search,
    check_sequence,
    check_target,
    comparison_bound,
    count_of,
    first_index,
    is_sorted,
    last_index,
    legacy_note,
    legacy_sorted_index,
    legacy_wrong_value,
    linear_search,
    problems,
    read_numbers,
    run_demo,
)

DATA = (2, 4, 4, 7, 9, 11, 13, 13, 13, 17, 19, 23, 29, 31, 37, 41)


def a_numbers(folder: Path, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "numbers.txt"
    path.write_bytes(text.encode("utf-8"))
    return path


# --------------------------------------------------------------------------- #
# Probe
# --------------------------------------------------------------------------- #
def test_a_probe_keeps_its_window_and_its_middle():
    probe = Probe(0, 15, 7, 1)
    assert (probe.low, probe.high, probe.middle) == (0, 15, 7)


def test_a_probe_width_counts_inclusive_positions():
    assert Probe(0, 15, 7, 1).width == 16


def test_a_probe_of_one_position_has_width_one():
    assert Probe(6, 6, 6, 3).width == 1


def test_an_inverted_window_is_refused():
    with pytest.raises(SearchError, match="an empty window is refused"):
        Probe(5, 4, 5, 1)


def test_a_negative_window_is_refused():
    with pytest.raises(SearchError, match="an empty window is refused"):
        Probe(-1, 4, 0, 1)


def test_a_middle_outside_the_window_is_refused():
    with pytest.raises(SearchError, match="is outside"):
        Probe(2, 4, 9, 1)


def test_a_probe_needs_at_least_one_comparison():
    with pytest.raises(SearchError, match="at least one comparison"):
        Probe(0, 1, 0, 0)


# --------------------------------------------------------------------------- #
# Result
# --------------------------------------------------------------------------- #
def test_a_hit_reports_its_index_and_value():
    result = binary_search(DATA, 23)
    assert result.found and result.index == 11 and result.value == 23


def test_a_miss_reports_no_index_and_no_value():
    result = binary_search(DATA, 22)
    assert not result.found and result.index is None and result.value is None


def test_comparisons_are_the_probe_count():
    result = binary_search(DATA, 23)
    assert result.comparisons == len(result.probes) == 2


def test_is_hit_is_true_for_a_real_hit():
    assert binary_search(DATA, 17).is_hit()


def test_is_hit_is_true_for_a_real_miss():
    assert binary_search(DATA, 22).is_hit()


def test_is_hit_is_false_when_the_index_points_elsewhere():
    result = binary_search(DATA, 23)
    object.__setattr__(result, "index", 0)
    assert not result.is_hit()


def test_windows_shrink_holds_for_a_binary_search():
    assert binary_search(DATA, 22).windows_shrink()


def test_a_summary_holds_every_number():
    assert binary_search(DATA, 23).summary() == {
        "algorithm": "binary", "items": 16, "target": 23, "index": 11,
        "found": True, "comparisons": 2}


def test_a_result_dict_holds_the_probes():
    payload = binary_search(DATA, 23).to_dict()
    assert payload["probes"] == [[0, 15, 7], [8, 15, 11]]


def test_a_result_is_frozen():
    result = binary_search(DATA, 23)
    with pytest.raises(Exception):
        result.index = 0                            # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Reading and checking
# --------------------------------------------------------------------------- #
def test_read_numbers_refuses_a_missing_file(tmp_path):
    with pytest.raises(SearchError, match="numbers file not found"):
        read_numbers(tmp_path / "nope.txt")


def test_read_numbers_reads_one_integer_per_line(tmp_path):
    assert read_numbers(a_numbers(tmp_path, "1\n2\n3\n")) == (1, 2, 3)


def test_read_numbers_skips_comments_and_blanks(tmp_path):
    assert read_numbers(a_numbers(tmp_path, "# x\n\n7\n")) == (7,)


def test_read_numbers_refuses_a_word(tmp_path):
    with pytest.raises(SearchError, match="'two' is not an integer"):
        read_numbers(a_numbers(tmp_path, "1\ntwo\n"))


def test_read_numbers_of_an_empty_file_is_empty(tmp_path):
    assert read_numbers(a_numbers(tmp_path, "")) == ()


def test_the_bundled_numbers_are_pinned():
    assert read_numbers() == DATA


def test_the_bundled_file_has_one_line_per_number():
    assert NUMBERS.read_bytes().count(b"\n") == 16


def test_is_sorted_accepts_ascending_and_equal():
    assert is_sorted([1, 2, 2, 3]) and is_sorted([])


def test_is_sorted_refuses_a_drop():
    assert not is_sorted([1, 3, 2])


def test_check_sequence_returns_a_tuple():
    assert check_sequence([1, 2]) == (1, 2)


def test_check_sequence_refuses_a_word():
    with pytest.raises(SearchError, match="not an integer"):
        check_sequence([1, "two"])


def test_check_sequence_refuses_a_float():
    with pytest.raises(SearchError, match="not an integer"):
        check_sequence([1.0, 2])


def test_check_sequence_refuses_a_boolean():
    with pytest.raises(SearchError, match="not an integer"):
        check_sequence([True, 2])


def test_check_sequence_refuses_an_unsorted_sequence():
    with pytest.raises(SearchError, match=PRECONDITION):
        check_sequence([30, 10, 20])


def test_check_target_accepts_an_integer():
    assert check_target(5) == 5


def test_check_target_refuses_a_float():
    with pytest.raises(SearchError, match="a target must be an integer"):
        check_target(5.0)


def test_check_target_refuses_a_boolean():
    with pytest.raises(SearchError, match="a target must be an integer"):
        check_target(True)


# --------------------------------------------------------------------------- #
# binary_search
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("target", DATA)
def test_binary_search_finds_every_present_value(target):
    result = binary_search(DATA, target)
    assert result.found and result.is_hit()


@pytest.mark.parametrize("target", [1, 3, 5, 6, 8, 12, 14, 22, 24, 40, 42, -5])
def test_binary_search_reports_an_absent_value_as_a_miss(target):
    result = binary_search(DATA, target)
    assert not result.found and result.is_hit()


def test_binary_search_refuses_an_unsorted_sequence():
    with pytest.raises(SearchError, match=PRECONDITION):
        binary_search((30, 10, 20), 10)


def test_binary_search_refuses_a_non_integer_target():
    with pytest.raises(SearchError, match="a target must be an integer"):
        binary_search(DATA, "23")


def test_binary_search_of_an_empty_sequence_misses_without_comparing():
    result = binary_search((), 1)
    assert result.probes == () and not result.found


def test_binary_search_of_one_item_hits_in_one_comparison():
    result = binary_search((7,), 7)
    assert result.index == 0 and result.comparisons == 1


def test_binary_search_of_two_items_hits_in_one_or_two_comparisons():
    assert binary_search((1, 2), 1).comparisons == 1
    assert binary_search((1, 2), 2).comparisons == 2


def test_binary_search_never_sorts_the_input_it_was_given():
    values = (1, 3, 5, 7)
    result = binary_search(values, 7)
    assert result.values == values


def test_binary_search_returns_the_left_or_right_duplicate_it_meets():
    result = binary_search(DATA, 13)
    assert result.index in (6, 7, 8) and result.value == 13


def test_binary_search_stays_inside_the_hit_bound_for_every_present_value():
    for target in DATA:
        result = binary_search(DATA, target)
        assert result.comparisons <= comparison_bound(len(DATA), True)


def test_binary_search_stays_inside_the_miss_bound_for_absent_values():
    for target in range(0, 45):
        if target in DATA:
            continue
        result = binary_search(DATA, target)
        assert result.comparisons <= comparison_bound(len(DATA), False)


def test_binary_search_on_sixteen_items_costs_at_most_five_comparisons():
    assert max(binary_search(DATA, n).comparisons
               for n in range(0, 45)) <= 5


# --------------------------------------------------------------------------- #
# linear_search
# --------------------------------------------------------------------------- #
def test_linear_search_finds_the_first_copy():
    result = linear_search(DATA, 13)
    assert result.index == 6 and result.comparisons == 7


def test_linear_search_walks_one_position_per_comparison():
    assert linear_search(DATA, 2).comparisons == 1


def test_linear_search_of_an_absent_value_costs_the_whole_sequence():
    result = linear_search(DATA, 99)
    assert result.index is None and result.comparisons == 16


def test_linear_search_of_an_empty_sequence_compares_nothing():
    assert linear_search((), 1).probes == ()


def test_linear_search_does_not_require_a_sorted_sequence():
    assert linear_search((30, 10, 20), 10).index == 1


def test_linear_search_refuses_a_bad_target():
    with pytest.raises(SearchError, match="a target must be an integer"):
        linear_search((1, 2), 1.5)


def test_linear_search_reports_the_same_index_as_the_binary_hit():
    for target in DATA:
        assert linear_search(DATA, target).index == \
            binary_search(DATA, target).index or target in (4, 13)


# --------------------------------------------------------------------------- #
# range queries
# --------------------------------------------------------------------------- #
def test_first_index_of_a_block_of_three_is_six():
    assert first_index(DATA, 13) == 6


def test_last_index_of_a_block_of_three_is_eight():
    assert last_index(DATA, 13) == 8


def test_count_of_a_block_of_three_is_three():
    assert count_of(DATA, 13) == 3


def test_first_and_last_index_of_a_single_copy_agree():
    assert first_index(DATA, 23) == last_index(DATA, 23) == 11


def test_first_index_of_an_absent_value_is_none():
    assert first_index(DATA, 12) is None and last_index(DATA, 12) is None


def test_count_of_an_absent_value_is_zero():
    assert count_of(DATA, 12) == 0


def test_count_of_the_first_value_is_one():
    assert count_of(DATA, 2) == 1 and first_index(DATA, 2) == 0


def test_count_of_the_second_block_is_two():
    assert count_of(DATA, 4) == 2 and first_index(DATA, 4) == 1


def test_the_counts_of_the_bundled_data_sum_to_its_length():
    total = sum(count_of(DATA, key) for key in set(DATA))
    assert total == len(DATA)


def test_a_range_query_refuses_an_unsorted_sequence():
    with pytest.raises(SearchError, match=PRECONDITION):
        first_index((2, 1), 2)


def test_first_index_agrees_with_bisect_left():
    import bisect
    for target in range(0, 45):
        left = bisect.bisect_left(list(DATA), target)
        expected = left if left < len(DATA) and DATA[left] == target else None
        assert first_index(DATA, target) == expected


def test_last_index_agrees_with_bisect_right():
    import bisect
    for target in range(0, 45):
        right = bisect.bisect_right(list(DATA), target) - 1
        expected = right if right >= 0 and DATA[right] == target else None
        assert last_index(DATA, target) == expected


# --------------------------------------------------------------------------- #
# comparison_bound
# --------------------------------------------------------------------------- #
def test_the_hit_bound_of_zero_items_is_zero():
    assert comparison_bound(0, True) == 0


def test_the_hit_bound_of_one_item_is_one():
    assert comparison_bound(1, True) == 1


def test_the_hit_bound_of_sixteen_items_is_five():
    assert comparison_bound(16, True) == 5


def test_the_miss_bound_of_one_item_is_one():
    assert comparison_bound(1, False) == 1


def test_the_miss_bound_never_falls_below_the_hit_bound():
    for size in range(1, 65):
        assert comparison_bound(size, False) >= comparison_bound(size, True)


# --------------------------------------------------------------------------- #
# The legacy function
# --------------------------------------------------------------------------- #
def test_the_legacy_lines_are_pinned():
    assert LEGACY_SORT == "values = sorted(array)"
    assert "middle, middle" in LEGACY_RETURN
    assert legacy_note() == (LEGACY_SORT, LEGACY_RETURN)


def test_the_legacy_index_is_an_index_into_the_sorted_copy():
    assert legacy_sorted_index([30, 10, 20], 10) == 0


def test_the_legacy_index_points_at_the_wrong_item():
    assert legacy_wrong_value([30, 10, 20], 10) == 30


def test_the_legacy_function_agrees_when_the_input_is_already_sorted():
    assert legacy_wrong_value([10, 20, 30], 20) == 20


def test_the_legacy_function_reports_a_miss_as_none():
    assert legacy_sorted_index([1, 2, 3], 9) is None
    assert legacy_wrong_value([1, 2, 3], 9) is None


def test_the_legacy_function_refuses_a_bad_target():
    with pytest.raises(SearchError, match="a target must be an integer"):
        legacy_sorted_index([1, 2], "x")


def test_the_module_refuses_what_the_legacy_function_silently_sorted():
    with pytest.raises(SearchError):
        binary_search([30, 10, 20], 10)


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def audit_corpus():
    return [binary_search(DATA, n) for n in DATA] + [binary_search(DATA, 22)]


def test_the_audit_holds_seven_named_checks():
    assert [name for name, _ in audit(audit_corpus())] == [
        "every found index points at the target",
        "every miss is a value the sequence does not hold",
        "every index lies inside the sequence",
        "every binary probe narrows the window",
        "binary search stays inside its comparison bound",
        "a hit's value is the target and a miss's value is None",
        "every binary result was searched on an ascending sequence"]


def test_the_audit_passes_on_the_real_results():
    assert problems(audit_corpus()) == []


def test_the_audit_catches_a_index_that_misses_the_target():
    results = audit_corpus()
    object.__setattr__(results[0], "index", 3)
    assert "every found index points at the target" in problems(results)


def test_the_audit_catches_a_false_miss():
    results = audit_corpus()
    object.__setattr__(results[0], "index", None)
    assert "every miss is a value the sequence does not hold" in problems(results)


def test_the_audit_catches_an_index_outside_the_sequence():
    results = audit_corpus()
    object.__setattr__(results[0], "index", 99)
    assert "every index lies inside the sequence" in problems(results)


def test_the_audit_catches_a_window_that_does_not_shrink():
    results = audit_corpus()
    stuck = (Probe(0, 15, 7, 1), Probe(0, 15, 7, 2))
    object.__setattr__(results[0], "probes", stuck)
    assert "every binary probe narrows the window" in problems(results)


def test_the_audit_catches_exceeding_the_comparison_bound():
    results = audit_corpus()
    many = tuple(Probe(0, 15 - offset, 0, offset + 1) for offset in range(7))
    object.__setattr__(results[0], "probes", many)
    assert "binary search stays inside its comparison bound" in problems(results)


def test_the_audit_catches_a_binary_result_on_an_unsorted_sequence():
    results = audit_corpus()
    object.__setattr__(results[0], "values", (3, 1))
    assert "every binary result was searched on an ascending sequence" in \
        problems(results)


def test_the_audit_catches_a_hit_whose_value_is_wrong():
    results = audit_corpus()
    object.__setattr__(results[0], "values", (0,) * 16)
    assert "a hit's value is the target and a miss's value is None" in \
        problems(results)


def test_the_pair_audit_compares_the_totals():
    pairs = [(binary_search(DATA, n), linear_search(DATA, n)) for n in DATA]
    checks = audit_pairs(pairs)
    assert len(checks) == 1 and checks[0][1] is True


def test_the_pair_audit_is_not_a_restatement_of_one_pair():
    pairs = [(binary_search(DATA, n), linear_search(DATA, n)) for n in DATA]
    binary_total = sum(b.comparisons for b, _ in pairs)
    linear_total = sum(l.comparisons for _, l in pairs)
    assert binary_total < linear_total == 132


def test_the_audit_is_repeatable():
    results = audit_corpus()
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


def test_demo_shows_the_hit_and_the_linear_cost(capsys):
    run_demo()
    assert "index 11 in 2 comparisons, linear in 12" in \
        capsys.readouterr().out


def test_demo_shows_the_bounds(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "the bound for a hit on 16 is 5" in out
    assert "target 22 is absent: 4 comparisons, bound 5" in out


def test_demo_shows_the_legacy_line(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "values = sorted(array)" in out
    assert "gives 30" in out


def test_demo_shows_the_three_copies(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "first_index(13) 6" in out and "count_of(13) 3" in out


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


def test_cli_prints_the_binary_row(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "binary       16      23     11            2" in out


def test_cli_linear_adds_a_second_row(capsys):
    assert cli.main(["--linear"]) == 0
    out = capsys.readouterr().out
    assert "linear       16      23     11           12" in out


def test_cli_range_prints_the_block(capsys):
    assert cli.main(["--target", "13", "--range"]) == 0
    assert "first 6, last 8, count 3" in capsys.readouterr().out


def test_cli_legacy_prints_the_wrong_value(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "index 0 of the array you passed is 30" in out
    assert "the sequence must be ascending" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit", "--linear"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 8 and "FAIL" not in out


def test_cli_json_writes_the_two_results(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--linear", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["binary"]["index"] == 11
    assert payload["linear"]["comparisons"] == 12


def test_cli_json_without_linear_holds_null(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["linear"] is None


def test_cli_json_creates_directories(tmp_path, capsys):
    target = tmp_path / "a" / "b" / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    assert target.is_file()


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_miss_prints_a_dash(capsys):
    assert cli.main(["--target", "22"]) == 0
    assert "binary       16      22      -            4" in capsys.readouterr().out


def test_cli_reads_another_numbers_file(tmp_path, capsys):
    path = a_numbers(tmp_path, "1\n2\n3\n")
    assert cli.main(["--numbers", str(path), "--target", "2"]) == 0
    assert "3 numbers" in capsys.readouterr().out


def test_cli_refuses_an_unsorted_file(tmp_path, capsys):
    path = a_numbers(tmp_path, "3\n1\n2\n")
    assert cli.main(["--numbers", str(path), "--target", "1"]) == 2
    assert "the sequence must be ascending" in capsys.readouterr().err


def test_cli_missing_numbers_exits_two(tmp_path, capsys):
    assert cli.main(["--numbers", str(tmp_path / "nope.txt")]) == 2
    assert "numbers file not found" in capsys.readouterr().err


def test_cli_a_bad_line_exits_two(tmp_path, capsys):
    path = a_numbers(tmp_path, "1\nx\n")
    assert cli.main(["--numbers", str(path)]) == 2
    assert "is not an integer" in capsys.readouterr().err
