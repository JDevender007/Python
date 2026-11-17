<div align="center">

# 🖼️ Image Processing Projects

### Five pixel pipelines built from first principles, with the algebra as the test suite. A kernel is a linear operator with identities; a warp is a matrix plus an interpolation choice; equalisation is a monotone remap, not a contrast knob; a codec is a chain of invertible steps around one lossy step; and morphology is an algebra with duals and fixed points.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-From%20Scratch-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Pillow](https://img.shields.io/badge/Pillow-Image%20I%2FO-77A9BE?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)

</div>

---

# 📖 About

Five projects that operate on grayscale images bundled in `data/` (128×128 PNGs, small enough to
inspect and diff). Pillow is used for I/O only; the algorithms — convolution, warping, histogram
mapping, DCT, Huffman coding, morphology — are hand-written on `numpy` arrays.

What makes them checkable is that **image processing is algebra**, and algebra has identities:

- a box kernel of size 1 is the identity operator
- a translation by `(dx, dy)` with wrap is `np.roll`
- equalisation on a uniform image changes nothing
- an orthonormal DCT followed by its inverse returns the input
- erosion is the dual of dilation, and opening is idempotent

Each project is built around a different way a pixel pipeline can look convincing and be wrong.

- **Convolution_Filters** — *a kernel is a linear operator, so its identities are testable.* A filter
  demo that prints a pretty image cannot tell you whether the border handling is correct or whether
  the "separable" path actually saves anything. The rebuild implements convolution with explicit
  padding modes, then proves: `PSNR(img, img) = inf`, the **size-1 box kernel is an identity**,
  every smoothing kernel **sums to 1**, the **separable Gaussian equals the full 2-D one to within
  `1e-6`**, and edge-handling modes **differ only at the borders**. Every filter also reports a PSNR
  against the input, so "sharpen" has a number attached.
- **Geometric_Transforms** — *a warp is a matrix, and interpolation is a separate decision.* Rotating
  an image is affine geometry plus a resampling rule, and the failure is always at the boundary: wrap,
  clamp or zero-fill each produce a different picture and only one of them round-trips. The rebuild
  composes translation, rotation and scaling into 3×3 matrices, implements nearest, bilinear and
  bicubic sampling by hand, and verifies **identity is exact**, a **90° lattice rotation round-trips
  exactly**, **wrap-translate equals `np.roll`**, midpoint blend is exact, **rotate-then-unrotate
  recovers 24.3 dB**, and a composed transform matches its step-by-step equivalent (**34.2 dB**, and
  visibly worse at 27.1 dB when the order is reversed).
- **Histogram_Equalizer** — *equalisation is a monotone remap, and monotonicity is the whole claim.*
  A global CDF stretch can only reorder intensities, never swap them; if two pixels had the same
  brightness they must still have the same brightness afterwards. The rebuild computes the CDF from
  scratch, applies a global mapping and a tile-based **CLAHE-style** variant with clip limiting, and
  verifies: the output spans the **full 0–255 range**, the **mapping is monotone**, a **uniform image
  is unchanged**, **spread increases**, `PSNR(img, img) = inf`, and **CLAHE limits noise amplification
  relative to the global method**.
- **Image_Compressor** — *a codec is a chain of invertible steps around exactly one lossy step.* If the
  entropy coder does not reproduce the quantised coefficients bit for bit, the codec is broken no
  matter how the reconstruction looks. The rebuild implements the DCT matrix, orthonormality-checked
  2-D DCT/IDCT, JPEG-style quantisation tables, zig-zag ordering, run-length coding, and a canonical
  **Huffman** coder — then proves the **bitstream reproduces the quantised coefficients exactly**, the
  **codes are prefix-free and complete** (Kraft sum 1), PSNR and bit rate are **monotone in quality**,
  **quality 50 lands below 3 bpp**, and the **DC coefficient holds most of the energy**.
- **Morphological_Processing** — *morphology is an algebra, not a filter list.* Opening is
  anti-extensive and idempotent, closing is extensive and idempotent, erosion is the dual of dilation
  under complement, and a 3×3 dilation followed by another is one 5×5 dilation. The rebuild implements
  square, cross, disk, diamond and rectangular structuring elements, then verifies all of those
  identities and adds measured cleanup: **all 304 salt specks removed** (**a 1×1 element removes
  nothing**, as it must), **pepper holes fall from 110 to 0**, the **3 shapes account for all 4140
  cleaned pixels** while **plain erosion would have kept only 2778**, a **21×21 square has an 80-pixel
  boundary**, and the **skeleton only deletes pixels, keeps under a tenth of the area and preserves
  all 3 parts**.

**Every claim is checkable.** Each demo prints `Cross-checks OK: ...` with the numbers it verified,
then `Demo completed successfully.`; run it twice and the bytes match, run it with `--quiet` and it
writes nothing at all.

