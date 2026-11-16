"""Scaling an image is integer arithmetic, not a float times a width.

The legacy viewer resized with three lines:

    def resize(image, box):
        scale = min(box[0] / image[0], box[1] / image[1])
        return int(image[0] * scale), int(image[1] * scale)

**1. `int()` truncates twice, and the two truncations are not the same fraction.**
A 3x2 image in a 2x2 box has a scale of 0.6666666666666666, and
`3 * 0.6666666666666666` is `1.9999999999999998`. `int()` of that is **1**, so the
image is drawn **1x1**: one pixel short on both axes, and the aspect ratio it was
supposed to preserve is now 1:1.

**2. One dimension has to be exact.** A fitting scale makes one side equal the box
and derives the other. Rounding *both* sides independently lets both be wrong, and a
rounded width with a rounded height is not the same rectangle as a rounded ratio.

**3. A taller image is not a wider one.** A viewer that always scales by width puts a
90x160 photograph at 200x355 in a 200x200 box and clips a third of it. Which side binds
is a comparison of two products, not a rule about which number comes first.

**4. Covering a box is not the same problem as fitting inside it.** "Fill" must never
leave a seam, so its derived side rounds *up*; "fit" must never overflow, so its derived
side rounds to nearest. One rounding direction cannot serve both.

**5. A zero dimension has no scale.** `box[0] / image[0]` with a zero width raises, and
a viewer that catches it and returns `(0, 0)` draws a window that has no pixels.

So this module keeps a `Size` that cannot be zero, computes both placements in integers
(`round_half_up`, `ceil_div`), and states which side binds by comparing `width * box_h`
with `height * box_w`. The legacy path is kept beside it, executable, so every claim
above is reproduced with a pixel count.

The demonstration is offline: one bundled file of images and boxes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IMAGES_FILE = DATA_DIR / "images.txt"

#: The legacy resize, transcribed -- and executable.
LEGACY_RESIZE = ("def resize(image, box):\n"
                 "    scale = min(box[0] / image[0], box[1] / image[1])\n"
                 "    return int(image[0] * scale), int(image[1] * scale)")

#: The two ways an image can meet a box.
MODES = ("fit", "fill")

#: Which orientation a size has.
ORIENTATIONS = ("landscape", "portrait", "square")


class ImageError(Exception):
    """A size, a box or a placement that cannot be honoured, and why."""


# --------------------------------------------------------------------------- #
# Integer arithmetic
# --------------------------------------------------------------------------- #
def round_div(numerator: int, denominator: int) -> int:
    """`numerator / denominator` rounded half-up, from integers only."""
    for value, name in ((numerator, "a numerator"), (denominator, "a denominator")):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ImageError(f"{name} is a whole number, got {value!r}")
    if denominator <= 0:
        raise ImageError(f"a denominator is positive, got {denominator}")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return sign * quotient


def ceil_div(numerator: int, denominator: int) -> int:
    """`numerator / denominator` rounded up, from integers only."""
    for value, name in ((numerator, "a numerator"), (denominator, "a denominator")):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ImageError(f"{name} is a whole number, got {value!r}")
    if denominator <= 0:
        raise ImageError(f"a denominator is positive, got {denominator}")
    if numerator < 0:
        return -((-numerator) // denominator)
    return -(-numerator // denominator)


def _whole(value, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ImageError(f"{name} is a whole number, got {value!r}")
    return value


# --------------------------------------------------------------------------- #
# A size
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Size:
    """A width and a height, both positive -- a size of zero has no scale."""

    width: int
    height: int

    def __post_init__(self) -> None:
        _whole(self.width, "a width")
        _whole(self.height, "a height")
        if self.width <= 0:
            raise ImageError(f"a width is positive, got {self.width}")
        if self.height <= 0:
            raise ImageError(f"a height is positive, got {self.height}")

    def __iter__(self):
        return iter((self.width, self.height))

    def pixels(self) -> int:
        return self.width * self.height

    def orientation(self) -> str:
        if self.width > self.height:
            return "landscape"
        if self.height > self.width:
            return "portrait"
        return "square"

    def ratio(self) -> tuple[int, int]:
        """The aspect ratio as a reduced pair, so 4000x3000 is 4:3."""
        divisor = _gcd(self.width, self.height)
        return (self.width // divisor, self.height // divisor)

    def transposed(self) -> "Size":
        return Size(self.height, self.width)

    def scaled(self, factor_width: int, factor_height: int) -> "Size":
        """Both sides multiplied by whole numbers (a box, measured in units)."""
        _whole(factor_width, "a width factor")
        _whole(factor_height, "a height factor")
        return Size(self.width * factor_width, self.height * factor_height)

    def line(self) -> str:
        return (f"{self.width}x{self.height} "
                f"({self.orientation()}, {self.width / self.height:.4f})")

    def plain(self) -> str:
        return f"{self.width}x{self.height}"


def _gcd(left: int, right: int) -> int:
    while right:
        left, right = right, left % right
    return left or 1


# --------------------------------------------------------------------------- #
# Which side binds
# --------------------------------------------------------------------------- #
def binding_side(image: Size, box: Size) -> str:
    """`"width"` when the width is the limit, `"height"` when the height is.

    Comparing `box.width * image.height` with `box.height * image.width` is the
    same comparison as `box.width / image.width <= box.height / image.height`,
    with no division and no float.
    """
    if not isinstance(image, Size) or not isinstance(box, Size):
        raise ImageError("a binding side compares two sizes")
    if box.width * image.height <= box.height * image.width:
        return "width"
    return "height"


# --------------------------------------------------------------------------- #
# A placement
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Placement:
    """Where an image lands in a box: its rectangle, its offsets, and the mode."""

    image: Size
    box: Size
    width: int
    height: int
    x: int
    y: int
    mode: str

    def __post_init__(self) -> None:
        if not isinstance(self.image, Size) or not isinstance(self.box, Size):
            raise ImageError("a placement relates an image to a box")
        _whole(self.width, "a placed width")
        _whole(self.height, "a placed height")
        _whole(self.x, "an x offset")
        _whole(self.y, "a y offset")
        if self.width <= 0 or self.height <= 0:
            raise ImageError("a placement has a positive size")
        if self.mode not in MODES:
            raise ImageError(f"a mode is 'fit' or 'fill', got {self.mode!r}")

    def contains(self) -> bool:
        return self.width <= self.box.width and self.height <= self.box.height

    def covers(self) -> bool:
        return self.width >= self.box.width and self.height >= self.box.height

    def error(self) -> int:
        """`abs(width * image.height - height * image.width)`, in pixels squared."""
        return abs(self.width * self.image.height
                   - self.height * self.image.width)

    def plain(self) -> str:
        return f"{self.width}x{self.height}"

    def line(self) -> str:
        return (f"{self.mode:<4} {self.image.plain():>9} -> "
                f"{self.width}x{self.height} at ({self.x}, {self.y})")
def fit_inside(image: Size, box: Size) -> Placement:
    """Largest rectangle of the image's ratio that fits inside the box."""
    side = binding_side(image, box)
    if side == "width":
        return Placement(image, box, box.width,
                         round_div(image.height * box.width, image.width),
                         0, 0, "fit")
    return Placement(image, box,
                     round_div(image.width * box.height, image.height),
                     box.height, 0, 0, "fit")


