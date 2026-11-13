<div align="center">

# 🌐 Web Traffic Analyzer

### Analyse a local access-log CSV — request totals, status classes, error rates, top paths, hourly/daily profiles, slowest endpoints, and top clients. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-Data%20Analysis-orange?style=for-the-badge&logo=pandas&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Web Traffic Analyzer turns a CSV export of HTTP access logs into an operations-ready report: request and session counts, unique clients, bandwidth and average response time, status-class breakdowns (2xx/3xx/4xx/5xx) with an error rate, top paths by hits, slowest endpoints by average response time, a 24-hour traffic profile with peak hour, busiest days, and top clients by request count.

The loader validates every row — parseable timestamps, known HTTP methods, paths starting with `/`, statuses in 100–599, non-negative bytes/durations, non-empty client and session IDs — and supports an inclusive `--since` / `--until` date window (strict `YYYY-MM-DD`, no lenient parsing).

Everything runs on local files: the bundled **deterministic** sample (1,664 requests over 14 days) ships in `data/`, and `--demo` prints the full report with cross-checks. **No network, no live servers, no scraping.**

---

# ✨ Features

- Strict log validation: timestamps, methods, path shape, status range, non-negative metrics
- Inclusive date-window filtering (`--since` / `--until`, strict format)
- Status classes with ASCII share bars and error rate (4xx + 5xx)
- Top paths (hits, share, avg ms) and slowest paths (avg response)
- 24-hour traffic profile with peak hour; busiest-days summary
- Top clients by requests; bandwidth formatting (B/KB/MB/GB)
- JSON report export; bundled deterministic sample (1,664 requests, 643 sessions)
- 50 passing pytest tests

---

# 📂 Folder Structure

```text
Web_Traffic_Analyzer/
│
├── src/
│   ├── main.py             # CLI: demo, --file, --top, --since, --until, --json
│   └── traffic_analyzer.py # loading, validation, analysis, rendering, demo
│
├── tests/
│   └── test_traffic_analyzer.py
│
├── data/
│   └── traffic_sample.csv  # 1,664 deterministic requests over 14 days
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 14_Data_Analysis/Web_Traffic_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: analyse the bundled sample with cross-checks
python src/main.py --demo

# Analyse your own log export
python src/main.py --file access.csv

# Top 10 paths, one-week window, JSON report
python src/main.py --file access.csv --top 10 \
    --since 2025-06-01 --until 2025-06-07 --json report.json
```

Input schema (header row required):

```csv
timestamp,method,path,status,bytes,duration_ms,client_ip,session_id
2025-06-01 09:23:41,GET,/,200,41253,86,203.0.113.7,S-00-00001
```

**Exit codes:** `0` = success · `2` = usage/schema/file/date-window error.

---

# 🧠 How It Works

```text
CSV ──► validate rows ──► optional --since/--until window ──► aggregates
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
        status classes    path tables      time profiles
        + error rate    hits / avg ms     hourly + daily
              └───────────────┼────────────────┘
                              ▼
                     TrafficReport → text / JSON
```

`--demo` proves its own math: status classes must partition all requests, hourly and daily profiles must sum to the request count, and the top path's hit count is recomputed by hand.

---

# 🛠 Technologies

- Python
- pandas (loading, groupby, dt.hour/dt.normalize profiles)
- argparse / json / logging / re
- pytest

---

# 📚 Concepts Covered

- Access-log anatomy: methods, status codes, sessions, bytes
- Status-class partitioning and error-rate calculation
- Groupby aggregations: hits, shares, average latency
- Time-bucket profiles with `dt.hour` and `dt.normalize()`
- Strict vs. lenient date parsing (regex-gated inputs)
- Inclusive date-window filtering with an exclusive upper bound
- Human-readable byte formatting (binary units)
- Report dataclasses with `to_dict()` for JSON serialization

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**50 tests passed** covering every validation rule (timestamps, methods, paths, statuses, negatives, blanks), date-window filtering (since/until/ordering/empty/bad format), exact status-class and error-rate math, top/slowest path ordering, hourly/daily sums, formatting helpers, rendering, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
