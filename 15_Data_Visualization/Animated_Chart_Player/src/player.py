"""Animated chart player: animated GIFs from a league score table - offline.

Loads a CSV of weekly team scores and renders animated GIFs with
matplotlib's FuncAnimation saved through the Pillow writer: a progressive
line race, a re-sorting bar race, and a growing stacked area. Fully
offline - Agg backend, local files only, no network, no GUI.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

import matplotlib
matplotlib.use("Agg")  # headless: must precede pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402

LOG = logging.getLogger("player")

REQUIRED_COLUMNS = ("week", "team", "score")


class PlayerError(RuntimeError):
    """Raised for missing files, bad schemas, and unknown animation names."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_scores(path: str | Path) -> pd.DataFrame:
    """Load the weekly team-score CSV, validate it, return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise PlayerError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise PlayerError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise PlayerError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise PlayerError(f"no rows in {source.name}")

    frame = frame.copy()
    frame["team"] = frame["team"].astype(str).str.strip()
    if frame["team"].eq("").any() or frame["team"].str.lower().eq("nan").any():
        raise PlayerError("empty team value(s)")

    frame["week"] = pd.to_numeric(frame["week"], errors="coerce")
    if frame["week"].isna().any():
        raise PlayerError("column 'week' contains non-numeric values")
    if not frame["week"].between(1, 10_000).all() or (frame["week"] % 1 != 0).any():
        raise PlayerError("week must be whole numbers in 1..10000")
    frame["week"] = frame["week"].astype(int)

    frame["score"] = pd.to_numeric(frame["score"], errors="coerce")
    if frame["score"].isna().any():
        raise PlayerError("column 'score' contains non-numeric values")
    if not np.isfinite(frame["score"]).all():
        raise PlayerError("score must be finite")
    if (frame["score"] < 0).all():
        raise PlayerError("scores cannot all be negative")

    if frame.duplicated(subset=["week", "team"]).any():
        raise PlayerError("duplicate (week, team) rows")

    # every team must appear in every week (clean animation timeline)
    weeks = sorted(frame["week"].unique())
    teams = sorted(frame["team"].unique())
    expected = len(weeks) * len(teams)
    if len(frame) != expected:
        incomplete = [t for t in teams
                      if set(frame.loc[frame["team"] == t, "week"]) != set(weeks)]
        raise PlayerError(
            f"every team needs every week; incomplete: {', '.join(incomplete)}"
        )
    if len(teams) < 2:
        raise PlayerError("need at least two teams")
    if len(weeks) < 2:
        raise PlayerError("need at least two weeks")

    frame = frame.sort_values(["week", "team"]).reset_index(drop=True)
    LOG.info("loaded %d rows: %d teams x %d weeks from %s",
             len(frame), len(teams), len(weeks), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Frame data helpers (pure functions -> easy to test)
# --------------------------------------------------------------------------- #
def weeks(frame: pd.DataFrame) -> list[int]:
    return sorted(int(w) for w in frame["week"].unique())


def teams(frame: pd.DataFrame) -> list[str]:
    return sorted(frame["team"].unique())


def scores_through(frame: pd.DataFrame, week: int) -> dict[str, list[float]]:
    """Per-team scores from the first week up to (and including) `week`."""
    subset = frame[frame["week"] <= week]
    return {team: list(group.sort_values("week")["score"])
            for team, group in subset.groupby("team")}


def rankings_at(frame: pd.DataFrame, week: int) -> list[tuple[str, float]]:
    """Teams at `week` sorted by score descending (ties broken by name)."""
    subset = frame[frame["week"] == week].sort_values(
        ["score", "team"], ascending=[False, True])
    return [(str(row["team"]), float(row["score"]))
            for _, row in subset.iterrows()]


# --------------------------------------------------------------------------- #
# Animation builders (update functions over a fixed figure)
# --------------------------------------------------------------------------- #
PALETTE = ["#4C72B0", "#C44E52", "#55A868", "#8172B2",
           "#CCB974", "#64B5CD", "#8C8C8C", "#E57242"]


def _make_figure(title: str) -> tuple[Any, Any]:
    figure, axis = plt.subplots(figsize=(8, 4.5))
    figure.subplots_adjust(top=0.85)
    figure.suptitle(title)
    return figure, axis


def _build_line_race(frame: pd.DataFrame) -> tuple[Any, Callable[[int], Any]]:
    """Progressive line chart: each frame extends every team's line."""
    timeline = weeks(frame)
    all_teams = teams(frame)

    figure, axis = _make_figure("Score race - line")
    axis.set_xlim(timeline[0], timeline[-1])
    y_min = float(frame["score"].min())
    y_max = float(frame["score"].max())
    pad = (y_max - y_min) * 0.1 or 1.0
    axis.set_ylim(y_min - pad, y_max + pad)
    axis.set_xlabel("Week")
    axis.set_ylabel("Score")
    axis.grid(alpha=0.3)

    lines = {}
    for i, team in enumerate(all_teams):
        color = PALETTE[i % len(PALETTE)]
        line, = axis.plot([], [], marker="o", linewidth=2, color=color,
                          label=team)
        lines[team] = line
    axis.legend(loc="upper left")  # after artists exist (labels registered)

    def update(week: int):
        data = scores_through(frame, week)
        for team, values in data.items():
            xs = timeline[:len(values)]
            lines[team].set_data(xs, values)
        axis.set_title(f"Week {week}")
        return list(lines.values())

    return figure, update


