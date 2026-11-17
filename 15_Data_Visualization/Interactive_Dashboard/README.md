<div align="center">

# 📊 Interactive Dashboard

### A self-contained interactive plotly dashboard — 2×2 panels, metric switcher, range slider — built offline from bundled data into a single HTML file. No CDN, no server, no network.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![plotly](https://img.shields.io/badge/plotly-Interactive-orange?style=for-the-badge&logo=plotly&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Interactive Dashboard turns a CSV of monthly segment performance into a single HTML file you can open in any browser — fully offline. The dashboard is a 2×2 grid: a monthly trend line chart with a **range slider** and a **3-button metric switcher** (Revenue / Cost / Orders), a grouped revenue-vs-cost bar chart, a revenue-share donut, and a revenue-vs-orders scatter with a least-squares trend line. A KPI header summarizes total revenue, margin %, growth, orders, AOV, best segment, and best month.

The key property: **plotly.js is embedded inline** (`include_plotlyjs=True`), so the saved HTML needs no CDN, no internet connection, and no web server — email it, share it, open it from a USB stick. The demo asserts this by rejecting any `<script src>`, `<link href="http…">`, or remote `<img>`/`<iframe>` in the output.

Everything runs on local files. The bundled **deterministic** sample (4 segments × 12 months) ships in `data/`, and `--demo` prints the KPIs, writes `output/dashboard.html`, and cross-checks every number against the raw frame. **No network, no API keys.**

---

# ✨ Features

- Self-contained HTML export: plotly.js inlined, zero remote resources (verified by the demo)
- 2×2 dashboard: trend (range slider), grouped bars, donut share, scatter + trend line
- Metric switcher: Revenue / Cost / Orders buttons update the 12 line traces
- KPI header and text/JSON KPI export (`--kpis --json`)
- Strict CSV validation: `YYYY-MM` months, non-negative values, whole-number orders, unique (month, segment) rows
- KPI math proven against the frame: revenue, margin, growth (first → last month), AOV
- Bundled deterministic sample: 48 rows (4 segments × 12 months)
- 50 passing pytest tests

---

# 📂 Folder Structure

```text
Interactive_Dashboard/
│
├── src/
│   ├── main.py        # CLI: --demo, --build, --kpis, --file, --out, --json
│   └── dashboard.py   # loader, KPIs, figure builder, HTML export, demo
│
├── tests/
│   └── test_dashboard.py
│
├── data/
│   └── dashboard_sample.csv   # 48 deterministic rows (4 segments x 12 months)
│
├── output/
│   └── dashboard.html         # built by --demo (gitignored)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 15_Data_Visualization/Interactive_Dashboard

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Build output/dashboard.html from the bundled sample with cross-checks
python src/main.py --demo

# Print headline KPIs
python src/main.py --kpis

# KPIs as JSON
python src/main.py --kpis --json kpis.json

# Build a dashboard from your own CSV
python src/main.py --build --file my_data.csv --out site/index.html
```

Input schema (header row required):

```csv
month,segment,revenue,cost,orders
2025-01,Appliances,59900,35900,148
```

(`month` = `YYYY-MM`, numbers must be non-negative, `orders` whole numbers.)

**Exit codes:** `0` = success · `2` = usage/schema/file error.

---

# 🧠 How It Works

```text
CSV ──► validate ──► compute_kpis ──► build_dashboard ──► figure.to_html
                          │                │              (plotly.js inline)
                          ▼                ▼                        ▼
                     text / JSON     2x2 subplot grid        output/dashboard.html
                                       ├─ trend + range slider
                                       ├─ metric switcher (3 buttons)
                                       ├─ grouped bars
                                       ├─ donut share
                                       └─ scatter + OLS trend
```

The figure holds 17 traces: 12 line traces (4 segments × 3 metrics) where only the 4 revenue lines start visible, plus 2 bars, 1 pie, and 2 scatter traces. The metric switcher buttons each carry a full 17-slot visibility vector that flips which line group is shown while keeping the other panels on.

`run_demo` verifies its own output: KPIs must equal sums recomputed from the frame, the figure must have exactly 17 traces with a 3-button switcher and 9 default-visible traces, and the HTML must be >1 MB with no external script/stylesheet/image references.

---

# 🛠 Technologies

- Python
- plotly (`make_subplots`, `go.Scatter`/`go.Bar`/`go.Pie`, `updatemenus`, `rangeslider`)
- numpy (least-squares trend line)
- pandas (loading, validation, pivot_table)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- Self-contained HTML export vs CDN references (and how to verify it)
- plotly subplots with mixed types (`xy` + `domain`)
- Dropdown/updatemenus state: visibility vectors over traces
- Range sliders on time axes
- KPI derivation: growth, margin %, AOV from grouped sums
- Least-squares fit with `numpy.polyfit`
- Figure/trace accounting (why 17 traces, why 9 visible by default)
- Offline-first demo design with self-asserting cross-checks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**50 tests passed** covering loading/validation rules, exact KPI math on a hand-built two-month frame (growth 50.0%, margin 3.0%, AOV 10.0), figure structure (17 traces, 9 default-visible, 3-button switcher with 17-slot vectors, range slider, subplot titles), self-contained HTML (no external resources, >1 MB), demo idempotency/quiet/missing-sample, and every CLI path — all offline. Extra cases pin the exact KPI key set, best segment/month against `groupby`, the AOV and margin-percent identities, every report label, ASCII-only KPI text, the `METRICS` tuple, the figure type, and segment whitespace stripping.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
