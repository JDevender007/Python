"""Command line entry point for the Device Registry.

Usage
-----
    python src/main.py --demo
    python src/main.py --db registry.db --list
    python src/main.py --db registry.db --list --kind sensor
    python src/main.py --db registry.db --add "fan-attic:Attic Fan:actuator:attic:1.0.0"
    python src/main.py --db registry.db --status "fan-attic:online"
    python src/main.py --db registry.db --history fan-attic
    python src/main.py --db registry.db --remove fan-attic

Fully offline: a local SQLite file (or an in-memory database for --demo)
in, validated device rows out. No network, no broker, no API keys.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
from pathlib import Path

from registry import (
    ID_RE,
    KINDS,
    STATUSES,
    RegistryError,
    add_device,
    connect,
    device_events,
    get_device,
    list_devices,
    registry_stats,
    remove_device,
    render_report,
    run_demo,
    seed_registry,
    update_status,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("registry")

BANNER = """
========================================
 DEVICE REGISTRY
   SQLite device inventory
   validated CRUD + status history
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
        description="Manage a local IoT device registry in SQLite")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true",
                      help="run the offline demo")
    mode.add_argument("--db", type=Path, default=None,
                      help="SQLite database file (created if missing)")
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("--list", action="store_true",
                        help="list devices (combine with the filters)")
    action.add_argument("--add", default=None,
                        help="add a device as id:name:kind:room:firmware")
    action.add_argument("--status", default=None,
                        help="change status as id:status")
    action.add_argument("--remove", default=None, metavar="ID",
                        help="remove a device by id")
    action.add_argument("--history", default=None, metavar="ID",
                        help="show the status history of a device")
    action.add_argument("--stats", action="store_true",
                        help="print registry statistics")
    action.add_argument("--seed", action="store_true",
                        help="load the bundled seed devices into the database")
    parser.add_argument("--kind", choices=KINDS, default=None,
                        help="filter --list by kind")
    parser.add_argument("--room", default=None, help="filter --list by room")
    parser.add_argument("--status-filter", choices=STATUSES, default=None,
                        help="filter --list by status")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the result as JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress the text report")
    return parser


def _parse_add(spec: str) -> dict:
    parts = spec.split(":")
    if len(parts) != 5:
        raise RegistryError(
            "invalid --add value: expected id:name:kind:room:firmware")
    device_id, name, kind, room, firmware = (part.strip() for part in parts)
    return {"device_id": device_id, "name": name, "kind": kind, "room": room,
            "firmware": firmware}


def _parse_status(spec: str) -> tuple[str, str]:
    parts = spec.split(":")
    if len(parts) != 2:
        raise RegistryError("invalid --status value: expected id:status")
    return parts[0].strip(), parts[1].strip()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        try:
            return _run_demo(args.quiet, run_demo)
        except RegistryError as exc:
            if not args.quiet:
                print(f"Error: {exc}", file=sys.stderr)
            return 0
    if args.db is None:
        parser.error("one of the arguments --demo --db is required")

    actions = (args.list, args.add is not None, args.status is not None,
               args.remove is not None, args.history is not None, args.stats,
               args.seed)
    if sum(bool(action) for action in actions) != 1:
        print("Error: choose exactly one of --list --add --status --remove "
              "--history --stats --seed", file=sys.stderr)
        return 2
    if args.kind or args.room or args.status_filter:
        if not args.list:
            print("Error: --kind/--room/--status-filter require --list",
                  file=sys.stderr)
            return 2

    # fast-fail on malformed input before touching the database
    payload: dict = {}
    if args.add is not None:
        try:
            payload = _parse_add(args.add)
        except RegistryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
    if args.status is not None:
        try:
            device_id, status = _parse_status(args.status)
        except RegistryError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if status not in STATUSES:
            print(f"Error: invalid status {status!r} "
                  f"(choose from {', '.join(STATUSES)})", file=sys.stderr)
            return 2

    try:
        connection = connect(args.db)
        if args.seed:
            added = seed_registry(connection)
            lines = [f"Seeded {added} devices into {args.db}"]
        elif args.add is not None:
            device = add_device(connection, **payload)
            lines = [f"Added {device['id']} ({device['kind']}, "
                     f"{device['status']})"]
        elif args.status is not None:
            device = update_status(connection, device_id, status)
            lines = [f"{device['id']} is now {device['status']}"]
        elif args.remove is not None:
            device = remove_device(connection, args.remove)
            lines = [f"Removed {device['id']}"]
        elif args.history is not None:
            rows = device_events(connection, args.history)
            lines = [f"{args.history}: {len(rows)} status change(s)"]
            lines += [f"  {row['changed_at']}  {row['status']}" for row in rows]
        elif args.stats:
            stats = registry_stats(connection)
            lines = [f"Devices {stats['total']}, rooms {stats['rooms']}",
                     "By kind: " + ", ".join(
                         f"{kind}={count}"
                         for kind, count in stats["by_kind"].items()),
                     "By status: " + ", ".join(
                         f"{status}={count}"
                         for status, count in stats["by_status"].items())]
        else:
            devices = list_devices(connection, kind=args.kind, room=args.room,
                                   status=args.status_filter)
            lines = [f"{len(devices)} device(s)"] + [
                f"  {device['id']:<14} {device['kind']:<9} "
                f"{device['status']:<12} {device['room']}" for device in devices]
    except RegistryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(BANNER)
        for line in lines:
            print(line)
        if args.list:
            print()
            print(render_report(connection, devices=devices))

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {"devices": list_devices(connection),
                   "stats": registry_stats(connection)}
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"\nWrote {args.json}")

    connection.close()
    if not args.quiet:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
