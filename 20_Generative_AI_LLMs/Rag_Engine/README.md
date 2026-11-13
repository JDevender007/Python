<div align="center">

# 🔎 RAG Engine

### Retrieval-augmented answering over a local document store — hashed TF-IDF embeddings, cosine ranking, extractive answers with citations. No vector database, no embedding API, no downloads.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Stdlib](https://img.shields.io/badge/Dependencies-Standard%20Library-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

A retrieval-augmented generation pipeline normally needs three things: an embedding model, a vector index, and an LLM. This project shows that the *retrieval* half — the part that actually determines whether the answer is grounded — can be built from the standard library alone:

1. **Chunk** each document into sentences.
2. **Embed** with hashed TF-IDF: every token is MD5-hashed into one of 4096 buckets with a ±1 sign, weighted by `tf × idf`, then L2-normalised. No vocabulary is stored, so indexing is streaming-friendly and identical on every machine.
3. **Retrieve** with cosine similarity over unit vectors, returning a ranked list with scores.
4. **Extract** the sentence in the winning document with the highest query overlap — the answer is a verbatim quote, so it cannot hallucinate.
5. **Cite** every retrieved document, in rank order.

A light suffix stripper collapses `isolate`/`isolated` and `dependencies`/`dependency`, which matters more than it sounds: without it the gold query *"how do I isolate dependencies for a project"* missed `doc-venv` entirely. An early version also used a 256-dimensional hash space, and a single collision between `dependencies` and `dictionaries` pushed the wrong document to rank 1. Both bugs are now guarded by the demo's 100% accuracy-at-1 assertion.

No network, no API keys, no model downloads — the 9-document store ships in `data/documents.jsonl`.

---

# ✨ Features

- Hashed TF-IDF embedder with stable MD5 bucketing and signed collisions
- Cosine retrieval with ranked scores and deterministic tie-breaking
- Extractive answers: every answer is a verbatim sentence from a cited document
- Accuracy@1 and MRR evaluation over a gold query set
- Light stemmer tuned for the bundled store
- `--demo`, `--documents`, `--query`, `--top-k`, `--json` CLI
- Strict flag validation before the store is read
- 75 passing pytest tests

---

# 📂 Folder Structure

```text
Rag_Engine/
│
├── src/
│   ├── main.py  # CLI: --demo, --documents, --query, --top-k, --json
│   └── rag.py   # loading, embedding, retrieval, answers, evaluation
│
├── tests/
│   └── test_rag.py
│
├── data/
│   └── documents.jsonl   # 9 Python-topic documents
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 20_Generative_AI_LLMs/Rag_Engine

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

No runtime dependencies — `requirements.txt` only pins pytest.

---

# ▶️ Run

```bash
# Offline demo: validate the store, index it, score 9 gold queries
python src/main.py --demo

# Ask a question against the bundled store
python src/main.py --documents data/documents.jsonl --query "how do I test a function"

# Retrieve more context and export JSON
python src/main.py --documents data/documents.jsonl --query "decorators" \
                   --top-k 5 --json result.json
```

**Input:** a JSONL store, one object per line with `id`, `title`, and `text`.

**Exit codes:** `0` = success · `2` = usage/validation/store error.

---

# 🧠 How It Works

```text
documents.jsonl ──► Document(id, title, text)
                         │
                         ▼
        tokenize (lowercase, regex, stopwords) ──► stem
                         │
                         ▼
        hashed TF-IDF:  md5(token) -> bucket, sign
                        weight = (count / len) * idf
                         │
                         ▼
                 L2 normalise -> unit vector
                         │
   query ──► same pipeline ──► cosine vs every document
                         │
                         ▼
              ranked hits + scores (top-k)
                         │
                         ▼
     extract_answer: sentence with max query overlap
                         │
                         ▼
        {answer, score, citations[], hits[]}
```

Retrieval quality is measured, not assumed: the demo runs all nine gold queries through `evaluate()` and asserts accuracy@1 = 100% and MRR = 1.0, then rebuilds the index from scratch and asserts the vectors are bit-identical.

---

# 🛠 Technologies

- Python 3 standard library (`hashlib`, `re`, `math`, `json`, `dataclasses`)
- argparse / logging / pathlib
- pytest

No numpy, no faiss, no sentence-transformers, no OpenAI.

---

# 📚 Concepts Covered

- Retrieval-augmented generation (the retrieval half)
- Term frequency, inverse document frequency, and cosine similarity
- Feature hashing (the hashing trick) and signed collisions
- Unit-normalised embeddings and why the norm cancels in cosine
- Extractive vs abstractive answering
- Citation-first design and grounding
- Accuracy@1 and mean reciprocal rank
- Light stemming and its effect on recall
- Hash-space size as a bias/variance trade-off
- Deterministic, self-checking evaluation

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**75 tests passed** covering JSONL loading (bad JSON, missing fields, duplicates, empty text, empty store, blank lines), tokenisation and stopword removal, stem collapsing and short-word safety, IDF computation, unit-norm vectors, zero vectors, cosine edge cases, index construction and dimension checks, top-k behaviour, score ordering, empty/stopword-only queries, top-k validation, sentence splitting, answer extraction, citation integrity, JSON export, custom gold sets, demo idempotency, quiet mode, and every CLI error path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
