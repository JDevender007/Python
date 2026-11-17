"""Tests for the Convolution Filters project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from filters import (  # noqa: E402
    DEMO_IMG,
    EDGE_MODES,
    FILTER_NAMES,
    MAX_DIM,
    MIN_DIM,
    SHADES,
    ImgError,
    apply_filter,
    ascii_thumb,
    box_kernel,
    convolve,
    convolve_separable,
    emboss_kernel,
    filter_report,
    gaussian_kernel,
    gaussian_kernel_1d,
    get_kernel,
    load_image,
    mse,
    pad_image,
    psnr,
    run_demo,
    save_image,
    sharpen_kernel,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAMP_IMG = PROJECT_ROOT / "data" / "gradient_64.png"


@pytest.fixture(scope="module")
def shapes() -> np.ndarray:
    return load_image(DEMO_IMG)


@pytest.fixture(scope="module")
def ramp() -> np.ndarray:
    return load_image(RAMP_IMG)


def _naive_convolve(image: np.ndarray, kernel: np.ndarray,
                    mode: str) -> np.ndarray:
    """Independent loop implementation (zero-padded reference)."""
    height, width = image.shape
    kernel_h, kernel_w = kernel.shape
    flipped = kernel[::-1, ::-1]
    out = np.zeros_like(image, dtype=np.float64)
    for y in range(height):
        for x in range(width):
            total = 0.0
            for i in range(kernel_h):
                for j in range(kernel_w):
                    yy, xx = y + i - kernel_h // 2, x + j - kernel_w // 2
                    if 0 <= yy < height and 0 <= xx < width:
                        value = float(image[yy, xx])
                    elif mode == "constant":
                        value = 0.0
                    else:                       # replicate at the border
                        value = float(image[np.clip(yy, 0, height - 1),
                                            np.clip(xx, 0, width - 1)])
                    total += value * float(flipped[i, j])
            out[y, x] = total
    return out


# --------------------------------------------------------------------------- #
# Loading and saving
# --------------------------------------------------------------------------- #
def test_load_bundled_shapes(shapes):
    assert shapes.shape == (128, 128)
    assert shapes.dtype == np.uint8
    assert shapes.min() == 30 and shapes.max() == 220


def test_load_gradient_ramp(ramp):
    assert ramp.shape == (64, 64)
    assert ramp[0, 0] == 0 and ramp[0, -1] == 255
    assert np.all(np.diff(ramp[0]) >= 0)


def test_load_unreadable_inputs(tmp_path):
    with pytest.raises(ImgError, match="not found"):
        load_image(tmp_path / "nope.png")
    fake = tmp_path / "fake.png"
    fake.write_text("this is not a png", encoding="utf-8")
    with pytest.raises(ImgError, match="could not read image"):
        load_image(fake)


def test_load_rejects_too_large(tmp_path):
    path = tmp_path / "wide.png"
    Image.fromarray(np.zeros((16, MAX_DIM + 88), dtype=np.uint8),
                    mode="L").save(path)
    with pytest.raises(ImgError, match="too large"):
        load_image(path)


def test_load_rejects_too_small(tmp_path):
    path = tmp_path / "tiny.png"
    Image.fromarray(np.zeros((MIN_DIM - 1, 16), dtype=np.uint8),
                    mode="L").save(path)
    with pytest.raises(ImgError, match="too small"):
        load_image(path)


def test_load_rgb_converts_to_grey(tmp_path):
    path = tmp_path / "red.png"
    red = np.zeros((16, 16, 3), dtype=np.uint8)
    red[..., 0] = 255
    Image.fromarray(red, mode="RGB").save(path)
    grey = load_image(path)
    assert grey.ndim == 2 and grey.dtype == np.uint8
    assert abs(int(grey.mean()) - 76) <= 2


def test_save_and_reload_roundtrip(tmp_path, shapes):
    target = save_image(shapes, tmp_path / "nested" / "out.png")
    assert target.is_file()
    assert np.array_equal(load_image(target), shapes)


def test_save_rejects_bad_array(tmp_path):
    with pytest.raises(ImgError, match="2D"):
        save_image(np.zeros((4, 4, 3)), tmp_path / "bad.png")


# --------------------------------------------------------------------------- #
# ASCII preview
# --------------------------------------------------------------------------- #
def test_ascii_thumb_shape(shapes):
    art = ascii_thumb(shapes, cols=48)
    lines = art.splitlines()
    assert lines and len(lines) <= 24
    assert all(len(line) == len(lines[0]) for line in lines)
    assert set(art.replace("\n", "")) <= set(SHADES)


def test_ascii_thumb_validates_input(shapes):
    with pytest.raises(ImgError, match="cols must be >= 4"):
        ascii_thumb(shapes, cols=2)
    with pytest.raises(ImgError, match="2D"):
        ascii_thumb(np.arange(10))


# --------------------------------------------------------------------------- #
# Kernels
# --------------------------------------------------------------------------- #
def test_box_kernel_sums_to_one():
    kernel = box_kernel(5)
    assert kernel.shape == (5, 5)
    assert kernel.sum() == pytest.approx(1.0, abs=1e-12)


def test_box_kernel_validates_size():
    with pytest.raises(ImgError, match="box size must be >= 1"):
        box_kernel(0)
    with pytest.raises(ImgError, match="box size must be"):
        box_kernel(-3)


def test_gaussian_1d_symmetric_and_normalised():
    kernel = gaussian_kernel_1d(1.5)
    assert kernel.size == 2 * int(np.ceil(4.5)) + 1
    assert np.allclose(kernel, kernel[::-1])
    assert kernel.sum() == pytest.approx(1.0, abs=1e-12)
    assert kernel[kernel.size // 2] == kernel.max()
    with pytest.raises(ImgError, match="sigma must be > 0"):
        gaussian_kernel_1d(0.0)
    with pytest.raises(ImgError, match="sigma must be > 0"):
        gaussian_kernel_1d(-2.0)


def test_gaussian_2d_sum_and_shapes():
    auto = gaussian_kernel(sigma=1.0)
    assert auto.sum() == pytest.approx(1.0, abs=1e-12)
    assert auto.shape[0] == auto.shape[1] == 2 * int(np.ceil(3.0)) + 1
    fixed = gaussian_kernel(size=7, sigma=0.8)
    assert fixed.shape == (7, 7)
    assert fixed.sum() == pytest.approx(1.0, abs=1e-12)


def test_gaussian_2d_validates_size():
    with pytest.raises(ImgError, match="positive odd number"):
        gaussian_kernel(size=4, sigma=1.0)
    with pytest.raises(ImgError, match="too small for sigma"):
        gaussian_kernel(size=3, sigma=3.0)


def test_sharpen_and_emboss_known_values():
    sharpen = sharpen_kernel()
    assert sharpen[1, 1] == 5.0
    assert sharpen.sum() == 1.0
    assert np.count_nonzero(sharpen) == 5
    emboss = emboss_kernel()
    assert emboss.sum() == 1.0
    assert emboss[0, 2] == 0.0 and emboss[2, 0] == 0.0
    assert emboss[0, 0] == -2.0 and emboss[2, 2] == 2.0   # dark -> light


def test_get_kernel_dispatch():
    assert get_kernel("box", size=3).shape == (3, 3)
    assert get_kernel("gaussian", sigma=1.0).ndim == 2
    assert get_kernel("sharpen").shape == (3, 3)
    assert get_kernel("emboss").shape == (3, 3)
    with pytest.raises(ImgError, match="unknown filter"):
        get_kernel("sobel")


# --------------------------------------------------------------------------- #
# Padding
# --------------------------------------------------------------------------- #
GRID = np.array([[1.0, 2.0, 3.0],
                 [4.0, 5.0, 6.0],
                 [7.0, 8.0, 9.0]])


def test_pad_constant_fills_zero():
    padded = pad_image(GRID, 1, "constant")
    assert padded.shape == (5, 5)
    assert padded[0, 0] == 0.0
    assert padded[1:4, 1:4].tolist() == GRID.tolist()


def test_pad_replicate_edges():
    padded = pad_image(GRID, 1, "replicate")
    assert padded.shape == (5, 5)
    assert padded[1:4, 1:4].tolist() == GRID.tolist()
    assert padded[0].tolist() == [1.0, 1.0, 2.0, 3.0, 3.0]
    assert padded[:, 0].tolist() == [1.0, 1.0, 4.0, 7.0, 7.0]
    assert padded[4, 4] == 9.0


def test_pad_reflect_values():
    padded = pad_image(GRID, 1, "reflect")
    assert padded.shape == (5, 5)
    assert padded[1, 1] == 1.0            # original corner still inside
    assert padded[0, 1] == 4.0            # row reflection
    assert padded[1, 0] == 2.0            # column reflection
    assert padded[0, 0] == 5.0            # diagonal reflection


def test_pad_wrap_values():
    padded = pad_image(GRID, 1, "wrap")
    assert padded[0, 0] == 9.0            # wraps to the far corner
    assert padded[4, 4] == 1.0            # wraps back to the near corner
    assert padded[1, 0] == 3.0            # column wrap: 1,2,3 -> 3,1,2,3,1


def test_pad_validates_mode_and_radius():
    with pytest.raises(ImgError, match="unknown edge mode"):
        pad_image(GRID, 1, "mirror")
    with pytest.raises(ImgError, match="radius must be >= 0"):
        pad_image(GRID, -1, "reflect")
    with pytest.raises(ImgError, match="must be smaller than the image"):
        pad_image(GRID, 3, "reflect")
    with pytest.raises(ImgError, match="2D"):
        pad_image(np.zeros(5), 1, "reflect")


# --------------------------------------------------------------------------- #
# Convolution core
# --------------------------------------------------------------------------- #
def test_convolve_delta_kernel_is_identity(shapes):
    kernel = np.zeros((3, 3))
    kernel[1, 1] = 1.0
    out = convolve(shapes.astype(float), kernel, "reflect")
    assert np.array_equal(out, shapes.astype(float))


def test_convolve_matches_naive_loop(shapes):
    image = shapes[:9, :9].astype(float)
    out = convolve(image, box_kernel(3), "constant")
    expected = _naive_convolve(image, box_kernel(3), "constant")
    assert np.abs(out - expected).max() < 1e-9


def test_convolve_cross_kernel_matches_manual_sum():
    image = GRID.copy()
    kernel = np.array([[0.0, 1.0, 0.0],
                       [1.0, 1.0, 1.0],
                       [0.0, 1.0, 0.0]])
    out = convolve(image, kernel, "constant")
    assert out[1, 1] == 25.0             # 5+2+8+4+6
    assert out[0, 0] == 7.0              # 1+0+4+0+2 (zero-padded)


def test_kernels_summing_to_one_preserve_constants(shapes):
    constant = np.full((24, 24), 77.0)
    for name in FILTER_NAMES:
        params = {"sigma": 1.0} if name == "gaussian" else {}
        kernel = get_kernel(name, **params)
        out = convolve(constant, kernel, "reflect")
        assert np.abs(out - 77.0).max() < 1e-9, name


def test_convolve_constant_mode_preserves_interior(shapes):
    constant = np.full((24, 24), 77.0)
    out = convolve(constant, box_kernel(3), "constant")
    assert np.abs(out[2:-2, 2:-2] - 77.0).max() < 1e-9
    assert out[0, 0] < 77.0              # zero padding darkens borders


def test_convolve_keeps_shape_and_float_dtype(shapes):
    out = convolve(shapes, gaussian_kernel(sigma=1.0), "reflect")
    assert out.shape == shapes.shape
    assert out.dtype == np.float64


def test_convolve_rejects_bad_inputs():
    with pytest.raises(ImgError, match="2D image"):
        convolve(np.zeros(4), box_kernel(3), "reflect")
    with pytest.raises(ImgError, match="non-empty 2D"):
        convolve(np.zeros((4, 4)), np.zeros((0, 3)), "reflect")
    with pytest.raises(ImgError, match="kernel must be finite"):
        convolve(np.zeros((6, 6)), np.full((3, 3), np.nan), "reflect")
    with pytest.raises(ImgError, match="unknown edge mode"):
        convolve(np.zeros((6, 6)), box_kernel(3), "edge")
    with pytest.raises(ImgError, match="too large for image"):
        convolve(np.zeros((4, 4)), box_kernel(9), "reflect")


def test_separable_matches_full_convolution(shapes):
    sigma = 1.5
    full = convolve(shapes.astype(float), gaussian_kernel(sigma=sigma),
                    "reflect")
    sep = convolve_separable(shapes.astype(float), gaussian_kernel_1d(sigma),
                             "reflect")
    assert np.abs(full - sep).max() < 1e-6
    assert np.abs(sep).max() <= 255.0 + 1e-9


def test_separable_matches_full_for_all_edge_modes(shapes):
    kernel_1d = gaussian_kernel_1d(1.0)
    for mode in EDGE_MODES:
        full = convolve(shapes.astype(float),
                        np.outer(kernel_1d, kernel_1d), mode)
        sep = convolve_separable(shapes.astype(float), kernel_1d, mode)
        assert np.abs(full - sep).max() < 1e-6, mode


def test_separable_validates_kernel():
    with pytest.raises(ImgError, match="odd length"):
        convolve_separable(np.zeros((8, 8)), np.ones(4), "reflect")
    with pytest.raises(ImgError, match="1D array"):
        convolve_separable(np.zeros((8, 8)), np.ones((3, 3)), "reflect")
    with pytest.raises(ImgError, match="2D image"):
        convolve_separable(np.zeros(8), np.ones(3), "reflect")
    with pytest.raises(ImgError, match="smaller than the image"):
        convolve_separable(np.zeros((4, 4)), np.ones(9), "reflect")


def test_edge_modes_differ_only_at_border(ramp):
    interior = (slice(2, -2), slice(2, -2))
    reference = apply_filter(ramp, "box", mode="constant", size=3)
    for mode in EDGE_MODES:
        filtered = apply_filter(ramp, "box", mode=mode, size=3)
        assert filtered.shape == ramp.shape
        if mode != "constant":
            assert np.array_equal(filtered[interior],
                                  reference[interior]), mode
    borders = [tuple(apply_filter(ramp, "box", mode=m, size=3)[0][:4])
               for m in EDGE_MODES]
    assert len(set(borders)) == len(EDGE_MODES), "borders should differ"


# --------------------------------------------------------------------------- #
# apply_filter / report / metrics
# --------------------------------------------------------------------------- #
def test_apply_filter_box_size_one_identity(shapes):
    assert np.array_equal(apply_filter(shapes, "box", size=1), shapes)


def test_apply_filter_returns_uint8_in_range(shapes):
    for name in FILTER_NAMES:
        params = {"sigma": 1.5} if name == "gaussian" else {}
        out = apply_filter(shapes, name, **params)
        assert out.dtype == np.uint8, name
        assert out.shape == shapes.shape, name
        assert 0 <= out.min() and out.max() <= 255, name


def test_apply_filter_unknown_name():
    with pytest.raises(ImgError, match="unknown filter"):
        apply_filter(np.zeros((8, 8), dtype=np.uint8), "sobel")


def test_apply_filter_bad_box_size():
    with pytest.raises(ImgError, match="box size must be >= 1"):
        apply_filter(np.zeros((8, 8), dtype=np.uint8), "box", size=0)


def test_gaussian_blur_reduces_contrast(ramp):
    blurred = apply_filter(ramp, "gaussian", sigma=1.0)
    assert float(blurred.std()) < float(ramp.std())


def test_sharpen_raises_contrast(shapes):
    sharpened = apply_filter(shapes, "sharpen")
    assert float(sharpened.std()) > float(shapes.std())


def test_psnr_known_values(shapes):
    # identical images -> infinite PSNR
    assert psnr(shapes, shapes) == float("inf")
    assert mse(shapes, shapes) == 0.0
    # constant difference of exactly 1 grey level -> 20*log10(255)
    a = np.full((8, 8), 100, dtype=np.uint8)
    b = np.full((8, 8), 101, dtype=np.uint8)
    assert mse(a, b) == pytest.approx(1.0)
    assert psnr(a, b) == pytest.approx(20 * np.log10(255.0), abs=1e-9)
    # symmetric and finite for genuinely different images
    other = apply_filter(shapes, "box", size=3)
    forward, backward = psnr(shapes, other), psnr(other, shapes)
    assert 0.0 < forward < 100.0
    assert forward == pytest.approx(backward)


def test_metrics_reject_shape_mismatch():
    with pytest.raises(ImgError, match="shape mismatch"):
        psnr(np.zeros((4, 4)), np.zeros((5, 5)))
    with pytest.raises(ImgError, match="same shape"):
        filter_report(np.zeros((4, 4)), np.zeros((4, 5)))


def test_filter_report_fields(shapes):
    stats = filter_report(shapes, apply_filter(shapes, "emboss"))
    assert set(stats) == {"mean", "std", "min", "max", "mse", "psnr_db"}
    assert 0 <= stats["min"] <= stats["max"] <= 255
    assert stats["mse"] > 0


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out
    assert "ASCII preview" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(ImgError, match="bundled sample"):
        run_demo(image_path=tmp_path / "nope.png")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""  # --quiet is silent


def test_cli_filter_gaussian(capsys):
    assert main(["--file", str(RAMP_IMG), "--filter", "gaussian",
                 "--sigma", "1.0"]) == 0
    out = capsys.readouterr().out
    assert "PSNR" in out and "Done." in out


def test_cli_box_with_wrap_and_json(tmp_path, capsys):
    json_path = tmp_path / "stats.json"
    assert main(["--file", str(RAMP_IMG), "--filter", "box", "--size", "5",
                 "--edges", "wrap", "--json", str(json_path),
                 "--quiet"]) == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["filter"] == "box"
    assert payload["edges"] == "wrap"
    assert payload["size"] == 5
    assert payload["sigma"] is None
    assert payload["psnr_db"] > 0


def test_cli_out_writes_png(tmp_path, capsys):
    out_path = tmp_path / "nested" / "filtered.png"
    assert main(["--file", str(RAMP_IMG), "--filter", "sharpen",
                 "--out", str(out_path)]) == 0
    assert out_path.is_file()
    assert load_image(out_path).shape == load_image(RAMP_IMG).shape
    assert "Wrote" in capsys.readouterr().out


def test_cli_missing_file_returns_2(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.png")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_bad_sigma_fast_fails(tmp_path, capsys):
    # even with a missing file, the flag is validated first
    assert main(["--file", str(tmp_path / "nope.png"),
                 "--filter", "gaussian", "--sigma", "0"]) == 2
    assert "--sigma must be > 0" in capsys.readouterr().err


def test_cli_bad_size_returns_2(capsys):
    assert main(["--file", str(RAMP_IMG), "--filter", "box",
                 "--size", "0"]) == 2
    assert "--size must be >= 1" in capsys.readouterr().err


def test_cli_usage_errors(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    capsys.readouterr()
    for argv in (["--file", str(RAMP_IMG), "--filter", "sobel"],
                 ["--file", str(RAMP_IMG), "--edges", "mirror"]):
        with pytest.raises(SystemExit) as bad:
            main(argv)
        assert bad.value.code == 2
        assert "invalid choice" in capsys.readouterr().err


def test_project_has_sample_data():
    assert DEMO_IMG.is_file()
    assert RAMP_IMG.is_file()
    assert DEMO_IMG.parent == PROJECT_ROOT / "data"
