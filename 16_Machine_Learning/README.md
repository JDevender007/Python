<div align="center">

# 🤖 Machine Learning Projects

### Five classical-ML projects where the model is the easy part. The hard part is the number you print next to it: a silhouette that is not accuracy, a hold-out score that hides its split, an R² with no baseline, a cross-validation mean that averaged the wrong folds, and a text classifier whose vocabulary had already seen the test set.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Machine%20Learning-FF7A00?style=for-the-badge&logo=scikitlearn&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)

</div>

---

# 📖 About

Each project loads a bundled CSV, validates it against named rules, fits a model with a fixed seed,
and reports metrics it can re-derive from the same split it used. The dataset is local, the split is
seeded, and the demo asserts its own arithmetic before it prints anything.

None of them downloads a dataset, imports a pretrained artefact, or calls a service. `scikit-learn`
does the fitting; everything else is standard library plus `pandas`/`numpy`.

**The lesson of each project is different, on purpose.** Five variations on "fit, score, print" would
teach nothing; five different summary numbers that can be true and still mislead is the subject.

- **Iris_Species_Classifier** — *a hold-out score is an estimate of a split, so report the split.*
  Accuracy computed on the training rows is not accuracy, and a confusion matrix that does not add up
  to the number of test rows is a decoration. The rebuild trains k-NN on a stratified 75/25 split,
  recomputes accuracy directly from the predictions and confirms it matches, checks that the matrix
  counts the test rows (**38 rows**), clamps `k` to the smallest training class instead of failing,
  and reports a 5-fold CV beside the hold-out — **accuracy 0.974**.
- **Customer_Segmentation** — *clustering has no labels, so nothing here is accuracy.* A silhouette of
  0.70 does not mean "70% correct", and `k` is a decision that has to be stated rather than defaulted.
  The rebuild sweeps `k = 2..8`, picks the best silhouette only as a default, keeps the whole sweep in
  the result, ranks clusters by a stated value index, and proves that `assign()` on the training rows
  reproduces the training labels exactly — **3 clusters partition 360 customers, silhouette 0.704**.
- **Housing_Price_Predictor** — *an R² means nothing without a baseline.* Predicting the mean of the
  target is a model, and it is the one your forest has to beat. The rebuild fits a linear model and a
  forest, reports RMSE/MAE/R² for both against the mean baseline, requires the feature importances to
  sum to 1, and pins a sanity ordering: larger, newer, central houses must be predicted higher —
  **forest R² 0.949**, both models beating the baseline.
- **Model_Evaluation_Harness** — *comparing models means sharing folds.* If each model gets its own
  random split, the ranking is mostly noise, and a "CV mean" that re-scores the full data is not a CV
  mean. The rebuild evaluates four pipelines under one stratified protocol, keeps per-fold means and
  standard deviations, ranks by mean CV F1, and a spy in the test suite proves the 5th scoring call is
  really the hold-out — **4 models × 5 folds, best naive_bayes at CV F1 0.824**.
- **Spam_Email_Classifier** — *fit the vocabulary on the training text only.* Vectorising before the
  split leaks test-set words into the vocabulary, and accuracy hides an unbalanced corpus. The rebuild
  builds a `CountVectorizer` inside the pipeline so it can only ever see training rows, reports
  precision/recall/F1 for the *spam* class beside the confusion matrix, and confirms the vocabulary
  size is the one it reports — **accuracy 1.000 on 35 test messages, vocabulary 603**.

**Every number is exact and every claim is checkable.** Splits are seeded, metrics are recomputed from
the predictions rather than restated, and each demo prints `Cross-checks OK: ...` with the values it
verified before `Demo completed successfully.`

---

# 🎓 Learning Objectives

- Validate a dataset before modelling it: schema, ranges, class sizes, constant features
- Separate a hold-out split from cross-validation, and say which one a number came from
- Recompute accuracy from predictions and prove the confusion matrix counts the same rows
- Read a confusion matrix as four numbers that must add up, not a picture
- Clamp a hyperparameter to what the data can support instead of crashing
- Treat a clustering result as a partition, and a silhouette as a relative score
- Choose `k` explicitly, keep the sweep, and state why the default is a default
- Reuse a fitted scaler when assigning new rows, so training and inference agree
- Compare every model against a trivial baseline before claiming it learned anything
- Require feature importances to sum to 1, and treat them as evidence, not truth
- Share folds across models so a ranking compares models rather than splits
- Keep per-fold means and standard deviations, not just a headline average
- Build a text pipeline so the vectoriser can only fit on training rows
- Report precision/recall/F1 for the class you actually care about
- Make a demo that asserts its own metrics instead of describing them

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Customer_Segmentation | k-means with a silhouette sweep, ranked profiles, `assign()` for new customers. | 51 | ✅
02 | Housing_Price_Predictor | Linear and forest regression against a mean baseline, importances, sanity ordering. | 57 | ✅
03 | Iris_Species_Classifier | Stratified k-NN, hold-out plus 5-fold CV, confusion matrix, single-flower prediction. | 51 | ✅
04 | Model_Evaluation_Harness | Four pipelines under one stratified protocol, per-fold means, ranking by CV F1. | 51 | ✅
05 | Spam_Email_Classifier | Bag-of-words pipeline, spam-class precision/recall/F1, single-message classification. | 51 | ✅

**Total: 261 tests.**

