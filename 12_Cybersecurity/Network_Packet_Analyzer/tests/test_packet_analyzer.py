"""Tests for the Network Packet Analyzer project."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from packet_analyzer import (  # noqa: E402
    PacketRecord,
    analyze,
    apply_filters,
    load_pcap,
    record_from_scapy,
    records_from_packets,
    render_report,
    run_demo,
    save_pcap,
    synthesize_demo_capture,
)


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def demo_records() -> list[PacketRecord]:
    return records_from_packets(synthesize_demo_capture())


# --------------------------------------------------------------------------- #
# Record conversion
# --------------------------------------------------------------------------- #
def test_record_from_tcp_packet():
    from scapy.layers.inet import IP, TCP

    pkt = IP(src="10.0.0.1", dst="10.0.0.2") / TCP(sport=1234, dport=80, flags="S")
    pkt.time = 100.0
    record = record_from_scapy(pkt, 0)
    assert record.proto == "TCP"
    assert record.src == "10.0.0.1" and record.dst == "10.0.0.2"
    assert record.src_port == 1234 and record.dst_port == 80
    assert record.info == "flags=S"
    assert record.timestamp == 100.0
    assert record.length == len(pkt)
    assert record.ports == (1234, 80)


def test_record_from_dns_packet():
    from scapy.layers.dns import DNS, DNSQR
    from scapy.layers.inet import IP, UDP

    pkt = IP(src="192.168.1.5", dst="8.8.8.8") / UDP(sport=5555, dport=53) / \
        DNS(rd=1, qd=DNSQR(qname="example.org"))
    record = record_from_scapy(pkt, 1)
    assert record.proto == "DNS"
    assert record.dst_port == 53
    assert "example.org" in record.info


def test_record_from_icmp_packet():
    from scapy.layers.inet import ICMP, IP

    pkt = IP(src="1.1.1.1", dst="2.2.2.2") / ICMP(type=8, code=0)
    record = record_from_scapy(pkt, 2)
    assert record.proto == "ICMP"
    assert record.src_port is None and record.dst_port is None
    assert "type=8" in record.info


def test_record_non_ip_packet_is_other():
    from scapy.packet import Packet

    record = record_from_scapy(Packet(), 3)
    assert record.proto == "OTHER"
    assert record.src == "-" and record.dst == "-"


def test_record_to_dict_shape():
    record = PacketRecord(0, 1.0, "a", "b", "TCP", 1, 2, 60, "info")
    payload = record.to_dict()
    assert payload["src"] == "a" and payload["proto"] == "TCP"
    assert set(payload) == {"index", "timestamp", "src", "dst", "proto",
                            "src_port", "dst_port", "length", "info"}


# --------------------------------------------------------------------------- #
# Synthetic capture
# --------------------------------------------------------------------------- #
def test_synthesize_capture_size(demo_records):
    assert len(demo_records) >= 12


def test_synthesize_capture_has_all_protocols(demo_records):
    protos = {r.proto for r in demo_records}
    assert {"DNS", "TCP", "ICMP", "UDP"} <= protos


def test_synthesize_capture_timestamps_increasing(demo_records):
    times = [r.timestamp for r in demo_records]
    assert times == sorted(times)


def test_synthesize_capture_addresses(demo_records):
    assert any(r.src == "192.168.1.10" for r in demo_records)
    assert all(r.length > 0 for r in demo_records)


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
def test_filter_by_host(demo_records):
    result = apply_filters(demo_records, host="8.8.8.8")
    assert result
    assert all("8.8.8.8" in (r.src, r.dst) for r in result)


def test_filter_by_proto(demo_records):
    result = apply_filters(demo_records, proto="dns")  # case-insensitive
    assert result and all(r.proto == "DNS" for r in result)


def test_filter_by_port(demo_records):
    result = apply_filters(demo_records, port=80)
    assert result
    assert all(80 in r.ports for r in result)


def test_filter_combined(demo_records):
    result = apply_filters(demo_records, host="192.168.1.10", proto="DNS")
    assert all(r.proto == "DNS" for r in result)
    assert all(r.src == "192.168.1.10" or r.dst == "192.168.1.10" for r in result)


def test_filter_no_match(demo_records):
    assert apply_filters(demo_records, host="203.0.113.9") == []


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def test_analyze_totals(demo_records):
    report = analyze(demo_records)
    assert report.total_packets == len(demo_records)
    assert report.total_bytes == sum(r.length for r in demo_records)
    assert report.duration_s > 0
    assert sum(report.protocol_counts.values()) == len(demo_records)


def test_analyze_top_talkers_sorted(demo_records):
    report = analyze(demo_records, top=3)
    assert len(report.top_talkers) <= 3
    sizes = [size for _, _, size in report.top_talkers]
    assert sizes == sorted(sizes, reverse=True)
    # the local host exchanges the most bytes in the demo capture
    assert report.top_talkers[0][0] in {"192.168.1.10", "93.184.216.34"}


def test_analyze_top_ports(demo_records):
    report = analyze(demo_records, top=5)
    ports = [port for port, _, _ in report.top_ports]
    assert 53 in ports and 80 in ports
    assert len(report.top_ports) <= 5


def test_analyze_timeline_buckets(demo_records):
    report = analyze(demo_records)
    assert report.timeline
    assert report.timeline == sorted(report.timeline)
    total = sum(pkts for _, pkts, _ in report.timeline)
    assert total == len(demo_records)


def test_analyze_empty():
    report = analyze([])
    assert report.total_packets == 0
    assert report.avg_packets_per_s == 0.0
    assert render_report(report) == "No packets to analyse."


def test_analyze_single_packet_duration_zero():
    records = records_from_packets(synthesize_demo_capture())[:1]
    report = analyze(records)
    assert report.duration_s == 0.0
    assert report.avg_packets_per_s == 0.0


def test_report_to_dict_shape(demo_records):
    payload = analyze(demo_records).to_dict()
    for key in ("total_packets", "total_bytes", "duration_s", "protocol_counts",
                "top_talkers", "top_ports", "timeline", "packets"):
        assert key in payload
    assert payload["top_talkers"][0]["ip"]
    assert payload["packets"][0]["proto"]


# --------------------------------------------------------------------------- #
# PCAP I/O
# --------------------------------------------------------------------------- #
def test_pcap_roundtrip(tmp_path):
    packets = synthesize_demo_capture()
    path = save_pcap(packets, tmp_path / "cap.pcap")
    reread = load_pcap(path)
    assert len(reread) == len(packets)
    assert {r.proto for r in reread} == {r.proto for r in records_from_packets(packets)}


def test_pcap_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_pcap(tmp_path / "nope.pcap")


def test_pcap_invalid_file(tmp_path):
    bad = tmp_path / "bad.pcap"
    bad.write_bytes(b"this is definitely not a pcap file")
    with pytest.raises(ValueError, match="could not read"):
        load_pcap(bad)


def test_pcap_empty_file(tmp_path):
    empty = tmp_path / "empty.pcap"
    empty.write_bytes(b"")
    with pytest.raises(ValueError):
        load_pcap(empty)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_render_report_sections(demo_records):
    text = render_report(analyze(demo_records))
    assert "Packets  :" in text
    assert "Protocols:" in text
    assert "Top talkers:" in text
    assert "Top ports:" in text
    assert "Timeline" in text


def test_render_with_packet_list(demo_records):
    text = render_report(analyze(demo_records), show_packets=3)
    lines = text.splitlines()
    start = lines.index("Packets:")
    # header row + exactly 3 packet rows, nothing after
    assert "PROTO" in lines[start + 1]
    packet_lines = lines[start + 2:start + 5]
    assert len(packet_lines) == 3
    assert all(any(p in ln for p in ("DNS", "TCP", "UDP", "ICMP")) for ln in packet_lines)
    assert len(lines) == start + 5


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Protocols:" in out
    assert "re-read" in out


def test_cli_demo_direct(capsys):
    assert run_demo() == 0
    assert "offline demo" in capsys.readouterr().out


def test_cli_pcap_analysis(tmp_path, capsys):
    path = save_pcap(synthesize_demo_capture(), tmp_path / "cap.pcap")
    assert main(["--pcap", str(path)]) == 0
    out = capsys.readouterr().out
    assert "Packets  :" in out and "Done." in out


def test_cli_pcap_with_filters(tmp_path, capsys):
    path = save_pcap(synthesize_demo_capture(), tmp_path / "cap.pcap")
    assert main(["--pcap", str(path), "--proto", "DNS", "--host", "8.8.8.8", "--list", "5"]) == 0
    out = capsys.readouterr().out
    assert "DNS" in out


def test_cli_pcap_no_match(tmp_path, capsys):
    path = save_pcap(synthesize_demo_capture(), tmp_path / "cap.pcap")
    assert main(["--pcap", str(path), "--host", "203.0.113.9"]) == 0
    assert "No packets match" in capsys.readouterr().out


def test_cli_missing_pcap(tmp_path, capsys):
    assert main(["--pcap", str(tmp_path / "nope.pcap")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_invalid_pcap(tmp_path, capsys):
    bad = tmp_path / "bad.pcap"
    bad.write_bytes(b"garbage")
    assert main(["--pcap", str(bad)]) == 2
    assert "could not read" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    path = save_pcap(synthesize_demo_capture(), tmp_path / "cap.pcap")
    out_file = tmp_path / "report.json"
    assert main(["--pcap", str(path), "--json", str(out_file)]) == 0
    import json

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["total_packets"] >= 12
    assert payload["protocol_counts"]["TCP"] >= 1


def test_cli_live_refused(capsys):
    assert main(["--live", "Ethernet"]) == 2
    assert "authorized" in capsys.readouterr().err


def test_cli_requires_source(capsys):
    with pytest.raises(SystemExit):
        main([])