def _build_bar_race(frame: pd.DataFrame) -> tuple[Any, Callable[[int], Any]]:
    """Horizontal bars that re-sort by score every frame."""
    timeline = weeks(frame)
    all_teams = teams(frame)

    figure, axis = _make_figure("Score race - bar")
    axis.set_xlim(0, float(frame["score"].max()) * 1.12)
    axis.set_xlabel("Score")
    axis.grid(axis="x", alpha=0.3)
    axis.invert_yaxis()  # best score on top

    bars = {}
    texts = {}
    for i, team in enumerate(all_teams):
        color = PALETTE[i % len(PALETTE)]
        bar = axis.barh(team, 0.0, color=color, height=0.65)
        text = axis.text(0.0, 0.0, "", va="center", ha="left", fontsize=9)
        bars[team] = bar
        texts[team] = text

    def update(week: int):
        ranking = rankings_at(frame, week)
        for position, (team, score) in enumerate(ranking):
            bar = bars[team]
            bar[0].set_y(position)
            bar[0].set_width(score)
            text = texts[team]
            text.set_y(position)
            text.set_x(score)
            text.set_text(f" {score:.1f}")
        axis.set_yticks(range(len(ranking)))
        axis.set_yticklabels([name for name, _ in ranking])
        axis.set_title(f"Week {week}")
        return list(bars.values()) + list(texts.values())

    return figure, update


def _build_area_race(frame: pd.DataFrame) -> tuple[Any, Callable[[int], Any]]:
    """Stacked area growing week by week."""
    timeline = weeks(frame)
    all_teams = teams(frame)

    figure, axis = _make_figure("Score race - stacked area")
    axis.set_xlim(timeline[0], timeline[-1])
    axis.set_ylim(0, float(frame.groupby("week")["score"].sum().max()) * 1.08)
    axis.set_xlabel("Week")
    axis.set_ylabel("Total score")
    axis.grid(alpha=0.3)

    stacked = frame.pivot_table(index="week", columns="team",
                                values="score", aggfunc="sum")
    stacked = stacked.reindex(index=timeline, columns=all_teams)

    def update(week: int):
        axis.cla()
        axis.set_xlim(timeline[0], timeline[-1])
        axis.set_ylim(0, float(frame.groupby("week")["score"].sum().max()) * 1.08)
        axis.set_xlabel("Week")
        axis.set_ylabel("Total score")
        axis.grid(alpha=0.3)
        visible_weeks = [w for w in timeline if w <= week]
        matrix = stacked.loc[visible_weeks].T.values
        axis.stackplot(visible_weeks, matrix, labels=all_teams,
                       colors=[PALETTE[i % len(PALETTE)]
                               for i in range(len(all_teams))],
                       alpha=0.9)
        axis.set_title(f"Week {week}")
        axis.legend(loc="upper left")
        return axis.collections + axis.lines

    return figure, update


