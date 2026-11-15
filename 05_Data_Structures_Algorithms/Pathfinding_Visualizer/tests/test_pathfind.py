"""Tests for Pathfinding_Visualizer: a wall clock makes a result
unreproducible, and greedy best-first shares a dropdown with the optimal three.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
from pathfind import (                                        # noqa: E402
    ALGORITHMS,
    ALIASES,
    END,
    FLOOR,
    GRID_FILE,
    LEGACY_FIELD,
    LEGACY_FOUND,
    LEGACY_TIMING,
    LONGER,
    MOVES,
    OPTIMAL,
    START,
    WALL,
    Cell,
    Grid,
    Outcome,
    PathError,
    audit,
    astar,
    breadth_first,
    depth_first,
    dijkstra,
    greedy,
    has_clock,
    legacy_spread,
    legacy_times,
    manhattan,
    problems,
    read_grid,
    resolve,
    run_all,
    run_demo,
)

BFS_PATH = ((0, 0), (0, 1), (1, 1), (2, 1), (2, 2), (3, 2), (4, 2), (5, 2),
            (5, 3), (5, 4), (5, 5))
GREEDY_PATH = ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (1, 5), (2, 5),
               (3, 5), (3, 4), (3, 3), (3, 2), (4, 2), (5, 2), (5, 3), (5, 4),
               (5, 5))


def cells(pairs) -> tuple[Cell, ...]:
    return tuple(Cell(row, column) for row, column in pairs)


def bundled() -> Grid:
    return read_grid()


def a_grid(folder: Path, text: str, name: str = "grid.txt") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(text.encode("utf-8"))
    return path


def sealed() -> Grid:
    return Grid(("S#", "#E"), Cell(0, 0), Cell(1, 1))


# --------------------------------------------------------------------------- #
# Cell
# --------------------------------------------------------------------------- #
def test_a_cell_keeps_its_row_and_column():
    cell = Cell(3, 4)
    assert (cell.row, cell.column) == (3, 4)


def test_a_cell_prints_as_a_coordinate_pair():
    assert str(Cell(3, 4)) == "(3,4)"


def test_cells_order_by_row_then_column():
    assert sorted([Cell(1, 0), Cell(0, 2), Cell(0, 1)]) == [
        Cell(0, 1), Cell(0, 2), Cell(1, 0)]


def test_two_cells_with_the_same_coordinates_are_equal():
    assert Cell(1, 2) == Cell(1, 2) and hash(Cell(1, 2)) == hash(Cell(1, 2))


def test_cells_with_different_coordinates_are_not_equal():
    assert Cell(1, 2) != Cell(2, 1)


def test_a_cell_is_frozen():
    with pytest.raises(Exception):
        Cell(0, 0).row = 1                          # type: ignore[misc]


def test_a_negative_row_is_refused():
    with pytest.raises(PathError, match="a cell's row cannot be negative"):
        Cell(-1, 0)


def test_a_negative_column_is_refused():
    with pytest.raises(PathError, match="a cell's column cannot be negative"):
        Cell(0, -2)


def test_a_boolean_coordinate_is_refused():
    with pytest.raises(PathError, match="a cell's row must be an integer"):
        Cell(True, 0)


def test_a_text_coordinate_is_refused():
    with pytest.raises(PathError, match="a cell's row must be an integer"):
        Cell("0", 0)


def test_a_step_down_and_right_lands_on_the_new_cell():
    assert Cell(1, 1).step((1, 0)) == Cell(2, 1)


def test_a_step_off_the_top_edge_is_refused():
    with pytest.raises(PathError, match="leaves the grid"):
        Cell(0, 1).step((-1, 0))


def test_a_step_off_the_left_edge_is_refused():
    with pytest.raises(PathError, match="leaves the grid"):
        Cell(1, 0).step((0, -1))


# --------------------------------------------------------------------------- #
# Grid
# --------------------------------------------------------------------------- #
def test_a_grid_keeps_its_rows():
    grid = sealed()
    assert grid.rows == ("S#", "#E")


def test_a_grid_reports_its_height_and_width():
    assert (sealed().height, sealed().width) == (2, 2)


def test_a_cell_inside_the_grid_is_contained():
    assert Cell(1, 1) in sealed() and Cell(2, 0) not in sealed()


def test_a_negative_cell_is_not_contained():
    assert Cell(0, 0) in sealed()


def test_a_character_is_read_from_its_cell():
    assert sealed().character(Cell(0, 0)) == START
    assert sealed().character(Cell(0, 1)) == WALL


def test_a_character_outside_the_grid_is_refused():
    with pytest.raises(PathError, match=r"\(9,9\) is outside a 2x2 grid"):
        sealed().character(Cell(9, 9))


def test_a_wall_is_not_open():
    assert sealed().is_wall(Cell(0, 1)) and not sealed().is_open(Cell(0, 1))


def test_a_floor_cell_is_open():
    assert sealed().is_open(Cell(0, 0)) and not sealed().is_wall(Cell(0, 0))


def test_a_cell_outside_the_grid_is_not_open():
    assert not sealed().is_open(Cell(5, 5))


def test_the_walls_of_the_bundled_grid_are_pinned():
    assert bundled().walls == frozenset(cells(
        [(1, 0), (1, 2), (3, 0), (4, 1), (4, 3), (4, 4), (4, 5)]))


def test_the_open_cells_of_the_bundled_grid_number_twenty_nine():
    assert len(bundled().open_cells) == 29


def test_the_open_cells_exclude_every_wall():
    grid = bundled()
    assert not any(cell in grid.walls for cell in grid.open_cells)


def test_cells_enumerates_the_whole_rectangle():
    assert len(list(bundled().cells())) == 36


def test_cells_comes_back_in_reading_order():
    first = list(sealed().cells())[:3]
    assert first == [Cell(0, 0), Cell(0, 1), Cell(1, 0)]


def test_the_neighbours_of_the_start_are_pinned():
    assert bundled().neighbors(Cell(0, 0)) == (Cell(0, 1),)


def test_neighbours_follow_the_move_order_right_down_left_up():
    assert MOVES == ((0, 1), (1, 0), (0, -1), (-1, 0))
    assert bundled().neighbors(Cell(1, 1)) == (Cell(2, 1), Cell(0, 1))


def test_neighbours_never_include_a_wall():
    grid = bundled()
    assert all(not grid.is_wall(cell) for cell in grid.neighbors(Cell(1, 1)))


def test_the_neighbours_of_a_corner_never_leave_the_grid():
    assert bundled().neighbors(Cell(5, 5)) == (Cell(5, 4),)


def test_neighbours_of_a_cell_outside_the_grid_are_refused():
    with pytest.raises(PathError, match=r"\(9,9\) is outside the grid"):
        bundled().neighbors(Cell(9, 9))


def test_a_grid_prints_its_rows():
    assert str(sealed()) == "S#\n#E"


def test_render_with_no_arguments_shows_the_grid():
    assert bundled().render() == bundled().rows


def test_render_marks_a_path_with_stars_and_the_rest_of_the_search_with_os():
    assert bundled().render(cells(BFS_PATH), breadth_first(bundled()).expanded) == (
        "S*oooo",
        "#*#ooo",
        "o**ooo",
        "#o*ooo",
        ".#*###",
        "oo***E",
    )


def test_render_keeps_the_start_and_the_end_visible():
    rendered = bundled().render(breadth_first(bundled()).path)
    assert rendered[0][0] == START and rendered[5][5] == END


def test_a_grid_needs_two_rows():
    with pytest.raises(PathError, match="a grid needs at least two rows"):
        Grid(("S.E",), Cell(0, 0), Cell(0, 2))


def test_a_grid_needs_two_columns():
    with pytest.raises(PathError, match="a grid needs at least two columns"):
        Grid(("S", ".", "E"), Cell(0, 0), Cell(2, 0))


def test_a_ragged_grid_is_refused():
    with pytest.raises(PathError, match="every row of a grid must be the same"):
        Grid(("S..", ".E"), Cell(0, 0), Cell(1, 1))


def test_a_grid_row_with_an_unknown_character_is_refused():
    with pytest.raises(PathError, match="row 1 holds 'X'"):
        Grid(("SX", ".E"), Cell(0, 0), Cell(1, 1))


def test_the_start_and_the_end_cannot_be_one_cell():
    with pytest.raises(PathError, match="cannot be the same cell"):
        Grid(("S.", ".E"), Cell(0, 0), Cell(0, 0))


def test_the_end_must_be_inside_the_grid():
    with pytest.raises(PathError, match="must be inside the grid"):
        Grid(("S.", ".E"), Cell(0, 0), Cell(3, 3))


def test_the_start_must_be_inside_the_grid():
    with pytest.raises(PathError, match="must be inside the grid"):
        Grid(("S.", ".E"), Cell(9, 9), Cell(1, 1))


def test_the_start_cannot_be_a_wall():
    with pytest.raises(PathError, match="cannot be walls"):
        Grid(("#.", ".E"), Cell(0, 0), Cell(1, 1))


def test_a_grid_is_frozen():
    with pytest.raises(Exception):
        sealed().start = Cell(0, 1)                 # type: ignore[misc]


# --------------------------------------------------------------------------- #
# read_grid
# --------------------------------------------------------------------------- #
def test_read_grid_refuses_a_missing_file(tmp_path):
    with pytest.raises(PathError, match="grid file not found"):
        read_grid(tmp_path / "nope.txt")


def test_read_grid_reads_rows_and_finds_the_start_and_the_end(tmp_path):
    grid = read_grid(a_grid(tmp_path, "S.\n.E\n"))
    assert (grid.height, grid.width) == (2, 2)
    assert grid.start == Cell(0, 0) and grid.end == Cell(1, 1)


def test_read_grid_skips_semicolon_comments(tmp_path):
    grid = read_grid(a_grid(tmp_path, "; a note\nS.\n.E\n; another\n"))
    assert grid.height == 2


def test_read_grid_skips_slash_comments(tmp_path):
    assert read_grid(a_grid(tmp_path, "// a note\nS.\n.E\n")).height == 2


def test_read_grid_skips_blank_lines(tmp_path):
    assert read_grid(a_grid(tmp_path, "S.\n\n.E\n")).height == 2


def test_read_grid_does_not_treat_a_wall_row_as_a_comment(tmp_path):
    text = "#.\nS.\n.E\n"
    assert read_grid(a_grid(tmp_path, text)).rows[0] == "#."


def test_read_grid_refuses_a_ragged_row_and_names_the_line(tmp_path):
    with pytest.raises(PathError, match="grid.txt:2: the row is 2 wide, not 3"):
        read_grid(a_grid(tmp_path, "S..\n.E\n"))


def test_read_grid_refuses_a_grid_without_a_start(tmp_path):
    with pytest.raises(PathError, match="the grid needs one S and one E"):
        read_grid(a_grid(tmp_path, "..\n.E\n"))


def test_read_grid_refuses_a_grid_without_an_end(tmp_path):
    with pytest.raises(PathError, match="the grid needs one S and one E"):
        read_grid(a_grid(tmp_path, "S.\n..\n"))


def test_read_grid_refuses_a_second_start(tmp_path):
    with pytest.raises(PathError, match="grid.txt:3: a second start"):
        read_grid(a_grid(tmp_path, "S..\n...\nS.E\n"))


def test_read_grid_refuses_a_second_end(tmp_path):
    with pytest.raises(PathError, match="grid.txt:3: a second end"):
        read_grid(a_grid(tmp_path, "..E\nS..\n..E\n"))


def test_read_grid_refuses_a_file_with_no_rows(tmp_path):
    with pytest.raises(PathError, match="no grid rows"):
        read_grid(a_grid(tmp_path, ""))


def test_read_grid_refuses_a_file_of_comments_only(tmp_path):
    with pytest.raises(PathError, match="no grid rows"):
        read_grid(a_grid(tmp_path, "; nothing here\n"))


def test_read_grid_of_the_bundled_file_is_pinned():
    grid = read_grid()
    assert (grid.height, grid.width) == (6, 6)
    assert grid.start == Cell(0, 0) and grid.end == Cell(5, 5)


def test_the_bundled_grid_file_is_exactly_161_bytes():
    assert GRID_FILE.stat().st_size == 161


# --------------------------------------------------------------------------- #
# Outcome
# --------------------------------------------------------------------------- #
def test_an_outcome_reports_found_steps_and_expansions():
    outcome = Outcome("test", cells(BFS_PATH), cells([(0, 0)]))
    assert outcome.found and outcome.steps == 10 and outcome.expansions == 1


def test_a_one_cell_path_takes_no_steps():
    assert Outcome("test", cells([(0, 0)]), cells([(0, 0)])).steps == 0


def test_an_empty_path_takes_no_steps_and_found_is_false():
    outcome = Outcome("test", (), ())
    assert outcome.steps == 0 and not outcome.found


def test_an_empty_path_follows_edges_vacuously():
    assert Outcome("test", (), ()).follows_edges(bundled())


def test_a_real_path_follows_edges():
    assert breadth_first(bundled()).follows_edges(bundled())


def test_a_path_that_jumps_is_not_a_path():
    assert not Outcome("test", cells([(0, 0), (0, 5)]),
                       ()).follows_edges(bundled())


def test_a_path_through_a_wall_is_not_a_path():
    assert not Outcome("test", cells([(0, 0), (1, 0)]),
                       ()).follows_edges(bundled())


def test_a_path_outside_the_grid_is_not_a_path():
    assert not Outcome("test", cells([(0, 0), (9, 9)]),
                       ()).follows_edges(bundled())


def test_an_outcome_summary_holds_the_counts():
    assert breadth_first(bundled()).summary() == {
        "algorithm": "breadth", "found": True, "steps": 10, "expansions": 28,
        "path": [str(cell) for cell in cells(BFS_PATH)]}


def test_an_outcome_dict_adds_the_expanded_cells():
    payload = breadth_first(bundled()).to_dict()
    assert list(payload) == ["algorithm", "found", "steps", "expansions",
                             "path", "expanded"]
    assert payload["expanded"][0] == "(0,0)"


def test_an_outcome_is_frozen():
    with pytest.raises(Exception):
        breadth_first(bundled()).steps = 3           # type: ignore[misc]


def test_an_outcome_carries_no_clock_field():
    assert list(Outcome.__dataclass_fields__) == ["algorithm", "path",
                                                  "expanded"]


# --------------------------------------------------------------------------- #
# has_clock: the negative control for the audit's clock check
# --------------------------------------------------------------------------- #
def test_has_clock_is_false_for_an_outcome():
    assert not has_clock(breadth_first(bundled()))


def test_has_clock_is_true_for_the_legacy_field_name():
    @dataclass(frozen=True)
    class Timed:
        execution_time_ms: float = 0.0

    assert has_clock(Timed())


def test_has_clock_is_true_for_any_timer_spelling():
    @dataclass(frozen=True)
    class Timed:
        elapsed_ms: float = 0.0
        seconds: float = 0.0

    assert has_clock(Timed())


def test_has_clock_is_false_for_a_plain_object():
    assert not has_clock(object())


# --------------------------------------------------------------------------- #
# The five searches
# --------------------------------------------------------------------------- #
def test_breadth_first_steps_and_expansions_are_pinned():
    outcome = breadth_first(bundled())
    assert outcome.steps == 10 and outcome.expansions == 28


def test_breadth_first_takes_the_gap_on_row_two():
    assert breadth_first(bundled()).path == cells(BFS_PATH)


def test_depth_first_steps_and_expansions_are_pinned():
    outcome = depth_first(bundled())
    assert outcome.steps == 16 and outcome.expansions == 17


def test_depth_first_dives_along_the_top_edge():
    assert depth_first(bundled()).path[:6] == cells(
        [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)])


def test_dijkstra_returns_the_shortest_path():
    assert dijkstra(bundled()).steps == 10


def test_dijkstra_expands_exactly_what_breadth_first_expands():
    reference = breadth_first(bundled())
    found = dijkstra(bundled())
    assert found.path == reference.path
    assert found.expanded == reference.expanded


def test_astar_returns_the_shortest_path_with_fewer_expansions():
    outcome = astar(bundled())
    assert outcome.steps == 10 and outcome.expansions == 25
    assert outcome.expansions < dijkstra(bundled()).expansions


def test_astar_finds_the_same_path_as_breadth_first():
    assert astar(bundled()).path == cells(BFS_PATH)


def test_greedy_walks_six_steps_further_than_the_shortest_path():
    outcome = greedy(bundled())
    assert outcome.steps == 16
    assert outcome.steps - breadth_first(bundled()).steps == 6


def test_greedy_path_is_pinned():
    assert greedy(bundled()).path == cells(GREEDY_PATH)


def test_greedy_expands_fewer_cells_than_breadth_first():
    assert greedy(bundled()).expansions == 20
    assert greedy(bundled()).expansions < breadth_first(bundled()).expansions


def test_greedy_and_depth_first_are_longer_by_the_same_six_steps():
    shortest = breadth_first(bundled()).steps
    assert {name: ALGORITHMS[name](bundled()).steps - shortest
            for name in LONGER} == {"depth": 6, "greedy": 6}


def test_every_search_finds_a_path_on_the_bundled_grid():
    assert all(outcome.found for outcome in run_all(bundled()))


def test_every_search_follows_real_edges():
    grid = bundled()
    assert all(outcome.follows_edges(grid) for outcome in run_all(grid))


def test_every_search_starts_at_the_start_and_ends_at_the_end():
    grid = bundled()
    assert all(outcome.path[0] == grid.start and outcome.path[-1] == grid.end
               for outcome in run_all(grid))


def test_a_search_can_be_given_another_pair_of_cells():
    grid = bundled()
    assert breadth_first(grid, Cell(0, 0), Cell(0, 5)).steps == 5


def test_a_search_from_a_cell_outside_the_grid_is_refused():
    with pytest.raises(PathError, match="outside the grid"):
        breadth_first(bundled(), Cell(9, 9))


def test_the_sealed_grid_is_found_by_none_of_the_five():
    assert all(not outcome.found for outcome in run_all(sealed()))


def test_the_sealed_grid_still_costs_every_search_one_expansion():
    assert [outcome.expansions for outcome in run_all(sealed())] == [1] * 5


def test_a_failed_search_has_an_empty_path():
    assert breadth_first(sealed()).path == ()


def test_manhattan_counts_horizontal_and_vertical_steps():
    assert manhattan(Cell(0, 0), Cell(5, 5)) == 10
    assert manhattan(Cell(5, 5), Cell(0, 0)) == 10


def test_manhattan_of_a_cell_with_itself_is_zero():
    assert manhattan(Cell(2, 3), Cell(2, 3)) == 0


def test_the_five_searches_are_keyed_by_the_name_each_one_reports():
    assert list(ALGORITHMS) == ["breadth", "depth", "dijkstra", "astar",
                                "greedy"]
    assert set(ALGORITHMS) == {outcome.algorithm for outcome in
                               run_all(bundled())}


def test_the_three_optimal_names_and_the_two_longer_ones_are_pinned():
    assert OPTIMAL == ("breadth", "dijkstra", "astar")
    assert LONGER == ("depth", "greedy")


def test_run_all_runs_every_search_in_a_fixed_order():
    assert [outcome.algorithm for outcome in run_all(bundled())] == list(
        ALGORITHMS)


# --------------------------------------------------------------------------- #
# resolve
# --------------------------------------------------------------------------- #
def test_resolve_keeps_a_canonical_name():
    assert resolve("astar") == "astar"


def test_resolve_maps_the_short_aliases():
    assert ALIASES == {"bfs": "breadth", "dfs": "depth"}
    assert resolve("bfs") == "breadth" and resolve("dfs") == "depth"


def test_resolve_ignores_case_and_spaces():
    assert resolve("  BFS  ") == "breadth"


def test_resolve_refuses_an_unknown_name():
    with pytest.raises(PathError, match="no such algorithm: 'speed'"):
        resolve("speed")


def test_resolve_refuses_an_empty_name():
    with pytest.raises(PathError, match="no such algorithm: ''"):
        resolve("")


def test_resolve_refuses_a_name_that_is_not_text():
    with pytest.raises(PathError, match="must be text"):
        resolve(3)


# --------------------------------------------------------------------------- #
# The legacy clock
# --------------------------------------------------------------------------- #
def test_the_legacy_lines_are_pinned():
    assert LEGACY_FIELD == "execution_time_ms: float"
    assert LEGACY_TIMING == "elapsed_ms = (perf_counter() - started_at) * 1_000.0"
    assert LEGACY_FOUND == "found=bool(path)"


def test_legacy_times_returns_one_positive_measurement_per_run():
    times = legacy_times(bundled(), 6)
    assert len(times) == 6 and all(value > 0 for value in times)


def test_legacy_times_never_agree_with_itself():
    assert len(set(legacy_times(bundled(), 12))) > 1


def test_two_runs_of_astar_do_compare_equal():
    assert astar(bundled()) == astar(bundled())


def test_the_two_spreads_are_measured_in_microseconds():
    assert legacy_spread([180.0, 250.0]) == 70.0


def test_a_spread_of_one_measurement_is_zero():
    assert legacy_spread([5.0]) == 0.0


def test_a_spread_needs_a_measurement():
    with pytest.raises(PathError, match="a spread needs at least one"):
        legacy_spread([])


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_the_audit_holds_ten_named_checks():
    assert [name for name, _ in audit(bundled(), run_all(bundled()))] == [
        "every path starts at the start and ends at the end",
        "every step of every path is one move between open cells",
        "no path visits a cell twice",
        "every expanded cell is open and inside the grid",
        "no cell is expanded twice",
        "the goal is the last cell expanded, when it is found",
        "the three optimal searches return the shortest path",
        "breadth-first and dijkstra expand the same number of cells",
        "no result carries a wall-clock field",
        "two runs of every search agree exactly"]


def test_the_audit_passes_on_the_real_outcomes():
    assert problems(audit(bundled(), run_all(bundled()))) == []


def test_the_audit_catches_a_path_that_ends_elsewhere():
    grid = bundled()
    found = list(run_all(grid))
    found[0] = Outcome("breadth", tuple(reversed(found[0].path)),
                       found[0].expanded)
    assert "every path starts at the start and ends at the end" in \
        problems(audit(grid, found))


def test_the_audit_catches_a_path_that_jumps():
    grid = bundled()
    found = list(run_all(grid))
    found[1] = Outcome("depth", cells([(0, 0), (0, 5)]), found[1].expanded)
    assert "every step of every path is one move between open cells" in \
        problems(audit(grid, found))


def test_the_audit_catches_a_path_that_repeats_a_cell():
    grid = bundled()
    found = list(run_all(grid))
    doubled = found[2].path[:3] + found[2].path[1:2] + found[2].path[3:]
    found[2] = Outcome("dijkstra", doubled, found[2].expanded)
    assert problems(audit(grid, found)) != []
    assert any("one move between open cells" in name or "visits a cell twice"
               in name for name in problems(audit(grid, found)))


def test_the_audit_catches_an_expanded_cell_that_is_a_wall():
    grid = bundled()
    found = list(run_all(grid))
    found[3] = Outcome("astar", found[3].path,
                       found[3].expanded + (Cell(1, 0),))
    assert "every expanded cell is open and inside the grid" in \
        problems(audit(grid, found))


def test_the_audit_catches_an_expanded_cell_that_is_outside_the_grid():
    grid = bundled()
    found = list(run_all(grid))
    found[3] = Outcome("astar", found[3].path,
                       found[3].expanded + (Cell(9, 9),))
    assert "every expanded cell is open and inside the grid" in \
        problems(audit(grid, found))


def test_the_audit_catches_a_cell_expanded_twice():
    grid = bundled()
    found = list(run_all(grid))
    found[4] = Outcome("greedy", found[4].path,
                       found[4].expanded + found[4].expanded[-1:])
    assert "no cell is expanded twice" in problems(audit(grid, found))


def test_the_audit_catches_a_search_that_stops_before_the_goal():
    grid = bundled()
    found = list(run_all(grid))
    found[3] = Outcome("astar", found[3].path, found[3].expanded[:-1])
    assert "the goal is the last cell expanded, when it is found" in \
        problems(audit(grid, found))


def test_the_audit_catches_an_optimal_search_that_is_not_shortest():
    grid = bundled()
    found = list(run_all(grid))
    found[2] = Outcome("dijkstra", found[4].path, found[2].expanded)
    assert "the three optimal searches return the shortest path" in \
        problems(audit(grid, found))


def test_the_audit_catches_dijkstra_expanding_more_than_breadth_first():
    grid = bundled()
    found = list(run_all(grid))
    found[2] = Outcome("dijkstra", found[2].path, found[2].expanded[:-1])
    assert "breadth-first and dijkstra expand the same number of cells" in \
        problems(audit(grid, found))


def test_the_audit_catches_a_result_that_changes_between_runs():
    grid = bundled()
    found = list(run_all(grid))
    found[4] = Outcome("greedy", found[4].path, found[4].expanded[:-1])
    assert "two runs of every search agree exactly" in problems(audit(grid,
                                                                      found))


def test_the_audit_is_repeatable():
    grid = bundled()
    assert audit(grid, run_all(grid)) == audit(grid, run_all(grid))


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


def test_demo_shows_the_grid(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "  S....." in out and "  .....E" in out


def test_demo_shows_the_grid_shape(capsys):
    run_demo()
    assert "6x6, 7 walls, start (0,0), end (5,5), 29 open cells" in \
        capsys.readouterr().out


def test_demo_shows_the_five_row_table(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "  breadth       yes     10          28       yes" in out
    assert "  greedy        yes     16          20        no" in out


def test_demo_shows_both_paths(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "breadth-first, 10 steps:" in out and "greedy, 16 steps -- 6 longer" \
        in out


def test_demo_draws_the_greedy_path(capsys):
    run_demo()
    assert "    S*****" in capsys.readouterr().out


def test_demo_shows_the_sealed_grid(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "the same five on a 2x2 grid whose end is walled off:" in out
    assert "every one of them ran; the legacy found=bool(path) cannot say so" \
        in out


def test_demo_shows_the_clock_spread(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "the legacy field, execution_time_ms: float, over 40 identical runs:" \
        in out
    assert "the 40 numbers are not all the same: yes" in out
    assert "expansions instead: 25 both times" in out


def test_demo_shows_all_ten_checks(capsys):
    run_demo()
    assert "10/10 checks pass" in capsys.readouterr().out


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
    assert "data/grid.txt: 6x6, 7 walls, start (0,0), end (5,5)" in out
    assert "  algorithm   found  steps  expansions  shortest" in out
    assert "  dijkstra      yes     10          28       yes" in out


def test_cli_algorithm_prints_one_row(capsys):
    assert cli.main(["--algorithm", "greedy"]) == 0
    out = capsys.readouterr().out
    assert "greedy" in out and "dijkstra" not in out


def test_cli_accepts_the_short_alias(capsys):
    assert cli.main(["--algorithm", "dfs"]) == 0
    out = capsys.readouterr().out
    assert "depth" in out and "breadth" not in out


def test_cli_unknown_algorithm_exits_two(capsys):
    assert cli.main(["--algorithm", "speed"]) == 2
    assert "no such algorithm: 'speed'" in capsys.readouterr().err


def test_cli_render_draws_the_default_path(capsys):
    assert cli.main(["--render"]) == 0
    out = capsys.readouterr().out
    assert "breadth: 10 steps, 28 cells expanded" in out
    assert "    S*oooo" in out


def test_cli_render_takes_a_name(capsys):
    assert cli.main(["--render", "greedy"]) == 0
    out = capsys.readouterr().out
    assert "greedy: 16 steps, 20 cells expanded" in out
    assert "    S*****" in out


def test_cli_render_works_when_only_another_algorithm_ran(capsys):
    assert cli.main(["--algorithm", "greedy", "--render"]) == 0
    assert "breadth: 10 steps, 28 cells expanded" in capsys.readouterr().out


def test_cli_render_refuses_an_unknown_name(capsys):
    assert cli.main(["--render", "speed"]) == 2
    assert "no such algorithm: 'speed'" in capsys.readouterr().err


def test_cli_legacy_shows_the_spread(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "execution_time_ms: float, on 40 identical A* runs:" in out
    assert "but two runs still compare equal" in out


def test_cli_sealed_shows_five_failures(capsys):
    assert cli.main(["--sealed"]) == 0
    out = capsys.readouterr().out
    assert "a 2x2 grid whose end is walled off:" in out
    assert out.count("found nothing after 1 expansion(s)") == 5


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 10 and "FAIL" not in out


def test_cli_json_writes_the_outcomes(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["grid"]["height"] == 6 and payload["grid"]["width"] == 6
    assert len(payload["grid"]["walls"]) == 7
    assert [outcome["algorithm"] for outcome in payload["outcomes"]] == list(
        ALGORITHMS)
    assert payload["outcomes"][0]["steps"] == 10
    assert payload["clocks"] == [False] * 5


def test_cli_json_creates_directories(tmp_path, capsys):
    target = tmp_path / "a" / "b" / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    assert target.is_file()


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_missing_grid_exits_two(tmp_path, capsys):
    assert cli.main(["--grid", str(tmp_path / "nope.txt")]) == 2
    assert "grid file not found" in capsys.readouterr().err


def test_cli_a_ragged_grid_exits_two(tmp_path, capsys):
    path = a_grid(tmp_path, "S..\n.E\n")
    assert cli.main(["--grid", str(path)]) == 2
    assert "the row is 2 wide, not 3" in capsys.readouterr().err


def test_cli_reads_another_grid_file(tmp_path, capsys):
    path = a_grid(tmp_path, "S.\n.E\n")
    assert cli.main(["--grid", str(path)]) == 0
    out = capsys.readouterr().out
    assert "grid.txt: 2x2, 0 walls" in out
    assert "  breadth       yes      2           4       yes" in out
