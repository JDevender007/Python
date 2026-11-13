<div align="center">

# 🔗 Markov Text Generator

### Order-n Markov chain text generation in the standard library — transition counts, weighted sampling, backoff for unseen contexts, and add-one smoothed perplexity.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Stdlib](https://img.shields.io/badge/Dependencies-Standard%20Library-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

This project builds a Markov chain language model from a local corpus. For every order-*n* context it stores the observed successor counts, samples continuations proportionally to those counts, and measures quality in **bits per word** with add-one smoothing plus unigram backoff when a context was never seen.

Three orders are trained side by side (1, 2, 3) so the trade-off is visible: a unigram model is smooth but context-free; a trigram model has the lowest training perplexity in principle but pays for sparsity with a 42-word vocabulary — the demo asserts the bigram beats the unigram and prints all three scores honestly, including the case where the trigram loses.

Everything is deterministic: seeded sampling, a generated corpus, and an independent naive recount that the demo cross-checks against the incremental model.

---

# ✨ Features

- Order 1–3 transition counts with validated ranges
- Weighted sampling via `random.choices` and a seeded `random.Random`
- Backoff to a sentence start when a context dead-ends
- Fixed start-context support (`--start` via the API)
- Add-one smoothed perplexity with unigram fallback
- Top-transition report (`the garden -> . x25, the x25`)
- `--demo`, `--corpus`, `--order`, `--length`, `--seed`, `--json`
- 50 passing pytest tests

---

# 📂 Folder Structure

```text
Markov_Text_Generator/
│
├── src/
│   ├── main.py    # CLI: --demo, --corpus, --order, --length, --json
│   └── markov.py  # corpus, model, sampling, perplexity, demo
│
├── tests/
│   └── test_markov.py
│
├── data/
│   └── corpus.txt
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 20_Generative_AI_LLMs/Markov_Text_Generator

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

No runtime dependencies — `requirements.txt` only pins pytest for the tests.

---

# ▶️ Run

```bash
# Offline demo: verify corpus, build orders 1-3, sample, score
python src/main.py --demo

# Train on your own text
python src/main.py --corpus mytext.txt --order 2 --length 60 --seed 7

# Machine-readable summary
python src/main.py --corpus data/corpus.txt --json run.json
```

**Input:** any plain-text file. Tokens are lowercase words plus `. , ! ? ;`.

**Exit codes:** `0` = success · `2` = usage/validation/corpus error.

---

# 🧠 How It Works

```text
corpus.txt ──► tokens (words + punctuation, lowercased)
                    │
                    ▼
     for each index: context = tokens[i:i+n]
                     counts[context][tokens[i+n]] += 1
                    ▼
   model.counts: dict[tuple, Counter]  +  vocab Counter  +  clean starts
                    │
     ┌──────────────┼─────────────────────────┐
     ▼              ▼                         ▼
 most_likely()   generate_text()          perplexity()
 argmax count    weighted choice          add-one smoothing
                 seeded RNG               unigram backoff
```

Perplexity is `2^(mean bits)` where each word contributes

```text
-log2( (count(context, word) + 1) / (total(context) + |vocab|) )
```

and falls back to the unigram distribution `(count(word) + 1) / (N + |vocab|)` when the context has no counts at all — the standard way to avoid an infinite penalty on held-out text.

---

# 🛠 Technologies

- Python 3 standard library (`collections.Counter`, `random`, `math`, `re`, `json`)
- argparse / dataclasses / logging
- pytest

---

# 📚 Concepts Covered

- Markov chains and the Markov assumption
- Transition counting with `Counter` of `Counter`
- Weighted random sampling and determinism via seeding
- Backoff strategies for sparse contexts
- Add-one (Laplace) smoothing
- Perplexity as bits per word
- Cross-checking an incremental model against a naive recount
- The bias/variance trade-off of increasing model order

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**50 tests passed** covering corpus determinism and bundling, load errors, tokenisation, model construction and counts, order validation, tiny-corpus guards, clean sentence starts, `most_likely` hits and misses, deterministic and seed-sensitive sampling, length and vocabulary constraints, fixed start contexts, detokenisation, perplexity bounds and backoff, report rendering, JSON export, demo idempotency, quiet mode, and every CLI error path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
