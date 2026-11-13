"""Tests for the Image Denoising Autoencoder project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from autoencoder import (  # noqa: E402
    DEMO_CSV,
    IMAGE_SIZE,
    MIN_PER_CLASS,
    MIN_ROWS,
    NOISE_SIGMA,
    PIXELS,
    SHAPES,
    AError,
    DenoisingAE,
    add_noise,
    ascii_image,
    build_autoencoder,
    load_images,
    psnr,
    render_report,
    run_demo,
    to_tensor,
    train_model,
)
from main import main, parse_pixels  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
N_PIXELS = IMAGE_SIZE * IMAGE_SIZE


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _grid(n: int = 360) -> pd.DataFrame:
    """n valid rows cycling the 3 shape classes with varying pixels."""
    base = np.arange(N_PIXELS)
    rows = []
    for i in range(n):
        pixels = ((base + i) % 17) / 16.0
        rows.append(list(np.round(pixels, 4)) + [i % 3])
    return pd.DataFrame(rows, columns=list(PIXELS) + ["label"])


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_images(DEMO_CSV)


@pytest.fixture(scope="module")
def trained(sample):
    # 2 epochs keeps the suite fast; the demo covers real convergence
    return train_model(sample, epochs=2, lr=5e-3, batch_size=64)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 600
    assert list(sample.columns) == list(PIXELS) + ["label"]
    assert set(sample["label"]) == set(range(len(SHAPES)))
    counts = sample["label"].value_counts()
    assert counts.min() >= MIN_PER_CLASS
    for column in PIXELS[:20]:
        assert sample[column].between(0, 1).all()


def test_load_missing_file(tmp_path):
    with pytest.raises(AError, match="not found"):
        load_images(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("image_0,label\n0.5,1\n", encoding="utf-8")
    with pytest.raises(AError, match="missing column"):
        load_images(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(list(PIXELS) + ["label"]) + "\n",
                    encoding="utf-8")
    with pytest.raises(AError, match="no rows"):
        load_images(path)


def test_load_non_numeric_pixel(tmp_path):
    frame = _grid()
    frame["image_3"] = frame["image_3"].astype(object)
    frame.loc[0, "image_3"] = "dark"
    path = tmp_path / "s.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(AError, match="'image_3' contains non-numeric"):
        load_images(path)


def test_load_pixel_above_one(tmp_path):
    frame = _grid()
    frame.loc[0, "image_10"] = 1.5
    path = tmp_path / "s.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(AError, match="'image_10' outside 0..1"):
        load_images(path)


def test_load_negative_pixel(tmp_path):
    frame = _grid()
    frame.loc[0, "image_11"] = -0.2
    path = tmp_path / "s.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(AError, match="'image_11' outside 0..1"):
        load_images(path)


def test_load_label_out_of_range(tmp_path):
    frame = _grid()
    frame.loc[0, "label"] = 7
    path = tmp_path / "s.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(AError, match="label must be 0..2"):
        load_images(path)


def test_load_fractional_label(tmp_path):
    frame = _grid()
    frame["label"] = frame["label"].astype(float)
    frame.loc[0, "label"] = 1.5
    path = tmp_path / "s.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(AError, match="whole numbers"):
        load_images(path)


def test_load_too_few_rows(tmp_path):
    path = tmp_path / "short.csv"
    _grid(100).to_csv(path, index=False)
    with pytest.raises(AError, match=f"at least {MIN_ROWS}"):
        load_images(path)


def test_load_sparse_class(tmp_path):
    frame = _grid(600)            # 200 per class; drop one class
    frame = frame[frame["label"] != 2]  # drop crosses entirely (400 left)
    path = tmp_path / "sparse.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(AError, match="too few images.*2"):
        load_images(path)


# --------------------------------------------------------------------------- #
# Noise and tensors
# --------------------------------------------------------------------------- #
def test_add_noise_preserves_shape_and_range():
    x = torch.rand(4, 1, IMAGE_SIZE, IMAGE_SIZE)
    gen = torch.Generator().manual_seed(1)
    noisy = add_noise(x, 0.3, gen)
    assert noisy.shape == x.shape
    assert float(noisy.min()) >= 0.0 and float(noisy.max()) <= 1.0


def test_add_noise_is_deterministic_per_seed():
    x = torch.rand(2, 1, IMAGE_SIZE, IMAGE_SIZE)
    a = add_noise(x, 0.3, torch.Generator().manual_seed(5))
    b = add_noise(x, 0.3, torch.Generator().manual_seed(5))
    c = add_noise(x, 0.3, torch.Generator().manual_seed(6))
    assert torch.equal(a, b)
    assert not torch.equal(a, c)


def test_add_noise_actually_changes_pixels():
    x = torch.zeros(8, 1, IMAGE_SIZE, IMAGE_SIZE)
    noisy = add_noise(x, 0.3, torch.Generator().manual_seed(1))
    assert not torch.equal(noisy, x)


def test_to_tensor_shape(sample):
    x, y = to_tensor(sample.head(6))
    assert x.shape == (6, 1, IMAGE_SIZE, IMAGE_SIZE)
    assert y.shape == (6,)
    assert x.dtype == torch.float32
    assert float(x.max()) <= 1.0


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def test_build_autoencoder_seeded():
    first = build_autoencoder(latent=16, seed=3)
    second = build_autoencoder(latent=16, seed=3)
    for a, b in zip(first.parameters(), second.parameters()):
        assert torch.equal(a, b)


def test_model_forward_roundtrip_shape():
    model = build_autoencoder(latent=16, seed=1)
    x = torch.rand(3, 1, IMAGE_SIZE, IMAGE_SIZE)
    out = model(x)
    assert out.shape == x.shape
    detached = out.detach()
    assert float(detached.min()) >= 0.0 and float(detached.max()) <= 1.0
    z = model.encode(x)
    assert z.shape == (3, 16)
    assert model.decode(z).shape == x.shape


def test_model_rejects_bad_latent():
    with pytest.raises(AError, match="latent"):
        DenoisingAE(latent=0)


# --------------------------------------------------------------------------- #
# Metrics helpers
# --------------------------------------------------------------------------- #
def test_psnr_known_values():
    assert psnr(0.01) == pytest.approx(20.0)
    assert psnr(1.0) == pytest.approx(0.0)
    assert psnr(0.0) == float("inf")


def test_psnr_ordering():
    assert psnr(0.001) > psnr(0.01) > psnr(0.1)


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
def test_train_valid_metrics(trained):
    assert trained.test_mse > 0 and trained.noisy_mse > 0
    assert np.isfinite(trained.test_psnr) and np.isfinite(trained.noisy_psnr)
    assert trained.rows == 600
    assert trained.train_rows == 450 and trained.test_rows == 150
    assert len(trained.history) == 2
    assert {"loss", "val_loss"} <= set(trained.history[0])


def test_noisy_baseline_reflects_sigma(trained):
    # MSE of clamped N(0, sigma^2) noise against binary images
    assert 0.01 < trained.noisy_mse < 0.12


def test_reported_mse_matches_reconstructions(trained):
    recomputed = float(np.mean((trained.test_recon
                                - trained.test_clean) ** 2))
    assert trained.test_mse == pytest.approx(recomputed, abs=1e-9)


def test_reconstructions_in_range(trained):
    assert trained.test_recon.min() >= 0.0
    assert trained.test_recon.max() <= 1.0
    assert trained.test_clean.shape == (150, N_PIXELS)
    assert trained.test_noisy.shape == (150, N_PIXELS)
    assert len(trained.test_labels) == 150


def test_per_shape_mse_covers_all_shapes(trained):
    assert set(trained.per_shape_mse) == set(SHAPES)
    assert all(0 < v < 1 for v in trained.per_shape_mse.values())


def test_train_is_deterministic(sample):
    first = train_model(sample, epochs=2, lr=5e-3, seed=7)
    second = train_model(sample, epochs=2, lr=5e-3, seed=7)
    assert first.test_mse == second.test_mse
    assert [h["loss"] for h in first.history] == \
        [h["loss"] for h in second.history]


def test_seed_changes_training(sample):
    first = train_model(sample, epochs=2, lr=5e-3, seed=1)
    second = train_model(sample, epochs=2, lr=5e-3, seed=2)
    assert [h["loss"] for h in first.history] != \
        [h["loss"] for h in second.history]


def test_more_epochs_reduce_loss(sample):
    quick = train_model(sample, epochs=1, lr=5e-3)
    longer = train_model(sample, epochs=4, lr=5e-3)
    assert longer.history[-1]["loss"] < quick.history[-1]["loss"]


def test_result_to_dict(trained):
    payload = trained.to_dict()
    json.dumps(payload)
    assert payload["epochs"] == 2
    assert payload["latent"] == 32
    assert payload["test_mse"] < payload["noisy_mse"] * 3
    assert set(payload["per_shape_mse"]) == set(SHAPES)


# --------------------------------------------------------------------------- #
# Configuration validation
# --------------------------------------------------------------------------- #
def test_train_rejects_bad_hyperparams(sample):
    with pytest.raises(AError, match="epochs"):
        train_model(sample, epochs=0)
    with pytest.raises(AError, match="lr must be"):
        train_model(sample, lr=0.0)
    with pytest.raises(AError, match="batch_size"):
        train_model(sample, batch_size=0)
    with pytest.raises(AError, match="test_fraction"):
        train_model(sample, test_fraction=0.9)


def test_train_rejects_bad_sigma(sample):
    with pytest.raises(AError, match="sigma"):
        train_model(sample, sigma=0.0)
    with pytest.raises(AError, match="sigma"):
        train_model(sample, sigma=1.5)


def test_train_rejects_missing_columns():
    with pytest.raises(AError, match="missing column"):
        train_model(_grid().drop(columns=["image_5"]))


def test_train_rejects_non_finite_pixels():
    frame = _grid(360)
    frame.loc[0, "image_7"] = np.nan
    with pytest.raises(AError, match="non-finite"):
        train_model(frame)


# --------------------------------------------------------------------------- #
# Denoise / encode APIs and ASCII
# --------------------------------------------------------------------------- #
def test_encode_returns_latent(trained, sample):
    image = sample.iloc[0][list(PIXELS)].to_numpy(dtype=float)
    latent = trained.encode(image)
    assert latent.shape == (trained.model.latent,)
    assert np.isfinite(latent).all()


def test_denoise_returns_image(trained, sample):
    image = sample.iloc[0][list(PIXELS)].to_numpy(dtype=float)
    out = trained.denoise(image)
    assert out.shape == (N_PIXELS,)
    assert out.min() >= 0.0 and out.max() <= 1.0


def test_denoise_rejects_wrong_length(trained):
    with pytest.raises(AError, match="784 pixels"):
        trained.denoise(np.zeros(10))


def test_denoise_rejects_out_of_range(trained):
    with pytest.raises(AError, match="0..1"):
        trained.denoise(np.full(N_PIXELS, 3.0))


def test_denoise_rejects_nan(trained):
    bad = np.zeros(N_PIXELS)
    bad[4] = np.nan
    with pytest.raises(AError, match="finite"):
        trained.denoise(bad)


def test_ascii_image_shape():
    art = ascii_image(np.random.default_rng(0).random(N_PIXELS))
    lines = art.splitlines()
    assert len(lines) == 14 and all(len(line) == 14 for line in lines)


def test_ascii_image_rejects_wrong_size():
    with pytest.raises(AError, match="784 pixels"):
        ascii_image(np.zeros(9))


def test_parse_pixels():
    values = parse_pixels(",".join(["0.5"] * N_PIXELS))
    assert len(values) == N_PIXELS and values[0] == 0.5


def test_parse_pixels_wrong_count():
    with pytest.raises(AError, match="expected 784"):
        parse_pixels("0,1,0")


def test_parse_pixels_not_a_number():
    with pytest.raises(AError, match="not a number for image_"):
        parse_pixels(",".join(["0.5"] * (N_PIXELS - 1) + ["opaque"]))


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections(trained):
    text = render_report(trained)
    assert "IMAGE DENOISING AUTOENCODER" in text
    assert "Learning curve" in text
    assert "Hold-out denoising:" in text
    assert "noisy input" in text
    assert "AE reconstruction" in text
    assert "Per-shape reconstruction MSE:" in text
    for name in SHAPES:
        assert name in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Sample hold-out image" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(AError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_file_training(capsys):
    assert main(["--file", str(DEMO_CSV), "--epochs", "2"]) == 0
    out = capsys.readouterr().out
    assert "Hold-out denoising:" in out and "Done." in out


def test_cli_denoise_path(capsys):
    pixels = ",".join(["0.0"] * (N_PIXELS - 90) + ["1.0"] * 90)
    assert main(["--denoise", pixels, "--epochs", "2", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Denoised preview (14x14):" in out


def test_cli_denoise_bad_count_fails_fast(capsys):
    # parsing happens before training, so this must not take seconds
    assert main(["--denoise", "1,2,3"]) == 2
    assert "expected 784" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--epochs", "2",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["epochs"] == 2
    assert set(payload["per_shape_mse"]) == set(SHAPES)


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_invalid_schema(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "missing column" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_project_has_sample_data():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent == PROJECT_ROOT / "data"