The dependencies are `numpy` and Pillow. Nothing reads a clock, opens a socket, or writes into the
repository: filtered images and JSON go only where you point them.

---

# 🎓 Learning Objectives

- Implement convolution and padding modes by hand, including `reflect` and edge clamping
- Use operator identities (identity kernel, kernel sum, separability) as tests
- Build a separable kernel and prove it matches the full 2-D version numerically
- Compose affine transforms as 3×3 matrices and apply them in one warp
- Implement nearest, bilinear and bicubic resampling and see the quality difference in dB
- Test a transform by round-tripping it and reporting PSNR, not by looking
- Build a histogram and its CDF from scratch and read them as a mapping
- Prove a brightness mapping is monotone and pixel-count preserving
- Explain what CLAHE's clip limit does, and measure it against the global method
- Implement an orthonormal DCT matrix and verify `dct2`/`idct2` inversion
- Quantise with a JPEG-style table and scale it by a quality factor
- Zig-zag coefficients, run-length encode them, and rebuild them exactly
- Build canonical Huffman codes and verify prefix-freeness with the Kraft sum
- Separate the lossy step from the lossless step and test them independently
- Report PSNR and bit rate as a trade-off curve over quality
- Implement dilation, erosion, opening, closing and their structuring elements
- Verify the duality, anti-extensivity and idempotence laws of morphology
- Compose structuring elements and check that two 3×3 dilations equal one 5×5
- Use connected components and area statistics to count specks and holes
- Skeletonise a mask and prove it only removes pixels
- Make an image pipeline reproducible byte for byte

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Convolution_Filters | Box/Gaussian/sharpen/emboss kernels, separable paths, padding modes, PSNR per filter. | 55 | ✅
02 | Geometric_Transforms | Affine matrices, three interpolation modes, wrap/clamp/zero edges, compose vs steps. | 91 | ✅
03 | Histogram_Equalizer | Global CDF stretch and CLAHE-style tiles with clip limiting, monotonicity checks. | 51 | ✅
04 | Image_Compressor | DCT, quantisation, zig-zag, RLE, canonical Huffman, PSNR/bit-rate trade-off. | 122 | ✅
05 | Morphological_Processing | Structuring elements, morph laws, speck/hole cleanup, components, skeleton. | 188 | ✅

**Total: 507 tests.**

---

# 🧠 Concepts Covered

- Discrete convolution, kernel orientation, and border padding policies
- Separability and the `O(n)` win of two 1-D passes over one 2-D pass
- Linear-operator identities as tests: identity kernel, kernel sum, delta response
- Gaussian kernels from `sigma`, and their normalisation
- Sharpening and embossing as linear combinations that can amplify noise
- MSE and PSNR, and why `PSNR(img, img)` is infinite rather than large
- Affine transforms in homogeneous coordinates and matrix composition order
- Forward mapping vs inverse mapping in a warp
- Nearest, bilinear and bicubic interpolation and their failure modes
- Boundary handling: wrap, clamp, zero-fill, and which one round-trips
- Rotation about a centre and the translation that makes it behave
- Histograms, CDFs, and histogram equalisation as a monotone lookup
- Pixel-count conservation under a remap
- Tile-based equalisation (CLAHE) and clip limiting as noise control
- The discrete cosine transform, orthonormality, and 2-D separability
- Quantisation tables and quality scaling
- Zig-zag ordering and the run-length structure of quantised coefficients
- Canonical Huffman coding, prefix-freeness, and the Kraft inequality
- Bit rate in bits per pixel, and its monotone relationship with quality
- Energy compaction: why the DC coefficient carries most of the image
- Binary morphology: structuring elements, dilation, erosion, opening, closing
- Duality under complement, anti-extensivity, extensivity and idempotence
- Composition of structuring elements and its size law
- Connected-component labelling, area filtering, and speck/hole counts
- Boundary extraction, morphological gradient, top-hat and black-hat
- Skeletonisation as an iterative thinning that never adds pixels
- Determinism: fixed inputs, byte-identical demo re-runs

---

# 📁 Repository Structure

