<div align="center">

# 🧠 Deep Learning Projects

### Five networks trained on a laptop, with no GPU, no download, and no pretrained weights. The subject is not the architecture — it is the evidence: a backpropagation you can verify numerically, a loss that is not the metric you report, a validation number that has to be reproduced from the confusion matrix, a vocabulary that must never see the test split, and a forecast that has to beat the last value you already knew.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-Deep%20Learning-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-From%20Scratch-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)

</div>

---

# 📖 About

Five projects, one shared discipline: every network is trained from a seeded initialisation on a
bundled CSV, in a few seconds, on a CPU. Two of them use PyTorch, one is a NumPy implementation of
forward and backward passes, one trains an autoencoder on images of shapes, and one forecasts a
univariate series.

Nothing is downloaded, nothing is pretrained, and no demo writes model files into the repository. Every
demo finishes by printing the values it verified: `Cross-checks OK: ...` then
`Demo completed successfully.`

**The lesson of each project is different, on purpose.** Five variations on "add a layer" would teach
nothing; five different ways a training run can look successful and mean nothing is the subject.

- **Neural_Network_From_Scratch** — *backpropagation is a claim, and a claim can be checked.* A
  gradient that is merely "small enough to learn something" may still be the wrong gradient, and an
  accuracy of 1.0 on a separable dataset says more about the dataset than the network. The rebuild
  implements forward and backward passes in NumPy, compares analytic gradients against numerical
  differentiation on two architectures (**max relative error 3.4e-10**), reports the mean-predictor
  baseline beside the hold-out score, and shows the loss curve falling from **0.645 to 0.001**.
- **Digit_Recognizer** — *a validation number must survive being recomputed.* A softmax classifier
  that reports 0.94 while its confusion matrix counts a different number of rows is reporting two
  different things. The rebuild trains a small fully-connected net on 8×8 digit pixels, recomputes
  accuracy from the predictions, requires the matrix to count all **450 test images**, requires every
  class recall above 0.6 so no digit is silently abandoned, and confirms a seeded re-run reproduces
  the metrics — **hold-out 0.942**.
- **Image_Denoising_Autoencoder** — *the loss you train on is not the metric you report.* An
  autoencoder minimising pixel MSE will happily report a small loss while the image is still visibly
  noisy, and a denoiser has an obvious baseline: the noisy input itself. The rebuild trains on
  corrupted shapes, scores the reconstruction against the **clean** target in both MSE and PSNR, and
  requires an improvement over the noisy input — **MSE 0.02266 vs 0.07774 (a 70.9% reduction), PSNR
  11.1 → 16.4 dB**.
- **Sentiment_MLP_Classifier** — *the vectoriser is part of the model, so it belongs inside the
  split.* Fitting the vocabulary on all the text leaks the test messages, and a probability threshold
  is what turns a score into a label. The rebuild fits the vocabulary on training rows only, records
  the vocabulary size in the result, reports precision/recall/F1 beside the confusion matrix, and
  checks that the label returned matches the thresholded probability — **hold-out 0.992, F1 0.992,
  vocabulary 69, 124 test messages**.
- **Time_Series_Predictor** — *the baseline for a forecast is the last value you already have.*
  Reporting an RMSE of 0.31 tells you nothing until you know the persistence error, and a correlation
  of 0.98 between predictions and targets can coexist with a model that only tracks the level. The
  rebuild standardises the series with a stored `mu`/`sigma`, trains an LSTM on sliding windows,
  inverts the scaling before scoring, and requires an improvement over persistence — **RMSE 0.3146
  vs 0.4524 persistence (30.5% lower), correlation 0.988**.

**Determinism is part of the contract.** `torch.manual_seed` and `numpy.random.default_rng` make a
re-run produce the same weights, the same loss curve and the same metrics; the test suites assert that
directly, and also assert that a different seed changes the result — otherwise "deterministic" would
just mean "broken".

---

# 🎓 Learning Objectives

- Implement a forward pass and a backward pass by hand and check the gradients numerically
- Explain why a numerical gradient check is the only proof a backprop implementation works
- Seed PyTorch and NumPy so a training run is reproducible, and prove a different seed changes it
- Build a small classifier, a softmax head, and an autoencoder in PyTorch
- Choose a loss that matches the task, then choose a *different* metric to report
- Compute PSNR and MSE against a clean target, and treat the corrupted input as a baseline
- Recompute accuracy from predictions and prove the confusion matrix counts the test set
- Watch per-class recall so a majority class cannot hide a dead class
- Keep a vectoriser inside the pipeline so it can only fit on training rows
- Turn a probability into a label with an explicit threshold
- Build sliding windows for a time series and keep targets inside their segment
- Standardise a series with stored statistics and invert the scaling before scoring
- Compare a forecast against persistence, the strongest trivial baseline
- Report a correlation only alongside the error it accompanies
- Write a demo that asserts its own training evidence instead of printing it

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Digit_Recognizer | Fully-connected classifier on 8×8 digits, per-class recall, confusion audit, CLI inference. | 50 | ✅
02 | Image_Denoising_Autoencoder | Autoencoder on corrupted shapes; MSE and PSNR against the clean target, noisy baseline. | 56 | ✅
03 | Neural_Network_From_Scratch | NumPy MLP with hand-written backprop, numerical gradient check, baseline comparison. | 51 | ✅
04 | Sentiment_MLP_Classifier | Bag-of-words MLP, training-only vocabulary, precision/recall/F1, single-message scoring. | 52 | ✅
05 | Time_Series_Predictor | LSTM forecaster on sliding windows, persistence baseline, RMSE/MAE/correlation. | 51 | ✅

