"""Morphological image processing from scratch - fully offline.

Binary morphology is set arithmetic on pixel neighbourhoods: a
structuring element decides which neighbour configurations matter, and
two operations decide everything else.

* ``dilate`` grows the foreground (set union over the reflected element);
* ``erode`` shrinks it (set intersection over the reflected element).

Composing them gives the four classic filters - opening, closing,
morphological gradient, top-hat and black-hat - and those give the
practical tools used here: salt-and-pepper removal, hole filling,
boundary extraction, connected-component labelling and skeletonisation.

Only NumPy + Pillow - no OpenCV, no scipy, no skimage, no network.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image

LOG = logging.getLogger("morph")

SE_SHAPES = ("square", "cross", "disk", "diamond", "rect")
BORDER_MODES = ("background", "replicate")
OPERATIONS = ("erode", "dilate", "open", "close", "gradient", "boundary",
              "tophat", "blackhat", "clean")
MAX_DIM = 512
MIN_DIM = 8


class MorphError(RuntimeError):
    """Raised for missing files, bad images and invalid morphology inputs."""


# --------------------------------------------------------------------------- #
# Image loading / saving / ASCII preview
# --------------------------------------------------------------------------- #
def load_image(path: str | Path) -> np.ndarray:
    """Load a PNG/JPEG as a 2D uint8 array (RGB is converted to grey)."""
    source = Path(path)
    if not source.is_file():
        raise MorphError(f"file not found: {source}")
    try:
        with Image.open(source) as handle:
            array = np.asarray(handle.convert("L"), dtype=np.uint8)
    except MorphError:
        raise
    except Exception as exc:
        raise MorphError(f"could not read image {source.name}: {exc}") from exc
    if array.ndim != 2:
        raise MorphError(f"expected a 2D greyscale image, got {array.ndim}D")
    height, width = array.shape
    if height < MIN_DIM or width < MIN_DIM:
        raise MorphError(f"image too small: {height}x{width} "
                         f"(need >= {MIN_DIM}x{MIN_DIM})")
    if height > MAX_DIM or width > MAX_DIM:
        raise MorphError(f"image too large: {height}x{width} "
                         f"(max {MAX_DIM}x{MAX_DIM})")
    return array


def save_image(array: np.ndarray, path: str | Path) -> Path:
    """Write an array as a PNG (True -> 255, False -> 0); makes parents."""
    image = np.asarray(array)
    if image.ndim != 2:
        raise MorphError(f"expected a 2D array to save, got {image.ndim}D")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if image.dtype == bool:
        grey = np.where(image, 255, 0).astype(np.uint8)
    else:
        grey = np.clip(np.rint(image.astype(np.float64)), 0, 255).astype(np.uint8)
    Image.fromarray(grey).save(target)
    return target


def ascii_thumb(mask: np.ndarray, cols: int = 48) -> str:
    """Down-sample a binary mask to fixed-width ASCII art (2:1 aspect)."""
    array = np.asarray(mask)
    if array.ndim != 2 or array.size == 0:
        raise MorphError("ascii_thumb needs a non-empty 2D array")
    if cols < 4:
        raise MorphError(f"cols must be >= 4, got {cols}")
    height, width = array.shape
    scale = max(width / cols, height / (cols // 2), 1.0)
    out_w = max(int(round(width / scale)), 1)
    out_h = max(int(round(height / scale)), 1)
    ys = np.clip(np.round(np.linspace(0, height - 1, out_h)).astype(int),
                 0, height - 1)
    xs = np.clip(np.round(np.linspace(0, width - 1, out_w)).astype(int),
                 0, width - 1)
    small = array[ys][:, xs].astype(bool)
    return "\n".join("".join("#" if value else "." for value in row)
                     for row in small)


# --------------------------------------------------------------------------- #
# Mask validation and thresholding
# --------------------------------------------------------------------------- #
def _as_mask(mask: np.ndarray, label: str = "mask") -> np.ndarray:
    """Validate a 2D array and return it as bool."""
    array = np.asarray(mask)
    if array.ndim != 2:
        raise MorphError(f"{label} must be a 2D array, got {array.ndim}D")
    if array.size == 0:
        raise MorphError(f"{label} must not be empty")
    if max(array.shape) > MAX_DIM:
        raise MorphError(f"{label} is {array.shape[0]}x{array.shape[1]}, "
                         f"max is {MAX_DIM}")
    return array != 0


def threshold(image: np.ndarray, level: int = 128) -> np.ndarray:
    """Binarise an image: pixels strictly above `level` become foreground."""
    array = np.asarray(image)
    if array.ndim != 2:
        raise MorphError(f"expected a 2D image, got {array.ndim}D")
    if array.size == 0:
        raise MorphError("image must not be empty")
    if isinstance(level, bool) or not isinstance(level, (int, np.integer)):
        raise MorphError(f"threshold level must be an integer, got {level!r}")
    value = int(level)
    if not 0 <= value <= 255:
        raise MorphError(f"threshold level must be in [0, 255], got {value}")
    return array.astype(np.float64) > value


def invert(mask: np.ndarray) -> np.ndarray:
    """Swap foreground and background."""
    return ~_as_mask(mask)


def area(mask: np.ndarray) -> int:
    """Number of foreground pixels."""
    return int(_as_mask(mask).sum())


def fraction(mask: np.ndarray) -> float:
    """Foreground share of the whole frame, in [0, 1]."""
    array = _as_mask(mask)
    return float(array.sum()) / float(array.size)


# --------------------------------------------------------------------------- #
# Structuring elements
# --------------------------------------------------------------------------- #
def _check_odd_size(size: int, label: str = "size") -> int:
    if isinstance(size, bool) or not isinstance(size, (int, np.integer)):
        raise MorphError(f"{label} must be an integer, got {size!r}")
    value = int(size)
    if value < 1:
        raise MorphError(f"{label} must be >= 1, got {value}")
    if value % 2 == 0:
        raise MorphError(f"{label} must be odd, got {value}")
    if value > 2 * MAX_DIM + 1:
        raise MorphError(f"{label} must be <= {2 * MAX_DIM + 1}, got {value}")
    return value


def square_se(size: int = 3) -> np.ndarray:
    """All-ones size x size block (the default erosion element)."""
    size = _check_odd_size(size)
    return np.ones((size, size), dtype=bool)


def cross_se(size: int = 3) -> np.ndarray:
    """Plus shape: full middle row plus full middle column."""
    size = _check_odd_size(size)
    element = np.zeros((size, size), dtype=bool)
    middle = size // 2
    element[middle, :] = True
    element[:, middle] = True
    return element


def disk_se(radius: int = 1) -> np.ndarray:
    """Digital disk of the given radius (radius 1 -> the plus shape).

    The threshold is ``r^2 + r/2``, so radius 1 selects the four direct
    neighbours but not the diagonals, and radius 2 includes (2, 1) but
    not (2, 2) - the usual integer approximation of a Euclidean ball.
    """
    if isinstance(radius, bool) or not isinstance(radius, (int, np.integer)):
        raise MorphError(f"radius must be an integer, got {radius!r}")
    value = int(radius)
    if value < 0:
        raise MorphError(f"radius must be >= 0, got {value}")
    if value > MAX_DIM:
        raise MorphError(f"radius must be <= {MAX_DIM}, got {value}")
    offset = np.arange(-value, value + 1, dtype=np.float64)
    rows, cols = np.meshgrid(offset, offset, indexing="ij")
    limit = value * value + value / 2.0
    return (rows * rows + cols * cols) <= limit


def diamond_se(radius: int = 1) -> np.ndarray:
    """Manhattan (L1) ball: |dr| + |dc| <= radius."""
    if isinstance(radius, bool) or not isinstance(radius, (int, np.integer)):
        raise MorphError(f"radius must be an integer, got {radius!r}")
    value = int(radius)
    if value < 0:
        raise MorphError(f"radius must be >= 0, got {value}")
    if value > MAX_DIM:
        raise MorphError(f"radius must be <= {MAX_DIM}, got {value}")
    offset = np.arange(-value, value + 1, dtype=np.int64)
    rows, cols = np.meshgrid(offset, offset, indexing="ij")
    return (np.abs(rows) + np.abs(cols)) <= value


def rect_se(height: int = 3, width: int = 5) -> np.ndarray:
    """Rectangular element with independent odd height and width."""
    height = _check_odd_size(height, "height")
    width = _check_odd_size(width, "width")
    return np.ones((height, width), dtype=bool)


def structuring_element(shape: str = "square", size: int = 3,
                        radius: int = 1) -> np.ndarray:
    """Build a named structuring element."""
    if not isinstance(shape, str):
        raise MorphError(f"shape must be a string, got {shape!r}")
    name = shape.strip().lower()
    if name not in SE_SHAPES:
        raise MorphError(f"unknown shape {shape!r} "
                         f"(choose from {', '.join(SE_SHAPES)})")
    if name == "square":
        return square_se(size)
    if name == "cross":
        return cross_se(size)
    if name == "disk":
        return disk_se(radius)
    if name == "diamond":
        return diamond_se(radius)
    return rect_se(size, size)


def describe_se(element: np.ndarray) -> str:
    """One-line description of a structuring element for reports."""
    array = _as_se(element)
    rows, cols = array.shape
    return f"{rows}x{cols}, {int(array.sum())} active pixel(s)"


def _as_se(element: np.ndarray) -> np.ndarray:
    array = np.asarray(element)
    if array.ndim != 2:
        raise MorphError(f"structuring element must be 2D, got {array.ndim}D")
    if array.size == 0:
        raise MorphError("structuring element must not be empty")
    if array.shape[0] % 2 == 0 or array.shape[1] % 2 == 0:
        raise MorphError(f"structuring element must have odd dimensions, "
                         f"got {array.shape[0]}x{array.shape[1]}")
    if max(array.shape) > MAX_DIM + 1:
        raise MorphError(f"structuring element is too large: "
                         f"{array.shape[0]}x{array.shape[1]}")
    mask = array.astype(bool)
    if not mask.any():
        raise MorphError("structuring element must contain at least one pixel")
    return mask


def _validate_mode(mode: str) -> str:
    if mode not in BORDER_MODES:
        raise MorphError(f"unknown border mode {mode!r} "
                         f"(choose from {', '.join(BORDER_MODES)})")
    return mode


# --------------------------------------------------------------------------- #
# The two primitive operations
# --------------------------------------------------------------------------- #
def _morph(mask: np.ndarray, element: np.ndarray, mode: str,
           reduce: Callable[..., np.ndarray], neutral: bool) -> np.ndarray:
    """Shared engine: select the element's cells, then any()/all() them.

    Cells outside a non-rectangular element must contribute ``neutral``
    (False for a union, True for an intersection), otherwise a cross or a
    disk would behave exactly like its bounding box.
    """
    array = _as_mask(mask)
    se = _as_se(element)
    _validate_mode(mode)
    rows, cols = se.shape
    top, left = rows // 2, cols // 2
    bottom, right = rows - 1 - top, cols - 1 - left

    pad_mode = "constant" if mode == "background" else "edge"
    padded = np.pad(array, ((top, bottom), (left, right)), mode=pad_mode)
    windows = np.lib.stride_tricks.sliding_window_view(padded, se.shape)
    selected = np.where(se, windows, neutral)
    hits = selected.reshape(windows.shape[0], windows.shape[1], -1)
    return reduce(hits, axis=2)


def dilate(mask: np.ndarray, element: np.ndarray,
           mode: str = "background") -> np.ndarray:
    """Foreground if ANY window pixel covered by the element is foreground."""
    return _morph(mask, element, mode, np.any, False)


def erode(mask: np.ndarray, element: np.ndarray,
          mode: str = "background") -> np.ndarray:
    """Foreground only where EVERY window pixel under the element is on."""
    return _morph(mask, element, mode, np.all, True)


# --------------------------------------------------------------------------- #
# Composite operations
# --------------------------------------------------------------------------- #
def _on_canvas(mask: np.ndarray, element: np.ndarray,
               operation: Callable[[np.ndarray, np.ndarray], np.ndarray]
               ) -> np.ndarray:
    """Run an operation on a background-extended canvas, then crop.

    Everything outside the image is background, so a composite operation
    must be allowed to *look* outside it: without the canvas, closing
    would trim the outermost foreground ring instead of extending the
    foreground, and ``closing(A) >= A`` would fail at the border.
    """
    array = _as_mask(mask)
    se = _as_se(element)
    pad_rows, pad_cols = se.shape[0] // 2, se.shape[1] // 2
    canvas = np.pad(array, ((pad_rows, pad_rows), (pad_cols, pad_cols)),
                    mode="constant", constant_values=False)
    grown = operation(canvas, se)
    return grown[pad_rows:pad_rows + array.shape[0],
                 pad_cols:pad_cols + array.shape[1]]


def opening(mask: np.ndarray, element: np.ndarray,
            mode: str = "background") -> np.ndarray:
    """Erode then dilate: removes specks smaller than the element."""
    _validate_mode(mode)
    return _on_canvas(mask, element,
                      lambda canvas, se: dilate(erode(canvas, se, mode),
                                                se, mode))


def closing(mask: np.ndarray, element: np.ndarray,
            mode: str = "background") -> np.ndarray:
    """Dilate then erode: fills holes smaller than the element."""
    _validate_mode(mode)
    return _on_canvas(mask, element,
                      lambda canvas, se: erode(dilate(canvas, se, mode),
                                               se, mode))


def clear_border(mask: np.ndarray) -> np.ndarray:
    """Zero the outermost pixel ring (pads are artefacts, not content)."""
    array = _as_mask(mask).copy()
    if array.shape[0] > 2 and array.shape[1] > 2:
        array[0, :] = array[-1, :] = False
        array[:, 0] = array[:, -1] = False
    return array


def boundary(mask: np.ndarray, element: np.ndarray | None = None,
             mode: str = "background") -> np.ndarray:
    """Inner boundary: foreground minus its erosion."""
    array = _as_mask(mask)
    se = square_se(3) if element is None else _as_se(element)
    return array & ~erode(array, se, mode)


def morphological_gradient(mask: np.ndarray, element: np.ndarray | None = None,
                           mode: str = "background") -> np.ndarray:
    """Dilation minus erosion: a two-sided edge band."""
    array = _as_mask(mask)
    se = square_se(3) if element is None else _as_se(element)
    return dilate(array, se, mode) & ~erode(array, se, mode)


def top_hat(mask: np.ndarray, element: np.ndarray,
            mode: str = "background") -> np.ndarray:
    """Foreground detail removed by opening (small protrusions)."""
    array = _as_mask(mask)
    return array & ~opening(array, element, mode)


def black_hat(mask: np.ndarray, element: np.ndarray,
              mode: str = "background") -> np.ndarray:
    """Background detail added by closing (small holes and notches)."""
    array = _as_mask(mask)
    return closing(array, element, mode) & ~array


def clean(mask: np.ndarray, element: np.ndarray,
          mode: str = "background") -> np.ndarray:
    """Opening then closing: removes salt specks, then fills pepper holes."""
    return closing(opening(mask, element, mode), element, mode)


OPERATION_FUNCTIONS = {
    "erode": lambda mask, se: erode(mask, se),
    "dilate": lambda mask, se: dilate(mask, se),
    "open": lambda mask, se: opening(mask, se),
    "close": lambda mask, se: closing(mask, se),
    "gradient": lambda mask, se: morphological_gradient(mask, se),
    "boundary": lambda mask, se: boundary(mask, se),
    "tophat": lambda mask, se: top_hat(mask, se),
    "blackhat": lambda mask, se: black_hat(mask, se),
    "clean": lambda mask, se: clean(mask, se),
}


def apply_operation(mask: np.ndarray, operation: str,
                    element: np.ndarray | None = None) -> np.ndarray:
    """Apply one named operation (used by the CLI pipeline)."""
    if not isinstance(operation, str):
        raise MorphError(f"operation must be a string, got {operation!r}")
    name = operation.strip().lower()
    if name not in OPERATION_FUNCTIONS:
        raise MorphError(f"unknown operation {operation!r} "
                         f"(choose from {', '.join(OPERATIONS)})")
    se = square_se(3) if element is None else _as_se(element)
    return OPERATION_FUNCTIONS[name](_as_mask(mask), se)


# --------------------------------------------------------------------------- #
# Connected components
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Component:
    """One connected foreground region."""

    label: int
    area: int
    bbox: tuple[int, int, int, int]
    centroid: tuple[float, float]
    touches_border: bool

    @property
    def height(self) -> int:
        return self.bbox[2] - self.bbox[0] + 1

    @property
    def width(self) -> int:
        return self.bbox[3] - self.bbox[1] + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "area": self.area,
            "bbox": list(self.bbox),
            "height": self.height,
            "width": self.width,
            "centroid": [round(self.centroid[0], 3),
                         round(self.centroid[1], 3)],
            "touches_border": self.touches_border,
        }


_NEIGHBOURHOODS = {
    4: ((-1, 0), (1, 0), (0, -1), (0, 1)),
    8: ((-1, 0), (1, 0), (0, -1), (0, 1),
        (-1, -1), (-1, 1), (1, -1), (1, 1)),
}


def label_components(mask: np.ndarray, connectivity: int = 8
                     ) -> tuple[np.ndarray, tuple[Component, ...]]:
    """Flood-fill labelling; returns (labels, components), background = 0."""
    array = _as_mask(mask)
    if isinstance(connectivity, bool) or connectivity not in (4, 8):
        raise MorphError(f"connectivity must be 4 or 8, got {connectivity!r}")
    offsets = _NEIGHBOURHOODS[int(connectivity)]
    height, width = array.shape
    labels = np.zeros((height, width), dtype=np.int32)
    components: list[Component] = []
    next_label = 0

    for start_row in range(height):
        for start_col in range(width):
            if not array[start_row, start_col] or labels[start_row, start_col]:
                continue
            next_label += 1
            labels[start_row, start_col] = next_label
            queue = deque([(start_row, start_col)])
            total = 0
            sum_row = 0
            sum_col = 0
            min_row = max_row = start_row
            min_col = max_col = start_col
            border = False
            while queue:
                row, col = queue.popleft()
                total += 1
                sum_row += row
                sum_col += col
                min_row, max_row = min(min_row, row), max(max_row, row)
                min_col, max_col = min(min_col, col), max(max_col, col)
                if row == 0 or col == 0 or row == height - 1 or col == width - 1:
                    border = True
                for delta_row, delta_col in offsets:
                    next_row = row + delta_row
                    next_col = col + delta_col
                    if (0 <= next_row < height and 0 <= next_col < width
                            and array[next_row, next_col]
                            and not labels[next_row, next_col]):
                        labels[next_row, next_col] = next_label
                        queue.append((next_row, next_col))
            components.append(Component(
                label=next_label,
                area=total,
                bbox=(min_row, min_col, max_row, max_col),
                centroid=(sum_row / total, sum_col / total),
                touches_border=border))
    return labels, tuple(components)


def count_specks(mask: np.ndarray, max_area: int = 4,
                 connectivity: int = 8) -> int:
    """Count foreground components no larger than `max_area` pixels."""
    if isinstance(max_area, bool) or not isinstance(max_area, (int, np.integer)) \
            or max_area < 1:
        raise MorphError(f"max_area must be an integer >= 1, got {max_area!r}")
    _, components = label_components(mask, connectivity)
    return sum(1 for component in components if component.area <= max_area)


def count_holes(mask: np.ndarray, max_area: int = 8,
                connectivity: int = 4) -> int:
    """Count enclosed background islands no larger than `max_area` pixels."""
    if isinstance(max_area, bool) or not isinstance(max_area, (int, np.integer)) \
            or max_area < 1:
        raise MorphError(f"max_area must be an integer >= 1, got {max_area!r}")
    _, components = label_components(~_as_mask(mask), connectivity)
    return sum(1 for component in components
               if component.area <= max_area and not component.touches_border)


def largest_components(mask: np.ndarray, minimum_area: int = 1,
                       connectivity: int = 8) -> tuple[Component, ...]:
    """Components at or above `minimum_area`, biggest first."""
    if isinstance(minimum_area, bool) \
            or not isinstance(minimum_area, (int, np.integer)) \
            or minimum_area < 1:
        raise MorphError(
            f"minimum_area must be an integer >= 1, got {minimum_area!r}")
    _, components = label_components(mask, connectivity)
    keep = [component for component in components
            if component.area >= minimum_area]
    return tuple(sorted(keep, key=lambda item: (-item.area, item.label)))


# --------------------------------------------------------------------------- #
# Thinning
# --------------------------------------------------------------------------- #
def skeleton(mask: np.ndarray, max_iterations: int = 100) -> np.ndarray:
    """Zhang-Suen thinning: reduce a blob to a one-pixel-wide skeleton."""
    array = _as_mask(mask)
    if isinstance(max_iterations, bool) \
            or not isinstance(max_iterations, (int, np.integer)) \
            or max_iterations < 1:
        raise MorphError(
            f"max_iterations must be an integer >= 1, got {max_iterations!r}")
    image = array.astype(np.uint8)
    for _ in range(int(max_iterations)):
        changed = False
        for step in (0, 1):
            padded = np.pad(image, 1)
            p2 = padded[:-2, 1:-1]
            p3 = padded[:-2, 2:]
            p4 = padded[1:-1, 2:]
            p5 = padded[2:, 2:]
            p6 = padded[2:, 1:-1]
            p7 = padded[2:, :-2]
            p8 = padded[1:-1, :-2]
            p9 = padded[:-2, :-2]
            ring = [p2, p3, p4, p5, p6, p7, p8, p9]
            neighbours = sum(ring).astype(np.int16)
            transitions = sum(
                ((ring[index] == 0) & (ring[(index + 1) % 8] == 1)
                 ).astype(np.int16) for index in range(8))
            foreground = image == 1
            candidate = (foreground & (neighbours >= 2) & (neighbours <= 6)
                         & (transitions == 1))
            if step == 0:
                candidate &= (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                candidate &= (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            if candidate.any():
                image[candidate] = 0
                changed = True
        if not changed:
            break
    else:
        LOG.warning("skeleton hit the iteration cap (%d)", max_iterations)
    return image.astype(bool)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def iou(first: np.ndarray, second: np.ndarray) -> float:
    """Intersection over union of two masks (1.0 when both are empty)."""
    a = _as_mask(first, "first mask")
    b = _as_mask(second, "second mask")
    if a.shape != b.shape:
        raise MorphError(f"shape mismatch: {a.shape} vs {b.shape}")
    union = int((a | b).sum())
    if union == 0:
        return 1.0
    return float((a & b).sum()) / float(union)


def perimeter(mask: np.ndarray) -> int:
    """Boundary pixel count using the 3x3 square element."""
    return int(boundary(mask).sum())


def render_report(rows: list[dict[str, Any]], title: str) -> str:
    """Align a list of per-operation metrics into a text table."""
    if not rows:
        raise MorphError("render_report needs at least one row")
    header = (f"{'operation':<12}{'pixels':>9}{'share':>9}"
              f"{'vs input':>11}{'components':>12}")
    lines = [title, "=" * len(title), header, "-" * len(header)]
    for row in rows:
        lines.append(
            f"{row['operation']:<12}{row['pixels']:>9}"
            f"{100.0 * row['share']:>8.2f}%{row['delta']:>+11d}"
            f"{row['components']:>12}")
    return "\n".join(lines)


def _row(name: str, mask: np.ndarray, input_area: int) -> dict[str, Any]:
    pixels = area(mask)
    _, components = label_components(mask)
    return {
        "operation": name,
        "pixels": pixels,
        "share": fraction(mask),
        "delta": pixels - input_area,
        "components": len(components),
    }


NOISY = Path(__file__).resolve().parent.parent / "data" / "noisy_shapes_128.png"
LEVEL = 128


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(image_path: Path | None = None) -> int:
    """Threshold, filter, label and thin the bundled noisy image - offline."""
    print("=" * 74)
    print(" MORPHOLOGICAL PROCESSING - offline demo")
    print(" Erode/dilate/opening/closing, components and thinning, from")
    print(" scratch. No OpenCV, no SciPy, no skimage.")
    print("=" * 74)

    source = image_path or NOISY
    if not source.is_file():
        raise MorphError(f"bundled sample not found: {source}")
    image = load_image(source)
    mask = threshold(image, LEVEL)
    levels = np.unique(image)
    print(f"\nImage   : {source.name} {image.shape[1]}x{image.shape[0]}, "
          f"{len(levels)} grey level(s) "
          f"({int(levels.min())}..{int(levels.max())})")
    print(f"Mask    : {area(mask)} px above level {LEVEL} "
          f"({100.0 * fraction(mask):.2f}% of the frame)")

    # --- algebraic identities, on the real mask --------------------------- #
    se = square_se(3)
    # 1. erosion is dilation on the complement (the SE is symmetric)
    dual = np.array_equal(~dilate(~mask, se), erode(mask, se))
    assert dual, "erosion is not the dual of dilation under complement"

    # 2. opening is anti-extensive and closing is extensive
    opened = opening(mask, se)
    closed = closing(mask, se)
    assert not (opened & ~mask).any(), "opening added foreground"
    assert not (mask & ~closed).any(), "closing removed foreground"

    # 3. opening is idempotent, and so is closing
    assert np.array_equal(opening(opened, se), opened), \
        "opening is not idempotent"
    assert np.array_equal(closing(closed, se), closed), \
        "closing is not idempotent"

    # 4. area is monotone: erode <= input <= dilate
    eroded = erode(mask, se)
    dilated = dilate(mask, se)
    assert area(eroded) <= area(mask) <= area(dilated), \
        "erosion/dilation did not bracket the input area"

    # 5. dilating twice with a 3x3 square == dilating once with a 5x5 square
    probe = np.zeros((40, 40), dtype=bool)
    probe[15:25, 15:25] = True
    stepwise = dilate(dilate(probe, square_se(3)), square_se(3))
    together = dilate(probe, square_se(5))
    assert np.array_equal(stepwise, together), \
        "3x3 + 3x3 dilation != one 5x5 dilation (Minkowski sum)"

    # 6. boundary of an n x n solid square is exactly 4n - 4 pixels
    side = 21
    square = np.zeros((32, 32), dtype=bool)
    square[5:5 + side, 5:5 + side] = True
    ring = int(boundary(square).sum())
    assert ring == 4 * side - 4, f"square boundary {ring} != {4 * side - 4}"

    # 7. the threshold is safe: the image is bimodal, so any level in the
    #    open interval gives the same mask (0 and 255 are the only values)
    for level in (1, 64, 200, 254):
        assert np.array_equal(threshold(image, level), mask), \
            f"threshold level {level} changed a bimodal mask"

    # --- the cleaning pipeline -------------------------------------------- #
    cleaned = clean(mask, se)
    specks_before = count_specks(mask, 4)
    specks_after = count_specks(cleaned, 4)
    holes_before = count_holes(mask, 8)
    holes_after = count_holes(cleaned, 8)
    big_before = largest_components(mask, 500)
    big_after = largest_components(cleaned, 500)

    # 8. opening kills the salt specks (negative control: a 1x1 element is
    #    the identity, so it cannot be the threshold doing the work)
    assert specks_after == 0, f"{specks_after} speck(s) survived cleaning"
    assert specks_before > 0, "the sample has no salt noise to remove"
    assert np.array_equal(opening(mask, np.ones((1, 1), dtype=bool)), mask), \
        "a 1x1 element must be the identity"

    # 9. closing fills pepper holes
    assert holes_after < holes_before, \
        f"closing left {holes_after} hole(s), started with {holes_before}"

    # 10. all three blobs survive, and they now account for the whole
    #     cleaned foreground - i.e. nothing but the shapes is left
    assert len(big_after) == 3, \
        f"expected 3 large shapes after cleaning, got {len(big_after)}"
    assert len(big_before) >= len(big_after), "cleaning created new shapes"
    shape_total = sum(component.area for component in big_after)
    assert shape_total == area(cleaned), (
        f"shapes cover {shape_total} px but the cleaned mask is "
        f"{area(cleaned)} px")

    # 11. opening beats plain erosion for this job: erosion also removes the
    #     specks but eats into the shapes, so opening keeps more foreground
    assert area(eroded) < area(cleaned), (
        f"erosion kept {area(eroded)} px, opening+closing kept "
        f"{area(cleaned)} px")

    rows = [_row(name, result, area(mask)) for name, result in (
        ("input", mask),
        ("erode 3x3", eroded),
        ("dilate 3x3", dilated),
        ("open 3x3", opened),
        ("close 3x3", closed),
        ("gradient", morphological_gradient(mask, se)),
        ("boundary", boundary(mask, se)),
        ("clean", cleaned),
    )]
    print()
    print(render_report(rows, "OPERATIONS - 3x3 square structuring element"))

    print("\nCleaning (opening then closing, 3x3 square)")
    print(f"  salt specks  <=  4 px : {specks_before:>4} -> {specks_after:>4}")
    print(f"  pepper holes <=  8 px : {holes_before:>4} -> {holes_after:>4}")
    print(f"  shapes >= 500 px      : {len(big_before):>4} -> {len(big_after):>4}")

    print("\nLargest components after cleaning (8-connectivity)")
    header = (f"  {'label':>6}{'area':>8}{'height':>8}{'width':>7}"
              f"{'centre row':>12}{'centre col':>12}")
    print(header)
    print("  " + "-" * (len(header) - 2))
    for component in big_after:
        print(f"  {component.label:>6}{component.area:>8}"
              f"{component.height:>8}{component.width:>7}"
              f"{component.centroid[0]:>12.1f}{component.centroid[1]:>12.1f}")

    # --- thinning --------------------------------------------------------- #
    thin = skeleton(cleaned)
    skeleton_area = area(thin)
    # 12. thinning only deletes foreground pixels
    assert not (thin & ~cleaned).any(), "skeleton invented pixels"
    # 13. and it really thins: under a tenth of the cleaned area
    assert skeleton_area * 10 < area(cleaned), \
        f"skeleton kept {skeleton_area} of {area(cleaned)} px"
    # 14. and it preserves connectivity: same number of 8-connected parts
    _, skeleton_parts = label_components(thin, 8)
    assert len(skeleton_parts) == len(big_after), \
        (f"skeleton has {len(skeleton_parts)} part(s), "
         f"cleaned shape has {len(big_after)}")

    print("\nSkeleton (Zhang-Suen thinning)")
    print(f"  cleaned pixels  : {area(cleaned):>6}")
    print(f"  skeleton pixels : {skeleton_area:>6} "
          f"({100.0 * skeleton_area / max(1, area(cleaned)):.1f}%)")
    print(f"  parts preserved : {len(skeleton_parts):>6}")

    print("\nASCII preview (cleaned mask, 64 columns)")
    print(ascii_thumb(cleaned, 64))

    # --- determinism ------------------------------------------------------ #
    assert np.array_equal(clean(mask, se), cleaned), "cleaning is not deterministic"
    assert np.array_equal(skeleton(cleaned), thin), "thinning is not deterministic"

    print(f"\nCross-checks OK: erosion is the dual of dilation, opening is "
          f"anti-extensive and idempotent, closing is extensive and "
          f"idempotent, area is monotone through erode/dilate, 3x3 + 3x3 "
          f"dilation equals one 5x5 dilation, a {side}x{side} square has a "
          f"{ring}-pixel boundary, thresholding is level-invariant on a "
          f"bimodal image, all {specks_before} salt specks are gone (and a "
          f"1x1 element removes nothing), pepper holes fall {holes_before} "
          f"-> {holes_after}, the 3 shapes account for all {shape_total} "
          f"cleaned pixels while plain erosion would have kept only "
          f"{area(eroded)}, the skeleton only deletes pixels, keeps under a "
          f"tenth of the area and preserves all 3 parts, deterministic "
          f"re-run")
    print("Demo completed successfully.")
    return 0
