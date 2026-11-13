<div align="center">

# 📋 Survey Data Analyzer

### Load, validate, and analyse survey responses — Likert distributions, top/bottom-box analysis, NPS, group comparisons, and cross-tabulations. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-Data%20Analysis-orange?style=for-the-badge&logo=pandas&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Survey Data Analyzer turns a CSV of survey responses into a decision-ready report: response counts and date range, satisfaction statistics (mean/median/std), Likert distributions with ASCII bars, top-box (4–5) and bottom-box (1–2) percentages, Net Promoter Score with promoter/passive/detractor splits, demographic stats, group comparisons (department / gender / remote), a satisfaction-bucket × group cross-tabulation, and a remote-vs-onsite split.

The loader is strict on purpose — missing columns, unparseable dates, empty or duplicate IDs, non-numeric values, fractional Likert scores, and out-of-range answers are rejected with precise messages.

Everything runs on local files: the bundled **deterministic** sample (500 responses) ships in `data/`, and `--demo` prints the full report with cross-checks (distribution sums to 100%, weighted group means reproduce the overall mean). **No network, no APIs, no API keys.**

---

# ✨ Features

- Strict schema validation: ranges (age 16–120, satisfaction 1–5, NPS 1–10), whole-number scores, unique response IDs
- Likert distribution with ASCII bars and share percentages
- Top-box / bottom-box / net-top-box analysis
- Net Promoter Score: promoters (9–10) − detractors (1–6)
- Group comparisons for department, gender, and remote — count, mean satisfaction, mean recommend, top-box %
- Satisfaction bucket (Low 1–2 / Mid 3 / High 4–5) × group cross-tab in row percentages
- JSON report export; bundled deterministic sample dataset (500 responses)
- 44 passing pytest tests

---

# 📂 Folder Structure

```text
Survey_Data_Analyzer/
│
├── src/
│   ├── main.py            # CLI: demo, --file, --group, --json, --quiet
│   └── survey_analyzer.py # loading, validation, NPS, analysis, rendering, demo
│
├── tests/
│   └── test_survey_analyzer.py
│
├── data/
│   └── survey_sample.csv  # 500 deterministic sample responses
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 14_Data_Analysis/Survey_Data_Analyzer

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
python src/main.py --file survey.csv

# Group by gender instead of department
python src/main.py --file survey.csv --group gender

# JSON report
python src/main.py --file survey.csv --group remote --json report.json
```

Input schema (header row required):

```csv
response_id,date,department,gender,age,tenure_years,satisfaction,recommend_score,remote
R-1000,2025-07-01,Engineering,F,30,2.5,4,9,yes
```

(`satisfaction` is 1–5, `recommend_score` is 1–10 for NPS.)

**Exit codes:** `0` = success · `2` = usage/schema/file error.

---

# 🧠 How It Works

```text
CSV ──► validate ──► distributions ──► report
                     ├─ Likert 1..5 (top/bottom box)
                     ├─ NPS from recommend_score
                     ├─ group tables (dept / gender / remote)
                     └─ bucket × group crosstab (row %)
                              │
                              ▼
                     text / JSON (+ cross-checks in --demo)
```

The demo verifies itself: bucket shares sum to 100%, the department-weighted mean equals the overall mean, and every cross-tab row sums to 100%.

---

# 🛠 Technologies

- Python
- pandas (loading, groupby, crosstab, aggregations)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- Likert-scale analysis: distributions, top/bottom-box, net scores
- Net Promoter Score composition (promoters/passives/detractors)
- Groupby aggregations and weighted-mean reconciliation
- Cross-tabulations with row-percentage normalization
- Defensive data validation (ranges, uniqueness, whole numbers)
- Report dataclasses with `to_dict()` for JSON serialization
- Test-driven development with fixture datasets

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**44 tests passed** covering every validation rule (ranges, duplicates, blanks, fractional scores), exact NPS and satisfaction math on hand-built frames, weighted-mean reconciliation, crosstab row sums, rendering, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
