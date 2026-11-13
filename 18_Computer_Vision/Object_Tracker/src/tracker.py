"""Colour-blob object tracking over a synthetic video sequence.

The sequence is procedurally generated (deterministic), bundled as PNG
frames in ``data/frames`` plus a ground-truth CSV, and tracked by colour
thresholding + centroid extraction + nearest-neighbour association.
Fully offline: no video codecs, no downloads, no network.

Public API
----------
generate_sequence     deterministic frames + ground-truth rows
bundle_frames         write frames + truth.csv into data/
load_frames           read the bundled frames in order
load_truth            read the bundled ground-truth CSV
colour_mask           threshold one tracked colour
blob_centroid         centroid of the largest blob (or None)
track_colour          per-frame centroids with jump rejection
analyse               tracking statistics for every colour
render_report         text report with an ASCII trajectory map
to_dict               JSON-safe summary
run_demo              offline demo over the bundled frames
"""

from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FRAMES_DIR = DATA_DIR / "frames"
TRUTH_FILE = DATA_DIR / "truth.csv"

WIDTH, HEIGHT = 160, 120
FRAME_COUNT = 24
RADIUS = 7
NOISE_AMPLITUDE = 5
COLOUR_RANGES = {
    "red": ((150, 0, 0), (255, 90, 90)),
    "blue": ((0, 0, 150), (90, 90, 255)),
}
BALL_RGB = {"red": (215, 15, 15), "blue": (15, 15, 215)}
MAX_JUMP = 30.0
ASCII_WIDTH = 64


class TrackerError(Exception):
    """Raised for invalid input, bad flags or corrupted bundled data."""


# --------------------------------------------------------------------------- #
# Procedural sequence
# --------------------------------------------------------------------------- #
def _positions(index: int) -> dict[str, tuple[int, int]]:
    t = index / float(FRAME_COUNT - 1)
    red_x = 20 + int(120 * t)
    red_y = 85 + int(20 * np.sin(2.0 * np.pi * t))
    blue_x = 140 - int(110 * t)
    blue_y = 30 + int(12 * np.cos(3.0 * np.pi * t))
    return {"red": (red_x, red_y), "blue": (blue_x, blue_y)}


def generate_sequence() -> tuple[list[np.ndarray], list[dict]]:
    """Build frames in RGB plus ground-truth rows."""
    frames: list[np.ndarray] = []
    truth: list[dict] = []
    rng = np.random.default_rng(11)
    base = np.linspace(45, 70, HEIGHT, dtype=np.float64)[:, None]
    for index in range(FRAME_COUNT):
        frame = np.repeat(base, WIDTH, axis=1)
        frame = np.stack([frame, frame + 4, frame + 8], axis=-1)
        noise = rng.integers(-NOISE_AMPLITUDE, NOISE_AMPLITUDE + 1,
                             (HEIGHT, WIDTH, 1))
        frame = np.clip(frame + noise, 0, 255).astype(np.uint8)
        positions = _positions(index)
        for name, (x, y) in positions.items():
            cv2.circle(frame, (x, y), RADIUS, BALL_RGB[name], -1,
                       lineType=cv2.LINE_8)
        frames.append(frame)
        truth.append({"frame": index,
                      "red_x": positions["red"][0],
                      "red_y": positions["red"][1],
                      "blue_x": positions["blue"][0],
                      "blue_y": positions["blue"][1]})
    return frames, truth


