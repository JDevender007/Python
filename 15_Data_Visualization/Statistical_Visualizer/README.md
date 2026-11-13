<div align="center">

# 📈 Statistical Visualizer

### Descriptive statistics, a Welch t-test, confidence intervals, and six statistical charts — histogram with normal fit, box plots, Q-Q plot, means with 95% CI, regression, and a correlation heatmap. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![matplotlib](https://img.shields.io/badge/matplotlib-Visualization-orange?style=for-the-badge&logo=matplotlib&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Statistical Visualizer analyses a CSV of measurements across groups and renders the six charts every statistics workflow needs: a **histogram with a fitted normal curve**, **box plots with Tukey outlier fences**, a **normal Q-Q plot**, **group means with 95% t-interval error bars**, a **scatter with least-squares regression**, and a **correlation heatmap**.

The inference side is implemented from scratch — no scipy: descriptive statistics (mean, median, sample std, quartiles, IQR, SEM, Fisher skewness), Tukey fences and outlier detection, z-scores, a 95% t-interval using a critical-value table with normal approximation for large df, **Welch's unequal-variance t-test** (Welch–Satterthwaite df and a p-value from the regularized incomplete beta function via Lentz's method), and Pearson correlation with a least-squares fit.

Everything runs on local files: the bundled **deterministic** sample (120 subjects, Control vs Treatment) ships in `data/`, and `--demo` prints the full report, renders all six PNGs, and cross-checks the math. **No network, no API keys.**

---

# ✨ Features

- Descriptive stats: n, mean, median, sample std/variance, quartiles, IQR, SEM, range, skewness
- Tukey outlier fences (1.5 × IQR) and outlier extraction
- Z-scores with a zero-variance guard
- 95% t confidence intervals (table-based critical values, normal approx for df > 60)
- Welch t-test: t, Welch–Satterthwaite df, two-sided p (incomplete-beta implementation)
- Pearson r, r², slope, intercept via `numpy.polyfit`
- Six charts, uniform `(data → Figure)` registry, Agg backend, no figure leaks
- Bundled deterministic sample: 120 rows, 2 groups
- 66 passing pytest tests

---

# 📂 Folder Structure

```text
Statistical_Visualizer/
│
├── src/
│   ├── main.py      # CLI: --demo, --file, --chart, --list, --json, --out
│   └── stats_viz.py # loading, stats, t-test, correlation, 6 charts, demo
│
├── tests/
│   └── test_stats_viz.py
│
├── data/
│   └── measurements.csv   # 120 deterministic rows (Control / Treatment)
│
├── output/                 # rendered PNGs (created by --demo, gitignored)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 15_Data_Visualization/Statistical_Visualizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: analyse the bundled sample and render all 6 charts
python src/main.py --demo

# Analyse your own measurements
python src/main.py --file measurements.csv

# One chart to a custom folder
python src/main.py --file measurements.csv --chart qq --out graphs

# JSON report
python src/main.py --file measurements.csv --json report.json

# Chart catalog
python src/main.py --list
```

Input schema (header row required):

```csv
subject_id,group,score,age,improved
S-001,Control,49.07,41.2,yes
```

(`group` needs ≥ 2 groups with ≥ 3 rows each; `improved` is `yes`/`no`; `age` 0–120.)

**Exit codes:** `0` = success · `2` = usage/schema/chart-name error.

---

# 🧠 How It Works

```text
CSV ──► validate ──► describe() per group ──► Welch t-test ──► report
                          │                        │
                          ├─ Tukey fences          ├─ t, df (Welch-Satterthwaite)
                          ├─ z-scores              └─ p = 2 * T_sf(|t|, df)
                          └─ 95% t-interval
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼             ▼            ▼           ▼             ▼
       histogram+fit   box+fences    Q-Q plot   means+95%CI   regression/heatmap
```

The p-value uses the survival function of Student's t, computed as `0.5 · I_x(df/2, 1/2)` where `I` is the regularized incomplete beta evaluated with a modified Lentz continued fraction — the same approach used by scientific libraries, implemented here in ~30 lines.

`--demo` proves its own math: group counts must partition the sample, quartiles must be ordered within each group, p must lie in [0,1], |r| ≤ 1, and all six PNGs must be written with figures closed.

---

# 🛠 Technologies

- Python
- numpy (arrays, percentiles, polyfit, corrcoef)
- pandas (loading, validation, groupby)
- matplotlib (Agg backend — headless rendering)
- argparse / json / dataclasses / logging
- pytest

---

# 📚 Concepts Covered

- Sample vs population std (ddof=1) and standard error
- Quartiles, IQR, and Tukey outlier fences
- Skewness as the third standardized moment
- The t distribution: critical values, confidence intervals, Welch's test
- Welch–Satterthwaite degrees of freedom
- p-values from the incomplete beta function (Lentz's algorithm)
- Normal Q-Q plots and Blom plotting positions
- Acklam's rational approximation for the inverse normal CDF
- Least-squares regression, r vs r²
- Correlation matrices and heatmaps

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**66 tests passed** covering every validation rule, exact descriptive math on the classic `[2,4,4,4,5,5,7,9]` set (mean 5, std √(32/7)), t-table values, CI bracketing, Welch t-test on clear/similar/constant samples, p-value symmetry under sample swap, correlation edge cases, group partitioning, chart rendering (parametrized over all 6 charts, no figure leaks), demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
