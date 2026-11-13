"""Command line entry point for the Config Manager.

Usage
-----
    python src/main.py --demo                                # bundled layers
    python src/main.py --file data/settings.yaml             # add file layer
    python src/main.py --file data/settings.yaml --json out.json
    python src/main.py --file data/settings.yaml --env-prefix APP_

Fully offline: local YAML/JSON in, validated config + provenance out.
No network, no remote config servers, no secrets fetched at runtime.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from configmanager import (
    DEFAULTS_YAML,
    DEFAULT_ENV_PREFIX,
    ENV_JSON,
    SCHEMA_YAML,
    ConfigError,
    load_config,
    load_json,
    render_report,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("config")

BANNER = """
========================================
 CONFIG MANAGER
   layered YAML/JSON + schema checks
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Layer defaults -> file -> env and validate against a "
                    "schema (offline)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="layer the bundled sample configs")
    action.add_argument("--file", type=Path, default=None,
                        help="config file (.yaml/.yml/.json) layered over "
                             "the defaults")
    parser.add_argument("--defaults", type=Path, default=DEFAULTS_YAML,
                        help="defaults layer (default: bundled defaults.yaml)")
    parser.add_argument("--schema", type=Path, default=SCHEMA_YAML,
                        help="schema file (default: bundled schema.yaml)")
    parser.add_argument("--env-file", type=Path, default=None,
                        help="JSON file of APP_* environment variables to "
                             "use as the env layer (default: bundled env.json "
                             "in --demo, none otherwise)")
    parser.add_argument("--env-prefix", default=DEFAULT_ENV_PREFIX,
                        help=f"env var prefix (default {DEFAULT_ENV_PREFIX})")
    parser.add_argument("--json", type=Path, default=None,
                        help="write values + provenance as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the provenance report")
    return parser


def _validate_flags(parser: argparse.ArgumentParser,
                    args: argparse.Namespace) -> None:
    """Fast-fail flag validation before any file is read."""
    if not args.env_prefix:
        parser.error("--env-prefix must be non-empty")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_flags(parser, args)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    run_demo()
            else:
                run_demo()
        except ConfigError as exc:
            # --demo never fails on user input: bundled data ships with the
            # repo, so a ConfigError here is reported but not fatal.
            print(f"Error: {exc}", file=sys.stderr)
        return 0

    if args.file is None:
        parser.error("one of the arguments --demo --file is required")

    if not args.quiet:
        print(BANNER)
    try:
        # --env-file without --file: only the defaults layer applies
        env_path = args.env_file
        environ = load_json(env_path) if env_path else None
        if environ is not None and not all(
                isinstance(v, str) for v in environ.values()):
            raise ConfigError(f"{env_path.name}: env values must be strings")
        result = load_config(args.defaults, args.schema,
                             file_path=args.file,
                             environ=environ,
                             env_prefix=args.env_prefix)
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(render_report(result))
        print("\nDone.")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result.to_dict(), indent=2),
                             encoding="utf-8")
        if not args.quiet:
            print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
