<div align="center">

# 🤖 Generative AI & LLM Projects

### Five offline generative-modelling projects: a character-level Transformer, an order-n Markov generator, a retrieval-augmented answering engine, a GAN, and a from-scratch multi-head attention visualiser.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This category builds generative systems from their components instead of wrapping a hosted API. Each project answers a different question:

- **Can a Transformer learn to write?** A decoder-only mini-GPT with hand-written causal attention, trained for 150 steps on a bundled corpus.
- **What does a chain without embeddings get you?** An order-1/2/3 Markov generator with backoff sampling and honest perplexity numbers.
- **What actually grounds a RAG answer?** Hashed TF-IDF retrieval, extractive quoting and citations — the retrieval half, with no LLM.
- **Can adversarial training be watched end to end?** A 90-line GAN on two moons, scored with coverage, nearest-real distance and mode balance.
- **What do attention heads really compute?** Multi-head self-attention in NumPy, measured with entropy and head diversity and drawn as ASCII heat maps.

Everything runs on CPU, in seconds, with **no network, no API keys and no model downloads**. Data ships in each project's `data/` folder, and every demo validates its own inputs before asserting anything.

---

# 🎯 Learning Objectives

- Implement causal self-attention and a decoder-only Transformer block
- Train a language model with cross-entropy and AdamW on a CPU budget
- Sample with temperature and top-k using a seeded generator
- Build a Markov language model and measure it with bits-per-word perplexity
- Understand why add-one smoothing and backoff matter for sparse contexts
- Build retrieval with hashed TF-IDF and cosine similarity
- Design extractive answers that cannot hallucinate
- Train a GAN with alternating updates and detect mode collapse quantitatively
- Compute scaled dot-product attention and interpret its entropy
- Keep generative demos deterministic, fast and self-verifying

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Tiny_Transformer_LM | Character-level GPT (2 layers, 2 heads, d_model 64); loss 3.83 → 1.08 in 150 steps. | ✅
02 | Markov_Text_Generator | Order 1–3 transition counts, seeded sampling, backoff, perplexity 6.43 bits/word. | ✅
03 | Rag_Engine | Hashed TF-IDF retrieval over 9 documents, 100% accuracy@1, cited extractive answers. | ✅
04 | Tiny_GAN | MLP GAN on two moons; 800 steps, 95.5% coverage, 50/50 mode balance. | ✅
05 | Attention_Visualizer | Multi-head attention in NumPy with causal masks, entropy, head diversity, ASCII maps. | ✅

---

# 💡 Concepts Covered

- Decoder-only Transformer architecture and pre-LayerNorm residuals
- Scaled dot-product attention, causal masking, multi-head splitting
- Learned positional embeddings and weight tying
- Cross-entropy, AdamW and block sampling
- Temperature and top-k decoding
- Markov chains, transition counts and backoff
- Add-one smoothing and perplexity in bits per word
- Retrieval-augmented generation, embeddings and cosine ranking
- Feature hashing and signed collisions
- Extractive answering, grounding and citations
- GAN minimax objectives, BCE-with-logits and Adam `beta1 = 0.5`
- Mode collapse, coverage and nearest-neighbour metrics
- Attention entropy and head diversity as interpretability signals
- Deterministic training and sampling via seeds

---

# 📁 Repository Structure

```text
20_Generative_AI_LLMs/
│
├── Tiny_Transformer_LM/
├── Markov_Text_Generator/
├── Rag_Engine/
├── Tiny_GAN/
├── Attention_Visualizer/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── data/             # bundled corpus / dataset / document store
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- PyTorch (Tiny_Transformer_LM, Tiny_GAN)
- NumPy (Attention_Visualizer)
- Standard library (`hashlib`, `re`, `math`, `csv`, `json`, `argparse`)
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Tiny Transformer LM | ✅ |
| Markov Text Generator | ✅ |
| RAG Engine | ✅ |
| Tiny GAN | ✅ |
| Attention Visualizer | ✅ |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 20_Generative_AI_LLMs/Tiny_Transformer_LM

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

Each project follows the same shape: `python src/main.py --demo` for a self-checking offline run, `python -m pytest tests/ -q` for the suite.

---

# 📚 Skills Developed

- Writing attention and Transformer blocks from their equations
- Debugging training loops (learning rate, optimiser choice, masking)
- Reading loss curves and knowing when a model is under-trained
- Measuring generative quality instead of eyeballing samples
- Building retrieval and evaluation harnesses
- Designing extractive pipelines that stay grounded
- Using entropy and diversity to interpret attention maps
- Bundling small deterministic datasets and validating them at runtime
- Writing 50–100 pytest cases per project, including every error path

---

# 🚀 Key Learning Outcomes

- Train a small GPT and sample from it, fully offline, in under 30 seconds
- Generate text with a Markov chain and understand its perplexity trade-offs
- Answer questions over documents with citations and no LLM
- Train a GAN and prove it did not mode-collapse
- Visualise attention and explain what each head attends to

---

# 🔮 Future Enhancements

- KV-cache and top-p sampling for the Transformer
- Byte-pair encoding instead of character tokens
- Hybrid retrieval (BM25 + embeddings) in the RAG engine
- WGAN-GP objective as a stable alternative to BCE
- Interactive HTML heat maps alongside the ASCII renderer

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
