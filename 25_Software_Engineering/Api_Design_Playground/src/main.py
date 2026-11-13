"""Command line entry point for the API Design Playground.

Usage
-----
    python src/main.py --demo                     # self-checking demo
    python src/main.py                            # list every task
    python src/main.py --query "priority>=3"      # one expression
    python src/main.py --query "priority>=3" --query "done==false"
    python src/main.py --query "title~api" --order-by priority --desc
    python src/main.py --version v1               # legacy wire shape
    python src/main.py --limit 3 --json out.json

Queries are combined with AND, evaluated by the same builder the library
uses, and serialized through `respond()` so `--version` really changes the
wire shape. Fully offline: seed tasks in, a rendered response out.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from api import (
    SUPPORTED_VERSIONS,
    TASK_FIELDS,
    ApiError,
    ValidationError,
    TaskQueryBuilder,
    apply_query,
    load_tasks,
    parse_expression,
    respond_many,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("api_playground")

BANNER = """
====================================
 API DESIGN PLAYGROUND
   builder, repository, versioning
====================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query a bundled task store through a fluent builder, "
                    "with typed errors and v1/v2 response shapes (offline)")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=None,
                        help="seed tasks JSON (default: the bundled sample)")
    parser.add_argument("--query", action="append", default=None,
                        metavar="EXPR",
                        help="filter expression such as 'priority>=3' "
                             "(repeatable, combined with AND)")
    parser.add_argument("--order-by", choices=TASK_FIELDS, default=None,
                        help="field to sort by")
    parser.add_argument("--desc", action="store_true",
                        help="sort descending")
    parser.add_argument("--limit", type=int, default=None,
                        help="keep at most N results")
    parser.add_argument("--version", choices=SUPPORTED_VERSIONS,
                        default="v2", help="response shape to render")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the response as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text output")
    return parser


def build_query(expressions: list[str] | None, order_by: str | None,
                descending: bool, limit: int | None):
    """Compose the CLI flags into one validated Query."""
    builder = TaskQueryBuilder()
    for expression in expressions or ():
        parsed = parse_expression(expression)
        for field_name, op, value in parsed.filters:
            builder.where(field_name, op, value)
    if order_by is not None:
        builder.order_by(order_by, descending=descending)
    elif descending:
        raise ValidationError("--desc requires --order-by")
    if limit is not None:
        builder.limit(limit)
    return builder.build()


def render_rows(payload: dict) -> str:
    lines = [f"  {'id':<6}{'pri':<5}{'done':<6}{'title'}"]
    lines.append("  " + "-" * 56)
    for record in payload["tasks"]:
        done = "yes" if record["done"] else "no"
        lines.append(f"  {record['id']:<6}{record['priority']:<5}{done:<6}"
                     f"{record['title']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except ApiError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    try:
        tasks = load_tasks(args.file)
        query = build_query(args.query, args.order_by, args.desc, args.limit)
        hits = apply_query(tasks, query)
        payload = {"api_version": args.version, "count": len(hits),
                   "tasks": respond_many(hits, args.version)}
    except ApiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        print(render_rows(payload))
        print(f"\n{len(hits)} of {len(tasks)} tasks "
              f"({args.version} shape)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
