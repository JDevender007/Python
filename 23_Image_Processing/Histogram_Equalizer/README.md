<div align="center">

# 📊 Histogram Equalizer

### Global CDF equalization and a CLAHE-style local limiter implemented from scratch — before/after spread statistics, PSNR-vs-original report, and ASCII histograms. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-Histograms-4D77CF?style=for-the-badge&logo=numpy&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Histogram Equalizer brightens and stretches low-contrast images using two from-scratch algorithms: **global histogram equalization** (the classic CDF mapping `round(255 · (cdf − cdf_min)/(N − cdf_min))`) and a **CLAHE-style local limiter** (tile grids, clip limits with uniform redistribution across occupied levels, and bilinear interpolation between per-tile mappings). No OpenCV, no scipy — just NumPy and Pillow.

The `--demo` loads the bundled `lowcontrast_128.png` (a 82–164 grey-range squeeze of a shapes scene), reports **before/after statistics** (mean, spread/`std`, range, bins used, **PSNR vs original**), renders **ASCII histograms** before and after, then repeats the comparison on `flat_noise_128.png` to show the whole point of CLAHE: the global method amplifies noise (std 6 → 74) while the clip-limited version keeps it in check (→ 51). Self-assertions cover PSNR(x, x) = `inf`, the exact 0..255 stretch, monotonicity of the mapping, uniform images passing through untouched, and byte-identical re-runs. **No network, no API keys, no downloads.**

---

# ✨ Features

- `histogram()` / `cumulative_counts()` — 256-bin counts and monotone CDF, conserved pixel counts
- `equalize_global()` — exact CDF LUT with `cdf_min` subtraction; uniform images unchanged
- `equalize_clahe()` — `tiles × tiles` grid, per-tile clipping at `clip_limit · pixels/256`, excess redistributed over occupied levels, bilinear blend of the four nearest tile LUTs
- `histogram_stats()` — mean, std (spread), range, occupied bins, pixel count
- `ascii_histogram()` — grouped ASCII bar chart (no plotting libraries)
- `render_report()` — before/after table + PSNR-vs-original in dB
- Strict validation: image dimensions, `clip > 0`, tile grid divisibility — fast-fail before processing
- Deterministic: identical input → identical output on every run
- 42 passing pytest tests

---

# 📂 Folder Structure

```text
Histogram_Equalizer/
│
├── src/
│   ├── main.py       # CLI: --demo, --file, --method, --clip, --tiles, --out, --json, --ascii
│   └── histogram.py  # histogram/CDF, global eq, CLAHE, stats, ASCII, report, demo
│
├── tests/
│   └── test_histogram.py
│
├── data/
│   ├── lowcontrast_128.png  # 128x128 grey-squeezed scene (range 82..164)
│   └── flat_noise_128.png   # 128x128 flat grey + seeded gaussian noise
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 23_Image_Processing/Histogram_Equalizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: global + CLAHE, before/after stats, ASCII histograms, cross-checks
python src/main.py --demo

# Global CDF equalization of your own image
python src/main.py --file photo.png

# CLAHE with a tighter clip limit and a finer grid + JSON stats
python src/main.py --file photo.png --method clahe --clip 3.0 --tiles 4 --json stats.json

# Save the equalized image and print the result histogram
python src/main.py --file photo.png --out output/eq.png --ascii
```

Input schema:

- Any PNG/JPEG **grayscale or RGB** image (RGB → luminance), minimum **8×8**, maximum **512×512** pixels.
- `--method` ∈ `global | clahe` (default `global`).
- `--clip` > 0 (default 2.0) — CLAHE clipping strength, in multiples of the average bin count.
- `--tiles` ≥ 2 (default 8) — both image sides must be divisible by it.

**Exit codes:** `0` = success · `2` = usage/parameter/input error.

---

# 🧠 How It Works

```text
input (uint8, H x W)
        │
        ├── global ─────────────────────────────────────────────┐
        │   hist[256] = bincount(pixels)                        │
        │   cdf = cumsum(hist);  cdf_min = first non-zero       │
        │   LUT[x] = round(255 * (cdf[x] - cdf_min) / (N - cdf_min))
        │   out = LUT[input]                                    │
        │                                                       ▼
        ├── clahe ────────────────────────────────────   before/after stats
        │   split into tiles x tiles blocks               mean / std / range
        │   per tile: clip hist at ceil(limit*px/256),    bins used / PSNR
        │             spread excess over occupied bins            │
        │             equalise -> 256-entry tile LUT             ▼
        │   per pixel: bilinear blend of the 4 nearest      ASCII histogram
        │              tile LUTs at tile-centre coords      before / after
        ▼
   rint + clip -> uint8 ──► optional PNG + JSON
```

Details worth knowing:

- **`cdf_min` subtraction** guarantees the darkest occupied level maps to 0 and the brightest to 255 — that's the full-range stretch the demo asserts (`min 0, max 255`).
- **Monotone by construction**: the CDF never decreases, so a brighter input level can never map to a darker output — the demo verifies this on an ascending ramp.
- **Uniform images short-circuit**: nothing to stretch, so they return unchanged instead of dividing by zero.
- **Why clip?** Unconstrained equalisation of a noisy flat patch turns sensor noise into huge swings (demo: std 6 → 74). CLAHE's clip limit flattens each tile's peaks first, spreading only a bounded amount of contrast (→ 51), while still localising the mapping to each region's own range.
- **Redistribution goes to occupied levels only**: pushing the clipped mass into empty bins below the range would quietly eat the tile's dynamic range.

---

# 🛠 Technologies

- Python 3
- NumPy (`bincount`, `cumsum`, fancy indexing for LUT blends, vectorised bilinear interpolation)
- Pillow (PNG loading/saving, RGB → grey)
- argparse / json / logging
- pytest

---

# 📚 Concepts Covered

- Histograms, CDFs, and the classic equalisation mapping
- Why `cdf_min` makes the mapping hit both 0 and 255
- Local (tile-based) vs global equalisation and halftoning artefacts
- CLAHE: clip limits, uniform excess redistribution, and why they tame noise
- Bilinear interpolation between tile mappings to avoid block seams
- PSNR as a fidelity-vs-original measure (equalisation trades PSNR for spread)
- Reading "spread" (`std`) and "bins used" as contrast indicators
- Fast-fail parameter validation (clip, tile grid) before image work
- Deterministic, idempotent demos with self-assertions

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**42 tests passed** covering every validation rule (unreadable files, image dimensions, fractional/out-of-range pixels, clip limits, tile grids, method names), exact known-value mappings (`[[0,128]] → [[0,255]]`), CDF monotonicity, pixel-count conservation, uniform-image passthrough, CLAHE range/spread/intermediate-level effects, noise limiting vs global, clip-limit behaviour, PSNR/MSE known values, ASCII histogram rendering, report sections, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
