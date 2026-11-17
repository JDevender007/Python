"""Command line entry point for the Interactive Dashboard.

Usage
-----
    python src/main.py --demo                       # bundled data -> output/dashboard.html
    python src/main.py --build --file data.csv      # your own data -> HTML
    python src/main.py --kpis --file data.csv       # print headline KPIs
    python src/main.py --kpis --json kpis.json      # KPIs as JSON
    python src/main.py --demo --out site/index.html

The saved HTML embeds plotly.js inline: open it in any browser, fully
offline. No network, no server, no API keys.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from dashboard import (
    DEFAULT_OUTPUT,
    DEMO_CSV,
    DashboardError,
    compute_kpis,
    load_data,
    render_kpis,
    run_demo,
    save_dashboard,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("dashboard")

BANNER = """
========================================
 INTERACTIVE DASHBOARD
   plotly HTML, self-contained offline
========================================
"""


def _run_demo(quiet: bool, func, *args, **kwargs) -> int:
    """Run the offline demo; with --quiet no stream prints anything."""
    if not quiet:
        return func(*args, **kwargs)
    # --quiet: silence the demo's own prints and its log records alike, so a
    # scripted run writes nothing to stdout or stderr.
    level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return func(*args, **kwargs)
    finally:
        logging.disable(level)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a self-contained interactive dashboard (offline HTML)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true",
                        help="build the dashboard from the bundled sample")
    action.add_argument("--build", action="store_true",
                        help="build a dashboard from --file")
    action.add_argument("--kpis", action="store_true",
                        help="print headline KPIs instead of building")
    parser.add_argument("--file", type=Path, default=None,
                        help="data CSV (default: bundled sample)")
    parser.add_argument("--out", type=Path,
                        default=DEFAULT_OUTPUT / "dashboard.html",
                        help="output HTML path for --demo/--build")
    parser.add_argument("--json", type=Path, default=None,
                        help="write KPIs as JSON to this path")
    parser.add_argument("--quiet", action="store_true", help="suppress progress output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        out_dir = args.out.parent  # Path("dashboard.html").parent == Path(".")

        def demo() -> int:
            try:
                shown = args.out.resolve().relative_to(Path.cwd().resolve())
            except ValueError:
                shown = args.out
            hint = None if args.quiet else f"Open {shown} in a browser (works offline)."
            code = run_demo(out_dir=out_dir, quiet=args.quiet, note=hint)
            # run_demo writes dashboard.html; honour a custom --out filename
            produced = out_dir / "dashboard.html"
            if args.out.name != "dashboard.html" and produced.is_file():
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_bytes(produced.read_bytes())
                produced.unlink()
            return code

        try:
            return _run_demo(args.quiet, demo)
        except DashboardError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.kpis and not args.quiet:
        print(BANNER)

    try:
        frame = load_data(args.file) if args.file else load_data(DEMO_CSV)
    except DashboardError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    kpis = compute_kpis(frame)
    if not args.quiet:
        print(render_kpis(kpis))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(kpis, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    if args.build:
        try:
            path = save_dashboard(frame, args.out)
        except DashboardError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"\nWrote {path} ({path.stat().st_size:,} bytes, self-contained)")
            print("Open it in a browser - no network needed.")
        return 0

    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
