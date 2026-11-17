<div align="center">

# 🗣️ NLP Projects

### Five text pipelines where the sentence is the easy part. A named entity is a span, not a string; a tag sequence needs transitions as well as emissions; a summary is a selection you have to justify; a token is the output of four separate decisions; and an embedding is a model trained against noise, not a table you look things up in.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-From%20Scratch-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)

</div>

---

# 📖 About

Five projects, one shared discipline: the corpus ships in `data/`, the rules are written down in code,
and every number the demo prints is recomputed from the same objects it just produced. Nothing is
downloaded, no model is loaded, and there is no tokenizer library doing the hard thinking.

**The lesson of each project is different, on purpose.** Five variations on "split on whitespace"
would teach nothing; five different ways a text pipeline can be confidently wrong is the subject.

- **Named_Entity_Recognizer** — *an entity is a span, not a substring.* Finding "Paris" is not the
  same as knowing *which* "Paris", and a pattern and a gazetteer will often both claim the same
  characters. The rebuild extracts `Entity(text, label, start, end)` with a **stated label
  priority** so overlapping candidates resolve deterministically, requires the span to slice back to
  the exact text, forbids overlaps, and scores exact spans against a gold file — **micro precision
  1.000 / recall 1.000 / F1 1.000** on the bundled gold set, with the spans re-verified by slicing.
- **Pos_Tag_Tagger** — *a label sequence is not a bag of labels.* Tagging each word independently
  ignores that `read` is a verb after `we` and a past tense in a story, and a majority-tag baseline
  gets surprisingly far on a small corpus. The rebuild trains a smoothed bigram HMM with proper
  `log` tables, decodes with Viterbi, reports the **majority-tag baseline (0.996)** beside the model
  (**accuracy 1.000**), and accounts for every one of the **816 test tokens** so the metric cannot
  quietly drop a sentence.
- **Text_Summarizer** — *an extractive summary is a selection, so it can be checked verbatim.* A
  summary that paraphrases is unfalsifiable; a summary made of real sentences must be a **subset of
  the source, in document order**. The rebuild scores sentences with a TF-IDF centroid, selects
  with an explicit `ceil(ratio × n)` rule, asserts that every selected sentence appears verbatim in
  the output, and reports coverage beside compression — **3 articles summarised, compression below
  1, coverage at least 0.6**, best sentences selected, deterministic re-run.
- **Tokenizer_Workshop** — *a token is the end of a pipeline, not the start of one.* Normalisation,
  minimum length, stopword removal, stemming, and n-gram assembly each change the count, and each
  one needs its own invariant. The rebuild makes every stage a pure function over a list of tokens,
  refuses non-strings by name, and reports the whole funnel: **339 tokens → 110 stopwords removed →
  176 unique stems → 228 bigrams**, with every number recomputed from the lists it just built.
- **Word2Vec_From_Scratch** — *an embedding is trained, so the gradient is the claim.* Skip-gram
  with negative sampling only works if the negative distribution, the window, and the loss are all
  what you say they are. The rebuild builds pairs from a window, samples negatives from the
  **count^0.75** table (and checks the table against the analytic distribution), trains with a
  hand-written sigmoid, and then tests the only thing a user cares about: nearest neighbours rank
  sensibly, cities cluster, and the **analogy resolves to `queen`** — with a loss that decreased,
  not a loss that was merely printed.

**Every number is exact and every claim is checkable.** Each demo prints `Cross-checks OK: ...` with
the values it verified, then `Demo completed successfully.`; run it twice and the bytes match, run it
with `--quiet` and it writes nothing at all.

The only third-party dependency across the five is `numpy`. Everything — the pattern engine, the
HMM, the TF-IDF matrix, the stemmer, the gradients — is standard library plus arrays.

---

# 🎓 Learning Objectives

- Model an entity as a typed character span and validate it against its own slice
- Resolve overlapping candidates with an explicit, documented priority
- Score span-level extraction with exact-match precision, recall and F1
- Explain why a gazetteer alone is not a recogniser, and a pattern alone is not either
- Train a bigram HMM with add-`alpha` smoothing and keep the tables usable in log space
- Decode with Viterbi and show that the best path beats independent per-token argmax
- Report a majority-class baseline beside an accuracy, and account for every token
- Handle unknown words with an explicit `<UNK>` column rather than a crash
- Score sentences with TF-IDF, then select with an explicit count rule
- Prove an extractive summary is a verbatim, ordered subset of the source
- Separate compression from coverage: a short summary can miss the point
- Build tokenisation as a pipeline of pure, individually testable stages
- Distinguish normalisation, filtering, stemming and n-gram assembly
- Generate skip-gram pairs from a sliding window and sample negatives from count^0.75
- Implement sigmoid and its gradient by hand and train with plain SGD
- Evaluate an embedding by neighbourhood and analogy, not by loss alone
- Make every stage deterministic: fixed seeds, byte-identical demo re-runs

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Named_Entity_Recognizer | Pattern + gazetteer extraction into typed spans, priority resolution, span-level P/R/F1. | 51 | ✅
02 | Pos_Tag_Tagger | Smoothed bigram HMM, Viterbi decoding, majority-tag baseline, per-tag metrics. | 51 | ✅
03 | Text_Summarizer | TF-IDF centroid scoring, explicit selection rule, verbatim subset proof, coverage metrics. | 51 | ✅
04 | Tokenizer_Workshop | Normalise, tokenise, stopword filter, stem, n-gram assembly, funnel statistics. | 50 | ✅
05 | Word2Vec_From_Scratch | Skip-gram with negative sampling, count^0.75 table, neighbour ranking and analogy test. | 66 | ✅

**Total: 269 tests.**

---

# 🧠 Concepts Covered

