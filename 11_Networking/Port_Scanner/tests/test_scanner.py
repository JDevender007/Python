"""Tests for the Port Scanner project."""

from __future__ import annotations

import json
import socket
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from scanner import (  # noqa: E402
    DEFAULT_HOST,
    probe_port,
    parse_ports,
    scan,
    summarize,
)


@pytest.fixture()
def local_server():
    """Start a temporary localhost TCP server and yield its port."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        try:
            conn, _ = server.accept()
            conn.close()
        except OSError:
            pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield port
    try:
        server.close()
    except OSError:
        pass


def test_parse_ports_list():
    assert parse_ports("80,443,8080") == [80, 443, 8080]
    assert parse_ports(" 80 , 443 ") == [80, 443]


def test_parse_ports_range():
    assert parse_ports("1-5") == [1, 2, 3, 4, 5]
    assert parse_ports("5-1") == [1, 2, 3, 4, 5]  # reversed range normalised


def test_parse_ports_mixed():
    assert parse_ports("22,80-82,443") == [22, 80, 81, 82, 443]


def test_parse_ports_invalid():
    with pytest.raises(ValueError, match="out of range"):
        parse_ports("70000")
    with pytest.raises(ValueError, match="too large"):
        parse_ports("1-99999")


def test_probe_open_port(local_server):
    result = probe_port(DEFAULT_HOST, local_server, timeout=1.0)
    assert result.open is True
    assert result.port == local_server
    assert result.latency_ms >= 0
    assert result.error == ""


def test_probe_closed_port():
    # port 1 (tcpmux) is virtually never listening on a dev machine
    result = probe_port(DEFAULT_HOST, 1, timeout=0.3)
    assert result.open is False
    assert result.error != ""


def test_scan_orders_by_port(local_server):
    results = scan(DEFAULT_HOST, [local_server, 1, 2], timeout=0.3, workers=5)
    assert [r.port for r in results] == sorted([local_server, 1, 2])
    assert any(r.open for r in results)


def test_scan_empty_ports():
    assert scan(DEFAULT_HOST, []) == []


def test_scan_too_many_ports():
    with pytest.raises(ValueError, match="too many"):
        scan(DEFAULT_HOST, list(range(1, 20_000)))


def test_summarize(local_server):
    results = scan(DEFAULT_HOST, [local_server, 1], timeout=0.3, workers=5)
    summary = summarize(results)
    assert summary["host"] == DEFAULT_HOST
    assert summary["scanned"] == 2
    assert summary["open"] == 1
    assert summary["closed"] == 1
    assert summary["open_ports"] == [local_server]


def test_summarize_empty():
    assert summarize([]) == {"host": "", "scanned": 0, "open": 0, "closed": 0, "open_ports": []}


def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_requires_ports(capsys):
    with pytest.raises(SystemExit):
        main([])
    assert "--ports" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert main(["--host", "127.0.0.1", "--ports", "1", "--timeout", "0.3",
                 "--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["summary"]["scanned"] == 1
    assert payload["results"][0]["port"] == 1


def test_cli_bad_ports(capsys):
    assert main(["--ports", "99999"]) == 2
    assert "out of range" in capsys.readouterr().err
