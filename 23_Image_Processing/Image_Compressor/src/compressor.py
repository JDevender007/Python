"""A JPEG-style image compressor built from scratch - fully offline.

The pipeline is the classic transform codec, minus the file format:

1. split the image into 8x8 blocks (edge-replicated padding);
2. apply the orthonormal 2-D DCT-II to each block;
3. divide by a quality-scaled quantisation table and round;
4. read the coefficients in zig-zag order;
5. run-length code each block into ``(zeros_before, amplitude)`` tokens,
   with ``(0, 0)`` marking end-of-block;
6. build a static Huffman code over this image's own token histogram and
   emit the bitstream.

Decoding reverses all six steps. Quantisation is the only lossy stage, and
the module proves that: the bitstream reproduces the quantised
coefficients exactly.

Only NumPy + Pillow - no OpenCV, no scipy, no network, no third-party
codec.
"""

from __future__ import annotations

import heapq
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

LOG = logging.getLogger("compressor")

BLOCK = 8
COEFFS = BLOCK * BLOCK
QUALITY_RANGE = (1, 100)
MAX_DIM = 2048

# JPEG's standard luminance quantisation table.
LUMINANCE = np.array([
    [16, 11, 10, 16, 24, 40, 51, 61],
    [12, 12, 14, 19, 26, 58, 60, 55],
    [14, 13, 16, 24, 40, 57, 69, 56],
    [14, 17, 22, 29, 51, 87, 80, 62],
    [18, 22, 37, 56, 68, 109, 103, 77],
    [24, 35, 55, 64, 81, 104, 113, 92],
    [49, 64, 78, 87, 103, 121, 120, 101],
    [72, 92, 95, 98, 112, 100, 103, 99],
], dtype=np.int64)


class CodecError(RuntimeError):
    """Raised for bad images, bad flags and undecodable bitstreams."""


# --------------------------------------------------------------------------- #
# Zig-zag order
# --------------------------------------------------------------------------- #
def zigzag_order(size: int = BLOCK) -> tuple[tuple[int, int], ...]:
    """Return the (row, col) visiting order of a JPEG zig-zag scan."""
    order: list[tuple[int, int]] = []
    for step in range(2 * size - 1):
        diagonal = [(row, step - row) for row in range(size)
                    if 0 <= step - row < size]
        if step % 2 == 0:
            diagonal.reverse()
        order.extend(diagonal)
    return tuple(order)


ZIGZAG = zigzag_order()


# --------------------------------------------------------------------------- #
# DCT
# --------------------------------------------------------------------------- #
def dct_matrix(size: int = BLOCK) -> np.ndarray:
    """Orthonormal 1-D DCT-II basis matrix."""
    if size < 2:
        raise CodecError(f"size must be >= 2, got {size}")
    matrix = np.zeros((size, size), dtype=np.float64)
    for frequency in range(size):
        alpha = math.sqrt(1.0 / size) if frequency == 0 \
            else math.sqrt(2.0 / size)
        for position in range(size):
            matrix[frequency, position] = alpha * math.cos(
                (2 * position + 1) * frequency * math.pi / (2 * size))
    return matrix


DCT = dct_matrix()


def dct2(blocks: np.ndarray) -> np.ndarray:
    """Forward 2-D DCT over the last two axes."""
    array = np.asarray(blocks, dtype=np.float64)
    if array.shape[-2:] != (BLOCK, BLOCK):
        raise CodecError(f"blocks must be 8x8, got {array.shape[-2:]}")
    return np.einsum("ik,...kl,jl->...ij", DCT, array, DCT)


def idct2(blocks: np.ndarray) -> np.ndarray:
    """Inverse 2-D DCT over the last two axes."""
    array = np.asarray(blocks, dtype=np.float64)
    if array.shape[-2:] != (BLOCK, BLOCK):
        raise CodecError(f"blocks must be 8x8, got {array.shape[-2:]}")
    return np.einsum("ki,...kl,lj->...ij", DCT, array, DCT)


