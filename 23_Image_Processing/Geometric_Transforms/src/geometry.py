"""Geometric transforms from scratch - offline.

Rotate, scale, translate and arbitrary affine warps via inverse mapping
with bilinear (or nearest) interpolation, plus four out-of-bounds
handling modes. Only NumPy + Pillow - no OpenCV, no scipy, no network.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

LOG = logging.getLogger("geometry")

EDGE_MODES = ("constant", "reflect", "replicate", "wrap")
INTERPOLATIONS = ("bilinear", "nearest")
SHADES = " .:-=+*#%@"
MAX_DIM = 512
MIN_DIM = 8


class GeoError(RuntimeError):
    """Raised for missing files, bad images, and invalid transforms."""


# --------------------------------------------------------------------------- #
# Image loading / saving / ASCII preview
# --------------------------------------------------------------------------- #
def load_image(path: str | Path) -> np.ndarray:
    """Load a PNG/JPEG as a 2D uint8 array (RGB is converted to grey)."""
    source = Path(path)
    if not source.is_file():
        raise GeoError(f"file not found: {source}")
    try:
        with Image.open(source) as handle:
            array = np.asarray(handle.convert("L"), dtype=np.uint8)
    except GeoError:
        raise
    except Exception as exc:
        raise GeoError(f"could not read image {source.name}: {exc}") from exc
    if array.ndim != 2:
        raise GeoError(f"expected a 2D grayscale image, got {array.ndim}D")
    height, width = array.shape
    if height < MIN_DIM or width < MIN_DIM:
        raise GeoError(f"image too small: {height}x{width} "
                       f"(need >= {MIN_DIM}x{MIN_DIM})")
    if height > MAX_DIM or width > MAX_DIM:
        raise GeoError(f"image too large: {height}x{width} "
                       f"(max {MAX_DIM}x{MAX_DIM})")
    return array


def save_image(array: np.ndarray, path: str | Path) -> Path:
    """Write a uint8 array as a PNG (creates parent directories)."""
    image = np.asarray(array)
    if image.ndim != 2:
        raise GeoError(f"expected a 2D array to save, got {image.ndim}D")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    grey = np.clip(np.rint(image.astype(np.float64)), 0, 255).astype(np.uint8)
    Image.fromarray(grey).save(target)
    return target


def ascii_thumb(array: np.ndarray, cols: int = 48) -> str:
    """Down-sample an image to ASCII shade art (2:1 character aspect)."""
    image = np.asarray(array)
    if image.ndim != 2 or image.size == 0:
        raise GeoError("ascii_thumb needs a non-empty 2D array")
    if cols < 4:
        raise GeoError(f"cols must be >= 4, got {cols}")
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
    if hi <= lo:
        # flat image: keep the array shape, otherwise idx collapses to 0-d
        ramp = np.zeros_like(small)
    else:
        ramp = (small - lo) / (hi - lo)
    idx = np.clip(np.round(ramp * (len(SHADES) - 1)).astype(int),
                  0, len(SHADES) - 1)
    return "\n".join("".join(SHADES[v] for v in row) for row in idx)


# --------------------------------------------------------------------------- #
# Affine matrices (all map DESTINATION -> SOURCE: inverse mapping)
# --------------------------------------------------------------------------- #
def translation_matrix(dx: float, dy: float) -> np.ndarray:
    """Inverse map for content shifted by (+dx, +dy) pixels."""
    if not np.isfinite(dx) or not np.isfinite(dy):
        raise GeoError(f"translation must be finite, got ({dx}, {dy})")
    return np.array([[1.0, 0.0, -dx],
                     [0.0, 1.0, -dy],
                     [0.0, 0.0, 1.0]], dtype=np.float64)


def rotation_matrix(angle_deg: float,
                    center: tuple[float, float]) -> np.ndarray:
    """Inverse map for content rotated `angle_deg` degrees counter-clockwise
    (as displayed) about `center` in (x, y) pixel coordinates."""
    if not np.isfinite(angle_deg):
        raise GeoError(f"angle must be finite, got {angle_deg}")
    cx, cy = float(center[0]), float(center[1])
    theta = np.deg2rad(angle_deg)
    cos, sin = float(np.cos(theta)), float(np.sin(theta))
    # forward: p_out = C + [[c, s], [-s, c]] (p - C);  inverse = transpose
    forward = np.array([[cos, sin], [-sin, cos]], dtype=np.float64)
    linear = forward.T
    matrix = np.eye(3, dtype=np.float64)
    matrix[:2, :2] = linear
    matrix[:2, 2] = np.array([cx, cy]) - linear @ np.array([cx, cy])
    return matrix


def scaling_matrix(scale: float,
                   center: tuple[float, float]) -> np.ndarray:
    """Inverse map for content scaled by `scale` about `center`."""
    if not np.isfinite(scale) or scale <= 0:
        raise GeoError(f"scale must be > 0, got {scale}")
    cx, cy = float(center[0]), float(center[1])
    inverse = 1.0 / scale
    matrix = np.eye(3, dtype=np.float64)
    matrix[0, 0] = matrix[1, 1] = inverse
    matrix[0, 2] = cx * (1.0 - inverse)
    matrix[1, 2] = cy * (1.0 - inverse)
    return matrix


def compose(*matrices: np.ndarray) -> np.ndarray:
    """Compose dest->src maps applied inner-first: compose(A, B, C)
    produces the map for 'apply A, then B, then C' (= A @ B @ C)."""
    if not matrices:
        raise GeoError("compose needs at least one matrix")
    result = np.eye(3, dtype=np.float64)
    for matrix in matrices:
        result = result @ _as_matrix(matrix)
    return result


def _as_matrix(matrix: np.ndarray) -> np.ndarray:
    """Validate a 2x3 or 3x3 affine matrix and return it as 3x3."""
    array = np.asarray(matrix, dtype=np.float64)
    if array.shape == (2, 3):
        array = np.vstack([array, [0.0, 0.0, 1.0]])
    elif array.shape != (3, 3):
        raise GeoError(f"matrix must be 2x3 or 3x3, got {array.shape}")
    if not np.isfinite(array).all():
        raise GeoError("matrix must be finite")
    if abs(array[0, 0] * array[1, 1] - array[0, 1] * array[1, 0]) < 1e-12:
        raise GeoError("matrix is singular (zero area)")
    if not np.allclose(array[2], [0.0, 0.0, 1.0]):
        raise GeoError("matrix bottom row must be 0 0 1")
    return array


def _resolve(coord: np.ndarray, size: int, mode: str) -> np.ndarray:
    """Fold out-of-range sample coordinates for replicate/wrap/reflect.

    Results are guaranteed to lie in [0, size-1]; the wrap branch also
    handles the floating-point edge case where np.mod(-tiny, size)
    rounds up to exactly `size`.
    """
    if mode == "replicate":
        return np.clip(coord, 0.0, size - 1.0)
    if mode == "wrap":
        wrapped = np.mod(coord, float(size))
        wrapped = np.where(wrapped >= size, 0.0, wrapped)
        return np.clip(wrapped, 0.0, size - 1.0)
    # reflect: mirror without repeating the edge (numpy 'reflect')
    if size == 1:
        return np.zeros_like(coord)
    period = 2.0 * (size - 1)
    folded = np.mod(coord, period)
    folded = np.where(folded <= size - 1, folded, period - folded)
    return np.clip(folded, 0.0, size - 1.0)


# --------------------------------------------------------------------------- #
# Inverse-mapping warp
# --------------------------------------------------------------------------- #
def affine_warp(image: np.ndarray, matrix: np.ndarray,
                order: str = "bilinear", mode: str = "reflect") -> np.ndarray:
    """Warp an image with an inverse (dest->src) affine map.

    Every output pixel asks "which input pixel do I come from?", samples
    it with bilinear/nearest interpolation, and fills out-of-bounds
    sources according to `mode`.
    """
    source = np.asarray(image)
    if source.ndim != 2:
        raise GeoError(f"expected a 2D image, got {source.ndim}D")
    if source.size == 0:
        raise GeoError("image must not be empty")
    if order not in INTERPOLATIONS:
        raise GeoError(f"unknown interpolation {order!r} "
                       f"(choose from {', '.join(INTERPOLATIONS)})")
    if mode not in EDGE_MODES:
        raise GeoError(f"unknown edge mode {mode!r} "
                       f"(choose from {', '.join(EDGE_MODES)})")
    linear = _as_matrix(matrix)

    height, width = source.shape
    pixels = source.astype(np.float64)
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float64)
    src_x = linear[0, 0] * xs + linear[0, 1] * ys + linear[0, 2]
    src_y = linear[1, 0] * xs + linear[1, 1] * ys + linear[1, 2]

    if order == "nearest":
        if mode == "constant":
            ix = np.floor(src_x + 0.5).astype(np.int64)
            iy = np.floor(src_y + 0.5).astype(np.int64)
            valid = (ix >= 0) & (ix < width) & (iy >= 0) & (iy < height)
            out = np.where(valid,
                           pixels[np.clip(iy, 0, height - 1),
                                  np.clip(ix, 0, width - 1)], 0.0)
        else:
            rx = _resolve(src_x, width, mode)
            ry = _resolve(src_y, height, mode)
            ix = np.clip(np.floor(rx + 0.5).astype(np.int64),
                         0, width - 1)
            iy = np.clip(np.floor(ry + 0.5).astype(np.int64),
                         0, height - 1)
            out = pixels[iy, ix]
        return np.clip(np.rint(out), 0, 255).astype(np.uint8)

    # ---- bilinear -------------------------------------------------------- #
    if mode == "constant":
        x0 = np.floor(src_x).astype(np.int64)
        y0 = np.floor(src_y).astype(np.int64)
        fx, fy = src_x - x0, src_y - y0
        x1, y1 = x0 + 1, y0 + 1

        def sample(ix: np.ndarray, iy: np.ndarray) -> np.ndarray:
            valid = (ix >= 0) & (ix < width) & (iy >= 0) & (iy < height)
            return np.where(valid,
                            pixels[np.clip(iy, 0, height - 1),
                                   np.clip(ix, 0, width - 1)], 0.0)

        out = (sample(x0, y0) * (1 - fx) * (1 - fy)
               + sample(x1, y0) * fx * (1 - fy)
               + sample(x0, y1) * (1 - fx) * fy
               + sample(x1, y1) * fx * fy)
    else:
        rx = _resolve(src_x, width, mode)
        ry = _resolve(src_y, height, mode)
        x0 = np.floor(rx).astype(np.int64)
        y0 = np.floor(ry).astype(np.int64)
        fx, fy = rx - x0, ry - y0
        x1 = np.minimum(x0 + 1, width - 1)
        y1 = np.minimum(y0 + 1, height - 1)
        out = (pixels[y0, x0] * (1 - fx) * (1 - fy)
               + pixels[y0, x1] * fx * (1 - fy)
               + pixels[y1, x0] * (1 - fx) * fy
               + pixels[y1, x1] * fx * fy)

    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- #
# Convenience wrappers
# --------------------------------------------------------------------------- #
def image_center(image: np.ndarray) -> tuple[float, float]:
    """(x, y) coordinates of the pixel-grid centre of an image."""
    height, width = image.shape
    return (width - 1) / 2.0, (height - 1) / 2.0


def rotate(image: np.ndarray, angle_deg: float,
           order: str = "bilinear", mode: str = "reflect") -> np.ndarray:
    """Rotate the content counter-clockwise (as displayed) about centre."""
    matrix = rotation_matrix(angle_deg, image_center(image))
    return affine_warp(image, matrix, order=order, mode=mode)


def scale(image: np.ndarray, factor: float,
          order: str = "bilinear", mode: str = "reflect") -> np.ndarray:
    """Zoom the content by `factor` about the image centre."""
    matrix = scaling_matrix(factor, image_center(image))
    return affine_warp(image, matrix, order=order, mode=mode)


def translate(image: np.ndarray, dx: float, dy: float,
              order: str = "bilinear", mode: str = "reflect") -> np.ndarray:
    """Shift the content by (+dx, +dy) pixels."""
    matrix = translation_matrix(dx, dy)
    return affine_warp(image, matrix, order=order, mode=mode)


def image_stats(image: np.ndarray) -> dict[str, Any]:
    """Summary statistics used by the report and demo assertions."""
    array = np.asarray(image, dtype=np.float64)
    if array.ndim != 2 or array.size == 0:
        raise GeoError("stats need a non-empty 2D array")
    return {
        "mean": round(float(array.mean()), 3),
        "std": round(float(array.std()), 3),
        "min": int(array.min()),
        "max": int(array.max()),
        "pixels": int(array.size),
    }


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def mse(first: np.ndarray, second: np.ndarray) -> float:
    """Mean squared error between two images."""
    a = np.asarray(first, dtype=np.float64)
    b = np.asarray(second, dtype=np.float64)
    if a.shape != b.shape:
        raise GeoError(f"shape mismatch: {a.shape} vs {b.shape}")
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
CHECKER_IMG = Path(__file__).resolve().parent.parent / "data" / "checker_128.png"
SHAPES_IMG = Path(__file__).resolve().parent.parent / "data" / "shapes_128.png"


def run_demo(image_path: Path | None = None) -> int:
    """Rotate/scale/translate the bundled samples - offline, self-checking."""
    print("=" * 68)
    print(" GEOMETRIC TRANSFORMS - offline demo")
    print(" Inverse mapping + bilinear interpolation from scratch.")
    print("=" * 68)

    source = image_path or CHECKER_IMG
    if not source.is_file():
        raise GeoError(f"bundled sample not found: {source}")
    checker = load_image(source)
    shapes = load_image(SHAPES_IMG)
    print(f"\nLoaded {source.name}: {checker.shape[0]}x{checker.shape[1]} "
          f"grey, {len(np.unique(checker))} levels")

    # --- exact lattice checks --------------------------------------------- #
    odd = np.arange(25, dtype=np.uint8).reshape(5, 5)
    turned = affine_warp(odd, rotation_matrix(90.0, (2.0, 2.0)))
    print("\n90 degree rotation of a 5x5 lattice matches np.rot90:",
          np.array_equal(turned, np.rot90(odd, 1)))
    print("integer translation under wrap matches np.roll:",
          np.array_equal(translate(odd, 2, -1, mode="wrap"),
                         np.roll(odd, (-1, 2), axis=(0, 1))))

    # --- the bundled images ------------------------------------------------ #
    print(f"\n{'transform':<26} {'mean':>8} {'std':>8} {'range':>11} "
          f"{'PSNR dB':>9}")
    print("-" * 68)
    rows = [
        ("identity (checker)", affine_warp(checker, np.eye(3))),
        ("rotate 45 (shapes)", rotate(shapes, 45.0)),
        ("scale 1.5 (checker)", scale(checker, 1.5)),
        ("translate 30,18 (shapes)", translate(shapes, 30, 18)),
        ("nearest rotate 45", rotate(shapes, 45.0, order="nearest")),
    ]
    outputs = {}
    for label, out in rows:
        outputs[label] = out
        stats = image_stats(out)
        print(f"{label:<26} {stats['mean']:>8.1f} {stats['std']:>8.1f} "
              f"{stats['min']:>5d}..{stats['max']:<5d} "
              f"{psnr(shapes if 'shapes' in label else checker, out):>9.2f}")

    # composed pipeline: scale -> rotate -> translate (inner first)
    composed = affine_warp(checker, compose(
        scaling_matrix(1.3, (63.5, 63.5)),
        rotation_matrix(25.0, (63.5, 63.5)),
        translation_matrix(12.0, -8.0)))
    stepwise = translate(rotate(scale(checker, 1.3), 25.0), 12.0, -8.0)

    # Hard-edged art cannot test composition order: two bilinear resamples
    # differ from one on every checkerboard edge, whatever the order. So the
    # order check runs on a smooth blob, where interpolation error is small
    # and a reversed composition is unmistakable.
    grid = np.mgrid[0:128, 0:128].astype(np.float64)
    smooth = (127.0 * np.exp(-((grid[1] - 64.0) ** 2
                              + (grid[0] - 64.0) ** 2)
                             / (2.0 * 22.0 ** 2))).astype(np.uint8)
    smooth_composed = affine_warp(smooth, compose(
        scaling_matrix(1.3, (63.5, 63.5)),
        rotation_matrix(25.0, (63.5, 63.5)),
        translation_matrix(12.0, -8.0)))
    smooth_stepwise = translate(rotate(scale(smooth, 1.3), 25.0), 12.0, -8.0)
    smooth_wrong = affine_warp(smooth, compose(
        translation_matrix(12.0, -8.0),
        rotation_matrix(25.0, (63.5, 63.5)),
        scaling_matrix(1.3, (63.5, 63.5))))
    compose_diff = psnr(smooth_composed, smooth_stepwise)
    wrong_order = psnr(smooth_wrong, smooth_stepwise)
    print(f"\nCompose order check, smooth blob : {compose_diff:.2f} dB "
          f"(reversed order {wrong_order:.2f} dB)")
    print(f"Compose on hard-edged art       : "
          f"{psnr(composed, stepwise):.2f} dB (double resampling)")

    print("\nASCII preview (rotate 45, shapes):")
    for line in ascii_thumb(outputs["rotate 45 (shapes)"]).splitlines():
        print(f"  |{line}|")

    # --- cross-checks the demo asserts ------------------------------------- #
    # identity warp is exact
    assert np.array_equal(outputs["identity (checker)"], checker), \
        "identity warp must be exact"

    # exact lattice rotation and integer translation
    assert np.array_equal(turned, np.rot90(odd, 1)), "90 degree mismatch"
    turned_back = affine_warp(turned, rotation_matrix(-90.0, (2.0, 2.0)))
    assert np.array_equal(turned_back, odd), "90/-90 must round-trip exactly"
    assert np.array_equal(translate(odd, 2, -1, mode="wrap"),
                          np.roll(odd, (-1, 2), axis=(0, 1))), \
        "integer translate under wrap == np.roll"
    assert np.array_equal(translate(odd, 2, -1, order="nearest",
                                    mode="wrap"),
                          np.roll(odd, (-1, 2), axis=(0, 1)))

    # PSNR of an image against itself is inf; identity PSNR likewise
    assert psnr(checker, checker) == float("inf")
    assert psnr(checker, outputs["identity (checker)"]) == float("inf")

    # out-of-bounds handling: constant mode fills the border with zeros
    shifted = translate(checker, 40, 0, mode="constant")
    assert np.all(shifted[:, :40] == 0), \
        "constant mode must zero uncovered pixels"
    assert np.array_equal(shifted[:, 40:], checker[:, :88]), \
        "covered region must be an exact integer shift"

    # bilinear midpoint interpolation is exact on a clean ramp
    ramp = np.array([[0, 10, 20], [30, 40, 50], [60, 70, 80]],
                    dtype=np.uint8)
    half = translate(ramp, -0.5, 0, mode="replicate")
    assert int(half[0, 0]) == 5 and int(half[0, 1]) == 15, \
        f"midpoint blend expected 5/15, got {half[0, 0]}/{half[0, 1]}"

    # rotation round-trip keeps the image recognisable (two bilinear
    # resamples soften hard edges, so expect a solid-but-finite PSNR)
    rotated = rotate(shapes, 30.0)
    restored = rotate(rotated, -30.0)
    round_trip = psnr(shapes, restored)
    assert round_trip > 20.0, f"rotate round-trip PSNR {round_trip:.1f}"

    # composed matrix == applying the three warps step by step
    assert compose_diff > 30.0, f"compose mismatch PSNR {compose_diff:.1f}"
    # ... and the reversed order must not match, or the check proves nothing
    assert wrong_order < compose_diff - 3.0, (
        f"reversed composition scored {wrong_order:.1f} dB, too close to "
        f"the correct {compose_diff:.1f} dB")

    # nearest interpolation only ever emits original grey levels
    near = outputs["nearest rotate 45"]
    assert set(np.unique(near)) <= set(np.unique(shapes)), \
        "nearest must not invent grey levels"
    # bilinear output stays a legal uint8 image of the same shape
    for label, out in outputs.items():
        assert out.dtype == np.uint8 and out.shape == shapes.shape, label
        assert 0 <= out.min() and out.max() <= 255, label

    # deterministic: identical input -> identical output
    assert np.array_equal(rotate(shapes, 45.0),
                          outputs["rotate 45 (shapes)"]), "not deterministic"

    print(f"\nCross-checks OK: identity exact, 90 deg lattice round-trip, "
          f"wrap translate == np.roll, midpoint blend exact, "
          f"rotate round-trip {round_trip:.1f} dB, compose == steps "
          f"{compose_diff:.1f} dB (reversed {wrong_order:.1f} dB), "
          f"deterministic re-run")
    print("Demo completed successfully.")
    return 0
