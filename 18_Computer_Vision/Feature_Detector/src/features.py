"""Harris corners from scratch + ORB keypoint matching.

OpenCV is used for PNG decoding and as the ORB implementation (ORB's
FAST + BRIEF pipeline is a library algorithm); the Harris detector,
the box filter and non-maximum suppression are implemented here with
NumPy only. No network, no downloads.

Public API
----------
load_image                 decode a local image to uint8 grayscale
generate_samples           deterministic procedural test images
bundle_samples             write the samples to data/
harris_response            structure-tensor response map
harris_corners             threshold + 3x3 non-max suppression
orb_keypoints              ORB detect/compute
match_descriptors          Hamming kNN with Lowe ratio test
analyse                    run a mode and collect statistics
render_report              text report with ASCII preview
to_dict                    JSON-safe summary
run_demo                   offline demo over the bundled samples
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

MODES = ("harris", "orb", "all")
DEFAULT_K = 0.04
DEFAULT_THRESHOLD = 1e-4
ASCII_WIDTH = 48
ASCII_CHARS = " .:-=+*#%@"
SHIFT = (17, 9)                       # translation between scene_a / scene_b


class FeatureError(Exception):
    """Raised for invalid input, bad flags or corrupted bundled data."""


# --------------------------------------------------------------------------- #
# Procedural samples
# --------------------------------------------------------------------------- #
def _checkerboard(size: int = 128, square: int = 32) -> np.ndarray:
    y, x = np.mgrid[0:size, 0:size]
    board = (((y // square) + (x // square)) % 2) * 215 + 20
    return board.astype(np.uint8)


def _scene(shift: tuple[int, int] = (0, 0)) -> np.ndarray:
    h, w = 140, 180
    img = np.full((h, w), 28, dtype=np.uint8)
    rng = np.random.default_rng(7)
    for _ in range(46):
        cx = int(rng.integers(10, w - 10))
        cy = int(rng.integers(10, h - 10))
        value = int(rng.integers(150, 245))
        kind = int(rng.integers(0, 3))
        if kind == 0:
            cv2.circle(img, (cx, cy), int(rng.integers(3, 8)), value, -1)
        elif kind == 1:
            s = int(rng.integers(4, 9))
            cv2.rectangle(img, (cx - s, cy - s), (cx + s, cy + s), value, -1)
        else:
            s = int(rng.integers(5, 10))
            pts = np.array([[cx, cy - s], [cx - s, cy + s],
                            [cx + s, cy + s]], np.int32)
            cv2.fillPoly(img, [pts], value)
    if shift != (0, 0):
        dx, dy = shift
        img = np.roll(np.roll(img, dy, axis=0), dx, axis=1)
        if dy > 0:
            img[:dy, :] = 25
        elif dy < 0:
            img[dy:, :] = 25
        if dx > 0:
            img[:, :dx] = 25
        elif dx < 0:
            img[:, dx:] = 25
    return img


def generate_samples() -> dict[str, np.ndarray]:
    """Deterministic procedural images (no randomness)."""
    return {
        "checkerboard": _checkerboard(),
        "scene_a": _scene(),
        "scene_b": _scene(SHIFT),
    }


def bundle_samples(data_dir: Path | None = None) -> list[Path]:
    """Write every generated sample as PNG; return the paths."""
    root = data_dir or DATA_DIR
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, image in generate_samples().items():
        path = root / f"{name}.png"
        if not cv2.imwrite(str(path), image):
            raise FeatureError(f"could not write sample: {path}")
        paths.append(path)
    return paths


def load_image(path: Path | str) -> np.ndarray:
    p = Path(path)
    if not p.is_file():
        raise FeatureError(f"image not found: {p}")
    image = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FeatureError(f"could not decode image: {p.name}")
    return image


# --------------------------------------------------------------------------- #
# Box filter from scratch (integral image)
# --------------------------------------------------------------------------- #
def box_filter(arr: np.ndarray, size: int = 3) -> np.ndarray:
    """Mean filter with an odd square window, computed via cumsum."""
    if size < 1 or size % 2 == 0:
        raise FeatureError("box filter size must be a positive odd number")
    a = np.asarray(arr, dtype=np.float64)
    r = size // 2
    padded = np.pad(a, r, mode="edge")
    integral = np.cumsum(np.cumsum(padded, axis=0), axis=1)
    integral = np.pad(integral, ((1, 0), (1, 0)))
    h, w = a.shape
    total = (integral[size:size + h, size:size + w]
             - integral[0:h, size:size + w]
             - integral[size:size + h, 0:w]
             + integral[0:h, 0:w])
    return total / float(size * size)


# --------------------------------------------------------------------------- #
# Harris
# --------------------------------------------------------------------------- #
def _gradients(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    g = np.asarray(gray, dtype=np.float64) / 255.0
    gx = np.zeros_like(g)
    gy = np.zeros_like(g)
    gx[:, 1:-1] = (g[:, 2:] - g[:, :-2]) * 0.5
    gy[1:-1, :] = (g[2:, :] - g[:-2, :]) * 0.5
    return gx, gy


def harris_response(gray: np.ndarray, k: float = DEFAULT_K,
                    window: int = 3) -> np.ndarray:
    """Corner response R = det(M) - k*trace(M)^2 for every pixel."""
    if not 0.0 < k < 0.25:
        raise FeatureError(f"k must be in (0, 0.25), got {k}")
    gx, gy = _gradients(gray)
    ixx = box_filter(gx * gx, window)
    iyy = box_filter(gy * gy, window)
    ixy = box_filter(gx * gy, window)
    det = ixx * iyy - ixy * ixy
    trace = ixx + iyy
    return det - k * trace * trace


def harris_corners(gray: np.ndarray, threshold: float = DEFAULT_THRESHOLD,
                   k: float = DEFAULT_K, window: int = 3,
                   max_corners: int = 200, min_distance: int = 5
                   ) -> np.ndarray:
    """Return (N, 3) rows of ``(y, x, response)`` sorted by response.

    ``min_distance`` applies greedy suppression so a flat response plateau
    (common on hard-edged synthetic images) yields one corner, not four.
    """
    response = harris_response(gray, k=k, window=window)
    h, w = response.shape
    margin = 2
    padded = np.pad(response, 1, mode="constant", constant_values=-np.inf)
    is_max = np.ones_like(response, dtype=bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            is_max &= response >= padded[1 + dy:1 + dy + h,
                                        1 + dx:1 + dx + w]
    mask = is_max & (response > threshold)
    mask[:margin, :] = False
    mask[-margin:, :] = False
    mask[:, :margin] = False
    mask[:, -margin:] = False
    ys, xs = np.nonzero(mask)
    values = response[ys, xs]
    order = np.argsort(values)[::-1]

    kept: list[tuple[int, int, float]] = []
    radius_sq = max(0, int(min_distance)) ** 2
    for idx in order:
        y, x, value = int(ys[idx]), int(xs[idx]), float(values[idx])
        if radius_sq:
            if any((y - ky) ** 2 + (x - kx) ** 2 < radius_sq
                   for ky, kx, _ in kept):
                continue
        kept.append((y, x, value))
        if len(kept) >= max(1, max_corners):
            break
    if not kept:
        return np.zeros((0, 3), dtype=np.float64)
    return np.asarray(kept, dtype=np.float64)


# --------------------------------------------------------------------------- #
# ORB
# --------------------------------------------------------------------------- #
def orb_keypoints(image: np.ndarray, nfeatures: int = 300
                  ) -> tuple[list, np.ndarray]:
    """Detect ORB keypoints and compute descriptors."""
    if nfeatures < 1:
        raise FeatureError("nfeatures must be positive")
    orb = cv2.ORB_create(nfeatures=nfeatures)
    gray = np.asarray(image, dtype=np.uint8)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    if descriptors is None:
        descriptors = np.zeros((0, 32), dtype=np.uint8)
    return list(keypoints), descriptors


def match_descriptors(desc_a: np.ndarray, desc_b: np.ndarray,
                      ratio: float = 0.75) -> list:
    """Lowe-ratio Hamming kNN matching."""
    if not 0.0 < ratio <= 1.0:
        raise FeatureError(f"ratio must be in (0, 1], got {ratio}")
    if desc_a is None or desc_b is None or len(desc_a) == 0 or len(desc_b) == 0:
        return []
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    pairs = matcher.knnMatch(desc_a, desc_b, k=2)
    good = []
    for pair in pairs:
        if len(pair) < 2:
            continue
        first, second = pair
        if first.distance < ratio * second.distance:
            good.append(first)
    return good


def displacement_stats(keypoints_a: list, keypoints_b: list,
                       matches: list) -> dict:
    """Median/mean displacement of matched keypoints."""
    if not matches:
        return {"count": 0, "median_dx": 0.0, "median_dy": 0.0,
                "mean_distance": 0.0}
    deltas = np.array([
        [keypoints_b[m.trainIdx].pt[0] - keypoints_a[m.queryIdx].pt[0],
         keypoints_b[m.trainIdx].pt[1] - keypoints_a[m.queryIdx].pt[1]]
        for m in matches], dtype=np.float64)
    distances = np.linalg.norm(deltas, axis=1)
    return {
        "count": len(matches),
        "median_dx": round(float(np.median(deltas[:, 0])), 2),
        "median_dy": round(float(np.median(deltas[:, 1])), 2),
        "mean_distance": round(float(distances.mean()), 2),
    }


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def analyse(image: np.ndarray, mode: str = "harris",
            threshold: float = DEFAULT_THRESHOLD, k: float = DEFAULT_K,
            max_corners: int = 200, reference: np.ndarray | None = None
            ) -> dict:
    """Run a detection mode and return statistics + points."""
    if mode not in MODES:
        raise FeatureError(f"unknown mode '{mode}' "
                           f"(choose from {', '.join(MODES)})")
    if mode in ("orb", "all") and reference is None:
        raise FeatureError("orb mode needs a reference image (--compare)")

    result: dict = {"mode": mode, "shape": tuple(int(v) for v in
                                                 np.shape(image)),
                    "stats": {}, "points": None}
    if mode in ("harris", "all"):
        corners = harris_corners(image, threshold=threshold, k=k,
                                 max_corners=max_corners)
        result["points"] = corners
        result["stats"]["harris"] = {
            "corners": int(corners.shape[0]),
            "threshold": float(threshold),
            "k": float(k),
            "strongest": round(float(corners[0, 2]), 8) if len(corners) else 0.0,
        }
    if mode in ("orb", "all"):
        kp_a, desc_a = orb_keypoints(image)
        kp_b, desc_b = orb_keypoints(reference)
        matches = match_descriptors(desc_a, desc_b)
        stats = displacement_stats(kp_a, kp_b, matches)
        stats.update({"keypoints_a": len(kp_a), "keypoints_b": len(kp_b)})
        result["stats"]["orb"] = stats
    return result


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def ascii_map(mask: np.ndarray, width: int = ASCII_WIDTH) -> str:
    m = np.asarray(mask).astype(np.float64)
    if m.ndim != 2:
        raise FeatureError(f"mask must be 2-D, got {m.shape}")
    h, w = m.shape
    width = max(1, min(width, w))
    xs = np.linspace(0, w, width + 1).astype(int)
    step_y = max(1, int(np.ceil(h / max(1, width // 2))))
    rows = []
    for y in range(0, h, step_y):
        line = []
        for i in range(width):
            x0, x1 = xs[i], max(xs[i] + 1, xs[i + 1])
            block = m[y:y + step_y, x0:x1]
            value = float(block.mean()) if block.size else 0.0
            idx = min(len(ASCII_CHARS) - 1,
                      int(value * (len(ASCII_CHARS) - 1)))
            line.append(ASCII_CHARS[idx])
        rows.append("".join(line))
    return "\n".join(rows)


def corner_mask(points: np.ndarray, shape: tuple[int, int],
                radius: int = 0) -> np.ndarray:
    """Rasterise corner coordinates into a binary mask.

    ``radius`` grows each corner into a square so the ASCII preview stays
    visible after downsampling.
    """
    mask = np.zeros(shape, dtype=np.uint8)
    r = max(0, int(radius))
    for y, x, _ in np.asarray(points):
        y, x = int(y), int(x)
        mask[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1] = 1
    return mask


def render_report(mode: str, image: np.ndarray, name: str,
                  threshold: float = DEFAULT_THRESHOLD, k: float = DEFAULT_K,
                  reference: np.ndarray | None = None) -> str:
    result = analyse(image, mode=mode, threshold=threshold, k=k,
                     reference=reference)
    shape = result["shape"]
    lines = [f"File           : {name}",
             f"Size           : {shape[0]}x{shape[1]}",
             f"Mode           : {mode}", ""]
    if "harris" in result["stats"]:
        s = result["stats"]["harris"]
        lines += [f"Harris corners : {s['corners']} "
                  f"(threshold {s['threshold']:.1e}, k={s['k']:g})",
                  f"Strongest      : R={s['strongest']:.6f}", ""]
        art = ascii_map(corner_mask(result["points"], shape, radius=3))
        lines.append("ASCII preview (corner mask):")
        for row in art.splitlines()[:10]:
            lines.append("  |" + row + "|")
        lines.append("  ...")
    if "orb" in result["stats"]:
        s = result["stats"]["orb"]
        lines += ["", f"ORB keypoints  : A={s['keypoints_a']} "
                      f"B={s['keypoints_b']}",
                  f"Good matches   : {s['count']} (Lowe ratio 0.75)",
                  f"Median shift   : dx={s['median_dx']} dy={s['median_dy']}",
                  f"Mean distance  : {s['mean_distance']:.2f} px"]
    return "\n".join(lines)


def to_dict(mode: str, name: str, payload: dict) -> dict:
    return {
        "file": name,
        "mode": mode,
        "shape": [int(v) for v in payload["shape"]],
        "stats": payload["stats"],
    }


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
BUNDLED = ("checkerboard.png", "scene_a.png", "scene_b.png")


def run_demo(data_dir: Path | None = None) -> int:
    """Detect corners and match keypoints on bundled images - offline."""
    root = data_dir or DATA_DIR
    expected = generate_samples()
    print("=" * 64)
    print(" FEATURE DETECTOR - offline demo")
    print(" Harris from scratch + ORB matching; no network.")
    print("=" * 64)

    for name, reference in expected.items():
        path = root / f"{name}.png"
        if not path.is_file():
            raise FeatureError(f"bundled sample not found: {path}")
        loaded = load_image(path)
        if not np.array_equal(loaded, reference):
            raise FeatureError(f"bundled sample does not match the "
                               f"procedural generator: {path.name}")
    print(f"\nVerified {len(expected)} bundled samples against the "
          f"procedural generator (no downloads).")

    board = expected["checkerboard"]
    corners = harris_corners(board, max_corners=100)
    # a 128x128 board with 32 px squares has exactly 3x3 interior grid
    # intersections (x,y in {32,64,96})
    assert corners.shape[0] == 9, \
        f"expected 9 checkerboard corners, got {corners.shape[0]}"
    snapped = {(int(round(x / 32.0)) * 32, int(round(y / 32.0)) * 32)
               for y, x, _ in corners}
    expected_grid = {(x, y) for x in (32, 64, 96) for y in (32, 64, 96)}
    assert snapped == expected_grid, f"corner grid mismatch: {sorted(snapped)}"
    offsets = [max(abs(x - round(x / 32.0) * 32),
                   abs(y - round(y / 32.0) * 32)) for y, x, _ in corners]
    assert max(offsets) <= 2, f"corner localisation error too high: {offsets}"
    print(f"Harris grid      : 9/9 interior intersections at "
          f"{{32,64,96}}^2 (exact)")

    # response must be invariant to adding a constant offset
    response = harris_response(board)
    shifted = harris_response(np.clip(board.astype(np.int16) + 5,
                                      0, 255).astype(np.uint8))
    assert np.allclose(response, shifted, atol=1e-6), \
        "Harris response must ignore constant brightness"
    print("Brightness check : constant +5 offset leaves R unchanged")

    # ORB matching across the known (17, 9) translation
    scene_a = expected["scene_a"]
    scene_b = expected["scene_b"]
    kp_a, desc_a = orb_keypoints(scene_a)
    kp_b, desc_b = orb_keypoints(scene_b)
    matches = match_descriptors(desc_a, desc_b)
    stats = displacement_stats(kp_a, kp_b, matches)
    assert len(kp_a) >= 20 and len(kp_b) >= 20, "ORB found too few keypoints"
    assert stats["count"] >= 10, f"too few ORB matches: {stats['count']}"
    assert abs(stats["median_dx"] - SHIFT[0]) <= 3, stats
    assert abs(stats["median_dy"] - SHIFT[1]) <= 3, stats
    print(f"ORB matching     : {len(kp_a)}/{len(kp_b)} keypoints, "
          f"{stats['count']} ratio-test matches")
    print(f"Shift recovered  : dx={stats['median_dx']} dy={stats['median_dy']} "
          f"(true {SHIFT[0]},{SHIFT[1]})")

    # determinism
    again = harris_corners(board, max_corners=100)
    assert np.array_equal(again, corners), "Harris is not deterministic"
    assert analyse(scene_a, mode="all", reference=scene_b)["stats"] \
        == analyse(scene_a, mode="all", reference=scene_b)["stats"]
    print("Deterministic    : repeated Harris + ORB runs identical")

    art = ascii_map(corner_mask(corners, board.shape, radius=3))
    assert len(art.splitlines()[0]) == ASCII_WIDTH
    print("\nASCII preview (Harris corners):")
    for row in art.splitlines()[:8]:
        print("  |" + row + "|")

    print(f"\nCross-checks OK: 9/9 checkerboard corners, brightness "
          f"invariance, ORB shift ({stats['median_dx']}, "
          f"{stats['median_dy']}) ~= {SHIFT}, deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
