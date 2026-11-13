<div align="center">

# 🗜 Image Compressor

### A JPEG-style transform codec built from scratch: 8×8 DCT, quality-scaled quantisation, zig-zag scan, run-length coding and a canonical Huffman bitstream. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-2.5.2-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Pillow](https://img.shields.io/badge/Pillow-12.3.0-3776AB?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

A JPEG file is six stages in a row, and only one of them loses information. This project implements all six, without a third-party codec:

```text
8x8 blocks -> 2-D DCT-II -> quantise -> zig-zag -> RLE -> Huffman
```

**The DCT is orthonormal, so it conserves energy exactly.** `dct2` uses the basis matrix `C` with `C Cᵀ = I`, and the demo asserts both the orthonormality and that `(dct2(x)²).sum() == (x²).sum()` for a random block. `idct2` inverts it to `4e-13`, so any visible error after a round trip belongs to quantisation, not to the transform.

**Quantisation is the whole compression story.** The standard luminance table is scaled by JPEG's quality formula (`5000/Q` below 50, `200 − 2Q` above) and clipped to `[1, 255]`, then every coefficient is divided and rounded **half away from zero** — NumPy's `np.rint` uses banker's rounding, which would make `±0.5` behave inconsistently, so `_round_half_away` does it explicitly.

**Zig-zag + RLE turn two-dimensional sparsity into one-dimensional runs.** `zigzag_order` walks anti-diagonals, producing `(0,0), (0,1), (1,0), (2,0), …` and visiting all 64 cells once (asserted with `set`). `rle` emits `(zeros_before, amplitude)` tokens and a `(0, 0)` end-of-block marker when the tail is zeros. Note the subtlety the codec has to handle: a **completely full** block emits no end-of-block token at all, because there is nothing left to skip — so `split_token_blocks` re-splits a flat token stream into per-block lists by *either* seeing `(0,0)` *or* accumulating 64 coefficients.

**Huffman is built per image, and proven lossless.** `huffman_lengths` merges the two lightest nodes with a heap; `canonical_codes` turns the lengths into prefix codes the standard way. The demo asserts the code is prefix-free, that the Kraft sum is exactly `1.0` (a *complete* code), and that decoding the bitstream reproduces the token list. Then the stronger claim: the decoded bitstream reproduces the **quantised coefficients** `array_equal`-exactly, which is what "the entropy stage is lossless" actually means.

**The measured results on the bundled 128×128 photo:**

| Quality | bpp | total bpp | PSNR dB | max error |
| --: | --: | --: | --: | --: |
| 10 | 0.15 | 0.17 | 34.45 | 24 |
| 30 | 0.26 | 0.32 | 41.73 | 19 |
| 50 | 0.37 | 0.45 | 43.96 | 16 |
| 75 | 0.53 | 0.66 | 48.37 | 12 |
| 90 | 0.76 | 0.98 | 52.44 | 7 |
| 100 | 1.82 | 2.28 | 60.56 | 1 |

Quality 50 lands at `0.37 bpp` — `21.9×` smaller than the 8 bpp raw image — with `43.96 dB`, which is high for a real codec at that rate because the source is a smooth, low-noise grey photo. **The demo says so rather than implying the numbers generalise:** every threshold is a bound on *this* image, and PSNR/bit-rate monotonicity in quality is checked as a trend, not as an equality.

**DC carries 93.2% of the energy and the top-left 3×3 carries 99.7%**, which is the quantitative justification for the zig-zag order. `energy_stats` computes that by summing squared coefficients *per grid cell across all blocks* — the obvious bug is to index `[0, 0]` of a reduced array and get one block's DC instead of the image's.

No network, no API keys, no downloads: one bundled 128×128 PNG and a local file in.

---

# ✨ Features

