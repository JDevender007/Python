"""Convolution filters from scratch - offline.

Implements 2D convolution, classic kernels (box, gaussian, sharpen,
emboss), separable-kernel fast paths, and four edge-padding modes
using only NumPy. Local images in, filtered images + stats out -
no network, no downloads, no OpenCV/scipy required.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

LOG = logging.getLogger("filters")

EDGE_MODES = ("constant", "reflect", "replicate", "wrap")
FILTER_NAMES = ("box", "gaussian", "sharpen", "emboss")
SHADES = " .:-=+*#%@"
MAX_DIM = 512
MIN_DIM = 8


class ImgError(RuntimeError):
    """Raised for missing files, bad images, and invalid filter inputs."""


# --------------------------------------------------------------------------- #
# Image loading / saving / ASCII preview
# --------------------------------------------------------------------------- #
def load_image(path: str | Path) -> np.ndarray:
    """Load a PNG/JPEG as a 2D uint8 array (RGB is converted to grey)."""
    source = Path(path)
    if not source.is_file():
        raise ImgError(f"file not found: {source}")
    try:
        with Image.open(source) as handle:
            array = np.asarray(handle.convert("L"), dtype=np.uint8)
    except ImgError:
        raise
    except Exception as exc:
        raise ImgError(f"could not read image {source.name}: {exc}") from exc
    if array.ndim != 2:
        raise ImgError(f"expected a 2D grayscale image, got {array.ndim}D")
    height, width = array.shape
    if height < MIN_DIM or width < MIN_DIM:
        raise ImgError(f"image too small: {height}x{width} "
                       f"(need >= {MIN_DIM}x{MIN_DIM})")
    if height > MAX_DIM or width > MAX_DIM:
        raise ImgError(f"image too large: {height}x{width} "
                       f"(max {MAX_DIM}x{MAX_DIM})")
    return array


def save_image(array: np.ndarray, path: str | Path) -> Path:
    """Write a uint8 array as a PNG (creates parent directories)."""
    image = np.asarray(array)
    if image.ndim != 2:
        raise ImgError(f"expected a 2D array to save, got {image.ndim}D")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    grey = np.clip(np.rint(image.astype(np.float64)), 0, 255).astype(np.uint8)
    Image.fromarray(grey).save(target)
    return target


def ascii_thumb(array: np.ndarray, cols: int = 48) -> str:
    """Down-sample an image to ASCII shade art (2:1 character aspect)."""
    image = np.asarray(array)
    if image.ndim != 2 or image.size == 0:
        raise ImgError("ascii_thumb needs a non-empty 2D array")
    if cols < 4:
        raise ImgError(f"cols must be >= 4, got {cols}")
    height, width = image.shape
    scale = max(width / cols, height / (cols // 2), 1.0)
    out_w = max(int(round(width / scale)), 1)
    out_h = max(int(round(height / scale)), 1)
    ys = np.clip(np.round(np.linspace(0, height - 1, out_h)).astype(int),
                 0, height - 1)
    xs = np.clip(np.round(np.linspace(0, width - 1, out_w)).astype(int),
                 0, width - 1)
    small = image[ys][:, xs].astype(np.float64)
    lo, hi = float(small.min()), float(small.max())
    ramp = 0 if hi <= lo else (small - lo) / (hi - lo)
    idx = np.clip(np.round(ramp * (len(SHADES) - 1)).astype(int),
                  0, len(SHADES) - 1)
    return "\n".join("".join(SHADES[v] for v in row) for row in idx)


# --------------------------------------------------------------------------- #
# Kernels
# --------------------------------------------------------------------------- #
def box_kernel(size: int = 3) -> np.ndarray:
    """Uniform averaging kernel (sums to exactly 1)."""
    if size < 1:
        raise ImgError(f"box size must be >= 1, got {size}")
    if size > 2 * MAX_DIM:
        raise ImgError(f"box size must be <= {2 * MAX_DIM}, got {size}")
    return np.full((size, size), 1.0 / (size * size), dtype=np.float64)


def gaussian_kernel_1d(sigma: float) -> np.ndarray:
    """Normalised 1D gaussian, radius = ceil(3 * sigma)."""
    if not np.isfinite(sigma) or sigma <= 0:
        raise ImgError(f"sigma must be > 0, got {sigma}")
    radius = max(int(np.ceil(3.0 * sigma)), 1)
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(x * x) / (2.0 * sigma * sigma))
    return kernel / kernel.sum()


def gaussian_kernel(size: int | None = None, sigma: float = 1.0) -> np.ndarray:
    """Full 2D gaussian = outer product of the 1D kernel (sums to 1)."""
    kernel_1d = gaussian_kernel_1d(sigma)
    if size is None:
        return np.outer(kernel_1d, kernel_1d)
    if size < 1 or size % 2 == 0:
        raise ImgError(f"gaussian size must be a positive odd number, "
                       f"got {size}")
    if size < kernel_1d.size:
        raise ImgError(f"gaussian size {size} too small for sigma {sigma} "
                       f"(need >= {kernel_1d.size})")
    radius = size // 2
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel_2d = np.exp(-(x[:, None] ** 2 + x[None, :] ** 2)
                       / (2.0 * sigma * sigma))
    return kernel_2d / kernel_2d.sum()


def sharpen_kernel() -> np.ndarray:
    """Classic 3x3 unsharp kernel (sums to 1, centre boosted)."""
    return np.array([[0.0, -1.0, 0.0],
                     [-1.0, 5.0, -1.0],
                     [0.0, -1.0, 0.0]], dtype=np.float64)


def emboss_kernel() -> np.ndarray:
    """Directional emboss relief kernel (sums to 1)."""
    return np.array([[-2.0, -1.0, 0.0],
                     [-1.0, 1.0, 1.0],
                     [0.0, 1.0, 2.0]], dtype=np.float64)


def get_kernel(name: str, **params: Any) -> np.ndarray:
    """Build a named kernel: box / gaussian / sharpen / emboss."""
    if name == "box":
        return box_kernel(int(params.get("size", 3)))
    if name == "gaussian":
        return gaussian_kernel(size=params.get("size"),
                               sigma=float(params.get("sigma", 1.0)))
    if name == "sharpen":
        return sharpen_kernel()
    if name == "emboss":
        return emboss_kernel()
    raise ImgError(f"unknown filter {name!r} "
                   f"(choose from {', '.join(FILTER_NAMES)})")


# --------------------------------------------------------------------------- #
# Padding and convolution
# --------------------------------------------------------------------------- #
def _validate_mode(mode: str) -> str:
    if mode not in EDGE_MODES:
        raise ImgError(f"unknown edge mode {mode!r} "
                       f"(choose from {', '.join(EDGE_MODES)})")
    return mode


_PAD_MODES = {"constant": "constant", "reflect": "reflect",
              "replicate": "edge", "wrap": "wrap"}


def _pad(image: np.ndarray, pad: tuple[tuple[int, int], tuple[int, int]],
         mode: str) -> np.ndarray:
    """np.pad wrapper with validated mode (zero-fill for 'constant')."""
    _validate_mode(mode)
    if mode == "constant":
        return np.pad(image, pad, mode="constant", constant_values=0.0)
    return np.pad(image, pad, mode=_PAD_MODES[mode])


def pad_image(image: np.ndarray, radius: int, mode: str = "reflect") -> np.ndarray:
    """Symmetrically pad a 2D image by `radius` on every side."""
    image = np.asarray(image, dtype=np.float64)
    if image.ndim != 2:
        raise ImgError(f"expected a 2D array, got {image.ndim}D")
    if radius < 0:
        raise ImgError(f"radius must be >= 0, got {radius}")
    height, width = image.shape
    if radius >= height or radius >= width:
        raise ImgError(f"pad radius {radius} must be smaller than the image "
                       f"({height}x{width})")
    return _pad(image, ((radius, radius), (radius, radius)), mode)


def convolve(image: np.ndarray, kernel: np.ndarray,
             mode: str = "reflect") -> np.ndarray:
    """Full 2D convolution (kernel flipped) with the given edge handling.

    Returns a float64 array of the same shape as `image`.
    """
    image = np.asarray(image, dtype=np.float64)
    if image.ndim != 2:
        raise ImgError(f"expected a 2D image, got {image.ndim}D")
    kernel = np.asarray(kernel, dtype=np.float64)
    if kernel.ndim != 2 or kernel.size == 0:
        raise ImgError("kernel must be a non-empty 2D array")
    if not np.isfinite(kernel).all():
        raise ImgError("kernel must be finite")
    _validate_mode(mode)

    height, width = image.shape
    kernel_h, kernel_w = kernel.shape
    top, left = kernel_h // 2, kernel_w // 2
    bottom, right = kernel_h - 1 - top, kernel_w - 1 - left
    if top + bottom >= height or left + right >= width:
        raise ImgError(f"kernel {kernel_h}x{kernel_w} too large for image "
                       f"{height}x{width}")

    padded = _pad(image, ((top, bottom), (left, right)), mode)
    windows = np.lib.stride_tricks.sliding_window_view(
        padded, (kernel_h, kernel_w))                      # (h, w, kh, kw)
    flipped = kernel[::-1, ::-1]                            # true convolution
    return np.einsum("ijkl,kl->ij", windows, flipped)


def convolve_separable(image: np.ndarray, kernel_1d: np.ndarray,
                       mode: str = "reflect") -> np.ndarray:
    """Two 1D passes for a separable kernel - equal to the full 2D result."""
    image = np.asarray(image, dtype=np.float64)
    if image.ndim != 2:
        raise ImgError(f"expected a 2D image, got {image.ndim}D")
    kernel_1d = np.asarray(kernel_1d, dtype=np.float64)
    if kernel_1d.ndim != 1 or kernel_1d.size == 0:
        raise ImgError("kernel_1d must be a non-empty 1D array")
    if not np.isfinite(kernel_1d).all():
        raise ImgError("kernel_1d must be finite")
    if kernel_1d.size % 2 == 0:
        raise ImgError(f"kernel_1d must have odd length, "
                       f"got {kernel_1d.size}")
    _validate_mode(mode)

    radius = kernel_1d.size // 2
    height, width = image.shape
    if radius >= height or radius >= width:
        raise ImgError(f"kernel radius {radius} must be smaller than the "
                       f"image ({height}x{width})")

    # horizontal pass (flipped for convolution)
    padded = _pad(image, ((0, 0), (radius, radius)), mode)
    windows = np.lib.stride_tricks.sliding_window_view(
        padded, kernel_1d.size, axis=1)                   # (h, w, kw)
    rows = np.einsum("ijk,k->ij", windows, kernel_1d[::-1])

    # vertical pass
    padded = _pad(rows, ((radius, radius), (0, 0)), mode)
    windows = np.lib.stride_tricks.sliding_window_view(
        padded, kernel_1d.size, axis=0)                   # (h, w, kh)
    return np.einsum("ijk,k->ij", windows, kernel_1d[::-1])


# --------------------------------------------------------------------------- #
# Applying filters
# --------------------------------------------------------------------------- #
def _to_uint8(array: np.ndarray) -> np.ndarray:
    """Clip to 0..255 and round back to uint8 (deterministic)."""
    return np.clip(np.rint(np.asarray(array, dtype=np.float64)),
                   0, 255).astype(np.uint8)


def apply_filter(image: np.ndarray, name: str, mode: str = "reflect",
                 **params: Any) -> np.ndarray:
    """Apply a named kernel and return a uint8 image of the same shape."""
    if name == "gaussian":
        sigma = float(params.get("sigma", 1.0))
        size = params.get("size")
        if size is None:
            kernel_1d = gaussian_kernel_1d(sigma)
            filtered = convolve_separable(image, kernel_1d, mode)
        else:
            filtered = convolve(image, gaussian_kernel(size, sigma), mode)
    elif name == "box":
        filtered = convolve(image, box_kernel(int(params.get("size", 3))),
                            mode)
    else:
        filtered = convolve(image, get_kernel(name, **params), mode)
    return _to_uint8(filtered)


def filter_report(image: np.ndarray, filtered: np.ndarray) -> dict[str, Any]:
    """Summary statistics of a filtered image vs its original."""
    if image.shape != filtered.shape:
        raise ImgError("image and filtered must have the same shape")
    difference = image.astype(np.float64) - filtered.astype(np.float64)
    mse = float(np.mean(difference * difference))
    return {
        "mean": round(float(filtered.mean()), 3),
        "std": round(float(filtered.std()), 3),
        "min": int(filtered.min()),
        "max": int(filtered.max()),
        "mse": round(mse, 4),
        "psnr_db": round(psnr(image, filtered), 3),
    }


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def mse(first: np.ndarray, second: np.ndarray) -> float:
    """Mean squared error between two images."""
    a = np.asarray(first, dtype=np.float64)
    b = np.asarray(second, dtype=np.float64)
    if a.shape != b.shape:
        raise ImgError(f"shape mismatch: {a.shape} vs {b.shape}")
    return float(np.mean((a - b) ** 2))


def psnr(first: np.ndarray, second: np.ndarray,
         peak: float = 255.0) -> float:
    """Peak signal-to-noise ratio in dB; identical images give inf."""
    error = mse(first, second)
    if error == 0.0:
        return float("inf")
    return 10.0 * np.log10((peak * peak) / error)


# --------------------------------------------------------------------------- #
# Bundled demo
# --------------------------------------------------------------------------- #
DEMO_IMG = Path(__file__).resolve().parent.parent / "data" / "shapes_128.png"
RAMP_IMG = Path(__file__).resolve().parent.parent / "data" / "gradient_64.png"


def run_demo(image_path: Path | None = None) -> int:
    """Apply every bundled kernel, print stats, assert cross-checks."""
    print("=" * 68)
    print(" CONVOLUTION FILTERS - offline demo")
    print(" Box/gaussian/sharpen/emboss from scratch; no OpenCV/scipy.")
    print("=" * 68)

    source = image_path or DEMO_IMG
    if not source.is_file():
        raise ImgError(f"bundled sample not found: {source}")
    image = load_image(source)
    print(f"\nLoaded {source.name}: {image.shape[0]}x{image.shape[1]} "
          f"grey, range {image.min()}..{image.max()}")

    # --- apply the four classic kernels ----------------------------------- #
    results: dict[str, np.ndarray] = {}
    print(f"\n{'filter':<10} {'mode':<10} {'mean':>8} {'std':>8} "
          f"{'min':>5} {'max':>5} {'PSNR dB':>9}")
    print("-" * 68)
    for name in FILTER_NAMES:
        params = {"sigma": 1.5} if name == "gaussian" else {}
        filtered = apply_filter(image, name, mode="reflect", **params)
        results[name] = filtered
        stats = filter_report(image, filtered)
        print(f"{name:<10} {'reflect':<10} {stats['mean']:>8.1f} "
              f"{stats['std']:>8.1f} {stats['min']:>5d} {stats['max']:>5d} "
              f"{stats['psnr_db']:>9.2f}")

    # --- edge-mode comparison on the ramp image --------------------------- #
    ramp = load_image(RAMP_IMG)
    print("\nEdge modes on gradient_64 (gaussian sigma 1.0, border row):")
    border_by_mode = {}
    for mode in EDGE_MODES:
        blurred = apply_filter(ramp, "gaussian", mode=mode, sigma=1.0)
        border_by_mode[mode] = blurred[0]
        print(f"  {mode:<10} first values "
              f"{[int(v) for v in blurred[0][:6]]}")

    print("\nASCII preview (emboss):")
    for line in ascii_thumb(results["emboss"]).splitlines():
        print(f"  |{line}|")

    # --- cross-checks the demo asserts ------------------------------------ #
    # PSNR of an image against itself is inf
    assert psnr(image, image) == float("inf"), "PSNR(img, img) must be inf"
    assert mse(image, image) == 0.0

    # a size-1 box filter is the identity
    identity = apply_filter(image, "box", size=1)
    assert np.array_equal(identity, image), "size-1 box must be identity"

    # kernels sum to 1 -> a constant image is reproduced exactly
    constant = np.full((32, 32), 77, dtype=np.uint8)
    for name in FILTER_NAMES:
        out = apply_filter(constant, name, mode="reflect", sigma=1.0)
        assert np.abs(out.astype(int) - 77).max() <= 1, \
            f"{name} changed a constant image"
    assert np.allclose(box_kernel(5).sum(), 1.0)
    assert np.allclose(gaussian_kernel_1d(1.5).sum(), 1.0, atol=1e-12)
    assert np.allclose(sharpen_kernel().sum(), 1.0)
    assert np.allclose(emboss_kernel().sum(), 1.0)

    # separable gaussian == full 2D gaussian (float64, before rounding)
    sigma = 1.5
    full = convolve(image.astype(float), gaussian_kernel(sigma=sigma))
    sep = convolve_separable(image.astype(float), gaussian_kernel_1d(sigma))
    assert np.abs(full - sep).max() < 1e-6, "separable path diverged"

    # rounding stays in range and outputs are uint8, same shape
    for name, out in results.items():
        assert out.dtype == np.uint8 and out.shape == image.shape, name
        assert 0 <= out.min() and out.max() <= 255, name

    # sharpening raises contrast on an image with strong edges
    assert results["sharpen"].std() > image.std(), "sharpen should raise std"

    # edge modes genuinely differ at the border but agree in the interior
    constant_border = apply_filter(ramp, "box", size=3, mode="constant")[0]
    reflect_border = apply_filter(ramp, "box", size=3, mode="reflect")[0]
    assert not np.array_equal(constant_border, reflect_border), \
        "constant vs reflect borders should differ"
    inner_c = apply_filter(ramp, "box", size=3, mode="constant")[2:-2, 2:-2]
    inner_r = apply_filter(ramp, "box", size=3, mode="reflect")[2:-2, 2:-2]
    assert np.array_equal(inner_c, inner_r), \
        "edge mode must not affect the interior"
    # wrap pulls the far end of the ramp into the border: the 3x3 window
    # at (0,0) sees (255, 0, 4) in every row -> 86.33 -> rounds to 86
    wrap_first = int(apply_filter(ramp, "box", size=3, mode="wrap")[0, 0])
    assert wrap_first == 86, f"wrap border expected 86, got {wrap_first}"

    # deterministic re-run produces byte-identical output
    again = apply_filter(image, "gaussian", mode="reflect", sigma=1.5)
    assert np.array_equal(again, results["gaussian"]), "not deterministic"

    # blurring a pure ramp must reduce its contrast (std)
    blurred_ramp = apply_filter(ramp, "gaussian", sigma=1.0)
    assert blurred_ramp.std() < ramp.std(), "gaussian should smooth a ramp"

    print("\nCross-checks OK: PSNR(img,img)=inf, box size 1 identity, "
          "kernels sum to 1, separable == full gaussian (<1e-6), "
          "edge modes differ only at borders, deterministic re-run")
    print("Demo completed successfully.")
    return 0
