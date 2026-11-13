"""Tests for the Object Tracker project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from tracker import (  # noqa: E402
    BALL_RGB,
    COLOUR_RANGES,
    DATA_DIR,
    FRAME_COUNT,
    HEIGHT,
    RADIUS,
    WIDTH,
    TrackerError,
    analyse,
    blob_centroid,
    bundle_frames,
    colour_mask,
    detect,
    detect_area,
    generate_sequence,
    load_frames,
    load_truth,
    path_stats,
    position_errors,
    render_report,
    run_demo,
    to_dict,
    track_colour,
    trajectory_map,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRAMES = PROJECT_ROOT / "data" / "frames"


@pytest.fixture(scope="module")
def frames() -> list[np.ndarray]:
    return load_frames()


@pytest.fixture(scope="module")
def truth() -> list[dict]:
    return load_truth()


# --------------------------------------------------------------------------- #
# Generation / bundling
# --------------------------------------------------------------------------- #
def test_generate_sequence_shape_and_count():
    frames, rows = generate_sequence()
    assert len(frames) == FRAME_COUNT == 24
    assert frames[0].shape == (HEIGHT, WIDTH, 3)
    assert len(rows) == FRAME_COUNT


def test_generate_sequence_is_deterministic():
    a, ra = generate_sequence()
    b, rb = generate_sequence()
    assert ra == rb
    for left, right in zip(a, b):
        assert np.array_equal(left, right)


def test_truth_rows_have_expected_keys(truth):
    assert set(truth[0]) == {"frame", "red_x", "red_y", "blue_x", "blue_y"}
    assert [row["frame"] for row in truth] == list(range(FRAME_COUNT))


def test_balls_travel_in_opposite_directions(truth):
    assert truth[-1]["red_x"] > truth[0]["red_x"]
    assert truth[-1]["blue_x"] < truth[0]["blue_x"]


def test_balls_stay_inside_frame(truth):
    for row in truth:
        for colour in ("red", "blue"):
            assert RADIUS < row[f"{colour}_x"] < WIDTH - RADIUS
            assert RADIUS < row[f"{colour}_y"] < HEIGHT - RADIUS


def test_bundle_frames_writes_all_frames(tmp_path):
    paths = bundle_frames(tmp_path)
    assert len(paths) == FRAME_COUNT
    assert (tmp_path / "truth.csv").is_file()


def test_load_frames_missing_dir(tmp_path):
    with pytest.raises(TrackerError, match="frames directory not found"):
        load_frames(tmp_path / "missing")


def test_load_frames_empty_dir(tmp_path):
    (tmp_path / "frames").mkdir()
    with pytest.raises(TrackerError, match="no frames found"):
        load_frames(tmp_path / "frames")


def test_load_truth_missing(tmp_path):
    with pytest.raises(TrackerError, match="ground truth not found"):
        load_truth(tmp_path)


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
def test_colour_mask_finds_ball(frames):
    mask = colour_mask(frames[0], "red")
    assert mask.dtype == bool
    assert mask.shape == (HEIGHT, WIDTH)
    assert 0.6 * np.pi * RADIUS ** 2 < mask.sum() < 1.4 * np.pi * RADIUS ** 2


def test_colour_mask_rejects_unknown_colour(frames):
    with pytest.raises(TrackerError, match="unknown colour"):
        colour_mask(frames[0], "green")


def test_colour_mask_rejects_grayscale():
    with pytest.raises(TrackerError, match="frame must be HxWx3"):
        colour_mask(np.zeros((10, 10), dtype=np.uint8), "red")


def test_colour_mask_empty_on_background(frames):
    assert not colour_mask(frames[0], "blue")[20:40, 40:60].any()


def test_blob_centroid_none_on_empty_mask():
    assert blob_centroid(np.zeros((8, 8), dtype=bool)) is None


def test_blob_centroid_of_square():
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:5, 3:7] = True
    x, y = blob_centroid(mask)
    assert x == pytest.approx(4.5)
    assert y == pytest.approx(3.0)


def test_blob_centroid_rejects_3d():
    with pytest.raises(TrackerError, match="mask must be 2-D"):
        blob_centroid(np.ones((4, 4, 2)))


def test_detect_matches_truth(frames, truth):
    for index in (0, 12, FRAME_COUNT - 1):
        centre = detect(frames[index], "red")
        assert centre is not None
        assert abs(centre[0] - truth[index]["red_x"]) <= 1.0
        assert abs(centre[1] - truth[index]["red_y"]) <= 1.0


def test_detect_area_tracks_visibility(frames):
    assert detect_area(frames[0], "red") > 100
    assert detect_area(np.zeros((HEIGHT, WIDTH, 3), np.uint8), "red") == 0


def test_detect_returns_none_without_ball():
    assert detect(np.zeros((HEIGHT, WIDTH, 3), np.uint8), "blue") is None


# --------------------------------------------------------------------------- #
# Tracking
# --------------------------------------------------------------------------- #
def test_track_colour_full_coverage(frames):
    path = track_colour(frames, "red")
    assert len(path) == FRAME_COUNT
    assert all(point is not None for point in path)


def test_track_colour_requires_frames():
    with pytest.raises(TrackerError, match="no frames to track"):
        track_colour([], "red")


def test_track_colour_rejects_nonpositive_jump(frames):
    with pytest.raises(TrackerError, match="max_jump must be positive"):
        track_colour(frames, "red", max_jump=0)


def test_track_colour_rejects_impossible_jump():
    blank = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    moved = blank.copy()
    moved[10:24, 10:24] = BALL_RGB["red"]
    jumped = blank.copy()
    jumped[90:104, 130:144] = BALL_RGB["red"]
    path = track_colour([moved, jumped], "red", max_jump=40)
    assert path[0] is not None
    assert path[1] is None


def test_track_colour_allows_small_jump():
    blank = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    first = blank.copy()
    first[10:24, 10:24] = BALL_RGB["red"]
    second = blank.copy()
    second[10:24, 20:34] = BALL_RGB["red"]
    path = track_colour([first, second], "red", max_jump=40)
    assert all(point is not None for point in path)


def test_path_stats_totals(frames):
    stats = path_stats(track_colour(frames, "red"))
    assert stats["frames"] == FRAME_COUNT
    assert stats["detected"] == FRAME_COUNT
    assert stats["lost"] == 0
    assert stats["coverage"] == 1.0
    assert stats["length"] > 100


def test_path_stats_counts_lost_frames():
    stats = path_stats([(0.0, 0.0), None, (3.0, 4.0)])
    assert stats["detected"] == 2
    assert stats["lost"] == 1
    assert stats["length"] == pytest.approx(5.0)


def test_path_stats_empty_raises():
    with pytest.raises(TrackerError, match="path is empty"):
        path_stats([])


def test_path_stats_start_and_end(frames):
    stats = path_stats(track_colour(frames, "blue"))
    assert stats["start"] is not None
    assert stats["end"][0] < stats["start"][0]


def test_analyse_requires_frames():
    with pytest.raises(TrackerError, match="no frames to analyse"):
        analyse([])


def test_analyse_covers_both_colours(frames):
    result = analyse(frames)
    assert set(result["colours"]) == {"red", "blue"}
    assert result["frames"] == FRAME_COUNT


def test_analyse_single_colour(frames):
    result = analyse(frames, colours=("red",))
    assert list(result["colours"]) == ["red"]


def test_analyse_is_deterministic(frames):
    assert analyse(frames)["colours"] == analyse(frames)["colours"]


# --------------------------------------------------------------------------- #
# Ground truth comparison
# --------------------------------------------------------------------------- #
def test_position_errors_small(frames, truth):
    path = track_colour(frames, "red")
    errors = position_errors(path, truth, "red")
    assert errors["count"] == FRAME_COUNT
    assert errors["max"] <= 1.5
    assert errors["mean"] <= 1.0


def test_position_errors_length_mismatch(frames, truth):
    with pytest.raises(TrackerError, match="lengths differ"):
        position_errors([(1.0, 1.0)], truth, "red")


def test_position_errors_all_missing(truth):
    errors = position_errors([None] * len(truth), truth, "red")
    assert errors == {"count": 0, "max": 0.0, "mean": 0.0}


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def test_trajectory_map_contains_glyphs(frames):
    result = analyse(frames)
    art = trajectory_map(result["paths"])
    assert "R" in art
    assert "B" in art
    assert len(art.splitlines()[0]) == 64


def test_render_report_sections(frames):
    text = render_report(frames)
    assert "Frames" in text
    assert "[red]" in text
    assert "[blue]" in text
    assert "ASCII trajectory map" in text


def test_to_dict_is_json_safe(frames):
    payload = to_dict(analyse(frames))
    json.dumps(payload)
    assert payload["frames"] == FRAME_COUNT


# --------------------------------------------------------------------------- #
# Demo + CLI
# --------------------------------------------------------------------------- #
def test_run_demo_prints_cross_checks(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    assert capsys.readouterr().out == first


def test_cli_demo(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_requires_demo_or_frames():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_frames_report(capsys):
    assert main(["--frames", str(FRAMES)]) == 0
    assert "[red]" in capsys.readouterr().out


def test_cli_single_colour(capsys):
    assert main(["--frames", str(FRAMES), "--colour", "blue"]) == 0
    out = capsys.readouterr().out
    assert "[blue]" in out
    assert "[red]" not in out


def test_cli_rejects_bad_max_jump(capsys):
    assert main(["--frames", str(FRAMES), "--max-jump", "0"]) == 2
    assert "max-jump must be positive" in capsys.readouterr().err


def test_cli_missing_frames_dir(tmp_path, capsys):
    assert main(["--frames", str(tmp_path / "nope")]) == 2
    assert "frames directory not found" in capsys.readouterr().err


def test_cli_json_export(tmp_path):
    out = tmp_path / "report.json"
    assert main(["--frames", str(FRAMES), "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["frames"] == FRAME_COUNT
    assert payload["errors"]["red"]["max"] <= 1.5


def test_bundled_data_present():
    assert (DATA_DIR / "truth.csv").is_file()
    assert FRAMES.is_dir()


@pytest.mark.parametrize("colour", tuple(COLOUR_RANGES))
def test_every_colour_range_is_valid(colour):
    low, high = COLOUR_RANGES[colour]
    assert all(0 <= value <= 255 for value in low + high)
    assert all(lo <= hi for lo, hi in zip(low, high))
