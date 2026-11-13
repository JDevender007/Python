"""Tests for the SSH Automation Tool project."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import paramiko
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import collect_commands, main  # noqa: E402
from ssh_tool import (  # noqa: E402
    DEFAULT_HOST,
    CommandResult,
    LocalShell,
    SSHError,
    SSHSession,
    run_demo,
)


@pytest.fixture()
def session():
    """A connected session backed by the offline LocalShell."""
    s = SSHSession(host="offline", username="demo", backend=LocalShell())
    s.connect()
    yield s
    s.close()


# --------------------------------------------------------------------------- #
# Command execution
# --------------------------------------------------------------------------- #
def test_session_requires_connection():
    s = SSHSession(host="offline")
    with pytest.raises(SSHError, match="not connected"):
        s.run("whoami")


def test_run_whoami_and_pwd(session):
    assert session.run("whoami").stdout == "demo\n"
    assert session.run("pwd").stdout == "/home/demo\n"
    assert session.run("whoami").ok is True


def test_run_echo(session):
    result = session.run('echo "hello world"')
    assert result.stdout == '"hello world"\n'
    assert result.exit_status == 0


def test_run_unknown_command(session):
    result = session.run("definitely_not_a_command")
    assert result.exit_status == 127
    assert "command not found" in result.stderr
    assert result.ok is False


def test_run_false_and_true(session):
    assert session.run("true").ok is True
    assert session.run("false").ok is False
    assert session.run("false").exit_status == 1


def test_run_all(session):
    results = session.run_all(["whoami", "pwd", "nope"])
    assert [r.exit_status for r in [results[0], results[1]]] == [0, 0]
    assert results[2].exit_status == 127


# --------------------------------------------------------------------------- #
# File transfer
# --------------------------------------------------------------------------- #
def test_upload_and_ls(session, tmp_path):
    source = tmp_path / "hello.txt"
    source.write_text("payload", encoding="utf-8")

    sent = session.upload(source, "/home/demo/hello.txt")
    assert sent == len("payload")

    listing = session.run("ls /home/demo")
    assert "hello.txt" in listing.stdout


def test_upload_missing_local(session, tmp_path):
    with pytest.raises(SSHError, match="local file not found"):
        session.upload(tmp_path / "missing.txt", "/tmp/x")


def test_download_roundtrip(session, tmp_path):
    source = tmp_path / "data.bin"
    source.write_bytes(b"\x01\x02\x03binary")
    session.upload(source, "/home/demo/data.bin")

    target = session.download("/home/demo/data.bin", tmp_path / "restored.bin")
    assert target.read_bytes() == b"\x01\x02\x03binary"


def test_download_missing_remote(session, tmp_path):
    with pytest.raises(SSHError, match="remote file not found"):
        session.download("/home/demo/nope.txt", tmp_path / "out.txt")


def test_cat_after_upload(session, tmp_path):
    source = tmp_path / "note.txt"
    source.write_bytes(b"line one\nline two\n")  # bytes: no Windows CRLF translation
    session.upload(source, "/home/demo/note.txt")

    result = session.run("cat /home/demo/note.txt")
    assert result.stdout == "line one\nline two\n"
    assert result.ok


def test_cat_missing_file(session):
    result = session.run("cat /home/demo/missing.txt")
    assert result.exit_status == 1
    assert "No such file" in result.stderr


def test_ls_missing_directory(session):
    result = session.run("ls /nowhere")
    assert result.exit_status == 2
    assert "No such directory" in result.stderr


def test_relative_paths_resolve(session, tmp_path):
    source = tmp_path / "rel.txt"
    source.write_text("rel", encoding="utf-8")
    session.upload(source, "rel.txt")  # relative -> /home/demo/rel.txt
    assert session.run("cat rel.txt").stdout == "rel"


# --------------------------------------------------------------------------- #
# Session lifecycle
# --------------------------------------------------------------------------- #
def test_close_is_idempotent(session):
    session.close()
    assert session.connected is False
    session.close()
    with pytest.raises(SSHError, match="not connected"):
        session.run("whoami")


def test_context_manager():
    with SSHSession(backend=LocalShell()) as s:
        assert s.connected is True
        assert s.run("whoami").stdout == "demo\n"
    assert s.connected is False


def test_connect_refused_reports_error():
    # nothing listens on port 1 on localhost; offline-safe failure path
    s = SSHSession(host=DEFAULT_HOST, port=1, timeout=0.5, username="demo", password="x")
    with pytest.raises(SSHError, match="could not connect"):
        s.connect()


def test_connect_with_injected_backend_is_noop():
    shell = LocalShell()
    s = SSHSession(backend=shell)
    s.connect()  # must not touch the network
    assert s.connected is True
    assert s._backend is shell


# --------------------------------------------------------------------------- #
# Real paramiko surface (no network needed)
# --------------------------------------------------------------------------- #
def test_paramiko_key_generation_roundtrip(tmp_path):
    key = paramiko.RSAKey.generate(2048)
    key_path = tmp_path / "test_key"
    key.write_private_key_file(str(key_path))

    loaded = paramiko.RSAKey(filename=str(key_path))
    assert loaded.get_base64() == key.get_base64()


def test_command_result_helpers():
    ok = CommandResult("ls", 0, "a\n", "")
    bad = CommandResult("ls", 2, "", "boom")
    assert ok.ok is True and bad.ok is False
    assert ok.to_dict()["exit_status"] == 0
    assert bad.to_dict()["stderr"] == "boom"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "identical=True" in out


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])
    assert "--demo" in capsys.readouterr().err


def test_cli_unreachable_host_fails_cleanly(capsys):
    assert main([
        "--host", "127.0.0.1", "--port", "1", "--user", "demo",
        "--password", "x", "--timeout", "0.5", "--cmd", "whoami",
    ]) == 1
    assert "could not connect" in capsys.readouterr().err


def test_collect_commands_from_script(tmp_path):
    script = tmp_path / "cmds.txt"
    script.write_text("# comment\nwhoami\n\npwd\n", encoding="utf-8")

    args = SimpleNamespace(cmd=["echo hi"], script=script)
    commands = collect_commands(args)
    assert commands == ["echo hi", "whoami", "pwd"]


def test_run_demo_writes_files(tmp_path):
    assert run_demo(workdir=tmp_path) == 0
    assert (tmp_path / "hello.txt").exists()
    restored = (tmp_path / "restored.txt").read_text(encoding="utf-8")
    assert restored == (tmp_path / "hello.txt").read_text(encoding="utf-8")