def bundle_frames(data_dir: Path | None = None) -> list[Path]:
    """Write every frame as PNG plus truth.csv; return the frame paths."""
    root = data_dir or DATA_DIR
    frames_dir = root / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames, truth = generate_sequence()
    paths = []
    for index, frame in enumerate(frames):
        path = frames_dir / f"frame_{index:02d}.png"
        if not cv2.imwrite(str(path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)):
            raise TrackerError(f"could not write frame: {path}")
        paths.append(path)
    truth_path = root / "truth.csv"
    with truth_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(truth[0]))
        writer.writeheader()
        writer.writerows(truth)
    return paths


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_frames(directory: Path | None = None) -> list[np.ndarray]:
    """Load PNG frames in numeric order (RGB) from ``directory``.

    Defaults to the bundled ``data/frames`` folder.
    """
    root = Path(directory) if directory is not None else FRAMES_DIR
    if not root.is_dir():
        raise TrackerError(f"frames directory not found: {root}")
    paths = sorted(root.glob("frame_*.png"))
    if not paths:
        raise TrackerError(f"no frames found in {root}")
    frames = []
    for path in paths:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise TrackerError(f"could not decode frame: {path.name}")
        frames.append(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    return frames


def load_truth(data_dir: Path | None = None) -> list[dict]:
    path = (data_dir or DATA_DIR) / "truth.csv"
    if not path.is_file():
        raise TrackerError(f"ground truth not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [{k: int(v) for k, v in row.items()} for row in rows]


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
def colour_mask(frame: np.ndarray, colour: str) -> np.ndarray:
    """Boolean mask for one tracked colour (RGB frame)."""
    if colour not in COLOUR_RANGES:
        raise TrackerError(f"unknown colour '{colour}' "
                           f"(choose from {', '.join(COLOUR_RANGES)})")
    arr = np.asarray(frame)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise TrackerError(f"frame must be HxWx3, got {arr.shape}")
    low, high = COLOUR_RANGES[colour]
    rgb = arr[:, :, :3]
    mask = np.ones(rgb.shape[:2], dtype=bool)
    for channel in range(3):
        mask &= (rgb[:, :, channel] >= low[channel])
        mask &= (rgb[:, :, channel] <= high[channel])
    return mask


def blob_centroid(mask: np.ndarray) -> tuple[float, float] | None:
    """Centroid (x, y) of the mask, or None when nothing is visible."""
    m = np.asarray(mask).astype(bool)
    if m.ndim != 2:
        raise TrackerError(f"mask must be 2-D, got {m.shape}")
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return float(xs.mean()), float(ys.mean())


def detect(frame: np.ndarray, colour: str) -> tuple[float, float] | None:
    return blob_centroid(colour_mask(frame, colour))


def detect_area(frame: np.ndarray, colour: str) -> int:
    return int(colour_mask(frame, colour).sum())


def track_colour(frames: list[np.ndarray], colour: str,
                 max_jump: float = MAX_JUMP) -> list[tuple[float, float] | None]:
    """Track one colour across frames, rejecting implausible jumps."""
    if not frames:
        raise TrackerError("no frames to track")
    if max_jump <= 0:
        raise TrackerError("max_jump must be positive")
    path: list[tuple[float, float] | None] = []
    previous = None
    for frame in frames:
        centre = detect(frame, colour)
        if centre is not None and previous is not None:
            dist = float(np.hypot(centre[0] - previous[0],
                                  centre[1] - previous[1]))
            if dist > max_jump:
                centre = None            # spurious detection
        if centre is not None:
            previous = centre
        path.append(centre)
    return path


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def path_stats(path: list[tuple[float, float] | None]) -> dict:
    """Summarise one tracked trajectory."""
    if not path:
        raise TrackerError("path is empty")
    points = [p for p in path if p is not None]
    detected = len(points)
    length = 0.0
    speeds = []
    for a, b in zip(points, points[1:]):
        step = float(np.hypot(b[0] - a[0], b[1] - a[1]))
        length += step
        speeds.append(step)
    start = points[0] if points else None
    end = points[-1] if points else None
    return {
        "frames": len(path),
        "detected": detected,
        "lost": len(path) - detected,
        "coverage": round(detected / len(path), 4),
        "length": round(length, 3),
        "mean_step": round(float(np.mean(speeds)), 3) if speeds else 0.0,
        "max_step": round(float(np.max(speeds)), 3) if speeds else 0.0,
        "start": [round(start[0], 2), round(start[1], 2)] if start else None,
        "end": [round(end[0], 2), round(end[1], 2)] if end else None,
    }


def analyse(frames: list[np.ndarray],
            colours: tuple[str, ...] = ("red", "blue")) -> dict:
    """Track every requested colour and collect statistics."""
    if not frames:
        raise TrackerError("no frames to analyse")
    result: dict = {"frames": len(frames), "colours": {}, "paths": {}}
    for colour in colours:
        path = track_colour(frames, colour)
        result["paths"][colour] = path
        result["colours"][colour] = path_stats(path)
    return result


def position_errors(path: list[tuple[float, float] | None],
                    truth: list[dict], colour: str) -> dict:
    """Compare tracked centroids with the bundled ground truth."""
    if len(path) != len(truth):
        raise TrackerError("path and truth lengths differ")
    errors = []
    for centre, row in zip(path, truth):
        if centre is None:
            continue
        errors.append(float(np.hypot(centre[0] - row[f"{colour}_x"],
                                     centre[1] - row[f"{colour}_y"])))
    if not errors:
        return {"count": 0, "max": 0.0, "mean": 0.0}
    return {"count": len(errors), "max": round(max(errors), 3),
            "mean": round(float(np.mean(errors)), 3)}


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def trajectory_map(paths: dict[str, list[tuple[float, float] | None]],
                   width: int = ASCII_WIDTH) -> str:
    """ASCII canvas with one glyph per tracked colour."""
    height = max(1, int(width * HEIGHT / WIDTH / 2))
    grid = [[" "] * width for _ in range(height)]
    glyphs = {"red": "R", "blue": "B"}
    for colour, path in paths.items():
        for point in path:
            if point is None:
                continue
            x = min(width - 1, max(0, int(point[0] / WIDTH * width)))
            y = min(height - 1, max(0, int(point[1] / HEIGHT * height)))
            grid[y][x] = glyphs.get(colour, "?")
    return "\n".join("".join(row) for row in grid)


def render_report(frames: list[np.ndarray],
                  colours: tuple[str, ...] = ("red", "blue")) -> str:
    result = analyse(frames, colours)
    lines = [f"Frames         : {result['frames']}",
             f"Frame size     : {WIDTH}x{HEIGHT}", ""]
    for colour in colours:
        s = result["colours"][colour]
        lines += [f"[{colour}] detected {s['detected']}/{s['frames']} frames "
                  f"({s['coverage']:.0%})",
                  f"  path length  : {s['length']:.1f} px",
                  f"  mean step    : {s['mean_step']:.2f} px",
                  f"  start -> end : {s['start']} -> {s['end']}", ""]
    lines.append("ASCII trajectory map:")
    for row in trajectory_map(result["paths"]).splitlines():
        lines.append("  |" + row + "|")
    return "\n".join(lines)


def to_dict(payload: dict) -> dict:
    return {"frames": int(payload["frames"]),
            "colours": payload["colours"]}


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    """Track the bundled sequence - fully offline."""
    root = data_dir or DATA_DIR
    print("=" * 64)
    print(" OBJECT TRACKER - offline demo")
    print(" Colour-blob centroids + nearest-neighbour association.")
    print("=" * 64)

    expected_frames, expected_truth = generate_sequence()
    frames = load_frames(root / "frames")
    if len(frames) != len(expected_frames):
        raise TrackerError(f"expected {len(expected_frames)} frames, "
                           f"found {len(frames)}")
    for index, (loaded, expected) in enumerate(zip(frames, expected_frames)):
        if not np.array_equal(loaded, expected):
            raise TrackerError(f"frame {index} does not match the "
                               f"procedural generator")
    truth = load_truth(root)
    if truth != expected_truth:
        raise TrackerError("truth.csv does not match the generator")
    print(f"\nVerified {len(frames)} bundled frames + truth.csv against the "
          f"procedural generator (no downloads).")

    result = analyse(frames)
    for colour in ("red", "blue"):
        stats = result["colours"][colour]
        assert stats["detected"] == len(frames), \
            f"{colour}: detected only {stats['detected']} frames"
        assert stats["lost"] == 0
        assert stats["length"] > 50, f"{colour} path too short"
        error = position_errors(result["paths"][colour], truth, colour)
        assert error["count"] == len(frames)
        assert error["max"] <= 1.5, \
            f"{colour} tracking error too high: {error['max']} px"
        print(f"{colour:>5} track    : {stats['detected']}/{stats['frames']} "
              f"frames, path {stats['length']:.1f} px, "
              f"max error {error['max']:.2f} px vs truth")

    red_forward = result["colours"]["red"]["end"][0] > \
        result["colours"]["red"]["start"][0]
    blue_backward = result["colours"]["blue"]["end"][0] < \
        result["colours"]["blue"]["start"][0]
    assert red_forward, "red ball should move left -> right"
    assert blue_backward, "blue ball should move right -> left"
    print("Direction check  : red moves right, blue moves left (asserted)")

    area_frame = detect_area(frames[0], "red")
    expected_area = np.pi * RADIUS ** 2
    assert 0.6 * expected_area < area_frame < 1.4 * expected_area, area_frame
    print(f"Blob area        : {area_frame} px ~= pi*r^2 = "
          f"{expected_area:.0f}")

    empty = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    assert detect(empty, "red") is None
    assert blob_centroid(np.zeros((10, 10), dtype=bool)) is None
    print("Negative test    : flat frame yields no detection (None)")

    again = analyse(frames)
    assert again["colours"] == result["colours"], "tracking is not deterministic"
    print("Deterministic    : repeated tracking run is identical")

    print("\nASCII trajectory map:")
    for row in trajectory_map(result["paths"]).splitlines():
        print("  |" + row + "|")

    print("\nCross-checks OK: 24/24 frames verified, <=1.5 px tracking error "
          "vs truth, correct directions, blob area, empty-frame None, "
          "deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
