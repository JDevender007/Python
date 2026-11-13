<div align="center">

# 📡 Network Monitor

### A host network monitor that reports interface bandwidth, connection tables, top talkers, and system load — with CSV and JSON export.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![psutil](https://img.shields.io/badge/psutil-powered-14B8A6?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Network Monitor samples your machine's network state using `psutil` and prints a readable report: per-interface throughput in Mbps, the active connection table, the processes moving the most data, and CPU/memory load.

Rate calculation works by diffing two counter snapshots, so the first pass establishes a baseline and the second reports real throughput.

---

# ✨ Features

- Per-interface send/receive rates in Mbps (delta-based)
- Total transferred volume and error counters per interface
- Active TCP/UDP connection table with PIDs
- Top talkers ranked by cumulative process I/O
- CPU and memory percentage in the same snapshot
- Continuous watch mode with configurable interval
- CSV export of the interface table, JSON export of the full snapshot
- Graceful degradation when a counter is permission-denied
- 14 passing pytest tests

---

# 📂 Folder Structure

```text
Network_Monitor/
│
├── src/
│   ├── main.py         # CLI: demo, watch mode, CSV/JSON export
│   └── monitor.py      # collectors, snapshot model, formatting
│
├── tests/
│   └── test_monitor.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 11_Networking/Network_Monitor

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Two snapshots so throughput rates are calculated
python src/main.py --demo

# Refresh every 2 seconds
python src/main.py --watch --interval 2

# Take 5 snapshots and export them
python src/main.py --count 5 --csv interfaces.csv --json snapshot.json
```

---

# 🛠 Technologies

- Python
- psutil
- csv
- json
- argparse
- logging

---

# 📚 Concepts Covered

- Counter-based rate calculation (delta / elapsed time)
- Sampling and baseline management
- Process and socket inspection
- Graceful handling of permission errors
- Dataclass modelling of snapshots
- Tabular report formatting
- CSV and JSON serialisation
- CLI design with argparse

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**14 tests passed** covering sampling, rate baselines, reset behaviour, connection and talker shapes, snapshot rendering, and CLI export paths.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
