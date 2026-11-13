"""Command line entry point for the Plugin Architecture project.

Usage
-----
    python src/main.py --demo                          # bundled pipeline
    python src/main.py --config data/plugins.json      # your own config
    python src/main.py --config c.json --plugins dir/  # custom plugin dir

Fully offline: plugins ship in plugins/, config in data/plugins.json.
No network, no API keys, no downloads.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import logging
import sys
from pathlib import Path

from plugin_core import (
    DEFAULT_PLUGINS_DIR,
    PluginError,
    enabled_plugins,
    execute,
    format_report,
    load_config,
    load_plugins,
    run_demo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("plugins")

BANNER = """
========================================
 PLUGIN ARCHITECTURE
   Discovery, lifecycle, sandbox
========================================
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dynamic plugin discovery with lifecycle and sandbox")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--demo", action="store_true",
                        help="run the bundled pipeline with self-checks")
    action.add_argument("--config", type=Path, default=None,
                        help="pipeline config JSON (input, enable, disable)")
    parser.add_argument("--plugins", type=Path, default=None,
                        help="plugin directory (requires --config)")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the banner")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        if not args.quiet:
            print(BANNER)
        try:
            if args.quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    return run_demo()
            return run_demo()
        except PluginError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.config is None:
        parser.error("one of the arguments --demo --config is required")

    if not args.quiet:
        print(BANNER)

    # Fast-fail: validate both inputs before any plugin work runs.
    if not args.config.is_file():
        print(f"Error: file not found: {args.config}", file=sys.stderr)
        return 2
    if args.plugins is not None and not args.plugins.is_dir():
        print(f"Error: plugin directory not found: {args.plugins}",
              file=sys.stderr)
        return 2

    try:
        config = load_config(args.config)
        registry = load_plugins(args.plugins or DEFAULT_PLUGINS_DIR)
        selection = enabled_plugins(config, registry.names)
        report = execute(registry, selection, config["input"])
    except PluginError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if registry.failures:
        for failure in registry.failures:
            print(f"Warning: {failure.path.name}: {failure.message}",
                  file=sys.stderr)
    print(format_report(report, len(config["input"])))
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
