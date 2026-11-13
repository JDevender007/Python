"""Tests for the Chat Application project."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from client import ChatClient  # noqa: E402
from main import main  # noqa: E402
from server import PROTOCOL_SEP, ChatServer  # noqa: E402


@pytest.fixture()
def server():
    """A started localhost chat server on an ephemeral port."""
    srv = ChatServer(host="127.0.0.1", port=0)
    srv.start()
    yield srv
    srv.stop()


def _connect(server: ChatServer, nick: str) -> ChatClient:
    client = ChatClient(*server.address, timeout=3.0)
    client.connect(nick)
    return client


def test_server_starts_and_stops(server):
    assert server.running is True
    host, port = server.address
    assert host == "127.0.0.1"
    assert port > 0


def test_single_client_join(server):
    alice = _connect(server, "alice")
    try:
        assert server.client_count == 1
        assert server.room_members("lobby") == ["alice"]
        assert "MSG" in alice.wait_for("MSG")
    finally:
        alice.close()


def test_duplicate_nickname_rejected(server):
    first = _connect(server, "alice")
    second = ChatClient(*server.address, timeout=3.0)
    try:
        with pytest.raises(ConnectionError, match="already taken"):
            second.connect("alice")
    finally:
        first.close()
        second.close()


def test_nickname_required(server):
    client = ChatClient(*server.address, timeout=3.0)
    try:
        client._sock = __import__("socket").create_connection(server.address, timeout=3.0)
        client._sock.sendall(f"NICK{PROTOCOL_SEP}   \n".encode())
        response = client._sock.recv(1024).decode()
        assert response.startswith("ERR")
    finally:
        client.close()


def test_broadcast_between_clients(server):
    alice = _connect(server, "alice")
    bob = _connect(server, "bob")
    try:
        time.sleep(0.2)
        alice.drain()
        bob.drain()

        bob.say("hello from bob")
        message = alice.wait_for("MSG")
        assert message is not None
        assert "<bob> hello from bob" in message
    finally:
        alice.close()
        bob.close()


def test_rooms_isolate_messages(server):
    alice = _connect(server, "alice")
    bob = _connect(server, "bob")
    try:
        time.sleep(0.2)
        alice.join("projects")
        time.sleep(0.2)
        alice.drain()
        bob.drain()

        # bob is still in the lobby, alice is in projects
        bob.say("lobby only")
        assert alice.wait_for("MSG") is None
        bob.drain()  # discard bob's own echo before the real assertion

        alice.say("projects only")
        assert bob.wait_for("MSG") is None
    finally:
        alice.close()
        bob.close()


def test_join_and_room_membership(server):
    alice = _connect(server, "alice")
    try:
        alice.join("random")
        time.sleep(0.2)
        assert "random" in server.room_names
        assert server.room_members("random") == ["alice"]
        assert server.room_members("lobby") == []
    finally:
        alice.close()


def test_who_lists_members(server):
    alice = _connect(server, "alice")
    bob = _connect(server, "bob")
    try:
        time.sleep(0.2)
        alice.who()
        response = alice.wait_for("LIST")
        assert response is not None
        assert "alice" in response and "bob" in response
    finally:
        alice.close()
        bob.close()


def test_leave_returns_to_lobby(server):
    alice = _connect(server, "alice")
    try:
        alice.join("projects")
        time.sleep(0.2)
        alice.leave()
        time.sleep(0.2)
        assert server.room_members("lobby") == ["alice"]
        assert server.room_members("projects") == []
    finally:
        alice.close()


def test_disconnect_cleans_state(server):
    alice = _connect(server, "alice")
    time.sleep(0.2)
    assert server.client_count == 1
    alice.close()
    time.sleep(0.3)
    assert server.client_count == 0
    assert server.room_members("lobby") == []


def test_unknown_command(server):
    alice = _connect(server, "alice")
    try:
        alice._send("TELEPORT\x1emoon")
        response = alice.wait_for("ERR")
        assert response is not None
        assert "unknown command" in response
    finally:
        alice.close()


def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_help_without_mode(capsys):
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()
