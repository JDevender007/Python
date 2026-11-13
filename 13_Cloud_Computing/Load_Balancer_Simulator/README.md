<div align="center">

# ⚖️ Load Balancer Simulator

### An offline load balancer with five strategies, a health-check state machine, failover, and distribution stats — all in-process with a seeded RNG.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Load Balancer Simulator models the core behavior of a real L4/L7 balancer without opening a single socket. Backends are in-process objects with weights, failure rates, and connection counters; requests are served by a chosen strategy with automatic failover; a health-check state machine pulls failing backends out of rotation and lets them back in after consecutive good probes.

The demo tells a complete story in three phases: healthy traffic, an outage (`web-3` fails three probes and is pulled), and recovery (two good probes return it to rotation) — followed by a side-by-side comparison of round-robin, least-connections, weighted, and ip-hash distribution over identical traffic. Everything is **seeded and deterministic**: the same command always produces byte-identical output.

---

# ✨ Features

- Five strategies: `round_robin`, `least_connections`, `weighted` (nginx smooth WRR), `random`, `ip_hash`
- Health checker with configurable down/up consecutive-probe thresholds
- Automatic failover: each retry targets a *different* healthy backend
- Per-backend counters: served, failures, active connections, share
- Event log of failures, health transitions, and exhausted requests
- Seeded RNG — fully reproducible runs and tests
- JSON stats export; `--clients` distinct IPs for hashing experiments
- 41 passing pytest tests

---

# 📂 Folder Structure

```text
Load_Balancer_Simulator/
│
├── src/
│   ├── main.py           # CLI: demo, --requests, --strategy, --json
│   └── load_balancer.py  # Backend, HealthChecker, LoadBalancer, rendering
│
├── tests/
│   └── test_load_balancer.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 13_Cloud_Computing/Load_Balancer_Simulator

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: outage + recovery + strategy showcase
python src/main.py --demo

# Simulate traffic with a different strategy
python src/main.py --requests 5000 --strategy weighted

# Hash-based routing with 64 distinct clients, JSON stats
python src/main.py --requests 1000 --strategy ip_hash --clients 64 --json

# Tune failover (attempts per request)
python src/main.py --requests 500 --failover 3
```

---

# 🧠 How the Strategies Behave

| Strategy | Picks | Best for |
| --- | --- | --- |
| `round_robin` | next healthy in rotation | equal-capacity peers |
| `least_connections` | fewest in-flight requests | uneven request costs |
| `weighted` | smooth WRR by weight (3:2:1 → exactly proportional) | heterogeneous capacity |
| `random` | seeded random choice | simplicity, statistical balance |
| `ip_hash` | stable slot per client IP with healthy fallback | session affinity |

---

# 🛠 Technologies

- Python (standard library: hashlib, random, logging)
- argparse / json
- pytest

---

# 📚 Concepts Covered

- Load balancing algorithms and their trade-offs
- nginx smooth weighted round-robin
- Consistent-ish source hashing with failover probing
- Health-check thresholds (consecutive failure/success state machines)
- Retry semantics: distinct-candidate failover and attempt caps
- Connection accounting (active vs. cumulative)
- Deterministic simulation with seeded RNGs
- Distribution analysis and event logs
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**41 tests passed** covering backend validation, health-state transitions, all five strategies (including exact weighted proportions and hash stability), failover paths, stats/rendering, demo determinism, and every CLI mode — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
