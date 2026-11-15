"""Command line front end for the pathfinding lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pathfind import (                                        # noqa: E402
    ALGORITHMS,
    LEGACY_FIELD,
    Cell,
    Grid,
    PathError,
    audit,
    breadth_first,
    has_clock,
    legacy_spread,
    legacy_times,
    problems,
    read_grid,
    resolve,
    run_demo,
)


def _row(outcome, reference) -> str:
    shortest = "yes" if outcome.steps == reference.steps else "no"
    return (f"  {outcome.algorithm:<10}{'yes' if outcome.found else 'no':>7}"
            f"{outcome.steps:>7}{outcome.expansions:>12}{shortest:>10}")


def _header() -> str:
    return (f"  {'algorithm':<10}{'found':>7}{'steps':>7}{'expansions':>12}"
            f"{'shortest':>10}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="path-lab",
        description="Run five searches over one grid and report the number "
                    "that can be compared -- cells expanded -- instead of a "
                    "wall-clock time that cannot.")
    parser.add_argument("--grid", default=None,
                        help="a grid file (default: the bundled 6x6 grid)")
    parser.add_argument("--algorithm", default=None, metavar="NAME",
                        help="one search: breadth, depth, dijkstra, astar or "
                             "greedy (bfs and dfs also work)")
    parser.add_argument("--render", nargs="?", const="breadth", default=None,
                        metavar="NAME",
                        help="draw the grid with one search's path on it "
                             "(default name: breadth)")
    parser.add_argument("--legacy", action="store_true",
                        help="the legacy execution_time_ms, measured over and "
                             "over")
    parser.add_argument("--sealed", action="store_true",
                        help="also run all five on a grid with the end walled "
                             "off")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the outcomes to PATH as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def _run(grid: Grid, names):
    return [ALGORITHMS[name](grid) for name in names]


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    try:
        grid = read_grid(args.grid) if args.grid else read_grid()
    except PathError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.algorithm is not None:
        try:
            names = [resolve(args.algorithm)]
        except PathError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
    else:
        names = list(ALGORITHMS)

    outcomes = _run(grid, names)
    reference = breadth_first(grid)
    by_name = {outcome.algorithm: outcome for outcome in outcomes}

    if args.quiet:
        with contextlib.redirect_stdout(io.StringIO()):
            for outcome in outcomes:
                print(_row(outcome, reference))
        return 0

    where = Path(args.grid).name if args.grid else "data/grid.txt"
    print(f"  {where}: {grid.height}x{grid.width}, {len(grid.walls)} walls, "
          f"start {grid.start}, end {grid.end}, "
          f"{len(grid.open_cells)} open cells")
    print()
    print(_header())
    for outcome in outcomes:
        print(_row(outcome, reference))

    if args.render is not None:
        try:
            target = resolve(args.render)
        except PathError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        rendered = by_name[target] if target in by_name \
            else ALGORITHMS[target](grid)
        print(f"\n  {rendered.algorithm}: {rendered.steps} steps, "
              f"{rendered.expansions} cells expanded")
        for row in grid.render(rendered.path, rendered.expanded):
            print(f"    {row}")
        print(f"    {rendered.steps} steps: "
              f"{' -> '.join(str(cell) for cell in rendered.path)}")

    if args.legacy:
        times = legacy_times(grid, 40)
        print(f"\n  {LEGACY_FIELD}, on 40 identical A* runs:")
        print(f"    {len(set(times))} distinct values between {min(times):.1f} "
              f"and {max(times):.1f} microseconds, a spread of "
              f"{legacy_spread(times):.1f}")
        second = ALGORITHMS["astar"](grid)
        print(f"    but two runs still compare equal, because the result holds "
              f"expansions ({second.expansions}) and no clock: "
              f"{'yes' if second == ALGORITHMS['astar'](grid) else 'no'}")

    if args.sealed:
        sealed = Grid(("S#", "#E"), Cell(0, 0), Cell(1, 1))
        print(f"\n  a 2x2 grid whose end is walled off:")
        for outcome in _run(sealed, list(ALGORITHMS)):
            print(f"    {outcome.algorithm:<10}{'found' if outcome.found else 'found nothing':<14}"
                  f"after {outcome.expansions} expansion(s)")

    if args.audit:
        print()
        checks = audit(grid, _run(grid, list(ALGORITHMS)))
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)
        if failed:
            print(f"  {len(failed)} check(s) failed", file=sys.stderr)
            return 1

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"grid": {"height": grid.height, "width": grid.width,
                            "walls": [str(cell) for cell in sorted(grid.walls)],
                            "start": str(grid.start), "end": str(grid.end)},
                   "outcomes": [outcome.to_dict() for outcome in outcomes],
                   "clocks": [has_clock(outcome) for outcome in outcomes]}
        target.write_text(json.dumps(payload, indent=2) + "\n",
                          encoding="utf-8")
        print(f"  wrote {len(outcomes)} outcome(s) to {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
