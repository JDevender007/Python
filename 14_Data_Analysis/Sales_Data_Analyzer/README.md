<div align="center">

# 📊 Sales Data Analyzer

### Load, validate, and analyse a local sales CSV — totals, period trends, growth, segment breakdowns, and charts. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-Data%20Analysis-orange?style=for-the-badge&logo=pandas&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Sales Data Analyzer turns a CSV of orders into a decision-ready report: revenue and order totals, average order value, per-period revenue with an ASCII trend chart, period-over-period growth, revenue share by region and category, top products, and a moving-average trend line.

The loader is strict on purpose — missing columns, unparseable dates, non-numeric or negative values, and zero quantities are rejected with precise messages — and it **recomputes `revenue = quantity × unit_price`** so a stale CSV column can never skew the numbers.

Everything runs on local files: the bundled 704-order sample ships in `data/`, and `--demo` prints the full report with cross-checks. No network, no APIs.

---

# ✨ Features

- Strict CSV schema validation with precise error messages
- Automatic revenue recomputation (never trusts a stale column)
- Time buckets: `D`, `W`, `M`, `Q`, `Y`
- Period-over-period growth percentages (last + cumulative)
- Segment breakdowns: region, category, product — revenue, orders, units, share
- Top-N products and a moving-average trend line
- JSON report export and PNG chart export (matplotlib Agg)
- Bundled deterministic sample dataset (704 orders across 2024)
- 40 passing pytest tests

---

# 📂 Folder Structure

```text
Sales_Data_Analyzer/
│
├── src/
│   ├── main.py            # CLI: demo, --file, --period, --segment, --json, --chart
│   └── sales_analyzer.py  # loading, validation, analysis, rendering, demo
│
├── tests/
│   └── test_sales_analyzer.py
│
├── data/
│   └── sales_sample.csv   # 704 deterministic sample orders (2024)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 14_Data_Analysis/Sales_Data_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: analyse the bundled sample with cross-checks
python src/main.py --demo

# Analyse your own CSV
python src/main.py --file sales.csv

# Quarterly view, top 10 products
python src/main.py --file sales.csv --period Q --top 10

# Focus one segment + JSON report + trend chart
python src/main.py --file sales.csv --segment product --json report.json --chart trend.png
```

Input schema (header row required):

```csv
order_id,date,region,category,product,quantity,unit_price,revenue
ORD-1001,2024-01-05,North,Toys,Puzzle 1000pc,2,16.50,33.00
```

(`revenue` is recomputed from `quantity × unit_price` on load.)

**Exit codes:** `0` = success · `2` = usage/schema/file error.

---

# 🛠 Technologies

- Python
- pandas (loading, resampling, groupby aggregations)
- matplotlib (optional PNG chart export, Agg backend — headless)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- Data cleaning: type coercion, date parsing, invariant enforcement
- Resampled time-series bucketing (D/W/M/Q/Y with modern ME/QE/YE aliases)
- Groupby aggregations and revenue-share analysis
- Period-over-period growth rates
- Rolling (moving-average) trend smoothing
- Report dataclasses with `to_dict()` for JSON serialization
- Defensive loading: fail fast with precise, actionable errors
- Test-driven development with fixture datasets

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**40 tests passed** covering every validation rule (missing columns, bad dates, non-numeric/negative/zero values, stale revenue), all period buckets, growth, segment partitions, top products, moving averages, rendering, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
