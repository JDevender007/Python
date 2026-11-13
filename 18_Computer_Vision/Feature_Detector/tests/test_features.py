"""Tests for the Feature Detector project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from features import (  # noqa: E402
    ASCII_WIDTH,
    DATA_DIR,
    MODES,
    SHIFT,
    FeatureError,
    analyse,
    ascii_map,
    box_filter,
    bundle_samples,
    corner_mask,
    displacement_stats,
    generate_samples,
    harris_corners,
    harris_response,
    load_image,
    match_descriptors,
    orb_keypoints,
    render_report,
    run_demo,
    to_dict,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BOARD = PROJECT_ROOT / "data" / "checkerboard.png"
SCENE_A = PROJECT_ROOT / "data" / "scene_a.png"
SCENE_B = PROJECT_ROOT / "data" / "scene_b.png"


@pytest.fixture(scope="module")
def board() -> np.ndarray:
    return load_image(BOARD)


@pytest.fixture(scope="module")
def scene_a() -> np.ndarray:
    return load_image(SCENE_A)


@pytest.fixture(scope="module")
def scene_b() -> np.ndarray:
    return load_image(SCENE_B)


# --------------------------------------------------------------------------- #
# Samples / loading
# --------------------------------------------------------------------------- #
def test_generate_samples_keys():
    assert set(generate_samples()) == {"checkerboard", "scene_a", "scene_b"}


def test_generate_samples_is_deterministic():
    first = generate_samples()
    second = generate_samples()
    for key in first:
        assert np.array_equal(first[key], second[key])


def test_scene_b_is_shifted_scene_a(scene_a, scene_b):
    assert scene_a.shape == scene_b.shape
    dx, dy = SHIFT
    # interior pixels must match after undoing the roll
    restored = np.roll(np.roll(scene_b, -dy, axis=0), -dx, axis=1)
    assert np.array_equal(restored[12:-12, 20:-20], scene_a[12:-12, 20:-20])


def test_bundle_samples_writes_pngs(tmp_path):
    paths = bundle_samples(tmp_path)
    assert len(paths) == 3
    assert all(p.is_file() for p in paths)


def test_load_image_missing(tmp_path):
    with pytest.raises(FeatureError, match="image not found"):
        load_image(tmp_path / "ghost.png")


def test_load_image_undecodable(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_text("nope", encoding="utf-8")
    with pytest.raises(FeatureError, match="could not decode"):
        load_image(bad)


# --------------------------------------------------------------------------- #
# Box filter
# --------------------------------------------------------------------------- #
def test_box_filter_constant_image():
    out = box_filter(np.full((8, 8), 7.0), 3)
    assert np.allclose(out, 7.0)


def test_box_filter_shape_preserved():
    out = box_filter(np.arange(25, dtype=np.float64).reshape(5, 5), 3)
    assert out.shape == (5, 5)


def test_box_filter_mean_of_ramp():
    ramp = np.tile(np.arange(10, dtype=np.float64), (5, 1))
    out = box_filter(ramp, 3)
    # interior column means of a 3-wide window are the centre value
    assert np.allclose(out[:, 2:-2], ramp[:, 2:-2])


@pytest.mark.parametrize("size", [0, -1, 2, 4])
def test_box_filter_rejects_bad_size(size):
    with pytest.raises(FeatureError, match="positive odd number"):
        box_filter(np.zeros((4, 4)), size)


# --------------------------------------------------------------------------- #
# Harris response
# --------------------------------------------------------------------------- #
def test_response_shape(board):
    assert harris_response(board).shape == board.shape


def test_response_positive_at_intersection(board):
    response = harris_response(board)
    # grid intersection near (32, 32)
    patch = response[30:35, 30:35]
    assert patch.max() > 0


def test_response_low_on_flat_region(board):
    response = harris_response(board)
    assert abs(response[16, 16]) < 1e-9


def test_response_ignores_brightness_offset(board):
    shifted = np.clip(board.astype(np.int16) + 5, 0, 255).astype(np.uint8)
    assert np.allclose(harris_response(board), harris_response(shifted),
                       atol=1e-9)


@pytest.mark.parametrize("k", [0.0, 0.25, -0.1])
def test_response_rejects_bad_k(k, board):
    with pytest.raises(FeatureError, match="k must be in"):
        harris_response(board, k=k)


# --------------------------------------------------------------------------- #
# Harris corners
# --------------------------------------------------------------------------- #
def test_checkerboard_corners_exactly_nine(board):
    corners = harris_corners(board, max_corners=100)
    assert corners.shape == (9, 3)


def test_checkerboard_corner_positions(board):
    corners = harris_corners(board, max_corners=100)
    snapped = {(int(round(x / 32)) * 32, int(round(y / 32)) * 32)
               for y, x, _ in corners}
    assert snapped == {(x, y) for x in (32, 64, 96) for y in (32, 64, 96)}


def test_corners_sorted_by_response(board):
    corners = harris_corners(board, max_corners=100)
    assert np.all(np.diff(corners[:, 2]) <= 0)


def test_max_corners_limits_output(board):
    assert harris_corners(board, max_corners=4).shape[0] == 4


def test_high_threshold_removes_corners(board):
    assert harris_corners(board, threshold=10.0).shape[0] == 0


def test_min_distance_suppresses_plateaus(board):
    dense = harris_corners(board, min_distance=0, max_corners=100)
    sparse = harris_corners(board, min_distance=5, max_corners=100)
    assert sparse.shape[0] < dense.shape[0]


def test_harris_is_deterministic(board):
    assert np.array_equal(harris_corners(board, max_corners=50),
                          harris_corners(board, max_corners=50))


def test_corners_on_flat_image_are_empty():
    flat = np.full((32, 32), 128, dtype=np.uint8)
    assert harris_corners(flat).shape[0] == 0


# --------------------------------------------------------------------------- #
# ORB
# --------------------------------------------------------------------------- #
def test_orb_returns_descriptors(scene_a):
    keypoints, descriptors = orb_keypoints(scene_a)
    assert len(keypoints) >= 20
    assert descriptors.ndim == 2
    assert descriptors.shape[1] == 32


def test_orb_feature_budget(scene_a):
    keypoints, _ = orb_keypoints(scene_a, nfeatures=25)
    assert len(keypoints) <= 25


def test_orb_rejects_bad_nfeatures(scene_a):
    with pytest.raises(FeatureError, match="nfeatures must be positive"):
        orb_keypoints(scene_a, nfeatures=0)


def test_match_descriptors_finds_shift(scene_a, scene_b):
    kp_a, desc_a = orb_keypoints(scene_a)
    kp_b, desc_b = orb_keypoints(scene_b)
    matches = match_descriptors(desc_a, desc_b)
    stats = displacement_stats(kp_a, kp_b, matches)
    assert stats["count"] >= 10
    assert abs(stats["median_dx"] - SHIFT[0]) <= 3
    assert abs(stats["median_dy"] - SHIFT[1]) <= 3


def test_match_descriptors_empty_input():
    assert match_descriptors(np.zeros((0, 32), np.uint8),
                             np.zeros((0, 32), np.uint8)) == []


def test_match_descriptors_none_descriptors():
    assert match_descriptors(None, None) == []


@pytest.mark.parametrize("ratio", [0.0, 1.5])
def test_match_descriptors_rejects_bad_ratio(scene_a, ratio):
    _, desc = orb_keypoints(scene_a)
    with pytest.raises(FeatureError, match="ratio must be in"):
        match_descriptors(desc, desc, ratio=ratio)


def test_displacement_stats_empty():
    stats = displacement_stats([], [], [])
    assert stats["count"] == 0
    assert stats["median_dx"] == 0.0


# --------------------------------------------------------------------------- #
# analyse
# --------------------------------------------------------------------------- #
def test_analyse_harris_stats(scene_a):
    result = analyse(scene_a, mode="harris", threshold=1e-6)
    stats = result["stats"]["harris"]
    assert stats["corners"] > 0
    assert result["points"].shape[1] == 3
    assert "orb" not in result["stats"]


def test_analyse_all_stats(scene_a, scene_b):
    result = analyse(scene_a, mode="all", threshold=1e-6, reference=scene_b)
    assert set(result["stats"]) == {"harris", "orb"}
    assert result["stats"]["orb"]["keypoints_a"] >= 20


def test_analyse_orb_requires_reference(scene_a):
    with pytest.raises(FeatureError, match="needs a reference image"):
        analyse(scene_a, mode="orb")


def test_analyse_rejects_unknown_mode(scene_a):
    with pytest.raises(FeatureError, match="unknown mode"):
        analyse(scene_a, mode="sift")


def test_analyse_is_deterministic(scene_a, scene_b):
    first = analyse(scene_a, mode="all", reference=scene_b)
    second = analyse(scene_a, mode="all", reference=scene_b)
    assert first["stats"] == second["stats"]
    assert np.array_equal(first["points"], second["points"])


@pytest.mark.parametrize("mode", MODES)
def test_every_mode_runs(mode, scene_a, scene_b):
    result = analyse(scene_a, mode=mode, reference=scene_b)
    assert result["mode"] == mode


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def test_corner_mask_radius():
    mask = corner_mask(np.array([[5.0, 5.0, 1.0]]), (10, 10), radius=2)
    assert mask[3:8, 3:8].sum() == 25


def test_ascii_map_width():
    art = ascii_map(np.ones((20, 100)), width=ASCII_WIDTH)
    assert len(art.splitlines()[0]) == ASCII_WIDTH


def test_ascii_map_rejects_3d():
    with pytest.raises(FeatureError, match="mask must be 2-D"):
        ascii_map(np.ones((4, 4, 3)))


def test_render_report_sections(scene_a, scene_b):
    text = render_report("all", scene_a, "scene_a.png", reference=scene_b)
    assert "Harris corners" in text
    assert "ORB keypoints" in text
    assert "Good matches" in text
    assert "ASCII preview" in text


def test_to_dict_is_json_safe(scene_a, scene_b):
    payload = to_dict("all", "a.png",
                      analyse(scene_a, mode="all", reference=scene_b))
    json.dumps(payload)
    assert payload["file"] == "a.png"


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


def test_cli_requires_demo_or_file():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_harris_file(scene_a, tmp_path, capsys):
    path = tmp_path / "a.png"
    cv2.imwrite(str(path), scene_a)
    assert main(["--file", str(path), "--threshold", "1e-6"]) == 0
    assert "Harris corners" in capsys.readouterr().out


def test_cli_orb_requires_compare(scene_a, tmp_path, capsys):
    path = tmp_path / "a.png"
    cv2.imwrite(str(path), scene_a)
    assert main(["--file", str(path), "--mode", "orb"]) == 2
    assert "--compare" in capsys.readouterr().err


def test_cli_all_with_compare(scene_a, scene_b, tmp_path, capsys):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    cv2.imwrite(str(a), scene_a)
    cv2.imwrite(str(b), scene_b)
    assert main(["--file", str(a), "--compare", str(b),
                 "--mode", "all", "--threshold", "1e-6"]) == 0
    assert "Good matches" in capsys.readouterr().out


@pytest.mark.parametrize("flag,value,needle", [
    ("--k", "0.5", "k must be in"),
    ("--threshold", "0", "threshold must be positive"),
    ("--max-corners", "0", "max-corners must be positive"),
])
def test_cli_validates_flags(flag, value, needle, scene_a, tmp_path, capsys):
    path = tmp_path / "a.png"
    cv2.imwrite(str(path), scene_a)
    assert main(["--file", str(path), flag, value]) == 2
    assert needle in capsys.readouterr().err


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "ghost.png")]) == 2
    assert "image not found" in capsys.readouterr().err


def test_cli_json_export(scene_a, tmp_path):
    path = tmp_path / "a.png"
    out = tmp_path / "report.json"
    cv2.imwrite(str(path), scene_a)
    assert main(["--file", str(path), "--threshold", "1e-6",
                 "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["stats"]["harris"]["corners"] > 0


def test_data_dir_contains_bundled_samples():
    for name in ("checkerboard.png", "scene_a.png", "scene_b.png"):
        assert (DATA_DIR / name).is_file()
