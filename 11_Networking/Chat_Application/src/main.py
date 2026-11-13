"""Command line entry point for the Chat Application.

Usage
-----
    python src/main.py --demo                # local server + two clients, no input
    python src/main.py server --port 9000    # run the chat server
    python src/main.py client --nick alice   # connect interactively

Binds to localhost by default. Only expose it to networks you control.
"""

from __future__ import annotations

import argparse
import logging
import sys

from client import ChatClient
from server import ChatServer

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
LOG = logging.getLogger("chat")

BANNER = """
========================================
 CHAT APPLICATION
   localhost / trusted networks only
========================================
"""


def run_demo() -> int:
    """Start a server and two clients on localhost, exchange messages, exit."""
    print(BANNER)
    from client import demo

    return demo()


def run_server(host: str, port: int) -> int:
    """Run the chat server until interrupted."""
    print(BANNER)
    server = ChatServer(host=host, port=port)
    address = server.start()
    print(f"Listening on {address[0]}:{address[1]}  (Ctrl+C to stop)")
    print("Rooms:", server.room_names or "(empty)")
    try:
        while True:
            import time

            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()
    return 0


def run_client(host: str, port: int, nick: str) -> int:
    """Interactive chat client reading lines from stdin."""
    print(BANNER)
    client = ChatClient(host=host, port=port)
    try:
        ack = client.connect(nick)
        print(f"Connected as {ack}. Type messages, /join <room>, /who, /leave, /quit")
    except (ConnectionError, OSError, TimeoutError) as exc:
        print(f"Could not connect: {exc}", file=sys.stderr)
        return 1

    import threading

    def pump() -> None:
        """Print incoming messages as they arrive."""
        while client.connected:
            for line in client.drain():
                command, _, rest = line.partition("\x1e")
                print(f"\r{rest if command in {'MSG', 'LIST'} else rest}")
            import time

            time.sleep(0.1)

    threading.Thread(target=pump, daemon=True).start()

    try:
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line:
                continue
            if line in ("/quit", "/exit"):
                break
            if line.startswith("/join "):
                client.join(line[6:].strip())
            elif line == "/leave":
                client.leave()
            elif line == "/who":
                client.who()
            else:
                client.say(line)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()
    print("Disconnected.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rooms-based TCP chat application")
    parser.add_argument("--host", default="127.0.0.1", help="bind/connect host (default localhost)")
    sub = parser.add_subparsers(dest="mode")

    server = sub.add_parser("server", help="run the chat server")
    server.add_argument("--port", type=int, default=9000, help="TCP port (0 = auto)")

    client = sub.add_parser("client", help="connect as a client")
    client.add_argument("--port", type=int, default=9000, help="TCP port")
    client.add_argument("--nick", required=True, help="nickname")

    parser.add_argument("--demo", action="store_true", help="run the offline demo and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()
    if args.mode == "server":
        return run_server(args.host, args.port)
    if args.mode == "client":
        return run_client(args.host, args.port, args.nick)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
