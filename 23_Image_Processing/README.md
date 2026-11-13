<div align="center">

# 🖼 Image Processing Projects

### Five offline image-processing projects written from scratch: convolution filters with separable fast paths, histogram equalisation and CLAHE, inverse-mapped affine warps, a JPEG-style DCT codec, and binary morphology with component labelling and thinning.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Image processing is a small number of ideas applied with great care: **filter a neighbourhood, remap the intensities, move the pixels, transform the coefficients, and reason about sets of pixels.** Every step is easy to state and easy to get subtly wrong — an off-by-one in the kernel centre, banker's rounding in a quantiser, a `wrap` mode that does not actually wrap, or an erosion that quietly behaves like its bounding box.

This category implements each of those ideas from first principles, then proves the claims numerically:

- **Convolution_Filters** implements 2-D convolution with four edge-padding modes, classic kernels (box, gaussian, sharpen, emboss) and a separable two-pass fast path that must agree with the full 2-D result.
- **Histogram_Equalizer** builds the CDF-based global equaliser and a CLAHE-style local version with a clip limit, then measures spread, monotonicity and PSNR against the original.
- **Geometric_Transforms** warps images by **inverse** mapping with bilinear or nearest sampling, four out-of-bounds modes, and composition order verified on a smooth image.
- **Image_Compressor** is the classic transform codec: 8×8 DCT, quality-scaled quantisation, zig-zag scan, run-length coding and a canonical Huffman bitstream.
- **Morphological_Processing** covers binary morphology, connected components and Zhang-Suen thinning, with the standard algebraic laws asserted rather than assumed.

Every project runs on bundled data, finishes its demo in a couple of seconds, and **asserts its own claims** — a 90° rotation matching `np.rot90` bit-for-bit, a decode reproducing the quantised coefficients exactly, or opening removing every salt speck while plain erosion would have kept 1362 fewer pixels.

---

# 🎯 Learning Objectives

- Implement 2-D convolution and validate a separable fast path against it
- Handle boundaries explicitly with constant, reflect, replicate and wrap padding
- Design convolution kernels from their mathematical definition (gaussian, Laplacian)
- Equalise a histogram through its CDF and measure the resulting spread
- Add a clip limit and a tile grid for contrast-limited local equalisation
- Warp images by inverse mapping instead of forward scattering
- Interpolate with bilinear weights and prove the exact half-pixel blend
- Compose affine matrices in the right order and prove the order matters
- Implement an orthonormal DCT-II and its exact inverse
- Quantise with a perceptual table and explain why rounding mode matters
- Build a canonical Huffman code and verify prefix-freeness and the Kraft sum
- Implement binary dilation and erosion as neighbourhood reductions
- Recognise the algebraic laws of morphology (duality, idempotence, monotonicity)
- Label connected components with 4- and 8-connectivity
- Thin a binary blob with Zhang-Suen while preserving connectivity
- Measure quality with MSE, PSNR, bits per pixel and intersection-over-union

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Convolution_Filters | Box/gaussian/sharpen/emboss kernels, separable fast path, four edge modes, ASCII preview. | ✅
02 | Histogram_Equalizer | Global CDF equalisation plus a CLAHE-style clipped local version, spread statistics, ASCII histograms. | ✅
03 | Geometric_Transforms | Inverse-mapped rotation/scale/translation, bilinear and nearest sampling, four boundary modes. | ✅
04 | Image_Compressor | 8x8 DCT + quantisation + zig-zag + RLE + canonical Huffman, rate-distortion sweep over six qualities. | ✅
05 | Morphological_Processing | Dilate/erode/open/close/gradient/boundary/top-hat, BFS component labelling, Zhang-Suen thinning. | ✅

---

# 💡 Concepts Covered

- 2-D convolution vs correlation, and kernel flipping
- Separable kernels and the two-pass optimisation
- Edge-padding policies and their effect on the border
- Gaussian kernels from the exponential, and their normalisation
- Histogram, CDF and the monotone mapping that equalises it
- Contrast limiting and tile-based (CLAHE-style) local equalisation
- Inverse mapping vs forward mapping in image warps
- Bilinear interpolation as a four-tap weighted sum
- Homogeneous affine matrices and composition order
- Orthonormal DCT-II and energy conservation
- Quality-scaled quantisation tables and round-half-away-from-zero
- Zig-zag scanning and run-length coding with end-of-block markers
- Huffman code construction, canonical assignment, and the Kraft inequality
- Binary morphology: duality, anti-extensiveness, extensiveness, idempotence
- Minkowski sums and the composition of dilations
- Connected-component labelling with BFS, 4- vs 8-connectivity
- Zhang-Suen thinning and connectivity preservation
- Quality metrics: MSE, PSNR, bits per pixel, IoU

---

# 📁 Repository Structure

```text
23_Image_Processing/
│
├── Convolution_Filters/
├── Histogram_Equalizer/
├── Geometric_Transforms/
├── Image_Compressor/
├── Morphological_Processing/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library module
├── tests/            # pytest test suite
├── data/             # bundled deterministic PNGs
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- NumPy 2.5.2 (convolution, DCT via `einsum`, mask algebra)
- Pillow 12.3.0 (PNG decode/encode only)
- Standard library (`math`, `json`, `heapq`, `logging`, `argparse`, `pathlib`)
- pytest

No OpenCV, no SciPy, no scikit-image, no plotting library.

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Convolution Filters | ✅ |
| Histogram Equalizer | ✅ |
| Geometric Transforms | ✅ |
| Image Compressor | ✅ |
| Morphological Processing | ✅ |

**Completed:** **5 / 5 Projects** · 498 passing tests

---

# ▶️ Quick Start

```bash
cd 23_Image_Processing/Convolution_Filters

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

Each project follows the same shape: `python src/main.py --demo` for a self-checking offline run, `python -m pytest tests/ -q` for the suite.

---

# 📚 Skills Developed

- Implementing image operators from their mathematical definitions rather than calling a library
- Choosing the right fast path (separable kernels, `sliding_window_view`) and proving it equivalent
- Thinking carefully about border conventions, rounding modes and off-by-one centring
- Designing cross-checks that can actually fail: exact identities, negative controls, and bounded statistical claims
- Separating lossy from lossless stages in a codec and testing the boundary between them
- Measuring image quality honestly with PSNR, bpp and IoU instead of "looks fine"
- Writing 42-188 pytest cases per project, including every error path and CLI flag

---

# 🚀 Key Learning Outcomes

- Filter an image with arbitrary kernels and reason about what the edges should do
- Equalise a histogram globally and locally, and explain the clip limit
- Warp an image with any affine transform and know why inverse mapping is used
- Compress an image with a real transform codec and read its rate-distortion curve
- Clean, label and thin a binary mask, and check the morphology laws that make it valid

---

# 🔮 Future Enhancements

- Colour images with per-channel processing and a luminance/chroma split
- Non-local means and bilateral filtering
- GPU-accelerated convolution with a NumPy-free backend
- An arithmetic coder to replace the static Huffman stage
- Grayscale morphology on non-flat structuring elements
- Watershed segmentation on top of the distance transform

---

# 🤝 Contributions

Contributions, issues and feature requests are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this category useful, consider giving this repository a star.

</div>