**Total: 260 tests.**

---

# 🧠 Concepts Covered

- Forward propagation, backpropagation, and the chain rule in matrix form
- Numerical gradient checking with a relative-error tolerance
- Binary cross-entropy, mean squared error, and choosing a loss for the task
- Sigmoid, ReLU and tanh activations and their derivative behaviour
- He and Xavier initialisation, and why the scale depends on the activation
- Mini-batch gradient descent and the learning curve
- Seeded initialisation: `torch.manual_seed`, `np.random.default_rng`
- Train/validation splitting with stratification, and split arithmetic
- Softmax classification with per-class support and recall
- Autoencoders: encoder, bottleneck, decoder, and reconstruction error
- PSNR as a logarithmic image-fidelity metric, and its degenerate cases
- Denoising as a supervised task with a corrupted input and a clean target
- Bag-of-words vectorisation, unigrams and bigrams, vocabulary as fitted state
- Leakage prevention: fitting preprocessing inside the split only
- Probability thresholds and the label they imply
- Sliding windows for univariate forecasting, and window/target alignment
- LSTM sequence modelling with a last-step linear head
- Standardisation with stored `mu`/`sigma`, and inverting it before scoring
- Persistence forecasting as the baseline every model must beat
- RMSE, MAE, Pearson correlation, and what each one misses
- Deterministic training and byte-identical demo re-runs

---

# 📁 Repository Structure

```text
17_Deep_Learning/
│
├── Digit_Recognizer/
│   ├── src/    digits.py, main.py
│   ├── tests/  test_digits.py
│   └── data/   digits.csv
│
├── Image_Denoising_Autoencoder/
│   ├── src/    autoencoder.py, main.py
│   ├── tests/  test_autoencoder.py
│   └── data/   shapes.csv
│
├── Neural_Network_From_Scratch/
│   ├── src/    mlp.py, main.py
│   ├── tests/  test_mlp.py
│   └── data/   dataset.csv
│
├── Sentiment_MLP_Classifier/
│   ├── src/    sentiment.py, main.py
│   ├── tests/  test_sentiment.py
│   └── data/   messages.csv
│
└── Time_Series_Predictor/
    ├── src/    predictor.py, main.py
    ├── tests/  test_predictor.py
    └── data/   series.csv
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI, a
`tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a `.gitignore`, and a
`README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 17_Deep_Learning/Neural_Network_From_Scratch

python src/main.py --demo                     # offline, deterministic, exit 0
python src/main.py --demo --quiet             # prints nothing at all
python src/main.py --file data/dataset.csv --hidden 16,16 --epochs 400
python -m pytest tests -q                     # the suite
```

Every project supports `--demo` (plus `--quiet`), `--file <csv>` and `--json <path>`, and adds its own
flags (`--epochs`, `--lr`, `--hidden`, `--layers`, `--seed`, `--window`, `--text`, `--pixels`,
`--predict`). No demo writes weights or reports into the repository: JSON goes only where you point it.

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
5. no non-ASCII byte in `src/`, `tests` or the text data files

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why a gradient check is the difference between a network and a random number generator
- Why "it learned something" is not evidence, and a baseline is
- Why the loss you optimise and the metric you report are two different decisions
- Why a denoiser must be scored against the clean image, not the noisy one
- Why a confusion matrix and an accuracy can contradict each other
- Why per-class recall exposes a class the model gave up on
- Why a vectoriser fitted before the split is leakage, not convenience
- Why a probability is not a label until you choose a threshold
- Why a forecast has to beat the last value you already knew
- Why determinism needs a second seed to prove it is not a constant
- How to write a training demo whose claims are its own assertions

---

# 🧩 Patterns Included

Parsing — `load_data`, `load_digits_data`, `load_images`, `load_messages`, `load_series`
Values — `TrainResult`, `DigitResult`, `AEResult`, `SentimentResult`, `ForecastResult`
Networks — `MLP`, `DigitNet`, `DenoisingAE`, `SentimentMLP`, `LSTMForecaster`
Training — `train_model`, `fit`, `gradients`, `gradient_check`, `_stratified_split`
Evaluation — `_metrics`, `psnr`, confusion matrices, baselines, `to_dict`
Inference — `predict_proba`, `predict`, `forecast`, `denoise`, `encode`, `parse_pixels`
Refusal — `MLPError`, `DigitError`, `AError`, `SentimentError`, `SeriesError`
Reporting — `render_report`, `to_dict`, `--json`, ASCII digit rendering
Testing — gradient checks, metric identities, seeded determinism, seed sensitivity, CLI paths,
quiet-mode silence

---

# 🚀 Future Improvements

- A shared training harness, so the five projects report loss curves in one shape
- Learning-rate schedules and early stopping, with the patience recorded
- A convolutional denoiser beside the fully-connected one, for a fair architecture comparison
- Batch normalisation in the from-scratch MLP, with the gradient check extended to its parameters
- Uncertainty on the forecast: prediction intervals from residual quantiles
- A confusion-matrix renderer shared across the classification projects
- A CPU/GPU switch that leaves the demo output unchanged
- A category-wide `audit` harness comparing all five evidence tables

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
