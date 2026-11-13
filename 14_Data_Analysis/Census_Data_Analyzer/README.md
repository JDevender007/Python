<div align="center">

# 🏛️ Census Data Analyzer

### Analyse regional census indicators — population and household totals, weighted vs unweighted averages, state aggregation, urban/rural splits, correlations, and income rankings. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-Data%20Analysis-orange?style=for-the-badge&logo=pandas&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Census Data Analyzer turns a CSV of regional demographic indicators into a full population report: total population and households, average household size, population-weighted versus unweighted indicator means, estimated poverty headcount, state-level aggregation (weighted income, poverty, urbanization), urban/rural region splits, an indicator correlation matrix, highest-income and highest-poverty rankings, and an income interquartile ratio as a simple inequality measure.

The core lesson is **weighting**: averaging regional poverty rates naively treats a 15,000-person district the same as a 420,000-person one. The report shows both numbers side by side so the difference is visible.

The loader validates every row — unique region IDs, positive whole-number population/households with `households ≤ population`, incomes in range, rates as fractions in 0..1, ages 18–100. Everything runs on local files: the bundled **deterministic** sample (120 regions across 6 states) ships in `data/`, and `--demo` prints the full report with cross-checks. **No network, no APIs.**

---

# ✨ Features

- Strict schema validation: unique IDs, population/household invariants, rate fractions
- Population- and household-weighted means next to naive unweighted means
- Estimated poverty headcount (`poverty_rate × population`) and share
- State-level aggregation with weighted income/poverty/urbanization
- Urban vs rural region split (majority-urban criterion)
- Indicator correlation matrix (income, poverty, bachelor, unemployment, age, urban)
- Highest-income / highest-poverty rankings by district name; income IQR ratio
- JSON report export; bundled deterministic sample (120 regions, 6 states)
- 44 passing pytest tests

---

# 📂 Folder Structure

```text
Census_Data_Analyzer/
│
├── src/
│   ├── main.py             # CLI: demo, --file, --top, --json, --quiet
│   └── census_analyzer.py  # loading, validation, weighted analysis, demo
│
├── tests/
│   └── test_census_analyzer.py
│
├── data/
│   └── census_sample.csv   # 120 deterministic regions across 6 states
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 14_Data_Analysis/Census_Data_Analyzer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: analyse the bundled sample with cross-checks
python src/main.py --demo

# Analyse your own data
python src/main.py --file census.csv

# Top 10 rankings + JSON report
python src/main.py --file census.csv --top 10 --json report.json
```

Input schema (header row required):

```csv
region_id,region_name,state,population,households,median_household_income,poverty_rate,unemployment_rate,bachelor_degree_pct,median_age,urban_population_pct
NL-01,Northland District 01,Northland,184230,71040,66800,0.131,0.049,0.301,37.4,0.412
```

(`poverty_rate`, `unemployment_rate`, `bachelor_degree_pct`, `urban_population_pct` are fractions in 0..1.)

**Exit codes:** `0` = success · `2` = usage/schema/file error.

---

# 🧠 How It Works

```text
CSV ──► validate rows ──► weighted analysis
                             ├─ weighted vs unweighted indicator means
                             ├─ state aggregation (groupby + weighted_mean)
                             ├─ urban/rural split
                             ├─ correlation matrix
                             └─ rankings + IQR inequality ratio
                                        │
                                        ▼
                               CensusReport → text / JSON
```

`--demo` proves its own math: state populations must partition the national total, urban + rural must cover every region, weighted income must sit inside the observed range, and the correlation matrix must be symmetric with a unit diagonal.

---

# 🛠 Technologies

- Python
- pandas (groupby, weighted means, corr, quantiles)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- Why aggregation needs weights (population vs. region averages)
- Weighted means and their bounds within observed data
- Groupby aggregation with multiple weighted indicators
- Estimated headcounts from rates (`rate × population`)
- Correlation matrices and interpreting sign/magnitude
- Interquartile ratio as a simple inequality measure
- Urban/rural binary segmentation on a continuous share
- Defensive validation of demographic data (invariants, ranges)

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**44 tests passed** covering every validation rule (duplicate IDs, household/population invariant, rate fractions, ranges), exact weighted-mean math (weighted 17,500 vs unweighted 15,000 on a hand-built frame), state partitioning, urban/rural coverage, correlation symmetry, ranking correctness, rendering, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
