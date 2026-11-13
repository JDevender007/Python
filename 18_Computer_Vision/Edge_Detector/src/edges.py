"""Edge detection from scratch - Sobel, Prewitt and Laplacian in pure NumPy,
with OpenCV's Canny as an offline cross-check.

Loads a local image (PNG/JPG), runs a hand-written 3x3 convolution
(reflect-101 border handling), thresholds the gradient magnitude, and
reports edge statistics plus a downsampled ASCII preview of the edge map.
Local files only - no network, no downloads, no model artifacts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

LOG = logging.getLogger("edges")

METHODS = ("sobel", "prewitt", "laplacian", "canny")
ALL_METHODS = METHODS + ("all",)
SHADES = " .:-=+*#%@"
MIN_SIZE = 8
DEFAULT_THRESHOLD = 40.0
DEFAULT_LOW = 50.0
DEFAULT_HIGH = 150.0
ASCII_WIDTH = 64

# Hand-written 3x3 kernels -------------------------------------------------- #
SOBEL_X = np.array([[-1.0, 0.0, 1.0],
                    [-2.0, 0.0, 2.0],
                    [-1.0, 0.0, 1.0]])
SOBEL_Y = SOBEL_X.T.copy()
PREWITT_X = np.array([[-1.0, 0.0, 1.0],
                      [-1.0, 0.0, 1.0],
                      [-1.0, 0.0, 1.0]])
PREWITT_Y = PREWITT_X.T.copy()
LAPLACIAN = np.array([[0.0, 1.0, 0.0],
                      [1.0, -4.0, 1.0],
                      [0.0, 1.0, 0.0]])

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class EdgeError(RuntimeError):
    """Raised for missing files, undecodable images, and bad parameters."""


# --------------------------------------------------------------------------- #
# Image loading and validation
# --------------------------------------------------------------------------- #
def load_image(path: str | Path) -> np.ndarray:
    """Load an image as float64 grayscale (values 0..255)."""
    source = Path(path)
    if not source.is_file():
        raise EdgeError(f"file not found: {source}")
    image = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise EdgeError(f"could not decode image: {source.name}")
    if image.size == 0:
        raise EdgeError(f"empty image: {source.name}")
    if min(image.shape) < MIN_SIZE:
        raise EdgeError(
            f"image too small: {image.shape[0]}x{image.shape[1]} "
            f"(need at least {MIN_SIZE}x{MIN_SIZE})")
    result = image.astype(np.float64)
    if not np.isfinite(result).all():
        raise EdgeError(f"image contains non-finite values: {source.name}")
    LOG.info("loaded %dx%d image from %s", result.shape[0], result.shape[1],
             source.name)
    return result


def save_image(path: str | Path, image: np.ndarray) -> Path:
    """Write a uint8 image to disk (used when bundling sample data)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = np.clip(np.round(image), 0, 255).astype(np.uint8)
    if not cv2.imwrite(str(target), payload):
        raise EdgeError(f"could not write image: {target}")
    return target


