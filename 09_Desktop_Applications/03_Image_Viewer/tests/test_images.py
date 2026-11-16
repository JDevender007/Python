"""Tests for the image lab: int(width * scale) is not a size."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import images as module                                     # noqa: E402
import main as cli                                          # noqa: E402
from images import (                                        # noqa: E402
    LEGACY_RESIZE,
    MODES,
    ORIENTATIONS,
    Entry,
    ImageError,
    Placement,
    Size,
    audit,
    binding_side,
    ceil_div,
    centred,
    fill_box,
    fit_inside,
    legacy_resize,
    measure,
    parse_images,
    problems,
    read_images,
    round_div,
    run_demo,
)

ENTRIES = read_images()


def all_sizes():
    return (Size(4000, 3000), Size(3000, 1000), Size(1000, 3000),
            Size(3, 1), Size(90, 160), Size(400, 300), Size(101, 51),
            Size(500, 500), Size(100, 50))


# --------------------------------------------------------------------------- #
# round_div
# --------------------------------------------------------------------------- #
def test_round_div_rounds_a_tie_up():
    assert round_div(5, 2) == 3


def test_round_div_floors_below_the_tie():
    assert round_div(7, 3) == 2


def test_round_div_rounds_a_negative_tie_away_from_zero():
    assert round_div(-5, 2) == -3


def test_round_div_of_an_exact_division():
    assert round_div(12, 4) == 3


def test_round_div_refuses_a_zero_denominator():
    with pytest.raises(ImageError, match="a denominator is positive"):
        round_div(1, 0)


def test_round_div_refuses_a_float():
    with pytest.raises(ImageError, match="a numerator is a whole number"):
        round_div(1.0, 2)


def test_round_div_refuses_a_true():
    with pytest.raises(ImageError, match="a numerator is a whole number"):
        round_div(True, 2)


# --------------------------------------------------------------------------- #
# ceil_div
# --------------------------------------------------------------------------- #
def test_ceil_div_rounds_an_exact_division_flat():
    assert ceil_div(12, 4) == 3


def test_ceil_div_rounds_a_fraction_up():
    assert ceil_div(7, 3) == 3


def test_ceil_div_of_a_small_fraction_is_one():
    assert ceil_div(1, 100) == 1


def test_ceil_div_handles_a_negative_numerator():
    assert ceil_div(-7, 3) == -2


def test_ceil_div_refuses_a_negative_denominator():
    with pytest.raises(ImageError, match="a denominator is positive"):
        ceil_div(1, -2)


def test_ceil_div_is_never_below_round_div():
    for numerator in range(0, 40):
        for denominator in range(1, 9):
            assert ceil_div(numerator, denominator) >= \
                round_div(numerator, denominator)


# --------------------------------------------------------------------------- #
# Size
# --------------------------------------------------------------------------- #
def test_a_size_holds_a_width_and_a_height():
    size = Size(4000, 3000)
    assert (size.width, size.height) == (4000, 3000)


def test_a_size_unpacks_as_a_pair():
    assert tuple(Size(4, 3)) == (4, 3)


def test_a_size_counts_its_pixels():
    assert Size(4000, 3000).pixels() == 12_000_000


def test_a_size_names_its_orientation():
    assert Size(4000, 3000).orientation() == "landscape"


def test_a_taller_size_is_portrait():
    assert Size(3000, 4000).orientation() == "portrait"


def test_an_equal_size_is_square():
    assert Size(500, 500).orientation() == "square"


def test_a_size_ratio_is_reduced():
    assert Size(4000, 3000).ratio() == (4, 3)


def test_a_square_ratio_is_one_to_one():
    assert Size(500, 500).ratio() == (1, 1)


def test_a_prime_sized_image_keeps_its_ratio():
    assert Size(101, 51).ratio() == (101, 51)


def test_a_size_transposes_into_the_other_orientation():
    assert Size(4000, 3000).transposed() == Size(3000, 4000)


def test_transposing_twice_returns_the_original():
    assert Size(101, 51).transposed().transposed() == Size(101, 51)


def test_a_size_scales_both_sides():
    assert Size(4, 3).scaled(2, 5) == Size(8, 15)


def test_a_size_line_names_the_orientation_and_the_ratio():
    assert Size(4000, 3000).line() == "4000x3000 (landscape, 1.3333)"


def test_a_size_prints_as_a_pair():
    assert Size(4000, 3000).plain() == "4000x3000"


def test_a_zero_width_is_refused():
    with pytest.raises(ImageError, match="a width is positive"):
        Size(0, 300)


def test_a_zero_height_is_refused():
    with pytest.raises(ImageError, match="a height is positive"):
        Size(400, 0)


def test_a_negative_width_is_refused():
    with pytest.raises(ImageError, match="a width is positive"):
        Size(-4, 3)


def test_a_float_width_is_refused():
    with pytest.raises(ImageError, match="a width is a whole number"):
        Size(4.0, 3)


def test_a_bool_height_is_refused():
    with pytest.raises(ImageError, match="a height is a whole number"):
        Size(4, True)


def test_the_orientations_are_the_three_names():
    assert ORIENTATIONS == ("landscape", "portrait", "square")


# --------------------------------------------------------------------------- #
# binding_side
# --------------------------------------------------------------------------- #
def test_the_wider_ratio_makes_the_width_bind():
    assert binding_side(Size(4000, 3000), Size(320, 240)) == "width"


def test_a_very_wide_image_binds_by_width():
    assert binding_side(Size(3000, 1000), Size(320, 240)) == "width"


def test_a_very_tall_image_binds_by_height():
    assert binding_side(Size(1000, 3000), Size(320, 240)) == "height"


def test_an_equal_ratio_binds_by_width():
    assert binding_side(Size(400, 300), Size(320, 240)) == "width"


def test_a_tall_image_in_a_tall_box_binds_by_width():
    assert binding_side(Size(90, 160), Size(200, 200)) == "height"


def test_the_binding_side_agrees_with_the_float_ratio():
    for image in all_sizes():
        for box in (Size(320, 240), Size(240, 320), Size(2, 2)):
            side = binding_side(image, box)
            widths = box.width / image.width
            heights = box.height / image.height
            if abs(widths - heights) < 1e-12:
                continue
            expected = "width" if widths < heights else "height"
            assert side == expected


def test_binding_side_refuses_a_pair_of_numbers():
    with pytest.raises(ImageError, match="compares two sizes"):
        binding_side((4000, 3000), Size(320, 240))


# --------------------------------------------------------------------------- #
# fit_inside
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("image,box,expected", [
    ((4000, 3000), (320, 240), "320x240"),
    ((3000, 1000), (320, 240), "320x107"),
    ((1000, 3000), (320, 240), "80x240"),
    ((3, 1), (2, 2), "2x1"),
    ((90, 160), (200, 200), "113x200"),
    ((400, 300), (400, 300), "400x300"),
    ((101, 51), (320, 240), "320x162"),
    ((500, 500), (320, 240), "240x240"),
    ((100, 50), (40, 40), "40x20"),
])
def test_fit_inside_lands_where_it_should(image, box, expected):
    assert fit_inside(Size(*image), Size(*box)).plain() == expected


def test_a_fit_sets_one_side_exactly_to_the_box():
    for entry in ENTRIES:
        placed = fit_inside(entry.image, entry.box)
        assert placed.width == entry.box.width or \
            placed.height == entry.box.height


def test_a_fit_never_exceeds_the_box():
    for entry in ENTRIES:
        assert fit_inside(entry.image, entry.box).contains() is True


def test_a_fit_of_an_exact_ratio_is_the_box():
    placed = fit_inside(Size(400, 300), Size(400, 300))
    assert (placed.width, placed.height) == (400, 300)


def test_a_fit_is_mode_fit():
    assert fit_inside(Size(4, 3), Size(40, 30)).mode == "fit"


def test_a_fit_starts_at_the_origin():
    placed = fit_inside(Size(1000, 3000), Size(320, 240))
    assert (placed.x, placed.y) == (0, 0)


def test_a_fit_of_a_sliver_cannot_have_a_zero_side():
    placed = fit_inside(Size(3, 1), Size(2, 2))
    assert placed.height == 1


def test_a_fit_keeps_a_tall_image_taller():
    placed = fit_inside(Size(90, 160), Size(200, 200))
    assert placed.height > placed.width


def test_a_fit_never_mirrors_the_ratio():
    for entry in ENTRIES:
        placed = fit_inside(entry.image, entry.box)
        assert (placed.width > placed.height) == \
            (entry.image.width > entry.image.height) or \
            placed.width == placed.height


# --------------------------------------------------------------------------- #
# fill_box
# --------------------------------------------------------------------------- #
def test_fill_covers_the_box():
    for entry in ENTRIES:
        assert fill_box(entry.image, entry.box).covers() is True


def test_fill_sets_one_side_exactly_to_the_box():
    for entry in ENTRIES:
        placed = fill_box(entry.image, entry.box)
        assert placed.width == entry.box.width or \
            placed.height == entry.box.height


def test_fill_of_a_wide_image_is_taller_than_the_box():
    placed = fill_box(Size(100, 50), Size(40, 40))
    assert placed.plain() == "80x40"


def test_fill_centres_the_crop_on_the_left():
    placed = fill_box(Size(100, 50), Size(40, 40))
    assert (placed.x, placed.y) == (-20, 0)


def test_fill_of_a_tall_image_crops_above_and_below():
    placed = fill_box(Size(50, 100), Size(40, 40))
    assert placed.plain() == "40x80" and (placed.x, placed.y) == (0, -20)


def test_fill_of_a_sliver_extends_both_ways():
    placed = fill_box(Size(3, 1), Size(2, 2))
    assert placed.plain() == "6x2" and placed.x == -2


def test_fill_of_an_exact_ratio_is_the_box_with_no_offset():
    placed = fill_box(Size(400, 300), Size(40, 30))
    assert placed.plain() == "40x30" and (placed.x, placed.y) == (0, 0)


def test_fill_is_mode_fill():
    assert fill_box(Size(4, 3), Size(40, 30)).mode == "fill"


def test_fill_rounds_the_derived_side_up():
    placed = fill_box(Size(100, 60), Size(40, 40))
    assert placed.height == 40 and placed.width == 67


# --------------------------------------------------------------------------- #
# centred
# --------------------------------------------------------------------------- #
def test_centring_letterboxes_a_wide_image():
    placed = centred(Size(1000, 3000), Size(320, 240))
    assert (placed.x, placed.y) == (120, 0)


def test_centring_letterboxes_a_tall_image():
    placed = centred(Size(3000, 1000), Size(320, 240))
    assert (placed.x, placed.y) == (0, 66)


def test_centring_an_exact_fit_does_not_move_it():
    placed = centred(Size(400, 300), Size(400, 300))
    assert (placed.x, placed.y) == (0, 0)


def test_centring_keeps_the_fitted_size():
    fitted = fit_inside(Size(101, 51), Size(320, 240))
    placed = centred(Size(101, 51), Size(320, 240))
    assert placed.plain() == fitted.plain()


def test_a_centred_placement_stays_inside_the_box():
    for entry in ENTRIES:
        placed = centred(entry.image, entry.box)
        assert placed.contains() and placed.x >= 0 and placed.y >= 0


# --------------------------------------------------------------------------- #
# Placement
# --------------------------------------------------------------------------- #
def test_a_placement_line_names_the_mode_the_size_and_the_offset():
    placed = fit_inside(Size(4000, 3000), Size(320, 240))
    assert placed.line() == "fit  4000x3000 -> 320x240 at (0, 0)"


def test_a_placement_measures_its_ratio_error():
    placed = fit_inside(Size(90, 160), Size(200, 200))
    assert placed.error() == 80


def test_an_exact_placement_has_no_error():
    assert fit_inside(Size(4000, 3000), Size(320, 240)).error() == 0


def test_a_placement_refuses_a_number_instead_of_a_size():
    with pytest.raises(ImageError, match="relates an image to a box"):
        Placement((4000, 3000), Size(320, 240), 320, 240, 0, 0, "fit")


def test_a_placement_refuses_an_unknown_mode():
    with pytest.raises(ImageError, match="a mode is 'fit' or 'fill'"):
        Placement(Size(4, 3), Size(3, 3), 3, 2, 0, 0, "stretch")


def test_a_placement_refuses_a_zero_side():
    with pytest.raises(ImageError, match="positive size"):
        Placement(Size(4, 3), Size(3, 3), 0, 2, 0, 0, "fit")


def test_a_placement_refuses_a_float_offset():
    with pytest.raises(ImageError, match="an x offset is a whole number"):
        Placement(Size(4, 3), Size(3, 3), 3, 2, 0.0, 0, "fit")


def test_the_two_modes_are_fit_and_fill():
    assert MODES == ("fit", "fill")


# --------------------------------------------------------------------------- #
# The legacy path
# --------------------------------------------------------------------------- #
def test_the_legacy_resize_floors_the_derived_side():
    assert legacy_resize((3000, 1000), (320, 240)) == (320, 106)


def test_the_legacy_resize_returns_a_zero_height_for_a_sliver():
    assert legacy_resize((3, 1), (2, 2)) == (2, 0)


def test_the_legacy_resize_agrees_on_a_clean_ratio():
    assert legacy_resize((4000, 3000), (320, 240)) == (320, 240)


def test_the_legacy_resize_divides_by_zero():
    with pytest.raises(ZeroDivisionError):
        legacy_resize((0, 300), (320, 240))


def test_the_legacy_resize_is_wrong_four_times_in_the_bundle():
    wrong = 0
    for entry in ENTRIES:
        placed = fit_inside(entry.image, entry.box)
        if legacy_resize(tuple(entry.image), tuple(entry.box)) != \
                (placed.width, placed.height):
            wrong += 1
    assert wrong == 4


def test_the_transcribed_legacy_resize_is_the_three_lines():
    assert LEGACY_RESIZE.startswith("def resize(image, box):")
    assert "int(image[0] * scale)" in LEGACY_RESIZE


# --------------------------------------------------------------------------- #
# Entry and parsing
# --------------------------------------------------------------------------- #
def test_an_entry_holds_a_name_an_image_and_a_box():
    entry = Entry("photo", Size(4000, 3000), Size(320, 240))
    assert (entry.name, entry.image.width, entry.box.width) == ("photo", 4000, 320)


def test_an_entry_needs_a_name():
    with pytest.raises(ImageError, match="needs a name"):
        Entry(" ", Size(4, 3), Size(4, 3))


def test_an_entry_refuses_a_name_with_a_space():
    with pytest.raises(ImageError, match="holds no spaces"):
        Entry("my photo", Size(4, 3), Size(4, 3))


def test_parse_images_reads_five_fields():
    entries = parse_images("photo 4000 3000 320 240\n")
    assert entries[0].name == "photo"
    assert entries[0].image == Size(4000, 3000)


def test_parse_images_skips_a_comment():
    assert parse_images("; a note\nphoto 4 3 4 3\n") == \
        (Entry("photo", Size(4, 3), Size(4, 3)),)


def test_parse_images_skips_blank_lines():
    assert len(parse_images("\nphoto 4 3 4 3\n\n")) == 1


def test_parse_images_reads_windows_line_endings():
    assert len(parse_images("a 4 3 4 3\r\nb 2 2 2 2\r\n")) == 2


def test_parse_images_refuses_a_short_line():
    with pytest.raises(ImageError, match="five fields are needed"):
        parse_images("photo 4000 3000 320\n")


def test_parse_images_refuses_a_word_where_a_number_should_be():
    with pytest.raises(ImageError, match="is not a whole number"):
        parse_images("photo 4000 wide 320 240\n")


def test_parse_images_refuses_an_empty_bundle():
    with pytest.raises(ImageError, match="at least one image"):
        parse_images("; only a comment\n")


def test_the_bundled_bundle_has_nine_images():
    assert len(ENTRIES) == 9


def test_every_bundled_entry_has_a_unique_name():
    names = [entry.name for entry in ENTRIES]
    assert len(names) == len(set(names))


def test_read_images_refuses_a_missing_file(tmp_path):
    with pytest.raises(ImageError, match="file not found"):
        read_images(tmp_path / "nope.txt")


def test_read_images_accepts_its_own_file(tmp_path):
    path = tmp_path / "images.txt"
    path.write_bytes(b"photo 4 3 40 30\n")
    assert read_images(path)[0].name == "photo"


# --------------------------------------------------------------------------- #
# measure
# --------------------------------------------------------------------------- #
MEASURED = measure(ENTRIES)


def test_measure_pins_the_sliver_fit():
    assert MEASURED["tiny_fit"] == "2x1"


def test_measure_pins_the_sliver_legacy_answer():
    assert MEASURED["tiny_legacy"] == "2x0"


def test_measure_pins_the_double_python_actually_holds():
    assert MEASURED["tiny_scale"] == "0.6666666666666666"


def test_measure_pins_the_exact_fit():
    assert MEASURED["exact_fit"] == "400x300"


def test_measure_pins_the_portrait_fit():
    assert MEASURED["portrait_fit"] == "113x200"


def test_measure_shows_scaling_by_width_overflows():
    assert MEASURED["portrait_by_width"] == "200x356"


def test_measure_pins_the_fill_and_its_offset():
    assert MEASURED["fill"] == "80x40"
    assert MEASURED["fill_offset"] == "(-20, 0)"


def test_measure_shows_fitting_the_same_image_leaves_the_box_half_empty():
    assert MEASURED["fill_fitted"] == "40x20"


def test_measure_records_that_a_zero_side_is_refused():
    assert MEASURED["zero_refused"] is True


def test_measure_records_that_the_legacy_path_crashes_on_zero():
    assert MEASURED["legacy_zero"] == "crash"


def test_measure_reads_nothing_out_of_the_bundle_it_was_not_given():
    tiny = measure((ENTRIES[0],))
    assert tiny["tiny_fit"] == "2x1" and "fill" in tiny


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "the legacy float loses a pixel",
    "the binding side is exactly the box",
    "a contained placement never exceeds its box",
    "an exact fit is unchanged",
    "a taller image stays taller",
    "the derived side is within half a pixel",
    "a filled placement never leaves a seam",
    "a filled 2 by 1 image is twice as wide as it is tall",
    "a zero side is refused, not divided by",
    "every image produced one placement",
    "the reduced ratio has no common factor",
]


def real_checks():
    return audit(MEASURED, ENTRIES)


def test_the_audit_holds_eleven_named_checks():
    assert [name for name, _ in real_checks()] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_images():
    assert problems(real_checks()) == []


def test_the_audit_is_repeatable():
    assert real_checks() == real_checks()


def corrupted(**changes) -> dict:
    payload = dict(MEASURED)
    payload.update(changes)
    return payload


def test_the_audit_catches_a_legacy_resize_that_happened_to_be_right():
    checks = audit(corrupted(tiny_fit="2x0"), ENTRIES)
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_a_binding_side_named_wrong():
    sides = dict(MEASURED["binding"])
    sides["wide"] = "height"          # 320x107 has only its width at the box
    checks = audit(corrupted(binding=sides), ENTRIES)
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_a_bundle_that_produced_nothing():
    checks = audit(MEASURED, ())
    assert CHECK_NAMES[9] in problems(checks)


def test_the_audit_catches_a_bundle_of_one_image():
    checks = audit(MEASURED, (ENTRIES[0],))
    assert CHECK_NAMES[9] in problems(checks)


def test_the_audit_catches_an_exact_fit_that_moved():
    checks = audit(corrupted(exact_fit="399x300"), ENTRIES)
    assert CHECK_NAMES[3] in problems(checks)


def test_the_audit_catches_a_zero_side_accepted():
    checks = audit(corrupted(zero_refused=False), ENTRIES)
    assert CHECK_NAMES[8] in problems(checks)


def test_the_audit_catches_a_legacy_zero_that_did_not_crash():
    checks = audit(corrupted(legacy_zero="no refusal"), ENTRIES)
    assert CHECK_NAMES[8] in problems(checks)


def test_the_audit_catches_a_portrait_fit_recorded_as_landscape():
    checks = audit(corrupted(portrait_fit="200x113"), ENTRIES)
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_a_width_scaled_portrait_recorded_as_portrait():
    checks = audit(corrupted(portrait_by_width="113x200"), ENTRIES)
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_a_fill_one_pixel_short():
    checks = audit(corrupted(fill_shortfall=-1), ENTRIES)
    assert CHECK_NAMES[6] in problems(checks)


def test_a_fill_one_pixel_short_does_not_cover_its_box():
    narrow = Entry("seam", Size(4000, 3000), Size(320, 240))
    short = Placement(narrow.image, narrow.box, 319, 240, 0, 0, "fill")
    assert short.covers() is False


def test_the_audit_catches_a_derived_side_off_by_more_than_a_pixel():
    placed = fit_inside(Size(3000, 1000), Size(320, 240))
    assert 2 * placed.error() <= 3000
    off_by_seven = Placement(Size(3000, 1000), Size(320, 240), 320, 113, 0, 0, "fit")
    assert 2 * off_by_seven.error() > 3000


class Unreduced(Size):
    """A size that reports its ratio as written -- the bug the check exists for."""

    def ratio(self):
        return (self.width, self.height)


def test_the_audit_catches_an_unreduced_ratio():
    checks = audit(MEASURED, tuple(
        Entry(entry.name, Unreduced(entry.image.width, entry.image.height),
              entry.box)
        for entry in ENTRIES if entry.image.ratio() != (entry.image.width,
                                                        entry.image.height)))
    assert CHECK_NAMES[10] in problems(checks)


def test_a_missing_measurement_is_a_failure_not_a_traceback():
    payload = corrupted()
    del payload["exact_fit"]
    checks = audit(payload, ENTRIES)
    assert CHECK_NAMES[3] in problems(checks)
    assert len(checks) == len(CHECK_NAMES)


def test_every_check_has_a_negative_control():
    evidence = {
        CHECK_NAMES[0]: audit(corrupted(tiny_fit="2x0"), ENTRIES),
        CHECK_NAMES[1]: audit(corrupted(binding={**MEASURED["binding"],
                                                "wide": "height"}), ENTRIES),
        CHECK_NAMES[2]: audit(MEASURED, tuple(
            Entry(entry.name, entry.image, Size(1, 1)) for entry in ENTRIES
        )),
        CHECK_NAMES[3]: audit(corrupted(exact_fit="399x300"), ENTRIES),
        CHECK_NAMES[4]: audit(corrupted(portrait_fit="200x113"), ENTRIES),
        CHECK_NAMES[5]: audit(MEASURED, tuple(
            Entry(entry.name, entry.image, Size(entry.box.width * 3,
                                               entry.box.height * 3))
            for entry in ENTRIES)),
        CHECK_NAMES[6]: audit(corrupted(fill_shortfall=-1), ENTRIES),
        CHECK_NAMES[7]: audit(corrupted(fill="80x41"), ENTRIES),
        CHECK_NAMES[8]: audit(corrupted(zero_refused=False), ENTRIES),
        CHECK_NAMES[9]: audit(MEASURED, (ENTRIES[0],)),
        CHECK_NAMES[10]: audit(MEASURED, tuple(
            Entry(entry.name, Unreduced(entry.image.width, entry.image.height),
                  entry.box)
            for entry in ENTRIES if entry.image.ratio() != (entry.image.width,
                                                            entry.image.height))),
    }
    caught = set()
    for checks in evidence.values():
        caught |= set(problems(checks))
    assert caught == set(CHECK_NAMES)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out and "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_legacy_resize(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "IMAGE LAB" in out and "int(image[0] * scale)" in out


def test_demo_counts_the_wrong_sizes(capsys):
    run_demo()
    assert "4 of 9 images come out the wrong size" in capsys.readouterr().out


def test_demo_shows_all_eleven_checks(capsys):
    run_demo()
    assert "11/11 checks pass" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_every_image(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert len(out.strip().splitlines()) == len(ENTRIES)


def test_cli_places_one_image(capsys):
    assert cli.main(["--image", "4000x3000", "--box", "320x240"]) == 0
    out = capsys.readouterr().out
    assert "320x240" in out and "width binds" in out


def test_cli_fits_a_tall_image_by_height(capsys):
    assert cli.main(["--image", "1000x3000", "--box", "320x240"]) == 0
    out = capsys.readouterr().out
    assert "80x240" in out and "height binds" in out


def test_cli_fills_a_box(capsys):
    assert cli.main(["--image", "100x50", "--box", "40x40",
                     "--mode", "fill"]) == 0
    out = capsys.readouterr().out
    assert "80x40 at (-20, 0)" in out


def test_cli_centres_a_fitted_image(capsys):
    assert cli.main(["--image", "1000x3000", "--box", "320x240",
                     "--centre"]) == 0
    assert "at (120, 0)" in capsys.readouterr().out


def test_cli_prints_the_legacy_answer(capsys):
    assert cli.main(["--image", "3000x1000", "--box", "320x240",
                     "--legacy"]) == 0
    assert "legacy: 320x106" in capsys.readouterr().out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 11 and "FAIL" not in out


def test_cli_one_image_cannot_satisfy_the_audit(capsys):
    assert cli.main(["--image", "4000x3000", "--audit"]) == 1
    out, err = capsys.readouterr()
    assert "FAIL" in out and "check(s) failed" in err


def test_cli_writes_the_placements_as_json(tmp_path, capsys):
    target = tmp_path / "placements.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["placements"]) == len(ENTRIES)
    assert payload["placements"][3]["legacy"] == "2x0"
    assert payload["placements"][3]["placed"] == "2x1"


def test_cli_json_carries_the_measurements_and_checks(tmp_path, capsys):
    target = tmp_path / "placements.json"
    assert cli.main(["--audit", "--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["measurements"]["fill_offset"] == "(-20, 0)"
    assert len(payload["checks"]) == 11
    assert all(check["ok"] for check in payload["checks"])


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_refuses_a_size_without_an_x(capsys):
    assert cli.main(["--image", "4000"]) == 2
    assert "written WxH" in capsys.readouterr().err


def test_cli_refuses_a_size_with_a_word_in_it(capsys):
    assert cli.main(["--image", "4000xwide"]) == 2
    assert "two whole numbers" in capsys.readouterr().err


def test_cli_refuses_a_zero_box(capsys):
    assert cli.main(["--image", "4000x3000", "--box", "0x240"]) == 2
    assert "a width is positive" in capsys.readouterr().err


def test_cli_refuses_a_missing_bundle(tmp_path, capsys):
    assert cli.main(["--images", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_refuses_an_unknown_mode(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["--mode", "stretch"])
    assert raised.value.code == 2


def test_the_module_keeps_its_mode_names():
    assert module.MODES == ("fit", "fill")
