<div align="center">

# 💰 Cloud Cost Calculator

### Estimate monthly cloud spend from a small JSON infrastructure config — bundled rate cards, plan comparisons, savings tips, and budget alerts. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Cloud Cost Calculator turns a JSON description of your infrastructure — VMs, managed databases, block storage, and bandwidth egress — into a line-item bill with a monthly total, per-category breakdown, and budget status.

Pricing tables are **bundled and static** (illustrative aws/gcp rate cards), so the tool makes no API calls and never scrapes pricing pages. The calculator answers the questions that matter before you deploy: *What will this cost? What if I commit to 1- or 3-year reservations? Am I over budget? Where is the fat?*

---

# ✨ Features

- JSON infrastructure configs (compute, database, storage, bandwidth)
- Two bundled rate cards: `aws` and `gcp` with cross-provider shape aliases
- Purchase plans: `ondemand`, `1yr`, `3yr` — effective hourly rates
- Line-item bill with per-category subtotals
- Plan comparison: ondemand vs 1-year vs 3-year with dollar deltas
- Savings tips derived from the actual report (reservations, egress, storage tiering)
- Budget alerts: exit code 1 when over budget (CI-friendly)
- JSON output for scripting; `--provider` / `--budget` overrides
- 44 passing pytest tests

---

# 📂 Folder Structure

```text
CloudCost_Calculator/
│
├── src/
│   ├── main.py             # CLI: demo, --config, --compare, --json, --budget
│   └── cost_calculator.py  # rate cards, pricing, comparison, tips, rendering
│
├── tests/
│   └── test_cost_calculator.py
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 13_Cloud_Computing/CloudCost_Calculator

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: sample web-app footprint, plan comparison, savings tips
python src/main.py --demo

# Price your own config
python src/main.py --config infra.json

# Compare purchase plans + JSON export
python src/main.py --config infra.json --compare --json

# Budget gate for CI (exit 1 when over budget)
python src/main.py --config infra.json --budget 300
```

Example `infra.json`:

```json
{
  "provider": "aws",
  "hours_per_month": 730,
  "budget": 400,
  "resources": [
    {"type": "compute",   "instance": "t3.medium", "count": 3, "plan": "ondemand"},
    {"type": "database",  "instance": "db.m5.large", "count": 1},
    {"type": "storage",   "class": "gp3", "size_gb": 500},
    {"type": "bandwidth", "gb_out": 2000}
  ]
}
```

**Exit codes:** `0` = within budget · `1` = over budget · `2` = usage/config error.

---

# ⚠️ Note on Pricing Data

Bundled rates are **illustrative** and change over time. Before making real decisions, update `PROVIDERS` in `cost_calculator.py` with your negotiated prices or current provider list prices — the calculator's math stays the same.

---

# 🛠 Technologies

- Python (standard library only)
- json / dataclasses / argparse / logging
- pytest

---

# 📚 Concepts Covered

- Unit economics of cloud resources (per-hour, per-GB-month, per-GB egress)
- Reserved-instance effective-rate modelling
- Immutable dataclass rate cards
- JSON config validation with friendly errors
- Aggregation by category, budget thresholding
- Deep-copy config variants for what-if analysis
- Exit-code conventions for CI budget gates
- Cross-provider shape normalization
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**44 tests passed** covering every pricing path, config validation, totals, plan ordering, savings tips, config translation, rendering, demo idempotency, and every CLI mode — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
