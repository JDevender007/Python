"""Command line front end for the image lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from images import (                                        # noqa: E402
    IMAGES_FILE,
    Entry,
    ImageError,
    Size,
    audit,
    binding_side,
    centred,
    fill_box,
    fit_inside,
    legacy_resize,
    measure,
    parse_images,
    problems,
    read_images,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image-lab",
        description="Fit or fill an image inside a box, in integers.")
    parser.add_argument("--images", default=None, metavar="PATH",
                        help="a bundle of images (default: the bundled one)")
    parser.add_argument("--image", default=None, metavar="WxH",
                        help="one image size, e.g. 4000x3000")
    parser.add_argument("--box", default="320x240", metavar="WxH",
                        help="the box to place it in (default: 320x240)")
    parser.add_argument("--mode", default="fit", choices=("fit", "fill"),
                        help="fit inside the box, or fill it (default: fit)")
    parser.add_argument("--centre", action="store_true",
                        help="move a fitted image to the middle of the box")
    parser.add_argument("--legacy", action="store_true",
                        help="print what the float-based resize says")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the placements to PATH as JSON")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def parse_size(text: str, name: str) -> Size:
    fields = str(text).strip().lower().split("x")
    if len(fields) != 2:
        raise ImageError(f"{name} is written WxH, got {text!r}")
    try:
        width, height = int(fields[0]), int(fields[1])
    except ValueError:
        raise ImageError(f"{name} is two whole numbers, got {text!r}") from None
    return Size(width, height)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    try:
        if args.image is not None:
            image = parse_size(args.image, "an image")
            box = parse_size(args.box, "a box")
            entries = (Entry("cli", image, box),)
        else:
            entries = read_images(args.images)
    except ImageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    rows = []
    for entry in entries:
        placed = fill_box(entry.image, entry.box) if args.mode == "fill" else \
            (centred(entry.image, entry.box) if args.centre else
             fit_inside(entry.image, entry.box))
        rows.append((entry, placed))

    if not args.quiet:
        for entry, placed in rows:
            side = binding_side(entry.image, entry.box)
            print(f"  {entry.name:<10} {entry.image.plain():>9} in "
                  f"{entry.box.plain():>9} -> {placed.line()}  {side} binds")
            if args.legacy:
                old = legacy_resize(tuple(entry.image), tuple(entry.box))
                print(f"  {'':<10} {'':>9}    {'':>9}    legacy: "
                      f"{old[0]}x{old[1]}")

    checks = []
    failed: list[str] = []
    measured: dict = {}
    if args.audit:
        measured = measure(entries)
        checks = audit(measured, entries)
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": args.mode,
            "placements": [
                {
                    "name": entry.name,
                    "image": entry.image.plain(),
                    "box": entry.box.plain(),
                    "binding": binding_side(entry.image, entry.box),
                    "placed": placed.plain(),
                    "offset": [placed.x, placed.y],
                    "error": placed.error(),
                    "legacy": "x".join(str(side) for side in
                                       legacy_resize(tuple(entry.image),
                                                     tuple(entry.box))),
                }
                for entry, placed in rows
            ],
            "measurements": measured,
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the placements to {destination}")

    if failed:
        print(f"  {len(failed)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
