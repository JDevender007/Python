"""Tests for the Edge Detector project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from edges import (  # noqa: E402
    ASCII_WIDTH,
    DATA_DIR,
    LAPLACIAN,
    METHODS,
    PREWITT_X,
    SOBEL_X,
    EdgeError,
    analyse,
    ascii_map,
    bundle_samples,
    canny_edges,
    convolve2d,
    edge_mask,
    generate_samples,
    jaccard,
    laplacian,
    load_image,
    magnitude,
    prewitt,
    render_report,
    run_demo,
    save_image,
    sobel,
    threshold_mask,
    to_dict,
    validate_thresholds,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHAPES = PROJECT_ROOT / "data" / "shapes.png"


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def shapes() -> np.ndarray:
    return load_image(SHAPES)


@pytest.fixture(scope="module")
def samples() -> dict[str, np.ndarray]:
    return generate_samples()


def _binary(path: Path, text: str = "definitely not an image") -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Image loading and validation
# --------------------------------------------------------------------------- #
def test_bundled_samples_load():
    expected = {"gradient_ramp": (64, 64), "shapes": (160, 160),
                "noisy_step": (128, 128)}
    for name, shape in expected.items():
        image = load_image(DATA_DIR / f"{name}.png")
        assert image.shape == shape
        assert image.dtype == np.float64
        assert 0.0 <= image.min() and image.max() <= 255.0


def test_load_missing_file(tmp_path):
    with pytest.raises(EdgeError, match="file not found"):
        load_image(tmp_path / "nope.png")


def test_load_undecodable_file(tmp_path):
    with pytest.raises(EdgeError, match="could not decode image"):
        load_image(_binary(tmp_path / "garbage.png"))


def test_load_too_small_image(tmp_path):
    path = tmp_path / "tiny.png"
    assert cv2.imwrite(str(path), np.zeros((4, 4), dtype=np.uint8))
    with pytest.raises(EdgeError, match="image too small"):
        load_image(path)


def test_load_converts_colour_to_grey(tmp_path):
    bgr = np.zeros((32, 32, 3), dtype=np.uint8)
    bgr[..., 0] = 255           # blue channel only
    path = tmp_path / "colour.png"
    assert cv2.imwrite(str(path), bgr)
    image = load_image(path)
    assert image.ndim == 2
    assert image.shape == (32, 32)


def test_save_image_roundtrip(tmp_path):
    source = np.arange(64, dtype=float).reshape(8, 8) * 2
    path = save_image(tmp_path / "round.png", source)
    assert path.is_file()
    assert np.array_equal(load_image(path), source)


# --------------------------------------------------------------------------- #
# Convolution and kernels
# --------------------------------------------------------------------------- #
def test_convolve_identity_kernel():
    image = np.arange(25, dtype=float).reshape(5, 5)
    assert np.allclose(convolve2d(image, np.ones((1, 1))), image)


def test_convolve_impulse_response():
    image = np.zeros((5, 5))
    image[2, 2] = 1.0
    out = convolve2d(image, SOBEL_X)
    assert np.allclose(out[1:4, 1:4], SOBEL_X[::-1, ::-1])
    assert np.isclose(out[0, 0], 0.0)   # no wrap-around at the corner


def test_convolve_validation():
    image = np.ones((9, 9))
    with pytest.raises(EdgeError, match="expected a 2-D image"):
        convolve2d(np.ones((4, 4, 3)), SOBEL_X)
    with pytest.raises(EdgeError, match="kernel must be square"):
        convolve2d(image, np.ones((3, 4)))
    with pytest.raises(EdgeError, match="kernel must have odd size"):
        convolve2d(image, np.ones((2, 2)))
    with pytest.raises(EdgeError, match="kernel must be finite"):
        convolve2d(image, np.full((3, 3), np.nan))
    with pytest.raises(EdgeError, match="image must be finite"):
        convolve2d(np.full((9, 9), np.inf), SOBEL_X)
    with pytest.raises(EdgeError, match="image smaller than kernel"):
        convolve2d(np.ones((2, 2)), SOBEL_X)


def test_kernel_values():
    assert SOBEL_X.shape == (3, 3) and SOBEL_X.sum() == 0
    assert SOBEL_X[1].tolist() == [-2.0, 0.0, 2.0]
    assert PREWITT_X.sum() == 0 and np.abs(PREWITT_X).sum() == 6
    assert LAPLACIAN.sum() == 0 and LAPLACIAN[1, 1] == -4.0


# --------------------------------------------------------------------------- #
# From-scratch detectors vs cv2
# --------------------------------------------------------------------------- #
def test_ramp_has_analytic_slopes(samples):
    ramp = samples["gradient_ramp"]
    gx, gy = sobel(ramp)
    inner = (slice(4, -4), slice(4, -4))
    assert np.allclose(gx[inner], 32.0)      # 8 * slope(4)
    assert np.allclose(gy[inner], 0.0)
    assert np.allclose(laplacian(ramp)[inner], 0.0)


def test_prewitt_ramp_has_analytic_slopes(samples):
    ramp = samples["gradient_ramp"]
    gx, gy = prewitt(ramp)
    inner = (slice(4, -4), slice(4, -4))
    assert np.allclose(gx[inner], 24.0)      # 6 * slope(4)
    assert np.allclose(gy[inner], 0.0)


def test_sobel_matches_cv2(shapes):
    gx, gy = sobel(shapes)
    assert np.allclose(gx, cv2.Sobel(shapes, cv2.CV_64F, 1, 0, ksize=3),
                       atol=1e-6)
    assert np.allclose(gy, cv2.Sobel(shapes, cv2.CV_64F, 0, 1, ksize=3),
                       atol=1e-6)


def test_prewitt_matches_cv2(shapes):
    gx, _ = prewitt(shapes)
    expected = cv2.filter2D(shapes, cv2.CV_64F, PREWITT_X,
                            borderType=cv2.BORDER_REFLECT_101)
    assert np.allclose(gx, expected, atol=1e-6)


def test_laplacian_matches_cv2(shapes):
    # cv2's ksize=1 Laplacian is the unsmoothed 4-neighbour kernel
    assert np.allclose(laplacian(shapes),
                       cv2.Laplacian(shapes, cv2.CV_64F, ksize=1),
                       atol=1e-6)


def test_magnitude(shapes):
    gx, gy = sobel(shapes)
    mag = magnitude(gx, gy)
    assert mag.shape == shapes.shape
    assert (mag >= 0).all()
    assert np.allclose(mag, np.sqrt(gx ** 2 + gy ** 2))


def test_magnitude_shape_mismatch():
    with pytest.raises(EdgeError, match="same shape"):
        magnitude(np.ones((4, 4)), np.ones((5, 5)))


# --------------------------------------------------------------------------- #
# Thresholding and Canny
# --------------------------------------------------------------------------- #
def test_threshold_mask_basic():
    values = np.array([[0.0, 5.0], [10.0, 20.0]])
    mask = threshold_mask(values, 6.0)
    assert mask.dtype == bool
    assert mask.tolist() == [[False, False], [True, True]]


def test_threshold_mask_validation():
    with pytest.raises(EdgeError, match="expected a 2-D array"):
        threshold_mask(np.ones((2, 2, 2)), 1.0)
    with pytest.raises(EdgeError, match="threshold must be >= 0"):
        threshold_mask(np.ones((2, 2)), -1.0)
    with pytest.raises(EdgeError, match="values must be finite"):
        threshold_mask(np.array([[np.nan, 1.0], [1.0, 1.0]]), 1.0)


def test_canny_returns_boolean_mask(shapes):
    mask = canny_edges(shapes, 50, 150)
    assert mask.dtype == bool
    assert mask.shape == shapes.shape
    assert 100 < int(mask.sum()) < mask.size // 2


def test_canny_validation(shapes):
    with pytest.raises(EdgeError, match=r"low \(150\.0\) must be < high"):
        canny_edges(shapes, 150.0, 50.0)
    with pytest.raises(EdgeError, match="low must be in 0..255"):
        canny_edges(shapes, -5, 50)
    with pytest.raises(EdgeError, match="high must be in 0..255"):
        canny_edges(shapes, 50, 400)
    with pytest.raises(EdgeError, match="expected a 2-D image"):
        canny_edges(np.ones((4, 4, 3)), 50, 150)


def test_validate_thresholds():
    validate_thresholds(50, 150, 40)          # no raise
    with pytest.raises(EdgeError, match="threshold must be > 0"):
        validate_thresholds(50, 150, 0)
    with pytest.raises(EdgeError, match="low must be in 0..255"):
        validate_thresholds(-1, 150, 40)
    with pytest.raises(EdgeError, match="high must be in 0..255"):
        validate_thresholds(50, 300, 40)


# --------------------------------------------------------------------------- #
# Dispatch and agreement metrics
# --------------------------------------------------------------------------- #
def test_edge_mask_unknown_method(shapes):
    with pytest.raises(EdgeError, match="unknown method"):
        edge_mask("roberts", shapes)


def test_edge_mask_all_methods(shapes):
    for method in METHODS:
        mask = edge_mask(method, shapes)
        assert mask.dtype == bool
        assert mask.shape == shapes.shape
        assert mask.sum() > 0


def test_jaccard_values():
    a = np.array([[True, False]])
    b = np.array([[True, True]])
    assert jaccard(a, a) == 1.0
    assert jaccard(a, ~a) == 0.0
    assert jaccard(a, b) == 0.5
    empty = np.zeros((3, 3), dtype=bool)
    assert jaccard(empty, empty) == 1.0


def test_jaccard_shape_mismatch():
    with pytest.raises(EdgeError, match="same shape"):
        jaccard(np.zeros((2, 2), bool), np.zeros((3, 3), bool))


# --------------------------------------------------------------------------- #
# ASCII rendering
# --------------------------------------------------------------------------- #
def test_ascii_map_width(shapes):
    mask = edge_mask("sobel", shapes, threshold=40)
    lines = ascii_map(mask).splitlines()
    assert all(len(line) == ASCII_WIDTH for line in lines)
    assert len(lines) > 4
    assert "#" in ascii_map(mask)


def test_ascii_map_validation():
    with pytest.raises(EdgeError, match="mask is empty"):
        ascii_map(np.zeros((0, 0), dtype=bool))
    with pytest.raises(EdgeError, match="expected a 2-D mask"):
        ascii_map(np.ones(4, dtype=bool))
    with pytest.raises(EdgeError, match="width must be >= 4"):
        ascii_map(np.ones((4, 4), dtype=bool), width=2)


# --------------------------------------------------------------------------- #
# Procedural sample data
# --------------------------------------------------------------------------- #
def test_generate_samples_deterministic():
    first, second = generate_samples(), generate_samples()
    assert set(first) == {"gradient_ramp", "shapes", "noisy_step"}
    for name in first:
        assert np.array_equal(first[name], second[name]), name


def test_generate_samples_ranges(samples):
    for name, image in samples.items():
        assert image.ndim == 2, name
        assert image.min() >= 0.0 and image.max() <= 255.0, name
    # the noisy step really is bimodal
    step = samples["noisy_step"]
    assert step[:, :40].mean() < 60 and step[:, -40:].mean() > 190


def test_bundled_pngs_match_generator(samples):
    for name, image in samples.items():
        loaded = load_image(DATA_DIR / f"{name}.png")
        assert np.array_equal(loaded, np.round(image)), \
            f"{name}.png does not match the generator"


def test_bundle_samples_rewrites(tmp_path):
    written = bundle_samples(tmp_path)
    assert len(written) == 3
    for path in written:
        assert path.is_file()
    assert np.array_equal(load_image(tmp_path / "shapes.png"),
                          np.round(generate_samples()["shapes"]))


# --------------------------------------------------------------------------- #
# Analysis, reporting
# --------------------------------------------------------------------------- #
def test_analyse_all_methods(shapes):
    result = analyse(shapes, method="all")
    assert set(result["masks"]) == set(METHODS)
    assert set(result["stats"]) == set(METHODS)
    for stat in result["stats"].values():
        assert 0 <= stat["edge_pixels"] <= shapes.size
        assert 0.0 <= stat["fraction"] <= 1.0


def test_analyse_reports_canny_agreement(shapes):
    result = analyse(shapes, method="sobel", threshold=40)
    assert "jaccard_vs_canny" in result["stats"]["sobel"]
    assert 0.0 < result["stats"]["sobel"]["jaccard_vs_canny"] <= 1.0


def test_render_report_sections(shapes):
    result = analyse(shapes, method="all")
    text = render_report(result, shapes, "shapes.png", "all")
    assert "EDGE DETECTOR" in text
    assert "shapes.png (160x160" in text
    assert "ASCII preview" in text
    for method in METHODS:
        assert f"{method}" in text


def test_to_dict_payload(shapes):
    result = analyse(shapes, method="canny")
    payload = to_dict(result, "shapes.png", shapes.shape)
    json.dumps(payload)
    assert payload["image"] == "shapes.png"
    assert payload["width"] == 160 and payload["height"] == 160
    assert set(payload["methods"]) == {"canny"}


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Verified 3 bundled samples" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_data(tmp_path):
    with pytest.raises(EdgeError, match="bundled sample"):
        run_demo(data_dir=tmp_path)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_file_sobel(capsys):
    assert main(["--file", str(SHAPES), "--method", "sobel"]) == 0
    out = capsys.readouterr().out
    assert "edge pixels" in out and "Done." in out


def test_cli_file_canny_quiet(capsys):
    assert main(["--file", str(SHAPES), "--method", "canny",
                 "--low", "60", "--high", "180", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_file_all_with_json(tmp_path, capsys):
    report = tmp_path / "report.json"
    assert main(["--file", str(SHAPES), "--method", "all",
                 "--json", str(report)]) == 0
    out = capsys.readouterr().out
    assert "Wrote" in out and "Done." in out
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert set(payload["methods"]) == set(METHODS)
    assert payload["image"] == "shapes.png"


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.png")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_undecodable_file(tmp_path, capsys):
    bad = _binary(tmp_path / "bad.png")
    assert main(["--file", str(bad)]) == 2
    assert "could not decode image" in capsys.readouterr().err


def test_cli_bad_thresholds_fail_fast(tmp_path, capsys):
    # the file does not exist: seeing the threshold error proves the flags
    # are validated before any image work happens
    assert main(["--file", str(tmp_path / "missing.png"),
                 "--low", "150", "--high", "50"]) == 2
    assert "must be < high" in capsys.readouterr().err


def test_cli_bad_threshold_value(capsys):
    assert main(["--file", str(SHAPES), "--threshold", "0"]) == 2
    assert "threshold must be > 0" in capsys.readouterr().err


def test_cli_requires_action():
    with pytest.raises(SystemExit):
        main([])


def test_cli_rejects_unknown_method():
    with pytest.raises(SystemExit):
        main(["--file", str(SHAPES), "--method", "roberts"])


def test_project_has_sample_data():
    for name in generate_samples():
        assert (PROJECT_ROOT / "data" / f"{name}.png").is_file()
    assert DATA_DIR == PROJECT_ROOT / "data"
