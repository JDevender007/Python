"""Command line entry point for the Serverless Event Queue.

Usage
-----
    python src/main.py --demo                          # offline fake-clock demo
    python src/main.py --create orders                 # create a queue (persisted)
    python src/main.py --send orders --body "hello"
    python src/main.py --receive orders --max 5
    python src/main.py --delete orders --id <message-id>
    python src/main.py --purge orders
    python src/main.py --attributes orders
    python src/main.py --list

Queue state persists to a local JSON file (--state, default
data/queue_state.json) so commands compose across runs. No network, no AWS.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from event_queue import QueueError, QueueManager, run_demo

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("queue")

BANNER = """
========================================
 SERVERLESS EVENT QUEUE
   local, offline, SQS-style semantics
========================================
"""

DEFAULT_STATE = Path(__file__).resolve().parent.parent / "data" / "queue_state.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="In-memory SQS-style event queue (local)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--demo", action="store_true", help="run the offline demo")
    action.add_argument("--list", action="store_true", help="list queues")
    action.add_argument("--create", metavar="NAME", help="create a queue")
    action.add_argument("--send", metavar="NAME", help="send a message to NAME")
    action.add_argument("--receive", metavar="NAME", help="receive messages from NAME")
    action.add_argument("--delete", metavar="NAME", help="delete a message by --id")
    action.add_argument("--purge", metavar="NAME", help="purge all messages from NAME")
    action.add_argument("--attributes", metavar="NAME", help="show queue attributes")

    parser.add_argument("--body", default="", help="message body for --send")
    parser.add_argument("--attr", action="append", default=[], metavar="K=V",
                        help="message attribute for --send (repeatable)")
    parser.add_argument("--delay", type=float, default=None,
                        help="send delay seconds for --send")
    parser.add_argument("--dedup", default=None, help="dedup id for --send")
    parser.add_argument("--max", type=int, default=1, help="max messages for --receive")
    parser.add_argument("--wait", type=float, default=0.0,
                        help="long-poll seconds for --receive")
    parser.add_argument("--id", default=None, help="message id for --delete")
    parser.add_argument("--visibility", type=float, default=None,
                        help="visibility timeout for --create")
    parser.add_argument("--max-receive", type=int, default=None,
                        help="max receive count before dead-letter for --create")
    parser.add_argument("--dlq", default=None, help="dead-letter queue name for --create")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE,
                        help="state file path")
    parser.add_argument("--json", action="store_true", help="JSON output where applicable")
    return parser


def _parse_attrs(pairs: list[str]) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise QueueError(f"attribute must look like K=V: {pair!r}")
        key, value = pair.split("=", 1)
        if not key:
            raise QueueError(f"empty attribute key in {pair!r}")
        attributes[key] = value
    return attributes


def _load_manager(args: argparse.Namespace) -> QueueManager:
    if args.state.is_file():
        return QueueManager.load(args.state)
    return QueueManager()


def _save(manager: QueueManager, args: argparse.Namespace) -> None:
    manager.save(args.state)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()

    print(BANNER)
    try:
        if args.list:
            manager = _load_manager(args)
            names = manager.list_queues()
            if args.json:
                print(json.dumps(names, indent=2))
            elif not names:
                print("(no queues yet - try --create NAME)")
            else:
                for name in names:
                    attrs = manager.get_queue(name).attributes()
                    print(f"  {name:<20} depth={attrs['depth']} "
                          f"in_flight={attrs['in_flight']} sent={attrs['sent']}")
            return 0

        if args.create is not None:
            manager = _load_manager(args)
            kwargs: dict = {}
            if args.visibility is not None:
                kwargs["visibility_timeout"] = args.visibility
            if args.max_receive is not None:
                kwargs["max_receive_count"] = args.max_receive
            if args.dlq:
                kwargs["dead_letter"] = manager.get_queue(args.dlq)
            queue = manager.create_queue(args.create, **kwargs)
            _save(manager, args)
            print(f"Queue '{queue.name}' ready "
                  f"(visibility={queue.visibility_timeout}s, "
                  f"max_receive={queue.max_receive_count})")
            return 0

        if args.send is not None:
            if not args.body:
                print("Error: --body is required for --send", file=sys.stderr)
                return 2
            manager = _load_manager(args)
            queue = manager.get_queue(args.send)
            attributes = _parse_attrs(args.attr)
            message = queue.send(args.body, attributes,
                                 delay=args.delay, dedup_id=args.dedup)
            _save(manager, args)
            if args.json:
                print(json.dumps(message.to_dict(), indent=2, default=str))
            else:
                print(f"Sent {message.id} to '{queue.name}' "
                      f"(visible_at={message.visible_at:.0f})")
            return 0

        if args.receive is not None:
            manager = _load_manager(args)
            queue = manager.get_queue(args.receive)
            messages = queue.receive(max_messages=args.max, wait=args.wait)
            _save(manager, args)
            if args.json:
                print(json.dumps([m.to_dict() for m in messages],
                                 indent=2, default=str))
            elif not messages:
                print("(no messages visible)")
            else:
                for message in messages:
                    print(f"  {message.id}  recv={message.receive_count}  "
                          f"body={message.body!r}  attrs={message.attributes}")
            return 0

        if args.delete is not None:
            if not args.id:
                print("Error: --id is required for --delete", file=sys.stderr)
                return 2
            manager = _load_manager(args)
            queue = manager.get_queue(args.delete)
            queue.delete(args.id)
            _save(manager, args)
            print(f"Deleted {args.id} from '{queue.name}'")
            return 0

        if args.purge is not None:
            manager = _load_manager(args)
            queue = manager.get_queue(args.purge)
            removed = queue.purge()
            _save(manager, args)
            print(f"Purged {removed} message(s) from '{queue.name}'")
            return 0

        if args.attributes is not None:
            manager = _load_manager(args)
            queue = manager.get_queue(args.attributes)
            attrs = queue.attributes()
            if args.json:
                print(json.dumps(attrs, indent=2))
            else:
                for key, value in attrs.items():
                    print(f"  {key:<20} {value}")
            return 0

    except QueueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    parser.error("choose an action")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
