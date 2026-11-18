"""Time series predictor: a PyTorch LSTM next-step forecaster - offline.

Loads a univariate series (t, value), standardises it with train-only
statistics, cuts chronological train/hold-out segments, builds sliding
windows, and trains an LSTM to predict the next value. Reports hold-out
RMSE/MAE against a persistence baseline plus forecast correlation.
Local files only - no network, no dataset downloads, no artifacts.
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

LOG = logging.getLogger("series")

REQUIRED_COLUMNS = ("t", "value")
MIN_ROWS = 400
MIN_WINDOW = 5
MIN_SEG_WINDOWS = 10      # each segment needs at least this many targets


class SeriesError(RuntimeError):
    """Raised for missing files, bad schemas, and training failures."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_series(path: str | Path) -> pd.DataFrame:
    """Load the series CSV, validate it, and return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise SeriesError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise SeriesError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SeriesError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise SeriesError(f"no rows in {source.name}")

    frame = frame.copy()
    for column in REQUIRED_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise SeriesError(f"column {column!r} contains non-numeric values")
        if not np.isfinite(frame[column]).all():
            raise SeriesError(f"column {column!r} must be finite")

    if frame["t"].duplicated().any():
        raise SeriesError("duplicate t value(s)")
    if len(frame) < MIN_ROWS:
        raise SeriesError(f"need at least {MIN_ROWS} points, "
                          f"got {len(frame)}")
    if float(frame["value"].std()) == 0.0:
        raise SeriesError("series has no variation (constant values)")

    frame = frame.sort_values("t").reset_index(drop=True)
    LOG.info("loaded %d points from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Windows and the network
# --------------------------------------------------------------------------- #
def make_windows(values: np.ndarray, window: int,
                 start: int, stop: int) -> tuple[np.ndarray, np.ndarray]:
    """Sliding windows whose targets lie in [start, stop)."""
    xs, ys = [], []
    for target in range(max(start, window), stop):
        xs.append(values[target - window:target])
        ys.append(values[target])
    if not xs:
        raise SeriesError("no windows could be built for this segment")
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32)


class LSTMForecaster(nn.Module):
    """LSTM over a window of scalars -> single next-step prediction."""

    def __init__(self, hidden: int = 32, num_layers: int = 1) -> None:
        super().__init__()
        if hidden < 1 or num_layers < 1:
            raise SeriesError("hidden and num_layers must be >= 1")
        self.lstm = nn.LSTM(1, hidden, num_layers=num_layers,
                            batch_first=True)
        self.head = nn.Linear(hidden, 1)
        self.hidden = hidden
        self.num_layers = num_layers

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, window, 1) -> take the last time step's output
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
@dataclass
class ForecastResult:
    """Trained forecaster, learning history, and hold-out metrics."""

    model: LSTMForecaster
    history: list[dict[str, float]]
    test_rmse: float
    test_mae: float
    baseline_rmse: float
    baseline_mae: float
    correlation: float
    window: int
    mu: float
    sigma: float
    rows: int = 0
    train_rows: int = 0
    test_rows: int = 0
    test_targets: np.ndarray = field(default_factory=lambda: np.zeros(0))
    test_predictions: np.ndarray = field(default_factory=lambda: np.zeros(0))

    @property
    def final_loss(self) -> float:
        return self.history[-1]["loss"] if self.history else float("nan")

    def forecast(self, recent: np.ndarray) -> float:
        """Predict the next value from the last `window` observations."""
        window = np.asarray(recent, dtype=np.float32).ravel()
        if window.size != self.window:
            raise SeriesError(f"expected {self.window} recent values, "
                              f"got {window.size}")
        if not np.isfinite(window).all():
            raise SeriesError("recent values must be finite")
        scaled = (window - self.mu) / self.sigma
        with torch.no_grad():
            pred = self.model(torch.tensor(scaled).view(1, -1, 1))
        return float(pred.item() * self.sigma + self.mu)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "train_rows": self.train_rows,
            "test_rows": self.test_rows,
            "window": self.window,
            "epochs": len(self.history),
            "final_loss": round(self.final_loss, 6),
            "test_rmse": round(self.test_rmse, 4),
            "test_mae": round(self.test_mae, 4),
            "baseline_rmse": round(self.baseline_rmse, 4),
            "baseline_mae": round(self.baseline_mae, 4),
            "correlation": round(self.correlation, 4),
        }


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> tuple[float, float]:
    errors = np.asarray(actual) - np.asarray(predicted)
    return (float(np.sqrt(np.mean(errors ** 2))),
            float(np.mean(np.abs(errors))))


def train_model(frame: pd.DataFrame, window: int = 40, epochs: int = 25,
                lr: float = 5e-3, hidden: int = 32, batch_size: int = 32,
                seed: int = 42, test_fraction: float = 0.2) -> ForecastResult:
    """Chronological split + LSTM training + persistence baseline."""
    if "value" not in frame.columns:
        raise SeriesError("frame must contain a 'value' column")
    values = pd.to_numeric(frame["value"], errors="coerce").to_numpy(
        dtype=float)
    if np.isnan(values).any() or not np.isfinite(values).all():
        raise SeriesError("'value' contains non-finite values")
    if len(values) < 60:
        raise SeriesError(f"need at least 60 points, got {len(values)}")
    if not isinstance(window, (int, np.integer)) or window < MIN_WINDOW:
        raise SeriesError(f"window must be an integer >= {MIN_WINDOW}")
    if epochs < 1:
        raise SeriesError(f"epochs must be >= 1, got {epochs}")
    if not np.isfinite(lr) or lr <= 0:
        raise SeriesError(f"lr must be > 0, got {lr}")
    if batch_size < 1:
        raise SeriesError(f"batch_size must be >= 1, got {batch_size}")
    if not 0.05 <= test_fraction <= 0.5:
        raise SeriesError("test_fraction must be in 0.05..0.5")

    n = len(values)
    split = int(n * (1 - test_fraction))
    train_windows = split - window
    test_windows = n - split
    if train_windows < MIN_SEG_WINDOWS:
        raise SeriesError(
            f"window {window} leaves only {max(train_windows, 0)} training "
            f"windows (need >= {MIN_SEG_WINDOWS})")
    if test_windows < MIN_SEG_WINDOWS:
        raise SeriesError(
            f"test segment has only {test_windows} points "
            f"(need >= {MIN_SEG_WINDOWS})")

    # standardise with TRAIN statistics only (no leakage)
    mu = float(values[:split].mean())
    sigma = float(values[:split].std())
    if sigma == 0:
        raise SeriesError("training segment has no variation")
    scaled = (values - mu) / sigma

    x_train, y_train = make_windows(scaled, window, 0, split)
    x_test, y_test = make_windows(scaled, window, split, n)

    torch.manual_seed(seed)
    model = LSTMForecaster(hidden=hidden)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    generator = torch.Generator().manual_seed(seed)

    x_train_t = torch.tensor(x_train).unsqueeze(-1)
    y_train_t = torch.tensor(y_train)
    x_test_t = torch.tensor(x_test).unsqueeze(-1)
    y_test_t = torch.tensor(y_test)

    history: list[dict[str, float]] = []
    model.train()
    for _ in range(epochs):
        order = torch.randperm(len(x_train_t), generator=generator)
        total = 0.0
        for start in range(0, len(order), batch_size):
            idx = order[start:start + batch_size]
            optimizer.zero_grad()
            pred = model(x_train_t[idx])
            loss = criterion(pred, y_train_t[idx])
            loss.backward()
            optimizer.step()
            total += float(loss.detach()) * len(idx)

        model.eval()
        with torch.no_grad():
            val_pred = model(x_test_t)
            val_loss = float(criterion(val_pred, y_test_t))
        model.train()
        history.append({"loss": total / len(x_train_t), "val_loss": val_loss})

    # ---------------------------------------------------------- evaluation
    model.eval()
    with torch.no_grad():
        pred_scaled = model(x_test_t).numpy()
    pred = pred_scaled * sigma + mu
    actual = y_test * sigma + mu

    test_rmse, test_mae = _metrics(actual, pred)
    # persistence baseline: predict the last value inside the window
    baseline_pred = np.array([x_test[i][-1] * sigma + mu
                              for i in range(len(x_test))])
    baseline_rmse, baseline_mae = _metrics(actual, baseline_pred)

    if actual.std() > 0 and pred.std() > 0:
        correlation = float(np.corrcoef(actual, pred)[0, 1])
    else:
        correlation = 0.0

    result = ForecastResult(
        model=model, history=history, test_rmse=test_rmse,
        test_mae=test_mae, baseline_rmse=baseline_rmse,
        baseline_mae=baseline_mae, correlation=correlation, window=window,
        mu=mu, sigma=sigma, rows=n, train_rows=split, test_rows=n - split,
        test_targets=actual, test_predictions=pred)
    LOG.info("hold-out RMSE %.4f (persistence %.4f), corr %.3f",
             test_rmse, baseline_rmse, correlation)
    return result


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(result: ForecastResult) -> str:
    """Human-readable forecasting report used by the CLI and demo."""
    lines = [
        "TIME SERIES PREDICTOR (LSTM next-step forecasting)",
        "=" * 66,
        f"Series      : {result.rows} points "
        f"({result.train_rows} train / {result.test_rows} hold-out), "
        f"window {result.window}",
        f"Scaler      : z-score from train segment "
        f"(mean {result.mu:.3f}, std {result.sigma:.3f})",
        f"Network     : LSTM(input=1, hidden={result.model.hidden}) "
        f"-> Linear(hidden, 1)",
        f"Training    : {len(result.history)} epochs, Adam, "
        f"MSE on scaled values",
        "",
        "Learning curve (MSE):",
        f"  {'epoch':>7}{'train loss':>13}{'val loss':>12}",
    ]
    marks = {0, 1, len(result.history) // 2, len(result.history) - 1}
    for i, entry in enumerate(result.history):
        if i in marks:
            lines.append(f"  {i + 1:>7}{entry['loss']:>13.5f}"
                         f"{entry['val_loss']:>12.5f}")

    lift = (1 - result.test_rmse / result.baseline_rmse) * 100 \
        if result.baseline_rmse else 0.0
    lines += [
        "",
        "Hold-out next-step forecast:",
        f"  LSTM            RMSE {result.test_rmse:.4f}   "
        f"MAE {result.test_mae:.4f}",
        f"  Persistence     RMSE {result.baseline_rmse:.4f}   "
        f"MAE {result.baseline_mae:.4f}",
        f"  RMSE lift vs persistence: {lift:+.1f}%   "
        f"correlation {result.correlation:.3f}",
        "",
        "Last few hold-out steps (actual vs predicted):",
    ]
    tail = min(5, len(result.test_targets))
    for i in range(len(result.test_targets) - tail,
                   len(result.test_targets)):
        lines.append(f"  t={result.train_rows + i:>5}  "
                     f"actual {result.test_targets[i]:>8.3f}  "
                     f"predicted {result.test_predictions[i]:>8.3f}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "series.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Forecast the bundled sine series - fully offline."""
    print("=" * 66)
    print(" TIME SERIES PREDICTOR - offline demo")
    print(" Bundled sine series; PyTorch LSTM on CPU; no network.")
    print("=" * 66)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise SeriesError(f"bundled sample not found: {source}")

    frame = load_series(source)
    print(f"\nLoaded {len(frame)} points from {source.name}")

    result = train_model(frame, window=40, epochs=12, lr=5e-3)
    print()
    print(render_report(result))

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(result.history) == 12, "history must have one entry/epoch"
    first, last = result.history[0], result.history[-1]
    assert last["loss"] < first["loss"] * 0.5, "training loss did not fall"
    assert result.test_rmse < result.baseline_rmse, \
        "LSTM failed to beat the persistence baseline"
    assert result.test_rmse < result.baseline_rmse * 0.8, \
        "LSTM lift over persistence is too small"
    assert result.correlation > 0.7, "forecasts are not tracking the series"
    assert len(result.test_targets) == len(result.test_predictions) > 0

    # forecasting from the raw tail returns a finite, plausible number
    tail = frame["value"].to_numpy(dtype=float)[-result.window:]
    next_value = result.forecast(tail)
    assert np.isfinite(next_value), "forecast is not finite"
    assert abs(next_value) <= abs(frame["value"]).max() + 1.0, \
        "forecast is implausibly far from the series range"

    # deterministic re-run
    again = train_model(frame, window=40, epochs=12, lr=5e-3)
    assert again.test_rmse == result.test_rmse, "not deterministic"
    assert [h["loss"] for h in again.history] == \
        [h["loss"] for h in result.history], "history changed between runs"

    print(f"\nNext-step forecast after t={result.rows - 1}: "
          f"{next_value:.3f}")
    print(f"\nCross-checks OK: RMSE {result.test_rmse:.4f} vs persistence "
          f"{result.baseline_rmse:.4f} "
          f"({(1 - result.test_rmse / result.baseline_rmse) * 100:+.1f}%), "
          f"correlation {result.correlation:.3f}, deterministic re-run")
    print("Demo completed successfully.")
    return 0
