"""From-scratch image segmentation: Otsu, k-means, connected components.

Everything is implemented with NumPy; OpenCV is used only to *cross-check*
the results (and to decode PNGs). No network, no downloads.

Public API
----------
load_image / load_color_image   decode a local PNG/JPG into an array
otsu_threshold                  between-class-variance threshold search
threshold_mask                  boolean mask from a threshold
kmeans_segment                  seeded k-means over pixel colours
connected_components            BFS labelling, 4- or 8-connectivity
analyse                         run a mode and collect statistics
render_report                   human-readable text report
to_dict                         JSON-safe summary
run_demo                        offline demo over the bundled samples
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

MIN_CLUSTERS = 2
MAX_CLUSTERS = 8
MODES = ("otsu", "kmeans", "components", "all")
ASCII_WIDTH = 48
ASCII_CHARS = " .:-=+*#%@"


class SegError(Exception):
    """Raised for invalid input, bad flags or corrupted bundled data."""


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_image(path: Path | str) -> np.ndarray:
    """Load a local image as 2-D uint8 grayscale."""
    p = Path(path)
    if not p.is_file():
        raise SegError(f"image not found: {p}")
    image = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise SegError(f"could not decode image: {p.name}")
    return image


def load_color_image(path: Path | str) -> np.ndarray:
    """Load a local image as HxWx3 uint8 BGR."""
    p = Path(path)
    if not p.is_file():
        raise SegError(f"image not found: {p}")
    image = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if image is None:
        raise SegError(f"could not decode image: {p.name}")
    return image


def to_gray(image: np.ndarray) -> np.ndarray:
    """Convert any loaded image to a 2-D uint8 array."""
    arr = np.asarray(image)
    if arr.ndim == 2:
        return arr.astype(np.uint8, copy=False)
    if arr.ndim == 3 and arr.shape[2] == 3:
        return cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    if arr.ndim == 3 and arr.shape[2] == 4:
        return cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_BGRA2GRAY)
    raise SegError(f"unsupported image shape: {arr.shape}")


# --------------------------------------------------------------------------- #
# Otsu thresholding (from scratch)
# --------------------------------------------------------------------------- #
def otsu_threshold(gray: np.ndarray) -> int:
    """Return the threshold maximising between-class variance (0..255)."""
    arr = to_gray(gray)
    hist = np.bincount(arr.ravel(), minlength=256).astype(np.float64)
    total = hist.sum()
    if total == 0:
        raise SegError("image contains no pixels")
    prob = hist / total
    levels = np.arange(256, dtype=np.float64)
    omega = np.cumsum(prob)                 # weight of background
    mu = np.cumsum(prob * levels)           # background mean accumulator
    mu_total = mu[-1]
    denom = omega * (1.0 - omega)
    with np.errstate(divide="ignore", invalid="ignore"):
        sigma_b = np.where(denom > 0,
                           (mu_total * omega - mu) ** 2 / denom,
                           0.0)
    return int(np.argmax(sigma_b))


def threshold_mask(gray: np.ndarray, threshold: int) -> np.ndarray:
    """Boolean mask of pixels strictly brighter than ``threshold``."""
    if not 0 <= threshold <= 255:
        raise SegError(f"threshold must be in 0..255, got {threshold}")
    return to_gray(gray) > threshold


def otsu_mask(gray: np.ndarray) -> tuple[np.ndarray, int]:
    """Convenience: Otsu threshold + mask."""
    threshold = otsu_threshold(gray)
    return threshold_mask(gray, threshold), threshold


# --------------------------------------------------------------------------- #
# k-means (from scratch)
# --------------------------------------------------------------------------- #
def _init_centers(pixels: np.ndarray, k: int,
                  rng: np.random.Generator) -> np.ndarray:
    """Deterministic k-means++ style seeding."""
    n = pixels.shape[0]
    centers = [pixels[int(rng.integers(n))]]
    for _ in range(1, k):
        dist = np.min(
            ((pixels[:, None, :] - np.asarray(centers)[None, :, :]) ** 2)
            .sum(axis=2), axis=1)
        total = dist.sum()
        if total <= 0:
            idx = int(rng.integers(n))
        else:
            idx = int(rng.choice(n, p=dist / total))
        centers.append(pixels[idx])
    return np.asarray(centers, dtype=np.float64)


def kmeans_segment(image: np.ndarray, clusters: int = 4, seed: int = 42,
                   max_iter: int = 30, tol: float = 1e-4
                   ) -> tuple[np.ndarray, np.ndarray, float, int]:
    """Cluster pixel colours.

    Returns ``(labels, centers, inertia, iterations)`` where ``labels`` has
    the same height/width as the input and ``centers`` is ``(k, 3)``.
    """
    if not MIN_CLUSTERS <= clusters <= MAX_CLUSTERS:
        raise SegError(f"clusters must be in {MIN_CLUSTERS}..{MAX_CLUSTERS}, "
                       f"got {clusters}")
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise SegError(f"unsupported image shape: {arr.shape}")
    rgb = arr[:, :, :3].astype(np.float64)
    h, w = rgb.shape[:2]
    pixels = rgb.reshape(-1, 3)

    rng = np.random.default_rng(seed)
    centers = _init_centers(pixels, clusters, rng)
    labels = np.full(pixels.shape[0], -1, dtype=np.int32)
    iterations = 0

    for step in range(1, max_iter + 1):
        dist = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_labels = dist.argmin(axis=1).astype(np.int32)
        new_centers = centers.copy()
        for idx in range(clusters):
            members = pixels[new_labels == idx]
            if members.size:
                new_centers[idx] = members.mean(axis=0)
        shift = float(np.linalg.norm(new_centers - centers))
        centers = new_centers
        iterations = step
        if shift < tol and np.array_equal(new_labels, labels):
            labels = new_labels
            break
        labels = new_labels

    diff = pixels - centers[labels]
    inertia = float((diff ** 2).sum())
    return labels.reshape(h, w), centers, inertia, iterations


# --------------------------------------------------------------------------- #
# Connected components (from scratch)
# --------------------------------------------------------------------------- #
_OFFSETS = {
    4: ((-1, 0), (1, 0), (0, -1), (0, 1)),
    8: ((-1, -1), (-1, 0), (-1, 1), (0, -1),
        (0, 1), (1, -1), (1, 0), (1, 1)),
}


def connected_components(mask: np.ndarray, connectivity: int = 8
                         ) -> tuple[np.ndarray, int]:
    """Label connected foreground regions with an explicit BFS stack."""
    if connectivity not in _OFFSETS:
        raise SegError("connectivity must be 4 or 8")
    m = np.asarray(mask).astype(bool)
    if m.ndim != 2:
        raise SegError(f"mask must be 2-D, got {m.shape}")
    h, w = m.shape
    labels = np.zeros((h, w), dtype=np.int32)
    offsets = _OFFSETS[connectivity]
    count = 0
    for y in range(h):
        for x in range(w):
            if not m[y, x] or labels[y, x]:
                continue
            count += 1
            labels[y, x] = count
            stack = [(y, x)]
            while stack:
                cy, cx = stack.pop()
                for dy, dx in offsets:
                    ny, nx = cy + dy, cx + dx
                    if (0 <= ny < h and 0 <= nx < w
                            and m[ny, nx] and labels[ny, nx] == 0):
                        labels[ny, nx] = count
                        stack.append((ny, nx))
    return labels, count


def component_sizes(labels: np.ndarray) -> np.ndarray:
    """Foreground region sizes, largest first (background excluded)."""
    arr = np.asarray(labels)
    if arr.size == 0:
        return np.zeros(0, dtype=np.int64)
    counts = np.bincount(arr.ravel().astype(np.int64))
    sizes = counts[1:] if counts.size > 1 else np.zeros(0, dtype=np.int64)
    return np.sort(sizes)[::-1]


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def analyse(image: np.ndarray, mode: str = "otsu", clusters: int = 4,
            connectivity: int = 8, seed: int = 42) -> dict:
    """Run one segmentation mode and return masks + statistics."""
    if mode not in MODES:
        raise SegError(f"unknown mode '{mode}' (choose from {', '.join(MODES)})")
    if not MIN_CLUSTERS <= clusters <= MAX_CLUSTERS:
        raise SegError(f"clusters must be in {MIN_CLUSTERS}..{MAX_CLUSTERS}, "
                       f"got {clusters}")
    if connectivity not in _OFFSETS:
        raise SegError("connectivity must be 4 or 8")

    result: dict = {"mode": mode, "shape": tuple(int(v) for v in
                                                 np.shape(image)),
                    "stats": {}, "masks": {}}
    gray = to_gray(image)

    if mode in ("otsu", "components", "all"):
        mask, threshold = otsu_mask(gray)
        result["masks"]["otsu"] = mask
        result["stats"]["otsu"] = {
            "threshold": int(threshold),
            "foreground_pixels": int(mask.sum()),
            "foreground_ratio": round(float(mask.mean()), 6),
        }
        if mode in ("components", "all"):
            labels, count = connected_components(mask, connectivity)
            sizes = component_sizes(labels)
            result["masks"]["components"] = labels
            result["stats"]["components"] = {
                "count": int(count),
                "connectivity": int(connectivity),
                "largest": int(sizes[0]) if sizes.size else 0,
                "median": round(float(np.median(sizes)), 3) if sizes.size else 0.0,
                "tiny_regions": int((sizes < 10).sum()),
            }

    if mode in ("kmeans", "all"):
        labels, centers, inertia, iterations = kmeans_segment(
            image, clusters=clusters, seed=seed)
        counts = np.bincount(labels.ravel(), minlength=clusters)
        result["masks"]["kmeans"] = labels
        result["stats"]["kmeans"] = {
            "clusters": int(clusters),
            "seed": int(seed),
            "iterations": int(iterations),
            "inertia": round(inertia, 3),
            "cluster_sizes": [int(v) for v in counts],
            "centers": [[round(float(c), 2) for c in row] for row in centers],
        }
    return result


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def ascii_map(mask: np.ndarray, width: int = ASCII_WIDTH) -> str:
    """Downsample a mask to an ASCII art block."""
    m = np.asarray(mask).astype(np.float64)
    if m.ndim != 2:
        raise SegError(f"mask must be 2-D, got {m.shape}")
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
            idx = min(len(ASCII_CHARS) - 1, int(value * (len(ASCII_CHARS) - 1)))
            line.append(ASCII_CHARS[idx])
        rows.append("".join(line))
    return "\n".join(rows)


def render_report(mode: str, image: np.ndarray, name: str,
                  clusters: int = 4, connectivity: int = 8,
                  seed: int = 42) -> str:
    """Build the console report for one segmentation run."""
    result = analyse(image, mode=mode, clusters=clusters,
                     connectivity=connectivity, seed=seed)
    shape = result["shape"]
    lines = [f"File           : {name}",
             f"Shape          : {shape[0]}x{shape[1]}"
             + (f"x{shape[2]}" if len(shape) == 3 else ""),
             f"Mode           : {mode}", ""]

    if "otsu" in result["stats"]:
        s = result["stats"]["otsu"]
        lines += [f"Otsu threshold : {s['threshold']}",
                  f"Foreground     : {s['foreground_pixels']} px "
                  f"({s['foreground_ratio']:.1%})", ""]
    if "components" in result["stats"]:
        s = result["stats"]["components"]
        lines += [f"Components     : {s['count']} regions "
                  f"({s['connectivity']}-connected)",
                  f"Largest region : {s['largest']} px",
                  f"Median region  : {s['median']:.1f} px",
                  f"Tiny (<10 px)  : {s['tiny_regions']}", ""]
    if "kmeans" in result["stats"]:
        s = result["stats"]["kmeans"]
        lines += [f"k-means        : k={s['clusters']} seed={s['seed']} "
                  f"iterations={s['iterations']}",
                  f"Inertia (SSE)  : {s['inertia']:.1f}",
                  f"Cluster sizes  : {s['cluster_sizes']}", ""]

    mask_key = "otsu" if "otsu" in result["masks"] else "kmeans"
    art = ascii_map(result["masks"][mask_key])
    lines.append(f"ASCII preview ({ASCII_WIDTH} cols):")
    for row in art.splitlines()[:12]:
        lines.append("  |" + row + "|")
    lines.append("  ...")
    return "\n".join(lines)


def to_dict(mode: str, name: str, payload: dict) -> dict:
    """JSON-safe view of ``analyse`` output (masks omitted)."""
    return {
        "file": name,
        "mode": mode,
        "shape": [int(v) for v in payload["shape"]],
        "stats": payload["stats"],
    }


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
BUNDLED = ("otsu_shapes.png", "components.png", "color_blocks.png")


def run_demo(data_dir: Path | None = None) -> int:
    """Segment the bundled procedural samples - fully offline."""
    root = data_dir or DATA_DIR
    print("=" * 64)
    print(" IMAGE SEGMENTATION - offline demo")
    print(" From-scratch Otsu / k-means / components, cv2 cross-checks.")
    print("=" * 64)

    for name in BUNDLED:
        path = root / name
        if not path.is_file():
            raise SegError(f"bundled sample not found: {path}")
        image = load_image(path)
        if image.size == 0:
            raise SegError(f"bundled sample is empty: {name}")
    print(f"\nLoaded {len(BUNDLED)} bundled samples (no downloads).")

    # --- Otsu vs OpenCV ------------------------------------------------ #
    shapes = load_image(root / "otsu_shapes.png")
    threshold = otsu_threshold(shapes)
    cv_value, _ = cv2.threshold(shapes, 0, 255,
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    assert int(cv_value) == threshold, \
        f"Otsu {threshold} differs from cv2 {int(cv_value)}"
    mask = threshold_mask(shapes, threshold)
    assert 0.05 < float(mask.mean()) < 0.95, "Otsu mask is degenerate"
    print(f"Otsu threshold   : {threshold} == cv2.THRESH_OTSU "
          f"(foreground {mask.mean():.1%})")

    # --- components vs OpenCV ------------------------------------------ #
    blobs = load_image(root / "components.png")
    bmask, _ = otsu_mask(blobs)
    labels, count = connected_components(bmask, 8)
    cv_count, _ = cv2.connectedComponents(bmask.astype(np.uint8), 8)
    assert count == cv_count - 1, \
        f"components {count} differs from cv2 {cv_count - 1}"
    sizes = component_sizes(labels)
    assert sizes.size == count and int(sizes[0]) >= int(sizes[-1])
    print(f"Components       : {count} == cv2.connectedComponents "
          f"(largest {int(sizes[0])} px, smallest {int(sizes[-1])} px)")

    # --- k-means sanity + determinism ---------------------------------- #
    colour = load_color_image(root / "color_blocks.png")
    labels_a, centers_a, inertia_a, iters_a = kmeans_segment(colour, 4, 42)
    labels_b, centers_b, inertia_b, _ = kmeans_segment(colour, 4, 42)
    assert np.array_equal(labels_a, labels_b), "k-means is not deterministic"
    assert np.allclose(centers_a, centers_b)
    assert inertia_b == inertia_a
    again = analyse(colour, mode="kmeans", clusters=4, seed=42)
    assert again["stats"]["kmeans"]["inertia"] == round(inertia_a, 3)
    pixels = colour.reshape(-1, 3).astype(np.float64)
    global_mean = pixels.mean(axis=0)
    one_cluster_sse = float(((pixels - global_mean) ** 2).sum())
    assert inertia_a < one_cluster_sse, (
        "4 clusters must explain variance better than 1")
    used = len(set(np.unique(labels_a).tolist()))
    assert used == 4, f"expected 4 clusters in use, got {used}"
    print(f"k-means          : k=4 converged in {iters_a} iterations, "
          f"SSE {inertia_a:.0f} vs 1-cluster {one_cluster_sse:.0f}, "
          f"deterministic")

    # --- mode validation + ASCII preview ------------------------------- #
    for mode in MODES:
        result = analyse(colour, mode=mode, clusters=3, connectivity=4)
        assert result["mode"] == mode
    art = ascii_map(np.asarray(labels_a) > 0)
    assert art and len(set(art.splitlines()[0])) > 1
    print("\nASCII preview (k=4 labels):")
    for row in art.splitlines()[:8]:
        print("  |" + row + "|")

    print(f"\nCross-checks OK: Otsu == cv2, components == cv2 "
          f"({count} regions), k-means deterministic + monotone SSE, "
          f"all 4 modes run")
    print("\nDemo completed successfully.")
    return 0