# name -> (builder, description)
ANIMATIONS: dict[str, tuple[Callable[[pd.DataFrame], Any], str]] = {
    "line": (_build_line_race, "progressive multi-team line race"),
    "bar": (_build_bar_race, "re-sorting horizontal bar race"),
    "area": (_build_area_race, "growing stacked area chart"),
}


def build_animation(name: str, frame: pd.DataFrame) -> FuncAnimation:
    """Create a FuncAnimation over every week of the timeline."""
    if name not in ANIMATIONS:
        available = ", ".join(sorted(ANIMATIONS))
        raise PlayerError(f"unknown animation {name!r} (available: {available})")
    builder = ANIMATIONS[name][0]
    figure, update = builder(frame)
    timeline = weeks(frame)
    animation = FuncAnimation(
        figure, update, frames=timeline, interval=600, repeat=False,
        blit=False,
    )
    return animation


def render_animation(name: str, frame: pd.DataFrame, out_path: str | Path,
                     fps: int = 4) -> Path:
    """Render one animation to a GIF (Pillow writer, local file only)."""
    if fps < 1 or fps > 30:
        raise PlayerError("fps must be in 1..30")
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    animation = build_animation(name, frame)
    figure = animation._fig
    try:
        animation.save(target, writer=PillowWriter(fps=fps))
    finally:
        plt.close(figure)
    if not target.is_file() or target.stat().st_size == 0:
        raise PlayerError(f"failed to write {target}")
    LOG.info("rendered %s -> %s (%d bytes)", name, target, target.stat().st_size)
    return target


def gif_frame_count(path: str | Path) -> int:
    """Number of frames in a GIF (via Pillow)."""
    from PIL import Image
    with Image.open(path) as image:
        return int(getattr(image, "n_frames", 1))


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "league_sample.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "output"


def run_demo(out_dir: Path | None = None, quiet: bool = False) -> int:
    """Render every animation from the bundled sample - fully offline."""
    if not quiet:
        print("=" * 60)
        print(" ANIMATED CHART PLAYER - offline demo")
        print(" Bundled league scores; Agg backend; local GIFs.")
        print("=" * 60)

    if not DEMO_CSV.is_file():
        raise PlayerError(f"bundled sample not found: {DEMO_CSV}")
    frame = load_scores(DEMO_CSV)
    target_dir = out_dir or DEFAULT_OUTPUT
    timeline = weeks(frame)

    if not quiet:
        print(f"\nLoaded {len(frame)} rows: {len(teams(frame))} teams x "
              f"{len(timeline)} weeks from {DEMO_CSV.name}")
        print(f"Rendering {len(ANIMATIONS)} animations "
              f"({len(timeline)} frames each) to {target_dir}/\n")

    written: dict[str, Path] = {}
    for name in ANIMATIONS:
        path = render_animation(name, frame, target_dir / f"{name}.gif")
        written[name] = path
        if not quiet:
            print(f"  {name:<8} {path.name:<14} {path.stat().st_size:>9,} bytes "
                  f"({gif_frame_count(path)} frames)")

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(written) == len(ANIMATIONS) == 3, "expected 3 animations"
    for name, path in written.items():
        assert path.is_file(), f"{name} not written"
        assert path.stat().st_size > 5_000, f"{name} suspiciously small"
        assert gif_frame_count(path) == len(timeline), f"{name} frame count"

    # rankings: strict order at the final week, consistent with raw scores
    final = rankings_at(frame, timeline[-1])
    assert len(final) == len(teams(frame))
    scores = [score for _, score in final]
    assert scores == sorted(scores, reverse=True), "rankings not sorted"
    manual = sorted(
        ((str(t), float(s)) for t, s in
         frame[frame["week"] == timeline[-1]][["team", "score"]].values),
        key=lambda pair: (-pair[1], pair[0]))
    assert final == manual, "ranking mismatch vs raw frame"

    # scores_through grows monotonically in length
    half = timeline[len(timeline) // 2]
    partial = scores_through(frame, half)
    assert all(len(v) == half for v in partial.values())
    assert all(len(v) == timeline[-1] for v in scores_through(
        frame, timeline[-1]).values())

    if not quiet:
        leader, leader_score = final[0]
        print(f"\nCross-checks OK: 3 GIFs with {len(timeline)} frames each, "
              f"rankings sorted (leader {leader} at {leader_score:.1f})")
        print("Demo completed successfully.")
    return 0
