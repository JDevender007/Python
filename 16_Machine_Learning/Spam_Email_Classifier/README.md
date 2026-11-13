<div align="center">

# 📧 Spam Email Classifier

### Bag-of-words + Multinomial Naive Bayes — trains on bundled labelled messages, reports hold-out metrics, and classifies new text with a spam probability. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Classification-FF7A00?style=for-the-badge&logo=scikitlearn&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Spam Email Classifier turns labelled messages (`spam` / `ham`) into a working filter. Subject and body are joined into one document, vectorised into a **word + bigram bag-of-words** (lower-cased, English stop words removed — the stop-word list ships inside scikit-learn, nothing is downloaded), and fed to **Multinomial Naive Bayes** — the classic text-classification baseline.

The report shows hold-out accuracy, spam-class precision/recall/F1, a confusion matrix, and the per-class classification report. `--classify` applies the trained model to a single message and returns a verdict plus the calibrated spam probability.

The loader validates labels against `spam`/`ham`, rejects empty subjects/bodies, requires ≥ 40 messages with ≥ 10 per class (both classes must be present — a single-class file cannot train a classifier). Everything runs on local files: the bundled **deterministic** sample (140 messages, 70/70 balanced) ships in `data/`, and `--demo` trains, classifies two obvious examples, and cross-checks its own metrics. **No network, no corpus downloads.**

---

# ✨ Features

- `CountVectorizer` (1–2 grams, stop words, 4 000 feature cap) + `MultinomialNB`
- Stratified hold-out split: accuracy, spam precision/recall/F1, confusion matrix
- `classify(text)` → `(label, spam_probability)` with a 0.5 threshold
- Subject is weighted (appears twice in the document) — a cheap attention prior
- Strict validation: known labels, non-empty text, ≥ 40 rows, ≥ 10 per class
- JSON metrics export (with the classification attached when `--classify` is used)
- Deterministic: seeded split, stable predictions
- Bundled deterministic sample: 140 messages (70 spam / 70 ham)
- 46 passing pytest tests

---

# 📂 Folder Structure

```text
Spam_Email_Classifier/
│
├── src/
│   ├── main.py            # CLI: --demo, --file, --classify, --json, --seed
│   └── spam_classifier.py # loading, pipeline, metrics, classify, demo
│
├── tests/
│   └── test_spam_classifier.py
│
├── data/
│   └── messages.csv       # 140 deterministic rows (70 spam / 70 ham)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 16_Machine_Learning/Spam_Email_Classifier

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train, evaluate, classify sample messages
python src/main.py --demo

# Train on your own labelled CSV
python src/main.py --file messages.csv

# Classify one message (bundled data by default)
python src/main.py --classify "You are the WINNER, click to claim your FREE prize"

# Train on your CSV + classify + JSON metrics
python src/main.py --file messages.csv \
    --classify "lunch tomorrow at noon?" --json metrics.json
```

Input schema (header row required):

```csv
label,subject,body
ham,Meeting notes,Please review the agenda before Thursday. Thanks!
```

(`label` is `spam` or `ham`; ≥ 40 rows, ≥ 10 per class.)

**Exit codes:** `0` = success · `2` = usage/schema/classification error.

---

# 🧠 How It Works

```text
CSV ──► validate labels/text ──► subject+body documents ──► stratified split
                                                                    │
                                              ┌─────────────────────┤
                                              ▼                     ▼
                                  CountVectorizer(1,2 grams)   hold-out texts
                                   + MultinomialNB (fit)             │
                                              │                      ▼
                                              └──────────► predict ─► metrics
                                                                    │
                        ┌───────────────────────────────────────────┤
                        ▼                                           ▼
              confusion matrix / report                    classify("...") → P(spam)
```

Why this works: Naive Bayes counts how often each word appears in spam vs ham during `fit`, then multiplies those likelihoods at predict time (with Laplace smoothing, `alpha=1`). Bigrams like "free prize" carry more signal than "free" alone, and stop words ("the", "your") add noise — hence `(1, 2)` grams with `stop_words="english"`.

The probability threshold is 0.5: `P(spam) ≥ 0.5` → spam. On the bundled template messages the model reaches **100 % hold-out accuracy** — realistic corpora land lower, which is exactly why the demo prints precision and recall alongside accuracy.

---

# 🛠 Technologies

- Python
- scikit-learn (`CountVectorizer`, `MultinomialNB`, `Pipeline`, metrics)
- pandas (loading, validation, confusion DataFrame)
- re / argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- The bag-of-words model and n-gram features
- Why Naive Bayes suits text (and its independence assumption)
- Laplace/additive smoothing (`alpha`)
- Stop words and why they are removed
- Stratified splits for balanced classes
- Precision vs recall for the spam positive class
- Confusion matrices and per-class reports
- Probability calibration and decision thresholds
- Deterministic NLP pipelines with fixed seeds

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**46 tests passed** covering every validation rule (labels, empty text, row/class minimums, single-class files), pipeline structure, metric correctness (accuracy recomputed from predictions, confusion row counts), determinism across seeds, classification edge cases (empty, non-string, huge, unseen words), demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
