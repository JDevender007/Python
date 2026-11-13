"""Tests for the Image Compressor project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from compressor import (  # noqa: E402
    BLOCK,
    COEFFS,
    LUMINANCE,
    PHOTO,
    QUALITIES,
    ZIGZAG,
    CodecError,
    _round_half_away,
    canonical_codes,
    check_quality,
    compress,
    decode_coefficients,
    decode_tokens,
    decompress,
    dequantise,
    dct2,
    dct_matrix,
    energy_stats,
    huffman_decode,
    huffman_encode,
    huffman_lengths,
    idct2,
    is_prefix_free,
    kraft_sum,
    load_image,
    merge_blocks,
    mse,
    pad_to_blocks,
    psnr,
    quant_table,
    quantise,
    render_report,
    rle,
    run_demo,
    save_image,
    split_blocks,
    split_token_blocks,
    unrle,
    zigzag_order,
)
from main import main  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def photo():
    return load_image(PHOTO)


@pytest.fixture(scope="module")
def packed50(photo):
    return compress(photo, 50)


@pytest.fixture()
def gradient():
    """A smooth 32x32 gradient, small enough for fast per-test runs."""
    rows = np.linspace(20.0, 235.0, 32)[:, None]
    cols = np.linspace(0.0, 20.0, 32)[None, :]
    return np.clip(rows + cols, 0, 255).astype(np.uint8)


@pytest.fixture()
def rng():
    return np.random.default_rng(11)


# --------------------------------------------------------------------------- #
# Zig-zag order
# --------------------------------------------------------------------------- #
def test_zigzag_has_64_unique_cells():
    assert len(ZIGZAG) == COEFFS
    assert len(set(ZIGZAG)) == COEFFS


def test_zigzag_boundaries():
    assert ZIGZAG[0] == (0, 0)
    assert ZIGZAG[1] == (0, 1)
    assert ZIGZAG[2] == (1, 0)
    assert ZIGZAG[-1] == (7, 7)


def test_zigzag_is_sorted_by_diagonal():
    diagonals = [row + col for row, col in ZIGZAG]
    assert diagonals == sorted(diagonals)


def test_zigzag_order_of_another_size():
    order = zigzag_order(2)
    assert order == ((0, 0), (0, 1), (1, 0), (1, 1))


def test_dct_matrix_rejects_a_tiny_size():
    with pytest.raises(CodecError, match="size must be >= 2"):
        dct_matrix(1)


# --------------------------------------------------------------------------- #
# DCT
# --------------------------------------------------------------------------- #
def test_dct_basis_is_orthonormal():
    basis = dct_matrix()
    assert np.allclose(basis @ basis.T, np.eye(BLOCK), atol=1e-12)


def test_dct_matrix_matches_its_definition():
    basis = dct_matrix(4)
    assert basis[0, 0] == pytest.approx(0.5)
    assert basis[1, 0] == pytest.approx(math.sqrt(0.5) * math.cos(math.pi / 8))


@pytest.mark.parametrize("seed", [0, 3, 9])
def test_dct_idct_round_trip(seed):
    block = np.random.default_rng(seed).integers(0, 256, (BLOCK, BLOCK))
    block = block.astype(np.float64)
    assert np.allclose(idct2(dct2(block)), block, atol=1e-10)


def test_dct_of_a_constant_block_is_dc_only():
    coefficients = dct2(np.full((BLOCK, BLOCK), 5.0))
    assert coefficients[0, 0] == pytest.approx(40.0)
    assert np.allclose(coefficients[1:, :], 0.0, atol=1e-12)
    assert np.allclose(coefficients[:, 1:], 0.0, atol=1e-12)


def test_dct_preserves_energy():
    block = np.random.default_rng(7).normal(0.0, 40.0, (BLOCK, BLOCK))
    assert (dct2(block) ** 2).sum() == pytest.approx((block ** 2).sum())


def test_dct_rejects_a_bad_block_shape():
    with pytest.raises(CodecError, match="blocks must be 8x8"):
        dct2(np.zeros((4, 4)))


def test_idct_rejects_a_bad_block_shape():
    with pytest.raises(CodecError, match="blocks must be 8x8"):
        idct2(np.zeros((2, 2, 4, 4)))


def test_dct_accepts_a_stack_of_blocks(rng):
    stack = rng.integers(0, 256, (3, 4, BLOCK, BLOCK)).astype(np.float64)
    assert stack.shape == np.asarray(dct2(stack)).shape


# --------------------------------------------------------------------------- #
# Quantisation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("quality", [1, 50, 100])
def test_check_quality_accepts_the_range(quality):
    assert check_quality(quality) == quality


@pytest.mark.parametrize("quality", [0, -5, 101])
def test_check_quality_rejects_out_of_range(quality):
    with pytest.raises(CodecError, match=r"quality must be in \[1, 100\]"):
        check_quality(quality)


def test_check_quality_rejects_a_boolean():
    with pytest.raises(CodecError, match="quality must be an integer"):
        check_quality(True)


def test_check_quality_rejects_a_string():
    with pytest.raises(CodecError, match="quality must be an integer"):
        check_quality("75")


def test_quant_table_at_the_luminance_reference():
    table = quant_table(50)
    assert table[0, 0] == int(LUMINANCE[0, 0])
    assert table.shape == (BLOCK, BLOCK)


def test_quant_table_at_quality_100_is_all_ones():
    assert np.all(quant_table(100) == 1)


def test_quant_table_is_monotone_in_quality():
    assert quant_table(10)[0, 0] > quant_table(90)[0, 0]


def test_quant_table_stays_within_legal_bounds():
    for quality in QUALITIES:
        table = quant_table(quality)
        assert table.min() >= 1
        assert table.max() <= 255


def test_quantise_rounds_half_away_from_zero():
    table = np.ones((BLOCK, BLOCK), dtype=np.int64)
    values = np.zeros((BLOCK, BLOCK))
    values[0, 0] = 0.5
    values[0, 1] = -0.5
    values[0, 2] = 1.4
    values[0, 3] = -1.6
    quantised = quantise(values, table)
    assert quantised[0, :4].tolist() == [1, -1, 1, -2]


def test_round_half_away_is_symmetric():
    values = np.array([0.5, 1.5, 2.5, -0.5, -1.5])
    assert _round_half_away(values).tolist() == [1, 2, 3, -1, -2]


def test_quantise_then_dequantise_is_near_lossless_at_quality_100(rng):
    coefficients = rng.normal(0.0, 20.0, (BLOCK, BLOCK))
    table = quant_table(100)
    assert np.abs(dequantise(quantise(coefficients, table), table)
                  - coefficients).max() <= 0.5


def test_quantise_rejects_a_zero_table():
    with pytest.raises(CodecError, match="table entries must be > 0"):
        quantise(np.zeros((BLOCK, BLOCK)), np.zeros((BLOCK, BLOCK)))


def test_quantise_rejects_a_bad_table_shape():
    with pytest.raises(CodecError, match="table must be 8x8"):
        quantise(np.zeros((BLOCK, BLOCK)), np.ones((4, 4)))


def test_dequantise_rejects_a_bad_table_shape():
    with pytest.raises(CodecError, match="table must be 8x8"):
        dequantise(np.zeros((BLOCK, BLOCK)), np.ones((3, 3)))


# --------------------------------------------------------------------------- #
# Blocks and padding
# --------------------------------------------------------------------------- #
def test_pad_to_blocks_pads_odd_sizes():
    padded, shape = pad_to_blocks(np.zeros((13, 9), dtype=np.uint8))
    assert padded.shape == (16, 16)
    assert shape == (13, 9)


def test_pad_to_blocks_leaves_multiples_alone():
    padded, shape = pad_to_blocks(np.zeros((16, 24), dtype=np.uint8))
    assert padded.shape == (16, 24)
    assert shape == (16, 24)


def test_padding_replicates_the_edge():
    image = np.zeros((9, 8), dtype=np.uint8)
    image[8, :] = 200
    padded, _ = pad_to_blocks(image)
    assert padded.shape == (16, 8)
    assert np.all(padded[8:, :] == 200)


def test_pad_rejects_a_three_dimensional_image():
    with pytest.raises(CodecError, match="expected a 2D image"):
        pad_to_blocks(np.zeros((8, 8, 3), dtype=np.uint8))


def test_pad_rejects_an_empty_image():
    with pytest.raises(CodecError, match="image must not be empty"):
        pad_to_blocks(np.zeros((0, 0), dtype=np.uint8))


def test_split_and_merge_round_trip(rng):
    image = rng.integers(0, 256, (16, 24)).astype(np.uint8)
    blocks = split_blocks(image)
    assert blocks.shape == (2, 3, BLOCK, BLOCK)
    assert np.array_equal(merge_blocks(blocks), image)


def test_split_blocks_rejects_a_non_multiple():
    with pytest.raises(CodecError, match="must be a multiple of 8"):
        split_blocks(np.zeros((10, 8), dtype=np.uint8))


def test_merge_blocks_rejects_a_bad_shape():
    with pytest.raises(CodecError, match="expected a .r, c, 8, 8. block array"):
        merge_blocks(np.zeros((2, 2, 4, 4)))


# --------------------------------------------------------------------------- #
# Run-length coding
# --------------------------------------------------------------------------- #
def test_rle_all_zeros_is_one_eob_token():
    assert rle([0] * COEFFS) == [(0, 0)]


def test_rle_without_zeros_emits_no_eob():
    tokens = rle(list(range(1, COEFFS + 1)))
    assert len(tokens) == COEFFS
    assert tokens[0] == (0, 1)
    assert (0, 0) not in tokens


def test_rle_encodes_the_zero_runs():
    values = [0, 0, 3, 0, 0, 0, -2] + [0] * 57
    tokens = rle(values)
    assert tokens[0] == (2, 3)
    assert tokens[1] == (3, -2)
    assert tokens[-1] == (0, 0)
    assert len(values) == COEFFS


@pytest.mark.parametrize("seed", [0, 5, 12])
def test_rle_round_trip(seed):
    values = np.random.default_rng(seed).integers(-25, 26, COEFFS).tolist()
    assert unrle(rle(values)) == values


def test_rle_round_trip_on_a_sparse_block():
    values = [0] * COEFFS
    values[0] = 17
    values[63] = -1
    assert unrle(rle(values)) == values


def test_unrle_pads_the_tail_with_zeros():
    assert unrle([(0, 4)]) == [4] + [0] * (COEFFS - 1)


def test_unrle_honours_a_custom_count():
    assert unrle([(0, 7), (0, 0)], count=4) == [7, 0, 0, 0]


def test_unrle_rejects_a_malformed_token():
    with pytest.raises(CodecError, match="must be"):
        unrle([(0, 1, 2)])


def test_unrle_rejects_a_negative_run():
    with pytest.raises(CodecError, match="run must be an integer >= 0"):
        unrle([(-1, 5)])


def test_unrle_rejects_an_eob_with_a_run():
    with pytest.raises(CodecError, match="end-of-block must be"):
        unrle([(3, 0)])


def test_unrle_rejects_an_overrun():
    with pytest.raises(CodecError, match="overruns"):
        unrle([(70, 1)])


def test_unrle_rejects_a_bad_count():
    with pytest.raises(CodecError, match="count must be an integer >= 1"):
        unrle([(0, 0)], count=0)


def test_split_token_blocks_round_trips():
    first = [0, 0, 5] + [0] * 61
    second = [9] + [0] * 63
    stream = rle(first) + rle(second)
    blocks = split_token_blocks(stream, 2)
    assert unrle(blocks[0]) == first
    assert unrle(blocks[1]) == second


def test_split_token_blocks_handles_a_full_block():
    full = list(range(1, COEFFS + 1))
    stream = rle(full) + rle([0] * COEFFS)
    blocks = split_token_blocks(stream, 2)
    assert unrle(blocks[0]) == full
    assert unrle(blocks[1]) == [0] * COEFFS


def test_split_token_blocks_rejects_a_short_stream():
    with pytest.raises(CodecError, match="ends before block 1"):
        split_token_blocks(rle([0] * COEFFS), 2)


def test_split_token_blocks_rejects_leftover_tokens():
    stream = rle([0] * COEFFS) + rle([0] * COEFFS)
    with pytest.raises(CodecError, match="left over"):
        split_token_blocks(stream, 1)


def test_split_token_blocks_rejects_a_malformed_token():
    with pytest.raises(CodecError, match="must be"):
        split_token_blocks([(0, 1, 2)], 1)


def test_split_token_blocks_rejects_a_bad_count():
    with pytest.raises(CodecError, match="count must be an integer >= 1"):
        split_token_blocks([], 0)


# --------------------------------------------------------------------------- #
# Huffman
# --------------------------------------------------------------------------- #
def test_huffman_single_symbol_gets_one_bit():
    assert huffman_lengths({("a", 1): 5}) == {("a", 1): 1}


def test_huffman_two_equal_symbols_get_one_bit_each():
    lengths = huffman_lengths({"a": 10, "b": 10})
    assert lengths == {"a": 1, "b": 1}


def test_huffman_gives_rare_symbols_longer_codes():
    lengths = huffman_lengths({"a": 100, "b": 50, "c": 5, "d": 1})
    assert lengths["a"] <= lengths["b"] <= lengths["d"]


def test_huffman_rejects_an_empty_histogram():
    with pytest.raises(CodecError, match="at least one symbol"):
        huffman_lengths({})


def test_huffman_rejects_a_zero_weight():
    with pytest.raises(CodecError, match="positive integer"):
        huffman_lengths({"a": 0})


def test_huffman_rejects_a_negative_weight():
    with pytest.raises(CodecError, match="positive integer"):
        huffman_lengths({"a": -1})


def test_huffman_rejects_a_boolean_weight():
    with pytest.raises(CodecError, match="positive integer"):
        huffman_lengths({"a": True})


def test_canonical_codes_are_prefix_free():
    lengths = huffman_lengths({"a": 5, "b": 3, "c": 2, "d": 1, "e": 1})
    assert is_prefix_free(canonical_codes(lengths))


def test_canonical_codes_are_complete():
    lengths = huffman_lengths({"a": 9, "b": 4, "c": 3, "d": 2})
    assert kraft_sum(lengths) == pytest.approx(1.0)


def test_kraft_sum_of_a_deliberately_incomplete_code():
    assert kraft_sum({"a": 1, "b": 2}) == pytest.approx(0.75)


def test_is_prefix_free_detects_a_bad_code():
    assert not is_prefix_free({"a": "0", "b": "00"})


def test_canonical_codes_reject_an_empty_table():
    with pytest.raises(CodecError, match="at least one symbol"):
        canonical_codes({})


def test_canonical_codes_reject_a_zero_length():
    with pytest.raises(CodecError, match="must be >= 1"):
        canonical_codes({"a": 0})


def test_huffman_encode_decode_round_trip():
    symbols = ["a", "b", "a", "c", "c", "c", "a", "b"]
    lengths = huffman_lengths({"a": 3, "b": 2, "c": 3})
    codes = canonical_codes(lengths)
    assert huffman_decode(huffman_encode(symbols, codes), codes) == symbols


def test_huffman_encode_rejects_an_unknown_symbol():
    with pytest.raises(CodecError, match="no code for symbol"):
        huffman_encode(["z"], {"a": "0"})


def test_huffman_decode_rejects_a_non_string():
    with pytest.raises(CodecError, match="bitstream must be a string"):
        huffman_decode(["0", "1"], {"a": "0"})


def test_huffman_decode_rejects_a_bad_character():
    with pytest.raises(CodecError, match="only contain 0 and 1"):
        huffman_decode("0x1", {"a": "0"})


def test_huffman_decode_rejects_a_truncated_stream():
    with pytest.raises(CodecError, match="mid-code"):
        huffman_decode("01", {"a": "00"})


def test_huffman_decode_rejects_duplicate_codes():
    with pytest.raises(CodecError, match="duplicate codes"):
        huffman_decode("0", {"a": "0", "b": "0"})


# --------------------------------------------------------------------------- #
# Compress / decompress
# --------------------------------------------------------------------------- #
def test_compress_rejects_a_bad_quality(photo):
    with pytest.raises(CodecError, match=r"quality must be in \[1, 100\]"):
        compress(photo, 0)


def test_compress_records_the_shape_metadata(photo, packed50):
    assert packed50.quality == 50
    assert packed50.image_shape == photo.shape
    assert packed50.padded_shape == (128, 128)
    assert packed50.blocks == (16, 16)


def test_compress_token_count_is_plausible(photo, packed50):
    assert 0 < len(packed50.tokens) < photo.size
    assert len(packed50.bits) > 0


def test_compressed_properties(photo, packed50):
    assert packed50.pixels == photo.size
    assert packed50.payload_bytes == (len(packed50.bits) + 7) // 8
    assert packed50.total_bytes == (packed50.payload_bytes
                                    + packed50.header_bytes)
    assert packed50.bits_per_pixel == pytest.approx(
        len(packed50.bits) / photo.size)
    assert packed50.total_bits_per_pixel > packed50.bits_per_pixel


def test_decode_tokens_reproduces_the_token_stream(packed50):
    assert decode_tokens(packed50) == packed50.tokens


def test_decode_coefficients_reproduces_the_quantised_coefficients(photo,
                                                                 packed50):
    padded, _ = pad_to_blocks(photo)
    expected = quantise(dct2(split_blocks(padded) - 128.0),
                        quant_table(50))
    assert np.array_equal(decode_coefficients(packed50), expected)


def test_decompress_restores_the_shape(photo, packed50):
    rebuilt = decompress(packed50)
    assert rebuilt.shape == photo.shape
    assert rebuilt.dtype == np.uint8


def test_quality_100_is_nearly_lossless(photo):
    rebuilt = decompress(compress(photo, 100))
    assert psnr(photo, rebuilt) > 40.0
    assert np.abs(photo.astype(int) - rebuilt.astype(int)).max() <= 2


def test_quality_is_monotone(photo):
    psnrs = []
    bits = []
    for quality in (10, 50, 90):
        compressed = compress(photo, quality)
        psnrs.append(psnr(photo, decompress(compressed)))
        bits.append(len(compressed.bits))
    assert psnrs == sorted(psnrs)
    assert bits == sorted(bits)


def test_compression_actually_compresses(photo):
    compressed = compress(photo, 50)
    assert compressed.bits_per_pixel < 3.0
    assert compressed.total_bytes < photo.size // 2


def test_compress_is_deterministic(photo, packed50):
    again = compress(photo, 50)
    assert again.bits == packed50.bits
    assert again.tokens == packed50.tokens
    assert np.array_equal(again.table, packed50.table)


def test_a_flat_image_round_trips_exactly():
    image = np.full((32, 32), 128, dtype=np.uint8)
    compressed = compress(image, 75)
    assert set(compressed.tokens) == {(0, 0)}
    assert compressed.bits_per_pixel < 0.02
    assert np.array_equal(decompress(compressed), image)


def test_an_unpadded_image_crops_back_to_its_original_size():
    image = np.full((13, 9), 90, dtype=np.uint8)
    image[0, 0] = 200
    compressed = compress(image, 100)
    rebuilt = decompress(compressed)
    assert rebuilt.shape == (13, 9)
    # padding is cropped away, not merged into the visible pixels
    assert np.abs(rebuilt.astype(int) - image.astype(int)).max() <= 5
    assert abs(float(rebuilt[6, 4]) - 90.0) <= 2.0


# --------------------------------------------------------------------------- #
# Metrics and reports
# --------------------------------------------------------------------------- #
def test_mse_of_identical_images_is_zero(photo):
    assert mse(photo, photo) == 0.0


def test_mse_rejects_a_shape_mismatch(photo):
    with pytest.raises(CodecError, match="shape mismatch"):
        mse(photo, photo[:8])


def test_psnr_of_identical_images_is_infinite(photo):
    assert psnr(photo, photo) == float("inf")


def test_psnr_matches_the_closed_form(photo):
    brighter = np.clip(photo.astype(int) + 4, 0, 255).astype(np.uint8)
    assert psnr(photo, brighter) == pytest.approx(
        10.0 * math.log10(255.0 ** 2 / 16.0))


def test_energy_stats_of_a_gradient():
    image = np.tile(np.linspace(0, 255, 128), (128, 1)).astype(np.uint8)
    stats = energy_stats(image)
    assert stats["dc"] > 0.9
    assert stats["low3"] > 0.99


def test_energy_stats_of_a_flat_image():
    stats = energy_stats(np.full((16, 16), 128, dtype=np.uint8))
    assert stats == {"total": 0.0, "dc": 0.0, "low3": 0.0}


def test_render_report_keys(photo):
    row = render_report(photo, 60)
    assert set(row) == {"quality", "tokens", "distinct_tokens",
                        "payload_bits", "payload_bytes", "header_bytes",
                        "total_bytes", "bits_per_pixel",
                        "total_bits_per_pixel", "psnr", "mse", "max_error",
                        "ratio_payload"}
    assert row["quality"] == 60
    assert row["max_error"] >= 0
    assert row["psnr"] > 0.0


def test_render_report_ratio_matches_the_bit_count(photo):
    row = render_report(photo, 40)
    assert row["ratio_payload"] == pytest.approx(
        photo.size * 8 / row["payload_bits"], rel=1e-3)


# --------------------------------------------------------------------------- #
# Image IO
# --------------------------------------------------------------------------- #
def test_load_missing_file(tmp_path):
    with pytest.raises(CodecError, match="file not found"):
        load_image(tmp_path / "ghost.png")


def test_load_rejects_a_non_image(tmp_path):
    path = tmp_path / "junk.png"
    path.write_text("not an image", encoding="utf-8")
    with pytest.raises(CodecError, match="could not read image"):
        load_image(path)


def test_save_and_load_round_trip(tmp_path):
    image = np.tile(np.arange(8, dtype=np.uint8) * 30, (8, 1))
    path = save_image(image, tmp_path / "nested" / "out.png")
    assert path.is_file()
    assert np.array_equal(load_image(path), image)


def test_save_rejects_a_non_2d_array(tmp_path):
    with pytest.raises(CodecError, match="expected a 2D array to save"):
        save_image(np.zeros((2, 2, 2), dtype=np.uint8), tmp_path / "x.png")


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


def test_run_demo_prints_the_quality_sweep(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    for quality in QUALITIES:
        assert f"{quality:>7}" in out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_demo_rejects_sweep():
    with pytest.raises(SystemExit) as exc:
        main(["--demo", "--sweep"])
    assert exc.value.code == 2


def test_cli_demo_rejects_save():
    with pytest.raises(SystemExit) as exc:
        main(["--demo", "--save", "x.png"])
    assert exc.value.code == 2


def test_cli_default_run(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "photo_128.png" in out
    assert "PSNR dB" in out
    assert "Done." in out


def test_cli_quality_flag(capsys):
    assert main(["--quality", "30"]) == 0
    out = capsys.readouterr().out
    assert "quality" in out
    assert "30" in out


def test_cli_rejects_a_bad_quality(capsys):
    assert main(["--quality", "0"]) == 2
    assert "quality must be in" in capsys.readouterr().err


def test_cli_sweep(capsys):
    assert main(["--sweep"]) == 0
    out = capsys.readouterr().out
    for quality in QUALITIES:
        assert f"{quality:>7}" in out


def test_cli_saves_the_decoded_image(tmp_path):
    out = tmp_path / "out" / "rebuilt.png"
    assert main(["--quality", "80", "--save", str(out), "--quiet"]) == 0
    assert out.is_file()
    assert load_image(out).shape == (128, 128)


def test_cli_writes_json(tmp_path):
    out = tmp_path / "stats.json"
    assert main(["--quality", "60", "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["image_shape"] == [128, 128]
    assert payload["pixels"] == 16384
    row = payload["rows"][0]
    assert row["quality"] == 60
    assert row["tokens"] > 0
    assert "bits_per_pixel" in row


def test_cli_sweep_json_has_every_quality(tmp_path):
    out = tmp_path / "sweep.json"
    assert main(["--sweep", "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert [row["quality"] for row in payload["rows"]] == list(QUALITIES)


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "ghost.png")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_quiet_suppresses_the_report(capsys):
    assert main(["--quality", "70", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_bundled_photo_exists():
    assert PHOTO.is_file()
