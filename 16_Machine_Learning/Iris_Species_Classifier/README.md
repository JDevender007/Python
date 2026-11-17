<div align="center">

# 🌸 Iris Species Classifier

### k-NN classification of iris flowers — training, hold-out and cross-validation metrics, confusion matrix, and single-flower prediction. Fully offline on the bundled dataset.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Machine%20Learning-FF7A00?style=for-the-badge&logo=scikitlearn&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Iris Species Classifier trains a k-nearest-neighbours model on the classic iris dataset (150 flowers, 3 species, 4 measurements) and reports the numbers that matter: hold-out accuracy, macro precision/recall/F1, a 5-fold stratified cross-validation score, and a confusion matrix. It also prints mean measurements per species so you can see *why* predictions work, and classifies a single flower given four numbers.

The loader validates sepal/petal ranges (a petal width of 9.9 cm is rejected, not silently scored) and requires at least two species with ≥ 5 rows each. Everything runs on local files: the bundled **deterministic** copy of iris ships in `data/`, and `--demo` trains, evaluates, and cross-checks its own metrics. **No network, no dataset downloads, no model files fetched from anywhere.**

---

# ✨ Features

- k-NN training with stratified 75/25 hold-out split (configurable `--k`, `--test-size`)
- Metrics: accuracy, macro precision/recall/F1, 5-fold stratified CV (train split only)
- Confusion matrix and per-class classification report
- Single-flower prediction via `--predict "5.1,3.5,1.4,0.2"`
- Feature means by species (interpretable model baseline)
- Strict validation: measurement ranges, known species labels, class counts
- k is clamped to the smallest training class instead of crashing
- JSON metrics export; bundled dataset copy (150 rows, balanced classes)
- 51 passing pytest tests

---

# 📂 Folder Structure

```text
Iris_Species_Classifier/
│
├── src/
│   ├── main.py            # CLI: --demo, --file, --k, --predict, --json
│   └── iris_classifier.py # loading, training, metrics, prediction, demo
│
├── tests/
│   └── test_iris_classifier.py
│
├── data/
│   └── iris.csv           # 150 rows (50 per species), bundled copy
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 16_Machine_Learning/Iris_Species_Classifier

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train, evaluate, predict sample flowers
python src/main.py --demo

# Train on your own CSV with 7 neighbours
python src/main.py --file iris.csv --k 7

# Classify one flower + JSON metrics
python src/main.py --file iris.csv --predict "5.1,3.5,1.4,0.2" \
    --json metrics.json
```

Input schema (header row required):

```csv
sepal_length,sepal_width,petal_length,petal_width,species
5.1,3.5,1.4,0.2,setosa
```

**Exit codes:** `0` = success · `2` = usage/schema/prediction error.

---

# 🧠 How It Works

```text
CSV ──► validate ranges/labels ──► stratified split ──► fit k-NN
                                                          │
                    ┌─────────────────────────────────────┤
                    ▼                                     ▼
             hold-out metrics                     5-fold stratified CV
          accuracy/P/R/F1 + confusion            F1 mean +/- std (train only)
                    └─────────────────────────────────────┤
                                                          ▼
                                  report + --predict (named-frame inference)
```

Two details worth stealing:

- **Stratification** keeps every species represented in both the train and test splits, so the metrics don't swing on a lucky shuffle (the split is seeded for reproducibility).
- **k clamping**: `n_neighbors` must not exceed the smallest training class, so a requested `--k 50` is reduced to what the split allows instead of raising a cryptic sklearn error at fit time.

Cross-validation runs on the *training portion only* — the hold-out test split is never touched by model selection, which is what keeps the reported numbers honest.

---

# 🛠 Technologies

- Python
- scikit-learn (`KNeighborsClassifier`, `train_test_split`, `StratifiedKFold`, metrics)
- pandas / numpy (loading, validation, confusion DataFrame)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- The k-nearest-neighbours classifier and the role of k
- Stratified train/test splits and why they matter for balanced metrics
- Macro precision / recall / F1 vs raw accuracy
- Confusion matrices and per-class classification reports
- K-fold cross-validation (and CV-on-train vs hold-out honesty)
- Feature ranges as input validation for inference
- Reproducible experiments with fixed seeds
- Feature-name consistency at predict time (DataFrame vs ndarray)

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**51 tests passed** covering every validation rule (ranges, unknown species, class sizes, non-numeric cells), metric correctness (accuracy recomputed from predictions, confusion matrix row counts), determinism across seeds, k clamping, prediction edge cases (missing/non-numeric/out-of-range measurements), parsing helpers, demo idempotency, and every CLI path — all offline. Extra cases pin the confusion matrix covering every species, the five-fold record, per-species means lying inside the observed range, petal-length ordering across species, k clamping, and stable repeat predictions.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
