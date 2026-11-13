"""Client library for the threaded TCP chat application."""

from __future__ import annotations

import socket
import threading

from server import PROTOCOL_SEP


class ChatClient:
    """Minimal synchronous client with a background reader thread."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9000, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.nickname = ""
        self._sock: socket.socket | None = None
        self._inbox: list[str] = []
        self._buffer = ""
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None

    # ------------------------------------------------------------------ #
    @property
    def connected(self) -> bool:
        return self._sock is not None

    def connect(self, nickname: str) -> str:
        """Open the connection and register a nickname. Returns the server ACK."""
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        self._sock = sock
        self._buffer = ""
        self.nickname = nickname
        self._send(f"NICK{PROTOCOL_SEP}{nickname}")
        response = self._readline()
        command, _, arg = response.partition(PROTOCOL_SEP)
        if command != "OK":
            sock.close()
            self._sock = None
            raise ConnectionError(arg or "nickname rejected")
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        return arg

    def close(self) -> None:
        """Ask the server to drop us, then close locally."""
        if self._sock is None:
            return
        try:
            self._send(f"QUIT{PROTOCOL_SEP}")
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass
        self._sock = None
        if self._reader is not None:
            self._reader.join(timeout=2.0)
            self._reader = None

    # ------------------------------------------------------------------ #
    def say(self, text: str) -> None:
        """Broadcast a chat message to the current room."""
        self._send(f"MSG{PROTOCOL_SEP}{text}")

    def join(self, room: str) -> None:
        """Switch rooms."""
        self._send(f"JOIN{PROTOCOL_SEP}{room}")

    def leave(self) -> None:
        """Return to the lobby."""
        self._send(f"LEAVE{PROTOCOL_SEP}")

    def who(self) -> None:
        """Request the member list of the current room."""
        self._send(f"WHO{PROTOCOL_SEP}")

    # ------------------------------------------------------------------ #
    def _send(self, payload: str) -> None:
        if self._sock is None:
            raise ConnectionError("not connected")
        self._sock.sendall((payload + "\n").encode("utf-8"))

    def _readline(self) -> str:
        """Read one newline-delimited message, keeping any remainder buffered."""
        if self._sock is None:
            raise ConnectionError("not connected")
        while "\n" not in self._buffer:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("connection closed")
            self._buffer += chunk.decode("utf-8", errors="replace")
        line, _, self._buffer = self._buffer.partition("\n")
        return line

    def _read_loop(self) -> None:
        """Continuously push incoming messages into the inbox."""
        assert self._sock is not None
        buffer = self._buffer  # continue where the handshake left off
        try:
            while True:
                # drain anything already buffered before blocking on recv
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    with self._lock:
                        self._inbox.append(line)
                try:
                    chunk = self._sock.recv(4096)
                except (socket.timeout, TimeoutError):
                    continue  # idle connection, keep listening
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
        except OSError:
            pass
        finally:
            self._buffer = buffer

    # ------------------------------------------------------------------ #
    def drain(self) -> list[str]:
        """Return and clear everything received so far."""
        with self._lock:
            messages, self._inbox = self._inbox, []
        return messages

    def wait_for(self, prefix: str, limit: int = 50) -> str | None:
        """Poll the inbox until a message starting with prefix arrives."""
        import time

        deadline = time.time() + self.timeout
        collected: list[str] = []
        while time.time() < deadline:
            for message in self.drain():
                collected.append(message)
                if message.startswith(prefix):
                    return message
            time.sleep(0.05)
        for message in collected:
            if message.startswith(prefix):
                return message
        return None


def demo(host: str = "127.0.0.1") -> int:
    """Spin up a server locally, connect two clients, and exchange messages."""
    from server import ChatServer

    server = ChatServer(host=host, port=0)
    address = server.start()
    print(f"Server listening on {address[0]}:{address[1]}")

    alice = ChatClient(*address)
    bob = ChatClient(*address)
    try:
        print("Alice ->", alice.connect("alice"))
        print("Bob   ->", bob.connect("bob"))
        alice.say("hello from alice!")
        bob.say("hi alice, bob here")
        alice.join("projects")
        bob.who()

        import time

        time.sleep(0.3)
        print("\nAlice inbox:")
        for line in alice.drain():
            print("   ", line)
        print("Bob inbox:")
        for line in bob.drain():
            print("   ", line)

        print("\nRooms:", server.room_names)
        print("Lobby members:", server.room_members("lobby"))
        print("Projects members:", server.room_members("projects"))
        print("\nDemo completed successfully.")
        return 0
    finally:
        alice.close()
        bob.close()
        server.stop()


if __name__ == "__main__":
    raise SystemExit(demo())
