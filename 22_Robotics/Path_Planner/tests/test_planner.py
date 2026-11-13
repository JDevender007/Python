"""Tests for the Path Planner project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from planner import (  # noqa: E402
    ALGORITHMS,
    DEMO_MAP,
    DIAGONAL_COST,
    HEURISTICS,
    GridMap,
    Plan,
    PlannerError,
    astar,
    bresenham,
    check_point,
    dijkstra,
    find_path,
    heuristic,
    line_of_sight,
    load_map,
    neighbours,
    parse_map,
    parse_point,
    path_cost,
    path_turns,
    render_map,
    render_report,
    route_cost,
    rrt,
    run_demo,
    smooth_path,
    step_allowed,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAP_FILE = PROJECT_ROOT / "data" / "map.txt"

OPEN_TEXT = "\n".join([
    "#####",
    "#S..#",
    "#...#",
    "#..G#",
    "#####",
])

CORNER_TEXT = "\n".join([
    "#####",
    "#S..#",
    "##..#",
    "#..G#",
    "#####",
])

STRAIGHT_TEXT = "\n".join([
    "#######",
    "#S...G#",
    "#######",
])

BLOCKED_TEXT = "\n".join([
    "#####",
    "#S#G#",
    "#####",
])


@pytest.fixture(scope="module")
def grid():
    return load_map(MAP_FILE)


@pytest.fixture()
def open_map():
    return parse_map(OPEN_TEXT)


@pytest.fixture()
def corner_map():
    return parse_map(CORNER_TEXT)


# --------------------------------------------------------------------------- #
# Map parsing
# --------------------------------------------------------------------------- #
def test_parse_map_sets_start_and_goal():
    parsed = parse_map(OPEN_TEXT)
    assert parsed.start == (1, 1)
    assert parsed.goal == (3, 3)
    assert parsed.cells[1] == "#...#"


def test_parse_map_replaces_markers_with_free_cells():
    parsed = parse_map(OPEN_TEXT)
    assert parsed.cells[1][1] == "."
    assert parsed.cells[3][3] == "."


def test_parse_map_ignores_blank_lines():
    parsed = parse_map("\n".join(["", OPEN_TEXT, "", ""]))
    assert parsed.rows == 5


def test_parse_map_rejects_empty_text():
    with pytest.raises(PlannerError, match="map is empty"):
        parse_map("   \n \n")


def test_parse_map_rejects_ragged_rows():
    with pytest.raises(PlannerError, match="row 1 has 4 column"):
        parse_map("#S#\n#..G\n####")


def test_parse_map_rejects_unknown_symbols():
    with pytest.raises(PlannerError, match="unknown map symbol"):
        parse_map("#S?G#")


def test_parse_map_requires_a_start():
    with pytest.raises(PlannerError, match="exactly one start"):
        parse_map("#####\n#..G#\n#####")


def test_parse_map_rejects_two_starts():
    with pytest.raises(PlannerError, match="exactly one start"):
        parse_map("#####\n#SSG#\n#####")


def test_parse_map_requires_a_goal():
    with pytest.raises(PlannerError, match="exactly one goal"):
        parse_map("#####\n#S..#\n#####")


def test_parse_map_rejects_two_goals():
    with pytest.raises(PlannerError, match="exactly one goal"):
        parse_map("#####\n#SGG#\n#####")


def test_load_map_bundled(grid):
    assert grid.rows == 15
    assert grid.cols == 21
    assert grid.start == (1, 1)
    assert grid.goal == (13, 19)


def test_load_map_missing_file(tmp_path):
    with pytest.raises(PlannerError, match="map file not found"):
        load_map(tmp_path / "ghost.txt")


def test_parse_point_valid():
    assert parse_point(" 2, 3 ") == (2, 3)


def test_parse_point_wrong_count():
    with pytest.raises(PlannerError, match="point must be"):
        parse_point("2")


def test_parse_point_non_integer():
    with pytest.raises(PlannerError, match="must be integers"):
        parse_point("2.5,3")


def test_check_point_valid(open_map):
    assert check_point(open_map, (1, 2), "start") == (1, 2)


def test_check_point_out_of_bounds(open_map):
    with pytest.raises(PlannerError, match="outside the 5x5 grid"):
        check_point(open_map, (9, 9), "goal")


def test_check_point_on_a_wall(open_map):
    with pytest.raises(PlannerError, match="is a wall"):
        check_point(open_map, (0, 0), "start")


def test_check_point_rejects_bad_type(open_map):
    with pytest.raises(PlannerError, match="pair of integers"):
        check_point(open_map, (1.5, 2), "start")


# --------------------------------------------------------------------------- #
# Grid queries
# --------------------------------------------------------------------------- #
def test_grid_bounds(open_map):
    assert open_map.in_bounds((0, 0)) is True
    assert open_map.in_bounds((-1, 0)) is False
    assert open_map.in_bounds((5, 0)) is False


def test_grid_wall_queries(open_map):
    assert open_map.is_wall((0, 0)) is True
    assert open_map.is_free((0, 0)) is False
    assert open_map.is_free((1, 1)) is True
    assert open_map.is_free((99, 99)) is False


def test_grid_free_cells(open_map):
    assert open_map.free_cells() == 9


def test_grid_to_dict(open_map):
    payload = open_map.to_dict()
    assert payload == {"name": "map", "rows": 5, "cols": 5,
                       "start": [1, 1], "goal": [3, 3], "free_cells": 9}


# --------------------------------------------------------------------------- #
# Movement
# --------------------------------------------------------------------------- #
def test_neighbours_orthogonal_only(open_map):
    found = neighbours(open_map, (2, 2), diagonal=False)
    assert [point for point, _ in found] == [(1, 2), (2, 3), (3, 2),
                                             (2, 1)]


def test_neighbours_include_diagonals(open_map):
    found = neighbours(open_map, (2, 2), diagonal=True)
    assert len(found) == 8
    assert all(cost in (1.0, DIAGONAL_COST) for _, cost in found)


def test_neighbours_skip_walls(open_map):
    found = [point for point, _ in neighbours(open_map, (1, 2))]
    assert (0, 2) not in found
    assert (1, 3) in found


def test_neighbours_block_corner_cutting(corner_map):
    found = [point for point, _ in neighbours(corner_map, (1, 1))]
    assert (2, 2) not in found


def test_neighbours_allow_corner_cutting(corner_map):
    found = [point for point, _ in neighbours(corner_map, (1, 1),
                                              allow_corner_cutting=True)]
    assert (2, 2) in found


def test_step_allowed_adjacent(open_map):
    assert step_allowed(open_map, (1, 1), (1, 2)) is True


def test_step_allowed_rejects_a_jump(open_map):
    assert step_allowed(open_map, (1, 1), (3, 3)) is False


def test_step_allowed_rejects_walls(open_map):
    assert step_allowed(open_map, (1, 1), (0, 1)) is False


def test_step_allowed_corner_rule(corner_map):
    assert step_allowed(corner_map, (1, 1), (2, 2)) is False
    assert step_allowed(corner_map, (1, 1), (2, 2),
                        allow_corner_cutting=True) is True


def test_bresenham_horizontal():
    assert bresenham((2, 1), (2, 4)) == [(2, 1), (2, 2), (2, 3), (2, 4)]


def test_bresenham_diagonal():
    cells = bresenham((1, 1), (4, 4))
    assert cells[0] == (1, 1) and cells[-1] == (4, 4)
    assert len(cells) == 4


def test_bresenham_reverse_is_the_same_set():
    forward = bresenham((1, 2), (4, 5))
    backward = bresenham((4, 5), (1, 2))
    assert set(forward) == set(backward)


def test_line_of_sight_open_room(open_map):
    assert line_of_sight(open_map, (1, 1), (3, 3)) is True


def test_line_of_sight_blocked_by_wall(corner_map):
    assert line_of_sight(corner_map, (1, 1), (3, 1)) is False


def test_line_of_sight_corner_rule(corner_map):
    assert line_of_sight(corner_map, (1, 1), (2, 2)) is False
    assert line_of_sight(corner_map, (1, 1), (2, 2),
                         allow_corner_cutting=True) is True


# --------------------------------------------------------------------------- #
# Costs and metrics
# --------------------------------------------------------------------------- #
def test_path_cost_straight():
    assert path_cost([(0, 0), (0, 1), (0, 2)]) == pytest.approx(2.0)


def test_path_cost_diagonal():
    assert path_cost([(0, 0), (1, 1)]) == pytest.approx(DIAGONAL_COST)


def test_path_cost_single_cell():
    assert path_cost([(0, 0)]) == 0.0


def test_path_cost_rejects_a_gap():
    with pytest.raises(PlannerError, match="not contiguous"):
        path_cost([(0, 0), (2, 2)])


def test_route_cost_straight_leg():
    assert route_cost([(0, 0), (0, 5)]) == pytest.approx(5.0)


def test_route_cost_diagonal_leg():
    assert route_cost([(0, 0), (3, 3)]) == pytest.approx(3 * DIAGONAL_COST)


def test_route_cost_mixed_leg():
    assert route_cost([(0, 0), (2, 5)]) == pytest.approx(
        2 * DIAGONAL_COST + 3)


def test_route_cost_rejects_diagonal_when_disabled():
    with pytest.raises(PlannerError, match="needs a diagonal step"):
        route_cost([(0, 0), (1, 1)], diagonal=False)


def test_route_cost_empty():
    assert route_cost([]) == 0.0


def test_path_turns_straight():
    assert path_turns([(0, 0), (0, 1), (0, 2)]) == 0


def test_path_turns_counts_changes():
    assert path_turns([(0, 0), (0, 1), (1, 1)]) == 1


def test_path_turns_short_path():
    assert path_turns([(0, 0)]) == 0


def test_heuristic_zero():
    assert heuristic("zero", (0, 0), (4, 7)) == 0.0


def test_heuristic_manhattan():
    assert heuristic("manhattan", (0, 0), (4, 7)) == 11.0


def test_heuristic_euclidean():
    assert heuristic("euclidean", (0, 0), (3, 4)) == pytest.approx(5.0)


def test_heuristic_octile():
    assert heuristic("octile", (0, 0), (4, 7)) == pytest.approx(
        7 + (DIAGONAL_COST - 1.0) * 4)


def test_heuristic_rejects_unknown():
    with pytest.raises(PlannerError, match="unknown heuristic"):
        heuristic("chebyshev", (0, 0), (1, 1))


# --------------------------------------------------------------------------- #
# A*
# --------------------------------------------------------------------------- #
def test_astar_finds_the_straight_path():
    plan = astar(parse_map(STRAIGHT_TEXT))
    assert plan.path[0] == (1, 1) and plan.path[-1] == (1, 5)
    assert plan.cost == pytest.approx(4.0)
    assert plan.expanded > 0


def test_astar_path_is_legal(open_map):
    plan = astar(open_map)
    assert plan.path[0] == open_map.start
    assert plan.path[-1] == open_map.goal
    for point in plan.path:
        assert open_map.is_free(point)
    for start, end in zip(plan.path, plan.path[1:]):
        assert step_allowed(open_map, start, end)


def test_astar_same_start_and_goal(open_map):
    plan = astar(open_map, start=(1, 1), goal=(1, 1))
    assert plan.path == ((1, 1),)
    assert plan.cost == 0.0


def test_astar_uses_the_cheapest_legal_route(corner_map):
    assert astar(corner_map).cost == pytest.approx(2.0 + DIAGONAL_COST)


def test_astar_corner_cutting_shortens(corner_map):
    plan = astar(corner_map, allow_corner_cutting=True)
    assert plan.cost == pytest.approx(2 * DIAGONAL_COST)


def test_astar_orthogonal_is_longer(open_map):
    diagonal = astar(open_map).cost
    orthogonal = astar(open_map, diagonal=False).cost
    assert orthogonal == pytest.approx(4.0)
    assert orthogonal > diagonal


def test_astar_reports_no_path():
    with pytest.raises(PlannerError, match="no path"):
        astar(parse_map(BLOCKED_TEXT))


def test_astar_start_on_a_wall(open_map):
    with pytest.raises(PlannerError, match="start .* is a wall"):
        astar(open_map, start=(0, 0))


def test_astar_goal_out_of_bounds(open_map):
    with pytest.raises(PlannerError, match="outside the 5x5 grid"):
        astar(open_map, goal=(9, 9))


def test_astar_rejects_unknown_heuristic(open_map):
    with pytest.raises(PlannerError, match="unknown heuristic"):
        astar(open_map, heuristic_name="chebyshev")


def test_astar_zero_heuristic_matches_dijkstra(open_map):
    zero = astar(open_map, heuristic_name="zero")
    uniform = dijkstra(open_map)
    assert zero.cost == pytest.approx(uniform.cost)


def test_astar_heuristic_field(open_map):
    assert astar(open_map).heuristic == "octile"
    assert astar(open_map, diagonal=False).heuristic == "manhattan"


# --------------------------------------------------------------------------- #
# Dijkstra
# --------------------------------------------------------------------------- #
def test_dijkstra_optimal_on_bundled_map(grid):
    assert dijkstra(grid).cost == pytest.approx(astar(grid).cost)


def test_dijkstra_label(open_map):
    assert dijkstra(open_map).algorithm == "dijkstra"


def test_dijkstra_expands_at_least_as_many(grid):
    assert dijkstra(grid).expanded >= astar(grid).expanded


def test_dijkstra_path_is_legal(open_map):
    plan = dijkstra(open_map)
    assert path_cost(plan.path) == pytest.approx(plan.cost)


# --------------------------------------------------------------------------- #
# RRT
# --------------------------------------------------------------------------- #
def test_rrt_finds_a_path(grid):
    plan = rrt(grid, seed=7)
    assert plan.algorithm == "rrt"
    assert plan.path[0] == grid.start and plan.path[-1] == grid.goal


def test_rrt_path_is_contiguous(grid):
    plan = rrt(grid, seed=7)
    for start, end in zip(plan.path, plan.path[1:]):
        assert step_allowed(grid, start, end)


def test_rrt_is_deterministic(grid):
    first = rrt(grid, seed=11)
    second = rrt(grid, seed=11)
    assert first.path == second.path
    assert first.cost == pytest.approx(second.cost)


def test_rrt_same_start_and_goal(open_map):
    plan = rrt(open_map, start=(1, 1), goal=(1, 1))
    assert plan.path == ((1, 1),)


def test_rrt_rejects_bad_step(open_map):
    with pytest.raises(PlannerError, match="step must be an integer"):
        rrt(open_map, step=0)


def test_rrt_rejects_bad_iteration_budget(open_map):
    with pytest.raises(PlannerError, match="max_iters must be >= 1"):
        rrt(open_map, max_iters=0)


def test_rrt_rejects_bad_goal_bias(open_map):
    with pytest.raises(PlannerError, match="goal_bias must be in 0..1"):
        rrt(open_map, goal_bias=1.5)


def test_rrt_reports_failure():
    with pytest.raises(PlannerError, match="did not reach"):
        rrt(parse_map(BLOCKED_TEXT), max_iters=20)


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
def test_find_path_rejects_unknown_algorithm(open_map):
    with pytest.raises(PlannerError, match="unknown algorithm"):
        find_path(open_map, algorithm="bfs")


def test_find_path_dispatches_each_algorithm(open_map):
    assert find_path(open_map, "astar").algorithm == "astar"
    assert find_path(open_map, "dijkstra").algorithm == "dijkstra"
    assert find_path(open_map, "rrt", seed=3).algorithm == "rrt"


# --------------------------------------------------------------------------- #
# Smoothing
# --------------------------------------------------------------------------- #
def test_smooth_path_shortcuts_a_straight_run():
    plan = astar(parse_map(STRAIGHT_TEXT))
    smoothed = smooth_path(parse_map(STRAIGHT_TEXT), plan.path)
    assert smoothed == ((1, 1), (1, 5))
    assert route_cost(smoothed) == pytest.approx(plan.cost)


def test_smooth_path_keeps_the_endpoints(grid):
    plan = dijkstra(grid)
    smoothed = smooth_path(grid, plan.path)
    assert smoothed[0] == plan.path[0]
    assert smoothed[-1] == plan.path[-1]


def test_smooth_path_is_legal(grid):
    smoothed = smooth_path(grid, dijkstra(grid).path)
    for start, end in zip(smoothed, smoothed[1:]):
        assert line_of_sight(grid, start, end)


def test_smooth_path_never_lengthens(grid):
    plan = dijkstra(grid)
    assert route_cost(smooth_path(grid, plan.path)) <= plan.cost + 1e-9


def test_smooth_path_leaves_short_paths_alone(open_map):
    assert smooth_path(open_map, [(1, 1), (1, 2)]) == ((1, 1), (1, 2))


def test_smooth_path_rejects_wall_cells(open_map):
    with pytest.raises(PlannerError, match="crosses a wall"):
        smooth_path(open_map, [(1, 1), (0, 0), (1, 1)])


def test_smooth_path_rejects_gaps(open_map):
    with pytest.raises(PlannerError, match="not contiguous"):
        smooth_path(open_map, [(1, 1), (3, 3), (1, 1)])


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_render_map_marks_start_and_goal(open_map):
    drawing = render_map(open_map)
    assert "S" in drawing and "G" in drawing
    assert "o" not in drawing
    assert len(drawing.splitlines()) == 5


def test_render_map_draws_a_connected_route(grid):
    plan = astar(grid)
    drawing = render_map(grid, plan.path)
    assert drawing.count("o") >= plan.length - 2
    assert "S" in drawing and "G" in drawing


def test_render_report_contains_metrics(open_map):
    text = render_report(astar(open_map))
    for needle in ("PLAN", "start", "goal", "steps", "cost", "turns",
                   "expanded"):
        assert needle in text


def test_plan_to_dict(open_map):
    payload = astar(open_map).to_dict()
    assert payload["algorithm"] == "astar"
    assert payload["path"][0] == [1, 1]
    assert payload["steps"] == len(payload["path"]) - 1


def test_plan_euclidean_length(open_map):
    plan = astar(open_map)
    assert plan.euclidean_length == pytest.approx(
        math.hypot(2, 2), abs=1e-9)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    assert capsys.readouterr().out == first


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_requires_a_mode():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_astar(capsys):
    assert main(["--map", str(MAP_FILE)]) == 0
    out = capsys.readouterr().out
    assert "PLAN - astar" in out
    assert "(13, 19)" in out


def test_cli_dijkstra_with_smoothing(capsys):
    assert main(["--map", str(MAP_FILE), "--algorithm", "dijkstra",
                 "--smooth"]) == 0
    out = capsys.readouterr().out
    assert "dijkstra+smooth" in out
    assert "waypoints" not in out


def test_cli_rrt(capsys):
    assert main(["--map", str(MAP_FILE), "--algorithm", "rrt",
                 "--seed", "21"]) == 0
    assert "PLAN - rrt" in capsys.readouterr().out


def test_cli_override_start_and_goal(open_map, tmp_path, capsys):
    path = tmp_path / "open.txt"
    path.write_text(OPEN_TEXT, encoding="utf-8")
    assert main(["--map", str(path), "--start", "1,2",
                 "--goal", "3,2"]) == 0
    out = capsys.readouterr().out
    assert "start     : (1, 2)" in out
    assert "goal      : (3, 2)" in out


def test_cli_bad_start(capsys):
    assert main(["--map", str(MAP_FILE), "--start", "one"]) == 2
    assert "point must be" in capsys.readouterr().err


def test_cli_start_out_of_bounds(capsys):
    assert main(["--map", str(MAP_FILE), "--start", "99,99"]) == 2
    assert "outside the" in capsys.readouterr().err


def test_cli_rrt_rejects_orthogonal_mode(capsys):
    assert main(["--map", str(MAP_FILE), "--algorithm", "rrt",
                 "--no-diagonal"]) == 2
    assert "8-connected" in capsys.readouterr().err


def test_cli_rrt_rejects_bad_step(capsys):
    assert main(["--map", str(MAP_FILE), "--algorithm", "rrt",
                 "--step", "0"]) == 2
    assert "step must be >= 1" in capsys.readouterr().err


def test_cli_rrt_rejects_bad_budget(capsys):
    assert main(["--map", str(MAP_FILE), "--algorithm", "rrt",
                 "--max-iters", "0"]) == 2
    assert "max_iters must be >= 1" in capsys.readouterr().err


def test_cli_json_export(tmp_path):
    out = tmp_path / "plan.json"
    assert main(["--map", str(MAP_FILE), "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["map"]["rows"] == 15
    assert payload["plan"]["algorithm"] == "astar"
    assert len(payload["plan"]["path"]) > 10


def test_cli_missing_map(tmp_path, capsys):
    assert main(["--map", str(tmp_path / "ghost.txt")]) == 2
    assert "map file not found" in capsys.readouterr().err


def test_cli_no_path(tmp_path, capsys):
    path = tmp_path / "blocked.txt"
    path.write_text(BLOCKED_TEXT, encoding="utf-8")
    assert main(["--map", str(path)]) == 2
    assert "no path" in capsys.readouterr().err


def test_cli_quiet(tmp_path, capsys):
    out = tmp_path / "plan.json"
    assert main(["--map", str(MAP_FILE), "--json", str(out),
                 "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_bundled_constants():
    assert DEMO_MAP.is_file()
    assert ALGORITHMS == ("astar", "dijkstra", "rrt")
    assert set(HEURISTICS) == {"octile", "manhattan", "euclidean", "zero"}


def test_plan_dataclass_defaults():
    plan = Plan("astar", ((0, 0),), 0.0, 1)
    assert plan.heuristic == "-"
    assert plan.length == 1
