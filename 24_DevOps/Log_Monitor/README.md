<div align="center">

# 📜 Log Monitor

### Parse structured and unstructured logs, aggregate per-service error rates, raise threshold alerts, and rank top offenders — fully offline on bundled sample logs.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Stdlib](https://img.shields.io/badge/Logs-Offline-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Log Monitor ingests local log files in **two common formats** and turns them into an operational report. Structured lines look like `2025-03-10 09:00:00 INFO service=api-gateway msg="GET /health 200 ok" duration=12ms`; unstructured lines look like `2025-03-10 09:30:17 ERROR [payment-adapter] timeout talking to upstream`. Both are parsed with strict validation — a missing timestamp, an unknown level, or a malformed line fails fast with a precise error (or is skipped and counted in `--lenient` mode).

The report shows record/level totals, a **per-service summary** (total, errors, error rate), **threshold alerts** for services whose error rate crosses `--threshold` with at least `--min-samples` records, and a **top-offenders ranking** sorted by error count (ties broken by name). The demo analyses the bundled `data/app.log` + `data/legacy.log` (80 records, 17 errors, 6 services), asserts every cross-check (alert set, top offender, deterministic re-parse), and re-parses to prove idempotency. **No network, no log shippers, no daemons — just local files.**

---

# ✨ Features

- Dual-format parser: `service=... msg="..."` structured lines and `[service] message` bracketed lines
- Strict validation: timestamp format, level whitelist (DEBUG→CRITICAL), service tag, fast-fail errors
- `--lenient` mode that skips malformed lines and reports how many were skipped
- Per-service aggregation: totals, per-level counts, `ERROR`/`CRITICAL` error rate
- Threshold alerts with a minimum-sample guard (no flapping on 1-line services)
- Top-offenders report with deterministic tie-breaking
- Minute-bucket error rates (`rate_by_minute`) for time-localised spikes
- `--json` export of the full aggregated payload
- Deterministic: pure parsing, identical output every run — demo asserts its own numbers
- 52 passing pytest tests

---

# 📂 Folder Structure

```text
Log_Monitor/
│
├── src/
│   ├── main.py        # CLI: --demo, --file, --threshold, --top, --json, --lenient
│   └── logmonitor.py  # parsing, aggregation, alerts, report, offline demo
│
├── tests/
│   └── test_logmonitor.py
│
├── data/
│   ├── app.log        # 60 structured lines, 4 services, 12 errors
│   └── legacy.log     # 20 bracketed lines, 2 services, 5 errors
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 24_DevOps/Log_Monitor

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: bundled logs, per-service report, alerts, top offenders
python src/main.py --demo

# Analyse your own log file with a stricter threshold
python src/main.py --file data/app.log --threshold 0.45 --top 3

# Skip malformed lines instead of failing
python src/main.py --file data/app.log --lenient

# Aggregated report as JSON
python src/main.py --file data/legacy.log --json report.json
```

Input schema (one record per line; blank lines ignored):

```text
# structured
2025-03-10 09:00:00 INFO service=api-gateway msg="GET /health 200 ok" duration=12ms

# unstructured / bracketed
2025-03-10 09:30:17 ERROR [payment-adapter] timeout talking to upstream
```

(Timestamp `YYYY-MM-DD HH:MM:SS`, level ∈ DEBUG/INFO/WARNING/ERROR/CRITICAL, service tag required.)

**Exit codes:** `0` = success · `2` = usage/file/parse error.

---

# 🧠 How It Works

```text
data/app.log + data/legacy.log
        │
        ▼  parse_line(): structured regex first, then bracketed regex
   LogRecord(timestamp, level, service, message, attributes)
        │                    │
        │                    └─ invalid → LogError (strict) or skip+count (lenient)
        ▼
   summarize() ──► per-service {total, errors, error_rate, level counts}
        │
        ├─► threshold_alerts(threshold, min_samples)   # rate >= T with enough data
        ├─► top_offenders(n)                           # errors desc, name asc
        └─► rate_by_minute()                           # spike buckets
        │
        ▼
   render_report() ──► text table  ──► (optional) --json payload
```

Details worth knowing:

- **`ERROR` and `CRITICAL` count as errors**; `WARNING` does not — the alert math is explicit and asserted.
- **The min-samples guard** stops a single failed request on a quiet service from paging anyone: a 1/1 line is rate 1.0 but never alerts when `--min-samples 5`.
- **Demo cross-checks**: exactly 80 records parse (0 skipped), the alert set at threshold 0.30 is exactly `{billing, payment-adapter}`, `billing` tops the list with 7 errors, per-service totals sum to the record count, and a full re-parse produces byte-identical summaries.
- **Fail-fast CLI**: `--threshold 0..1`, `--top >= 1`, and `--min-samples >= 1` are validated *before* any file is read.

---

# 🛠 Technologies

- Python 3
- `re` (dual-format line parsing), `dataclasses`, `collections.Counter`
- `datetime` (timestamp parsing + minute bucketing)
- argparse / json / logging / pathlib
- pytest

---

# 📚 Concepts Covered

- Defensive log parsing: format detection, layered fallbacks, precise errors
- Distinguishing malformed data (raise) from noisy data (`--lenient` + skip count)
- Error-rate aggregation with denominators you can trust
- Threshold alerts with minimum-sample guards against flapping
- Deterministic ranking with explicit tie-breakers
- Provenance of every number: totals always sum back to parsed records
- Fast-fail CLI validation before expensive work
- Idempotent, self-asserting demos

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**52 tests passed** covering both line formats, every validation rule (missing timestamp, unknown level, unrecognized format, empty lines), strict vs lenient file parsing, bundled-data integrity (80 records, 6 services), aggregation math (error rates, level counts, summary dicts), threshold/min-sample rules, top-offender ordering and tie-breaks, minute bucketing, report sections, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
