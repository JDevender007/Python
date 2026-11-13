"""Command line entry point for the Cloud Config Manager.

Usage
-----
    python src/main.py --demo                                   # full offline demo
    python src/main.py --validate infra.yaml                    # schema check
    python src/main.py --plan --desired base.yaml --observed live.yaml
    python src/main.py --plan --desired base.yaml --observed live.yaml --check   # exit 1 on drift
    python src/main.py --merge base.yaml --overlay prod.yaml --out merged.yaml

File-based and offline: no cloud APIs are contacted. Secrets in the plan are
always masked.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from config_manager import (
    ConfigError,
    build_plan,
    deep_merge,
    load_config,
    render_plan,
    run_demo,
    save_config,
    summarize,
    validate_config,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("config")

BANNER = """
========================================
 CLOUD CONFIG MANAGER
   file-based, offline, secrets masked
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cloud config validation, overlays, drift plans")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true", help="run the offline demo")
    action.add_argument("--validate", type=str, metavar="FILE",
                        help="validate a YAML/JSON config")
    action.add_argument("--plan", action="store_true",
                        help="diff desired vs observed (--desired/--observed)")
    action.add_argument("--merge", action="store_true",
                        help="deep-merge base + overlay (--base/--overlay)")
    parser.add_argument("--desired", help="desired config file (for --plan)")
    parser.add_argument("--observed", help="observed state file (for --plan)")
    parser.add_argument("--base", help="base config file (for --merge)")
    parser.add_argument("--overlay", help="overlay config file (for --merge)")
    parser.add_argument("--out", help="write merged config here (for --merge)")
    parser.add_argument("--check", action="store_true",
                        help="with --plan: exit 1 when drift exists")
    parser.add_argument("--json", action="store_true", help="JSON output where applicable")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    if args.validate is not None:
        try:
            config = load_config(args.validate)
        except ConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        errors = validate_config(config)
        if errors:
            print(f"INVALID: {args.validate} ({len(errors)} problem(s))", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 2
        print(f"VALID: {args.validate}")
        return 0

    if args.plan:
        if not args.desired or not args.observed:
            print("Error: --plan requires --desired and --observed",
                  file=sys.stderr)
            return 2
        try:
            desired = load_config(args.desired)
            observed = load_config(args.observed)
            changes = build_plan(desired, observed)
        except ConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(BANNER)
        if args.json:
            print(json.dumps({
                "changes": [c.to_dict() for c in changes],
                "summary": summarize(changes),
                "drift": bool(changes),
            }, indent=2, default=str))
        else:
            print(render_plan(changes))
        if args.check and changes:
            return 1
        return 0

    if args.merge:
        if not args.base or not args.overlay:
            print("Error: --merge requires --base and --overlay", file=sys.stderr)
            return 2
        try:
            base = load_config(args.base)
            overlay = load_config(args.overlay)
        except ConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        merged = deep_merge(base, overlay)
        errors = validate_config(merged)
        if errors:
            print("Error: merged config is invalid:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 2
        if args.out:
            target = save_config(merged, args.out)
            print(f"Merged config written to {target}")
        else:
            print(BANNER)
            print(json.dumps(merged, indent=2) if args.json else
                  _to_yaml(merged))
        return 0

    parser.error("choose an action: --demo, --validate, --plan, --merge")
    return 2  # pragma: no cover


def _to_yaml(config: dict) -> str:
    import yaml

    return yaml.safe_dump(config, sort_keys=False)


if __name__ == "__main__":
    raise SystemExit(main())
