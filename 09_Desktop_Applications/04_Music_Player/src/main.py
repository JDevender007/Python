"""Command line front end for the player lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from player import (                                        # noqa: E402
    PLAYLIST_FILE,
    REPEATS,
    Player,
    PlayerError,
    audit,
    format_duration,
    legacy_total,
    measure,
    parse_duration,
    problems,
    read_playlist,
    run_demo,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="player-lab",
        description="Play a playlist with a cue that survives an edit.")
    parser.add_argument("--playlist", default=None, metavar="PATH",
                        help="a playlist file (default: the bundled one)")
    parser.add_argument("--repeat", default="off", choices=REPEATS,
                        help="off, one or all (default: off)")
    parser.add_argument("--seed", default=None, type=int, metavar="N",
                        help="shuffle with this seed before playing")
    parser.add_argument("--remove", default=None, type=int, metavar="N",
                        help="delete the track at position N before playing")
    parser.add_argument("--steps", default=0, type=int, metavar="N",
                        help="advance N times and print the titles")
    parser.add_argument("--total", action="store_true",
                        help="print the total, and what the legacy format says")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the playlist and the run to PATH as JSON")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    try:
        tracks = read_playlist(args.playlist)
        player = Player(tracks, args.repeat, args.seed)
        removed = None
        if args.remove is not None:
            removed = player.remove(args.remove).title
        if args.steps < 0:
            raise PlayerError(f"steps is 0 or more, got {args.steps}")
        player.start()
        plays = [player.current().title]
        for _ in range(args.steps):
            following = player.advance()
            plays.append("stop" if following is None else following.title)
            if following is None:
                break
    except PlayerError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"  {player.line()}")
        if removed is not None:
            print(f"  removed position {args.remove}: {removed}")
        for number, title in enumerate(plays, start=1):
            print(f"  {number:>3}  {title}")
        if args.total:
            print(f"  total {player.total()} s = {player.total_text()} "
                  f"(the legacy format says {legacy_total(player.total())})")

    checks = []
    failed: list[str] = []
    measured: dict = {}
    if args.audit:
        measured = measure(read_playlist(args.playlist))
        checks = audit(measured, read_playlist(args.playlist))
        print()
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed = problems(checks)

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tracks": [
                {
                    "position": position,
                    "title": track.title,
                    "artist": track.artist,
                    "seconds": track.seconds,
                    "length": format_duration(track.seconds),
                }
                for position, track in enumerate(player.tracks())
            ],
            "repeat": player.repeat,
            "seed": player.seed,
            "order": list(player.titles()),
            "plays": plays,
            "history": list(player.history()),
            "removed": removed,
            "total_seconds": player.total(),
            "total_text": player.total_text(),
            "legacy_total": legacy_total(player.total()),
            "measurements": measured,
            "checks": [{"name": name, "ok": okay} for name, okay in checks],
        }
        destination.write_text(json.dumps(payload, indent=2) + "\n",
                               encoding="utf-8")
        if not args.quiet:
            print(f"  wrote the run to {destination}")

    if failed:
        print(f"  {len(failed)} check(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