- Character spans, half-open intervals, and why offsets beat substrings
- Overlap resolution by label priority and by longest match
- Gazetteers as data, patterns as rules, and the blind spot of each
- Exact-match evaluation and the micro/macro distinction
- Gold annotations as a JSON schema with its own validation
- Markov assumptions, transition and emission tables, add-`alpha` smoothing
- Log-space probabilities and underflow
- Viterbi decoding as dynamic programming over a lattice
- The majority-tag baseline and why it is the number to beat
- Unknown-word handling with `<UNK>` emissions
- Sentence splitting with abbreviations and the failure modes it hides
- TF-IDF construction, row normalisation, and centroid scoring
- Extractive vs abstractive summarisation, and why extraction is testable
- Compression and coverage as separate, sometimes opposed metrics
- Unicode-aware normalisation and case folding
- Stopword lists as data, and the corpus they depend on
- Porter-style suffix stripping and its over-stemming failure
- N-grams, vocabulary size, and the combinatorial cost of longer n
- Skip-gram pairs, context windows, and negative sampling
- The count^0.75 unigram distribution and why it is not uniform
- Logistic loss, hand-written gradients, and SGD
- Cosine similarity, nearest neighbours, and analogy arithmetic
- Determinism: seeded sampling, byte-identical demo re-runs

---

# 📁 Repository Structure

```text
19_NLP/
│
├── Named_Entity_Recognizer/
│   ├── src/    ner.py, main.py
│   ├── tests/  test_ner.py
│   └── data/   gazetteer_places.txt, gazetteer_orgs.txt, gold.json
│
├── Pos_Tag_Tagger/
│   ├── src/    hmm_tagger.py, main.py
│   ├── tests/  test_hmm_tagger.py
│   └── data/   corpus.txt
│
├── Text_Summarizer/
│   ├── src/    summarizer.py, main.py
│   ├── tests/  test_summarizer.py
│   └── data/   articles.json
│
├── Tokenizer_Workshop/
│   ├── src/    tokenizer.py, main.py
│   ├── tests/  test_tokenizer.py
│   └── data/   corpus.txt, stopwords.txt
│
└── Word2Vec_From_Scratch/
    ├── src/    word2vec.py, main.py
    ├── tests/  test_word2vec.py
    └── data/   corpus.txt
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI, a
`tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a `.gitignore`, and a
`README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 19_NLP/Pos_Tag_Tagger

python src/main.py --demo                            # offline, deterministic, exit 0
python src/main.py --demo --quiet                     # prints nothing at all
python src/main.py --sentence "the dogs read the book"
python src/main.py --file data/corpus.txt --ratio 0.7 --json out.json
python -m pytest tests -q                             # the suite
```

Every project supports `--demo` (plus `--quiet`), `--json <path>` and offline text input, and adds its
own flags (`--file`, `--text`, `--sentence`, `--gold`, `--index`, `--ratio`, `--n`, `--min-length`,
`--no-stopwords`, `--top`, `--dim`, `--window`, `--negatives`, `--similar`, `--analogy`). No demo
writes into the repository: JSON goes only where you point it.

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
5. no non-ASCII byte in `src/`, `tests/` or the text data files (currency signs are stored as
   JSON `\u` escapes)

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why an entity without offsets cannot be evaluated
- Why two detectors agreeing on the same characters still need a tie-break rule
- Why precision alone rewards a detector that finds nothing
- Why a tag sequence needs transitions, and what a Viterbi lattice buys you
- Why the majority-tag baseline is the first number to report
- Why an accuracy that ignores unknown words is measuring the vocabulary, not the model
- Why an extractive summary is the only kind you can verify verbatim
- Why compression and coverage can disagree, and which one the user asked for
- Why "tokenize" is four decisions wearing one name
- Why stemming silently merges distinct words and how to see it in the counts
- Why an embedding's loss is not its quality, and neighbours are
- Why negative sampling needs its own distribution, and count^0.75 is a choice
- How to make a text pipeline reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `load_gazetteer`, `load_gold`, `load_corpus`, `load_articles`, `load_stopwords`
Values — `Entity`, `HmmModel`, `SummaryResult`, `TokenizeResult`, `Word2Vec`
Extraction — `find_entities`, `_pattern_candidates`, `_gazetteer_candidates`, `_org_candidates`
Scoring — `evaluate`, `evaluate_texts`, `corpus_stats`, `baseline_accuracy`, `token_stats`
Modeling — `train_hmm`, `viterbi`, `build_model`, `train_model`
Summarising — `split_sentences`, `build_tfidf`, `score_sentences`, `summarize`
Tokenising — `normalize`, `tokenize`, `remove_stopwords`, `stem`, `ngrams`, `process`
Embeddings — `build_vocab`, `generate_pairs`, `negative_table`, `_sigmoid`
Rendering — `render_entities`, `render_evaluation`, `render_report`, `to_dict`
Refusal — `NerError`, `TaggerError`, `SummaryError`, `TokenError`, `Word2VecError`
Testing — hand-computed probabilities, span round-trips, baseline comparisons, verbatim subset
checks, seeded determinism, CLI paths, quiet-mode silence

---

# 🚀 Future Improvements

- A shared sentence splitter, so all five projects disagree about abbreviations in one place
- Beam search beside Viterbi, to show what the exact decoder is worth
- Second-order HMM transitions with a sparsity report
- MMR (maximal marginal relevance) beside the centroid scorer, for redundancy in summaries
- A reproducible evaluation harness over several gold files, not one
- Subword units (BPE) beside whitespace tokens, so the `<UNK>` column shrinks
- Skip-gram with subsampling of frequent words, compared against the current baseline
- A category-wide `audit` harness printing all five evidence tables in one shape

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