# --------------------------------------------------------------------------- #
# Convolution and kernels
# --------------------------------------------------------------------------- #
def convolve2d(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """2-D convolution with reflect-101 padding (no SciPy/cv2 involved)."""
    img = np.asarray(image, dtype=np.float64)
    ker = np.asarray(kernel, dtype=np.float64)
    if img.ndim != 2:
        raise EdgeError(f"expected a 2-D image, got {img.ndim}-D array")
    if ker.ndim != 2 or ker.shape[0] != ker.shape[1]:
        raise EdgeError(f"kernel must be square, got shape {ker.shape}")
    if ker.shape[0] < 1 or ker.shape[0] % 2 == 0:
        raise EdgeError(f"kernel must have odd size, got {ker.shape[0]}")
    if not np.isfinite(ker).all():
        raise EdgeError("kernel must be finite")
    if not np.isfinite(img).all():
        raise EdgeError("image must be finite")
    if img.shape[0] < ker.shape[0] or img.shape[1] < ker.shape[1]:
        raise EdgeError("image smaller than kernel")

    half = ker.shape[0] // 2
    padded = np.pad(img, half, mode="reflect") if half else img
    out = np.zeros_like(img)
    height, width = img.shape
    for i in range(ker.shape[0]):
        for j in range(ker.shape[1]):
            weight = ker[i, j]
            if weight == 0.0:
                continue
            out += weight * padded[i:i + height, j:j + width]
    return out


def sobel(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(dI/dx, dI/dy) via the hand-written Sobel kernels."""
    return (convolve2d(image, SOBEL_X), convolve2d(image, SOBEL_Y))


def prewitt(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(dI/dx, dI/dy) via the hand-written Prewitt kernels."""
    return (convolve2d(image, PREWITT_X), convolve2d(image, PREWITT_Y))


def laplacian(image: np.ndarray) -> np.ndarray:
    """Second derivative (d2I/dx2 + d2I/dy2) via the Laplacian kernel."""
    return convolve2d(image, LAPLACIAN)


def magnitude(gx: np.ndarray, gy: np.ndarray) -> np.ndarray:
    """Gradient magnitude sqrt(gx^2 + gy^2)."""
    gx = np.asarray(gx, dtype=np.float64)
    gy = np.asarray(gy, dtype=np.float64)
    if gx.shape != gy.shape:
        raise EdgeError("gx and gy must have the same shape")
    return np.hypot(gx, gy)


# --------------------------------------------------------------------------- #
# Thresholding, Canny, dispatch
# --------------------------------------------------------------------------- #
def validate_thresholds(low: float, high: float,
                        threshold: float) -> None:
    """Validate every threshold flag before any image work happens."""
    if not np.isfinite(low) or not 0 <= low <= 255:
        raise EdgeError(f"low must be in 0..255, got {low}")
    if not np.isfinite(high) or not 0 <= high <= 255:
        raise EdgeError(f"high must be in 0..255, got {high}")
    if low >= high:
        raise EdgeError(f"low ({low}) must be < high ({high})")
    if not np.isfinite(threshold) or threshold <= 0:
        raise EdgeError(f"threshold must be > 0, got {threshold}")


def threshold_mask(values: np.ndarray, threshold: float) -> np.ndarray:
    """Boolean edge mask: values strictly above the threshold."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2:
        raise EdgeError(f"expected a 2-D array, got {values.ndim}-D")
    if not np.isfinite(threshold) or threshold < 0:
        raise EdgeError(f"threshold must be >= 0, got {threshold}")
    if not np.isfinite(values).all():
        raise EdgeError("values must be finite")
    return values > threshold


def canny_edges(image: np.ndarray, low: float = DEFAULT_LOW,
                high: float = DEFAULT_HIGH) -> np.ndarray:
    """OpenCV Canny (the cross-check method) as a boolean edge mask."""
    if not np.isfinite(low) or not 0 <= low <= 255:
        raise EdgeError(f"low must be in 0..255, got {low}")
    if not np.isfinite(high) or not 0 <= high <= 255:
        raise EdgeError(f"high must be in 0..255, got {high}")
    if low >= high:
        raise EdgeError(f"low ({low}) must be < high ({high})")
    img = np.asarray(image, dtype=np.float64)
    if img.ndim != 2:
        raise EdgeError(f"expected a 2-D image, got {img.ndim}-D")
    payload = np.clip(np.round(img), 0, 255).astype(np.uint8)
    return cv2.Canny(payload, float(low), float(high)).astype(bool)


def edge_mask(method: str, image: np.ndarray,
              threshold: float = DEFAULT_THRESHOLD,
              low: float = DEFAULT_LOW,
              high: float = DEFAULT_HIGH) -> np.ndarray:
    """Dispatch to one method and return a boolean edge mask."""
    if method not in ALL_METHODS:
        raise EdgeError(f"unknown method: {method!r} "
                        f"(choose from {', '.join(ALL_METHODS)})")
    if method == "canny":
        return canny_edges(image, low, high)
    if method == "sobel":
        values = magnitude(*sobel(image))
    elif method == "prewitt":
        values = magnitude(*prewitt(image))
    else:
        values = np.abs(laplacian(image))
    return threshold_mask(values, threshold)


def jaccard(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Intersection-over-union of two boolean masks (1.0 if both empty)."""
    a = np.asarray(mask_a, dtype=bool)
    b = np.asarray(mask_b, dtype=bool)
    if a.shape != b.shape:
        raise EdgeError("masks must have the same shape")
    union = int(np.logical_or(a, b).sum())
    if union == 0:
        return 1.0
    return float(np.logical_and(a, b).sum()) / union


# --------------------------------------------------------------------------- #
# ASCII rendering
# --------------------------------------------------------------------------- #
def ascii_map(mask: np.ndarray, width: int = ASCII_WIDTH) -> str:
    """Downsample a boolean edge mask to `width` columns of ASCII shade."""
    m = np.asarray(mask, dtype=bool)
    if m.ndim != 2:
        raise EdgeError(f"expected a 2-D mask, got {m.ndim}-D")
    if m.size == 0:
        raise EdgeError("mask is empty")
    if width < 4:
        raise EdgeError(f"width must be >= 4, got {width}")

    height, cols = m.shape
    rows = max(1, int(round(height * width / cols / 2.0)))
    ys = np.linspace(0, height, rows + 1).astype(int)
    xs = np.linspace(0, cols, width + 1).astype(int)
    lines = []
    for r in range(rows):
        line = []
        for c in range(width):
            block = m[ys[r]:max(ys[r] + 1, ys[r + 1]),
                      xs[c]:max(xs[c] + 1, xs[c + 1])]
            density = float(block.mean()) if block.size else 0.0
            line.append(SHADES[min(len(SHADES) - 1,
                                   int(density * len(SHADES)))])
        lines.append("".join(line))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Procedural sample data (deterministic, no downloads)
# --------------------------------------------------------------------------- #
def _ramp_image(size: int = 64) -> np.ndarray:
    """Horizontal linear ramp: value = 4 * column (exact slope for tests)."""
    columns = np.arange(size, dtype=np.float64) * 4.0
    return np.tile(columns, (size, 1))


def _shapes_image(size: int = 160) -> np.ndarray:
    """Square + circle + diagonal band + inner ring on a grey background."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    image = np.full((size, size), 60.0)

    image[24:76, 24:76] = 210.0                       # filled square
    circle = (xx - 112.0) ** 2 + (yy - 46.0) ** 2 <= 30.0 ** 2
    image[circle] = 30.0                              # dark disc
    band = np.abs(yy - xx - 70.0) <= 5.0              # diagonal band
    image[band] = 150.0
    ring = ((xx - 46.0) ** 2 + (yy - 116.0) ** 2 <= 34.0 ** 2) & \
           ((xx - 46.0) ** 2 + (yy - 116.0) ** 2 >= 24.0 ** 2)
    image[ring] = 235.0                               # bright ring
    return image


def _noisy_step_image(size: int = 128, sigma: float = 5.0) -> np.ndarray:
    """Vertical step edge with seeded Gaussian noise (Canny input)."""
    image = np.full((size, size), 40.0)
    image[:, size // 2:] = 210.0
    rng = np.random.default_rng(7)
    noisy = image + rng.normal(0.0, sigma, image.shape)
    return np.clip(noisy, 0, 255)


def generate_samples() -> dict[str, np.ndarray]:
    """Deterministic procedural images used as bundled demo data."""
    return {
        "gradient_ramp": _ramp_image(),
        "shapes": _shapes_image(),
        "noisy_step": _noisy_step_image(),
    }


def bundle_samples(data_dir: Path | None = None) -> list[Path]:
    """(Re)write the bundled PNG samples - used to build data/."""
    target = data_dir or DATA_DIR
    return [save_image(target / f"{name}.png", image)
            for name, image in generate_samples().items()]


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def analyse(image: np.ndarray, method: str = "sobel",
            threshold: float = DEFAULT_THRESHOLD,
            low: float = DEFAULT_LOW, high: float = DEFAULT_HIGH) -> dict:
    """Run one method (or all) and collect edge statistics."""
    methods = list(METHODS) if method == "all" else [method]
    stats: dict[str, Any] = {}
    masks: dict[str, np.ndarray] = {}
    for name in methods:
        mask = edge_mask(name, image, threshold=threshold, low=low, high=high)
        masks[name] = mask
        stats[name] = {
            "edge_pixels": int(mask.sum()),
            "fraction": round(float(mask.mean()), 4),
        }
    # Canny is the reference for every gradient method, so it is always
    # computed (cheaply) even when the user asked for a single method.
    reference = (masks["canny"] if "canny" in masks
                 else canny_edges(image, low, high))
    for name, mask in masks.items():
        if name != "canny":
            stats[name]["jaccard_vs_canny"] = round(
                jaccard(mask, reference), 4)
    return {"stats": stats, "masks": masks}


def render_report(result: dict, image: np.ndarray, name: str,
                  method: str) -> str:
    """Human-readable report for one image."""
    height, width = image.shape
    lines = [
        "EDGE DETECTOR (Sobel / Prewitt / Laplacian from scratch + Canny)",
        "=" * 64,
        f"Image       : {name} ({width}x{height}, 8-bit greyscale)",
        f"Method(s)   : {method}",
        "",
    ]
    for key, stat in result["stats"].items():
        line = (f"  {key:<9}: {stat['edge_pixels']:>6} edge pixels "
                f"({stat['fraction'] * 100:5.2f} % of the image)")
        if "jaccard_vs_canny" in stat:
            line += f"   IoU vs Canny {stat['jaccard_vs_canny']:.3f}"
        lines.append(line)
    primary = "canny" if "canny" in result["masks"] else \
        next(iter(result["masks"]))
    lines += ["", f"ASCII preview of the {primary} edge map:", ""]
    lines.append(ascii_map(result["masks"][primary]))
    return "\n".join(lines)


def to_dict(result: dict, name: str, shape: tuple[int, int]) -> dict:
    """JSON-serialisable payload for --json."""
    return {
        "image": name,
        "width": int(shape[1]),
        "height": int(shape[0]),
        "methods": {k: dict(v) for k, v in result["stats"].items()},
    }


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    """Analyse the bundled samples - fully offline."""
    root = data_dir or DATA_DIR
    expected = generate_samples()
    print("=" * 64)
    print(" EDGE DETECTOR - offline demo")
    print(" Bundled procedural PNGs; NumPy convolution; no network.")
    print("=" * 64)

    for name in expected:
        path = root / f"{name}.png"
        if not path.is_file():
            raise EdgeError(f"bundled sample not found: {path}")
        loaded = load_image(path)
        reference = expected[name].astype(np.float64)
        if loaded.shape != reference.shape or not np.array_equal(
                loaded, np.round(reference)):
            raise EdgeError(f"bundled sample does not match generator: "
                            f"{path.name} (procedural data corrupted)")
    print(f"\nVerified {len(expected)} bundled samples against the "
          f"procedural generator (no downloads).")

    # --- cross-checks the demo asserts ----------------------------------- #
    ramp = expected["gradient_ramp"].astype(np.float64)
    gx, gy = sobel(ramp)
    interior = (slice(4, -4), slice(4, -4))
    assert np.allclose(gx[interior], 32.0), \
        "Sobel gx must equal 8 * ramp slope (32)"
    assert np.allclose(gy[interior], 0.0), "ramp must have zero gy"
    lap = laplacian(ramp)
    assert np.allclose(lap[interior], 0.0), "Laplacian of a ramp is 0"
    print("\nRamp check      : gx == 32, gy == 0, laplacian == 0 "
          "(analytic slopes)")

    shapes = expected["shapes"].astype(np.float64)
    gx, gy = sobel(shapes)
    cv_gx = cv2.Sobel(shapes, cv2.CV_64F, 1, 0, ksize=3)
    cv_gy = cv2.Sobel(shapes, cv2.CV_64F, 0, 1, ksize=3)
    assert np.allclose(gx, cv_gx, atol=1e-6), "Sobel gx differs from cv2"
    assert np.allclose(gy, cv_gy, atol=1e-6), "Sobel gy differs from cv2"
    pgx, pgy = prewitt(shapes)
    assert np.allclose(pgx, cv2.filter2D(shapes, cv2.CV_64F, PREWITT_X,
                                         borderType=cv2.BORDER_REFLECT_101),
                       atol=1e-6), "Prewitt differs from cv2.filter2D"
    # cv2's ksize=1 Laplacian is the unsmoothed 4-neighbour kernel
    # [[0,1,0],[1,-4,1],[0,1,0]] - exactly the one implemented above.
    assert np.allclose(laplacian(shapes),
                       cv2.Laplacian(shapes, cv2.CV_64F, ksize=1),
                       atol=1e-6), "Laplacian differs from cv2"
    print("cv2 cross-check  : Sobel/Prewitt/Laplacian match cv2 "
          "(atol 1e-6)")

    result = analyse(shapes, method="all")
    sobel_mask = result["masks"]["sobel"]
    canny_mask = result["masks"]["canny"]
    overlap = jaccard(sobel_mask, canny_mask)
    assert overlap > 0.20, f"Sobel/Canny overlap too low: {overlap:.3f}"
    assert result["stats"]["canny"]["edge_pixels"] > 100, "Canny found nothing"
    assert result["stats"]["laplacian"]["edge_pixels"] > 100
    print(f"Canny agreement  : Sobel IoU vs Canny = {overlap:.3f} "
          f"(thin vs thick edges)")

    # noise-free vs noisy detection counts
    step = edge_mask("canny", expected["noisy_step"].astype(np.float64))
    assert 50 < int(step.sum()) < 0.2 * step.size, "noisy step edges odd"
    print(f"Noisy step       : Canny found {int(step.sum())} edge pixels "
          f"on a noisy step")

    # deterministic re-run
    again = analyse(shapes, method="all")
    assert np.array_equal(again["masks"]["sobel"], sobel_mask), \
        "not deterministic"
    assert again["stats"] == result["stats"], "stats changed between runs"

    # ASCII preview sanity
    art = ascii_map(sobel_mask)
    lines = art.splitlines()
    assert all(len(line) == ASCII_WIDTH for line in lines), "bad ASCII width"
    assert "#" in art, "ASCII preview lost every edge"
    print(f"\nASCII preview ({ASCII_WIDTH} cols):")
    for line in lines[:12]:
        print("  |" + line + "|")
    print("  ...")

    print(f"\nCross-checks OK: analytic ramp slopes, cv2 agreement "
          f"(atol 1e-6), Sobel/Canny IoU {overlap:.3f}, "
          f"deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
