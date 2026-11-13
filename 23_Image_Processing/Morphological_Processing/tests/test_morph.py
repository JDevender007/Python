"""Tests for the Morphological Processing project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from morph import (  # noqa: E402
    BORDER_MODES,
    MAX_DIM,
    MIN_DIM,
    NOISY,
    OPERATIONS,
    SE_SHAPES,
    Component,
    MorphError,
    apply_operation,
    area,
    ascii_thumb,
    black_hat,
    boundary,
    clean,
    clear_border,
    closing,
    count_holes,
    count_specks,
    cross_se,
    describe_se,
    diamond_se,
    dilate,
    disk_se,
    erode,
    fraction,
    invert,
    iou,
    label_components,
    largest_components,
    load_image,
    morphological_gradient,
    opening,
    perimeter,
    rect_se,
    render_report,
    run_demo,
    save_image,
    skeleton,
    square_se,
    structuring_element,
    threshold,
    top_hat,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def image():
    return load_image(NOISY)


@pytest.fixture(scope="module")
def mask(image):
    return threshold(image, 128)


@pytest.fixture()
def blobs():
    """Two separated 9x9 squares."""
    canvas = np.zeros((40, 40), dtype=bool)
    canvas[5:14, 5:14] = True
    canvas[25:34, 25:34] = True
    return canvas


@pytest.fixture()
def square():
    """A solid 21x21 square inside a 32x32 frame."""
    canvas = np.zeros((32, 32), dtype=bool)
    canvas[5:26, 5:26] = True
    return canvas


@pytest.fixture()
def binary_png(tmp_path):
    """A small binary PNG on disk for the CLI tests."""
    data = np.zeros((32, 32), dtype=np.uint8)
    data[8:24, 8:24] = 255
    path = tmp_path / "shapes.png"
    save_image(data, path)
    return path


# --------------------------------------------------------------------------- #
# Thresholding and mask helpers
# --------------------------------------------------------------------------- #
def test_threshold_is_strictly_above_the_level():
    data = np.array([[0, 128, 129, 255]], dtype=np.uint8)
    assert threshold(data, 128).tolist() == [[False, False, True, True]]


def test_threshold_at_zero_keeps_everything_nonzero():
    data = np.array([[0, 1]], dtype=np.uint8)
    assert threshold(data, 0).tolist() == [[False, True]]


def test_threshold_at_255_keeps_nothing():
    data = np.array([[254, 255]], dtype=np.uint8)
    assert not threshold(data, 255).any()


def test_threshold_rejects_a_three_dimensional_image():
    with pytest.raises(MorphError, match="expected a 2D image"):
        threshold(np.zeros((4, 4, 3), dtype=np.uint8))


def test_threshold_rejects_an_empty_image():
    with pytest.raises(MorphError, match="must not be empty"):
        threshold(np.zeros((0, 0), dtype=np.uint8))


def test_threshold_rejects_a_boolean_level():
    with pytest.raises(MorphError, match="threshold level must be an integer"):
        threshold(np.zeros((4, 4), dtype=np.uint8), True)


def test_threshold_rejects_a_string_level():
    with pytest.raises(MorphError, match="threshold level must be an integer"):
        threshold(np.zeros((4, 4), dtype=np.uint8), "128")


def test_threshold_rejects_an_out_of_range_level():
    with pytest.raises(MorphError, match=r"must be in \[0, 255\]"):
        threshold(np.zeros((4, 4), dtype=np.uint8), 256)


def test_threshold_returns_a_boolean_array():
    assert threshold(np.zeros((4, 4), dtype=np.uint8)).dtype == bool


def test_invert_round_trips():
    data = np.array([[True, False], [False, True]])
    assert np.array_equal(invert(invert(data)), data)


def test_invert_rejects_a_three_dimensional_mask():
    with pytest.raises(MorphError, match="mask must be a 2D array"):
        invert(np.zeros((2, 2, 2), dtype=bool))


def test_area_counts_foreground_pixels(blobs):
    assert area(blobs) == 2 * 81


def test_area_of_an_empty_mask_is_zero():
    assert area(np.zeros((5, 5), dtype=bool)) == 0


def test_area_rejects_an_empty_array():
    with pytest.raises(MorphError, match="mask must not be empty"):
        area(np.zeros((0, 0), dtype=bool))


def test_area_rejects_an_oversized_array():
    with pytest.raises(MorphError, match="max is"):
        area(np.zeros((MAX_DIM + 1, MIN_DIM), dtype=bool))


def test_fraction_of_a_half_full_mask():
    assert fraction(np.array([[True, False]])) == pytest.approx(0.5)


def test_as_mask_treats_nonzero_as_foreground():
    assert area(np.array([[0, 5], [0, 0]], dtype=np.int32)) == 1


# --------------------------------------------------------------------------- #
# Structuring elements
# --------------------------------------------------------------------------- #
def test_square_se_is_all_ones():
    element = square_se(3)
    assert element.shape == (3, 3)
    assert element.dtype == bool
    assert element.all()


def test_square_se_of_one_is_a_single_pixel():
    assert square_se(1).sum() == 1


@pytest.mark.parametrize("size", [0, -3, 2, 4])
def test_square_se_rejects_bad_sizes(size):
    with pytest.raises(MorphError, match="size must be"):
        square_se(size)


def test_square_se_rejects_a_boolean_size():
    with pytest.raises(MorphError, match="size must be an integer"):
        square_se(True)


def test_cross_se_has_five_pixels():
    element = cross_se(3)
    assert element.sum() == 5
    assert not element[0, 0]


def test_cross_se_grows_with_size():
    assert cross_se(5).sum() == 9
    assert cross_se(5)[2, :].all()
    assert cross_se(5)[:, 2].all()


def test_disk_of_radius_one_is_a_plus_of_five_pixels():
    element = disk_se(1)
    assert element.shape == (3, 3)
    assert element.sum() == 5
    assert not element[0, 0]
    assert np.array_equal(element, diamond_se(1))


def test_cross_se_of_one_is_a_single_pixel():
    assert cross_se(1).shape == (1, 1)


def test_disk_of_radius_two_drops_the_corners():
    element = disk_se(2)
    assert element.shape == (5, 5)
    assert element.sum() == 21
    assert not element[0, 0] and not element[0, 4]


def test_disk_of_radius_zero_is_a_single_pixel():
    assert disk_se(0).sum() == 1


@pytest.mark.parametrize("radius", [-1, True])
def test_disk_rejects_bad_radii(radius):
    with pytest.raises(MorphError, match="radius must be"):
        disk_se(radius)


def test_diamond_of_radius_one_has_five_pixels():
    assert diamond_se(1).sum() == 5
    assert diamond_se(1).shape == (3, 3)


def test_diamond_of_radius_two_has_thirteen_pixels():
    assert diamond_se(2).sum() == 13


def test_diamond_rejects_a_negative_radius():
    with pytest.raises(MorphError, match="radius must be >= 0"):
        diamond_se(-2)


def test_rect_se_uses_both_dimensions():
    element = rect_se(3, 5)
    assert element.shape == (3, 5)
    assert element.all()


def test_rect_se_rejects_an_even_width():
    with pytest.raises(MorphError, match="width must be odd"):
        rect_se(3, 4)


@pytest.mark.parametrize("shape", SE_SHAPES)
def test_structuring_element_builds_every_shape(shape):
    element = structuring_element(shape, size=3, radius=1)
    assert element.ndim == 2
    assert element.any()


def test_structuring_element_rejects_an_unknown_shape():
    with pytest.raises(MorphError, match="unknown shape"):
        structuring_element("hexagon")


def test_structuring_element_rejects_a_non_string():
    with pytest.raises(MorphError, match="shape must be a string"):
        structuring_element(3)


def test_structuring_element_is_case_insensitive():
    assert np.array_equal(structuring_element(" Cross "), cross_se(3))


def test_describe_se_reports_shape_and_count():
    assert describe_se(cross_se(3)) == "3x3, 5 active pixel(s)"


def test_describe_se_rejects_a_bad_element():
    with pytest.raises(MorphError, match="must be 2D"):
        describe_se(np.ones((2, 2, 2), dtype=bool))


# --------------------------------------------------------------------------- #
# Structuring-element validation
# --------------------------------------------------------------------------- #
def test_dilate_rejects_a_three_dimensional_element():
    with pytest.raises(MorphError, match="must be 2D"):
        dilate(np.zeros((4, 4), dtype=bool), np.ones((2, 2, 2), dtype=bool))


def test_erode_rejects_an_empty_element():
    with pytest.raises(MorphError, match="must not be empty"):
        erode(np.zeros((4, 4), dtype=bool), np.zeros((0, 0), dtype=bool))


def test_erode_rejects_an_even_element():
    with pytest.raises(MorphError, match="odd dimensions"):
        erode(np.zeros((4, 4), dtype=bool), np.ones((2, 2), dtype=bool))


def test_erode_rejects_an_inactive_element():
    with pytest.raises(MorphError, match="at least one pixel"):
        erode(np.zeros((4, 4), dtype=bool), np.zeros((3, 3), dtype=bool))


def test_dilate_rejects_an_unknown_border_mode():
    with pytest.raises(MorphError, match="unknown border mode"):
        dilate(np.zeros((4, 4), dtype=bool), square_se(3), "smear")


def test_dilate_rejects_a_three_dimensional_mask():
    with pytest.raises(MorphError, match="mask must be a 2D array"):
        dilate(np.zeros((4, 4, 3), dtype=bool), square_se(3))


# --------------------------------------------------------------------------- #
# Dilation and erosion
# --------------------------------------------------------------------------- #
def test_dilate_of_one_pixel_is_the_element():
    mask = np.zeros((7, 7), dtype=bool)
    mask[3, 3] = True
    grown = dilate(mask, cross_se(3))
    assert grown.sum() == 5
    assert grown[3, 3] and grown[2, 3] and grown[4, 3]


def test_dilate_grows_the_area(blobs):
    assert area(dilate(blobs, square_se(3))) > area(blobs)


def test_erode_shrinks_the_area(blobs):
    assert area(erode(blobs, square_se(3))) < area(blobs)


def test_dilate_of_an_empty_mask_stays_empty():
    assert not dilate(np.zeros((8, 8), dtype=bool), square_se(3)).any()


def test_erode_of_an_empty_mask_stays_empty():
    assert not erode(np.zeros((8, 8), dtype=bool), square_se(3)).any()


def test_dilate_with_a_single_pixel_element_is_the_identity(blobs):
    assert np.array_equal(dilate(blobs, square_se(1)), blobs)


def test_erode_with_a_single_pixel_element_is_the_identity(blobs):
    assert np.array_equal(erode(blobs, square_se(1)), blobs)


def test_erosion_is_the_dual_of_dilation(blobs):
    element = square_se(3)
    assert np.array_equal(~dilate(~blobs, element), erode(blobs, element))


def test_erosion_is_the_dual_of_dilation_inside_the_frame(mask):
    # border pixels follow the background convention, so clear the ring
    # first and the identity becomes exact everywhere
    element = cross_se(3)
    frame = clear_border(mask)
    assert np.array_equal(~dilate(~frame, element), erode(frame, element))


def test_three_by_three_dilation_twice_equals_one_five_by_five(blobs):
    stepwise = dilate(dilate(blobs, square_se(3)), square_se(3))
    assert np.array_equal(stepwise, dilate(blobs, square_se(5)))


def test_background_mode_erodes_the_border():
    full = np.ones((8, 8), dtype=bool)
    shrunk = erode(full, square_se(3), "background")
    assert not shrunk[0, :].any()
    assert not shrunk[:, -1].any()
    assert shrunk[1:-1, 1:-1].all()
    assert shrunk.sum() == 36


def test_replicate_mode_keeps_a_full_frame():
    full = np.ones((8, 8), dtype=bool)
    assert erode(full, square_se(3), "replicate").all()


@pytest.mark.parametrize("mode", BORDER_MODES)
def test_every_border_mode_preserves_the_shape(blobs, mode):
    grown = dilate(blobs, square_se(3), mode)
    assert grown.shape == blobs.shape
    assert grown.dtype == bool


def test_dilation_is_deterministic(mask):
    assert np.array_equal(dilate(mask, square_se(3)), dilate(mask, square_se(3)))


def test_erosion_of_a_square_leaves_the_inner_ring(square):
    shrunk = erode(square, square_se(3))
    assert shrunk.sum() == 19 * 19
    assert not shrunk[5, :].any()


# --------------------------------------------------------------------------- #
# Composite operations
# --------------------------------------------------------------------------- #
def test_opening_is_anti_extensive(mask):
    assert not (opening(mask, square_se(3)) & ~mask).any()


def test_closing_is_extensive(mask):
    assert not (mask & ~closing(mask, square_se(3))).any()


def test_opening_is_idempotent(mask):
    once = opening(mask, square_se(3))
    assert np.array_equal(opening(once, square_se(3)), once)


def test_closing_is_idempotent(mask):
    once = closing(mask, square_se(3))
    assert np.array_equal(closing(once, square_se(3)), once)


def test_cleaning_is_idempotent(mask):
    once = clean(mask, square_se(3))
    assert np.array_equal(clean(once, square_se(3)), once)


def test_opening_removes_an_isolated_speck():
    canvas = np.zeros((20, 20), dtype=bool)
    canvas[2, 2] = True
    canvas[8:16, 8:16] = True
    assert not opening(canvas, square_se(3))[2, 2]
    assert area(opening(canvas, square_se(3))) == 64


def test_opening_keeps_a_shape_larger_than_the_element(square):
    assert np.array_equal(opening(square, square_se(3)), square)


def test_closing_fills_an_isolated_hole():
    canvas = np.ones((20, 20), dtype=bool)
    canvas[9, 9] = False
    assert closing(canvas, square_se(3))[9, 9]


def test_closing_does_not_fill_a_large_hole(square):
    canvas = square.copy()
    canvas[12:20, 12:20] = False
    assert not closing(canvas, square_se(3))[15, 15]


def test_opening_with_a_one_pixel_element_is_the_identity(mask):
    assert np.array_equal(opening(mask, square_se(1)), mask)


def test_top_hat_is_a_subset_of_the_mask(mask):
    assert not (top_hat(mask, square_se(3)) & ~mask).any()


def test_black_hat_is_disjoint_from_the_mask(mask):
    assert not (black_hat(mask, square_se(3)) & mask).any()


def test_top_hat_finds_a_thin_protrusion():
    canvas = np.zeros((20, 20), dtype=bool)
    canvas[8:16, 8:16] = True
    canvas[6, 11] = True
    assert top_hat(canvas, square_se(3))[6, 11]


def test_black_hat_finds_a_notch():
    canvas = np.ones((20, 20), dtype=bool)
    canvas[0, :] = canvas[-1, :] = False
    canvas[:, 0] = canvas[:, -1] = False
    canvas[10, 19] = False
    canvas = closing(canvas, square_se(1))
    canvas[10, 19] = False
    hat = black_hat(canvas, square_se(3))
    assert hat.shape == canvas.shape
    assert not (hat & canvas).any()


def test_boundary_is_a_subset_of_the_mask(square):
    assert not (boundary(square) & ~square).any()


def test_boundary_of_an_n_by_n_square_is_4n_minus_4(square):
    assert perimeter(square) == 4 * 21 - 4


def test_boundary_of_an_empty_mask_is_empty():
    assert not boundary(np.zeros((10, 10), dtype=bool)).any()


def test_boundary_of_a_single_pixel_is_that_pixel():
    canvas = np.zeros((7, 7), dtype=bool)
    canvas[3, 3] = True
    assert boundary(canvas).sum() == 1


def test_gradient_is_dilation_minus_erosion(mask):
    element = square_se(3)
    expected = dilate(mask, element) & ~erode(mask, element)
    assert np.array_equal(morphological_gradient(mask, element), expected)


def test_gradient_contains_the_boundary(square):
    assert not (boundary(square) & ~morphological_gradient(square)).any()


def test_clean_equals_closing_of_opening(mask):
    element = cross_se(3)
    assert np.array_equal(clean(mask, element),
                          closing(opening(mask, element), element))


def test_clear_border_zeroes_the_outer_ring():
    canvas = np.ones((6, 6), dtype=bool)
    cleared = clear_border(canvas)
    assert not cleared[0, :].any()
    assert not cleared[:, -1].any()
    assert cleared[1:-1, 1:-1].all()


def test_clear_border_on_a_tiny_mask():
    tiny = np.ones((2, 2), dtype=bool)
    assert np.array_equal(clear_border(tiny), tiny)


@pytest.mark.parametrize("name", OPERATIONS)
def test_apply_operation_handles_every_name(mask, name):
    result = apply_operation(mask, name, square_se(3))
    assert result.shape == mask.shape
    assert result.dtype == bool


def test_apply_operation_is_case_insensitive(mask):
    assert np.array_equal(apply_operation(mask, "Erode", square_se(3)),
                          erode(mask, square_se(3)))


def test_apply_operation_rejects_an_unknown_name(mask):
    with pytest.raises(MorphError, match="unknown operation"):
        apply_operation(mask, "smooth")


def test_apply_operation_rejects_a_non_string(mask):
    with pytest.raises(MorphError, match="operation must be a string"):
        apply_operation(mask, 7)


# --------------------------------------------------------------------------- #
# Connected components
# --------------------------------------------------------------------------- #
def test_label_components_counts_two_blobs(blobs):
    labels, components = label_components(blobs, 8)
    assert len(components) == 2
    assert labels.max() == 2


def test_background_is_label_zero(blobs):
    labels, _ = label_components(blobs, 8)
    assert labels[0, 0] == 0


def test_labels_are_contiguous_from_one(blobs):
    labels, components = label_components(blobs, 8)
    assert sorted(component.label for component in components) == [1, 2]
    assert set(np.unique(labels)) == {0, 1, 2}


def test_component_areas_sum_to_the_foreground(blobs):
    _, components = label_components(blobs, 8)
    assert sum(component.area for component in components) == area(blobs)


def test_diagonal_pixels_join_with_eight_connectivity():
    canvas = np.zeros((5, 5), dtype=bool)
    canvas[1, 1] = True
    canvas[2, 2] = True
    assert len(label_components(canvas, 8)[1]) == 1
    assert len(label_components(canvas, 4)[1]) == 2


def test_component_bbox_is_inclusive(blobs):
    _, components = label_components(blobs, 8)
    smallest = min(components, key=lambda item: item.label)
    assert smallest.bbox == (5, 5, 13, 13)


def test_component_centroid_is_the_mean(blobs):
    _, components = label_components(blobs, 8)
    first = min(components, key=lambda item: item.label)
    assert first.centroid == pytest.approx((9.0, 9.0))


def test_component_height_and_width(blobs):
    _, components = label_components(blobs, 8)
    first = min(components, key=lambda item: item.label)
    assert first.height == 9
    assert first.width == 9


def test_touches_border_is_false_for_an_inner_blob(blobs):
    _, components = label_components(blobs, 8)
    assert all(not component.touches_border for component in components)


def test_touches_border_is_true_at_the_edge():
    canvas = np.zeros((6, 6), dtype=bool)
    canvas[0, 0] = True
    _, components = label_components(canvas, 8)
    assert components[0].touches_border


def test_component_to_dict_shape(blobs):
    _, components = label_components(blobs, 8)
    payload = components[0].to_dict()
    assert set(payload) == {"label", "area", "bbox", "height", "width",
                            "centroid", "touches_border"}
    assert payload["label"] == 1
    assert len(payload["bbox"]) == 4


def test_component_is_frozen():
    component = Component(1, 4, (0, 0, 1, 1), (0.5, 0.5), False)
    with pytest.raises(Exception):
        component.area = 99


def test_label_components_of_an_empty_mask_is_empty():
    labels, components = label_components(np.zeros((5, 5), dtype=bool), 8)
    assert not labels.any()
    assert components == ()


@pytest.mark.parametrize("connectivity", [3, 6, 0])
def test_label_components_rejects_a_bad_connectivity(connectivity):
    with pytest.raises(MorphError, match="connectivity must be 4 or 8"):
        label_components(np.zeros((5, 5), dtype=bool), connectivity)


def test_label_components_rejects_a_boolean_connectivity():
    with pytest.raises(MorphError, match="connectivity must be 4 or 8"):
        label_components(np.zeros((5, 5), dtype=bool), True)


def test_count_specks_counts_small_parts(mask):
    assert count_specks(mask, 4) > 100


def test_count_specks_is_zero_after_cleaning(mask):
    assert count_specks(clean(mask, square_se(3)), 4) == 0


def test_count_specks_rejects_a_bad_max_area(mask):
    with pytest.raises(MorphError, match="max_area must be an integer >= 1"):
        count_specks(mask, 0)


def test_count_holes_finds_an_enclosed_island():
    canvas = np.ones((20, 20), dtype=bool)
    canvas[9, 9] = False
    assert count_holes(canvas, 4) == 1


def test_count_holes_ignores_open_background():
    canvas = np.zeros((20, 20), dtype=bool)
    canvas[5:15, 5:15] = True
    assert count_holes(canvas, 4) == 0


def test_count_holes_drops_after_closing(mask):
    assert count_holes(clean(mask, square_se(3)), 8) \
        < count_holes(mask, 8)


def test_count_holes_rejects_a_bad_max_area(mask):
    with pytest.raises(MorphError, match="max_area must be an integer >= 1"):
        count_holes(mask, -1)


def test_largest_components_is_sorted_biggest_first(mask):
    biggest = largest_components(mask, 100, 8)
    assert [component.area for component in biggest] == \
        sorted((component.area for component in biggest), reverse=True)


def test_largest_components_filters_by_area(blobs):
    assert len(largest_components(blobs, 81, 8)) == 2
    assert len(largest_components(blobs, 82, 8)) == 0


def test_largest_components_rejects_a_bad_minimum(mask):
    with pytest.raises(MorphError,
                       match="minimum_area must be an integer >= 1"):
        largest_components(mask, 0)


# --------------------------------------------------------------------------- #
# Thinning
# --------------------------------------------------------------------------- #
def test_skeleton_of_a_square_is_small(square):
    thin = skeleton(square)
    assert 0 < area(thin) < 20


def test_skeleton_is_a_subset(mask):
    cleaned = clean(mask, square_se(3))
    assert not (skeleton(cleaned) & ~cleaned).any()


def test_skeleton_of_an_empty_mask_is_empty():
    assert not skeleton(np.zeros((10, 10), dtype=bool)).any()


def test_skeleton_of_a_one_pixel_wide_line_is_that_line():
    canvas = np.zeros((12, 12), dtype=bool)
    canvas[5, 2:10] = True
    assert np.array_equal(skeleton(canvas), canvas)


def test_skeleton_preserves_the_number_of_parts(blobs):
    thin = skeleton(blobs)
    assert len(label_components(thin, 8)[1]) == 2


def test_skeleton_is_thinner_than_a_solid_blob(blobs):
    assert area(skeleton(blobs)) * 4 < area(blobs)


def test_skeleton_is_deterministic(mask):
    cleaned = clean(mask, square_se(3))
    assert np.array_equal(skeleton(cleaned), skeleton(cleaned))


def test_skeleton_returns_booleans(square):
    assert skeleton(square).dtype == bool


def test_skeleton_rejects_a_bad_iteration_cap():
    with pytest.raises(MorphError, match="max_iterations must be"):
        skeleton(np.zeros((5, 5), dtype=bool), 0)


def test_skeleton_respects_the_iteration_cap(square):
    one_pass = area(skeleton(square, max_iterations=1))
    full = area(skeleton(square))
    assert one_pass >= full


# --------------------------------------------------------------------------- #
# Metrics and reporting
# --------------------------------------------------------------------------- #
def test_iou_of_identical_masks_is_one(mask):
    assert iou(mask, mask) == pytest.approx(1.0)


def test_iou_of_disjoint_masks_is_zero():
    first = np.array([[True, False]])
    second = np.array([[False, True]])
    assert iou(first, second) == pytest.approx(0.0)


def test_iou_of_two_empty_masks_is_one():
    empty = np.zeros((4, 4), dtype=bool)
    assert iou(empty, empty) == pytest.approx(1.0)


def test_iou_known_value():
    first = np.array([[True, True, False, False]])
    second = np.array([[True, False, True, False]])
    assert iou(first, second) == pytest.approx(1.0 / 3.0)


def test_iou_rejects_a_shape_mismatch(blobs):
    with pytest.raises(MorphError, match="shape mismatch"):
        iou(blobs, blobs[:10])


def test_perimeter_of_a_single_pixel():
    canvas = np.zeros((5, 5), dtype=bool)
    canvas[2, 2] = True
    assert perimeter(canvas) == 1


def test_render_report_aligns_the_rows():
    rows = [{"operation": "input", "pixels": 100, "share": 0.1,
             "delta": 0, "components": 2}]
    text = render_report(rows, "TITLE")
    assert "TITLE" in text
    assert "operation" in text
    assert "input" in text
    assert len(text.splitlines()) == 5


def test_render_report_needs_a_row():
    with pytest.raises(MorphError, match="at least one row"):
        render_report([], "TITLE")


# --------------------------------------------------------------------------- #
# Image IO and ASCII preview
# --------------------------------------------------------------------------- #
def test_load_missing_file(tmp_path):
    with pytest.raises(MorphError, match="file not found"):
        load_image(tmp_path / "ghost.png")


def test_load_rejects_a_non_image(tmp_path):
    path = tmp_path / "junk.png"
    path.write_text("not a png", encoding="utf-8")
    with pytest.raises(MorphError, match="could not read image"):
        load_image(path)


def test_load_rejects_a_tiny_image(tmp_path):
    path = tmp_path / "tiny.png"
    save_image(np.zeros((MIN_DIM - 1, MIN_DIM), dtype=np.uint8), path)
    with pytest.raises(MorphError, match="image too small"):
        load_image(path)


def test_load_rejects_a_huge_image(tmp_path):
    path = tmp_path / "huge.png"
    save_image(np.zeros((MAX_DIM + 1, MIN_DIM), dtype=np.uint8), path)
    with pytest.raises(MorphError, match="image too large"):
        load_image(path)


def test_save_writes_a_boolean_mask_as_black_and_white(tmp_path):
    mask = np.zeros((16, 16), dtype=bool)
    mask[4:12, 4:12] = True
    path = save_image(mask, tmp_path / "mask.png")
    loaded = load_image(path)
    assert loaded[8, 8] == 255
    assert loaded[0, 0] == 0


def test_save_creates_parent_directories(tmp_path):
    path = save_image(np.zeros((8, 8), dtype=np.uint8),
                      tmp_path / "deep" / "nested" / "out.png")
    assert path.is_file()


def test_save_rejects_a_three_dimensional_array(tmp_path):
    with pytest.raises(MorphError, match="expected a 2D array to save"):
        save_image(np.zeros((2, 2, 2), dtype=np.uint8), tmp_path / "x.png")


def test_ascii_thumb_shape():
    art = ascii_thumb(np.zeros((32, 64), dtype=bool), cols=16)
    lines = art.splitlines()
    assert len(lines) == 8
    assert all(len(line) == 16 for line in lines)


def test_ascii_thumb_uses_two_characters(blobs):
    art = ascii_thumb(blobs, cols=40)
    assert set(art.replace("\n", "")) == {"#", "."}
    assert "#" in art


def test_ascii_thumb_rejects_too_few_columns(blobs):
    with pytest.raises(MorphError, match="cols must be >= 4"):
        ascii_thumb(blobs, cols=3)


def test_ascii_thumb_rejects_an_empty_array():
    with pytest.raises(MorphError, match="non-empty 2D array"):
        ascii_thumb(np.zeros((0, 0), dtype=bool))


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


def test_run_demo_reports_the_cleaning_counts(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "salt specks" in out
    assert "pepper holes" in out
    assert "skeleton pixels" in out


def test_run_demo_rejects_a_missing_sample(tmp_path):
    with pytest.raises(MorphError, match="bundled sample not found"):
        run_demo(tmp_path / "ghost.png")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_demo_rejects_operations():
    with pytest.raises(SystemExit) as exc:
        main(["--demo", "--op", "erode"])
    assert exc.value.code == 2


def test_cli_demo_rejects_json():
    with pytest.raises(SystemExit) as exc:
        main(["--demo", "--json", "x.json"])
    assert exc.value.code == 2


def test_cli_default_run(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "noisy_shapes_128.png" in out
    assert "OPERATIONS" in out
    assert "Done." in out


def test_cli_single_operation(binary_png, capsys):
    assert main(["--file", str(binary_png), "--op", "erode"]) == 0
    out = capsys.readouterr().out
    assert "erode" in out


def test_cli_pipeline_of_operations(binary_png, capsys):
    assert main(["--file", str(binary_png), "--op", "open",
                 "--op", "close", "--op", "boundary"]) == 0
    out = capsys.readouterr().out
    assert "open" in out and "close" in out and "boundary" in out


def test_cli_cross_element(binary_png, capsys):
    assert main(["--file", str(binary_png), "--shape", "cross",
                 "--size", "5"]) == 0
    assert "cross, 5x5, 9 active pixel(s)" in capsys.readouterr().out


def test_cli_disk_element(binary_png, capsys):
    assert main(["--file", str(binary_png), "--shape", "disk",
                 "--radius", "2", "--op", "dilate"]) == 0
    assert "disk" in capsys.readouterr().out


def test_cli_components(binary_png, capsys):
    assert main(["--file", str(binary_png), "--components"]) == 0
    out = capsys.readouterr().out
    assert "Components (8-connectivity" in out
    assert "border" in out


def test_cli_skeleton(binary_png, capsys):
    assert main(["--file", str(binary_png), "--skeleton"]) == 0
    out = capsys.readouterr().out
    assert "Skeleton:" in out
    assert "part(s)" in out


def test_cli_ascii(binary_png, capsys):
    assert main(["--file", str(binary_png), "--ascii"]) == 0
    assert "ASCII preview" in capsys.readouterr().out


def test_cli_saves_the_mask(binary_png, tmp_path):
    out = tmp_path / "out" / "mask.png"
    assert main(["--file", str(binary_png), "--save", str(out),
                 "--quiet"]) == 0
    assert out.is_file()
    assert set(np.unique(load_image(out)).tolist()) <= {0, 255}


def test_cli_writes_json(binary_png, tmp_path):
    out = tmp_path / "run.json"
    assert main(["--file", str(binary_png), "--threshold", "100",
                 "--components", "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["threshold"] == 100
    assert payload["operations"] == ["clean"]
    assert payload["final_pixels"] > 0
    assert isinstance(payload["components"], list)
    assert set(payload["element"]) == {"shape", "size", "radius",
                                       "description"}


def test_cli_json_records_every_stage(binary_png, tmp_path):
    out = tmp_path / "run.json"
    assert main(["--file", str(binary_png), "--op", "erode", "--op",
                 "dilate", "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert [stage["operation"] for stage in payload["stages"]] == \
        ["input", "erode", "dilate"]
    assert set(payload["stages"][0]) == {"operation", "pixels", "share",
                                         "delta", "components"}


def test_cli_json_records_the_skeleton(binary_png, tmp_path):
    out = tmp_path / "run.json"
    assert main(["--file", str(binary_png), "--skeleton", "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "skeleton" in payload
    assert payload["skeleton"]["pixels"] > 0
    assert "components" in payload["skeleton"]


def test_cli_quiet_suppresses_the_report(binary_png, capsys):
    assert main(["--file", str(binary_png), "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "ghost.png")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_rejects_a_bad_threshold():
    with pytest.raises(SystemExit) as exc:
        main(["--threshold", "300"])
    assert exc.value.code == 2


def test_cli_rejects_an_even_size():
    with pytest.raises(SystemExit) as exc:
        main(["--size", "4"])
    assert exc.value.code == 2


def test_cli_rejects_a_negative_radius():
    with pytest.raises(SystemExit) as exc:
        main(["--radius", "-1"])
    assert exc.value.code == 2


def test_cli_rejects_an_unknown_shape():
    with pytest.raises(SystemExit) as exc:
        main(["--shape", "hexagon"])
    assert exc.value.code == 2


def test_cli_rejects_an_even_rect(binary_png, capsys):
    assert main(["--file", str(binary_png), "--shape", "rect",
                 "--size", "4"]) == 2
    assert "must be odd" in capsys.readouterr().err


def test_bundled_sample_exists():
    assert NOISY.is_file()