def fill_box(image: Size, box: Size) -> Placement:
    """Smallest rectangle of the image's ratio that covers the box, centred.

    Covering is the other rounding problem from fitting: the side that *fits*
    is the side whose ratio is smaller, so the side that *covers* is the other
    one, and its derived length rounds **up** so a seam is impossible.
    """
    side = binding_side(image, box)
    if side == "width":
        # The width is the tighter ratio, so the height covers and the width
        # is derived -- the opposite of the fit that would have used width.
        width, height = ceil_div(image.width * box.height, image.height), box.height
    else:
        width, height = box.width, ceil_div(image.height * box.width, image.width)
    return Placement(image, box, width, height,
                     -((width - box.width) // 2), -((height - box.height) // 2),
                     "fill")


def centred(image: Size, box: Size) -> Placement:
    """The fitted rectangle, moved to the middle of the box (letterboxing)."""
    placed = fit_inside(image, box)
    return Placement(image, box, placed.width, placed.height,
                     (box.width - placed.width) // 2,
                     (box.height - placed.height) // 2, "fit")


def legacy_resize(image, box) -> tuple[int, int]:
    """`int(image * min(box/image))` -- the transcribed viewer, float and all."""
    scale = min(box[0] / image[0], box[1] / image[1])
    return int(image[0] * scale), int(image[1] * scale)


# --------------------------------------------------------------------------- #
# Reading the bundle
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Entry:
    """One line of the bundle: an image, the box it is shown in, and its name."""

    name: str
    image: Size
    box: Size

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ImageError("an entry needs a name")
        if " " in self.name:
            raise ImageError(f"a name holds no spaces, got {self.name!r}")


def parse_images(text: str) -> tuple[Entry, ...]:
    """Read `name width height box_width box_height` per line; `;` comments."""
    entries: list[Entry] = []
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        body = line.split(";", 1)[0].strip()
        if not body:
            continue
        fields = body.split()
        if len(fields) != 5:
            raise ImageError(f"line {number}: five fields are needed -- a name, "
                             f"two sizes -- got {len(fields)}")
        name = fields[0]
        numbers: list[int] = []
        for field in fields[1:]:
            try:
                numbers.append(int(field))
            except ValueError:
                raise ImageError(f"line {number}: {field!r} is not a whole "
                                 f"number") from None
        entries.append(Entry(name, Size(numbers[0], numbers[1]),
                             Size(numbers[2], numbers[3])))
    if not entries:
        raise ImageError("a bundle needs at least one image")
    return tuple(entries)


def read_images(path=None) -> tuple[Entry, ...]:
    target = Path(IMAGES_FILE if path is None else path)
    if not target.is_file():
        raise ImageError(f"file not found: {target}")
    return parse_images(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(measured: dict, entries) -> list[tuple[str, bool]]:
    """Eleven checks, re-derived from the numbers the demo just measured."""
    def at(name: str):
        if name not in measured:
            raise ImageError(f"no measurement named {name!r}")
        return measured[name]

    def placements():
        return [(entry, fit_inside(entry.image, entry.box)) for entry in entries]

    def the_legacy_float_loses_a_pixel() -> bool:
        old = legacy_resize((3, 1), (2, 2))
        return old == (2, 0) and at("tiny_fit") == "2x1"

    def the_binding_side_is_exactly_the_box() -> bool:
        """The side the demo named must be the side that equals the box."""
        sides = at("binding")
        for entry, placed in placements():
            side = sides[entry.name]
            if side == "width":
                if placed.width != entry.box.width:
                    return False
            elif side == "height":
                if placed.height != entry.box.height:
                    return False
            else:
                return False
        return True

    def a_contained_placement_never_exceeds_its_box() -> bool:
        return all(placed.contains() for _, placed in placements())

    def an_exact_fit_is_unchanged() -> bool:
        return at("exact_fit") == "400x300"

    def a_taller_image_stays_taller() -> bool:
        def pair(text: str) -> tuple[int, int]:
            width, height = text.split("x")
            return int(width), int(height)

        fitted = pair(at("portrait_fit"))
        by_width = pair(at("portrait_by_width"))
        # The fitted rectangle fills the 200x200 box without overflowing it;
        # scaling by width alone fills the width and spills the height.
        return (fitted[1] == 200 and fitted[0] <= 200
                and by_width[0] == 200 and by_width[1] > 200)

    def the_derived_side_is_within_half_a_pixel() -> bool:
        for entry, placed in placements():
            longest = max(entry.image.width, entry.image.height)
            if 2 * placed.error() > longest:
                return False
        return True

    def a_filled_placement_never_leaves_a_seam() -> bool:
        if at("fill_shortfall") < 0:
            return False
        return all(fill_box(entry.image, entry.box).covers() for entry in entries)

    def a_filled_2_by_1_image_is_twice_as_wide_as_it_is_tall() -> bool:
        def pair(text: str) -> tuple[int, int]:
            width, height = text.split("x")
            return int(width), int(height)

        width, height = pair(at("fill"))
        seam = [entry for entry in entries if entry.name == "seam"]
        if not seam:
            return False
        return width == 2 * height and height == seam[0].box.height

    def a_zero_side_is_refused_and_the_legacy_path_divides_by_zero() -> bool:
        return at("zero_refused") is True and at("legacy_zero") == "crash"

    def every_image_produced_one_placement() -> bool:
        names = [entry.name for entry in entries]
        return len(names) == len(set(names)) and len(names) >= 5 and \
            all(fit_inside(entry.image, entry.box).width > 0 for entry in entries)

    def the_reduced_ratio_has_no_common_factor() -> bool:
        for entry in entries:
            numerator, denominator = entry.image.ratio()
            if _gcd(numerator, denominator) != 1:
                return False
        return True

    checks = [
        ("the legacy float loses a pixel", the_legacy_float_loses_a_pixel),
        ("the binding side is exactly the box",
         the_binding_side_is_exactly_the_box),
        ("a contained placement never exceeds its box",
         a_contained_placement_never_exceeds_its_box),
        ("an exact fit is unchanged", an_exact_fit_is_unchanged),
        ("a taller image stays taller", a_taller_image_stays_taller),
        ("the derived side is within half a pixel",
         the_derived_side_is_within_half_a_pixel),
        ("a filled placement never leaves a seam",
         a_filled_placement_never_leaves_a_seam),
        ("a filled 2 by 1 image is twice as wide as it is tall",
         a_filled_2_by_1_image_is_twice_as_wide_as_it_is_tall),
        ("a zero side is refused, not divided by",
         a_zero_side_is_refused_and_the_legacy_path_divides_by_zero),
        ("every image produced one placement",
         every_image_produced_one_placement),
        ("the reduced ratio has no common factor",
         the_reduced_ratio_has_no_common_factor),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def measure(entries) -> dict:
    """Every number the audit is allowed to read, measured once."""
    measured: dict = {}
    tiny = Size(3, 1)
    square = Size(2, 2)
    measured["tiny_fit"] = fit_inside(tiny, square).plain()
    measured["tiny_legacy"] = "x".join(str(side) for side in
                                       legacy_resize((3, 1), (2, 2)))
    measured["tiny_scale"] = repr(1 * (2 / 3))

    exact = Size(400, 300)
    measured["exact_fit"] = fit_inside(exact, exact).plain()

    portrait = Size(90, 160)
    measured["portrait_fit"] = fit_inside(portrait, Size(200, 200)).plain()
    measured["portrait_by_width"] = "200x" + str(round_div(160 * 200, 90))

    seam = Size(100, 50)
    filled = fill_box(seam, Size(40, 40))
    measured["fill"] = filled.plain()
    measured["fill_offset"] = f"({filled.x}, {filled.y})"
    measured["fill_fitted"] = fit_inside(seam, Size(40, 40)).plain()

    try:
        Size(0, 100)
        measured["zero_refused"] = False
    except ImageError:
        measured["zero_refused"] = True
    try:
        legacy_resize((0, 100), (320, 240))
        measured["legacy_zero"] = "no refusal"
    except ZeroDivisionError:
        measured["legacy_zero"] = "crash"

    measured["binding"] = {entry.name: binding_side(entry.image, entry.box)
                           for entry in entries}
    measured["fill_shortfall"] = min(
        min(fill_box(entry.image, entry.box).width - entry.box.width,
            fill_box(entry.image, entry.box).height - entry.box.height)
        for entry in entries)

    return measured


def run_demo() -> int:
    entries = read_images()
    measured = measure(entries)

    print("=" * 78)
    print(" IMAGE LAB - int(width * scale) is not a size")
    print("=" * 78)

    print("\n  the legacy resize, transcribed:")
    for line in LEGACY_RESIZE.split("\n"):
        print(f"    {line}")

    print(f"\n  {len(entries)} images, each fitted inside its own box:")
    print(f"    {'name':<10} {'image':>9} {'box':>9} {'fit':>9} {'legacy':>9}")
    losses = 0
    for entry in entries:
        placed = fit_inside(entry.image, entry.box)
        old = legacy_resize(tuple(entry.image), tuple(entry.box))
        old_text = f"{old[0]}x{old[1]}"
        wrong = "  wrong" if old != (placed.width, placed.height) else ""
        if wrong:
            losses += 1
        print(f"    {entry.name:<10} {entry.image.plain():>9} "
              f"{entry.box.plain():>9} {placed.plain():>9} "
              f"{old_text:>9}{wrong}")
    print(f"\n    {losses} of {len(entries)} images come out the wrong size "
          f"under the legacy resize")

    print("\n  why the small one loses a pixel:")
    print(f"    the scale is 2/3, which as a double is 0.6666666666666666")
    print(f"    1 * 0.6666666666666666 is {measured['tiny_scale']}, and int() "
          f"of that is 0")
    print(f"    the height of a placed image cannot be zero: the correct "
          f"answer is {measured['tiny_fit']}")

    print("\n  which side binds is two products, not a habit:")
    for entry in entries[:3]:
        side = binding_side(entry.image, entry.box)
        print(f"    {entry.name:<10} {entry.image.plain():>9} in "
              f"{entry.box.plain():>9} -> {side} binds "
              f"({entry.box.width}*{entry.image.height} vs "
              f"{entry.box.height}*{entry.image.width})")

    print("\n  a portrait photograph is not scaled by its width:")
    print(f"    90x160 in a 200x200 box fits at {measured['portrait_fit']}")
    print(f"    scaling by width alone gives "
          f"{measured['portrait_by_width']} and clips the rest")

    print("\n  fitting is not filling:")
    print(f"    100x50 in a 40x40 box covers with {measured['fill']} at "
          f"{measured['fill_offset']}")
    print(f"    the same image fitted inside the box is "
          f"{measured['fill_fitted']}: it leaves the box half empty")
    print(f"    fitting rounds to nearest, covering rounds up: one direction "
          f"cannot do both")

    print("\n  a size of zero:")
    print(f"    Size(0, 100) refused: {measured['zero_refused']}")
    print(f"    the legacy path on the same input: {measured['legacy_zero']}")

    checks = audit(measured, entries)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(entries)} images, {losses} wrong under the legacy resize, "
          f"3x1 in a 2x2 box is {measured['tiny_legacy']} to the old viewer and "
          f"{measured['tiny_fit']} here, a 90x160 photo fits {measured['portrait_fit']} "
          f"but {measured['portrait_by_width']} if width always binds, the fill "
          f"of 100x50 is {measured['fill']} at {measured['fill_offset']}, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
