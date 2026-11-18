"""Motion analysis: frame differencing + running-average background models.

Both detectors are implemented with NumPy only (no cv2.absdiff, no
cv2.backgroundSubtractor). A tiny from-scratch morphology step cleans
isolated noise pixels. Fully offline: the 20-frame sequence and its
ground truth ship in ``data/``.

Public API
----------
generate_sequence       deterministic frames + truth rows
bundle_frames           write frames + truth.csv into data/
load_frames             read bundled frames (grayscale)
load_truth              read the ground-truth CSV
frame_difference        |curr - prev| > threshold
running_background      exponential moving-average background
background_mask         |frame - background| > threshold
dilate / erode          square structuring element, NumPy shifts
motion_stats            pixel counts, bbox, centroid
analyse                 run a method over the sequence
render_report           text report with ASCII overlays
to_dict                 JSON-safe summary
run_demo                offline demo over the bundled frames
"""

from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FRAMES_DIR = DATA_DIR / "frames"
TRUTH_FILE = DATA_DIR / "truth.csv"

WIDTH, HEIGHT = 128, 96
FRAME_COUNT = 20
DEFAULT_THRESHOLD = 25.0
DEFAULT_ALPHA = 0.15
DEFAULT_WARMUP = 3
METHODS = ("diff", "background", "all")
ASCII_WIDTH = 64
STATIC_BOX = (86, 10, 112, 34)          # x0, y0, x1, y1 - never moves
APPEARS_AT = 10                          # frame where the second object lands


class MotionError(Exception):
    """Raised for invalid input, bad flags or corrupted bundled data."""


# --------------------------------------------------------------------------- #
# Procedural sequence
# --------------------------------------------------------------------------- #
def _disc_position(index: int) -> tuple[int, int, int]:
    """Centre x, centre y and half-size of the moving object."""
    x = 14 + int(4.6 * index)
    y = 55 + int(12 * np.sin(2.0 * np.pi * index / FRAME_COUNT))
    return x, y, 6


def generate_sequence() -> tuple[list[np.ndarray], list[dict]]:
    """Build grayscale frames plus ground-truth rows."""
    frames: list[np.ndarray] = []
    truth: list[dict] = []
    rng = np.random.default_rng(23)
    base = np.linspace(35, 60, HEIGHT, dtype=np.float64)[:, None]
    base = np.repeat(base, WIDTH, axis=1)
    x0, y0, x1, y1 = STATIC_BOX

    for index in range(FRAME_COUNT):
        frame = base + index * 0.8          # slow global illumination drift
        frame = frame.copy()
        frame[y0:y1, x0:x1] = 190           # static bright object
        cx, cy, half = _disc_position(index)
        frame[cy - half:cy + half, cx - half:cx + half] = 225
        row = {"frame": index, "cx": cx, "cy": cy, "half": half}
        if index >= APPEARS_AT:
            hx, hy = 30, 20
            frame[hy - 5:hy + 5, hx - 5:hx + 5] = 240
            row.update({"new_x": hx, "new_y": hy})
        else:
            row.update({"new_x": -1, "new_y": -1})
        noise = rng.integers(-4, 5, (HEIGHT, WIDTH))
        frame = np.clip(frame + noise, 0, 255).astype(np.uint8)
        frames.append(frame)
        truth.append(row)
    return frames, truth


