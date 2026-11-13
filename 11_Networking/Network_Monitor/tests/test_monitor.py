"""Tests for the Network Monitor project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main, write_csv  # noqa: E402
from monitor import (  # noqa: E402
    InterfaceSample,
    MonitorSnapshot,
    format_snapshot,
    interface_samples,
    list_connections,
    require_psutil,
    reset_counters,
    take_snapshot,
    top_talkers,
)


def test_psutil_available():
    require_psutil()  # must not raise in this environment


def test_interface_samples_have_names():
    reset_counters()
    samples = interface_samples()
    assert isinstance(samples, list)
    assert len(samples) >= 1
    for sample in samples:
        assert sample.name
        assert sample.total_sent_mb >= 0
        assert sample.total_recv_mb >= 0
        assert sample.to_dict()["name"] == sample.name


def test_rate_calculation_needs_two_samples():
    reset_counters()
    first = interface_samples()
    # first pass has no baseline, so rates must be zero
    assert all(s.send_mbps == 0.0 and s.recv_mbps == 0.0 for s in first)

    second = interface_samples()
    assert len(second) == len(first)
    for sample in second:
        assert sample.send_mbps >= 0
        assert sample.recv_mbps >= 0


def test_reset_counters_clears_baseline():
    reset_counters()
    interface_samples()
    reset_counters()
    samples = interface_samples()
    assert all(s.send_mbps == 0.0 for s in samples)


def test_list_connections_shape():
    reset_counters()
    rows = list_connections(limit=10)
    assert isinstance(rows, list)
    assert len(rows) <= 10
    for row in rows:
        assert {"local", "remote", "status", "pid"} <= set(row)


def test_top_talkers_shape():
    rows = top_talkers(limit=3)
    assert isinstance(rows, list)
    assert len(rows) <= 3
    for row in rows:
        assert {"pid", "name", "io_mb"} <= set(row)
        assert row["io_mb"] >= 0


def test_take_snapshot():
    reset_counters()
    snapshot = take_snapshot(connection_limit=5, talker_limit=3)
    assert isinstance(snapshot, MonitorSnapshot)
    assert snapshot.timestamp > 0
    assert len(snapshot.connections) <= 5
    assert len(snapshot.top_talkers) <= 3
    payload = snapshot.to_dict()
    assert payload["cpu_percent"] >= 0
    assert "interfaces" in payload


def test_format_snapshot_renders_sections():
    reset_counters()
    snapshot = take_snapshot()
    text = format_snapshot(snapshot)
    assert "INTERFACE" in text
    assert "CONNECTIONS" in text
    assert "TOP TALKERS" in text
    assert "CPU" in text


def test_format_empty_snapshot():
    empty = MonitorSnapshot(timestamp=1.0)
    text = format_snapshot(empty)
    assert "INTERFACE" in text
    assert "CONNECTIONS (0)" in text


def test_interface_sample_dict_roundtrip():
    sample = InterfaceSample(name="lo", ip="127.0.0.1", send_mbps=1.5, recv_mbps=2.5)
    payload = sample.to_dict()
    assert payload["name"] == "lo"
    assert payload["send_mbps"] == 1.5
    assert payload["recv_mbps"] == 2.5


def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "INTERFACE" in out


def test_cli_csv_output(tmp_path, capsys):
    target = tmp_path / "interfaces.csv"
    assert main(["--csv", str(target)]) == 0
    content = target.read_text(encoding="utf-8")
    assert "name,ip,send_mbps" in content
    assert len(content.splitlines()) >= 2


def test_cli_json_output(tmp_path, capsys):
    target = tmp_path / "snapshot.json"
    assert main(["--json", str(target), "--connections", "3", "--top", "2"]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["connections"]) <= 3
    assert len(payload["top_talkers"]) <= 2
    assert "interfaces" in payload


def test_cli_watch_count(capsys):
    assert main(["--watch", "--count", "2", "--interval", "0.1"]) == 0
    out = capsys.readouterr().out
    assert "snapshot 1/2" in out
    assert "snapshot 2/2" in out
