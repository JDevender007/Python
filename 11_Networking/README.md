<div align="center">

# 🌐 Networking Projects

### A collection of Python projects covering socket programming, port scanning, chat systems, network monitoring, and remote automation.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This repository contains Python projects that demonstrate practical networking: scanning TCP ports, running a threaded chat server, monitoring live interface traffic, transferring files over FTP, and automating remote machines over SSH.

Every project defaults to `127.0.0.1`, runs fully offline with `--demo` where possible, and includes an ethical-use reminder — use these tools only on systems you own or are authorized to test.

---

# 🎯 Learning Objectives

- Program with TCP sockets (bind, listen, accept, connect)
- Design application-layer protocols with clear framing
- Build thread-per-client servers with shared state
- Measure network behaviour (ports, throughput, connections)
- Wrap library protocols (ftplib, paramiko) behind clean APIs
- Build offline test doubles for network services
- Handle timeouts, connection errors, and graceful teardown
- Practice test-driven development with live sockets

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Port Scanner | Multithreaded TCP port scanner with service names, latency, and JSON export. | ✅
02 | Chat Application | Threaded rooms-based TCP chat server and client with nicknames and broadcasting. | ✅
03 | Network Monitor | Interface bandwidth, connections, and top talkers via psutil, with CSV/JSON export. | ✅
04 | FTP Client | ftplib wrapper for upload/download/list with an offline in-memory demo backend. | ✅
05 | SSH Automation Tool | Remote command execution and SFTP transfers with an offline LocalShell backend. | ✅

---

# ⚠️ Ethical Use

These projects are for **authorized testing and education only**:

- Scan, connect, and administer only systems you own or have explicit permission to test.
- Defaults are `127.0.0.1` and localhost binding — keep them that way unless you know what you are doing.
- Never embed real credentials in code or commit private keys.

---

# 💡 Concepts Covered

- TCP Socket Programming
- Threaded Servers and Concurrency
- Application-Layer Protocol Design
- Buffered Stream Framing
- Port Scanning and Service Detection
- Bandwidth Sampling and Rate Calculation
- FTP and SFTP File Transfer
- SSH Automation with paramiko
- Offline Test Doubles for Network Services
- Error Handling and Timeouts
- Modular Programming and Type Hints
- Test-driven Development

---

# 📁 Repository Structure

```text
11_Networking/
│
├── Port_Scanner/
├── Chat_Application/
├── Network_Monitor/
├── FTP_Client/
├── SSH_Automation_Tool/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- socket / threading
- psutil
- ftplib
- paramiko
- argparse / json / csv
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Port Scanner | ✅ |
| Chat Application | ✅ |
| Network Monitor | ✅ |
| FTP Client | ✅ |
| SSH Automation Tool | ✅ |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 11_Networking/Port_Scanner

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

---

# 📚 Skills Developed

- Socket-level network programming
- Concurrent server design
- Protocol framing and parsing
- Live traffic measurement
- Remote automation and file transfer
- Offline testing strategies for network code
- CLI design and error reporting
- Automated Testing

---

# 🚀 Key Learning Outcomes

- Build real network tools in pure Python
- Test network code without hitting the internet
- Design protocols that survive packet fragmentation
- Keep tools safe by default (localhost, bounded scans)
- Apply clean coding practices to systems code

---

# 🔮 Future Enhancements

- asyncio-based variants of the chat server and scanner
- TLS-wrapped chat and file transfer
- Web dashboard for the network monitor
- SFTP sync/mirror mode for the SSH tool
- Packet capture with scapy
- Rate limiting and retry policies
- SSH jump-host / bastion support

---

# 🤝 Contributions

Suggestions, improvements, and feedback are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
