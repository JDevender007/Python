"""Tests for the Motion Analyzer project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from motion import (  # noqa: E402
    APPEARS_AT,
    ASCII_WIDTH,
    DATA_DIR,
    DEFAULT_THRESHOLD,
    FRAME_COUNT,
    HEIGHT,
    METHODS,
    STATIC_BOX,
    WIDTH,
    MotionError,
    analyse,
    ascii_overlay,
    background_mask,
    bundle_frames,
    clean_mask,
    dilate,
    erode,
    frame_difference,
    generate_sequence,
    load_frames,
    load_truth,
    motion_stats,
    render_report,
    run_demo,
    running_background,
    to_dict,
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
# Sequence / bundling
# --------------------------------------------------------------------------- #
def test_generate_sequence_shape_count():
    frames, rows = generate_sequence()
    assert len(frames) == FRAME_COUNT == 20
    assert frames[0].shape == (HEIGHT, WIDTH)
    assert frames[0].dtype == np.uint8
    assert len(rows) == FRAME_COUNT


def test_generate_sequence_deterministic():
    a, ra = generate_sequence()
    b, rb = generate_sequence()
    assert ra == rb
    for left, right in zip(a, b):
        assert np.array_equal(left, right)


def test_truth_rows_have_expected_keys(truth):
    assert set(truth[0]) == {"frame", "cx", "cy", "half", "new_x", "new_y"}
    assert [row["frame"] for row in truth] == list(range(FRAME_COUNT))


def test_new_object_absent_before_appears_at(truth):
    assert all(row["new_x"] == -1 for row in truth[:APPEARS_AT])
    assert all(row["new_x"] > 0 for row in truth[APPEARS_AT:])


def test_static_object_is_constant(frames):
    x0, y0, x1, y1 = STATIC_BOX
    reference = float(frames[0][y0:y1, x0:x1].mean())
    for frame in frames[1:]:
        # sensor noise is added everywhere; the *mean* must stay constant
        assert abs(float(frame[y0:y1, x0:x1].mean()) - reference) < 6.0


def test_bundle_frames_writes_files(tmp_path):
    paths = bundle_frames(tmp_path)
    assert len(paths) == FRAME_COUNT
    assert (tmp_path / "truth.csv").is_file()


def test_load_frames_missing_dir(tmp_path):
    with pytest.raises(MotionError, match="frames directory not found"):
        load_frames(tmp_path / "missing")


def test_load_frames_empty_dir(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(MotionError, match="no frames found"):
        load_frames(tmp_path / "empty")


def test_load_truth_missing(tmp_path):
    with pytest.raises(MotionError, match="ground truth not found"):
        load_truth(tmp_path)


# --------------------------------------------------------------------------- #
# Frame differencing
# --------------------------------------------------------------------------- #
def test_difference_of_identical_frames_is_empty():
    frame = np.full((10, 10), 50, dtype=np.uint8)
    assert not frame_difference(frame, frame).any()


def test_difference_detects_large_change():
    a = np.zeros((10, 10), dtype=np.uint8)
    b = a.copy()
    b[2:5, 2:5] = 200
    mask = frame_difference(a, b, 25)
    assert mask[2:5, 2:5].all()
    assert mask.sum() == 9


def test_difference_ignores_small_drift():
    a = np.full((6, 6), 60, dtype=np.uint8)
    b = np.full((6, 6), 66, dtype=np.uint8)
    assert not frame_difference(a, b, 25).any()


def test_difference_threshold_validation():
    a = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(MotionError, match="threshold must be in"):
        frame_difference(a, a, 0)


def test_difference_shape_mismatch():
    with pytest.raises(MotionError, match="frame shapes differ"):
        frame_difference(np.zeros((4, 4)), np.zeros((5, 5)))


# --------------------------------------------------------------------------- #
# Background model
# --------------------------------------------------------------------------- #
def test_running_background_requires_frames():
    with pytest.raises(MotionError, match="no frames"):
        running_background([])


@pytest.mark.parametrize("alpha", [0.0, -0.5, 1.5])
def test_running_background_validates_alpha(alpha):
    frame = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(MotionError, match="alpha must be in"):
        running_background([frame], alpha)


def test_running_background_alpha_one_is_last_frame():
    a = np.zeros((4, 4), dtype=np.uint8)
    b = np.full((4, 4), 100, dtype=np.uint8)
    model = running_background([a, b], alpha=1.0)
    assert np.allclose(model, 100.0)


def test_running_background_shape_mismatch():
    with pytest.raises(MotionError, match="frame shapes differ"):
        running_background([np.zeros((4, 4)), np.zeros((5, 5))])


def test_background_mask_detects_foreground():
    bg = np.full((10, 10), 40.0)
    frame = bg.copy()
    frame[3:7, 3:7] = 200
    mask = background_mask(frame, bg, 25)
    assert mask[3:7, 3:7].all()
    assert mask.sum() == 16


def test_background_mask_shape_mismatch():
    with pytest.raises(MotionError, match="shapes differ"):
        background_mask(np.zeros((4, 4)), np.zeros((5, 5)))


def test_background_mask_threshold_validation():
    with pytest.raises(MotionError, match="threshold must be in"):
        background_mask(np.zeros((4, 4)), np.zeros((4, 4)), 255)


# --------------------------------------------------------------------------- #
# Morphology
# --------------------------------------------------------------------------- #
def test_dilate_grows_mask():
    mask = np.zeros((9, 9), dtype=bool)
    mask[4, 4] = True
    assert dilate(mask, 1).sum() == 9
    assert dilate(mask, 2).sum() == 25


def test_erode_shrinks_mask():
    mask = np.zeros((9, 9), dtype=bool)
    mask[2:7, 2:7] = True
    assert erode(mask, 1).sum() == 9


def test_zero_iterations_returns_copy():
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 2] = True
    out = dilate(mask, 0)
    assert out.sum() == 1
    assert out is not mask


def test_negative_iterations_rejected():
    with pytest.raises(MotionError, match="iterations must be non-negative"):
        erode(np.ones((4, 4), dtype=bool), -1)


def test_morphology_rejects_3d():
    with pytest.raises(MotionError, match="mask must be 2-D"):
        dilate(np.ones((4, 4, 2), dtype=bool))


def test_clean_mask_removes_speckle_keeps_block():
    mask = np.zeros((20, 20), dtype=bool)
    mask[2, 2] = True
    mask[10:16, 10:16] = True
    cleaned = clean_mask(mask)
    assert not cleaned[2, 2]
    assert cleaned[12, 12]


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def test_motion_stats_empty_mask():
    stats = motion_stats(np.zeros((8, 8), dtype=bool))
    assert stats == {"pixels": 0, "ratio": 0.0, "bbox": None,
                     "centroid": None}


def test_motion_stats_known_square():
    mask = np.zeros((20, 20), dtype=bool)
    mask[4:8, 6:10] = True
    stats = motion_stats(mask)
    assert stats["pixels"] == 16
    assert stats["bbox"] == [6, 4, 9, 7]
    assert stats["centroid"] == [7.5, 5.5]
    assert stats["ratio"] == pytest.approx(16 / 400)


def test_motion_stats_rejects_3d():
    with pytest.raises(MotionError, match="mask must be 2-D"):
        motion_stats(np.ones((4, 4, 3), dtype=bool))


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def test_analyse_requires_frames():
    with pytest.raises(MotionError, match="no frames to analyse"):
        analyse([])


def test_analyse_rejects_unknown_method(frames):
    with pytest.raises(MotionError, match="unknown method"):
        analyse(frames, method="optical-flow")


def test_analyse_validates_threshold(frames):
    with pytest.raises(MotionError, match="threshold must be in"):
        analyse(frames, threshold=0)


def test_analyse_validates_warmup(frames):
    with pytest.raises(MotionError, match="warmup must be at least 1"):
        analyse(frames, warmup=0)


def test_analyse_diff_stats(frames):
    result = analyse(frames, method="diff")
    stats = result["stats"]["diff"]
    assert len(result["masks"]["diff"]) == FRAME_COUNT
    assert stats["active_frames"] == FRAME_COUNT - 1
    assert stats["max_pixels"] > 0


def test_analyse_background_stats(frames):
    result = analyse(frames, method="background")
    stats = result["stats"]["background"]
    assert stats["warmup"] == 3
    assert stats["active_frames"] == FRAME_COUNT
    assert result["background"].shape == (HEIGHT, WIDTH)


def test_analyse_all_contains_both(frames):
    result = analyse(frames, method="all")
    assert set(result["stats"]) == {"diff", "background"}
    assert set(result["masks"]) == {"diff", "background"}


@pytest.mark.parametrize("method", METHODS)
def test_every_method_runs(method, frames):
    assert analyse(frames, method=method)["method"] == method


def test_analyse_is_deterministic(frames):
    assert analyse(frames, method="all")["stats"] == \
        analyse(frames, method="all")["stats"]


def test_static_object_not_detected(frames):
    x0, y0, x1, y1 = STATIC_BOX
    masks = analyse(frames, method="background")["masks"]["background"]
    rate = np.mean([m[y0 + 2:y1 - 2, x0 + 2:x1 - 2].mean() for m in masks])
    assert rate < 0.05


def test_new_object_detected_only_after_appears(frames):
    masks = analyse(frames, method="background")["masks"]["background"]
    assert masks[-1][15:25, 25:35].mean() > 0.5
    assert masks[APPEARS_AT - 1][15:25, 25:35].mean() < 0.1


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def test_ascii_overlay_width(frames):
    art = ascii_overlay(analyse(frames, method="diff")["masks"]["diff"][-1])
    assert len(art.splitlines()[0]) == ASCII_WIDTH


def test_ascii_overlay_rejects_3d():
    with pytest.raises(MotionError, match="mask must be 2-D"):
        ascii_overlay(np.ones((4, 4, 3)))


def test_render_report_sections(frames):
    text = render_report(frames)
    assert "Frame size" in text
    assert "[diff]" in text
    assert "[background]" in text
    assert "ASCII overlay" in text


def test_to_dict_is_json_safe(frames):
    payload = to_dict("all", analyse(frames, method="all"))
    json.dumps(payload)
    assert payload["method"] == "all"


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
    out = capsys.readouterr().out
    assert "[diff]" in out
    assert "[background]" in out


def test_cli_single_method(capsys):
    assert main(["--frames", str(FRAMES), "--method", "diff"]) == 0
    out = capsys.readouterr().out
    assert "[diff]" in out
    assert "[background]" not in out


@pytest.mark.parametrize("flag,value,needle", [
    ("--threshold", "0", "threshold must be in"),
    ("--alpha", "0", "alpha must be in"),
    ("--warmup", "0", "warmup must be at least 1"),
])
def test_cli_validates_flags(flag, value, needle, capsys):
    assert main(["--frames", str(FRAMES), flag, value]) == 2
    assert needle in capsys.readouterr().err


def test_cli_missing_frames(tmp_path, capsys):
    assert main(["--frames", str(tmp_path / "nope")]) == 2
    assert "frames directory not found" in capsys.readouterr().err


def test_cli_json_export(tmp_path):
    out = tmp_path / "report.json"
    assert main(["--frames", str(FRAMES), "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["stats"]["diff"]["active_frames"] == FRAME_COUNT - 1
    assert payload["stats"]["background"]["active_frames"] == FRAME_COUNT


def test_bundled_data_present():
    assert (DATA_DIR / "truth.csv").is_file()
    assert FRAMES.is_dir()
    assert DEFAULT_THRESHOLD == 25.0