- Orthonormal 8×8 2-D DCT-II and its inverse, both vectorised over block stacks
- JPEG luminance quantisation table with the standard quality scaling
- Round-half-away-from-zero quantisation (`np.rint` uses banker's rounding)
- Canonical zig-zag scan order for any block size
- Run-length coding with `(zeros_before, amplitude)` tokens and end-of-block
- Full-block handling: no EOB token is emitted when all 64 coefficients survive
- Huffman code construction from a per-image histogram, plus canonical codes
- Prefix-freeness and Kraft-sum (completeness) verification
- Edge-replicated padding to a block multiple, with cropping back on decode
- Energy accounting: DC share and top-left 3×3 share
- MSE, PSNR, payload/header byte accounting and bits-per-pixel
- `--demo`, `--file`, `--quality`, `--sweep`, `--save`, `--json`, `--quiet`
- Fast-fail quality validation before the image is read
- Deterministic bundled data: `data/photo_128.png`
- 122 passing pytest tests

---

# 📂 Folder Structure

```text
Image_Compressor/
│
├── src/
│   ├── main.py         # CLI: --quality, --sweep, --save, --json
│   └── compressor.py   # DCT, quantise, zig-zag, RLE, Huffman, demo
│
├── tests/
│   └── test_compressor.py
│
├── data/
│   └── photo_128.png   # 128x128 greyscale, smooth 162-level photo
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 23_Image_Processing/Image_Compressor

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: six quality levels + nine self-checks
python src/main.py --demo

# Compress the bundled photo at quality 50 (default action)
python src/main.py --quality 50

# Print the whole quality sweep
python src/main.py --sweep

# Save the decoded image and the statistics
python src/main.py --quality 90 --save output/rebuilt.png --json output/stats.json

# Your own image
python src/main.py --file data/photo_128.png --quality 75
```

**Input:** a PNG/JPEG up to 2048×2048 (colour images are converted to grey).

**Exit codes:** `0` = success · `2` = usage, validation or IO error.

---

# 🧠 How It Works

```text
image (h, w)
   │  edge-replicate padding to a multiple of 8
   ▼
(r, c, 8, 8) blocks  ── minus 128 ──►  dct2  ──►  coefficients
                                                    │
                                          divide by quant table
                                            round half away
                                                    ▼
                                             quantised ints
                                                    │
                                              zig-zag scan
                                                    ▼
                                      rle: (zeros, amplitude) ...
                                                    │
                                    per-image Huffman histogram
                                                    ▼
                                    canonical codes -> bit string
```

Decoding runs the same list backwards, and the only irreversible step is the rounding inside `quantise`:

```text
bitstream -> tokens -> per-block scans -> zig-zag scatter
          -> dequantise -> idct2 (+128) -> merge -> crop
```

The quality scaling is JPEG's own:

```text
Q < 50    scale = 5000 / Q
Q >= 50   scale = 200 - 2Q
table     = clip(floor((base * scale + 50) / 100), 1, 255)
```

so `Q = 50` reproduces the reference table and `Q = 100` yields an all-ones table (still lossy, but only by rounding: max error 1 grey level).

---

# 🛠 Technologies

- Python 3 standard library (`math`, `heapq`, `json`, `logging`, `argparse`, `pathlib`, `dataclasses`)
- NumPy 2.5.2 (DCT via `einsum`, block reshaping, metrics)
- Pillow 12.3.0 (PNG decode/encode only)
- pytest

No OpenCV, no SciPy, no `zlib`, no external codec.

---

# 📚 Concepts Covered

- Orthonormal DCT-II as a change of basis, and energy conservation
- Block-based transform coding and edge-replicated padding
- Perceptual quantisation tables and quality scaling
- Rounding modes and why banker's rounding is wrong here
- Zig-zag scan order and 2-D-to-1-D sparsity
- Run-length coding with end-of-block markers and the full-block edge case
- Huffman code construction with a heap, and canonical code assignment
- Prefix-freeness and the Kraft inequality as code-validity tests
- Lossless vs lossy stage separation in a codec
- Rate–distortion trade-offs measured with bpp and PSNR
- Coefficient energy concentration as the justification for zig-zag ordering

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**122 tests passed** covering zig-zag completeness and ordering, the DCT basis definition and orthonormality, `dct2`/`idct2` round trips and energy conservation, constant-block DC-only output, quality validation and table bounds, round-half-away behaviour, padding and crop round trips, split/merge block inverses, RLE on all-zero / all-nonzero / sparse blocks, `split_token_blocks` including the full-block case and every malformed stream, Huffman lengths and canonical codes, prefix-freeness, Kraft sums, encode/decode round trips and every decode error path, `compress`/`decompress` determinism and monotonicity, flat-image and non-block-multiple images, MSE/PSNR closed forms, energy statistics, report keys, image IO errors, demo idempotency, and every CLI path including fast-fail quality checks and `--demo` flag rejection.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
