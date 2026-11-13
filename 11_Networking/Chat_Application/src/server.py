"""Threaded TCP chat server.

Handles multiple clients, nicknames, rooms, and broadcast messaging.
Binds to localhost by default.
"""

from __future__ import annotations

import logging
import socket
import threading
from collections import defaultdict
from dataclasses import dataclass, field

LOG = logging.getLogger("chat.server")

PROTOCOL_SEP = "\x1e"  # record separator: COMMAND\x1eARG1\x1eARG2


@dataclass(eq=False)
class Client:
    """A connected chat participant (identity-based hashing so it can live in sets)."""

    sock: socket.socket
    address: tuple[str, int]
    nickname: str = ""
    room: str = "lobby"
    lock: threading.Lock = field(default_factory=threading.Lock)

    def send(self, text: str) -> None:
        """Send one newline-terminated message to this client."""
        try:
            with self.lock:
                self.sock.sendall((text + "\n").encode("utf-8", errors="replace"))
        except OSError:
            pass


class ChatServer:
    """A small rooms-based chat server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self.port = port
        self._server: socket.socket | None = None
        self._clients: set[Client] = set()
        self._nicknames: dict[str, Client] = {}
        self._rooms: dict[str, set[Client]] = defaultdict(set)
        self._running = False
        self._accept_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    @property
    def address(self) -> tuple[str, int]:
        """Actual bound address (port is chosen automatically when 0)."""
        if self._server is None:
            raise RuntimeError("server not started")
        return self._server.getsockname()[:2]

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> tuple[str, int]:
        """Bind, listen and start the accept loop in a background thread."""
        if self._running:
            return self.address
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(16)
        self._server = server
        self._running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        LOG.info("chat server listening on %s:%s", *self.address)
        return self.address

    def stop(self) -> None:
        """Stop the server and disconnect everybody."""
        self._running = False
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        with self._lock:
            clients = list(self._clients)
        for client in clients:
            self._drop(client, announce=False)
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2.0)
            self._accept_thread = None
        LOG.info("chat server stopped")

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _accept_loop(self) -> None:
        assert self._server is not None
        while self._running:
            try:
                sock, addr = self._server.accept()
            except OSError:
                break
            client = Client(sock=sock, address=addr)
            with self._lock:
                self._clients.add(client)
            threading.Thread(target=self._client_loop, args=(client,), daemon=True).start()

    def _client_loop(self, client: Client) -> None:
        buffer = ""
        try:
            # First message must be the nickname: "NICK\x1e<name>"
            buffer = self._recv_until(client, buffer)
            line, _, buffer = buffer.partition("\n")  # consume the handshake line
            command, _, nickname = line.partition(PROTOCOL_SEP)
            if command != "NICK" or not nickname.strip():
                client.send("ERR\x1enickname required")
                return
            nickname = nickname.strip()[:24]

            with self._lock:
                if nickname in self._nicknames:
                    client.send("ERR\x1enickname already taken")
                    return
                self._nicknames[nickname] = client
            client.nickname = nickname
            client.send(f"OK\x1e{nickname}")
            self._join_room(client, "lobby")
            self.broadcast(f"MSG\x1e* {nickname} joined the lobby", room="lobby")

            while self._running:
                buffer = self._recv_until(client, buffer)
                raw, buffer = buffer.split("\n", 1)
                self._handle_command(client, raw)
        except OSError:
            pass
        finally:
            self._drop(client)

    def _recv_until(self, client: Client, buffer: str) -> str:
        """Read from the socket until a newline arrives, returning full buffer."""
        while "\n" not in buffer:
            chunk = client.sock.recv(4096)
            if not chunk:
                raise OSError("connection closed")
            buffer += chunk.decode("utf-8", errors="replace")
        return buffer

    def _handle_command(self, client: Client, raw: str) -> None:
        command, _, rest = raw.partition(PROTOCOL_SEP)
        command = command.upper()

        if command == "MSG":
            text = rest.strip()
            if text:
                self.broadcast(f"MSG\x1e<{client.nickname}> {text}", room=client.room)
        elif command == "JOIN":
            room = (rest.strip() or "lobby")[:24]
            self._leave_room(client, announce=True)
            self._join_room(client, room)
            client.send(f"OK\x1ejoined {room}")
        elif command == "LEAVE":
            self._leave_room(client, announce=True)
            self._join_room(client, "lobby")
            client.send("OK\x1eback in lobby")
        elif command == "WHO":
            members = sorted(c.nickname for c in self._rooms[client.room])
            client.send("LIST\x1e" + "\x1f".join(members))
        elif command == "QUIT":
            client.send("OK\x1egoodbye")
            client.sock.close()
        else:
            client.send(f"ERR\x1eunknown command {command}")

    def _join_room(self, client: Client, room: str) -> None:
        with self._lock:
            self._rooms[room].add(client)
        client.room = room
        self.broadcast(f"MSG\x1e* {client.nickname} is in {room}", room=room)

    def _leave_room(self, client: Client, *, announce: bool) -> None:
        with self._lock:
            members = self._rooms.get(client.room)
            if members:
                members.discard(client)
            if announce:
                target = client.room
        if announce:
            self.broadcast(f"MSG\x1e* {client.nickname} left", room=target)

    def _drop(self, client: Client, *, announce: bool = True) -> None:
        with self._lock:
            self._clients.discard(client)
            if client.nickname and self._nicknames.get(client.nickname) is client:
                del self._nicknames[client.nickname]
            members = self._rooms.get(client.room)
            room = client.room
            if members:
                members.discard(client)
        if announce and client.nickname:
            self.broadcast(f"MSG\x1e* {client.nickname} left {room}", room=room)
        try:
            client.sock.close()
        except OSError:
            pass

    def broadcast(self, message: str, *, room: str | None = None) -> None:
        """Send a message to everyone in a room (or everyone if room is None)."""
        with self._lock:
            targets = (
                list(self._rooms.get(room, set())) if room else list(self._clients)
            )
        for client in targets:
            client.send(message)

    # ------------------------------------------------------------------ #
    # Introspection (used by tests and the demo)
    # ------------------------------------------------------------------ #
    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    @property
    def room_names(self) -> list[str]:
        with self._lock:
            return sorted(name for name, members in self._rooms.items() if members)

    def room_members(self, room: str) -> list[str]:
        with self._lock:
            return sorted(c.nickname for c in self._rooms.get(room, set()))
