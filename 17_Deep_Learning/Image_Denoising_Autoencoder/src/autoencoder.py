"""Image denoising autoencoder: a small convolutional AE - offline.

Loads 28x28 grayscale shape images from a local CSV, corrupts them with
seeded Gaussian noise, and trains a convolutional autoencoder to
reconstruct the clean image from the noisy one. Reports hold-out
reconstruction MSE/PSNR against the noisy-input baseline, per-shape
breakdowns, and ASCII previews. Local files only - no network, no
dataset downloads, no model artifacts fetched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn

LOG = logging.getLogger("ae")

IMAGE_SIZE = 28
PIXELS = tuple(f"image_{i}" for i in range(IMAGE_SIZE * IMAGE_SIZE))
REQUIRED_COLUMNS = PIXELS + ("label",)
SHAPES = ("circle", "square", "cross")
MIN_ROWS = 300
MIN_PER_CLASS = 20
NOISE_SIGMA = 0.40
SHADES = " .:-=+*#%@"


class AError(RuntimeError):
    """Raised for missing files, bad schemas, and training failures."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_images(path: str | Path) -> pd.DataFrame:
    """Load the shapes CSV, validate it, and return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise AError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise AError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise AError(
            f"missing column(s): {', '.join(missing[:4])}"
            f"{' ...' if len(missing) > 4 else ''} "
            f"(expected image_0..image_{IMAGE_SIZE * IMAGE_SIZE - 1} "
            f"+ label)"
        )
    if frame.empty:
        raise AError(f"no rows in {source.name}")

    frame = frame.copy()
    for column in PIXELS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise AError(f"column {column!r} contains non-numeric values")
        if not np.isfinite(frame[column]).all():
            raise AError(f"column {column!r} must be finite")
        if not frame[column].between(0.0, 1.0).all():
            raise AError(f"column {column!r} outside 0..1 (grayscale)")

    frame["label"] = pd.to_numeric(frame["label"], errors="coerce")
    if frame["label"].isna().any():
        raise AError("column 'label' contains non-numeric values")
    if not (frame["label"] % 1 == 0).all():
        raise AError("column 'label' must be whole numbers")
    labels = sorted(int(v) for v in frame["label"].unique())
    if not set(labels) <= set(range(len(SHAPES))):
        raise AError(f"label must be 0..{len(SHAPES) - 1} "
                     f"({', '.join(SHAPES)}) (got {labels})")
    if len(frame) < MIN_ROWS:
        raise AError(f"need at least {MIN_ROWS} images, got {len(frame)}")
    counts = frame["label"].value_counts()
    sparse = [c for c in range(len(SHAPES))
              if counts.get(c, 0) < MIN_PER_CLASS]
    if sparse:
        raise AError(
            f"class(es) with too few images (need >= {MIN_PER_CLASS}): "
            f"{', '.join(str(c) for c in sparse)}"
        )

    frame["label"] = frame["label"].astype(int)
    frame = frame.sample(frac=1, random_state=17).reset_index(drop=True)
    LOG.info("loaded %d images from %s", len(frame), source.name)
    return frame


def to_tensor(frame: pd.DataFrame) -> tuple[torch.Tensor, torch.Tensor]:
    """(n, 1, 28, 28) images plus integer labels."""
    x = torch.tensor(frame[list(PIXELS)].to_numpy(dtype=np.float32),
                     dtype=torch.float32).view(-1, 1, IMAGE_SIZE,
                                               IMAGE_SIZE)
    y = torch.tensor(frame["label"].to_numpy(dtype=np.int64),
                     dtype=torch.long)
    return x, y


def add_noise(x: torch.Tensor, sigma: float,
              generator: torch.Generator | None = None) -> torch.Tensor:
    """Seeded Gaussian noise, clamped back to [0, 1]."""
    noise = torch.randn(x.shape, generator=generator) * sigma
    return (x + noise).clamp(0.0, 1.0)


# --------------------------------------------------------------------------- #
# The network
# --------------------------------------------------------------------------- #
class DenoisingAE(nn.Module):
    """Conv encoder -> 32-d latent -> conv decoder (sigmoid output)."""

    def __init__(self, latent: int = 32) -> None:
        super().__init__()
        if latent < 1:
            raise AError("latent must be >= 1")
        self.latent = latent
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 8, kernel_size=3, stride=2, padding=1),  # 14x14
            nn.ReLU(),
            nn.Conv2d(8, 16, kernel_size=3, stride=2, padding=1),  # 7x7
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(16 * 7 * 7, latent),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent, 16 * 7 * 7),
            nn.ReLU(),
            nn.Unflatten(1, (16, 7, 7)),
            nn.ConvTranspose2d(16, 8, kernel_size=4, stride=2, padding=1),
            nn.ReLU(),
            nn.ConvTranspose2d(8, 1, kernel_size=4, stride=2, padding=1),
            nn.Sigmoid(),                                          # 28x28
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        return self.decoder(z)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


def build_autoencoder(latent: int = 32, seed: int = 42) -> DenoisingAE:
    """Seeded construction so initial weights are reproducible."""
    torch.manual_seed(seed)
    return DenoisingAE(latent=latent)


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
@dataclass
class AEResult:
    """Trained autoencoder plus hold-out denoising metrics."""

    model: DenoisingAE
    history: list[dict[str, float]]
    test_mse: float
    noisy_mse: float
    test_psnr: float
    noisy_psnr: float
    per_shape_mse: dict[str, float] = field(default_factory=dict)
    sigma: float = NOISE_SIGMA
    rows: int = 0
    train_rows: int = 0
    test_rows: int = 0
    test_clean: np.ndarray = field(default_factory=lambda: np.zeros(0))
    test_noisy: np.ndarray = field(default_factory=lambda: np.zeros(0))
    test_recon: np.ndarray = field(default_factory=lambda: np.zeros(0))
    test_labels: np.ndarray = field(default_factory=lambda: np.zeros(0))

    @property
    def final_loss(self) -> float:
        return self.history[-1]["loss"] if self.history else float("nan")

    def encode(self, image: np.ndarray) -> np.ndarray:
        """784-pixel image -> latent vector."""
        values = self._check_image(image)
        with torch.no_grad():
            z = self.model.encode(torch.tensor(values).view(1, 1,
                                                            IMAGE_SIZE,
                                                            IMAGE_SIZE))
        return z.numpy().ravel()

    def denoise(self, image: np.ndarray) -> np.ndarray:
        """784-pixel (noisy or clean) image -> reconstructed 784 pixels."""
        values = self._check_image(image)
        with torch.no_grad():
            recon = self.model(
                torch.tensor(values).view(1, 1, IMAGE_SIZE, IMAGE_SIZE))
        return recon.numpy().ravel()

    @staticmethod
    def _check_image(image: np.ndarray) -> np.ndarray:
        values = np.asarray(image, dtype=np.float32).ravel()
        if values.size != IMAGE_SIZE * IMAGE_SIZE:
            raise AError(f"expected {IMAGE_SIZE * IMAGE_SIZE} pixels, "
                         f"got {values.size}")
        if not np.isfinite(values).all():
            raise AError("pixel values must be finite")
        if values.min() < 0 or values.max() > 1:
            raise AError("pixel values must be in 0..1")
        return values

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "train_rows": self.train_rows,
            "test_rows": self.test_rows,
            "latent": self.model.latent,
            "epochs": len(self.history),
            "noise_sigma": self.sigma,
            "final_loss": round(self.final_loss, 6),
            "test_mse": round(self.test_mse, 6),
            "noisy_mse": round(self.noisy_mse, 6),
            "test_psnr_db": round(self.test_psnr, 3),
            "noisy_psnr_db": round(self.noisy_psnr, 3),
            "per_shape_mse": {k: round(v, 6)
                              for k, v in self.per_shape_mse.items()},
        }


def psnr(mse: float, peak: float = 1.0) -> float:
    """Peak signal-to-noise ratio in dB (infinite for perfect recon)."""
    if mse <= 0:
        return float("inf")
    return float(10.0 * np.log10(peak * peak / mse))


def _stratified_split(frame: pd.DataFrame, test_fraction: float,
                      seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    trains, tests = [], []
    for label in range(len(SHAPES)):
        group = frame[frame["label"] == label].reset_index(drop=True)
        perm = rng.permutation(len(group))
        cut = int(round(len(group) * test_fraction))
        trains.append(group.iloc[perm[cut:]])
        tests.append(group.iloc[perm[:cut]])
    train = pd.concat(trains).sample(frac=1, random_state=seed).reset_index(
        drop=True)
    test = pd.concat(tests).sample(frac=1, random_state=seed).reset_index(
        drop=True)
    return train, test


def train_model(frame: pd.DataFrame, epochs: int = 12, lr: float = 1e-3,
                batch_size: int = 64, latent: int = 32,
                sigma: float = NOISE_SIGMA, seed: int = 42,
                test_fraction: float = 0.25) -> AEResult:
    """Stratified split + noise corruption + AE training + evaluation."""
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise AError(f"missing column(s): {', '.join(missing[:4])}")
    if len(frame) < MIN_ROWS:
        raise AError(f"need at least {MIN_ROWS} images, got {len(frame)}")
    # validate pixels even when a frame bypasses load_images()
    pixels = frame[list(PIXELS)].apply(pd.to_numeric, errors="coerce")
    if pixels.isna().any().any() or not np.isfinite(pixels.to_numpy(
            dtype=float)).all():
        raise AError("pixel columns contain non-finite values")
    if not 0.05 <= test_fraction <= 0.5:
        raise AError("test_fraction must be in 0.05..0.5")
    if epochs < 1:
        raise AError(f"epochs must be >= 1, got {epochs}")
    if not np.isfinite(lr) or lr <= 0:
        raise AError(f"lr must be > 0, got {lr}")
    if batch_size < 1:
        raise AError(f"batch_size must be >= 1, got {batch_size}")
    if not np.isfinite(sigma) or sigma <= 0 or sigma > 1:
        raise AError(f"sigma must be in (0, 1], got {sigma}")

    train, test = _stratified_split(frame, test_fraction, seed)
    x_train, y_train = to_tensor(train)
    x_test, y_test = to_tensor(test)

    # fixed, seeded noise banks -> fully deterministic corruptions
    noise_gen = torch.Generator().manual_seed(seed + 1)
    noisy_train = add_noise(x_train, sigma, noise_gen)
    noisy_test = add_noise(x_test, sigma,
                           torch.Generator().manual_seed(seed + 2))

    model = build_autoencoder(latent=latent, seed=seed)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    shuffle_gen = torch.Generator().manual_seed(seed)

    history: list[dict[str, float]] = []
    model.train()
    for _ in range(epochs):
        order = torch.randperm(len(x_train), generator=shuffle_gen)
        total = 0.0
        for start in range(0, len(order), batch_size):
            idx = order[start:start + batch_size]
            optimizer.zero_grad()
            recon = model(noisy_train[idx])
            loss = criterion(recon, x_train[idx])
            loss.backward()
            optimizer.step()
            total += float(loss.detach()) * len(idx)

        model.eval()
        with torch.no_grad():
            val_recon = model(noisy_test)
            val_loss = float(criterion(val_recon, x_test))
        model.train()
        history.append({"loss": total / len(x_train), "val_loss": val_loss})

    # ---------------------------------------------------------- evaluation
    model.eval()
    with torch.no_grad():
        recon = model(noisy_test).numpy()
    clean = x_test.numpy()
    noisy = noisy_test.numpy()

    test_mse = float(np.mean((recon - clean) ** 2))
    noisy_mse = float(np.mean((noisy - clean) ** 2))

    labels = y_test.numpy()
    per_shape: dict[str, float] = {}
    for index, name in enumerate(SHAPES):
        mask = labels == index
        if mask.any():
            per_shape[name] = float(np.mean((recon[mask]
                                             - clean[mask]) ** 2))

    result = AEResult(
        model=model, history=history, test_mse=test_mse,
        noisy_mse=noisy_mse, test_psnr=psnr(test_mse),
        noisy_psnr=psnr(noisy_mse), per_shape_mse=per_shape, sigma=sigma,
        rows=len(frame), train_rows=len(train), test_rows=len(test),
        test_clean=clean.reshape(len(clean), -1),
        test_noisy=noisy.reshape(len(noisy), -1),
        test_recon=recon.reshape(len(recon), -1), test_labels=labels)
    LOG.info("hold-out MSE %.5f (noisy baseline %.5f), PSNR %.1f dB",
             test_mse, noisy_mse, result.test_psnr)
    return result


# --------------------------------------------------------------------------- #
# ASCII rendering
# --------------------------------------------------------------------------- #
def ascii_image(pixels: np.ndarray, size: int = 14) -> str:
    """Render a 28x28 image as a downsampled `size` x `size` ASCII grid."""
    values = np.asarray(pixels, dtype=float).ravel()
    if values.size != IMAGE_SIZE * IMAGE_SIZE:
        raise AError(f"expected {IMAGE_SIZE * IMAGE_SIZE} pixels, "
                     f"got {values.size}")
    image = values.reshape(IMAGE_SIZE, IMAGE_SIZE)
    step = IMAGE_SIZE // size
    small = image.reshape(size, step, size, step).mean(axis=(1, 3))
    ramp = np.clip(np.round(small * (len(SHADES) - 1)), 0,
                   len(SHADES) - 1).astype(int)
    return "\n".join("".join(SHADES[v] for v in row) for row in ramp)


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(result: AEResult) -> str:
    """Human-readable denoising report used by the CLI and demo."""
    lift = (1 - result.test_mse / result.noisy_mse) * 100 \
        if result.noisy_mse else 0.0
    lines = [
        "IMAGE DENOISING AUTOENCODER (convolutional, PyTorch)",
        "=" * 70,
        f"Dataset     : {result.rows} images "
        f"({result.train_rows} train / {result.test_rows} hold-out), "
        f"{IMAGE_SIZE}x{IMAGE_SIZE}, {len(SHAPES)} shapes",
        f"Network     : Conv(1->8->16) -> latent {result.model.latent} "
        f"-> ConvTranspose back (sigmoid)",
        f"Training    : {len(result.history)} epochs, Adam, "
        f"MSE(reconstruction, clean), noise sigma {result.sigma}",
        "",
        "Learning curve (MSE on clean targets):",
        f"  {'epoch':>7}{'train loss':>13}{'val loss':>12}",
    ]
    marks = {0, 1, len(result.history) // 2, len(result.history) - 1}
    for i, entry in enumerate(result.history):
        if i in marks:
            lines.append(f"  {i + 1:>7}{entry['loss']:>13.5f}"
                         f"{entry['val_loss']:>12.5f}")

    lines += [
        "",
        "Hold-out denoising:",
        f"  noisy input      MSE {result.noisy_mse:.5f}   "
        f"PSNR {result.noisy_psnr:.2f} dB",
        f"  AE reconstruction MSE {result.test_mse:.5f}   "
        f"PSNR {result.test_psnr:.2f} dB",
        f"  MSE reduction vs noisy input: {lift:+.1f}%   "
        f"PSNR gain {result.test_psnr - result.noisy_psnr:+.2f} dB",
        "",
        "Per-shape reconstruction MSE:",
    ]
    for name, value in result.per_shape_mse.items():
        bar = "#" * max(1, int(round(-np.log10(max(value, 1e-9)) * 4)))
        lines.append(f"  {name:<8} {value:.5f}  {bar}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "shapes.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Denoise the bundled shape images - fully offline."""
    print("=" * 70)
    print(" IMAGE DENOISING AUTOENCODER - offline demo")
    print(" Bundled 28x28 shapes; PyTorch conv AE on CPU; no network.")
    print("=" * 70)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise AError(f"bundled sample not found: {source}")

    frame = load_images(source)
    print(f"\nLoaded {len(frame)} images from {source.name} "
          f"(circles, squares, crosses)")

    result = train_model(frame, epochs=40, lr=5e-3, batch_size=64)
    print()
    print(render_report(result))

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(result.history) == 40, "history must have one entry/epoch"
    first, last = result.history[0], result.history[-1]
    assert last["loss"] < first["loss"] * 0.5, "training loss did not fall"
    assert result.test_mse < result.noisy_mse * 0.5, \
        "autoencoder barely denoises"
    assert result.test_psnr > result.noisy_psnr + 3, \
        "PSNR gain under 3 dB"
    assert abs(result.test_mse - np.mean(
        (result.test_recon - result.test_clean) ** 2)) < 1e-9, \
        "reported MSE disagrees with stored reconstructions"
    assert len(result.per_shape_mse) == len(SHAPES)
    assert all(0 < v < result.noisy_mse
               for v in result.per_shape_mse.values()), \
        "a shape class is not being denoised"

    # encode/denoise APIs work on raw pixels and stay in range
    sample = result.test_clean[0]
    latent = result.encode(sample)
    assert latent.shape == (result.model.latent,)
    reconstructed = result.denoise(sample)
    assert reconstructed.shape == (IMAGE_SIZE * IMAGE_SIZE,)
    assert reconstructed.min() >= 0.0 and reconstructed.max() <= 1.0

    # ASCII previews are well-formed
    art = ascii_image(result.test_noisy[0])
    assert len(art.splitlines()) == 14
    assert all(len(line) == 14 for line in art.splitlines())

    # deterministic re-run
    again = train_model(frame, epochs=40, lr=5e-3, batch_size=64)
    assert again.test_mse == result.test_mse, "not deterministic"
    assert [h["loss"] for h in again.history] == \
        [h["loss"] for h in result.history], "history changed between runs"

    label_index = int(result.test_labels[0])
    name = SHAPES[label_index]
    panels = list(zip(ascii_image(result.test_noisy[0]).splitlines(),
                      ascii_image(result.test_recon[0]).splitlines(),
                      ascii_image(result.test_clean[0]).splitlines()))
    print(f"\nSample hold-out image (true shape: {name}):")
    print("  noisy input        AE output           clean target")
    for noisy_line, recon_line, clean_line in panels:
        print(f"  |{noisy_line}|  |{recon_line}|  |{clean_line}|")

    print(f"\nCross-checks OK: MSE {result.test_mse:.5f} vs noisy "
          f"{result.noisy_mse:.5f} "
          f"({(1 - result.test_mse / result.noisy_mse) * 100:+.1f}%), "
          f"PSNR {result.noisy_psnr:.1f} -> {result.test_psnr:.1f} dB, "
          f"deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
