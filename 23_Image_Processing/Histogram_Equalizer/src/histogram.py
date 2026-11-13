"""Global histogram equalization and CLAHE-style local limiting - offline.

Implements 256-bin histograms, the CDF mapping for global equalization,
and a CLAHE variant (tile clipping + uniform redistribution + bilinear
interpolation between tile mappings) from scratch with NumPy. Local
images in, equalized images + before/after statistics out - no network,
no downloads, no OpenCV/scipy required.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

LOG = logging.getLogger("histogram")

METHODS = ("global", "clahe")
SHADES = " .:-=+*#%@"
MAX_DIM = 512
MIN_DIM = 8
BINS = 256


class HistError(RuntimeError):
    """Raised for missing files, bad images, and invalid parameters."""


# --------------------------------------------------------------------------- #
# Image loading / saving / ASCII helpers
# --------------------------------------------------------------------------- #
def load_image(path: str | Path) -> np.ndarray:
    """Load a PNG/JPEG as a 2D uint8 array (RGB is converted to grey)."""
    source = Path(path)
    if not source.is_file():
        raise HistError(f"file not found: {source}")
    try:
        with Image.open(source) as handle:
            array = np.asarray(handle.convert("L"), dtype=np.uint8)
    except HistError:
        raise
    except Exception as exc:
        raise HistError(f"could not read image {source.name}: {exc}") from exc
    if array.ndim != 2:
        raise HistError(f"expected a 2D grayscale image, got {array.ndim}D")
    height, width = array.shape
    if height < MIN_DIM or width < MIN_DIM:
        raise HistError(f"image too small: {height}x{width} "
                        f"(need >= {MIN_DIM}x{MIN_DIM})")
    if height > MAX_DIM or width > MAX_DIM:
        raise HistError(f"image too large: {height}x{width} "
                        f"(max {MAX_DIM}x{MAX_DIM})")
    return array


def save_image(array: np.ndarray, path: str | Path) -> Path:
    """Write a uint8 array as a PNG (creates parent directories)."""
    image = np.asarray(array)
    if image.ndim != 2:
        raise HistError(f"expected a 2D array to save, got {image.ndim}D")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    grey = np.clip(np.rint(image.astype(np.float64)), 0, 255).astype(np.uint8)
    Image.fromarray(grey).save(target)
    return target


def _as_image(image: np.ndarray) -> np.ndarray:
    """Validate a 2D uint8-valued image and return it as-is."""
    array = np.asarray(image)
    if array.ndim != 2:
        raise HistError(f"expected a 2D image, got {array.ndim}D")
    if array.size == 0:
        raise HistError("image must not be empty")
    if array.dtype != np.uint8:
        if not np.issubdtype(array.dtype, np.number):
            raise HistError("image must be numeric")
        if not np.isfinite(array).all():
            raise HistError("image must be finite")
        if array.min() < 0 or array.max() > 255:
            raise HistError("pixel values must be in 0..255")
        if not np.equal(array, np.rint(array)).all():
            raise HistError("pixel values must be whole numbers")
    return array.astype(np.uint8, copy=False)


# --------------------------------------------------------------------------- #
# Histogram, CDF, statistics
# --------------------------------------------------------------------------- #
def histogram(image: np.ndarray) -> np.ndarray:
    """256-bin grey-level histogram (counts sum to the pixel count)."""
    array = _as_image(image)
    return np.bincount(array.ravel(), minlength=BINS).astype(np.int64)


def cumulative_counts(image: np.ndarray) -> np.ndarray:
    """Non-decreasing CDF of the histogram (last value = pixel count)."""
    return np.cumsum(histogram(image))


def histogram_stats(image: np.ndarray) -> dict[str, Any]:
    """Spread statistics used by the report and demo assertions."""
    array = _as_image(image).astype(np.float64)
    counts = histogram(array)
    return {
        "mean": round(float(array.mean()), 3),
        "std": round(float(array.std()), 3),
        "min": int(array.min()),
        "max": int(array.max()),
        "range": int(array.max() - array.min()),
        "occupied": int(np.count_nonzero(counts)),
        "pixels": int(array.size),
    }


def ascii_histogram(image: np.ndarray, bins: int = 32,
                    width: int = 40) -> str:
    """Render the histogram as grouped ASCII bars (no plotting needed)."""
    counts = histogram(image)
    if bins < 2 or BINS % bins:
        raise HistError(f"bins must divide {BINS} and be >= 2, got {bins}")
    if width < 4:
        raise HistError(f"width must be >= 4, got {width}")
    grouped = counts.reshape(bins, BINS // bins).sum(axis=1)
    peak = int(grouped.max())
    lines = []
    for index, count in enumerate(grouped):
        low = index * (BINS // bins)
        high = low + BINS // bins - 1
        bar = "#" * (0 if peak == 0
                     else int(round(count / peak * width)))
        lines.append(f"{low:>3}-{high:<3} | {bar}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Global equalization
# --------------------------------------------------------------------------- #
def equalize_global(image: np.ndarray) -> np.ndarray:
    """Classic CDF equalization: LUT[x] = round(255 * (cdf[x] - cdf_min)
    / (N - cdf_min)). Uniform images are returned unchanged."""
    array = _as_image(image)
    counts = histogram(array)
    total = int(array.size)
    cumulative = np.cumsum(counts)
    cdf_min = int(cumulative[cumulative > 0][0])
    if total == cdf_min:                      # every pixel is the same grey
        return array.copy()
    lut = np.rint(255.0 * (cumulative - cdf_min) / (total - cdf_min))
    lut = np.clip(lut, 0, 255).astype(np.uint8)
    return lut[array]


# --------------------------------------------------------------------------- #
# CLAHE-style local limiting
# --------------------------------------------------------------------------- #
def _tile_lut(tile: np.ndarray, clip_limit: float) -> np.ndarray:
    """Clipped, redistributed, equalised 256-entry LUT for one tile."""
    counts = np.bincount(tile.ravel(), minlength=BINS).astype(np.int64)
    if np.count_nonzero(counts) == 1:
        # a tile with a single grey level has no contrast to stretch
        return np.arange(BINS, dtype=np.uint8)
    tile_pixels = tile.size
    threshold = max(1, int(np.ceil(clip_limit * tile_pixels / BINS)))
    clipped = np.minimum(counts, threshold)
    # spread the clipped excess evenly across the tile's occupied levels
    # (empty levels below the range would otherwise steal the stretch)
    occupied = counts > 0
    active = int(np.count_nonzero(occupied))
    excess = int(counts.sum() - clipped.sum())
    share, remainder = divmod(excess, active)
    clipped[occupied] += share
    if remainder:
        clipped[np.flatnonzero(occupied)[:remainder]] += 1
    cumulative = np.cumsum(clipped).astype(np.float64)
    total = float(cumulative[-1])
    cdf_min = float(cumulative[cumulative > 0][0])
    lut = np.rint(255.0 * (cumulative - cdf_min) / (total - cdf_min))
    return np.clip(lut, 0, 255).astype(np.uint8)


def equalize_clahe(image: np.ndarray, clip_limit: float = 2.0,
                   tiles: int = 8) -> np.ndarray:
    """CLIP-limited Adaptive Histogram Equalization from scratch.

    The image is split into `tiles x tiles` blocks; each block's
    histogram is clipped at `clip_limit * (pixels/256)`, the excess is
    spread uniformly, and the per-block LUTs are combined with bilinear
    interpolation at each pixel's position between tile centres.
    """
    array = _as_image(image)
    if not np.isfinite(clip_limit) or clip_limit <= 0:
        raise HistError(f"clip_limit must be > 0, got {clip_limit}")
    if tiles < 2:
        raise HistError(f"tiles must be >= 2, got {tiles}")
    height, width = array.shape
    if tiles > min(height, width):
        raise HistError(f"tiles ({tiles}) larger than the image "
                        f"({height}x{width})")
    if height % tiles or width % tiles:
        raise HistError(f"image {height}x{width} must be divisible by "
                        f"tiles={tiles}")

    tile_h, tile_w = height // tiles, width // tiles
    lut = np.empty((tiles, tiles, BINS), dtype=np.uint8)
    for row in range(tiles):
        for col in range(tiles):
            block = array[row * tile_h:(row + 1) * tile_h,
                          col * tile_w:(col + 1) * tile_w]
            lut[row, col] = _tile_lut(block, clip_limit)

    # bilinear blend of the four nearest tile LUTs
    rows = np.arange(height) / tile_h - 0.5
    cols = np.arange(width) / tile_w - 0.5
    r0 = np.floor(rows).astype(int)
    c0 = np.floor(cols).astype(int)
    fr = (rows - r0)[:, None]
    fc = (cols - c0)[None, :]
    r0c, r1c = np.clip(r0, 0, tiles - 1), np.clip(r0 + 1, 0, tiles - 1)
    c0c, c1c = np.clip(c0, 0, tiles - 1), np.clip(c0 + 1, 0, tiles - 1)
    top = (lut[r0c[:, None], c0c[None, :], array] * (1 - fc)
           + lut[r0c[:, None], c1c[None, :], array] * fc)
    bottom = (lut[r1c[:, None], c0c[None, :], array] * (1 - fc)
              + lut[r1c[:, None], c1c[None, :], array] * fc)
    blended = top * (1 - fr) + bottom * fr
    return np.clip(np.rint(blended), 0, 255).astype(np.uint8)

def equalize(image: np.ndarray, method: str = "global",
             clip_limit: float = 2.0, tiles: int = 8) -> np.ndarray:
    """Dispatch: method 'global' or 'clahe'."""
    if method == "global":
        return equalize_global(image)
    if method == "clahe":
        return equalize_clahe(image, clip_limit=clip_limit, tiles=tiles)
    raise HistError(f"unknown method {method!r} "
                    f"(choose from {', '.join(METHODS)})")


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def mse(first: np.ndarray, second: np.ndarray) -> float:
    """Mean squared error between two images."""
    a = np.asarray(first, dtype=np.float64)
    b = np.asarray(second, dtype=np.float64)
    if a.shape != b.shape:
        raise HistError(f"shape mismatch: {a.shape} vs {b.shape}")
    return float(np.mean((a - b) ** 2))


def psnr(first: np.ndarray, second: np.ndarray,
         peak: float = 255.0) -> float:
    """Peak signal-to-noise ratio in dB; identical images give inf."""
    error = mse(first, second)
    if error == 0.0:
        return float("inf")
    return 10.0 * np.log10((peak * peak) / error)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def render_report(original: np.ndarray, processed: np.ndarray,
                  method: str, params: dict[str, Any]) -> str:
    """Before/after comparison block used by the CLI and the demo."""
    before = histogram_stats(original)
    after = histogram_stats(processed)
    lines = [
        "HISTOGRAM EQUALIZER",
        "=" * 68,
        f"Method       : {method}"
        + (f" (clip {params.get('clip_limit')}, "
           f"tiles {params.get('tiles')})" if method == "clahe" else ""),
        f"Image        : {before['pixels']} pixels, "
        f"range {before['min']}..{before['max']}",
        "",
        f"{'stat':<10} {'before':>12} {'after':>12}",
        f"{'mean':<10} {before['mean']:>12.2f} {after['mean']:>12.2f}",
        f"{'std':<10} {before['std']:>12.2f} {after['std']:>12.2f}",
        f"{'range':<10} {before['range']:>12d} {after['range']:>12d}",
        f"{'bins used':<10} {before['occupied']:>12d} "
        f"{after['occupied']:>12d}",
        "",
        f"PSNR vs original: {psnr(original, processed):.2f} dB "
        f"(higher = closer to the input)",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Bundled demo
# --------------------------------------------------------------------------- #
LOW_IMG = Path(__file__).resolve().parent.parent / "data" / "lowcontrast_128.png"
NOISY_IMG = Path(__file__).resolve().parent.parent / "data" / "flat_noise_128.png"


def run_demo(image_path: Path | None = None) -> int:
    """Equalize the bundled samples - fully offline, self-checking."""
    print("=" * 68)
    print(" HISTOGRAM EQUALIZER - offline demo")
    print(" Global CDF + CLAHE-style limiting from scratch; no OpenCV.")
    print("=" * 68)

    source = image_path or LOW_IMG
    if not source.is_file():
        raise HistError(f"bundled sample not found: {source}")
    image = load_image(source)
    print(f"\nLoaded {source.name}: {image.shape[0]}x{image.shape[1]} grey, "
          f"range {image.min()}..{image.max()}")

    global_out = equalize_global(image)
    clahe_out = equalize_clahe(image, clip_limit=2.0, tiles=8)
    print()
    print(render_report(image, global_out, "global", {}))
    print()
    clahe_params = {"clip_limit": 2.0, "tiles": 8}
    report = render_report(image, clahe_out, "clahe", clahe_params)
    print("\n".join(report.splitlines()[1:]))

    # --- noise-limiting comparison on the flat noisy sample ---------------- #
    noisy = load_image(NOISY_IMG)
    noisy_global = equalize_global(noisy)
    noisy_clahe = equalize_clahe(noisy, clip_limit=2.0, tiles=8)
    print(f"\nFlat noisy sample {NOISY_IMG.name} "
          f"(orig std {noisy.std():.2f}):")
    print(f"  global amplifies noise -> std {noisy_global.std():.2f}")
    print(f"  clahe limits it        -> std {noisy_clahe.std():.2f}")

    print("\nASCII histogram before (32 bins):")
    print(ascii_histogram(image))
    print("ASCII histogram after global equalization:")
    print(ascii_histogram(global_out))

    # --- cross-checks the demo asserts ------------------------------------ #
    # PSNR of an image against itself is inf; against a different one finite
    assert psnr(image, image) == float("inf"), "PSNR(img, img) must be inf"
    assert mse(image, image) == 0.0
    assert 0.0 < psnr(image, global_out) < 100.0

    # histograms conserve the pixel count exactly
    assert int(histogram(image).sum()) == image.size
    assert int(histogram(global_out).sum()) == image.size

    # global equalization stretches a low-contrast image to the full range
    low, high = int(global_out.min()), int(global_out.max())
    assert (low, high) == (0, 255), f"expected full range, got {low}..{high}"
    before, after = histogram_stats(image), histogram_stats(global_out)
    assert after["std"] > before["std"], "equalization must raise the spread"
    # a monotone LUT can only merge bins, never split them
    assert after["occupied"] >= before["occupied"], "bins were lost"
    # means stay in the same neighbourhood (equalization is mass-preserving
    # in the CDF sense, not exactly in the mean)
    assert abs(after["mean"] - before["mean"]) < 40.0, "mean drifted too far"

    # the mapping is monotone: an ascending ramp stays ascending
    ramp = np.arange(128, dtype=np.uint8).reshape(1, 128)
    mapped = equalize_global(ramp).ravel()
    assert np.all(np.diff(mapped.astype(int)) >= 0), "mapping not monotone"

    # a uniform image has no contrast to equalise -> unchanged
    flat = np.full((32, 32), 140, dtype=np.uint8)
    assert np.array_equal(equalize_global(flat), flat), "uniform changed"

    # CLAHE also spreads the low-contrast image, but stays below the
    # unconstrained global result on noisy input (the whole point of
    # the clip limit)
    clahe_stats = histogram_stats(clahe_out)
    assert clahe_stats["std"] > before["std"], "CLAHE must also spread"
    # bilinear blending between tile LUTs fills intermediate grey levels
    assert clahe_stats["occupied"] > before["occupied"], \
        "CLAHE should fill intermediate levels"
    assert clahe_stats["range"] > before["range"], "CLAHE should widen range"
    assert float(noisy_clahe.std()) < float(noisy_global.std()), \
        "CLAHE must limit noise amplification vs global"

    # deterministic: identical input -> identical output
    assert np.array_equal(equalize_global(image), global_out), \
        "global not deterministic"
    assert np.array_equal(
        equalize_clahe(image, clip_limit=2.0, tiles=8), clahe_out), \
        "clahe not deterministic"

    print("\nCross-checks OK: PSNR(img,img)=inf, full 0..255 stretch, "
          "spread increased, monotone mapping, uniform unchanged, "
          "CLAHE limits noise vs global, deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