---

# 🧠 Concepts Covered

- Strict dataset validation: dtypes, ranges, duplicates, class minimums, constant columns
- Stratified train/test splitting and why stratification matters for small classes
- Hold-out metrics versus k-fold cross-validation, and what each one estimates
- Confusion matrices, per-class support, and metric identities
- Macro precision/recall/F1 versus per-class scores
- k-nearest neighbours: distance scaling, `k` selection, and clamping to the training fold
- k-means clustering: standardisation, inertia, and the silhouette score
- Choosing `k` by a sweep, and keeping the sweep in the result
- Cluster profiles, shares, and a value index that ranks segments
- Reusing a fitted scaler for out-of-sample assignment
- Linear regression and random forests on the same split
- Baseline comparisons: the mean predictor as the model to beat
- RMSE, MAE, R², and why R² can be negative
- Feature importance as a normalised, checkable quantity
- Cross-validation protocol: same folds for every model, per-fold means and standard deviations
- Bag-of-words vectorisation with unigrams and bigrams
- Pipeline composition so preprocessing is fitted inside the split
- Class imbalance and why accuracy alone is not a result
- Determinism: fixed seeds, seeded splits, byte-identical re-runs

---

# 📁 Repository Structure

```text
16_Machine_Learning/
│
├── Customer_Segmentation/
│   ├── src/    segment.py, main.py
│   ├── tests/  test_segment.py
│   └── data/   customers.csv
│
├── Housing_Price_Predictor/
│   ├── src/    housing.py, main.py
│   ├── tests/  test_housing.py
│   └── data/   housing.csv
│
├── Iris_Species_Classifier/
│   ├── src/    iris_classifier.py, main.py
│   ├── tests/  test_iris_classifier.py
│   └── data/   iris.csv
│
├── Model_Evaluation_Harness/
│   ├── src/    harness.py, main.py
│   ├── tests/  test_harness.py
│   └── data/   dataset.csv
│
└── Spam_Email_Classifier/
    ├── src/    spam_classifier.py, main.py
    ├── tests/  test_spam_classifier.py
    └── data/   messages.csv
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI, a
`tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a `.gitignore`, and a
`README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 16_Machine_Learning/Iris_Species_Classifier

python src/main.py --demo                     # offline, deterministic, exit 0
python src/main.py --demo --quiet             # prints nothing at all
python src/main.py --file data/iris.csv --k 7 --json out.json
python src/main.py --predict "5.1,3.5,1.4,0.2"
python -m pytest tests -q                     # the suite
```

Every project supports `--demo` (plus `--quiet`), `--file <csv>` and `--json <path>`, and adds its own
flags (`--k`, `--predict`, `--folds`, `--test-size`, `--seed`, `--text`). No demo writes into the
repository: JSON goes only where you point it.

---

# ✅ Verify the whole category

```powershell
Get-ChildItem -Directory | ForEach-Object {
    Push-Location $_
    python -m compileall -q src tests
    python -m pytest tests -q
    python src\main.py --demo
    python src\main.py --demo --quiet
    Pop-Location
}
```

The gates each project must pass, and does:

1. `compileall` on `src` and `tests` exits 0
2. `pytest` passes with no skips, 50+ tests
3. `--demo` exits 0 and ends with `Cross-checks OK: ...` then `Demo completed successfully.`
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing at all
5. no non-ASCII byte in `src/`, `tests/` or the text data files

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why a metric without its split is a rumour
- Why a confusion matrix that does not count the test rows is not evidence
- Why clustering has no accuracy, and a silhouette is not a percentage
- Why `k` is a stated decision, and a sweep belongs in the result
- Why a baseline is the first model you fit
- Why importances that do not sum to 1 are a bug, not a rounding artefact
- Why comparing models on different folds compares noise
- Why preprocessing inside the pipeline is a leakage guard, not a style preference
- Why a spam classifier is judged on spam, not on accuracy
- How to write a demo whose claims are its own assertions

---

# 🧩 Patterns Included

Parsing — `load_customers`, `load_housing`, `load_iris`, `load_dataset`, `load_messages`
Values — `SegmentationResult`, `ModelResult`, `HarnessResult`, `SpamResult`
Fitting — `segment`, `sweep_k`, `train_model`, `evaluate_model`, `run_harness`, `build_pipeline`
Assignment — `assign`, `predict_species`, `predict_price`, `classify`, `predict`
Comparison — `metric_table`, `metrics["mean_baseline"]`, `rank_score`, `best`, `ranking`
Reporting — `render_report`, `to_dict`, `--json`
Refusal — `SegmentError`, `HousingError`, `IrisError`, `HarnessError`, `SpamError`
Testing — exact metric identities, validation refusals, seeded determinism, CLI paths, quiet-mode
silence

---

# 🚀 Future Improvements

- A single `--compare` mode that runs all five datasets through one reporting shape
- Nested cross-validation for the harness, so hyperparameters are tuned inside the folds
- Calibration curves and Brier scores beside accuracy
- Class-weighting experiments on an intentionally unbalanced spam corpus
- Clustering stability across seeds, reported as a distribution rather than one silhouette
- Partial dependence plots for the forest importances
- A shared validation layer, so every loader refuses the same way
- A category-wide `audit` harness comparing all five summaries in one table

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a clear message.
4. Push the branch.
5. Open a Pull Request.

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
