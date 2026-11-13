<div align="center">

# 🤖 Machine Learning Projects

### A collection of Python projects covering supervised classification, regression, unsupervised clustering, text classification, and cross-validated model comparison — all runnable offline with `--demo`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This category explores the core of classical machine learning: a k-NN species classifier from raw measurements, a housing-price regression battle (linear vs random forest) with coefficient analysis, k-means customer segmentation chosen automatically by silhouette sweep, a bag-of-words Naive Bayes spam filter, and a harness that evaluates four classifiers under one cross-validation protocol and ranks them honestly.

Every project runs **fully offline** with `--demo` — bundled deterministic sample data ships with each project, no dataset or model is ever downloaded, and demos assert their own output. No network, no API keys.

---

# 🎯 Learning Objectives

- Split data honestly: stratified train/hold-out splits that never leak
- Encode categoricals for linear models (one-hot + passthrough pipelines)
- Compare a baseline against real models (mean predictor, always)
- Scale features before distance-based algorithms and know why
- Choose k for k-means with silhouette analysis instead of guessing
- Featurise text with bag-of-words n-grams and classify with Naive Bayes
- Report accuracy, precision, recall, F1, ROC-AUC — with fold-to-fold std
- Run stratified k-fold cross-validation inside the train split
- Validate datasets rigorously (ranges, classes, variance, minimums)
- Prove determinism: seeded models, idempotent demos, self cross-checks

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Iris_Species_Classifier | k-NN on bundled 150-row iris measurements → species predictions. | ✅
02 | Housing_Price_Predictor | Linear regression vs random forest with coefficient/importance analysis. | ✅
03 | Customer_Segmentation | k-means + silhouette sweep (k = 2..8) with ranked value profiles. | ✅
04 | Spam_Email_Classifier | Bag-of-words + Multinomial Naive Bayes with spam probabilities. | ✅
05 | Model_Evaluation_Harness | 4 models × stratified k-fold CV → ranked leaderboard + hold-out. | ✅

---

# 💡 Concepts Covered

- The Train/Test Split and Why Baselines Matter
- k-Nearest Neighbours (distance metrics, odd k, feature scaling)
- One-Hot Encoding inside `ColumnTransformer` + `Pipeline`
- Linear Coefficients read back through encoded feature names
- Random Forests and `feature_importances_`
- Mean-Predictor Baselines (RMSE ≈ std of the targets)
- Feature Scaling (`StandardScaler`) for distance-based models
- The k-Means Algorithm (centroids, `n_init` restarts, seeded runs)
- Silhouette Analysis and Automatic k Selection
- Cluster Profiling and Value Ranking
- Bag-of-Words, N-grams, and Stop Words (bundled with scikit-learn)
- Multinomial Naive Bayes with Laplace Smoothing (`alpha`)
- Precision / Recall / F1 and Confusion Matrices
- Stratified k-Fold Cross-Validation and mean ± std reporting
- ROC-AUC and Probability Thresholds
- Model Registries (`name → factory`) for pluggable evaluation
- Deterministic ML with Fixed Seeds

---

# 📁 Repository Structure

```text
16_Machine_Learning/
│
├── Iris_Species_Classifier/
├── Housing_Price_Predictor/
├── Customer_Segmentation/
├── Spam_Email_Classifier/
├── Model_Evaluation_Harness/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── data/             # bundled deterministic sample data
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- scikit-learn (k-NN, pipelines, ColumnTransformer, KMeans, Naive Bayes, metrics, StratifiedKFold)
- pandas / numpy (loading, validation, profiling tables)
- argparse / json / logging / dataclasses
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Iris Species Classifier | ✅ |
| Housing Price Predictor | ✅ |
| Customer Segmentation | ✅ |
| Spam Email Classifier | ✅ |
| Model Evaluation Harness | ✅ |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 16_Machine_Learning/Iris_Species_Classifier

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

---

# 📚 Skills Developed

- End-to-end supervised pipelines (load → validate → train → evaluate → predict)
- Honest model evaluation (baselines, hold-outs, cross-validation)
- Unsupervised analysis and cluster interpretation
- Text classification without external corpora
- Dataset validation and failure-mode design
- Deterministic demo design with self-verification
- Modular Programming and Type Hints
- Automated Testing

---

# 🚀 Key Learning Outcomes

- Train and evaluate k-NN, linear regression, random forest, and Naive Bayes on bundled data
- Explain every metric in the leaderboard and how CV keeps it honest
- Pick k for clustering from the data itself (silhouette sweep)
- Classify raw text with probabilities using only scikit-learn
- Prove a model beats a baseline before trusting it

---

# 🔮 Future Enhancements

- Hyper-parameter search (GridSearchCV) inside the harness
- Precision–recall curves and threshold tuning for spam
- PCA visualisation of clusters back onto 2-D
- Pipeline persistence with `joblib` (offline export)
- Multi-class extension for the evaluation harness

---

# 🤝 Contributions

Suggestions, improvements, and feedback are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