```text
23_Image_Processing/
│
├── Convolution_Filters/
│   ├── src/    filters.py, main.py
│   ├── tests/  test_filters.py
│   └── data/   gradient_64.png, shapes_128.png
│
├── Geometric_Transforms/
│   ├── src/    geometry.py, main.py
│   ├── tests/  test_geometry.py
│   └── data/   checker_128.png, shapes_128.png
│
├── Histogram_Equalizer/
│   ├── src/    histogram.py, main.py
│   ├── tests/  test_histogram.py
│   └── data/   lowcontrast_128.png, flat_noise_128.png
│
├── Image_Compressor/
│   ├── src/    compressor.py, main.py
│   ├── tests/  test_compressor.py
│   └── data/   photo_128.png
│
└── Morphological_Processing/
    ├── src/    morph.py, main.py
    ├── tests/  test_morph.py
    └── data/   noisy_shapes_128.png
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI, a
`tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a `.gitignore`, and a
`README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 23_Image_Processing/Image_Compressor

python src/main.py --demo                             # offline, deterministic, exit 0
python src/main.py --demo --quiet                      # prints nothing at all
python src/main.py --file data/photo_128.png --quality 50 --sweep
python src/main.py --file data/photo_128.png --quality 75 --save out/decoded.png --json out.json
python -m pytest tests -q                              # the suite
```

Every project supports `--demo` (plus `--quiet`), `--file <png>` and `--json <path>`, and adds its own
flags (`--filter`, `--size`, `--sigma`, `--edges`, `--out`, `--rotate`, `--scale`, `--translate`,
`--interp`, `--method`, `--clip`, `--tiles`, `--ascii`, `--quality`, `--sweep`, `--save`, `--threshold`,
`--shape`, `--op`, `--skeleton`, `--components`). No demo writes into the repository: PNGs and JSON go
only where you point them.

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
5. no non-ASCII byte in `src/`, `tests/` (binary sample images are exempt)

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why an operator identity is the cheapest correctness test in image processing
- Why border handling is part of the algorithm and shows up only at the edges
- Why separability is a performance claim you can verify numerically
- Why a warp needs an inverse mapping and a stated interpolation rule
- Why only one edge mode round-trips, and how to find out which
- Why PSNR in dB is a useful comparison and a poor aesthetic judgement
- Why equalisation can only reorder intensities, never create detail
- Why a monotone mapping is the defining property of a histogram stretch
- Why CLAHE's clip limit exists, and how to measure what it bought
- Why orthonormality makes the DCT invertible
- Why the lossy step must be isolated from the lossless steps in a codec
- Why prefix-freeness is what makes a Huffman bitstream decodable
- Why bit rate and quality form a curve, not a setting
- Why morphology's laws (duality, idempotence, anti-extensivity) are testable
- Why a 1×1 structuring element must change nothing, and what that proves
- Why opening removes specks that erosion would take the object with it to remove
- Why a skeleton is judged by what it preserves, not by how it looks
- How to make an image pipeline reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `load_image`, `save_image`, `ascii_thumb`, `ascii_histogram`
Convolution — `box_kernel`, `gaussian_kernel_1d`, `gaussian_kernel`, `sharpen_kernel`,
`emboss_kernel`, `get_kernel`, `pad_image`, `convolve`, `convolve_separable`, `apply_filter`
Geometry — `translation_matrix`, `rotation_matrix`, `scaling_matrix`, `compose`, `affine_warp`,
`rotate`, `scale`, `translate`, `image_center`, `_resolve`
Histogram — `histogram`, `cumulative_counts`, `histogram_stats`, `equalize_global`, `_tile_lut`,
`equalize_clahe`, `equalize`
Codec — `dct_matrix`, `dct2`, `idct2`, `quant_table`, `quantise`, `dequantise`, `zigzag_order`,
`split_blocks`, `merge_blocks`, `rle`, `unrle`, `huffman_lengths`, `canonical_codes`, `huffman_encode`,
`huffman_decode`, `is_prefix_free`, `kraft_sum`, `compress`, `decompress`
Morphology — `square_se`, `cross_se`, `disk_se`, `diamond_se`, `rect_se`, `structuring_element`,
`dilate`, `erode`, `opening`, `closing`, `boundary`, `morphological_gradient`, `top_hat`, `black_hat`,
`clean`, `label_components`, `count_specks`, `count_holes`, `skeleton`, `perimeter`, `iou`
Metrics — `mse`, `psnr`, `filter_report`, `energy_stats`, `image_stats`
Refusal — `ImgError`, `GeoError`, `HistError`, `CodecError`, `MorphError`
Testing — operator identities, separability agreement, round-trip PSNR, monotonicity and
conservation laws, prefix-freeness, bit-exact codec recovery, morphology laws, CLI paths, quiet-mode
silence

---

# 🚀 Future Improvements

- A shared convolution core, so all five projects use one padding implementation
- Colour images throughout, with per-channel and luma/chroma handling
- Sub-pixel translation estimates alongside the interpolation error
- Adaptive histogram equalisation with a contrast-limited curve shown as a plot
- Chroma subsampling and a comparison against the current 4:4:4 pipeline
- Arithmetic coding beside Huffman, with the bit-rate difference measured
- Grayscale morphology on non-binary images (min/max filters) beside the binary algebra
- A category-wide `audit` harness that prints all five evidence tables in one shape

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
