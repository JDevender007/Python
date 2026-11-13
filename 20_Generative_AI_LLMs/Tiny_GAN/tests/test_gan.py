"""Tests for the Tiny GAN project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from gan import (  # noqa: E402
    COVERAGE_RADIUS,
    DATA_FILE,
    DEFAULT_STEPS,
    GanError,
    Generator,
    Discriminator,
    coverage,
    load_moons,
    mean_nearest_distance,
    mode_balance,
    run_demo,
    sample,
    standardize,
    train_gan,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "data" / "moons.csv"


@pytest.fixture(scope="module")
def moons():
    return load_moons(DATA)


@pytest.fixture(scope="module")
def scaled(moons):
    return standardize(moons.points)


@pytest.fixture(scope="module")
def trained(moons):
    # 40 steps is enough to exercise every code path quickly
    return train_gan(moons, steps=40, seed=5)


# --------------------------------------------------------------------------- #
# Dataset loading
# --------------------------------------------------------------------------- #
def test_load_moons_reads_every_row(moons):
    assert moons.size == 2000
    assert tuple(moons.points.shape) == (2000, 2)
    assert moons.labels.shape[0] == moons.size


def test_load_moons_labels_are_binary(moons):
    assert set(moons.labels.tolist()) == {0, 1}


def test_load_moons_balance_is_balanced(moons):
    assert 0.4 < moons.balance() < 0.6


def test_load_moons_points_are_finite(moons):
    assert torch.isfinite(moons.points).all()


def test_load_moons_missing_file(tmp_path):
    with pytest.raises(GanError, match="dataset not found"):
        load_moons(tmp_path / "ghost.csv")


def test_load_moons_rejects_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("x,y\n1,2\n", encoding="utf-8")
    with pytest.raises(GanError, match="missing columns"):
        load_moons(path)


def test_load_moons_rejects_non_numeric(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("x,y,label\n1,oops,0\n", encoding="utf-8")
    with pytest.raises(GanError, match="not numeric"):
        load_moons(path)


def test_load_moons_rejects_non_finite(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("x,y,label\n1,nan,0\n", encoding="utf-8")
    with pytest.raises(GanError, match="not finite"):
        load_moons(path)


def test_load_moons_rejects_bad_label(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("x,y,label\n1,2,7\n", encoding="utf-8")
    with pytest.raises(GanError, match="expected 0/1"):
        load_moons(path)


def test_load_moons_rejects_tiny_dataset(tmp_path):
    path = tmp_path / "small.csv"
    rows = ["x,y,label"] + [f"{i},0,0" for i in range(10)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(GanError, match="at least 200 rows"):
        load_moons(path)


def test_moons_to_dict(moons):
    payload = moons.to_dict()
    assert payload["rows"] == 2000
    assert payload["features"] == 2
    assert math.isclose(payload["second_moon_share"], moons.balance(),
                        abs_tol=1e-4)


# --------------------------------------------------------------------------- #
# Standardisation
# --------------------------------------------------------------------------- #
def test_standardize_is_zero_mean(scaled):
    data, _, _ = scaled
    assert abs(float(data.mean())) < 1e-5


def test_standardize_is_unit_variance(scaled):
    data, _, _ = scaled
    assert abs(float(data.std(unbiased=False)) - 1.0) < 1e-3


def test_standardize_returns_scaler(moons, scaled):
    _, mean, std = scaled
    assert mean.shape == (2,) and std.shape == (2,)
    assert torch.all(std > 0)


def test_standardize_rejects_wrong_shape():
    with pytest.raises(GanError, match=r"expected an \(n, 2\) tensor"):
        standardize(torch.zeros(3, 4))


def test_standardize_rejects_empty():
    with pytest.raises(GanError, match="empty tensor"):
        standardize(torch.zeros(0, 2))


def test_standardize_handles_constant_feature():
    points = torch.tensor([[1.0, 2.0], [1.0, 4.0], [1.0, 6.0]])
    data, _, std = standardize(points)
    assert torch.isfinite(data).all()
    assert float(std[0]) == 1.0


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
def test_generator_output_shape():
    model = Generator(latent_dim=4, hidden=8)
    assert model(torch.zeros(5, 4)).shape == (5, 2)


def test_generator_has_learnable_parameters():
    assert sum(p.numel() for p in Generator().parameters()) > 100


@pytest.mark.parametrize("latent", [0, -2])
def test_generator_rejects_bad_latent(latent):
    with pytest.raises(GanError, match="latent_dim must be >= 1"):
        Generator(latent_dim=latent)


def test_generator_rejects_tiny_hidden():
    with pytest.raises(GanError, match="hidden must be >= 4"):
        Generator(hidden=2)


def test_discriminator_output_shape():
    model = Discriminator(hidden=8)
    assert model(torch.zeros(5, 2)).shape == (5,)


def test_discriminator_rejects_tiny_hidden():
    with pytest.raises(GanError, match="hidden must be >= 4"):
        Discriminator(hidden=3)


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
def test_training_records_every_step(trained):
    assert len(trained.d_losses) == 40
    assert len(trained.g_losses) == 40


def test_training_losses_are_finite(trained):
    assert all(math.isfinite(value) for value in trained.d_losses)
    assert all(math.isfinite(value) for value in trained.g_losses)


def test_training_returns_both_networks(trained):
    assert isinstance(trained.generator, Generator)
    assert isinstance(trained.discriminator, Discriminator)


def test_training_is_deterministic(moons):
    first = train_gan(moons, steps=12, seed=2)
    second = train_gan(moons, steps=12, seed=2)
    assert first.d_losses == second.d_losses
    assert first.g_losses == second.g_losses


def test_training_seed_changes_losses(moons):
    first = train_gan(moons, steps=12, seed=2)
    other = train_gan(moons, steps=12, seed=3)
    assert first.d_losses != other.d_losses


def test_training_keeps_scaler(moons, scaled):
    result = train_gan(moons, steps=5)
    _, mean, std = scaled
    assert torch.allclose(result.mean, mean)
    assert torch.allclose(result.std, std)


@pytest.mark.parametrize("steps", [0, -5])
def test_training_rejects_bad_steps(moons, steps):
    with pytest.raises(GanError, match="steps must be >= 1"):
        train_gan(moons, steps=steps)


@pytest.mark.parametrize("batch", [1, 0])
def test_training_rejects_bad_batch(moons, batch):
    with pytest.raises(GanError, match="batch_size must be >= 2"):
        train_gan(moons, steps=3, batch_size=batch)


def test_training_rejects_oversized_batch(moons):
    with pytest.raises(GanError, match="exceeds dataset size"):
        train_gan(moons, steps=3, batch_size=moons.size + 1)


@pytest.mark.parametrize("lr", [0.0, -0.1])
def test_training_rejects_bad_lr(moons, lr):
    with pytest.raises(GanError, match="lr must be > 0"):
        train_gan(moons, steps=3, lr=lr)


def test_training_result_to_dict(trained):
    payload = trained.to_dict()
    json.dumps(payload)
    assert payload["steps"] == 40
    assert len(payload["d_loss"]) == 2
    assert len(payload["g_loss"]) == 2


# --------------------------------------------------------------------------- #
# Sampling
# --------------------------------------------------------------------------- #
def test_sample_shape(trained):
    assert sample(trained, 64).shape == (64, 2)


def test_sample_is_deterministic(trained):
    assert torch.equal(sample(trained, 32, seed=4),
                       sample(trained, 32, seed=4))


def test_sample_seed_changes_points(trained):
    assert not torch.equal(sample(trained, 32, seed=4),
                           sample(trained, 32, seed=5))


def test_sample_values_are_finite(trained):
    assert torch.isfinite(sample(trained, 128)).all()


@pytest.mark.parametrize("count", [0, -3])
def test_sample_rejects_bad_count(trained, count):
    with pytest.raises(GanError, match="count must be >= 1"):
        sample(trained, count)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def test_coverage_of_identical_sets_is_one():
    points = torch.randn(50, 2)
    assert coverage(points, points.clone()) == pytest.approx(1.0)


def test_coverage_of_far_points_is_zero():
    real = torch.zeros(10, 2)
    fake = torch.full((10, 2), 100.0)
    assert coverage(real, fake) == 0.0


def test_coverage_rejects_empty_input():
    with pytest.raises(GanError, match="both real and generated"):
        coverage(torch.zeros(0, 2), torch.zeros(4, 2))


def test_coverage_rejects_bad_radius():
    points = torch.zeros(2, 2)
    with pytest.raises(GanError, match="radius must be > 0"):
        coverage(points, points, radius=0)


def test_nearest_distance_of_identical_sets_is_zero():
    points = torch.randn(20, 2)
    assert mean_nearest_distance(points, points.clone()) == pytest.approx(0.0)


def test_nearest_distance_grows_with_offset():
    real = torch.zeros(10, 2)
    near = real + 0.1
    far = real + 3.0
    assert mean_nearest_distance(real, near) < mean_nearest_distance(real, far)


def test_nearest_distance_rejects_empty():
    with pytest.raises(GanError, match="both point sets"):
        mean_nearest_distance(torch.zeros(0, 2), torch.zeros(3, 2))


def test_mode_balance_sums_to_one(moons, scaled, trained):
    data, _, _ = scaled
    balance = mode_balance(data, moons.labels, sample(trained, 300, seed=1))
    assert math.isclose(sum(balance.values()), 1.0, abs_tol=1e-6)


def test_mode_balance_tracks_the_real_split(moons, scaled, trained):
    data, _, _ = scaled
    balance = mode_balance(data, moons.labels, data.clone())
    assert math.isclose(balance["moon1"], moons.balance(), abs_tol=0.01)


def test_mode_balance_rejects_label_mismatch(moons, scaled):
    data, _, _ = scaled
    with pytest.raises(GanError, match="labels must match"):
        mode_balance(data, moons.labels[:-1], data)


def test_mode_balance_rejects_empty_fake(moons, scaled):
    data, _, _ = scaled
    with pytest.raises(GanError, match="needs generated points"):
        mode_balance(data, moons.labels, torch.zeros(0, 2))


# --------------------------------------------------------------------------- #
# Demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_prints_cross_checks(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out
    assert "Coverage" in out


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


def test_cli_requires_a_mode():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_trains_on_csv(capsys):
    assert main(["--data", str(DATA), "--steps", "15"]) == 0
    out = capsys.readouterr().out
    assert "Coverage" in out
    assert "Discriminator" in out


@pytest.mark.parametrize("flag,value,needle", [
    ("--steps", "0", "steps must be >= 1"),
    ("--latent", "0", "latent must be >= 1"),
    ("--batch-size", "1", "batch-size must be >= 2"),
])
def test_cli_validates_flags(flag, value, needle, capsys):
    assert main(["--data", str(DATA), flag, value]) == 2
    assert needle in capsys.readouterr().err


def test_cli_missing_dataset(tmp_path, capsys):
    assert main(["--data", str(tmp_path / "nope.csv")]) == 2
    assert "dataset not found" in capsys.readouterr().err


def test_cli_json_export(tmp_path, capsys):
    out = tmp_path / "run.json"
    assert main(["--data", str(DATA), "--steps", "20", "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["rows"] == 2000
    assert payload["steps"] == 20
    assert "coverage" in payload
    assert capsys.readouterr().out == ""


def test_bundled_dataset_is_present():
    assert DATA_FILE.is_file()
    assert DEFAULT_STEPS >= 1
    assert COVERAGE_RADIUS > 0
