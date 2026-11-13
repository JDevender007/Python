"""Tests for the Geometric Transforms project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from geometry import (  # noqa: E402
    CHECKER_IMG,
    EDGE_MODES,
    INTERPOLATIONS,
    MAX_DIM,
    MIN_DIM,
    SHAPES_IMG,
    GeoError,
    affine_warp,
    ascii_thumb,
    compose,
    image_center,
    image_stats,
    load_image,
    mse,
    psnr,
    rotate,
    rotation_matrix,
    run_demo,
    save_image,
    scale,
    scaling_matrix,
    translate,
    translation_matrix,
)
from main import main, parse_translate  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def checker():
    return load_image(CHECKER_IMG)


@pytest.fixture(scope="module")
def lattice():
    return np.arange(25, dtype=np.uint8).reshape(5, 5)


@pytest.fixture()
def ramp():
    return np.array([[0, 10, 20], [30, 40, 50], [60, 70, 80]],
                    dtype=np.uint8)


@pytest.fixture()
def sample_png(tmp_path):
    """A 32x32 gradient PNG available for CLI tests."""
    image = np.tile(np.arange(32, dtype=np.uint8) * 8, (32, 1))
    path = tmp_path / "sample.png"
    save_image(image, path)
    return path


# --------------------------------------------------------------------------- #
# Matrices
# --------------------------------------------------------------------------- #
def test_translation_matrix_is_an_inverse_map():
    matrix = translation_matrix(3.0, -4.0)
    assert matrix[0, 2] == pytest.approx(-3.0)
    assert matrix[1, 2] == pytest.approx(4.0)
    assert matrix[2].tolist() == [0.0, 0.0, 1.0]


def test_translation_matrix_rejects_non_finite():
    with pytest.raises(GeoError, match="translation must be finite"):
        translation_matrix(float("inf"), 0.0)


def test_rotation_matrix_zero_is_identity():
    assert np.allclose(rotation_matrix(0.0, (10.0, 20.0)), np.eye(3))


def test_rotation_matrix_fixes_its_center():
    matrix = rotation_matrix(37.0, (10.0, 20.0))
    center = np.array([10.0, 20.0, 1.0])
    assert np.allclose(matrix @ center, center)


def test_rotation_matrix_round_trip():
    forward = rotation_matrix(25.0, (4.0, 4.0))
    back = rotation_matrix(-25.0, (4.0, 4.0))
    assert np.allclose(forward @ back, np.eye(3), atol=1e-12)


def test_rotation_matrix_rejects_non_finite():
    with pytest.raises(GeoError, match="angle must be finite"):
        rotation_matrix(float("nan"), (0.0, 0.0))


def test_scaling_matrix_unit_scale_is_identity():
    assert np.allclose(scaling_matrix(1.0, (5.0, 5.0)), np.eye(3))


def test_scaling_matrix_inverts_the_factor():
    matrix = scaling_matrix(4.0, (0.0, 0.0))
    assert matrix[0, 0] == pytest.approx(0.25)
    assert matrix[1, 1] == pytest.approx(0.25)


def test_scaling_matrix_fixes_its_center():
    matrix = scaling_matrix(2.5, (3.0, 7.0))
    center = np.array([3.0, 7.0, 1.0])
    assert np.allclose(matrix @ center, center)


@pytest.mark.parametrize("factor", [0.0, -1.0, float("nan")])
def test_scaling_matrix_rejects_bad_factors(factor):
    with pytest.raises(GeoError, match="scale must be > 0"):
        scaling_matrix(factor, (0.0, 0.0))


def test_compose_needs_a_matrix():
    with pytest.raises(GeoError, match="compose needs at least one matrix"):
        compose()


def test_compose_of_one_matrix_is_that_matrix():
    matrix = translation_matrix(2.0, 3.0)
    assert np.allclose(compose(matrix), matrix)


def test_compose_multiplies_left_to_right():
    first = translation_matrix(2.0, 0.0)
    second = translation_matrix(0.0, 3.0)
    assert np.allclose(compose(first, second), first @ second)


def test_compose_accepts_a_2x3_matrix():
    matrix = np.array([[1.0, 0.0, -2.0], [0.0, 1.0, 0.0]])
    assert compose(matrix).shape == (3, 3)


def test_compose_rejects_a_bad_shape():
    with pytest.raises(GeoError, match=r"matrix must be 2x3 or 3x3"):
        compose(np.eye(4))


def test_compose_rejects_a_non_finite_matrix():
    bad = np.eye(3)
    bad[0, 0] = float("nan")
    with pytest.raises(GeoError, match="matrix must be finite"):
        compose(bad)


def test_compose_rejects_a_singular_matrix():
    singular = np.array([[1.0, 2.0, 0.0], [2.0, 4.0, 0.0], [0.0, 0.0, 1.0]])
    with pytest.raises(GeoError, match="singular"):
        compose(singular)


def test_compose_rejects_a_bad_bottom_row():
    bad = np.eye(3)
    bad[2, 0] = 1.0
    with pytest.raises(GeoError, match="bottom row must be 0 0 1"):
        compose(bad)


# --------------------------------------------------------------------------- #
# Warp
# --------------------------------------------------------------------------- #
def test_identity_warp_is_exact(checker):
    assert np.array_equal(affine_warp(checker, np.eye(3)), checker)


def test_identity_warp_is_exact_for_nearest(checker):
    assert np.array_equal(affine_warp(checker, np.eye(3), order="nearest"),
                          checker)


def test_warp_preserves_shape_and_dtype(checker):
    out = rotate(checker, 33.0)
    assert out.shape == checker.shape
    assert out.dtype == np.uint8


def test_warp_rejects_a_non_2d_image():
    with pytest.raises(GeoError, match="expected a 2D image"):
        affine_warp(np.zeros((4, 4, 3), dtype=np.uint8), np.eye(3))


def test_warp_rejects_an_empty_image():
    with pytest.raises(GeoError, match="image must not be empty"):
        affine_warp(np.zeros((0, 0), dtype=np.uint8), np.eye(3))


def test_warp_rejects_an_unknown_interpolation():
    with pytest.raises(GeoError, match="unknown interpolation"):
        affine_warp(np.zeros((4, 4), dtype=np.uint8), np.eye(3),
                    order="cubic")


def test_warp_rejects_an_unknown_edge_mode():
    with pytest.raises(GeoError, match="unknown edge mode"):
        affine_warp(np.zeros((4, 4), dtype=np.uint8), np.eye(3), mode="smear")


@pytest.mark.parametrize("mode", EDGE_MODES)
def test_every_edge_mode_produces_a_legal_image(checker, mode):
    out = translate(checker, 11.5, -7.25, mode=mode)
    assert out.shape == checker.shape
    assert out.dtype == np.uint8


@pytest.mark.parametrize("order", INTERPOLATIONS)
def test_every_interpolation_produces_a_legal_image(checker, order):
    out = rotate(checker, 20.0, order=order)
    assert out.shape == checker.shape
    assert out.min() >= 0 and out.max() <= 255


def test_nearest_only_emits_original_levels(checker):
    out = rotate(checker, 45.0, order="nearest")
    assert set(np.unique(out)) <= set(np.unique(checker))


def test_constant_mode_zeros_uncovered_pixels(checker):
    shifted = translate(checker, 40, 0, mode="constant")
    assert np.all(shifted[:, :40] == 0)


def test_constant_mode_keeps_the_covered_region_exact(checker):
    shifted = translate(checker, 40, 0, mode="constant")
    assert np.array_equal(shifted[:, 40:], checker[:, :88])


def test_replicate_mode_repeats_the_edge(ramp):
    shifted = translate(ramp, 5, 0, mode="replicate")
    assert shifted.tolist() == [[0, 0, 0], [30, 30, 30], [60, 60, 60]]


def test_wrap_mode_translate_matches_np_roll(lattice):
    assert np.array_equal(translate(lattice, 2, -1, mode="wrap"),
                          np.roll(lattice, (-1, 2), axis=(0, 1)))


def test_wrap_mode_translate_matches_np_roll_nearest(lattice):
    assert np.array_equal(translate(lattice, 2, -1, order="nearest",
                                    mode="wrap"),
                          np.roll(lattice, (-1, 2), axis=(0, 1)))


def test_bilinear_midpoint_blend_is_exact(ramp):
    half = translate(ramp, -0.5, 0, mode="replicate")
    assert int(half[0, 0]) == 5
    assert int(half[0, 1]) == 15


def test_quarter_turn_matches_np_rot90(lattice):
    turned = affine_warp(lattice, rotation_matrix(90.0, (2.0, 2.0)))
    assert np.array_equal(turned, np.rot90(lattice, 1))


def test_quarter_turn_round_trips(lattice):
    twice = rotate(rotate(lattice, 90.0), 90.0)
    assert np.array_equal(twice, np.rot90(lattice, 2))


def test_warp_is_deterministic(checker):
    assert np.array_equal(rotate(checker, 45.0), rotate(checker, 45.0))


def test_scale_by_one_is_exact(checker):
    assert np.array_equal(scale(checker, 1.0), checker)


def test_translate_by_zero_is_exact(checker):
    assert np.array_equal(translate(checker, 0.0, 0.0), checker)


def test_rotate_by_zero_is_exact(checker):
    assert np.array_equal(rotate(checker, 0.0), checker)


# --------------------------------------------------------------------------- #
# Image IO
# --------------------------------------------------------------------------- #
def test_image_center():
    assert image_center(np.zeros((5, 9), dtype=np.uint8)) == (4.0, 2.0)


def test_load_missing_file(tmp_path):
    with pytest.raises(GeoError, match="file not found"):
        load_image(tmp_path / "ghost.png")


def test_load_rejects_a_non_image(tmp_path):
    path = tmp_path / "junk.png"
    path.write_text("this is not a png", encoding="utf-8")
    with pytest.raises(GeoError, match="could not read image"):
        load_image(path)


def test_load_rejects_a_tiny_image(tmp_path):
    path = tmp_path / "tiny.png"
    save_image(np.zeros((MIN_DIM - 1, MIN_DIM), dtype=np.uint8), path)
    with pytest.raises(GeoError, match="image too small"):
        load_image(path)


def test_load_rejects_a_huge_image(tmp_path):
    path = tmp_path / "huge.png"
    save_image(np.zeros((MAX_DIM + 1, MIN_DIM), dtype=np.uint8), path)
    with pytest.raises(GeoError, match="image too large"):
        load_image(path)


def test_save_and_load_round_trip(tmp_path):
    image = np.tile(np.arange(8, dtype=np.uint8) * 30, (8, 1))
    path = save_image(image, tmp_path / "nested" / "out.png")
    assert path.is_file()
    assert np.array_equal(load_image(path), image)


def test_save_clips_out_of_range_values(tmp_path):
    path = tmp_path / "clipped.png"
    image = np.full((MIN_DIM, MIN_DIM), -50, dtype=np.int64)
    image[0, 0] = 400
    save_image(image, path)
    loaded = load_image(path)
    assert loaded[1, 1] == 0
    assert loaded[0, 0] == 255


def test_save_rejects_a_non_2d_array(tmp_path):
    with pytest.raises(GeoError, match="expected a 2D array to save"):
        save_image(np.zeros((2, 2, 2), dtype=np.uint8), tmp_path / "x.png")


# --------------------------------------------------------------------------- #
# ASCII preview
# --------------------------------------------------------------------------- #
def test_ascii_thumb_line_count_and_width():
    art = ascii_thumb(np.zeros((32, 64), dtype=np.uint8), cols=16)
    lines = art.splitlines()
    assert len(lines) == 8
    assert all(len(line) == 16 for line in lines)


def test_ascii_thumb_is_deterministic(checker):
    assert ascii_thumb(checker) == ascii_thumb(checker)


def test_ascii_thumb_uses_the_full_shade_ramp(checker):
    art = ascii_thumb(checker, cols=32)
    distinct = set(art.replace("\n", ""))
    assert len(distinct) > 1


def test_ascii_thumb_handles_a_flat_image():
    art = ascii_thumb(np.zeros((16, 16), dtype=np.uint8), cols=8)
    assert set(art.replace("\n", "")) == {" "}
    assert len(art.splitlines()) == 4


def test_ascii_thumb_rejects_too_few_columns(checker):
    with pytest.raises(GeoError, match="cols must be >= 4"):
        ascii_thumb(checker, cols=3)


def test_ascii_thumb_rejects_an_empty_image():
    with pytest.raises(GeoError, match="non-empty 2D array"):
        ascii_thumb(np.zeros((0, 0), dtype=np.uint8))


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def test_image_stats_values(checker):
    stats = image_stats(checker)
    assert set(stats) == {"mean", "std", "min", "max", "pixels"}
    assert stats["pixels"] == checker.size
    assert stats["min"] == int(checker.min())
    assert stats["max"] == int(checker.max())


def test_image_stats_rejects_a_non_2d_array():
    with pytest.raises(GeoError, match="non-empty 2D array"):
        image_stats(np.zeros((2, 2, 2), dtype=np.uint8))


def test_mse_of_identical_images_is_zero(checker):
    assert mse(checker, checker) == 0.0


def test_mse_computes_the_mean_square(checker):
    brighter = np.clip(checker.astype(np.int32) + 10, 0, 255).astype(np.uint8)
    assert mse(checker, brighter) == pytest.approx(100.0)


def test_mse_rejects_a_shape_mismatch(checker):
    with pytest.raises(GeoError, match="shape mismatch"):
        mse(checker, checker[:10])


def test_psnr_of_identical_images_is_infinite(checker):
    assert psnr(checker, checker) == float("inf")


def test_psnr_matches_the_closed_form(checker):
    brighter = np.clip(checker.astype(np.int32) + 10, 0, 255).astype(np.uint8)
    assert psnr(checker, brighter) == pytest.approx(
        10.0 * math.log10(255.0 ** 2 / 100.0))


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    assert capsys.readouterr().out == first


def test_run_demo_reports_the_compose_order_check(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Compose order check" in out
    assert "reversed order" in out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_parse_translate_valid():
    assert parse_translate("10,-5") == (10.0, -5.0)


def test_parse_translate_accepts_spaces():
    assert parse_translate(" 3 , 4 ") == (3.0, 4.0)


def test_parse_translate_rejects_one_value():
    with pytest.raises(Exception, match="two comma-separated numbers"):
        parse_translate("10")


def test_parse_translate_rejects_text():
    with pytest.raises(Exception, match="not a number"):
        parse_translate("left,5")


def test_parse_translate_rejects_nan():
    with pytest.raises(Exception, match="must be finite"):
        parse_translate("nan,5")


def test_cli_demo(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_requires_a_mode():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_requires_a_transform():
    with pytest.raises(SystemExit) as exc:
        main(["--file", str(CHECKER_IMG)])
    assert exc.value.code == 2


def test_cli_rotates(sample_png, capsys):
    assert main(["--file", str(sample_png), "--rotate", "30"]) == 0
    out = capsys.readouterr().out
    assert "Transformed sample.png" in out
    assert "rotate 30" in out


def test_cli_scales(sample_png, capsys):
    assert main(["--file", str(sample_png), "--scale", "1.5"]) == 0
    assert "scale 1.5" in capsys.readouterr().out


def test_cli_translates(sample_png, capsys):
    assert main(["--file", str(sample_png), "--translate", "4,-2"]) == 0
    assert "translate" in capsys.readouterr().out


def test_cli_writes_the_output_image(sample_png, tmp_path):
    out = tmp_path / "out" / "rot.png"
    assert main(["--file", str(sample_png), "--rotate", "15",
                 "--out", str(out), "--quiet"]) == 0
    assert out.is_file()
    assert load_image(out).shape == load_image(sample_png).shape


def test_cli_writes_json(sample_png, tmp_path):
    out = tmp_path / "stats.json"
    assert main(["--file", str(sample_png), "--rotate", "20",
                 "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["rotate"] == 20.0
    assert payload["interp"] == "bilinear"
    assert payload["edges"] == "reflect"
    assert payload["pixels"] == 32 * 32


def test_cli_combines_transform_flags(sample_png, capsys):
    assert main(["--file", str(sample_png), "--rotate", "10", "--scale",
                 "1.2", "--translate", "3,3"]) == 0
    out = capsys.readouterr().out
    assert "rotate 10" in out and "scale 1.2" in out and "translate" in out


def test_cli_honours_interpolation_and_edges(sample_png, tmp_path):
    out = tmp_path / "s.json"
    assert main(["--file", str(sample_png), "--rotate", "10", "--interp",
                 "nearest", "--edges", "constant", "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["interp"] == "nearest"
    assert payload["edges"] == "constant"


def test_cli_rejects_a_bad_scale(sample_png, capsys):
    assert main(["--file", str(sample_png), "--scale", "0"]) == 2
    assert "scale must be > 0" in capsys.readouterr().err


def test_cli_rejects_a_nan_rotation(sample_png, capsys):
    assert main(["--file", str(sample_png), "--rotate", "nan"]) == 2
    assert "rotate must be a finite number" in capsys.readouterr().err


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "ghost.png"),
                 "--rotate", "10"]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_quiet_suppresses_the_report(sample_png, capsys):
    assert main(["--file", str(sample_png), "--rotate", "10",
                 "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_bundled_samples_exist():
    assert CHECKER_IMG.is_file()
    assert SHAPES_IMG.is_file()
