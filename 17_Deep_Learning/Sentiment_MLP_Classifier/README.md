<div align="center">

# 💬 Sentiment MLP Classifier

### A PyTorch bag-of-words MLP classifying message sentiment — bundled 500-message dataset, precision/recall/F1, confusion matrix, and per-message probabilities. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-Sentiment-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Sentiment MLP Classifier turns raw message text into a positive/negative judgement using a **bag-of-words featuriser + small fully-connected network** — no pre-trained models, no embeddings, no downloads. It loads a local `(text, label)` CSV, builds a binary bag-of-words vocabulary **from the training split only** (so the hold-out never leaks into the features), trains `vocab → 64 → 32 → 1` with dropout and BCE-with-logits loss, and reports hold-out accuracy, precision, recall, F1, a confusion matrix, and the most confident predictions with their probabilities.

`--classify "some message"` returns a sentiment label and probability for a single message. The demo's bundled dataset (500 deterministic templated reviews, balanced 250/250) ships in `data/messages.csv`; after 40 epochs the model reaches **~0.99 hold-out accuracy / F1**, and the demo cross-checks that a "love/wonderful" phrase scores above a "hate/terrible" one before declaring success.

Everything runs on local files: the vocabulary is capped at 3000 tokens, tokens are ≥ 2 characters, the loader validates binary labels with ≥ 20 rows per class, and the whole pipeline is seeded (split, weight init, shuffle) for bit-for-bit determinism. **No network, no corpus downloads, no GPU required.**

---

# ✨ Features

- Binary bag-of-words featurisation (`CountVectorizer`, unigrams, capped at 3000 tokens)
- Vocabulary fitted on the **train split only** — no hold-out leakage
- PyTorch MLP: `64 → 32 → 1` with ReLU, dropout, sigmoid output trained with BCE-with-logits
- Hold-out accuracy / precision / recall / F1 + hand-built confusion matrix
- `predict(message)` → `(label, P(positive))` for any single string
- Learning curve (train + validation BCE per epoch) in the report
- Strict validation: binary labels, ≥ 100 rows, ≥ 20 per class, non-empty texts
- `--classify "text"` with bundled-data fallback; JSON metrics export
- Deterministic: seeded split, init, and shuffle — identical results every run
- 52 passing pytest tests

---

# 📂 Folder Structure

```text
Sentiment_MLP_Classifier/
│
├── src/
│   ├── main.py      # CLI: --demo, --file, --classify, --epochs, --json
│   └── sentiment.py # loading, featurisation, MLP, metrics, report, demo
│
├── tests/
│   └── test_sentiment.py
│
├── data/
│   └── messages.csv # 500 deterministic messages (250 positive / 250 negative)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 17_Deep_Learning/Sentiment_MLP_Classifier

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train, metrics + confusion matrix, phrase checks, cross-checks
python src/main.py --demo

# Train on your own (text, label) CSV
python src/main.py --file messages.csv --epochs 80

# Classify one message (bundled sample if --file is omitted)
python src/main.py --classify "i love this wonderful movie"

# Metrics as JSON
python src/main.py --file messages.csv --json metrics.json
```

Input schema (header row required):

```csv
text,label
i love this wonderful movie,1
the service was terrible and slow,0
```

(`label` is `0` or `1`; ≥ 100 rows, ≥ 20 per class; texts non-empty.)

**Exit codes:** `0` = success · `2` = usage/schema/classification error.

---

# 🧠 How It Works

```text
messages.csv ──► validate (binary label, minimums, non-empty text)
                          │
                          ▼  stratified 75 / 25 split
   train texts ──► CountVectorizer.fit_transform  ← vocabulary built HERE
                          │                          (max 3000 tokens,
                          ▼                            binary, unigrams)
   x_train: (376, vocab) 0/1 matrix          x_test: (124, vocab) sealed
                          │
                          ▼
   Linear(vocab, 64) → ReLU → Dropout → Linear(64, 32) → ReLU → Dropout → Linear(32, 1)
                          │
              BCE-with-logits loss + Adam, 40 epochs, seeded shuffle
                          │
                          ▼
   sigmoid(logits) ─► accuracy / precision / recall / F1,
                      [[tn, fp], [fn, tp]] confusion,
                      predict("any text") → (label, probability)
```

Why bag-of-words + MLP works here: the templated vocabulary splits cleanly — positive messages contain *love/wonderful/excellent* and negatives contain *hate/terrible/awful* — so a linear-ish decision surface over token presence is sufficient, and the hidden layers just learn token interactions. The interesting discipline is the **leakage guard**: the vectoriser is fitted on the training split only, so hold-out messages can only be represented by tokens the model already saw — exactly the constraint you'd face on real unseen data.

`BCEWithLogitsLoss` is used instead of `BCE(sigmoid(x))` because it fuses the sigmoid for numerical stability (no `log(0)` blowups). Dropout (0.1) regularises the small dataset; the demo's train/hold-out gap (~1.0 vs ~0.99) shows it isn't overfitting the 376 training messages.

---

# 🛠 Technologies

- Python 3
- PyTorch (`nn.Sequential`, `BCEWithLogitsLoss`, `Adam`, seeded RNG)
- scikit-learn (`CountVectorizer` — bundled with the install, no corpora fetched)
- pandas / numpy (loading, validation, metrics, confusion matrix)
- argparse / json / logging / dataclasses
- pytest

---

# 📚 Concepts Covered

- Bag-of-words featurisation and why vocabulary must be fit on train only
- Binary vs count features for short messages
- Multilayer perceptrons on sparse high-dimensional inputs
- Dropout as regularisation on small datasets
- BCE-with-logits vs BCE (numerical stability)
- Precision / recall / F1 and reading a confusion matrix
- Stratified splitting to preserve class balance
- Probability outputs from sigmoid and choosing the 0.5 threshold
- Deterministic NLP pipelines with seeded RNG
- Fast-fail CLI validation (message checked before training)

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**52 tests passed** covering every validation rule (schema, binary/fractional labels, class minimums, empty texts, empty-row dropping), vectorizer behaviour, model config errors, training metrics, confusion-vs-metric consistency, determinism and seed sensitivity, loss reduction, `predict()` edge cases (empty, non-string, phrase ordering, agreement with hold-out outputs), report sections, demo idempotency, and every CLI path — all offline. Extra cases pin the train/test split in `to_dict`, the vocabulary size, label agreement with the probability threshold, probability bounds, and ASCII-only report text.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
