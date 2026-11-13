"""Tests for the Image Segmentation project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from segmentation import (  # noqa: E402
    ASCII_WIDTH,
    DATA_DIR,
    MAX_CLUSTERS,
    MIN_CLUSTERS,
    MODES,
    SegError,
    analyse,
    ascii_map,
    component_sizes,
    connected_components,
    kmeans_segment,
    load_color_image,
    load_image,
    otsu_mask,
    otsu_threshold,
    render_report,
    run_demo,
    threshold_mask,
    to_dict,
    to_gray,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHAPES = PROJECT_ROOT / "data" / "otsu_shapes.png"
BLOBS = PROJECT_ROOT / "data" / "components.png"
COLOUR = PROJECT_ROOT / "data" / "color_blocks.png"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def make_gray(shape=(40, 40), low=20, high=210, split=20) -> np.ndarray:
    img = np.full(shape, low, dtype=np.uint8)
    img[:, split:] = high
    return img


def make_blocks(seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.zeros((30, 30, 3), dtype=np.uint8)
    img[:, :15] = (30, 30, 200)
    img[:, 15:] = (200, 30, 30)
    img = np.clip(img.astype(np.int16)
                  + rng.integers(-4, 5, img.shape, dtype=np.int16),
                  0, 255).astype(np.uint8)
    return img


@pytest.fixture(scope="module")
def gray() -> np.ndarray:
    return load_image(SHAPES)


@pytest.fixture(scope="module")
def colour() -> np.ndarray:
    return load_color_image(COLOUR)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_load_image_shape_and_dtype(gray):
    assert gray.ndim == 2
    assert gray.dtype == np.uint8
    assert gray.shape == (160, 160)


def test_load_image_missing(tmp_path):
    with pytest.raises(SegError, match="image not found"):
        load_image(tmp_path / "nope.png")


def test_load_image_undecodable(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_text("not a png", encoding="utf-8")
    with pytest.raises(SegError, match="could not decode"):
        load_image(bad)


def test_load_color_image_is_bgr(colour):
    assert colour.ndim == 3
    assert colour.shape[2] == 3
    assert colour.dtype == np.uint8


def test_load_color_image_missing(tmp_path):
    with pytest.raises(SegError, match="image not found"):
        load_color_image(tmp_path / "x.png")


def test_to_gray_passthrough(gray):
    assert to_gray(gray) is gray


def test_to_gray_from_colour(colour):
    out = to_gray(colour)
    assert out.shape == colour.shape[:2]
    assert out.dtype == np.uint8


def test_to_gray_from_rgba():
    rgba = np.zeros((5, 5, 4), dtype=np.uint8)
    assert to_gray(rgba).shape == (5, 5)


def test_to_gray_rejects_1d():
    with pytest.raises(SegError, match="unsupported image shape"):
        to_gray(np.zeros(10, dtype=np.uint8))


# --------------------------------------------------------------------------- #
# Otsu
# --------------------------------------------------------------------------- #
def test_otsu_bimodal_splits_classes():
    img = make_gray()
    t = otsu_threshold(img)
    assert 20 <= t < 210
    mask = threshold_mask(img, t)
    assert mask[:, :20].sum() == 0
    assert mask[:, 20:].all()


def test_otsu_matches_opencv(gray):
    t = otsu_threshold(gray)
    cv_value, _ = cv2.threshold(gray, 0, 255,
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    assert int(cv_value) == t


def test_otsu_constant_image_returns_int():
    img = np.full((10, 10), 77, dtype=np.uint8)
    t = otsu_threshold(img)
    assert isinstance(t, int)
    assert 0 <= t <= 255


def test_otsu_mask_matches_threshold(gray):
    mask, t = otsu_mask(gray)
    assert mask.dtype == bool
    assert np.array_equal(mask, gray > t)


def test_threshold_mask_strict_comparison():
    img = np.array([[1, 2, 3]], dtype=np.uint8)
    assert threshold_mask(img, 2).tolist() == [[False, False, True]]


@pytest.mark.parametrize("bad", [-1, 256])
def test_threshold_mask_rejects_out_of_range(bad):
    with pytest.raises(SegError, match="threshold must be in 0..255"):
        threshold_mask(np.zeros((4, 4), dtype=np.uint8), bad)


# --------------------------------------------------------------------------- #
# k-means
# --------------------------------------------------------------------------- #
def test_kmeans_recovers_two_colours():
    img = make_blocks()
    labels, centers, inertia, iters = kmeans_segment(img, clusters=2)
    assert labels.shape == (30, 30)
    assert centers.shape == (2, 3)
    assert inertia >= 0
    assert iters >= 1
    assert len(np.unique(labels)) == 2
    # the left and right halves must land in different clusters
    assert labels[:, :10].mean() != pytest.approx(labels[:, 20:].mean())


def test_kmeans_is_deterministic(colour):
    a = kmeans_segment(colour, 4, seed=7)
    b = kmeans_segment(colour, 4, seed=7)
    assert np.array_equal(a[0], b[0])
    assert np.allclose(a[1], b[1])


def test_kmeans_seed_changes_init_but_keeps_shape(colour):
    a = kmeans_segment(colour, 3, seed=1)
    b = kmeans_segment(colour, 3, seed=99)
    assert a[0].shape == b[0].shape
    assert len(np.unique(b[0])) == 3


def test_kmeans_two_dee_input_is_accepted(gray):
    labels, centers, _, _ = kmeans_segment(gray, 3)
    assert labels.shape == gray.shape
    assert centers.shape == (3, 3)


def test_kmeans_inertia_beats_one_cluster(colour):
    pixels = colour.reshape(-1, 3).astype(np.float64)
    one = float(((pixels - pixels.mean(axis=0)) ** 2).sum())
    _, _, inertia, _ = kmeans_segment(colour, 4)
    assert inertia < one


@pytest.mark.parametrize("k", [MIN_CLUSTERS - 1, MAX_CLUSTERS + 1])
def test_kmeans_rejects_bad_cluster_count(k, colour):
    with pytest.raises(SegError, match="clusters must be in"):
        kmeans_segment(colour, k)


def test_kmeans_rejects_1d_input():
    with pytest.raises(SegError, match="unsupported image shape"):
        kmeans_segment(np.zeros(10, dtype=np.uint8), 2)


def test_kmeans_all_clusters_used(colour):
    labels, _, _, _ = kmeans_segment(colour, 4)
    counts = np.bincount(labels.ravel(), minlength=4)
    assert (counts > 0).all()


# --------------------------------------------------------------------------- #
# Connected components
# --------------------------------------------------------------------------- #
def test_components_two_blocks():
    mask = np.zeros((10, 10), dtype=bool)
    mask[1:4, 1:4] = True
    mask[6:9, 6:9] = True
    labels, count = connected_components(mask, 8)
    assert count == 2
    assert labels.max() == 2


def test_components_diagonal_connectivity_differs():
    mask = np.zeros((5, 5), dtype=bool)
    mask[1, 1] = True
    mask[2, 2] = True
    _, four = connected_components(mask, 4)
    _, eight = connected_components(mask, 8)
    assert four == 2
    assert eight == 1


def test_components_empty_mask():
    labels, count = connected_components(np.zeros((6, 6), dtype=bool))
    assert count == 0
    assert labels.sum() == 0


def test_components_full_mask():
    _, count = connected_components(np.ones((6, 6), dtype=bool))
    assert count == 1


def test_components_rejects_bad_connectivity():
    with pytest.raises(SegError, match="connectivity must be 4 or 8"):
        connected_components(np.ones((3, 3), dtype=bool), 6)


def test_components_rejects_3d_mask():
    with pytest.raises(SegError, match="mask must be 2-D"):
        connected_components(np.ones((3, 3, 2), dtype=bool))


def test_component_sizes_sorted_descending():
    labels = np.array([[1, 1, 2], [0, 2, 2], [3, 0, 0]], dtype=np.int32)
    sizes = component_sizes(labels)
    assert sizes.tolist() == [3, 2, 1]


def test_component_sizes_empty():
    assert component_sizes(np.zeros((4, 4), dtype=np.int32)).size == 0


# --------------------------------------------------------------------------- #
# analyse
# --------------------------------------------------------------------------- #
def test_analyse_otsu_stats(gray):
    result = analyse(gray, mode="otsu")
    stats = result["stats"]["otsu"]
    assert stats["threshold"] == otsu_threshold(gray)
    assert 0 <= stats["foreground_ratio"] <= 1
    assert "components" not in result["stats"]


def test_analyse_components_stats(gray):
    result = analyse(gray, mode="components", connectivity=4)
    stats = result["stats"]["components"]
    assert stats["connectivity"] == 4
    assert stats["count"] >= 1
    assert stats["largest"] >= stats["median"]


def test_analyse_kmeans_stats(colour):
    result = analyse(colour, mode="kmeans", clusters=3, seed=5)
    stats = result["stats"]["kmeans"]
    assert stats["clusters"] == 3
    assert stats["seed"] == 5
    assert sum(stats["cluster_sizes"]) == colour.shape[0] * colour.shape[1]
    assert len(stats["centers"]) == 3


def test_analyse_all_contains_three_modes(colour):
    result = analyse(colour, mode="all", clusters=3)
    assert set(result["stats"]) == {"otsu", "components", "kmeans"}
    assert set(result["masks"]) == {"otsu", "components", "kmeans"}


def test_analyse_rejects_unknown_mode(gray):
    with pytest.raises(SegError, match="unknown mode"):
        analyse(gray, mode="watershed")


def test_analyse_rejects_bad_clusters(gray):
    with pytest.raises(SegError, match="clusters must be in"):
        analyse(gray, clusters=1)


def test_analyse_rejects_bad_connectivity(gray):
    with pytest.raises(SegError, match="connectivity must be 4 or 8"):
        analyse(gray, connectivity=5)


def test_analyse_is_deterministic(colour):
    first = analyse(colour, mode="all", clusters=4, seed=11)
    second = analyse(colour, mode="all", clusters=4, seed=11)
    assert first["stats"] == second["stats"]


@pytest.mark.parametrize("mode", MODES)
def test_every_mode_runs(mode, colour):
    assert analyse(colour, mode=mode, clusters=3)["mode"] == mode


# --------------------------------------------------------------------------- #
# Report / serialisation
# --------------------------------------------------------------------------- #
def test_ascii_map_width():
    mask = np.ones((20, 100), dtype=bool)
    art = ascii_map(mask, width=ASCII_WIDTH)
    assert len(art.splitlines()[0]) == ASCII_WIDTH


def test_ascii_map_rejects_3d():
    with pytest.raises(SegError, match="mask must be 2-D"):
        ascii_map(np.ones((4, 4, 3)))


def test_render_report_has_sections(gray):
    text = render_report("all", gray, "sample.png", clusters=3)
    assert "sample.png" in text
    assert "Otsu threshold" in text
    assert "Components" in text
    assert "k-means" in text
    assert "ASCII preview" in text


def test_to_dict_is_json_safe(gray):
    payload = to_dict("otsu", "sample.png", analyse(gray, mode="otsu"))
    text = json.dumps(payload)
    assert "sample.png" in text
    assert payload["mode"] == "otsu"


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


def test_cli_file_otsu(gray, tmp_path, capsys):
    path = tmp_path / "shape.png"
    cv2.imwrite(str(path), gray)
    assert main(["--file", str(path), "--mode", "otsu"]) == 0
    assert "Otsu threshold" in capsys.readouterr().out


def test_cli_file_kmeans_colour(colour, tmp_path):
    path = tmp_path / "colour.png"
    cv2.imwrite(str(path), colour)
    assert main(["--file", str(path), "--mode", "kmeans",
                 "--clusters", "3", "--quiet"]) == 0


def test_cli_rejects_bad_cluster_count(gray, tmp_path, capsys):
    path = tmp_path / "shape.png"
    cv2.imwrite(str(path), gray)
    assert main(["--file", str(path), "--clusters", "12"]) == 2
    assert "clusters must be in" in capsys.readouterr().err


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "ghost.png")]) == 2
    assert "image not found" in capsys.readouterr().err


def test_cli_json_export(gray, tmp_path):
    path = tmp_path / "shape.png"
    out = tmp_path / "report.json"
    cv2.imwrite(str(path), gray)
    assert main(["--file", str(path), "--mode", "components",
                 "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["stats"]["components"]["count"] >= 1


def test_cli_all_mode(gray, tmp_path):
    path = tmp_path / "shape.png"
    cv2.imwrite(str(path), gray)
    assert main(["--file", str(path), "--mode", "all",
                 "--clusters", "3", "--quiet"]) == 0


def test_data_dir_contains_bundled_samples():
    for name in ("otsu_shapes.png", "components.png", "color_blocks.png"):
        assert (DATA_DIR / name).is_file()