# --------------------------------------------------------------------------- #
# Quantisation
# --------------------------------------------------------------------------- #
def check_quality(quality: int) -> int:
    """Validate a quality value in [1, 100]."""
    if isinstance(quality, bool) or not isinstance(quality, (int, np.integer)):
        raise CodecError(f"quality must be an integer, got {quality!r}")
    value = int(quality)
    low, high = QUALITY_RANGE
    if not low <= value <= high:
        raise CodecError(f"quality must be in [{low}, {high}], got {value}")
    return value


def quant_table(quality: int) -> np.ndarray:
    """Quality-scaled luminance table (JPEG's formula), all entries >= 1."""
    quality = check_quality(quality)
    scale = 5000.0 / quality if quality < 50 else 200.0 - 2.0 * quality
    table = np.floor((LUMINANCE.astype(np.float64) * scale + 50.0) / 100.0)
    return np.clip(table, 1.0, 255.0).astype(np.int64)


def _round_half_away(numbers: np.ndarray) -> np.ndarray:
    """Round half away from zero (np.rint uses banker's rounding)."""
    return np.sign(numbers) * np.floor(np.abs(numbers) + 0.5)


def quantise(coefficients: np.ndarray, table: np.ndarray) -> np.ndarray:
    """Divide by the table and round to integers."""
    table = np.asarray(table, dtype=np.float64)
    if table.shape != (BLOCK, BLOCK):
        raise CodecError(f"table must be 8x8, got {table.shape}")
    if np.any(table <= 0):
        raise CodecError("table entries must be > 0")
    values = np.asarray(coefficients, dtype=np.float64)
    return _round_half_away(values / table).astype(np.int64)


def dequantise(coefficients: np.ndarray, table: np.ndarray) -> np.ndarray:
    """Multiply the integer coefficients back by the table."""
    table = np.asarray(table, dtype=np.float64)
    if table.shape != (BLOCK, BLOCK):
        raise CodecError(f"table must be 8x8, got {table.shape}")
    return np.asarray(coefficients, dtype=np.float64) * table


