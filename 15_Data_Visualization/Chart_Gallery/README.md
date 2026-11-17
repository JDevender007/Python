<div align="center">

# 🎨 Chart Gallery

### Ten chart types rendered offline with matplotlib's headless Agg backend — line, area, bar, stacked bar, ranked bar, histogram, scatter, pie, box, and heatmap. One dataset, one command, ten PNGs.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![matplotlib](https://img.shields.io/badge/matplotlib-Visualization-orange?style=for-the-badge&logo=matplotlib&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Chart Gallery is a reference implementation of the ten most useful chart types for business data, all driven from a single bundled CSV of monthly revenue across four regions. Each chart type is a small, uniform function (`frame -> Figure`) registered in a dictionary, so rendering any of them takes one call — and adding an eleventh is a three-line change.

Everything runs **fully offline** with the `Agg` backend: no GUI display, no network, no notebooks. `--demo` renders all ten PNGs into `output/` and asserts that every file was written, that no figures leak, and that the pivot/summary numbers behind the charts match the raw data.

---

# ✨ Features

- Ten chart types: line, area, grouped bar, stacked bar, ranked bar, histogram, scatter (with trend line), donut pie, box plot, heatmap
- Uniform registry: `CHART_TYPES[name] = (function, description)`
- Headless rendering via the Agg backend (works on servers/CI)
- Figure hygiene: every render closes its figure (no leaks, tested)
- Data helpers: `pivot()` (region × month matrix) and `summary_table()` (revenue/cost/orders/margin/AOV)
- `--list` catalog, single-chart rendering, custom `--out`, JSON `--manifest`
- Bundled deterministic sample: 4 regions × 12 months (48 rows)
- 52 passing pytest tests

---

# 📂 Folder Structure

```text
Chart_Gallery/
│
├── src/
│   ├── main.py      # CLI: --demo, --list, --chart, --out, --manifest
│   └── gallery.py   # loader, helpers, 10 chart functions, registry, demo
│
├── tests/
│   └── test_gallery.py
│
├── data/
│   └── gallery_sample.csv  # 48 deterministic rows (4 regions x 12 months)
│
├── output/          # rendered PNGs (created by --demo, gitignored)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 15_Data_Visualization/Chart_Gallery

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Render all 10 charts to output/ with cross-checks
python src/main.py --demo

# See what's available
python src/main.py --list

# Render a single chart to a custom folder
python src/main.py --chart heatmap --out graphs

# Your own data + JSON manifest of rendered files
python src/main.py --demo --file my_data.csv --manifest charts.json
```

Input schema (header row required):

```csv
month,region,revenue,cost,orders
2025-01,North,43900,31200,88
```

(`month` = `YYYY-MM`, `region` = any label, numbers must be non-negative.)

**Exit codes:** `0` = success · `2` = usage/data/chart-name error.

---

# 🧠 How It Works

```text
CSV ──► validate ──► pivot / summary_table ──► chart functions ──► PNG (Agg)
                                                    │
                                     CHART_TYPES registry
                                     name ──► (fn, description)
```

Each chart function builds its own `Figure`, so `render_chart()` can `tight_layout()`, `savefig()`, and `close()` it in a `finally` block — the reason `plt.get_fignums()` stays empty no matter how many charts you render.

---

# 📊 The Ten Charts

Chart | Shows | Best for
--- | --- | ---
line | revenue trend per region over months | change over time
area | stacked revenue area | parts of a whole over time
bar | revenue vs cost by region | grouped comparisons
stacked_bar | monthly revenue by region | composition per period
ranked_bar | revenue ranking with value labels | league tables
histogram | distribution of monthly revenue | spread and shape
scatter | revenue vs orders + least-squares trend | relationships
pie | revenue share donut | simple shares
box | revenue spread per region | outliers and quartiles
heatmap | region × month revenue matrix | dense pattern scanning

---

# 🛠 Technologies

- Python
- matplotlib (Agg backend — headless rendering)
- numpy (trend-line fit, stacking math)
- pandas (pivot, groupby, validation)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- The matplotlib object model: `subplots()`, axes, legends, colorbars
- The Agg backend: rendering without a display
- Figure lifecycle management (why and how to `close()`)
- Pivot tables for multi-series plotting
- Least-squares trend lines with `numpy.polyfit`
- Stacked composition vs grouped comparison charts
- Choosing chart types by question (trend, share, spread, relationship)
- Registry patterns for pluggable rendering

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**52 tests passed** covering loading/validation rules, `pivot`/`summary_table` math against the raw frame, the registry contract, **parametrized rendering of all 10 charts** (file written, >1 KB, no figure leak), directory creation, repeated-render leak checks, demo idempotency (files overwritten, not doubled), and every CLI path — all offline. Extra cases pin `pivot()`'s default column, the `KeyError` on an unknown column, the `summary_table` column set / revenue ordering / AOV identity, a non-empty title on all 10 charts, and one pie wedge per region.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
