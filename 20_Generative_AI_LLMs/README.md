<div align="center">

# ✨ Generative AI / LLM Projects

### Five generative systems small enough to train on a laptop in seconds, and precise enough to audit. Attention is a matrix whose rows must sum to 1; a language model is a counting table before it is anything else; retrieval is a ranking you can score; a generator can look convincing while covering nothing; and a transformer is trained here, not imported.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-Tiny%20Models-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)

</div>

---

# 📖 About

Five projects, no API key, no GPU, no downloaded checkpoint. Each one ships a small corpus or dataset
in `data/`, builds its model from seeded initialisation, trains for seconds on a CPU, and then proves
something specific about what came out. The demos report the values they verified, so "it trained"
is never the claim.

**The lesson of each project is different, on purpose.** Five variations on "call a model" would teach
nothing; five different ways a generative system can look impressive and mean nothing is the subject.

- **Attention_Visualizer** — *attention is a matrix, so it has invariants you can check.* A heat-map
  is a picture; a **row-stochastic matrix with a causal mask** is a testable object. The rebuild
  builds embeddings from a PPMI co-occurrence matrix, adds a positional encoding, computes scaled
  dot-product scores, checks `softmax` against the naive formula written out by hand, requires every
  attention row to sum to 1, verifies the causal mask exactly (no token attends forward), and
  reports normalised entropy inside its theoretical bound — **4 sentences, entropy within [0, 2.58]**.
- **Markov_Text_Generator** — *a language model is a counting table before it is anything else.* If
  the generator's trigram counts disagree with a naive recount of the same tokens, everything built
  on top is decoration. The rebuild builds orders 1–3, re-derives every transition count from the
  corpus independently, samples with a seeded `random.Random` so a fixed start reproduces the same
  text, and reports **perplexity 6.43 bits/word** rather than a vibe.
- **Rag_Engine** — *retrieval is a ranking, and a ranking has a score you can miss.* A RAG demo that
  prints a plausible answer proves nothing; `accuracy@1` against gold queries proves something. The
  rebuild loads and validates JSONL documents, embeds them with a **hashing embedder** (stable across
  processes, no vocabulary to persist), ranks by cosine, extracts the answer sentence with a citation,
  and checks that scores decrease down the ranked list and that retrieval is deterministic —
  **9 documents validated, accuracy@1 100%** on the bundled gold queries.
- **Tiny_GAN** — *a generator can look right while covering nothing at all.* Two moons is small
  enough to eyeball, and eyeballing is exactly the trap: a generator that produces one convincing
  blob has learned a mode, not the distribution. The rebuild trains a generator/discriminator pair on
  standardised two-moon points and asserts **coverage of both moons, mode balance, finite losses, and
  deterministic sampling** — so "it looks like the data" is replaced by measured coverage.
- **Tiny_Transformer_LM** — *a transformer is a stack of decisions, not a download.* Character-level
  modelling makes every decision visible: vocabulary, block size, causal self-attention, and the
  sampling temperature. The rebuild trains a small GPT-style stack from scratch on a bundled corpus and
  shows the loss falling from **3.833 to 1.079** over the run, verifies that **164 characters** in the
  prompt are all in-vocabulary, proves the run is reproducible, and proves that a different seed
  produces different samples — otherwise "deterministic" would just mean "broken".

**Every claim is checkable.** Each demo prints `Cross-checks OK: ...` with the numbers it verified,
then `Demo completed successfully.`; run it twice and the bytes match, run it with `--quiet` and it
writes nothing at all.

`torch` does the tensor work in two of the five; the rest is `numpy` and the standard library. Nothing
reads a clock, opens a socket, or writes model files into the repository.

---

# 🎓 Learning Objectives

- Build a scaled dot-product attention matrix and check it against a hand-written softmax
- Verify that every attention row is a probability distribution
- Implement a causal mask and explain why it is not optional for a decoder
- Bound attention entropy and read it as a measure of focus
- Build n-gram models of several orders and recount the transitions independently
- Compute perplexity in bits per word and state which model it belongs to
- Sample deterministically with a seeded RNG and a fixed start context
- Embed documents without a fitted vocabulary, using a stable hashing trick
- Rank by cosine similarity and check monotonicity down the list
- Evaluate retrieval with accuracy@k against gold queries
- Extract an answer sentence with a citation instead of free-form text
- Train a GAN on a 2-D dataset and evaluate it by coverage, not by a screenshot
- Measure mode balance so a collapsed generator cannot pass
- Standardise inputs and keep the inverse transform available
- Implement causal self-attention and a transformer block from scratch
- Train a character-level LM and read a loss curve in nats or bits
- Prove determinism with a fixed seed, and prove sensitivity with a different one
- Sample with temperature and top-k, and see what each one does to the output

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Attention_Visualizer | PPMI embeddings, positional encoding, multi-head attention, causal mask, entropy bounds. | 105 | ✅
02 | Markov_Text_Generator | Orders 1–3, independently recounted transitions, seeded sampling, perplexity in bits. | 50 | ✅
03 | Rag_Engine | JSONL documents, hashing embedder, cosine ranking, citation-first answers, accuracy@1. | 75 | ✅
04 | Tiny_GAN | Two-moon GAN with standardisation, coverage, mode balance and deterministic sampling. | 67 | ✅
05 | Tiny_Transformer_LM | Character-level GPT stack from scratch, loss curve, in-vocab prompt, seed sensitivity. | 57 | ✅

**Total: 354 tests.**

---

# 🧠 Concepts Covered

