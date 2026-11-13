<div align="center">

# 🖼️ Image Denoising Autoencoder

### A convolutional autoencoder that removes Gaussian noise from 28×28 shape images — bundled dataset, PSNR/MSE metrics vs the noisy baseline, per-shape breakdowns, and ASCII previews. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-Conv%20AE-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Image Denoising Autoencoder trains a small **convolutional autoencoder** to recover clean 28×28 grayscale images from noisy ones. The pipeline: load a local image CSV → corrupt the pixels with seeded Gaussian noise (σ = 0.40, clamped to [0, 1]) → train `Conv(1→8→16) → latent 32 → ConvTranspose back → sigmoid` to reconstruct the **clean** target from the **noisy** input → evaluate on a sealed hold-out split.

The evaluation is honest by construction: reconstruction MSE and PSNR are reported **next to the noisy-input baseline** (what you'd get by doing nothing). The demo's bundled dataset (600 deterministic circle/square/cross renders) ships in `data/shapes.csv`, and after 40 epochs the autoencoder cuts MSE by **~71 %** (0.0777 → 0.0227) and gains **+5.35 dB PSNR** — the demo asserts both margins before declaring success.

Everything runs on local files: no network, no dataset downloads, no pre-trained weights. The loader validates every pixel column (0–1 grayscale), integer labels 0–2, ≥ 300 images, and ≥ 20 images per shape class. Determinism is guaranteed: seeded weight init, seeded noise banks, and a seeded shuffle generator — the demo re-trains and compares histories bit-for-bit.

---

# ✨ Features

- Convolutional denoising AE: strided conv encoder → 32-d latent → transposed-conv decoder with sigmoid output
- Seeded Gaussian noise corruption with fixed noise banks (fully deterministic)
- Hold-out MSE/PSNR vs the noisy-input baseline, with % reduction and dB gain
- Per-shape reconstruction MSE breakdown (circle / square / cross)
- `encode(image)` → latent vector; `denoise(image)` → reconstructed 784 pixels
- ASCII previews: noisy input, AE output, and clean target side by side (14×14 grids)
- Strict validation: pixel ranges, integer labels, class minimums, finiteness
- `--denoise "0,0,0.4,..."` classifies a single 784-value image (bundled-data fallback)
- Deterministic: seeded init, noise, shuffle, and split — identical results every run
- 56 passing pytest tests

---

# 📂 Folder Structure

```text
Image_Denoising_Autoencoder/
│
├── src/
│   ├── main.py          # CLI: --demo, --file, --denoise, --epochs, --sigma, --json
│   └── autoencoder.py   # loading, noise, DenoisingAE, training, PSNR, ASCII, demo
│
├── tests/
│   └── test_autoencoder.py
│
├── data/
│   └── shapes.csv       # 600 images x 784 pixels (0..1) + label 0..2
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 17_Deep_Learning/Image_Denoising_Autoencoder

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: train, denoising report, ASCII previews, cross-checks
python src/main.py --demo

# Train on your own image CSV with more epochs / a wider latent
python src/main.py --file shapes.csv --epochs 60 --latent 48

# Denoise one image given as 784 comma-separated values 0..1
python src/main.py --denoise "0,0,0.4,...,0"

# Tune the corruption level and export metrics
python src/main.py --file shapes.csv --sigma 0.3 --json metrics.json
```

Input schema (header row required):

```csv
image_0,image_1,...,image_783,label
0,0,0.4,1,1,...,0,1
```

(`label` is 0 = circle, 1 = square, 2 = cross; pixels are 0–1; ≥ 300 images, ≥ 20 per class.)

**Exit codes:** `0` = success · `2` = usage/schema/config/prediction error.

---

# 🧠 How It Works

```text
shapes.csv ──► validate (pixels 0..1, labels 0..2, all classes)
                        │
                        ▼  stratified 75 / 25 split
        x_train ──► + seeded N(0, 0.40²) noise ──► clamp [0,1] = noisy input
                        │
                        ▼
   Conv2d 1→8 s2 (14x14) → ReLU → Conv2d 8→16 s2 (7x7) → ReLU
                        │
                   Flatten → Linear(784, 32)          ← latent code
                        │
   Linear(32, 784) → ReLU → Unflatten(16,7,7)
                        │
   ConvTranspose 16→8 (14x14) → ReLU → ConvTranspose 8→1 (28x28) → Sigmoid
                        │
                        ▼  MSE(reconstruction, CLEAN target), Adam
   hold-out: MSE / PSNR vs noisy baseline, per-shape MSE, ASCII previews
```

Why it works: the encoder must discard the noise while preserving structure — but the latent is only 32 numbers for 784 pixels (a 24× compression), so it can only keep what matters (shape, position, thickness). Gaussian noise is by definition unstructured, so it doesn't survive the bottleneck. The decoder then paints the clean image back at full resolution.

**PSNR** (peak signal-to-noise ratio) converts MSE into decibels against the peak value of 1.0: `PSNR = 10·log₁₀(1 / MSE)`. Every +3 dB ≈ halving the error. The demo's jump from 11.1 dB (noisy) to 16.4 dB (reconstructed) is a real, visible cleanup — the ASCII panels show speckled input becoming a clean shape.

Two determinism details: the noise banks are generated from **fixed seeds before training** (so every epoch sees the same corruptions), and the train/test splits are stratified per class so all three shapes are represented in both segments.

---

# 🛠 Technologies

- Python 3
- PyTorch (`nn.Conv2d`, `nn.ConvTranspose2d`, `nn.Linear`, `MSELoss`, `Adam`, seeded RNG)
- pandas / numpy (loading, validation, MSE/PSNR, per-class masks)
- argparse / json / logging / dataclasses
- pytest

---

# 📚 Concepts Covered

- Autoencoders: encoder/decoder, latent bottlenecks, reconstruction loss
- Denoising autoencoders (corrupt input, reconstruct clean target)
- Strided convolutions vs pooling for downsampling
- Transposed convolutions for learned upsampling
- Sigmoid output + MSE for [0, 1]-valued image reconstruction
- PSNR in dB and how to compare it against a baseline
- Seeded noise banks for reproducible corruption
- Stratified splitting across shape classes
- Compression as a regulariser (32 numbers vs 784 pixels)
- Hold-out discipline: never evaluate on training images

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**56 tests passed** covering every validation rule (pixel ranges, labels, class minimums, row counts, non-finite values), noise determinism and clamping, seeded model equality, PSNR known values (0.01 → 20 dB, 0 → ∞), training metrics, reported-MSE-vs-stored-reconstructions consistency, encode/denoise APIs (shape, range, wrong length, NaN), ASCII rendering shape, parsing helpers, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
