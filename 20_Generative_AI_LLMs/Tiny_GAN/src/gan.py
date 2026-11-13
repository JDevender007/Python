"""A tiny generative adversarial network trained on two moons - offline.

A 2-layer MLP generator maps 8-dimensional noise to 2-D points; a 2-layer
MLP discriminator scores them against a bundled two-moons dataset. Both
are trained with BCE-with-logits for a few hundred steps on CPU, then the
generated cloud is scored for coverage, nearest-neighbour distance and
mode balance against the real data.

No network, no downloads - the dataset ships in data/moons.csv.

Public API
----------
load_moons           read the bundled two-moons CSV
standardize          zero-mean unit-variance scaling
Generator            noise -> points MLP
Discriminator        points -> logit MLP
train_gan            adversarial training loop
sample               draw standardised points from a generator
coverage             fraction of real points covered by samples
mean_nearest_distance  realism proxy in standardised space
mode_balance         share of samples on each moon
run_demo             offline demo with self-checks
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

import torch
from torch import nn

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "moons.csv"

LATENT_DIM = 8
HIDDEN = 64
DEFAULT_STEPS = 800
DEFAULT_BATCH = 128
DEFAULT_LR = 2e-3
MIN_ROWS = 200
COVERAGE_RADIUS = 0.35


class GanError(RuntimeError):
    """Raised for missing data, bad hyperparameters or corrupt files."""


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@dataclass
class Moons:
    points: torch.Tensor
    labels: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.points.shape[0])

    def balance(self) -> float:
        """Share of points on the second moon."""
        return float(self.labels.float().mean())

    def to_dict(self) -> dict:
        return {"rows": self.size, "features": int(self.points.shape[1]),
                "second_moon_share": round(self.balance(), 4)}


def load_moons(path: Path | str | None = None) -> Moons:
    target = Path(path) if path is not None else DATA_FILE
    if not target.is_file():
        raise GanError(f"dataset not found: {target}")

    xs: list[float] = []
    ys: list[float] = []
    labels: list[int] = []
    with target.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = {"x", "y", "label"} - set(header)
        if missing:
            raise GanError(f"dataset is missing columns {sorted(missing)}")
        for number, row in enumerate(reader, start=2):
            try:
                x = float(row["x"])
                y = float(row["y"])
                label = int(row["label"])
            except (TypeError, ValueError) as exc:
                raise GanError(f"line {number} is not numeric") from exc
            if not (math.isfinite(x) and math.isfinite(y)):
                raise GanError(f"line {number} is not finite")
            if label not in (0, 1):
                raise GanError(f"line {number} has label {label}, expected 0/1")
            xs.append(x)
            ys.append(y)
            labels.append(label)

    if len(xs) < MIN_ROWS:
        raise GanError(f"dataset needs at least {MIN_ROWS} rows, "
                       f"got {len(xs)}")
    points = torch.tensor(list(zip(xs, ys)), dtype=torch.float32)
    return Moons(points=points,
                 labels=torch.tensor(labels, dtype=torch.long))


def standardize(points: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor,
                                               torch.Tensor]:
    """Zero-mean, unit-variance per feature. Never divides by zero."""
    if points.ndim != 2 or points.shape[1] != 2:
        raise GanError(f"expected an (n, 2) tensor, got {tuple(points.shape)}")
    if points.shape[0] == 0:
        raise GanError("cannot standardise an empty tensor")
    mean = points.mean(dim=0)
    std = points.std(dim=0, unbiased=False)
    std = torch.where(std > 1e-8, std, torch.ones_like(std))
    return (points - mean) / std, mean, std


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class Generator(nn.Module):
    """Noise vector -> 2-D point."""

    def __init__(self, latent_dim: int = LATENT_DIM, hidden: int = HIDDEN
                 ) -> None:
        super().__init__()
        if latent_dim < 1:
            raise GanError(f"latent_dim must be >= 1, got {latent_dim}")
        if hidden < 4:
            raise GanError(f"hidden must be >= 4, got {hidden}")
        self.latent_dim = latent_dim
        self.net = nn.Sequential(
            nn.Linear(latent_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 2),
        )

    def forward(self, noise: torch.Tensor) -> torch.Tensor:
        return self.net(noise)


class Discriminator(nn.Module):
    """2-D point -> single real/fake logit."""

    def __init__(self, hidden: int = HIDDEN) -> None:
        super().__init__()
        if hidden < 4:
            raise GanError(f"hidden must be >= 4, got {hidden}")
        self.net = nn.Sequential(
            nn.Linear(2, hidden),
            nn.LeakyReLU(0.2),
            nn.Linear(hidden, hidden),
            nn.LeakyReLU(0.2),
            nn.Linear(hidden, 1),
        )

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        return self.net(points).squeeze(-1)


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
@dataclass
class GanResult:
    generator: Generator
    discriminator: Discriminator
    d_losses: list[float] = field(default_factory=list)
    g_losses: list[float] = field(default_factory=list)
    mean: torch.Tensor = field(default_factory=lambda: torch.zeros(2))
    std: torch.Tensor = field(default_factory=lambda: torch.ones(2))
    steps: int = 0
    latent_dim: int = LATENT_DIM

    @property
    def initial_d_loss(self) -> float:
        return self.d_losses[0]

    @property
    def final_d_loss(self) -> float:
        return self.d_losses[-1]

    @property
    def initial_g_loss(self) -> float:
        return self.g_losses[0]

    @property
    def final_g_loss(self) -> float:
        return self.g_losses[-1]

    def to_dict(self) -> dict:
        return {
            "steps": self.steps,
            "latent_dim": self.latent_dim,
            "d_loss": [round(self.initial_d_loss, 4),
                       round(self.final_d_loss, 4)],
            "g_loss": [round(self.initial_g_loss, 4),
                       round(self.final_g_loss, 4)],
        }


def train_gan(moons: Moons, steps: int = DEFAULT_STEPS,
              batch_size: int = DEFAULT_BATCH, lr: float = DEFAULT_LR,
              latent_dim: int = LATENT_DIM, seed: int = 0) -> GanResult:
    """Alternating D/G updates with BCE-with-logits."""
    if steps < 1:
        raise GanError(f"steps must be >= 1, got {steps}")
    if batch_size < 2:
        raise GanError(f"batch_size must be >= 2, got {batch_size}")
    if batch_size > moons.size:
        raise GanError(f"batch_size {batch_size} exceeds dataset "
                       f"size {moons.size}")
    if not math.isfinite(lr) or lr <= 0:
        raise GanError(f"lr must be > 0, got {lr}")

    data, mean, std = standardize(moons.points)

    torch.manual_seed(seed)
    generator = Generator(latent_dim=latent_dim)
    discriminator = Discriminator()

    g_optim = torch.optim.Adam(generator.parameters(), lr=lr, betas=(0.5, 0.999))
    d_optim = torch.optim.Adam(discriminator.parameters(), lr=lr,
                               betas=(0.5, 0.999))
    loss_fn = nn.BCEWithLogitsLoss()
    generator = generator.float()
    discriminator = discriminator.float()

    result = GanResult(generator=generator, discriminator=discriminator,
                       mean=mean, std=std, steps=steps, latent_dim=latent_dim)

    batch_generator = torch.Generator().manual_seed(seed + 1)
    for _ in range(steps):
        index = torch.randint(0, moons.size, (batch_size,),
                              generator=batch_generator)
        real = data[index]

        noise = torch.randn(batch_size, latent_dim,
                            generator=batch_generator)
        fake = generator(noise).detach()

        real_logits = discriminator(real)
        fake_logits = discriminator(fake)
        d_loss = (loss_fn(real_logits, torch.ones_like(real_logits)) +
                  loss_fn(fake_logits, torch.zeros_like(fake_logits))) / 2
        d_optim.zero_grad()
        d_loss.backward()
        d_optim.step()

        noise = torch.randn(batch_size, latent_dim,
                            generator=batch_generator)
        fake_logits = discriminator(generator(noise))
        g_loss = loss_fn(fake_logits, torch.ones_like(fake_logits))
        g_optim.zero_grad()
        g_loss.backward()
        g_optim.step()

        result.d_losses.append(float(d_loss.detach()))
        result.g_losses.append(float(g_loss.detach()))
    return result


def sample(result: GanResult, count: int = 512,
           seed: int = 0) -> torch.Tensor:
    """Draw standardised points from the trained generator."""
    if count < 1:
        raise GanError(f"count must be >= 1, got {count}")
    generator = torch.Generator().manual_seed(seed)
    noise = torch.randn(count, result.latent_dim, generator=generator)
    result.generator.eval()
    with torch.no_grad():
        return result.generator(noise).detach()


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def coverage(real: torch.Tensor, fake: torch.Tensor,
             radius: float = COVERAGE_RADIUS) -> float:
    """Share of real points with at least one generated point nearby."""
    if real.shape[0] == 0 or fake.shape[0] == 0:
        raise GanError("coverage needs both real and generated points")
    if radius <= 0:
        raise GanError(f"radius must be > 0, got {radius}")
    distances = torch.cdist(real, fake)
    nearest = distances.min(dim=1).values
    return float((nearest <= radius).float().mean())


def mean_nearest_distance(real: torch.Tensor, fake: torch.Tensor) -> float:
    """Mean distance from each generated point to the closest real point."""
    if real.shape[0] == 0 or fake.shape[0] == 0:
        raise GanError("nearest distance needs both point sets")
    distances = torch.cdist(fake, real)
    return float(distances.min(dim=1).values.mean())


def mode_balance(real: torch.Tensor, labels: torch.Tensor,
                 fake: torch.Tensor) -> dict:
    """Attribute generated points to the nearest moon and report the split."""
    if real.shape[0] != labels.shape[0]:
        raise GanError("labels must match the real points")
    if fake.shape[0] == 0:
        raise GanError("mode balance needs generated points")
    distances = torch.cdist(fake, real)
    nearest = distances.min(dim=1).indices
    assigned = labels[nearest].float()
    second = float(assigned.mean())
    return {"moon0": round(1.0 - second, 4), "moon1": round(second, 4)}


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    root = data_dir or DATA_DIR
    print("=" * 64)
    print(" TINY GAN - offline demo")
    print(" MLP generator vs MLP discriminator on two moons, CPU only.")
    print("=" * 64)

    moons = load_moons(root / "moons.csv")
    print(f"\nDataset         : {moons.size} rows, 2 features, "
          f"second-moon share {moons.balance():.3f}")
    data, mean, std = standardize(moons.points)
    assert abs(float(data.mean())) < 1e-5, "standardisation is off-centre"
    assert abs(float(data.std(unbiased=False)) - 1.0) < 1e-4
    print(f"Scaler          : mean {mean.tolist()}, std {std.tolist()}")

    result = train_gan(moons, steps=DEFAULT_STEPS, seed=7)
    assert len(result.d_losses) == DEFAULT_STEPS
    assert len(result.g_losses) == DEFAULT_STEPS
    assert all(math.isfinite(value) for value in result.d_losses)
    assert all(math.isfinite(value) for value in result.g_losses)
    print(f"Discriminator   : loss {result.initial_d_loss:.3f} -> "
          f"{result.final_d_loss:.3f}")
    print(f"Generator       : loss {result.initial_g_loss:.3f} -> "
          f"{result.final_g_loss:.3f}")

    fake = sample(result, 1000, seed=11)
    assert fake.shape == (1000, 2)
    assert torch.isfinite(fake).all()

    covered = coverage(data, fake, radius=COVERAGE_RADIUS)
    distance = mean_nearest_distance(data, fake)
    balance = mode_balance(data, moons.labels, fake)
    print(f"Coverage        : {covered:.1%} of real points within "
          f"{COVERAGE_RADIUS} (standardised units)")
    print(f"Nearest real    : mean distance {distance:.3f}")
    print(f"Mode balance    : moon0 {balance['moon0']:.1%}, "
          f"moon1 {balance['moon1']:.1%}")

    assert covered > 0.85, f"generator lost the moons: {covered:.2%}"
    assert distance < 0.25, f"generated points are far from real: {distance:.3f}"
    assert min(balance.values()) > 0.10, f"mode collapse: {balance}"

    # determinism of sampling and of the training run
    again = sample(result, 100, seed=11)
    assert torch.equal(again, sample(result, 100, seed=11))
    assert not torch.equal(again, sample(result, 100, seed=12))

    fresh = train_gan(moons, steps=25, seed=3)
    repeat = train_gan(moons, steps=25, seed=3)
    assert fresh.d_losses == repeat.d_losses, "training is not deterministic"
    assert fresh.d_losses != train_gan(moons, steps=25, seed=4).d_losses

    # discriminator must prefer real over noise after training
    critic = result.discriminator
    critic.eval()
    with torch.no_grad():
        real_score = float(critic(data[:500]).mean())
        fake_score = float(critic(sample(result, 500, seed=5)).mean())
    assert real_score > fake_score, (real_score, fake_score)
    print(f"D scores        : real {real_score:+.2f} vs fake {fake_score:+.2f}")

    print("\nCross-checks OK: dataset validated, standardisation exact, "
          "losses finite, coverage and mode balance asserted, sampling "
          "deterministic, training reproducible")
    print("\nDemo completed successfully.")
    return 0
