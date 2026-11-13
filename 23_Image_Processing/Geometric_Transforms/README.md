<div align="center">

# 📐 Geometric Transforms

### Rotation, scaling, translation and arbitrary affine warps implemented from scratch with inverse mapping, bilinear or nearest interpolation, and four out-of-bounds modes. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-2.5.2-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Pillow](https://img.shields.io/badge/Pillow-12.3.0-3776AB?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Every image editor's rotate and zoom tools come down to one idea: **do not push pixels forward, pull them backward.** For each output pixel, ask "where in the source did I come from?", use an affine matrix to answer it, and sample the source there. Forward mapping scatters holes; inverse mapping cannot.

**The matrix is the transform.** All matrices here are *destination → source* maps, so composing them means multiplying them in application order:

```text
compose(A, B, C) = A @ B @ C          # apply A, then B, then C
```

Each constructor builds the inverse of the intuitive content transform:

```text
translate(dx, dy)   ->  [[1, 0, -dx], [0, 1, -dy], [0, 0, 1]]
rotate(θ, centre)   ->  R(θ)ᵀ about the centre
scale(s, centre)    ->  1/s about the centre
```

**Sampling is bilinear by default**, so a half-pixel shift blends two neighbours instead of snapping. The demo proves this exactly: a `-0.5` pixel translate on the ramp `[0, 10, 20]` produces `5` and `15`, not a rounded copy. Nearest-neighbour is available for cases where you must not invent grey levels, and the demo asserts its output is a subset of the input's levels.

**Out-of-bounds pixels need a policy**, and there are four: `constant` (fill black), `replicate` (extend the edge), `reflect` (mirror without repeating the edge) and `wrap` (tile). They are not cosmetic — they decide what a rotated corner looks like. `wrap` is verified against `np.roll` for integer shifts, which is an exact identity rather than a visual similarity.

**Exactness where exactness is possible.** A 90° rotation of a lattice is compared to `np.rot90` with `array_equal`, and a 90°/−90° pair must round-trip bit-for-bit. The identity warp is byte-identical to the input. General rotations are a different story: bilinear resampling is a low-pass filter, so a 30° rotate followed by −30° gives about 24 dB PSNR rather than an identical image. That number is asserted, not glossed over.

**Composition order is tested on a smooth image, on purpose.** Two bilinear resamples of a hard-edged checkerboard differ from one resample on *every* edge, whatever the order — so a checkerboard cannot detect a reversed composition. The demo instead builds a Gaussian blob, where the correct order scores about 34 dB against the stepwise chain and the reversed order about 27 dB. The check asserts both: correct is above 30 dB **and** reversed is at least 3 dB worse, so the test cannot pass by accident.

**Metrics keep it honest.** `mse` and `psnr` (`10·log10(255²/MSE)`, `inf` for identical images) are computed from scratch and used throughout the demo table.

No network, no API keys, no downloads: two bundled 128×128 PNGs and a local file in.

---

# ✨ Features

- Inverse-mapping affine warp with bilinear or nearest sampling
- Translation, rotation about a centre, and scaling about a centre
- Arbitrary 2×3 / 3×3 affine matrices and left-to-right composition
- Four out-of-bounds modes: constant, replicate, reflect, wrap
- Matrix validation: shape, finiteness, singularity, bottom row
- 2:1 aspect ASCII preview with a full shade ramp
- Image loading with size limits and grey conversion, PNG saving
- Mean/std/min/max statistics per transform
- MSE and PSNR metrics from scratch
- Fast-fail CLI flag validation before the image is loaded
- `--rotate`, `--scale`, `--translate`, `--interp`, `--edges`, `--out`, `--json`, `--quiet`
- Deterministic bundled data: `checker_128.png`, `shapes_128.png`
- 91 passing pytest tests

---

# 📂 Folder Structure

```text
Geometric_Transforms/
│
├── src/
│   ├── main.py      # CLI: --rotate, --scale, --translate, --json, --out
│   └── geometry.py  # matrices, warp, edge modes, metrics, demo
│
├── tests/
│   └── test_geometry.py
│
├── data/
│   ├── checker_128.png  # hard-edged 8 px checkerboard
│   └── shapes_128.png   # shapes with smooth and hard edges
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 23_Image_Processing/Geometric_Transforms

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: all transforms, both interpolations, order check
python src/main.py --demo

# Rotate 30 degrees
python src/main.py --file data/shapes_128.png --rotate 30

# Scale with wrap-around edges, nearest sampling
python src/main.py --file data/checker_128.png --scale 1.5 --edges wrap --interp nearest

# Chained transform, PNG + JSON out
python src/main.py --file data/shapes_128.png --rotate 45 --scale 1.2 \
                   --translate "10,-5" --out output/rot.png --json output/stats.json
```

**Input:** a PNG/JPEG up to 512×512 (colour images are converted to grey).

**Exit codes:** `0` = success · `2` = usage, validation or IO error.

---

# 🧠 How It Works

```text
source image ──► (h, w) pixel grid
                    │
            dest -> src affine matrix
                    │
       src_x, src_y for every output pixel
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
   edge policy              interpolation
 constant / replicate        bilinear (4 taps)
 reflect / wrap              nearest  (1 tap)
        │                        │
        └───────────┬────────────┘
                    ▼
             clip + round to uint8
                    ▼
              output image
```

The composition rule, written out for the demo pipeline:

```text
dest -> src  =  M_scale @ M_rotate @ M_translate
content order =  scale, then rotate, then translate
```

---

# 🛠 Technologies

- Python 3 standard library (`math`, `json`, `logging`, `argparse`, `pathlib`)
- NumPy 2.5.2
- Pillow 12.3.0 (PNG decode/encode only)
- pytest

No OpenCV, no SciPy, no plotting library.

---

# 📚 Concepts Covered

- Inverse mapping vs forward mapping
- Homogeneous 2D affine matrices and composition order
- Rotation/scaling about an arbitrary centre
- Bilinear interpolation as a 4-tap weighted sum
- Nearest-neighbour sampling and level preservation
- Boundary policies: constant, replicate, reflect, wrap
- Exact identities (`np.rot90`, `np.roll`) as ground truth
- Interpolation loss measured with PSNR
- Matrix degeneracy checks (singular area, bottom row)
- Fast-fail CLI validation

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**91 tests passed** covering matrix construction and validation (finiteness, shape, singularity, bottom row), composition order and identity, every interpolation and edge mode, exact identities (identity warp, `np.rot90`, `np.roll`, midpoint blend), constant-mode border zeroing, replicate clamping, ASCII preview shape/ramp/flat-image handling, image IO limits and round-trips, MSE/PSNR closed forms, demo idempotency, and every CLI path including `parse_translate` failures and fast-fail flag checks.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
