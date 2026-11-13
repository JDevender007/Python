<div align="center">

# 📝 NLP Projects

### Five offline natural-language-processing projects: tokenisation, extractive summarisation, named-entity recognition, part-of-speech tagging, and Word2Vec embeddings trained from scratch.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This category walks the classic NLP stack from raw characters to dense vectors. Rather than calling a library for each step, the interesting machinery is built directly: a multi-strategy tokeniser, TF-IDF/TextRank-style sentence ranking, gazetteer + pattern NER, a bigram HMM-style POS tagger, and the full skip-gram with negative sampling objective trained in NumPy.

Every project ships a small **bundled corpus** in `data/` (`corpus.txt`, `gold.json`, `articles.json`, gazetteer lists) and verifies it against a deterministic generator before asserting anything. That means the demos are reproducible on any machine, need no downloads, and fail loudly if an asset is corrupted instead of silently changing the numbers.

No network, no API keys, no pre-trained models, no model downloads.

---

# 🎯 Learning Objectives

- Implement tokenisation rules (whitespace, punctuation, contractions, regex) and measure the differences
- Score sentences with TF-IDF and rank them for extractive summaries
- Build gazetteer- and pattern-based named-entity recognition with span de-duplication
- Tag parts of speech with a learned emission/transition model
- Derive and implement the skip-gram + negative-sampling objective by hand
- Verify sampling distributions empirically against the theoretical distribution
- Keep demos deterministic and self-checking
- Bundle small generated corpora instead of downloading datasets

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Tokenizer_Workshop | Whitespace / regex / contraction-aware tokenisers compared on a bundled corpus. | ✅
02 | Text_Summarizer | TF-IDF sentence ranking with compression-ratio and coverage statistics. | ✅
03 | Named_Entity_Recognizer | Gazetteer + pattern NER with span merging and precision/recall against gold. | ✅
04 | Pos_Tag_Tagger | Emission/transition POS tagging with accuracy and confusion reporting. | ✅
05 | Word2Vec_From_Scratch | Skip-gram + negative sampling in NumPy; learns `king`→`queen`, solves analogies. | ✅

---

# 💡 Concepts Covered

- Unicode-aware tokenisation, contraction splitting, and regex token boundaries
- Stop-word removal and stemming/lemmatisation approximations
- Term frequency, inverse document frequency, and cosine similarity
- Extractive summarisation and compression ratio
- Named-entity spans, gazetteers, and boundary disambiguation
- Part-of-speech inventories, emission and transition probabilities
- Viterbi-style sequence decoding
- Skip-gram objective and negative sampling
- Unigram^0.75 noise distribution
- Adam optimisation and gradient derivation
- Deterministic procedural corpora for reproducible evaluation

---

# 📁 Repository Structure

```text
19_NLP/
│
├── Tokenizer_Workshop/
├── Text_Summarizer/
├── Named_Entity_Recognizer/
├── Pos_Tag_Tagger/
├── Word2Vec_From_Scratch/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── data/             # bundled deterministic corpus / gold labels
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- NumPy (TF-IDF maths, embedding training, sampling tables)
- Standard library (`re`, `json`, `csv`, `argparse`, `dataclasses`)
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Tokenizer Workshop | ✅ |
| Text Summarizer | ✅ |
| Named Entity Recognizer | ✅ |
| POS Tag Tagger | ✅ |
| Word2Vec From Scratch | ✅ |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 19_NLP/Word2Vec_From_Scratch

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

---

# 📚 Skills Developed

- Designing tokenisation rules and reasoning about their trade-offs
- Building ranking functions from term statistics
- Evaluating extraction against gold labels with precision/recall
- Implementing sequence models from their probability definitions
- Deriving gradients for a neural objective and debugging training
- Recognising when an optimiser choice changes convergence qualitatively
- Building deterministic, self-verifying demos
- Automated testing with pytest

---

# 🚀 Key Learning Outcomes

- Tokenise text five different ways and see exactly where they disagree
- Summarise documents without a language model
- Extract named entities with gazetteers and patterns
- Tag parts of speech with learned probabilities
- Train word embeddings and query them by similarity and analogy

---

# 🔮 Future Enhancements

- Subword (BPE) tokenisation to handle unseen words
- Abstractive summarisation with a tiny seq2seq model
- CRF layer on top of the POS tagger
- Hierarchical softmax as an alternative to negative sampling
- GloVe and fastText comparisons on the same corpus

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
