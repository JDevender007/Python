"""Tests for the Histogram Equalizer project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from histogram import (  # noqa: E402
    BINS,
    LOW_IMG,
    METHODS,
    NOISY_IMG,
    HistError,
    ascii_histogram,
    cumulative_counts,
    equalize,
    equalize_clahe,
    equalize_global,
    histogram,
    histogram_stats,
    load_image,
    mse,
    psnr,
    render_report,
    run_demo,
    save_image,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def lowcontrast() -> np.ndarray:
    return load_image(LOW_IMG)


@pytest.fixture(scope="module")
def noisy() -> np.ndarray:
    return load_image(NOISY_IMG)


# --------------------------------------------------------------------------- #
# Loading and saving
# --------------------------------------------------------------------------- #
def test_load_bundled_samples(lowcontrast, noisy):
    assert lowcontrast.shape == (128, 128)
    assert lowcontrast.dtype == np.uint8
    assert (int(lowcontrast.min()), int(lowcontrast.max())) == (82, 164)
    assert noisy.shape == (128, 128)
    assert noisy.std() < 10.0          # flat sample really is low-noise


def test_load_unreadable_inputs(tmp_path):
    with pytest.raises(HistError, match="not found"):
        load_image(tmp_path / "nope.png")
    fake = tmp_path / "fake.png"
    fake.write_text("nope", encoding="utf-8")
    with pytest.raises(HistError, match="could not read image"):
        load_image(fake)


def test_load_dimension_limits(tmp_path):
    tiny = tmp_path / "tiny.png"
    Image.fromarray(np.zeros((4, 16), dtype=np.uint8)).save(tiny)
    with pytest.raises(HistError, match="too small"):
        load_image(tiny)
    wide = tmp_path / "wide.png"
    Image.fromarray(np.zeros((16, 600), dtype=np.uint8)).save(wide)
    with pytest.raises(HistError, match="too large"):
        load_image(wide)


def test_load_rgb_converts_to_grey(tmp_path):
    path = tmp_path / "green.png"
    green = np.zeros((16, 16, 3), dtype=np.uint8)
    green[..., 1] = 255
    Image.fromarray(green).save(path)
    grey = load_image(path)
    assert grey.ndim == 2 and grey.dtype == np.uint8
    assert abs(int(grey.mean()) - 150) <= 3


def test_save_roundtrip_and_validation(tmp_path, lowcontrast):
    target = save_image(lowcontrast, tmp_path / "nested" / "eq.png")
    assert np.array_equal(load_image(target), lowcontrast)
    with pytest.raises(HistError, match="2D"):
        save_image(np.zeros((4, 4, 3)), tmp_path / "bad.png")


# --------------------------------------------------------------------------- #
# Histogram, CDF, statistics, ASCII
# --------------------------------------------------------------------------- #
def test_histogram_counts_known_values():
    image = np.array([[0, 0, 255], [10, 10, 10]], dtype=np.uint8)
    counts = histogram(image)
    assert counts.shape == (BINS,)
    assert counts[0] == 2 and counts[255] == 1 and counts[10] == 3
    assert int(counts.sum()) == image.size


def test_histogram_validates_input():
    with pytest.raises(HistError, match="2D"):
        histogram(np.zeros((4, 4, 3)))
    with pytest.raises(HistError, match="must not be empty"):
        histogram(np.zeros((0, 4), dtype=np.uint8))
    with pytest.raises(HistError, match="whole numbers"):
        histogram(np.array([[1.5, 2.0]]))
    with pytest.raises(HistError, match="0..255"):
        histogram(np.array([[0.0, 300.0]]))
    with pytest.raises(HistError, match="finite"):
        histogram(np.array([[np.nan, 1.0]]))


def test_cumulative_counts_monotone(lowcontrast):
    cumulative = cumulative_counts(lowcontrast)
    assert np.all(np.diff(cumulative) >= 0)
    assert int(cumulative[-1]) == lowcontrast.size
    assert np.array_equal(cumulative, np.cumsum(histogram(lowcontrast)))


def test_histogram_stats_known_values():
    image = np.array([[0, 255]], dtype=np.uint8)
    stats = histogram_stats(image)
    assert stats["mean"] == pytest.approx(127.5)
    assert stats["std"] == pytest.approx(127.5)
    assert stats["min"] == 0 and stats["max"] == 255
    assert stats["range"] == 255 and stats["occupied"] == 2
    assert stats["pixels"] == 2


def test_ascii_histogram_bars_and_validation():
    image = np.full((8, 8), 100, dtype=np.uint8)
    art = ascii_histogram(image, bins=32, width=20)
    lines = art.splitlines()
    assert len(lines) == 32
    peak_line = next(line for line in lines if "96-103" in line)
    assert peak_line.rstrip().endswith("| " + "#" * 20)
    with pytest.raises(HistError, match="divide"):
        ascii_histogram(image, bins=3)
    with pytest.raises(HistError, match="width must be >= 4"):
        ascii_histogram(image, width=2)


# --------------------------------------------------------------------------- #
# Global equalization
# --------------------------------------------------------------------------- #
def test_global_output_properties(lowcontrast):
    equalized = equalize_global(lowcontrast)
    assert equalized.dtype == np.uint8
    assert equalized.shape == lowcontrast.shape
    assert int(equalized.min()) == 0 and int(equalized.max()) == 255
    assert float(equalized.std()) > float(lowcontrast.std())


def test_global_exact_known_mapping():
    # two values, equal counts: first -> 0, second -> 255
    assert np.array_equal(equalize_global(np.array([[0, 128]],
                                                    dtype=np.uint8)),
                          np.array([[0, 255]], dtype=np.uint8))
    # cdf_min sits at 100 -> it maps to 0, 200 maps to 255
    assert np.array_equal(equalize_global(np.array([[100, 100, 200]],
                                                    dtype=np.uint8)),
                          np.array([[0, 0, 255]], dtype=np.uint8))


def test_global_uniform_image_unchanged():
    flat = np.full((32, 32), 140, dtype=np.uint8)
    assert np.array_equal(equalize_global(flat), flat)


def test_global_mapping_is_monotone():
    ramp = np.arange(128, dtype=np.uint8).reshape(1, 128)
    mapped = equalize_global(ramp).ravel().astype(int)
    assert np.all(np.diff(mapped) >= 0)
    assert mapped[0] == 0 and mapped[-1] == 255


def test_global_mean_stays_nearby(lowcontrast):
    before = histogram_stats(lowcontrast)
    after = histogram_stats(equalize_global(lowcontrast))
    assert abs(after["mean"] - before["mean"]) < 40.0
    assert after["occupied"] >= before["occupied"]
    assert int(histogram(equalize_global(lowcontrast)).sum()) \
        == lowcontrast.size


def test_global_preserves_pixel_count(lowcontrast):
    counts = histogram(equalize_global(lowcontrast))
    assert int(counts.sum()) == lowcontrast.size


def test_global_is_deterministic(lowcontrast):
    first = equalize_global(lowcontrast)
    second = equalize_global(lowcontrast)
    assert np.array_equal(first, second)


def test_psnr_known_values(lowcontrast):
    equalized = equalize_global(lowcontrast)
    assert psnr(lowcontrast, lowcontrast) == float("inf")
    assert mse(lowcontrast, lowcontrast) == 0.0
    assert 0.0 < psnr(lowcontrast, equalized) < 100.0
    with pytest.raises(HistError, match="shape mismatch"):
        psnr(np.zeros((4, 4)), np.zeros((5, 5)))


# --------------------------------------------------------------------------- #
# CLAHE-style local limiting
# --------------------------------------------------------------------------- #
def test_clahe_output_properties(lowcontrast):
    clahe = equalize_clahe(lowcontrast, clip_limit=2.0, tiles=8)
    assert clahe.dtype == np.uint8 and clahe.shape == lowcontrast.shape
    before = histogram_stats(lowcontrast)
    after = histogram_stats(clahe)
    assert after["std"] > before["std"]
    assert after["range"] > before["range"]
    assert after["occupied"] > before["occupied"]


def test_clahe_limits_noise_versus_global(noisy):
    global_out = equalize_global(noisy)
    clahe = equalize_clahe(noisy, clip_limit=2.0, tiles=8)
    assert float(clahe.std()) < float(global_out.std())
    assert float(clahe.std()) > float(noisy.std()) - 1.0


def test_clahe_is_deterministic(lowcontrast):
    first = equalize_clahe(lowcontrast, clip_limit=2.5, tiles=8)
    second = equalize_clahe(lowcontrast, clip_limit=2.5, tiles=8)
    assert np.array_equal(first, second)


def test_clahe_clip_limit_changes_the_result(lowcontrast):
    clipped = equalize_clahe(lowcontrast, clip_limit=0.05, tiles=8)
    unclipped = equalize_clahe(lowcontrast, clip_limit=1e6, tiles=8)
    assert not np.array_equal(clipped, unclipped)
    # clipping flattens peaks, so the unconstrained result stretches more
    assert float(clipped.std()) <= float(unclipped.std())
    assert int(clipped.min()) == 0 and int(clipped.max()) == 255


def test_clahe_uniform_image_unchanged():
    flat = np.full((32, 32), 90, dtype=np.uint8)
    assert np.array_equal(equalize_clahe(flat, tiles=4), flat)


def test_clahe_validates_clip_limit(lowcontrast):
    with pytest.raises(HistError, match="clip_limit must be > 0"):
        equalize_clahe(lowcontrast, clip_limit=0.0)
    with pytest.raises(HistError, match="clip_limit must be > 0"):
        equalize_clahe(lowcontrast, clip_limit=-1.0)
    with pytest.raises(HistError, match="clip_limit must be > 0"):
        equalize_clahe(lowcontrast, clip_limit=float("nan"))


def test_clahe_validates_tiles(lowcontrast):
    with pytest.raises(HistError, match="tiles must be >= 2"):
        equalize_clahe(lowcontrast, tiles=1)
    with pytest.raises(HistError, match="larger than the image"):
        equalize_clahe(lowcontrast, tiles=200)
    with pytest.raises(HistError, match="divisible"):
        equalize_clahe(lowcontrast, tiles=7)


def test_clahe_preserves_shape_with_smaller_grid(lowcontrast):
    clahe = equalize_clahe(lowcontrast, clip_limit=2.0, tiles=4)
    assert clahe.shape == lowcontrast.shape
    assert int(clahe.min()) == 0 and int(clahe.max()) == 255


# --------------------------------------------------------------------------- #
# Dispatch and report
# --------------------------------------------------------------------------- #
def test_equalize_dispatch(lowcontrast):
    assert np.array_equal(equalize(lowcontrast, "global"),
                          equalize_global(lowcontrast))
    assert np.array_equal(equalize(lowcontrast, "clahe", 2.0, 8),
                          equalize_clahe(lowcontrast, 2.0, 8))
    with pytest.raises(HistError, match="unknown method"):
        equalize(lowcontrast, "adaptive")


def test_render_report_sections(lowcontrast):
    equalized = equalize_global(lowcontrast)
    text = render_report(lowcontrast, equalized, "global", {})
    assert "HISTOGRAM EQUALIZER" in text
    assert "PSNR vs original" in text
    assert "bins used" in text
    assert "Method       : global" in text
    clahe_text = render_report(lowcontrast, equalize_clahe(lowcontrast),
                               "clahe", {"clip_limit": 2.0, "tiles": 8})
    assert "clip 2.0" in clahe_text and "tiles 8" in clahe_text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out
    assert "ASCII histogram before" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(HistError, match="bundled sample"):
        run_demo(image_path=tmp_path / "nope.png")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "global CDF + CLAHE-style limiting" not in out  # BANNER hidden
    assert "Cross-checks OK" in out


def test_cli_global_on_file(capsys):
    assert main(["--file", str(LOW_IMG)]) == 0
    out = capsys.readouterr().out
    assert "PSNR vs original" in out and "Done." in out


def test_cli_clahe_with_json(tmp_path, capsys):
    json_path = tmp_path / "stats.json"
    assert main(["--file", str(LOW_IMG), "--method", "clahe",
                 "--clip", "3.0", "--tiles", "4", "--json", str(json_path),
                 "--quiet"]) == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["method"] == "clahe"
    assert payload["clip"] == 3.0 and payload["tiles"] == 4
    assert payload["after"]["std"] > payload["before"]["std"]


def test_cli_out_and_ascii(tmp_path, capsys):
    out_path = tmp_path / "eq.png"
    assert main(["--file", str(LOW_IMG), "--out", str(out_path),
                 "--ascii"]) == 0
    out = capsys.readouterr().out
    assert out_path.is_file()
    assert load_image(out_path).shape == (128, 128)
    assert "Histogram after:" in out and "|" in out


def test_cli_missing_file_returns_2(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.png")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_bad_clip_fast_fails(tmp_path, capsys):
    # flag validated before the (missing) file is touched
    assert main(["--file", str(tmp_path / "nope.png"),
                 "--method", "clahe", "--clip", "0"]) == 2
    assert "--clip must be > 0" in capsys.readouterr().err


def test_cli_bad_tiles_fast_fails(capsys):
    assert main(["--file", str(LOW_IMG), "--tiles", "1"]) == 2
    assert "--tiles must be >= 2" in capsys.readouterr().err


def test_cli_tile_grid_mismatch_returns_2(capsys):
    assert main(["--file", str(LOW_IMG), "--method", "clahe",
                 "--tiles", "7"]) == 2
    assert "divisible" in capsys.readouterr().err


def test_cli_usage_errors(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    capsys.readouterr()
    with pytest.raises(SystemExit) as bad:
        main(["--file", str(LOW_IMG), "--method", "adaptive"])
    assert bad.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_project_has_sample_data():
    assert LOW_IMG.is_file()
    assert NOISY_IMG.is_file()
    assert LOW_IMG.parent == PROJECT_ROOT / "data"
    assert set(METHODS) == {"global", "clahe"}