# --------------------------------------------------------------------------- #
# Block plumbing
# --------------------------------------------------------------------------- #
def pad_to_blocks(image: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
    """Edge-replicate an image up to a multiple of 8; return (padded, shape)."""
    array = _as_image(image)
    height, width = array.shape
    pad_h = (BLOCK - height % BLOCK) % BLOCK
    pad_w = (BLOCK - width % BLOCK) % BLOCK
    if pad_h or pad_w:
        LOG.debug("padding %dx%d image by %d/%d", height, width, pad_h, pad_w)
        array = np.pad(array, ((0, pad_h), (0, pad_w)), mode="edge")
    return array, (height, width)


def split_blocks(image: np.ndarray) -> np.ndarray:
    """Reshape a padded image into a (rows, cols, 8, 8) block array."""
    array = _as_image(image)
    height, width = array.shape
    if height % BLOCK or width % BLOCK:
        raise CodecError(
            f"image must be a multiple of {BLOCK} pixels, got {height}x{width}")
    return array.reshape(height // BLOCK, BLOCK,
                         width // BLOCK, BLOCK).swapaxes(1, 2)


def merge_blocks(blocks: np.ndarray) -> np.ndarray:
    """Inverse of ``split_blocks``."""
    array = np.asarray(blocks, dtype=np.float64)
    if array.ndim != 4 or array.shape[2:] != (BLOCK, BLOCK):
        raise CodecError(f"expected a (r, c, 8, 8) block array, "
                         f"got {array.shape}")
    rows, cols = array.shape[:2]
    return array.swapaxes(1, 2).reshape(rows * BLOCK, cols * BLOCK)


def _as_image(image: np.ndarray) -> np.ndarray:
    """Validate a 2-D grey image and return it as float64."""
    array = np.asarray(image)
    if array.ndim != 2:
        raise CodecError(f"expected a 2D image, got {array.ndim}D")
    if array.size == 0:
        raise CodecError("image must not be empty")
    if max(array.shape) > MAX_DIM:
        raise CodecError(f"image too large: {array.shape[0]}x{array.shape[1]} "
                         f"(max {MAX_DIM})")
    return np.clip(array.astype(np.float64), 0.0, 255.0)


# --------------------------------------------------------------------------- #
# Run-length coding
# --------------------------------------------------------------------------- #
def rle(values) -> list[tuple[int, int]]:
    """Encode 64 zig-zag coefficients as (zeros_before, amplitude) tokens.

    A non-zero coefficient is preceded by ``zeros_before`` zeros. When the
    block ends in zeros the token ``(0, 0)`` means end-of-block; an
    all-zero block is a single such token.
    """
    tokens: list[tuple[int, int]] = []
    run = 0
    for raw in values:
        value = int(raw)
        if value == 0:
            run += 1
            continue
        tokens.append((run, value))
        run = 0
    if run or not tokens:
        tokens.append((0, 0))
    return tokens


def unrle(tokens, count: int = COEFFS) -> list[int]:
    """Inverse of ``rle``; always returns exactly ``count`` values."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise CodecError(f"count must be an integer >= 1, got {count!r}")
    values: list[int] = []
    for index, token in enumerate(tokens):
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            raise CodecError(f"token {index} must be (zeros, amplitude)")
        run, amplitude = token
        if isinstance(run, bool) or not isinstance(run, (int, np.integer)) \
                or run < 0:
            raise CodecError(f"token {index} run must be an integer >= 0")
        if isinstance(amplitude, bool) \
                or not isinstance(amplitude, (int, np.integer)):
            raise CodecError(f"token {index} amplitude must be an integer")
        if amplitude == 0:
            if run != 0:
                raise CodecError(
                    f"token {index}: end-of-block must be (0, 0)")
            break
        values.extend([0] * int(run))
        values.append(int(amplitude))
        if len(values) > count:
            raise CodecError(
                f"token {index} overruns the {count}-coefficient block")
    if len(values) > count:
        raise CodecError(f"block decodes to more than {count} coefficients")
    values.extend([0] * (count - len(values)))
    return values


def split_token_blocks(tokens, count: int) -> list[list[tuple[int, int]]]:
    """Split a flat token stream into ``count`` per-block token lists.

    A block ends either at its ``(0, 0)`` end-of-block token or as soon as
    64 coefficients have been accumulated (a block can be completely full,
    in which case ``rle`` emits no end-of-block marker).
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise CodecError(f"count must be an integer >= 1, got {count!r}")
    stream = list(tokens)
    blocks: list[list[tuple[int, int]]] = []
    cursor = 0
    for index in range(count):
        block: list[tuple[int, int]] = []
        total = 0
        terminated = False
        while cursor < len(stream):
            token = stream[cursor]
            if not isinstance(token, (tuple, list)) or len(token) != 2:
                raise CodecError(f"token {cursor} must be (zeros, amplitude)")
            cursor += 1
            block.append((int(token[0]), int(token[1])))
            if token[1] == 0:
                terminated = True
                break
            total += int(token[0]) + 1
            if total >= COEFFS:
                break
        if not block:
            raise CodecError(f"token stream ends before block {index}")
        if not terminated and total < COEFFS:
            raise CodecError(f"block {index} ends without an end-of-block")
        if total > COEFFS:
            raise CodecError(
                f"block {index} overruns the {COEFFS}-coefficient block")
        blocks.append(block)
    if cursor != len(stream):
        raise CodecError(
            f"{len(stream) - cursor} token(s) left over after decoding")
    return blocks


# --------------------------------------------------------------------------- #
# Huffman coding
# --------------------------------------------------------------------------- #
def huffman_lengths(frequencies: dict) -> dict:
    """Code length per symbol from a weight histogram (Huffman's algorithm)."""
    if not frequencies:
        raise CodecError("huffman needs at least one symbol")
    for symbol, weight in frequencies.items():
        if isinstance(weight, bool) or not isinstance(weight, (int, np.integer)) \
                or weight <= 0:
            raise CodecError(
                f"weight for {symbol!r} must be a positive integer")
    lengths = {symbol: 0 for symbol in frequencies}
    if len(frequencies) == 1:
        return {next(iter(frequencies)): 1}
    heap = [(int(weight), index, {symbol})
            for index, (symbol, weight) in
            enumerate(sorted(frequencies.items(), key=lambda kv: repr(kv[0])))]
    heapq.heapify(heap)
    counter = len(heap)
    while len(heap) > 1:
        weight_a, _, symbols_a = heapq.heappop(heap)
        weight_b, _, symbols_b = heapq.heappop(heap)
        for symbol in symbols_a:
            lengths[symbol] += 1
        for symbol in symbols_b:
            lengths[symbol] += 1
        heapq.heappush(heap, (weight_a + weight_b, counter,
                              symbols_a | symbols_b))
        counter += 1
    return lengths


def canonical_codes(lengths: dict) -> dict:
    """Assign canonical prefix codes from code lengths (shortest first)."""
    if not lengths:
        raise CodecError("canonical_codes needs at least one symbol")
    for symbol, length in lengths.items():
        if isinstance(length, bool) or not isinstance(length, (int, np.integer)) \
                or length < 1:
            raise CodecError(f"code length for {symbol!r} must be >= 1")
    ordered = sorted(lengths.items(), key=lambda kv: (int(kv[1]), repr(kv[0])))
    codes: dict = {}
    code = 0
    previous = 0
    for symbol, length in ordered:
        length = int(length)
        code <<= length - previous
        codes[symbol] = format(code, f"0{length}b")
        code += 1
        previous = length
    return codes


def huffman_encode(symbols, codes: dict) -> str:
    """Encode a symbol sequence into a bit string."""
    try:
        return "".join(codes[symbol] for symbol in symbols)
    except KeyError as exc:
        raise CodecError(f"no code for symbol {exc.args[0]!r}") from exc


def huffman_decode(bits: str, codes: dict) -> list:
    """Decode a bit string back into symbols."""
    if not isinstance(bits, str):
        raise CodecError("bitstream must be a string")
    if any(bit not in "01" for bit in bits):
        raise CodecError("bitstream may only contain 0 and 1")
    lookup = {code: symbol for symbol, code in codes.items()}
    if len(lookup) != len(codes):
        raise CodecError("code table has duplicate codes")
    output: list = []
    buffer = ""
    for bit in bits:
        buffer += bit
        symbol = lookup.get(buffer)
        if symbol is not None:
            output.append(symbol)
            buffer = ""
    if buffer:
        raise CodecError("bitstream ends mid-code")
    return output


def is_prefix_free(codes: dict) -> bool:
    """True when no code is a proper prefix of another."""
    ordered = sorted(codes.values())
    return all(not later.startswith(earlier)
               for earlier, later in zip(ordered, ordered[1:]))


def kraft_sum(lengths: dict) -> float:
    """Kraft inequality sum; equals 1.0 for a complete binary code."""
    return float(sum(2.0 ** -int(length) for length in lengths.values()))


# --------------------------------------------------------------------------- #
# Compressed representation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Compressed:
    """Everything needed to decode one compressed image."""

    quality: int
    image_shape: tuple[int, int]
    padded_shape: tuple[int, int]
    blocks: tuple[int, int]
    tokens: tuple[tuple[int, int], ...]
    bits: str
    lengths: dict
    table: np.ndarray

    @property
    def pixels(self) -> int:
        return self.image_shape[0] * self.image_shape[1]

    @property
    def payload_bytes(self) -> int:
        return (len(self.bits) + 7) // 8

    @property
    def header_bytes(self) -> int:
        """Rough cost of shipping the code table: 4 length bits + 13 amplitude
        bits per distinct token, rounded up to whole bytes."""
        return (len(self.lengths) * 17 + 7) // 8

    @property
    def total_bytes(self) -> int:
        return self.payload_bytes + self.header_bytes

    @property
    def bits_per_pixel(self) -> float:
        return len(self.bits) / max(1, self.pixels)

    @property
    def total_bits_per_pixel(self) -> float:
        return 8.0 * self.total_bytes / max(1, self.pixels)


def compress(image: np.ndarray, quality: int = 75) -> Compressed:
    """Encode a grey image: DCT, quantise, zig-zag, RLE, Huffman."""
    quality = check_quality(quality)
    padded, shape = pad_to_blocks(image)
    block_array = split_blocks(padded)
    table = quant_table(quality)
    coefficients = dct2(block_array - 128.0)
    quantised = quantise(coefficients, table)

    tokens: list[tuple[int, int]] = []
    for block in quantised.reshape(-1, BLOCK, BLOCK):
        scan = [int(block[row, col]) for row, col in ZIGZAG]
        tokens.extend(rle(scan))

    frequencies: dict = {}
    for token in tokens:
        frequencies[token] = frequencies.get(token, 0) + 1
    lengths = huffman_lengths(frequencies)
    codes = canonical_codes(lengths)
    bits = huffman_encode(tokens, codes)

    LOG.debug("quality %d: %d tokens, %d bits, %.2f bpp",
              quality, len(tokens), len(bits), len(bits) / block_array.size)
    return Compressed(quality=quality, image_shape=shape,
                      padded_shape=padded.shape,
                      blocks=(padded.shape[0] // BLOCK,
                              padded.shape[1] // BLOCK),
                      tokens=tuple(tokens), bits=bits, lengths=lengths,
                      table=table)


def decode_tokens(compressed: Compressed) -> tuple[tuple[int, int], ...]:
    """Recover the token stream from the bitstream alone."""
    codes = canonical_codes(compressed.lengths)
    return tuple(huffman_decode(compressed.bits, codes))


def decode_coefficients(compressed: Compressed) -> np.ndarray:
    """Turn the bitstream back into quantised 8x8 coefficient blocks."""
    tokens = decode_tokens(compressed)
    rows, cols = compressed.blocks
    blocks = np.zeros((rows, cols, BLOCK, BLOCK), dtype=np.int64)
    per_block = split_token_blocks(tokens, rows * cols)
    for flat, block_tokens in enumerate(per_block):
        row, col = divmod(flat, cols)
        scan = unrle(block_tokens)
        for index, (scan_row, scan_col) in enumerate(ZIGZAG):
            blocks[row, col, scan_row, scan_col] = scan[index]
    return blocks


def decompress(compressed: Compressed) -> np.ndarray:
    """Inverse DCT, de-quantise and crop back to the original size."""
    blocks = decode_coefficients(compressed)
    spatial = idct2(dequantise(blocks, compressed.table)) + 128.0
    image = merge_blocks(spatial)
    height, width = compressed.image_shape
    cropped = image[:height, :width]
    return np.clip(np.rint(cropped), 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- #
# Image IO and metrics
# --------------------------------------------------------------------------- #
def load_image(path: str | Path) -> np.ndarray:
    """Load a PNG/JPEG as a 2-D uint8 array (colour becomes grey)."""
    source = Path(path)
    if not source.is_file():
        raise CodecError(f"file not found: {source}")
    try:
        with Image.open(source) as handle:
            array = np.asarray(handle.convert("L"), dtype=np.uint8)
    except CodecError:
        raise
    except Exception as exc:
        raise CodecError(f"could not read image {source.name}: {exc}") from exc
    if array.ndim != 2 or array.size == 0:
        raise CodecError(f"unsupported image layout {array.shape}")
    return array


def save_image(image: np.ndarray, path: str | Path) -> Path:
    """Write a uint8 array as a PNG (creates parent directories)."""
    array = np.asarray(image)
    if array.ndim != 2:
        raise CodecError(f"expected a 2D array to save, got {array.ndim}D")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    grey = np.clip(np.rint(array.astype(np.float64)), 0, 255).astype(np.uint8)
    Image.fromarray(grey).save(target)
    return target


def mse(first: np.ndarray, second: np.ndarray) -> float:
    """Mean squared error between two images."""
    a = np.asarray(first, dtype=np.float64)
    b = np.asarray(second, dtype=np.float64)
    if a.shape != b.shape:
        raise CodecError(f"shape mismatch: {a.shape} vs {b.shape}")
    return float(np.mean((a - b) ** 2))


def psnr(first: np.ndarray, second: np.ndarray, peak: float = 255.0) -> float:
    """Peak signal-to-noise ratio in dB; identical images give inf."""
    error = mse(first, second)
    if error == 0.0:
        return float("inf")
    return 10.0 * math.log10((peak * peak) / error)


def energy_stats(image: np.ndarray) -> dict[str, float]:
    """How much coefficient energy sits in the DC and top-left 3x3 terms."""
    padded, _ = pad_to_blocks(image)
    coefficients = dct2(split_blocks(padded) - 128.0)
    per_coefficient = (coefficients ** 2).sum(axis=(0, 1))
    total = float(per_coefficient.sum())
    if total <= 0.0:
        return {"total": 0.0, "dc": 0.0, "low3": 0.0}
    return {"total": total,
            "dc": float(per_coefficient[0, 0]) / total,
            "low3": float(per_coefficient[:3, :3].sum()) / total}


def render_report(image: np.ndarray, quality: int) -> dict[str, Any]:
    """Compress, decompress and measure one quality level."""
    compressed = compress(image, quality)
    rebuilt = decompress(compressed)
    return {
        "quality": quality,
        "tokens": len(compressed.tokens),
        "distinct_tokens": len(compressed.lengths),
        "payload_bits": len(compressed.bits),
        "payload_bytes": compressed.payload_bytes,
        "header_bytes": compressed.header_bytes,
        "total_bytes": compressed.total_bytes,
        "bits_per_pixel": round(compressed.bits_per_pixel, 4),
        "total_bits_per_pixel": round(compressed.total_bits_per_pixel, 4),
        "psnr": round(psnr(image, rebuilt), 4),
        "mse": round(mse(image, rebuilt), 4),
        "max_error": int(np.abs(image.astype(np.int64)
                                - rebuilt.astype(np.int64)).max()),
        "ratio_payload": round(image.size * 8 / max(1, len(compressed.bits)),
                               3),
    }


PHOTO = Path(__file__).resolve().parent.parent / "data" / "photo_128.png"
QUALITIES = (10, 30, 50, 75, 90, 100)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(image_path: Path | None = None) -> int:
    """Compress the bundled photo at six quality levels - offline."""
    print("=" * 74)
    print(" IMAGE COMPRESSOR - offline demo")
    print(" 8x8 DCT + quantisation + zig-zag + RLE + Huffman, from scratch.")
    print("=" * 74)

    source = image_path or PHOTO
    if not source.is_file():
        raise CodecError(f"bundled sample not found: {source}")
    image = load_image(source)
    print(f"\nImage : {source.name} {image.shape[1]}x{image.shape[0]} "
          f"greyscale, raw 8.00 bpp")

    energy = energy_stats(image)
    print(f"Energy: DC {100.0 * energy['dc']:.1f}% of total, "
          f"top-left 3x3 {100.0 * energy['low3']:.1f}%")

    rows = [render_report(image, quality) for quality in QUALITIES]
    header = (f"{'quality':>7}{'tokens':>9}{'symbols':>9}{'bits':>10}"
              f"{'bpp':>8}{'total bpp':>11}{'PSNR dB':>9}{'max err':>9}")
    print()
    print(header)
    print("-" * len(header))
    for row in rows:
        print(f"{row['quality']:>7}{row['tokens']:>9}{row['distinct_tokens']:>9}"
              f"{row['payload_bits']:>10}{row['bits_per_pixel']:>8.2f}"
              f"{row['total_bits_per_pixel']:>11.2f}{row['psnr']:>9.2f}"
              f"{row['max_error']:>9}")

    # --- structural checks ------------------------------------------------ #
    basis = dct_matrix()
    assert np.allclose(basis @ basis.T, np.eye(BLOCK), atol=1e-12), \
        "DCT basis must be orthonormal"

    rng = np.random.default_rng(4)
    probe = rng.integers(0, 256, size=(BLOCK, BLOCK)).astype(np.float64)
    round_trip = idct2(dct2(probe))
    basis_error = float(np.abs(round_trip - probe).max())
    assert basis_error < 1e-10, f"dct/idct error {basis_error}"

    assert len(set(ZIGZAG)) == COEFFS and len(ZIGZAG) == COEFFS, \
        "zig-zag must visit all 64 cells once"

    # RLE round-trips exactly on every quantised block
    compressed = compress(image, 75)
    coeffs = quantise(dct2(split_blocks(pad_to_blocks(image)[0]) - 128.0),
                      quant_table(75))
    for block in coeffs.reshape(-1, BLOCK, BLOCK):
        scan = [int(block[row, col]) for row, col in ZIGZAG]
        assert unrle(rle(scan)) == scan, "RLE round-trip failed"

    # Huffman: prefix-free, complete, and exactly reversible
    codes = canonical_codes(compressed.lengths)
    assert is_prefix_free(codes), "Huffman code is not prefix-free"
    assert abs(kraft_sum(compressed.lengths) - 1.0) < 1e-12, \
        "Huffman code is not complete"
    assert huffman_decode(compressed.bits, codes) == list(compressed.tokens), \
        "Huffman decode does not reproduce the tokens"

    # the bitstream reproduces the QUANTISED coefficients exactly, i.e. the
    # entropy stage is lossless and only quantisation loses information
    decoded = decode_coefficients(compressed)
    assert np.array_equal(decoded, coeffs), \
        "entropy coding must be lossless at the coefficient level"

    # quality 100 is (almost) lossless, and quality is monotone
    by_quality = {row["quality"]: row for row in rows}
    assert by_quality[100]["psnr"] > 40.0, "quality 100 is too lossy"
    psnrs = [by_quality[q]["psnr"] for q in QUALITIES]
    assert all(later >= earlier - 1e-9
               for earlier, later in zip(psnrs, psnrs[1:])), \
        f"PSNR must not fall as quality rises: {psnrs}"
    bits = [by_quality[q]["bits_per_pixel"] for q in QUALITIES]
    assert bits[0] < bits[2] < bits[-1], \
        f"bit rate must rise with quality: {bits}"

    # real compression at a sane quality, and the loss is bounded
    mid = by_quality[50]
    assert mid["bits_per_pixel"] < 3.0, \
        f"quality 50 needs {mid['bits_per_pixel']:.2f} bpp"
    assert mid["ratio_payload"] > 2.5, \
        f"quality 50 ratio {mid['ratio_payload']}"
    assert mid["psnr"] > 30.0, f"quality 50 PSNR {mid['psnr']}"

    # DC carries most of the energy on a smooth photo
    assert energy["dc"] > 0.5, f"DC energy share {energy['dc']:.3f}"

    # deterministic
    again = compress(image, 75)
    assert again.bits == compressed.bits and again.tokens == compressed.tokens, \
        "compression is not deterministic"

    print(f"\nDCT/IDCT round-trip error : {basis_error:.2e}")
    print(f"Quality 100 max error     : {by_quality[100]['max_error']} grey "
          f"level(s)")
    print(f"Quality 50 payload        : {mid['bits_per_pixel']:.2f} bpp "
          f"({mid['ratio_payload']:.2f}x smaller than raw)")
    print(f"Huffman symbols           : {len(compressed.lengths)} distinct "
          f"tokens, Kraft sum {kraft_sum(compressed.lengths):.6f}")

    print("\nCross-checks OK: orthonormal DCT, dct/idct inverse, zig-zag "
          "covers 64 cells, RLE round-trips, Huffman is prefix-free and "
          "complete, the bitstream reproduces the quantised coefficients "
          "exactly, PSNR and bit rate are monotone in quality, quality 50 "
          "compresses below 3 bpp, DC holds most of the energy, "
          "deterministic re-run")
    print("Demo completed successfully.")
    return 0
