<div align="center">

# 🏠 Housing Price Predictor

### Linear regression vs random forest on housing prices — one-hot encoded districts, hold-out metrics, coefficient/importance analysis, and single-house prediction. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Regression-FF7A00?style=for-the-badge&logo=scikitlearn&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Housing Price Predictor trains **two regressors** on the same housing listings — a regularized-free **linear regression** (interpretable coefficients) and a **random forest** (non-linear interactions) — and scores both against a **mean-predictor baseline** on a held-out split. The report shows RMSE, MAE, and R² for all three, the linear coefficients ranked by magnitude, and the forest's feature importances.

The loader validates every column: plausible size/distance/floor ranges, whole-number rooms and floors, strictly 0/1 lift and garden flags, and a known district name (case-insensitive, title-cased on load). Predictions go through the better hold-out model and take a single comma-separated house description.

Everything runs on local files: the bundled **deterministic** sample (400 synthetic listings, 5 districts) ships in `data/`, and `--demo` trains, reports, predicts sample houses, and cross-checks its own metrics. **No network, no dataset downloads, no model artifacts fetched.**

---

# ✨ Features

- Linear regression pipeline: `OneHotEncoder(district)` + `ColumnTransformer(remainder="passthrough")`
- Random forest (200 trees, depth 12, seeded) on the same encoded features
- Mean-predictor baseline so "good" has a reference point
- Metrics: RMSE, MAE, R² for every model on the same split
- Coefficient table (|value| ranked) and forest feature importances (sum ≈ 1)
- Single-house prediction: `--predict "180,5,3,3.0,12,1,1,Central"` (bundled data by default)
- Strict validation: ranges, whole numbers, binary flags, known districts, ≥ 40 rows
- JSON metrics export; deterministic seeds (`--seed`, `--test-size`)
- Bundled deterministic sample: 400 rows, 5 districts
- 57 passing pytest tests

---

# 📂 Folder Structure

```text
Housing_Price_Predictor/
│
├── src/
│   ├── main.py     # CLI: --demo, --file, --predict, --json, --seed
│   └── housing.py  # loading, training, metrics, prediction, report, demo
│
├── tests/
│   └── test_housing.py
│
├── data/
│   └── housing.csv # 400 deterministic listings (5 districts)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 16_Machine_Learning/Housing_Price_Predictor

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train both models, report, predict sample houses
python src/main.py --demo

# Train on your own CSV
python src/main.py --file housing.csv

# Train + predict one house + JSON metrics
python src/main.py --file housing.csv \
    --predict "180,5,3,3.0,12,1,1,Central" --json metrics.json

# Predict only (uses the bundled sample)
python src/main.py --predict "70,2,50,40.0,2,0,0,South"
```

Input schema (header row required):

```csv
size_sqm,rooms,age_years,dist_km,floor,has_lift,has_garden,district,price
120.0,4,8,6.5,7,1,0,Central,400000
```

Predict field order: `size_sqm,rooms,age_years,dist_km,floor,has_lift,has_garden,district`.

**Exit codes:** `0` = success · `2` = usage/schema/prediction error.

---

# 🧠 How It Works

```text
CSV ──► validate (ranges, binary, districts) ──► stratified split
                                                        │
              ┌─────────────────────────────────────────┤
              ▼                                         ▼
   OneHot(district)+LinearRegression        OneHot(district)+RandomForest
              │                                         │
              └────────────► RMSE / MAE / R² ◄──────────┘
                            (vs mean baseline)
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
          coefficients (ranked)          importances (sum ≈ 1)
                    └──────────────┬──────────────┘
                                   ▼
                    --predict → best model by hold-out RMSE
```

Two details worth noting:

- **Both models share the same encoding** via `ColumnTransformer` inside their own `Pipeline`, so a district unseen at predict time is ignored (`handle_unknown="ignore"`) instead of crashing.
- **The baseline is honest**: it predicts the training-split mean on the test split, giving `baseline_rmse ≈ std(test prices)` — any model that can't beat it has learned nothing.

`best_model_name` picks the lower hold-out RMSE (linear wins here: R² 0.967 vs 0.949), and `predict_price` routes every prediction through that winner.

---

# 🛠 Technologies

- Python
- scikit-learn (`ColumnTransformer`, `OneHotEncoder`, `LinearRegression`, `RandomForestRegressor`, metrics)
- pandas / numpy (loading, validation, coefficient tables)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- Encoding categoricals for linear models (one-hot + passthrough)
- Pipelines that keep preprocessing and model in one fitted object
- Regressor evaluation: RMSE vs MAE vs R² and why both errors matter
- Mean-predictor baseline as the "null model"
- Reading linear coefficients with one-hot groups
- `feature_importances_` for ensembles (and why they favor many-level features)
- Hold-out honesty: model selection never touches the test split
- Deterministic training with seeded splits and forests

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**57 tests passed** covering every validation rule (ranges, whole numbers, binary flags, districts, row counts), exact metric math on a hand-computed 3-point split, baseline comparisons, determinism across seeds, prediction ordering (central > peripheral, newer > older, larger > smaller), field validation, parsing helpers, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
