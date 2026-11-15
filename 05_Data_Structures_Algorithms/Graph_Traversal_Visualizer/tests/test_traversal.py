"""Tests for Graph_Traversal_Visualizer: an algorithm's step budget is part of
its interface, and when you mark a node decides the order."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
from traversal import (                                       # noqa: E402
    FIXED_PUSH,
    GRAPH,
    LEGACY_ENTRY,
    LEGACY_RECURSION,
    NAIVE_PUSH,
    Graph,
    GraphError,
    Traversal,
    Visit,
    audit,
    audit_orders,
    breadth_first,
    chain,
    component_of,
    components,
    depth_first,
    depth_first_naive,
    edge_pairs,
    legacy_recursive_dfs,
    problems,
    read_graph,
    recursion_limit,
    run_demo,
)

BFS_ORDER = ("A", "B", "C", "D", "F", "E")
DFS_ORDER = ("A", "B", "D", "C", "F", "E")
NAIVE_ORDER = ("A", "C", "F", "D", "E", "B")


def a_graph(folder: Path, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "graph.txt"
    path.write_bytes(text.encode("utf-8"))
    return path


def bundled() -> Graph:
    return read_graph()


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #
def test_an_empty_graph_has_no_nodes():
    assert Graph().nodes == () and len(Graph()) == 0


def test_adding_a_node_keeps_it():
    graph = Graph()
    graph.add_node("A")
    assert graph.nodes == ("A",) and "A" in graph


def test_a_node_name_is_stripped():
    graph = Graph()
    graph.add_node("  A  ")
    assert graph.nodes == ("A",)


def test_a_blank_node_name_is_refused():
    with pytest.raises(GraphError, match="a node name must be a non-empty"):
        Graph().add_node("   ")


def test_a_non_text_node_name_is_refused():
    with pytest.raises(GraphError, match="a node name must be a non-empty"):
        Graph().add_node(5)


def test_an_edge_is_undirected():
    graph = Graph()
    graph.add_edge("A", "B")
    assert graph.neighbors("A") == ("B",) and graph.neighbors("B") == ("A",)


def test_an_edge_creates_both_of_its_nodes():
    graph = Graph()
    graph.add_edge("A", "B")
    assert graph.nodes == ("A", "B")


def test_an_edge_from_a_node_to_itself_is_refused():
    with pytest.raises(GraphError, match="is not a link between two nodes"):
        Graph().add_edge("A", "A")


def test_an_edge_whose_sides_differ_only_by_spaces_is_refused():
    with pytest.raises(GraphError, match="is not a link between two nodes"):
        Graph().add_edge("A ", " A")


def test_an_edge_with_an_empty_side_is_refused():
    with pytest.raises(GraphError, match="a node name must be a non-empty"):
        Graph().add_edge("A", " ")


def test_a_duplicate_edge_is_stored_once():
    graph = Graph()
    graph.add_edge("A", "B")
    graph.add_edge("B", "A")
    assert graph.edge_count == 1


def test_neighbours_come_back_sorted():
    graph = Graph([("A", "C"), ("A", "B")])
    assert graph.neighbors("A") == ("B", "C")


def test_nodes_come_back_sorted():
    graph = Graph([("Z", "A"), ("M", "A")])
    assert graph.nodes == ("A", "M", "Z")


def test_the_neighbours_of_an_unknown_node_are_refused():
    with pytest.raises(GraphError, match="no such node"):
        Graph().neighbors("A")


def test_degree_counts_neighbours():
    graph = Graph([("A", "B"), ("A", "C")])
    assert graph.degree("A") == 2 and graph.degree("B") == 1


def test_the_edge_count_of_the_bundled_graph_is_seven():
    assert bundled().edge_count == 7


def test_the_bundled_graph_has_eight_nodes():
    assert bundled().nodes == ("A", "B", "C", "D", "E", "F", "G", "H")


def test_a_graph_iterates_its_nodes_in_order():
    assert list(bundled()) == list(bundled().nodes)


def test_a_graph_prints_its_degrees():
    assert str(bundled()) == ("A:2, B:2, C:3, D:3, E:1, F:1, G:1, H:1")


# --------------------------------------------------------------------------- #
# Visit and Traversal
# --------------------------------------------------------------------------- #
def test_a_visit_keeps_its_node_order_and_distance():
    visit = Visit("A", 1, 0)
    assert (visit.node, visit.order, visit.distance) == ("A", 1, 0)


def test_a_visit_cannot_be_order_zero():
    with pytest.raises(GraphError, match="the first visit is order 1"):
        Visit("A", 0, 0)


def test_a_visit_cannot_have_a_negative_distance():
    with pytest.raises(GraphError, match="a distance is never negative"):
        Visit("A", 1, -1)


def test_a_visit_is_frozen():
    visit = Visit("A", 1, 0)
    with pytest.raises(Exception):
        visit.order = 2                             # type: ignore[misc]


def test_a_traversal_needs_at_least_one_visit():
    with pytest.raises(GraphError, match="visits at least its start node"):
        Traversal("breadth", "A", ())


def test_a_traversal_reports_its_order():
    assert breadth_first(bundled(), "A").order == BFS_ORDER


def test_a_traversal_reports_its_distances():
    assert breadth_first(bundled(), "A").distances == (0, 1, 1, 2, 2, 3)


def test_a_traversal_reports_its_depth():
    assert breadth_first(bundled(), "A").depth == 3


def test_a_traversal_is_iterable_and_sized():
    traversal = breadth_first(bundled(), "A")
    assert len(traversal) == 6 and list(traversal) == list(BFS_ORDER)


def test_a_traversal_summary_holds_the_order():
    assert breadth_first(bundled(), "A").summary() == {
        "kind": "breadth", "start": "A", "visited": 6,
        "order": list(BFS_ORDER), "distances": [0, 1, 1, 2, 2, 3]}


def test_a_traversal_dict_holds_the_parents():
    parent = breadth_first(bundled(), "A").to_dict()["parent"]
    assert parent == {"A": None, "B": "A", "C": "A", "D": "B", "F": "C",
                      "E": "D"}


def test_a_traversal_is_frozen():
    traversal = breadth_first(bundled(), "A")
    with pytest.raises(Exception):
        traversal.start = "B"                       # type: ignore[misc]


# --------------------------------------------------------------------------- #
# breadth_first
# --------------------------------------------------------------------------- #
def test_breadth_first_order_is_pinned():
    assert breadth_first(bundled(), "A").order == BFS_ORDER


def test_breadth_first_distances_are_pinned():
    assert breadth_first(bundled(), "A").distances == (0, 1, 1, 2, 2, 3)


def test_breadth_first_distances_never_decrease():
    distances = breadth_first(bundled(), "A").distances
    assert all(a <= b for a, b in zip(distances, distances[1:]))


def test_breadth_first_reaches_only_its_component():
    traversal = breadth_first(bundled(), "G")
    assert traversal.order == ("G", "H")


def test_breadth_first_of_a_single_node_visits_it():
    graph = Graph()
    graph.add_node("A")
    result = breadth_first(graph, "A")
    assert result.order == ("A",) and result.distances == (0,)


def test_breadth_first_takes_the_shortest_path_to_every_node():
    graph = bundled()
    traversal = breadth_first(graph, "A")
    for node in ("D", "F", "E"):
        assert traversal.distances[traversal.order.index(node)] == 2 or node == "E"


def test_breadth_first_path_to_the_start_is_itself():
    assert breadth_first(bundled(), "A").path_to("A") == ("A",)


def test_breadth_first_path_to_f_is_two_hops():
    assert breadth_first(bundled(), "A").path_to("F") == ("A", "C", "F")


def test_breadth_first_refuses_an_unknown_start():
    with pytest.raises(GraphError, match="no such node: 'Z'"):
        breadth_first(bundled(), "Z")


def test_breadth_first_refuses_a_blank_start():
    with pytest.raises(GraphError, match="a start node must be a non-empty"):
        breadth_first(bundled(), "  ")


def test_breadth_first_refuses_a_non_text_start():
    with pytest.raises(GraphError, match="a start node must be a non-empty"):
        breadth_first(bundled(), 1)


# --------------------------------------------------------------------------- #
# depth_first: the faithful rewrite, and the naive one
# --------------------------------------------------------------------------- #
def test_depth_first_order_is_pinned():
    assert depth_first(bundled(), "A").order == DFS_ORDER


def test_depth_first_distances_are_pinned():
    assert depth_first(bundled(), "A").distances == (0, 1, 2, 3, 4, 3)


def test_depth_first_reproduces_recursion_exactly():
    graph = bundled()
    assert depth_first(graph, "A").order == legacy_recursive_dfs(graph,
                                                                "A").order


def test_depth_first_reproduces_recursion_distances_too():
    graph = bundled()
    assert depth_first(graph, "A").distances == \
        legacy_recursive_dfs(graph, "A").distances


def test_the_naive_stack_order_is_pinned():
    assert depth_first_naive(bundled(), "A").order == NAIVE_ORDER


def test_the_naive_stack_visits_the_same_set():
    core = depth_first_naive(bundled(), "A")
    assert set(core.order) == set(depth_first(bundled(), "A").order)


def test_the_naive_stack_order_differs_from_recursion():
    assert depth_first_naive(bundled(), "A").order != DFS_ORDER


def test_the_naive_stack_reaches_f_in_two_hops():
    assert depth_first_naive(bundled(), "A").path_to("F") == ("A", "C", "F")


def test_depth_first_reaches_f_the_long_way():
    assert depth_first(bundled(), "A").path_to("F") == ("A", "B", "D", "C",
                                                        "F")


def test_depth_first_distances_drop_where_a_branch_ends():
    distances = depth_first(bundled(), "A").distances
    assert any(b < a for a, b in zip(distances, distances[1:]))


def test_depth_first_of_a_chain_is_a_straight_walk():
    result = depth_first(chain(5), "n0")
    assert result.order == ("n0", "n1", "n2", "n3", "n4")
    assert result.distances == (0, 1, 2, 3, 4)


def test_depth_first_survives_a_1500_node_chain():
    assert len(depth_first(chain(1500), "n0")) == 1500


def test_depth_first_depth_of_a_1500_node_chain_is_1499():
    assert depth_first(chain(1500), "n0").depth == 1499


def test_the_naive_stack_also_survives_a_1500_node_chain():
    assert len(depth_first_naive(chain(1500), "n0")) == 1500


def test_depth_first_refuses_an_unknown_start():
    with pytest.raises(GraphError, match="no such node"):
        depth_first(bundled(), "Q")


# --------------------------------------------------------------------------- #
# legacy_recursive_dfs: the budget nobody wrote down
# --------------------------------------------------------------------------- #
def test_the_legacy_lines_are_pinned():
    assert LEGACY_RECURSION == "yield from walk(neighbor)"
    assert LEGACY_ENTRY == "yield from walk(start_node)"


def test_the_naive_and_fixed_push_lines_are_pinned():
    assert NAIVE_PUSH == "stack.extend(graph.neighbors(current))"
    assert FIXED_PUSH == \
        "stack.extend(reversed(graph.neighbors(current)))"


def test_the_recursion_limit_is_the_interpreter_default():
    assert recursion_limit() == sys.getrecursionlimit()


def test_the_recursive_walk_survives_a_short_chain():
    assert len(legacy_recursive_dfs(chain(200), "n0")) == 200


def test_the_recursive_walk_raises_past_the_limit():
    with pytest.raises(RecursionError):
        legacy_recursive_dfs(chain(recursion_limit() + 500), "n0")


def test_the_iterative_walk_does_not_raise_on_the_same_chain():
    deep = chain(recursion_limit() + 500)
    assert len(depth_first(deep, "n0")) == len(deep)


def test_the_recursive_walk_refuses_an_unknown_start():
    with pytest.raises(GraphError, match="no such node"):
        legacy_recursive_dfs(bundled(), "Q")


def test_the_recursive_walk_is_named_recursive():
    assert legacy_recursive_dfs(bundled(), "A").kind == "recursive"


# --------------------------------------------------------------------------- #
# components, component_of, edge_pairs
# --------------------------------------------------------------------------- #
def test_the_bundled_graph_has_two_components():
    assert components(bundled()) == (BFS_ORDER, ("G", "H"))


def test_components_of_an_empty_graph_is_empty():
    assert components(Graph()) == ()


def test_components_of_an_isolated_node_is_a_single_node():
    graph = Graph()
    graph.add_node("Z")
    assert components(graph) == (("Z",),)


def test_component_of_agrees_with_the_traversal_set():
    graph = bundled()
    assert set(component_of(graph, "A")) == set(breadth_first(graph,
                                                              "A").order)


def test_component_of_the_second_component_is_just_two_nodes():
    assert component_of(bundled(), "G") == frozenset({"G", "H"})


def test_component_of_an_isolated_node_is_itself():
    graph = Graph()
    graph.add_node("Z")
    assert component_of(graph, "Z") == frozenset({"Z"})


def test_component_of_refuses_an_unknown_node():
    with pytest.raises(GraphError, match="no such node"):
        component_of(bundled(), "Q")


def test_edge_pairs_lists_each_edge_once_in_name_order():
    assert edge_pairs(bundled()) == (
        ("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"), ("C", "F"),
        ("D", "E"), ("G", "H"))


def test_edge_pairs_of_an_empty_graph_is_empty():
    assert edge_pairs(Graph()) == ()


# --------------------------------------------------------------------------- #
# chain
# --------------------------------------------------------------------------- #
def test_a_chain_of_one_node_has_no_edges():
    graph = chain(1)
    assert graph.nodes == ("n0",) and graph.edge_count == 0


def test_a_chain_of_five_nodes_has_four_edges():
    graph = chain(5)
    assert len(graph) == 5 and graph.edge_count == 4


def test_a_chain_has_two_ends_of_degree_one():
    graph = chain(4)
    assert graph.degree("n0") == 1 and graph.degree("n3") == 1


def test_the_middle_of_a_chain_has_degree_two():
    assert chain(4).degree("n1") == 2


def test_a_chain_of_zero_nodes_is_refused():
    with pytest.raises(GraphError, match="a chain needs at least one node"):
        chain(0)


def test_a_chain_of_a_negative_length_is_refused():
    with pytest.raises(GraphError, match="a chain needs at least one node"):
        chain(-3)


# --------------------------------------------------------------------------- #
# read_graph
# --------------------------------------------------------------------------- #
def test_read_graph_refuses_a_missing_file(tmp_path):
    with pytest.raises(GraphError, match="graph file not found"):
        read_graph(tmp_path / "nope.txt")


def test_read_graph_reads_one_edge_per_line(tmp_path):
    graph = read_graph(a_graph(tmp_path, "A-B\nB-C\n"))
    assert graph.nodes == ("A", "B", "C") and graph.edge_count == 2


def test_read_graph_skips_comments_and_blank_lines(tmp_path):
    graph = read_graph(a_graph(tmp_path, "# head\n\nA-B\n"))
    assert graph.edge_count == 1


def test_read_graph_tolerates_spaces_around_the_dash(tmp_path):
    graph = read_graph(a_graph(tmp_path, "A - B\n"))
    assert graph.neighbors("A") == ("B",)


def test_read_graph_refuses_a_line_without_a_dash(tmp_path):
    with pytest.raises(GraphError, match="is not an edge written left-right"):
        read_graph(a_graph(tmp_path, "AB\n"))


def test_read_graph_refuses_an_edge_with_no_right_side(tmp_path):
    with pytest.raises(GraphError, match="an edge needs two names"):
        read_graph(a_graph(tmp_path, "A-\n"))


def test_read_graph_refuses_an_edge_with_no_left_side(tmp_path):
    with pytest.raises(GraphError, match="an edge needs two names"):
        read_graph(a_graph(tmp_path, "-B\n"))


def test_read_graph_names_the_offending_line(tmp_path):
    with pytest.raises(GraphError, match="graph.txt:2"):
        read_graph(a_graph(tmp_path, "A-B\nnope\n"))


def test_read_graph_of_an_empty_file_is_empty(tmp_path):
    assert len(read_graph(a_graph(tmp_path, ""))) == 0


def test_read_graph_of_the_bundled_file_is_pinned():
    graph = read_graph()
    assert len(graph) == 8 and graph.edge_count == 7


def test_the_bundled_graph_file_is_exactly_28_bytes():
    assert GRAPH.stat().st_size == 28


def test_the_bundled_graph_file_holds_seven_edges():
    assert GRAPH.read_bytes().count(b"\n") == 7


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def traversals():
    graph = bundled()
    return [breadth_first(graph, "A"), depth_first(graph, "A"),
            depth_first_naive(graph, "A")]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(bundled(), traversals())] == [
        "every traversal starts at its start node",
        "no traversal visits a node twice",
        "every visited node exists in the graph",
        "every parent is a neighbour that was reached first",
        "every reconstructed path follows real edges",
        "every recorded distance equals the path it came from",
        "breadth-first distances never decrease",
        "breadth-first reaches exactly its component",
        "depth-first reaches exactly its component too"]


def test_the_audit_passes_on_the_real_traversals():
    assert problems(audit(bundled(), traversals())) == []


def test_the_audit_catches_a_traversal_that_starts_elsewhere():
    found = traversals()
    object.__setattr__(found[0], "start", "B")
    assert "every traversal starts at its start node" in \
        problems(audit(bundled(), found))


def test_the_audit_catches_a_node_visited_twice():
    found = traversals()
    doubled = found[0].visits + (Visit("B", 7, 1),)
    object.__setattr__(found[0], "visits", doubled)
    assert "no traversal visits a node twice" in \
        problems(audit(bundled(), found))


def test_the_audit_catches_a_node_that_is_not_in_the_graph():
    found = traversals()
    extra = found[1].visits + (Visit("Z", 7, 3),)
    object.__setattr__(found[1], "visits", extra)
    assert "every visited node exists in the graph" in \
        problems(audit(bundled(), found))


def test_the_audit_catches_a_parent_that_is_not_a_neighbour():
    found = traversals()
    parent = dict(found[1].parent)
    parent["E"] = "A"
    object.__setattr__(found[1], "parent", parent)
    assert "every parent is a neighbour that was reached first" in \
        problems(audit(bundled(), found))


def test_the_audit_catches_a_broken_parent_chain():
    found = traversals()
    parent = dict(found[0].parent)
    parent["F"] = None
    object.__setattr__(found[0], "parent", parent)
    assert "every reconstructed path follows real edges" in \
        problems(audit(bundled(), found))


def test_the_audit_catches_a_distance_that_does_not_match_its_path():
    found = traversals()
    visits = list(found[2].visits)
    visits[3] = Visit(visits[3].node, visits[3].order, 9)
    object.__setattr__(found[2], "visits", tuple(visits))
    assert "every recorded distance equals the path it came from" in \
        problems(audit(bundled(), found))


def test_the_audit_catches_breadth_first_distances_that_decrease():
    found = traversals()
    visits = list(found[0].visits)
    visits[-1] = Visit(visits[-1].node, visits[-1].order, 0)
    object.__setattr__(found[0], "visits", tuple(visits))
    assert "breadth-first distances never decrease" in \
        problems(audit(bundled(), found))


def test_the_audit_catches_a_breadth_first_walk_that_stops_early():
    found = traversals()
    object.__setattr__(found[0], "visits", found[0].visits[:3])
    assert "breadth-first reaches exactly its component" in \
        problems(audit(bundled(), found))


def test_the_audit_catches_a_depth_first_walk_that_stops_early():
    found = traversals()
    object.__setattr__(found[1], "visits", found[1].visits[:3])
    assert "depth-first reaches exactly its component too" in \
        problems(audit(bundled(), found))


def test_the_audit_is_repeatable():
    graph = bundled()
    assert audit(graph, traversals()) == audit(graph, traversals())


# --------------------------------------------------------------------------- #
# audit_orders
# --------------------------------------------------------------------------- #
def test_the_order_audit_holds_four_named_checks():
    graph = bundled()
    assert [name for name, _ in audit_orders(legacy_recursive_dfs(graph, "A"),
                                             depth_first(graph, "A"),
                                             depth_first_naive(graph, "A"))] == [
        "the iterative rewrite keeps recursion's order",
        "the iterative rewrite keeps recursion's distances too",
        "the naive stack changes the order",
        "all three visit the same set"]


def test_the_order_audit_passes_on_the_real_traversals():
    graph = bundled()
    assert problems(audit_orders(legacy_recursive_dfs(graph, "A"),
                                 depth_first(graph, "A"),
                                 depth_first_naive(graph, "A"))) == []


def test_the_order_audit_catches_a_rewrite_that_reorders():
    graph = bundled()
    checks = audit_orders(legacy_recursive_dfs(graph, "A"),
                          depth_first_naive(graph, "A"),
                          depth_first_naive(graph, "A"))
    assert "the iterative rewrite keeps recursion's order" in problems(checks)


def test_the_order_audit_catches_a_rewrite_that_loses_distances():
    graph = bundled()
    fixed = depth_first(graph, "A")
    visits = list(fixed.visits)
    visits[-1] = Visit(visits[-1].node, visits[-1].order, 0)
    object.__setattr__(fixed, "visits", tuple(visits))
    checks = audit_orders(legacy_recursive_dfs(graph, "A"), fixed,
                          depth_first_naive(graph, "A"))
    assert "the iterative rewrite keeps recursion's distances too" in \
        problems(checks)


def test_the_order_audit_catches_a_naive_stack_that_matches_recursion():
    graph = bundled()
    checks = audit_orders(legacy_recursive_dfs(graph, "A"),
                          depth_first(graph, "A"), depth_first(graph, "A"))
    assert "the naive stack changes the order" in problems(checks)


def test_the_order_audit_catches_a_traversal_that_misses_a_node():
    graph = bundled()
    short = depth_first_naive(graph, "A")
    object.__setattr__(short, "visits", short.visits[:4])
    checks = audit_orders(legacy_recursive_dfs(graph, "A"),
                          depth_first(graph, "A"), short)
    assert "all three visit the same set" in problems(checks)


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


def test_demo_shows_the_breadth_first_order(capsys):
    run_demo()
    assert "breadth     A B C D F E" in capsys.readouterr().out


def test_demo_shows_the_depth_first_order(capsys):
    run_demo()
    assert "depth       A B D C F E" in capsys.readouterr().out


def test_demo_shows_the_naive_order(capsys):
    run_demo()
    assert "depth-naive A C F D E B" in capsys.readouterr().out


def test_demo_shows_the_components(capsys):
    run_demo()
    assert "components: A B C D F E | G H" in capsys.readouterr().out


def test_demo_shows_the_two_paths_to_c(capsys):
    run_demo()
    assert "DFS reaches C in 3 steps down A -> B -> D -> C, while BFS reaches " \
           "it in 1 down A -> C" in capsys.readouterr().out


def test_demo_shows_the_recursion_error(capsys):
    run_demo()
    out = capsys.readouterr().out
    limit = recursion_limit()
    assert "the legacy recursive walk: RecursionError" in out
    assert f"this module's iterative walk: {limit + 500} nodes, deepest " \
           f"distance {limit + 499}" in out


def test_demo_shows_the_frame_budget(capsys):
    run_demo()
    assert "the walk costs one frame per node" in capsys.readouterr().out


def test_demo_shows_all_thirteen_checks(capsys):
    run_demo()
    assert "13/13 checks pass" in capsys.readouterr().out


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


def test_cli_prints_both_traversals(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "8 nodes, 7 edges, start A" in out
    assert "breadth     A B C D F E" in out
    assert "depth       A B D C F E" in out


def test_cli_prints_the_two_push_lines(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert NAIVE_PUSH in out and FIXED_PUSH in out


def test_cli_bfs_prints_only_breadth(capsys):
    assert cli.main(["--bfs"]) == 0
    out = capsys.readouterr().out
    assert "breadth" in out and "depth " not in out


def test_cli_dfs_prints_only_depth(capsys):
    assert cli.main(["--dfs"]) == 0
    out = capsys.readouterr().out
    assert "depth  " in out and "breadth" not in out


def test_cli_naive_adds_the_third_row(capsys):
    assert cli.main(["--naive"]) == 0
    assert "depth-naive A C F D E B" in capsys.readouterr().out


def test_cli_path_prints_the_path(capsys):
    assert cli.main(["--path", "F"]) == 0
    out = capsys.readouterr().out
    assert "breadth reaches F in 2 steps: A -> C -> F" in out
    assert "depth reaches F in 4 steps: A -> B -> D -> C -> F" in out


def test_cli_components_prints_both_groups(capsys):
    assert cli.main(["--components"]) == 0
    out = capsys.readouterr().out
    assert "2 component(s):" in out
    assert "    A B C D F E" in out and "    G H" in out


def test_cli_legacy_shows_the_recursion_error(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "the iterative rewrite reproduces it: yes" in out
    assert f"a {recursion_limit() + 500}-node chain with the limit at " \
           f"{recursion_limit()}: the recursive walk RecursionError" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 13 and "FAIL" not in out


def test_cli_json_writes_the_traversals(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--naive", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["nodes"][0] == "A" and payload["start"] == "A"
    assert [t["kind"] for t in payload["traversals"]] == [
        "breadth", "depth", "depth-naive"]
    assert payload["traversals"][0]["order"] == list(BFS_ORDER)


def test_cli_json_creates_directories(tmp_path, capsys):
    target = tmp_path / "a" / "b" / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    assert target.is_file()


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_chain_traverses_a_made_graph(capsys):
    assert cli.main(["--chain", "5"]) == 0
    out = capsys.readouterr().out
    assert "5 nodes, 4 edges, start n0" in out
    assert "0 1 2 3 4" in out


def test_cli_chain_zero_exits_two(capsys):
    assert cli.main(["--chain", "0"]) == 2
    assert "a chain needs at least one node" in capsys.readouterr().err


def test_cli_unknown_start_exits_two(capsys):
    assert cli.main(["--start", "Z"]) == 2
    assert "no such node: 'Z'" in capsys.readouterr().err


def test_cli_missing_graph_exits_two(tmp_path, capsys):
    assert cli.main(["--graph", str(tmp_path / "nope.txt")]) == 2
    assert "graph file not found" in capsys.readouterr().err


def test_cli_a_bad_edge_line_exits_two(tmp_path, capsys):
    path = a_graph(tmp_path, "A-B\nnope\n")
    assert cli.main(["--graph", str(path)]) == 2
    assert "is not an edge written left-right" in capsys.readouterr().err


def test_cli_reads_another_graph_file(tmp_path, capsys):
    path = a_graph(tmp_path, "X-Y\nY-Z\n")
    assert cli.main(["--graph", str(path), "--start", "X"]) == 0
    out = capsys.readouterr().out
    assert "3 nodes, 2 edges, start X" in out
    assert "X Y Z" in out
