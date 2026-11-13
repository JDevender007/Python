<div align="center">

# 🧠 Deep Learning Projects

### A collection of Python projects covering a from-scratch neural network, digit classification, LSTM forecasting, convolutional autoencoders, and text classification — all runnable offline with `--demo`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

This category explores deep learning from first principles to applied models: a pure-NumPy MLP whose hand-derived backprop is gradient-checked against numerical differentiation, a PyTorch digit classifier with confusion-matrix diagnostics, an LSTM next-step forecaster benchmarked against persistence, a convolutional denoising autoencoder measured in PSNR, and a bag-of-words sentiment MLP.

Every project runs **fully offline** with `--demo` — bundled deterministic sample data ships with each project, nothing is downloaded at runtime (no datasets, no weights, no tokenizers), and demos assert their own output. No network, no API keys.

---

# 🎯 Learning Objectives

- Derive and implement backpropagation, then prove it with gradient checking
- Choose initialisation (He/Xavier) and activations deliberately
- Train multiclass classifiers and read per-class confusion diagnostics
- Forecast time series with chronological splits and leakage-free scaling
- Beat honest baselines (majority class, persistence) before trusting a model
- Build convolutional encoders/decoders and evaluate with MSE/PSNR
- Featurise text with train-only vocabularies
- Keep every demo deterministic: seeds, fixed noise banks, idempotent runs
- Budget demo runtime (benchmark, tune epochs, re-verify)
- Design standalone CLI flags that fail fast and never block `--demo`

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Neural_Network_From_Scratch | Pure-NumPy MLP: forward/backprop + gradient check (3.4e-10 error). | ✅
02 | Digit_Recognizer | PyTorch MLP on 1797 bundled 8×8 digits → confusion matrix + ASCII art. | ✅
03 | Time_Series_Predictor | LSTM next-step forecasting vs persistence baseline (+30 % RMSE lift). | ✅
04 | Image_Denoising_Autoencoder | Conv AE denoises 28×28 shapes (+71 % MSE cut, +5.4 dB PSNR). | ✅
05 | Sentiment_MLP_Classifier | Bag-of-words + MLP sentiment with F1/confusion/probabilities. | ✅

---

# 💡 Concepts Covered

- Forward Propagation and the Chain Rule
- Hand-Derived Backpropagation and Numerical Gradient Checking
- He vs Xavier Initialisation; ReLU/tanh/Sigmoid choices
- Sigmoid + Binary Cross-Entropy gradient cancellation
- Mini-Batch Gradient Descent with seeded shuffling
- Multiclass Softmax + Cross-Entropy (logits for stability)
- Confusion Matrices and Per-Class Precision/Recall
- Sequence Forecasting: Sliding Windows, Chronological Splits, Train-Only Scaling
- Persistence Baselines and what "beating them" proves
- LSTM cells vs last-hidden-state readout
- Autoencoders, Latent Bottlenecks, Denoising Objectives
- Strided/Transposed Convolutions and PSNR in dB
- Bag-of-Words featurisation with train-only vocabularies
- Dropout, BCE-with-logits, probability thresholds
- Deterministic DL: seeds, noise banks, idempotent demos

---

# 📁 Repository Structure

```text
17_Deep_Learning/
│
├── Neural_Network_From_Scratch/
├── Digit_Recognizer/
├── Time_Series_Predictor/
├── Image_Denoising_Autoencoder/
├── Sentiment_MLP_Classifier/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── data/             # bundled deterministic sample data
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- NumPy (from-scratch networks, gradient checking)
- PyTorch (MLP, LSTM, convolutional autoencoder, seeded RNG)
- scikit-learn (digits dataset export, CountVectorizer)
- pandas (loading, validation, stratified splits)
- argparse / json / logging / dataclasses
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Neural Network From Scratch | ✅ |
| Digit Recognizer | ✅ |
| Time Series Predictor | ✅ |
| Image Denoising Autoencoder | ✅ |
| Sentiment MLP Classifier | ✅ |

**Completed:** **5 / 5 Projects**

---

# ▶️ Quick Start

```bash
cd 17_Deep_Learning/Neural_Network_From_Scratch

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

---

# 📚 Skills Developed

- Implementing neural networks without a framework (and proving correctness)
- End-to-end PyTorch training loops (seeded, budgeted, deterministic)
- Honest evaluation: baselines, hold-outs, chronological splits
- Denoising evaluation with MSE/PSNR against a noisy-input baseline
- Text classification with leakage-free featurisation
- Demo budgeting: benchmark first, tune epochs, keep tests < 60 s
- Failure-mode design: fast-fail flags, idempotent demos, strict validation
- Modular Programming and Type Hints
- Automated Testing

---

# 🚀 Key Learning Outcomes

- Train and gradient-check a pure-NumPy network on non-linear data
- Classify digits and messages with reproducible PyTorch models
- Forecast a series honestly against the persistence baseline
- Denoise images and quantify the win in dB
- Ship demos that verify themselves and re-run identically

---

# 🔮 Future Enhancements

- Convolutional digit CNN alongside the MLP
- Attention/Transformer forecaster comparison
- Quantised/ONNX export for the autoencoder
- Learning-rate schedulers and early stopping hooks
- Calibration plots for the sentiment probabilities

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
