"""Tests for the FTP Client project."""

from __future__ import annotations

import sys
from pathlib import Path

import ftplib
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ftp_client import FTPClient, FTPError, LocalFTP, run_demo  # noqa: E402
from main import main  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    """A connected FTPClient backed by the in-memory LocalFTP server."""
    backend = LocalFTP()
    instance = FTPClient.__new__(FTPClient)  # skip the real socket connect
    instance.host, instance.port, instance.timeout = "local", 0, 5.0
    instance._ftp = backend  # type: ignore[assignment]
    instance.backend = backend  # type: ignore[attr-defined]
    yield instance
    instance.close()


def test_connect_returns_banner(client):
    assert "LocalFTP ready" in client.backend.banner
    assert client.connected is True


def test_upload_and_list(client, tmp_path):
    source = tmp_path / "hello.txt"
    source.write_text("hello world", encoding="utf-8")

    sent = client.upload(source, "hello.txt")
    assert sent == len("hello world")

    entries = client.list()
    names = [e.name for e in entries]
    assert "hello.txt" in names


def test_upload_missing_local_file(client):
    with pytest.raises(FTPError, match="local file not found"):
        client.upload("definitely_missing_file.xyz")


def test_download_roundtrip(client, tmp_path):
    source = tmp_path / "data.bin"
    source.write_bytes(b"\x00\x01\x02binary-payload")
    client.upload(source, "data.bin")

    target = tmp_path / "restored.bin"
    client.download("data.bin", target)
    assert target.read_bytes() == b"\x00\x01\x02binary-payload"


def test_download_missing_remote(client, tmp_path):
    with pytest.raises(FTPError, match="download failed"):
        client.download("nope.txt", tmp_path / "out.txt")


def test_delete(client, tmp_path):
    source = tmp_path / "temp.txt"
    source.write_text("x", encoding="utf-8")
    client.upload(source, "temp.txt")
    client.delete("temp.txt")
    assert "temp.txt" not in [e.name for e in client.list()]

    with pytest.raises(FTPError, match="delete failed"):
        client.delete("never-existed.txt")


def test_mkdir_and_rename(client, tmp_path):
    client.make_directory("archive")
    assert any(e.is_dir for e in client.list()) or "archive" in client.backend.directories

    source = tmp_path / "old.txt"
    source.write_text("v1", encoding="utf-8")
    client.upload(source, "old.txt")
    client.rename("old.txt", "new.txt")

    names = [e.name for e in client.list()]
    assert "old.txt" not in names
    assert "new.txt" in names


def test_list_order_dirs_first(client, tmp_path):
    client.make_directory("aaa_dir")
    source = tmp_path / "zzz.txt"
    source.write_text("z", encoding="utf-8")
    client.upload(source, "zzz.txt")

    entries = client.list()
    assert entries[0].is_dir is True


def test_requires_connection():
    instance = FTPClient.__new__(FTPClient)
    instance._ftp = None
    instance.host, instance.port, instance.timeout = "local", 0, 1.0
    with pytest.raises(FTPError, match="not connected"):
        instance.list()


def test_connect_failure_reports_error():
    instance = FTPClient(host="127.0.0.1", port=1, timeout=0.3)  # nothing listens on port 1
    with pytest.raises(FTPError, match="could not connect"):
        instance.connect()


def test_close_is_idempotent(client):
    client.close()
    assert client.connected is False
    client.close()  # second call must not raise


def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Content verified identical." in out


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])
    assert "--demo" in capsys.readouterr().err


def test_cli_action_without_server_fails(capsys, tmp_path):
    # port 1 has no FTP server -> clean error, non-zero exit
    assert main(["--host", "127.0.0.1", "--port", "1", "--timeout", "0.3", "--list"]) == 1
    assert "could not connect" in capsys.readouterr().err


def test_run_demo_writes_files(tmp_path):
    assert run_demo(workdir=tmp_path) == 0
    assert (tmp_path / "upload_sample.txt").exists()
    assert (tmp_path / "downloaded.txt").exists()
    assert (tmp_path / "downloaded.txt").read_text(encoding="utf-8") == (
        tmp_path / "upload_sample.txt").read_text(encoding="utf-8")