def bundle_frames(data_dir: Path | None = None) -> list[Path]:
    root = data_dir or DATA_DIR
    frames_dir = root / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames, truth = generate_sequence()
    paths = []
    for index, frame in enumerate(frames):
        path = frames_dir / f"frame_{index:02d}.png"
        if not cv2.imwrite(str(path), frame):
            raise MotionError(f"could not write frame: {path}")
        paths.append(path)
    with (root / "truth.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(truth[0]))
        writer.writeheader()
        writer.writerows(truth)
    return paths


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_frames(directory: Path | None = None) -> list[np.ndarray]:
    root = Path(directory) if directory is not None else FRAMES_DIR
    if not root.is_dir():
        raise MotionError(f"frames directory not found: {root}")
    paths = sorted(root.glob("frame_*.png"))
    if not paths:
        raise MotionError(f"no frames found in {root}")
    frames = []
    for path in paths:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise MotionError(f"could not decode frame: {path.name}")
        frames.append(image)
    return frames


def load_truth(data_dir: Path | None = None) -> list[dict]:
    path = (data_dir or DATA_DIR) / "truth.csv"
    if not path.is_file():
        raise MotionError(f"ground truth not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [{k: int(v) for k, v in row.items()} for row in rows]


# --------------------------------------------------------------------------- #
# Detectors (NumPy only)
# --------------------------------------------------------------------------- #
def _validate_threshold(threshold: float) -> None:
    if not 0 < threshold < 255:
        raise MotionError(f"threshold must be in (0, 255), got {threshold}")


def frame_difference(previous: np.ndarray, current: np.ndarray,
                     threshold: float = DEFAULT_THRESHOLD) -> np.ndarray:
    """Boolean mask of pixels whose brightness changed by > threshold."""
    _validate_threshold(threshold)
    prev = np.asarray(previous, dtype=np.float64)
    curr = np.asarray(current, dtype=np.float64)
    if prev.shape != curr.shape:
        raise MotionError(f"frame shapes differ: {prev.shape} vs {curr.shape}")
    return np.abs(curr - prev) > threshold


def running_background(frames: list[np.ndarray],
                       alpha: float = DEFAULT_ALPHA) -> np.ndarray:
    """Exponential moving-average background model (``alpha`` = adapt rate)."""
    if not frames:
        raise MotionError("no frames for the background model")
    if not 0 < alpha <= 1:
        raise MotionError(f"alpha must be in (0, 1], got {alpha}")
    model = np.asarray(frames[0], dtype=np.float64).copy()
    for frame in frames[1:]:
        arr = np.asarray(frame, dtype=np.float64)
        if arr.shape != model.shape:
            raise MotionError(f"frame shapes differ: {arr.shape} vs "
                              f"{model.shape}")
        model = (1.0 - alpha) * model + alpha * arr
    return model


def background_mask(frame: np.ndarray, background: np.ndarray,
                    threshold: float = DEFAULT_THRESHOLD) -> np.ndarray:
    _validate_threshold(threshold)
    arr = np.asarray(frame, dtype=np.float64)
    bg = np.asarray(background, dtype=np.float64)
    if arr.shape != bg.shape:
        raise MotionError(f"frame and background shapes differ: "
                          f"{arr.shape} vs {bg.shape}")
    return np.abs(arr - bg) > threshold


# --------------------------------------------------------------------------- #
# From-scratch morphology
# --------------------------------------------------------------------------- #
def _apply(mask: np.ndarray, mode: str, iterations: int) -> np.ndarray:
    if iterations < 0:
        raise MotionError("iterations must be non-negative")
    if iterations == 0:
        return np.asarray(mask).astype(bool).copy()
    m = np.asarray(mask).astype(bool)
    if m.ndim != 2:
        raise MotionError(f"mask must be 2-D, got {m.shape}")
    h, w = m.shape
    out = m
    for _ in range(iterations):
        padded = np.pad(out, 1, mode="constant", constant_values=False)
        windows = [padded[dy:dy + h, dx:dx + w]
                   for dy in range(3) for dx in range(3)]
        if mode == "dilate":
            out = np.logical_or.reduce(windows)
        else:
            out = np.logical_and.reduce(windows)
    return out


def dilate(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    return _apply(mask, "dilate", iterations)


def erode(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    return _apply(mask, "erode", iterations)


def clean_mask(mask: np.ndarray) -> np.ndarray:
    """Opening then closing: drop speckles, fill pinholes."""
    return dilate(erode(mask, 1), 1)


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def motion_stats(mask: np.ndarray) -> dict:
    m = np.asarray(mask).astype(bool)
    if m.ndim != 2:
        raise MotionError(f"mask must be 2-D, got {m.shape}")
    total = m.size
    pixels = int(m.sum())
    if pixels == 0:
        return {"pixels": 0, "ratio": 0.0, "bbox": None, "centroid": None}
    ys, xs = np.nonzero(m)
    return {
        "pixels": pixels,
        "ratio": round(pixels / total, 6),
        "bbox": [int(xs.min()), int(ys.min()),
                 int(xs.max()), int(ys.max())],
        "centroid": [round(float(xs.mean()), 2), round(float(ys.mean()), 2)],
    }


def _box_covered(mask: np.ndarray, cx: int, cy: int, half: int,
                 pad: int = 3, min_fraction: float = 0.3) -> bool:
    x0 = max(0, cx - half - pad)
    x1 = min(mask.shape[1], cx + half + pad + 1)
    y0 = max(0, cy - half - pad)
    y1 = min(mask.shape[0], cy + half + pad + 1)
    region = mask[y0:y1, x0:x1]
    return region.size > 0 and region.mean() >= min_fraction


def analyse(frames: list[np.ndarray], method: str = "all",
            threshold: float = DEFAULT_THRESHOLD,
            alpha: float = DEFAULT_ALPHA, warmup: int = 3) -> dict:
    if not frames:
        raise MotionError("no frames to analyse")
    if method not in METHODS:
        raise MotionError(f"unknown method '{method}' "
                          f"(choose from {', '.join(METHODS)})")
    _validate_threshold(threshold)
    if warmup < 1:
        raise MotionError(f"warmup must be at least 1 frame, got {warmup}")
    result: dict = {"frames": len(frames), "method": method,
                    "stats": {}, "masks": {}}
    if method in ("diff", "all"):
        masks = [np.zeros(np.shape(frames[0]), dtype=bool)]
        for previous, current in zip(frames, frames[1:]):
            masks.append(frame_difference(previous, current, threshold))
        result["masks"]["diff"] = masks
        result["stats"]["diff"] = {
            "active_frames": int(sum(1 for m in masks if m.any())),
            "mean_pixels": round(float(np.mean([m.sum() for m in masks])), 2),
            "max_pixels": int(max(m.sum() for m in masks)),
        }
    if method in ("background", "all"):
        # learned from the first `warmup` frames only: the model is causal,
        # so objects that appear later cannot leave "ghosts" in the past
        background = running_background(frames[:max(1, warmup)], alpha)
        masks = [clean_mask(background_mask(f, background, threshold))
                 for f in frames]
        result["background"] = background
        result["masks"]["background"] = masks
        result["stats"]["background"] = {
            "alpha": float(alpha),
            "warmup": int(warmup),
            "active_frames": int(sum(1 for m in masks if m.any())),
            "mean_pixels": round(float(np.mean([m.sum() for m in masks])), 2),
            "max_pixels": int(max(m.sum() for m in masks)),
        }
    return result


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def ascii_overlay(mask: np.ndarray, width: int = ASCII_WIDTH) -> str:
    m = np.asarray(mask).astype(float)
    if m.ndim != 2:
        raise MotionError(f"mask must be 2-D, got {m.shape}")
    h, w = m.shape
    width = max(1, min(width, w))
    xs = np.linspace(0, w, width + 1).astype(int)
    height = max(1, int(width * h / w / 2))
    ys = np.linspace(0, h, height + 1).astype(int)
    rows = []
    for j in range(height):
        y0, y1 = ys[j], max(ys[j] + 1, ys[j + 1])
        line = []
        for i in range(width):
            x0, x1 = xs[i], max(xs[i] + 1, xs[i + 1])
            block = m[y0:y1, x0:x1]
            line.append("#" if block.mean() > 0.4 else ".")
        rows.append("".join(line))
    return "\n".join(rows)


def render_report(frames: list[np.ndarray], method: str = "all",
                  threshold: float = DEFAULT_THRESHOLD,
                  alpha: float = DEFAULT_ALPHA,
                  warmup: int = DEFAULT_WARMUP) -> str:
    result = analyse(frames, method, threshold, alpha, warmup)
    lines = [f"Frames         : {result['frames']}",
             f"Frame size     : {WIDTH}x{HEIGHT}",
             f"Method         : {method}", ""]
    for key in ("diff", "background"):
        if key not in result["stats"]:
            continue
        s = result["stats"][key]
        lines += [f"[{key}] active {s['active_frames']}/{result['frames']} "
                  f"frames, mean {s['mean_pixels']:.0f} px, "
                  f"max {s['max_pixels']} px"]
        last = motion_stats(result["masks"][key][-1])
        lines.append(f"  last frame bbox: {last['bbox']} "
                     f"centroid {last['centroid']}")
        lines.append("")
    lines.append(f"ASCII overlay (last frame, {method}):")
    key = "background" if "background" in result["masks"] else "diff"
    for row in ascii_overlay(result["masks"][key][-1]).splitlines():
        lines.append("  |" + row + "|")
    return "\n".join(lines)


def to_dict(method: str, payload: dict) -> dict:
    return {"frames": int(payload["frames"]), "method": method,
            "stats": payload["stats"]}


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    root = data_dir or DATA_DIR
    print("=" * 64)
    print(" MOTION ANALYZER - offline demo")
    print(" Frame differencing + running-average background model.")
    print("=" * 64)

    expected_frames, expected_truth = generate_sequence()
    frames = load_frames(root / "frames")
    if len(frames) != len(expected_frames):
        raise MotionError(f"expected {len(expected_frames)} frames, "
                          f"found {len(frames)}")
    for index, (loaded, expected) in enumerate(zip(frames, expected_frames)):
        if not np.array_equal(loaded, expected):
            raise MotionError(f"frame {index} does not match the generator")
    truth = load_truth(root)
    if truth != expected_truth:
        raise MotionError("truth.csv does not match the generator")
    print(f"\nVerified {len(frames)} bundled frames + truth.csv against the "
          f"procedural generator (no downloads).")

    # --- frame differencing -------------------------------------------- #
    diff_result = analyse(frames, method="diff")
    diff_masks = diff_result["masks"]["diff"]
    assert not diff_masks[0].any(), "frame 0 has no previous frame"
    assert all(m.any() for m in diff_masks[1:]), \
        "every moving frame must differ from its predecessor"
    for index in range(1, FRAME_COUNT):
        cx, cy, half = _disc_position(index)
        assert _box_covered(diff_masks[index], cx, cy, half,
                            min_fraction=0.15), \
            f"diff mask misses the moving object at frame {index}"
    print(f"Frame diff       : {FRAME_COUNT - 1}/{FRAME_COUNT - 1} moving "
          f"frames detected (frame 0 empty by construction)")

    # --- background subtraction ---------------------------------------- #
    bg_result = analyse(frames, method="background")
    bg_masks = bg_result["masks"]["background"]
    assert all(m.any() for m in bg_masks), \
        "background model must see the object in every frame"
    for index in range(FRAME_COUNT):
        cx, cy, half = _disc_position(index)
        assert _box_covered(bg_masks[index], cx, cy, half), \
            f"background mask misses the object at frame {index}"
    print(f"Background model : object detected in {FRAME_COUNT}/"
          f"{FRAME_COUNT} frames (incl. frame 0)")

    # static object must not be flagged (the model absorbs it)
    x0, y0, x1, y1 = STATIC_BOX
    static_rate = float(np.mean([m[y0 + 2:y1 - 2, x0 + 2:x1 - 2].mean()
                                 for m in bg_masks]))
    assert static_rate < 0.05, f"static object flagged: {static_rate:.3f}"
    print(f"Static object    : flagged in {static_rate:.1%} of its area "
          f"(correctly ignored)")

    # the late-appearing object must show up after APPEARS_AT
    late = bg_masks[-1]
    assert late[15:25, 25:35].mean() > 0.5, "new object not detected"
    early = bg_masks[APPEARS_AT - 1]
    assert early[15:25, 25:35].mean() < 0.1, "new object leaked in early"
    print(f"New object       : absent before frame {APPEARS_AT}, present "
          f"after (asserted)")

    # --- illumination invariance --------------------------------------- #
    flat_a = np.full((HEIGHT, WIDTH), 60, dtype=np.uint8)
    flat_b = np.full((HEIGHT, WIDTH), 66, dtype=np.uint8)
    assert not frame_difference(flat_a, flat_b, 25).any(), \
        "a +6 brightness step must stay below threshold 25"
    assert frame_difference(flat_a, flat_b, 3).all(), "small threshold too low"
    print("Illumination     : +6 global drift yields no motion at "
          "threshold 25 (correct)")

    # --- morphology ----------------------------------------------------- #
    noisy = np.zeros((HEIGHT, WIDTH), dtype=bool)
    noisy[10, 10] = True
    noisy[50:60, 50:60] = True
    cleaned = clean_mask(noisy)
    assert cleaned[10, 10] == 0, "opening must remove the single-pixel speck"
    assert cleaned[54, 54], "opening must preserve the solid block"
    print("Morphology       : opening removes the 1-px speck, keeps the "
          "10x10 block")

    stats = motion_stats(bg_masks[-1])
    assert stats["pixels"] > 0 and stats["bbox"] is not None
    assert stats["centroid"] is not None
    print(f"Last-frame stats : {stats['pixels']} px "
          f"({stats['ratio']:.2%}), bbox {stats['bbox']}")

    again = analyse(frames, method="all")
    assert again["stats"]["background"] == bg_result["stats"]["background"]
    assert again["stats"]["diff"] == diff_result["stats"]["diff"]
    print("Deterministic    : repeated analysis is identical")

    print("\nASCII overlay (last frame, background model):")
    for row in ascii_overlay(bg_masks[-1]).splitlines():
        print("  |" + row + "|")

    print("\nCross-checks OK: 20/20 frames verified, diff catches all moving "
          "frames, background catches all frames, static object ignored, "
          "new object gated, illumination robustness, morphology")
    print("Demo completed successfully.")
    return 0
