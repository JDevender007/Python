"""Packet capture analysis: protocol stats, talkers, ports, and timelines.

Packets are analysed offline — either from a bundled synthetic capture built
with scapy (the demo) or from a `.pcap` file you provide. Live sniffing is
supported behind an explicit `--live` flag and requires Npcap/WinPcap plus
authorization on the network you capture.

Everything the demo does happens on the local machine with generated packets:
no network, no privileged capture.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# Silence scapy's chatty import-time loggers before loading its layers.
for _name in ("scapy.runtime", "scapy.loading", "scapy.utils"):
    logging.getLogger(_name).setLevel(logging.ERROR)
# scapy's ipsec module triggers a third-party TripleDES deprecation warning.
warnings.filterwarnings(
    "ignore", message=".*TripleDES.*", category=DeprecationWarning
)

from scapy.layers.dns import DNS, DNSQR  # noqa: E402
from scapy.layers.inet import ICMP, IP, TCP, UDP  # noqa: E402
from scapy.packet import Packet, Raw  # noqa: E402
from scapy.utils import rdpcap, wrpcap  # noqa: E402

LOG = logging.getLogger("packet.analyzer")

PROTOCOLS = ("TCP", "UDP", "ICMP", "DNS", "OTHER")


# --------------------------------------------------------------------------- #
# Packet records
# --------------------------------------------------------------------------- #
@dataclass
class PacketRecord:
    """Flat, analysis-friendly view of one packet."""

    index: int
    timestamp: float
    src: str
    dst: str
    proto: str
    src_port: int | None
    dst_port: int | None
    length: int
    info: str = ""

    @property
    def ports(self) -> tuple[int, ...]:
        return tuple(p for p in (self.src_port, self.dst_port) if p is not None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "src": self.src,
            "dst": self.dst,
            "proto": self.proto,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "length": self.length,
            "info": self.info,
        }


def record_from_scapy(packet: Packet, index: int) -> PacketRecord:
    """Convert a scapy packet into a PacketRecord."""
    timestamp = float(getattr(packet, "time", 0.0))
    src = dst = ""
    proto = "OTHER"
    src_port = dst_port = None
    info = ""

    if IP in packet:
        ip = packet[IP]
        src, dst = ip.src, ip.dst

    if DNS in packet:
        dns = packet[DNS]
        proto = "DNS"
        if UDP in packet:
            src_port = packet[UDP].sport
            dst_port = packet[UDP].dport
        elif TCP in packet:
            src_port = packet[TCP].sport
            dst_port = packet[TCP].dport
        if dns.qr == 0 and dns.qd is not None:
            info = f"query {dns.qd[DNSQR].qname!r}"
        elif dns.qr == 1:
            info = f"response rcode={dns.rcode}"
    elif TCP in packet:
        proto = "TCP"
        tcp = packet[TCP]
        src_port, dst_port = tcp.sport, tcp.dport
        info = f"flags={tcp.flags}"
        if Raw in packet:
            payload = bytes(packet[Raw].load)[:40]
            info += f" payload={payload!r}"
    elif UDP in packet:
        proto = "UDP"
        udp = packet[UDP]
        src_port, dst_port = udp.sport, udp.dport
        # udp.len is only computed once the packet is built; fall back to wire size
        info = f"len={udp.len if udp.len is not None else len(packet)}"
    elif ICMP in packet:
        proto = "ICMP"
        icmp = packet[ICMP]
        info = f"type={icmp.type} code={icmp.code}"
    elif IP in packet:
        proto = f"IP-{packet[IP].proto}"

    return PacketRecord(
        index=index,
        timestamp=timestamp,
        src=src or "-",
        dst=dst or "-",
        proto=proto,
        src_port=src_port,
        dst_port=dst_port,
        length=len(packet),
        info=info,
    )


def records_from_packets(packets: Iterable[Packet]) -> list[PacketRecord]:
    """Convert an iterable of scapy packets into indexed records."""
    return [record_from_scapy(pkt, i) for i, pkt in enumerate(packets)]


# --------------------------------------------------------------------------- #
# Synthetic demo capture (fully offline)
# --------------------------------------------------------------------------- #
def synthesize_demo_capture(start: float = 1_700_000_000.0) -> list[Packet]:
    """Build a small, realistic-looking capture entirely in memory.

    Contains a DNS exchange, an HTTP request/response pair on a TCP
    handshake, an ICMP echo, and NTP-style UDP traffic — enough to exercise
    every analysis path.
    """
    packets: list[Packet] = []
    t = start

    def add(packet: Packet, step: float) -> None:
        nonlocal t
        packet.time = t
        packets.append(packet)
        t += step

    # DNS query + response
    dns_q = IP(src="192.168.1.10", dst="8.8.8.8") / UDP(sport=51000, dport=53) / \
        DNS(rd=1, qd=DNSQR(qname="example.com"))
    add(dns_q, 0.02)
    dns_r = IP(src="8.8.8.8", dst="192.168.1.10") / UDP(sport=53, dport=51000) / \
        DNS(qr=1, aa=1, qd=DNSQR(qname="example.com"))
    add(dns_r, 0.30)

    # TCP handshake
    add(IP(src="192.168.1.10", dst="93.184.216.34") /
        TCP(sport=40001, dport=80, flags="S", seq=1000), 0.01)
    add(IP(src="93.184.216.34", dst="192.168.1.10") /
        TCP(sport=80, dport=40001, flags="SA", seq=5000, ack=1001), 0.01)
    add(IP(src="192.168.1.10", dst="93.184.216.34") /
        TCP(sport=40001, dport=80, flags="A", seq=1001, ack=5001), 0.05)

    # HTTP request with payload
    add(IP(src="192.168.1.10", dst="93.184.216.34") /
        TCP(sport=40001, dport=80, flags="PA", seq=1001, ack=5001) /
        Raw(load=b"GET /index.html HTTP/1.1\r\nHost: example.com\r\n\r\n"), 0.20)
    # HTTP response
    add(IP(src="93.184.216.34", dst="192.168.1.10") /
        TCP(sport=80, dport=40001, flags="PA", seq=5001, ack=1400) /
        Raw(load=b"HTTP/1.1 200 OK\r\nContent-Length: 13\r\n\r\nhello world\n"), 0.01)
    # FIN
    add(IP(src="192.168.1.10", dst="93.184.216.34") /
        TCP(sport=40001, dport=80, flags="FA", seq=1400, ack=5100), 0.02)

    # ICMP echo request + reply
    add(IP(src="192.168.1.10", dst="1.1.1.1") / ICMP(type=8, code=0, id=1, seq=1) /
        Raw(load=b"ping-payload"), 0.05)
    add(IP(src="1.1.1.1", dst="192.168.1.10") / ICMP(type=0, code=0, id=1, seq=1) /
        Raw(load=b"ping-payload"), 0.40)

    # NTP-style UDP chatter
    add(IP(src="192.168.1.10", dst="123.123.123.123") /
        UDP(sport=52000, dport=123) / Raw(load=b"\x1b" + b"\x00" * 47), 0.05)
    add(IP(src="123.123.123.123", dst="192.168.1.10") /
        UDP(sport=123, dport=52000) / Raw(load=b"\x24" + b"\x00" * 47), 0.05)

    # Extra DNS query for variety
    add(IP(src="192.168.1.11", dst="8.8.8.8") / UDP(sport=51111, dport=53) /
        DNS(rd=1, qd=DNSQR(qname="python.org")), 0.05)

    return packets


# --------------------------------------------------------------------------- #
# PCAP I/O
# --------------------------------------------------------------------------- #
def load_pcap(path: str | Path) -> list[PacketRecord]:
    """Read a pcap/pcapng file and return its records."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"pcap not found: {source}")
    try:
        packets = rdpcap(str(source))
    except Exception as exc:  # scapy raises assorted errors on bad files
        raise ValueError(f"could not read pcap {source}: {exc}") from exc
    if len(packets) == 0:
        raise ValueError(f"pcap contains no packets: {source}")
    return records_from_packets(packets)