- Tokenisation at word and character level, vocabulary as fitted state
- Co-occurrence matrices, PPMI weighting, and embeddings without gradients
- Positional encodings and why order must be injected
- Scaled dot-product attention: queries, keys, values, and the `1/sqrt(d)` factor
- Softmax as a normaliser, and numerical stability
- Causal masking and the difference between encoder and decoder attention
- Multi-head attention and head diversity
- Attention entropy as a measure of focus
- N-gram language models, smoothing, and back-off by construction
- Perplexity and its units: nats versus bits
- Seeded sampling and reproducible text generation
- Document ingestion, schema validation, and JSONL
- The hashing trick for stable, vocabulary-free embeddings
- Cosine similarity, ranking, and accuracy@k
- Citation-first answering and extractive grounding
- Generative adversarial training: generator, discriminator, and the alternating objective
- Standardisation and its inverse for generated samples
- Mode collapse, coverage, and mode balance as measurable quantities
- Causal self-attention, residual streams, and layer normalisation
- Cross-entropy in nats, and the loss curve as evidence
- Temperature and top-k sampling as separate controls
- Determinism with `torch.manual_seed` and seeded sampling, and seed sensitivity as the control

---

# 📁 Repository Structure

```text
20_Generative_AI_LLMs/
│
├── Attention_Visualizer/
│   ├── src/    attention.py, main.py
│   ├── tests/  test_attention.py
│   └── data/   texts.json
│
├── Markov_Text_Generator/
│   ├── src/    markov.py, main.py
│   ├── tests/  test_markov.py
│   └── data/   corpus.txt
│
├── Rag_Engine/
│   ├── src/    rag.py, main.py
│   ├── tests/  test_rag.py
│   └── data/   documents.jsonl
│
├── Tiny_GAN/
│   ├── src/    gan.py, main.py
│   ├── tests/  test_gan.py
│   └── data/   moons.csv
│
└── Tiny_Transformer_LM/
    ├── src/    lm.py, main.py
    ├── tests/  test_lm.py
    └── data/   corpus.txt
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI, a
`tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a `.gitignore`, and a
`README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 20_Generative_AI_LLMs/Tiny_Transformer_LM

python src/main.py --demo                                  # offline, deterministic, exit 0
python src/main.py --demo --quiet                           # prints nothing at all
python src/main.py --prompt "the model learns" --length 120 --temperature 0.8
python src/main.py --file data/corpus.txt --steps 500 --seed 7 --json out.json
python -m pytest tests -q                                   # the suite
```

Every project supports `--demo` (plus `--quiet`) and `--json <path>`, and adds its own flags
(`--file`, `--corpus`, `--documents`, `--data`, `--texts`, `--sentence`, `--query`, `--prompt`,
`--order`, `--steps`, `--length`, `--temperature`, `--top-k`, `--heads`, `--latent`, `--batch-size`,
`--seed`). No demo writes into the repository: JSON goes only where you point it.

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

- Why an attention heat-map is not evidence, and a row sum is
- Why a causal mask is a structural guarantee rather than a convention
- Why entropy is a better summary of an attention map than a colour scale
- Why an n-gram model's counts must be recounted independently before anything is built on them
- Why perplexity needs its unit and its model stated
- Why seeded sampling is the difference between a demo and a slot machine
- Why a hashing embedder makes retrieval reproducible and un-inspectable at the same time
- Why accuracy@k is the only honest number for a retrieval demo
- Why a citation-first answer is testable and a free-form answer is not
- Why a GAN can look right and cover one mode
- Why coverage and mode balance must be measured, not eyeballed
- Why "the loss went down" is the start of an argument, not the end
- Why determinism needs a second seed to be believable
- How to train a transformer on a CPU in seconds and still say something true about it

---

# 🧩 Patterns Included

Parsing — `load_texts`, `load_corpus`, `load_documents`, `load_moons`
Embedding — `cooccurrence`, `ppmi`, `embed_tokens`, `positional_encoding`, `HashingEmbedder`
Attention — `scaled_scores`, `softmax`, `causal_mask`, `head_projections`, `multi_head_attention`
Analysis — `row_entropy`, `normalized_entropy`, `head_diversity`, `top_attended`, `ascii_heatmap`
Counting — `build_model`, `most_likely`, `perplexity`, `transition_report`
Retrieval — `build_index`, `search`, `cosine`, `extract_answer`, `answer`, `evaluate`
Generation — `generate_text`, `detokenize`, `sample`, `_sample`
Adversarial — `Generator`, `Discriminator`, `train_gan`, `coverage`, `mean_nearest_distance`,
`mode_balance`
Transformers — `CharTokenizer`, `CausalSelfAttention`, `Block`, `TinyGPT`, `train_lm`
Rendering — `render_report`, `to_dict`, `_wrap`
Refusal — `AttentionError`, `MarkovError`, `RagError`, `GanError`, `LmError`
Testing — hand-written softmax cross-checks, row-sum and mask invariants, independent recounts,
gold-query retrieval scores, coverage and mode balance, seed determinism and seed sensitivity,
CLI paths, quiet-mode silence

---

# 🚀 Future Improvements

- Beam search beside greedy sampling, with the perplexity of each
- Subword tokenisation, so the character-level model has a vocabulary comparison
- A second encoder (bag-of-words) beside the hashing embedder, and a retrieval bake-off
- Reranking with a cross-encoder, evaluated against the same gold queries
- A conditional GAN on the moons dataset, to show mode coverage under conditioning
- Attention visualisation exported as SVG so a map can be reviewed in a diff
- Learning-rate schedules and gradient clipping, with the curve kept as evidence
- A category-wide `audit` harness comparing all five evidence tables in one shape

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
