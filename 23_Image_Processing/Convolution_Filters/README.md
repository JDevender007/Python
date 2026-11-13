<div align="center">

# 🔲 Convolution Filters

### Box, gaussian, sharpen and emboss kernels implemented from scratch in NumPy — separable fast paths, four edge-padding modes, and an ASCII preview. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-Convolution-4D77CF?style=for-the-badge&logo=numpy&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Convolution Filters applies the four classic image kernels — **box, gaussian, sharpen, emboss** — using a 2D convolution written from scratch (sliding-window view + `einsum`, kernel flipped for true convolution). No OpenCV, no scipy: just NumPy and Pillow.

The `--demo` loads the bundled `shapes_128.png`, filters it with every kernel, compares all four **edge modes** (`constant`, `reflect`, `replicate`, `wrap`) on a bundled gradient ramp, renders an **ASCII preview** of the embossed result, and asserts its own math: PSNR of an image against itself is `inf`, a size-1 box filter is the identity, kernels summing to 1 reproduce constant images exactly, the separable gaussian matches the full 2D kernel to `< 1e-6`, and edge modes only affect image borders. **No network, no API keys, no downloads.**

---

# ✨ Features

- From-scratch `convolve()` with kernel flipping, `einsum` window sums, and `float64` math
- Kernels: box (any size), gaussian (auto or fixed odd size), sharpen, emboss — all summing to 1
- `convolve_separable()`: two 1D passes that reproduce the full 2D result (< 1e-6 error)
- Four edge modes: `constant` (zero), `reflect`, `replicate`, `wrap` — borders differ, interiors never do
- `filter_report()` stats (mean/std/range/MSE/PSNR) + PNG output + JSON export
- ASCII thumbnails via a shade ramp (no plotting libraries)
- Strict validation: image dimensions, kernel size, sigma, mode names — fast-fail before filtering
- Deterministic: identical input → byte-identical output on every run
- 55 passing pytest tests

---

# 📂 Folder Structure

```text
Convolution_Filters/
│
├── src/
│   ├── main.py     # CLI: --demo, --file, --filter, --sigma, --edges, --out, --json
│   └── filters.py  # padding, convolution, kernels, separable path, stats, demo
│
├── tests/
│   └── test_filters.py
│
├── data/
│   ├── shapes_128.png   # 128x128 procedural shapes (gradient + rect + disc + line)
│   └── gradient_64.png  # 64x64 horizontal 0..255 ramp for edge-mode checks
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 23_Image_Processing/Convolution_Filters

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: all four filters, edge modes, ASCII preview, cross-checks
python src/main.py --demo

# Gaussian blur your own image (separable fast path)
python src/main.py --file photo.png --filter gaussian --sigma 2.0

# Box blur with wrap-around edges + JSON stats
python src/main.py --file photo.png --filter box --size 5 --edges wrap --json stats.json

# Sharpen and save the result
python src/main.py --file photo.png --filter sharpen --out output/sharp.png
```

Input schema:

- Any PNG/JPEG **grayscale or RGB** image (RGB is converted to luminance), minimum **8×8**, maximum **512×512** pixels.
- `--filter` ∈ `box | gaussian | sharpen | emboss` (default `gaussian`).
- `--sigma` > 0 (gaussian only, default 1.5); `--size` ≥ 1 and odd for gaussian (box may be any size ≥ 1).
- `--edges` ∈ `constant | reflect | replicate | wrap` (default `reflect`).

**Exit codes:** `0` = success · `2` = usage/filter/input error.

---

# 🧠 How It Works

```text
input image (H x W uint8)
        │
        ▼  pad by (kernel-1)/2 on each side, per --edges mode
  ┌──────────────────────────────────────────────┐
  │ constant → 0   reflect → mirror (no repeat)  │
  │ replicate → edge pixel   wrap → circular     │
  └──────────────────────────────────────────────┘
        │
        ▼  sliding_window_view → einsum("ijkl,kl->ij")
  out[y, x] = Σ kernel[ flipped ] · padded[ y+i, x+j ]      (float64)
        │
        ├─ gaussian: convolve_separable() = horizontal 1D pass + vertical 1D pass
        │            (identical result, O(W·K) instead of O(W·K²))
        ▼
  rint + clip to 0..255 → uint8 ──► stats (mean/std/MSE/PSNR) + optional PNG/JSON
```

Details worth knowing:

- **True convolution** flips the kernel (`kernel[::-1, ::-1]`); symmetric kernels (box, gaussian, sharpen) are unaffected, while emboss gets its consistent dark-to-light direction.
- **Separable gaussian** = outer product of two 1D kernels, so filtering row-by-row then column-by-row is mathematically identical — the demo proves it to `< 1e-6` and tests it across all four edge modes.
- **Edge modes only touch borders**: the demo asserts the interior of `constant` equals the interior of `reflect`, while borders differ — and hand-checks `wrap` at the ramp's first pixel (mean of 255, 0, 4 → **86**).
- **Kernels sum to 1**, so flat regions keep their grey value — the demo filters a constant image through every kernel and allows at most ±1 from uint8 rounding.

---

# 🛠 Technologies

- Python 3
- NumPy (`sliding_window_view`, `einsum`, `np.pad`, float64 math)
- Pillow (PNG loading/saving, RGB → grey)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- 2D convolution vs correlation (kernel flipping)
- Padding strategies: constant, reflect, replicate, wrap and where each is appropriate
- Separable kernels and the O(K²) → O(2K) speedup
- Why normalised kernels (sum = 1) preserve constant regions
- Clipping and rounding when returning to `uint8`
- PSNR/MSE as image-fidelity metrics (`PSNR(x, x) = inf`)
- ASCII raster rendering without plotting dependencies
- Fast-fail flag validation before expensive work
- Deterministic, idempotent demos with self-assertions

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**55 tests passed** covering every validation rule (missing/unreadable files, image dimensions, kernel sizes, sigma, edge modes), kernel properties (sums, symmetry, known values), convolution correctness against an independent naive loop and a hand-computed cross-kernel sum, constant preservation, separable-vs-full equality across all edge modes, border-only edge behaviour, PSNR/MSE known values, ASCII rendering, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