def save_pcap(packets: list[Packet], path: str | Path) -> Path:
    """Write packets to a pcap file (used by tests and export)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    wrpcap(str(target), packets)
    return target


# --------------------------------------------------------------------------- #
# Filtering and analysis
# --------------------------------------------------------------------------- #
def apply_filters(
    records: list[PacketRecord],
    *,
    host: str | None = None,
    proto: str | None = None,
    port: int | None = None,
) -> list[PacketRecord]:
    """Filter records by host (src/dst), protocol name, or port (src/dst)."""
    result = records
    if host:
        result = [r for r in result if r.src == host or r.dst == host]
    if proto:
        wanted = proto.upper()
        result = [r for r in result if r.proto == wanted]
    if port is not None:
        result = [r for r in result if port in r.ports]
    return result


@dataclass
class CaptureReport:
    """Aggregated statistics over a set of packet records."""

    records: list[PacketRecord]
    protocol_counts: dict[str, int] = field(default_factory=dict)
    top_talkers: list[tuple[str, int, int]] = field(default_factory=list)
    top_ports: list[tuple[int, int, int]] = field(default_factory=list)
    timeline: list[tuple[int, int, int]] = field(default_factory=list)
    total_packets: int = 0
    total_bytes: int = 0
    duration_s: float = 0.0

    @property
    def avg_packets_per_s(self) -> float:
        return self.total_packets / self.duration_s if self.duration_s > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_packets": self.total_packets,
            "total_bytes": self.total_bytes,
            "duration_s": round(self.duration_s, 3),
            "avg_packets_per_s": round(self.avg_packets_per_s, 2),
            "protocol_counts": self.protocol_counts,
            "top_talkers": [
                {"ip": ip, "packets": pkts, "bytes": size}
                for ip, pkts, size in self.top_talkers
            ],
            "top_ports": [
                {"port": port, "packets": pkts, "bytes": size}
                for port, pkts, size in self.top_ports
            ],
            "timeline": [
                {"second": sec, "packets": pkts, "bytes": size}
                for sec, pkts, size in self.timeline
            ],
            "packets": [r.to_dict() for r in self.records],
        }


def analyze(records: list[PacketRecord], top: int = 5) -> CaptureReport:
    """Compute protocol counts, talkers, ports, and a 1s timeline."""
    report = CaptureReport(records=list(records))
    if not records:
        return report

    report.total_packets = len(records)
    report.total_bytes = sum(r.length for r in records)

    times = [r.timestamp for r in records]
    report.duration_s = max(times) - min(times)

    for record in records:
        report.protocol_counts[record.proto] = report.protocol_counts.get(record.proto, 0) + 1

    # talkers: aggregate both directions per IP
    talkers: dict[str, list[int]] = {}
    for record in records:
        for ip in (record.src, record.dst):
            if ip in ("-", ""):
                continue
            entry = talkers.setdefault(ip, [0, 0])
            entry[0] += 1
            entry[1] += record.length
    report.top_talkers = sorted(
        ((ip, pkts, size) for ip, (pkts, size) in talkers.items()),
        key=lambda item: (-item[2], item[0]),
    )[:top]

    ports: dict[int, list[int]] = {}
    for record in records:
        for port in record.ports:
            entry = ports.setdefault(port, [0, 0])
            entry[0] += 1
            entry[1] += record.length
    report.top_ports = sorted(
        ((port, pkts, size) for port, (pkts, size) in ports.items()),
        key=lambda item: (-item[1], item[0]),
    )[:top]

    base = min(times)
    buckets: dict[int, list[int]] = {}
    for record in records:
        second = int(record.timestamp - base)
        entry = buckets.setdefault(second, [0, 0])
        entry[0] += 1
        entry[1] += record.length
    report.timeline = sorted(
        (sec, pkts, size) for sec, (pkts, size) in buckets.items()
    )
    return report


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_report(report: CaptureReport, show_packets: int = 0) -> str:
    """Human-readable report used by the CLI and demo."""
    lines: list[str] = []
    if report.total_packets == 0:
        return "No packets to analyse."

    lines.append(
        f"Packets  : {report.total_packets}  "
        f"({report.total_bytes:,} bytes, {report.duration_s:.2f}s, "
        f"{report.avg_packets_per_s:.1f} pkt/s)"
    )
    lines.append("Protocols: " + ", ".join(
        f"{name}={count}" for name, count in
        sorted(report.protocol_counts.items(), key=lambda kv: -kv[1])
    ))

    lines.append("Top talkers:")
    for ip, pkts, size in report.top_talkers:
        lines.append(f"  {ip:<16} {pkts:>4} pkts  {size:>8,} bytes")

    lines.append("Top ports:")
    for port, pkts, size in report.top_ports:
        lines.append(f"  {port:<16} {pkts:>4} pkts  {size:>8,} bytes")

    if report.timeline:
        lines.append("Timeline (packets per second):")
        peak = max(pkts for _, pkts, _ in report.timeline)
        for sec, pkts, _size in report.timeline:
            bar = "#" * max(1, round(pkts / peak * 20))
            lines.append(f"  +{sec:>3}s | {bar} {pkts}")

    if show_packets > 0:
        lines.append("Packets:")
        lines.append(f"  {'#':>3} {'PROTO':<5} {'SRC':<15} {'DST':<15} {'LEN':>5}  INFO")
        for record in report.records[:show_packets]:
            lines.append(
                f"  {record.index:>3} {record.proto:<5} {record.src:<15} "
                f"{record.dst:<15} {record.length:>5}  {record.info}"
            )
    return "\n".join(lines)


def run_demo() -> int:
    """Synthesise a capture in memory and analyse it — fully offline."""
    print("=" * 60)
    print(" NETWORK PACKET ANALYZER - offline demo")
    print(" Packets are generated locally; nothing touches the network.")
    print("=" * 60)

    packets = synthesize_demo_capture()
    records = records_from_packets(packets)
    report = analyze(records)

    print(f"\nSynthesised {len(packets)} packets (DNS, TCP/HTTP, ICMP, NTP).\n")
    print(render_report(report, show_packets=len(records)))

    # round-trip through a real pcap file to exercise file I/O
    demo_dir = Path(__file__).resolve().parent.parent / "data"
    demo_dir.mkdir(parents=True, exist_ok=True)
    pcap_path = demo_dir / "demo_capture.pcap"
    save_pcap(packets, pcap_path)
    reread = load_pcap(pcap_path)
    print(f"\nSaved and re-read {pcap_path.name}: {len(reread)} packets parsed back.")
    assert len(reread) == len(packets)

    # show a filter
    dns_only = apply_filters(records, proto="DNS")
    print(f"Filter proto=DNS -> {len(dns_only)} packets "
          f"({', '.join(str(r.dst_port) for r in dns_only)})")

    print("\nDemo completed successfully.")
    return 0
