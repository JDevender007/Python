"""Command line front end for the traversal lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from traversal import (                                       # noqa: E402
    FIXED_PUSH,
    NAIVE_PUSH,
    Graph,
    GraphError,
    audit,
    audit_orders,
    breadth_first,
    chain,
    components,
    depth_first,
    depth_first_naive,
    legacy_recursive_dfs,
    problems,
    read_graph,
    recursion_limit,
    run_demo,
)


def _table(traversals) -> None:
    print(f"  {'traversal':<12}{'order':<34}distances")
    for traversal in traversals:
        print(f"  {traversal.kind:<12}{' '.join(traversal.order):<34}"
              f"{' '.join(str(d) for d in traversal.distances)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="traversal-lab",
        description="Walk a graph breadth-first and depth-first, and show that "
                    "the order, the distances and the stack all depend on when "
                    "a node is marked.")
    parser.add_argument("--graph", default=None,
                        help="a file of left-right edges (default: the bundled "
                             "graph)")
    parser.add_argument("--start", default="A",
                        help="the node to start from (default: A)")
    parser.add_argument("--bfs", action="store_true",
                        help="breadth-first only")
    parser.add_argument("--dfs", action="store_true",
                        help="depth-first only")
    parser.add_argument("--naive", action="store_true",
                        help="the mark-on-push stack, for comparison")
    parser.add_argument("--legacy", action="store_true",
                        help="the recursive walk, and the chain that breaks it")
    parser.add_argument("--components", action="store_true",
                        help="every connected component")
    parser.add_argument("--path", default=None, metavar="NODE",
                        help="the path the traversal found to NODE")
    parser.add_argument("--chain", type=int, default=None, metavar="N",
                        help="traverse an N-node chain instead of the graph")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the traversals to PATH as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    if args.chain is not None:
        try:
            graph = chain(args.chain)
        except GraphError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        start = "n0"
    else:
        try:
            graph = read_graph(args.graph) if args.graph else read_graph()
        except GraphError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        start = args.start

    try:
        bfs = breadth_first(graph, start)
        dfs = depth_first(graph, start)
    except GraphError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    naive = depth_first_naive(graph, start)
    traversals = [bfs, dfs]
    if args.naive:
        traversals.append(naive)

    if args.bfs and not args.dfs:
        traversals = [bfs]
    elif args.dfs and not args.bfs:
        traversals = [dfs] + ([naive] if args.naive else [])

    if args.quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            _table(traversals)
        return 0

    print(f"  {len(graph)} nodes, {graph.edge_count} edges, start {start}")
    _table(traversals)
    print(f"  {'the naive stack pushes':<26}{NAIVE_PUSH}")
    print(f"  {'the faithful stack pushes':<26}{FIXED_PUSH}")

    if args.path is not None:
        for traversal in traversals:
            try:
                path = traversal.path_to(args.path)
            except GraphError as error:
                print(f"\n  {traversal.kind}: {error}")
                continue
            print(f"\n  {traversal.kind} reaches {args.path} in "
                  f"{len(path) - 1} steps: {' -> '.join(path)}")

    if args.components:
        groups = components(graph)
        print(f"\n  {len(groups)} component(s):")
        for group in groups:
            print(f"    {' '.join(group)}")

    if args.legacy:
        recursive = legacy_recursive_dfs(graph, start)
        print(f"\n  the recursive walk reaches {len(recursive)} nodes in the "
              f"order {' '.join(recursive.order)}")
        print(f"  the iterative rewrite reproduces it: "
              f"{'yes' if dfs.order == recursive.order else 'no'}")
        limit = recursion_limit()
        deep = chain(limit + 500)
        try:
            legacy_recursive_dfs(deep, "n0")
            outcome = "survived"
        except RecursionError:
            outcome = "RecursionError"
        iterative = depth_first(deep, "n0")
        print(f"  a {len(deep)}-node chain with the limit at {limit}: the "
              f"recursive walk {outcome}, the iterative one reaches "
              f"{len(iterative)} nodes at depth {iterative.depth}")

    if args.audit:
        print()
        checks = audit(graph, traversals) + \
            audit_orders(legacy_recursive_dfs(graph, start), dfs, naive)
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)
        if failed:
            print(f"  {len(failed)} check(s) failed", file=sys.stderr)
            return 1

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"nodes": list(graph.nodes), "start": start,
                   "traversals": [t.to_dict() for t in traversals]}
        target.write_text(json.dumps(payload, indent=2) + "\n",
                          encoding="utf-8")
        print(f"  wrote {len(traversals)} traversal(s) to {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
