<div align="center">

# 🧪 Model Evaluation Harness

### Stratified k-fold cross-validation comparing four classifiers — accuracy, precision, recall, F1, ROC-AUC, hold-out confusion matrix, and a ranked leaderboard. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Evaluation-FF7A00?style=for-the-badge&logo=scikitlearn&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Model Evaluation Harness answers the question every modeller eventually asks: **which model should I actually use?** It loads a binary-label dataset, evaluates **four registered models** (logistic regression, decision tree, random forest, Gaussian naive Bayes) under one identical protocol — **stratified k-fold cross-validation on the training split plus a 25 % hold-out** — and ranks them by mean CV F1.

Every model reports five metrics (accuracy, precision, recall, F1, ROC-AUC) with **mean ± standard deviation across folds**, plus a hold-out confusion matrix for the winner. The spread between models is printed too, so you can see whether cross-validation is actually discriminating or the models are simply comparable on that dataset.

The loader validates the dataset: numeric finite features, a strict binary `0/1` label with ≥ 10 rows per class, ≥ 60 rows total, and no constant features (a zero-variance column is a bug in the data, not a learning signal). Everything runs on local files: the bundled **deterministic** sample (320 rows, 5 features, balanced 164/156 labels) ships in `data/`, and `--demo` evaluates every model, prints the leaderboard, and cross-checks its own metrics. **No network, no dataset downloads, no model artifacts fetched.**

---

# ✨ Features

- Model registry: `logistic_regression`, `decision_tree`, `random_forest`, `naive_bayes` — each a `StandardScaler` + estimator `Pipeline`
- Stratified k-fold CV (2–10 folds, seeded) computed on the train split only — the 25 % hold-out stays untouched
- Five metrics per model: accuracy, precision, recall, F1, ROC-AUC — **mean and std across folds**
- Leaderboard ranked by mean CV F1; best model marked with its ± band
- Hold-out confusion matrix for the winning model
- CV F1 spread line: tells you whether the comparison was meaningful
- Strict validation: binary 0/1 labels, ≥ 60 rows, ≥ 10 per class, finite numeric features, no constant columns
- JSON export of the full comparison; `--list` prints the registry
- Deterministic: seeded splits and estimators, identical results every run
- Bundled deterministic sample: 320 rows, 5 features, balanced classes
- 51 passing pytest tests

---

# 📂 Folder Structure

```text
Model_Evaluation_Harness/
│
├── src/
│   ├── main.py     # CLI: --demo, --file, --list, --folds, --seed, --json
│   └── harness.py  # loading, registry, CV evaluation, ranking, report, demo
│
├── tests/
│   └── test_harness.py
│
├── data/
│   └── dataset.csv # 320 deterministic rows (5 features, 164/156 labels)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 16_Machine_Learning/Model_Evaluation_Harness

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: evaluate all 4 models, leaderboard + cross-checks
python src/main.py --demo

# Your own dataset (binary label column)
python src/main.py --file dataset.csv

# Custom CV folds + JSON export
python src/main.py --file dataset.csv --folds 8 --json comparison.json

# Show the model registry
python src/main.py --list
```

Input schema (header row required — any number of numeric feature columns):

```csv
feature_1,feature_2,feature_3,feature_4,feature_5,label
0.8421,-1.2034,0.5510,7.2000,4.1000,1
```

(`label` must be exactly `0` or `1`; ≥ 60 rows, ≥ 10 per class.)

**Exit codes:** `0` = success · `2` = usage/schema/evaluation error.

---

# 🧠 How It Works

```text
CSV ──► validate (binary label, ranges, variance) ──► stratified split
                                                             │
                        ┌────────────────────────────────────┤ 25% hold-out
                        ▼                                    ▼  (kept sealed)
          StratifiedKFold(shuffle, seed) on the train split
                        │
        ┌───────┬───────┼───────┬───────┐
        ▼       ▼       ▼       ▼       ▼  fold i: fit on k-1, score on 1
      model ──► accuracy / precision / recall / f1 / roc_auc
                        │
                        ▼  nanmean ± nanstd across folds
                 ModelScore (per model)
                        │
                        ▼
     rank by mean CV F1 ──► leaderboard ──► best model's hold-out confusion
```

Two protocol details worth noting:

- **CV runs inside the train split.** The 25 % hold-out is scored once per model, after cross-validation. That keeps the reported CV means honest — no fold ever trained on a row that also scored it — while the hold-out gives a second, independent read.
- **Every model sees the same splits.** The `StratifiedKFold` is built from the same seed for all four models, so differences in the leaderboard come from the *models*, not from lucky folds. F1 is used for ranking because it balances precision and recall on the positive class, and its fold-to-fold std shows how stable that score is.

The demo's cross-checks re-run the whole harness and assert determinism, metric bounds, that the confusion matrix counts exactly `ceil(0.25 · n)` rows, and that hold-out F1 sits within 0.35 of the CV mean — if that ever fails, the protocol is broken.

---

# 🛠 Technologies

- Python
- scikit-learn (`StratifiedKFold`, `train_test_split`, `Pipeline`, `StandardScaler`, classifiers, metrics)
- pandas / numpy (loading, validation, nanmean/nanstd)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- Why k-fold cross-validation beats a single train/test split
- Stratification: preserving class ratios in every fold
- Mean ± std as the honest way to report a score
- Keeping a hold-out set sealed from model selection
- Ranking models on one shared metric (F1) while reporting the rest
- ROC-AUC vs accuracy on balanced and imbalanced data
- Zero-variance feature detection
- Building a reusable model registry with factories (fresh estimator per fold)
- Deterministic evaluation pipelines with seeded splitters

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**51 tests passed** covering every validation rule (binary labels, row/class minimums, non-finite values, constant features), the registry contract, evaluation correctness (a monkeypatched spy proves `cv_means` really equals the nanmean of the per-fold scores and that the 5th scoring call is the hold-out), confusion-matrix row counts, ranking/best/`to_dict` behaviour, report sections, demo idempotency, and every CLI path — all offline. Extra cases pin the row/feature counts and fold label on the harness result, `to_dict` model order following the ranking, bounded hold-out and CV metrics, ASCII-only report text, and the row floor.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
