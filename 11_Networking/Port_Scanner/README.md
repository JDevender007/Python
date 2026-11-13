<div align="center">

# 🔍 Port Scanner

### A fast multithreaded TCP port scanner with service detection, latency reporting, and JSON export.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Port Scanner is a command line tool that probes TCP ports on a target host using a thread pool, then reports which ports are open, the service usually bound to each port, and the connection latency.

It is designed for **authorized testing only** — the default target is `127.0.0.1`, and you should only scan hosts you own or have explicit permission to test.

---

# ✨ Features

- Multithreaded scanning with a configurable worker pool
- Port lists (`80,443`), ranges (`1-1024`), or mixed (`22,80-82`)
- Well-known service name detection
- Per-port connection latency measurement
- Summary of open vs closed ports
- JSON export for later analysis
- Safe defaults: localhost, bounded port counts, short timeouts
- 15 passing pytest tests

---

# 📂 Folder Structure

```text
Port_Scanner/
│
├── src/
│   ├── main.py         # CLI entry point and reporting
│   └── scanner.py      # thread pool, probing, parsing, summaries
│
├── tests/
│   └── test_scanner.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 11_Networking/Port_Scanner

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo (scans a few localhost ports)
python src/main.py --demo

# Scan a range on localhost
python src/main.py --host 127.0.0.1 --ports 1-1024

# Specific ports with a JSON report
python src/main.py --host 127.0.0.1 --ports 22,80,443 --json results.json
```

---

# ⚠️ Ethical Use

Scan only systems you own or have written permission to test. Unauthorized scanning may be illegal in your jurisdiction. This tool defaults to `127.0.0.1` and caps scans at 10,000 ports to discourage misuse.

---

# 🛠 Technologies

- Python
- socket
- concurrent.futures
- argparse
- json
- logging

---

# 📚 Concepts Covered

- TCP connection handling
- Thread pools and concurrency
- Socket timeouts and error classification
- Range and list parsing with validation
- Latency measurement
- JSON serialisation
- CLI design with argparse
- Test-driven development with live sockets

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**15 tests passed** covering port parsing, open/closed probing against a real local server, scan ordering, summarisation, JSON output, and CLI error handling.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
