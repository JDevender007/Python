<div align="center">

# 📦 Network Packet Analyzer

### Offline packet-capture analysis with scapy — protocol stats, top talkers, port activity, and timelines from a pcap file or a synthetic demo capture.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![scapy](https://img.shields.io/badge/scapy-2.5-2D2D2D?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Network Packet Analyzer reads packet captures and turns them into actionable statistics: protocol distributions, the busiest endpoints, the hottest ports, and a per-second activity timeline. It understands TCP flags and payloads, UDP, ICMP, and DNS queries/responses.

Analysis is **fully offline**: the demo synthesises a realistic 13-packet capture (DNS exchange, TCP handshake + HTTP request/response, ICMP echo, NTP chatter) entirely in memory, round-trips it through a real `.pcap` file, and prints the report — no network, no privileged capture, no Wireshark required. Point `--pcap` at any capture file you already have.

Live sniffing exists behind `--live` but is refused by default: it needs Npcap/WinPcap, elevated privileges, and **authorization on the network you capture**.

---

# ✨ Features

- PCAP/PCAPNG loading via scapy with clean error reporting
- Protocol counts: TCP, UDP, ICMP, DNS, other
- Top talkers (IPs by packets/bytes) and top ports
- Per-second activity timeline with ASCII bar chart
- Filters: `--host`, `--proto`, `--port` (combined)
- Packet listing with TCP flags, DNS names, ICMP types, payload previews
- Synthetic demo capture generated in memory + pcap round-trip
- JSON export for tooling
- `--live` is gated: refuses without explicit harness wiring
- 37 passing pytest tests

---

# 📂 Folder Structure

```text
Network_Packet_Analyzer/
│
├── src/
│   ├── main.py              # CLI: demo, --pcap, filters, --json, --live gate
│   └── packet_analyzer.py   # records, filters, analysis, rendering, pcap I/O
│
├── tests/
│   └── test_packet_analyzer.py
│
├── data/
│   └── demo_capture.pcap    # written automatically by the demo
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 12_Cybersecurity/Network_Packet_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Fully offline demo: synthesise + analyse + pcap round-trip
python src/main.py --demo

# Analyse an existing capture
python src/main.py --pcap capture.pcap

# Filtered analysis with a packet listing
python src/main.py --pcap capture.pcap --proto TCP --host 10.0.0.5 --list 20

# Focus on one port, deeper top lists, JSON export
python src/main.py --pcap capture.pcap --port 443 --top 10 --json report.json
```

---

# ⚠️ Ethical Use

Only capture traffic on networks you own or are explicitly authorized to monitor. Employee/customer traffic is protected by law in most jurisdictions. Live capture requires Npcap and usually admin rights — the CLI refuses `--live` by default so accidental (or scripted) sniffing can't happen; wire it into your own harness deliberately.

---

# 🛠 Technologies

- Python
- scapy (packet construction, pcap read/write)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- pcap file format and round-trip I/O
- Layer-2/3/4 dissection (IP, TCP/UDP, ICMP) and application layers (DNS)
- TCP flags: SYN, SYN-ACK, ACK, PSH-ACK, FIN-ACK
- DNS query vs. response fields (qr, rcode, qname)
- Aggregate analytics: counts, byte totals, top-N with tie-breaking
- Time-bucketed timelines from packet timestamps
- Filtering pipelines over structured records
- Offline test strategy: synthetic captures instead of live sniffing

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**37 tests passed** covering record conversion for every protocol, the synthetic capture, all filter combinations, analysis totals/talkers/ports/timeline, pcap round-trips and error paths, report rendering, and every CLI mode — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
