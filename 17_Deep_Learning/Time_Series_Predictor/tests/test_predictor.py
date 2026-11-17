"""Tests for the Time Series Predictor project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from predictor import (  # noqa: E402
    DEMO_CSV,
    MIN_ROWS,
    MIN_WINDOW,
    REQUIRED_COLUMNS,
    ForecastResult,
    LSTMForecaster,
    SeriesError,
    load_series,
    make_windows,
    render_report,
    run_demo,
    train_model,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _series(n: int = 480, noise: float = 0.1, seed: int = 5) -> pd.DataFrame:
    """Deterministic sine + trend series for tests (>= MIN_ROWS)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    value = (2.0 * np.sin(2 * np.pi * t / 40.0)
             + 0.004 * t + rng.normal(0, noise, n))
    return pd.DataFrame({"t": t, "value": np.round(value, 4)})


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_series(DEMO_CSV)


@pytest.fixture(scope="module")
def trained(sample):
    # 2 epochs keeps the suite fast; the demo covers real convergence
    return train_model(sample, window=20, epochs=2, hidden=16)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 1200
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert sample["t"].is_monotonic_increasing
    assert not sample["t"].duplicated().any()
    assert float(sample["value"].std()) > 0


def test_load_missing_file(tmp_path):
    with pytest.raises(SeriesError, match="not found"):
        load_series(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("t,val\n0,1.0\n", encoding="utf-8")
    with pytest.raises(SeriesError, match="missing column"):
        load_series(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(SeriesError, match="no rows"):
        load_series(path)


def test_load_non_numeric_value(tmp_path):
    frame = _series()
    frame["value"] = frame["value"].astype(object)
    frame.loc[0, "value"] = "spiky"
    path = tmp_path / "s.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(SeriesError, match="'value' contains non-numeric"):
        load_series(path)


def test_load_infinite_value(tmp_path):
    frame = _series()
    frame.loc[3, "value"] = float("inf")
    path = tmp_path / "s.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(SeriesError, match="finite"):
        load_series(path)


def test_load_duplicate_t(tmp_path):
    frame = _series()
    frame.loc[10, "t"] = frame.loc[9, "t"]
    path = tmp_path / "s.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(SeriesError, match="duplicate t"):
        load_series(path)


def test_load_too_few_points(tmp_path):
    path = tmp_path / "short.csv"
    _series(50).to_csv(path, index=False)
    with pytest.raises(SeriesError, match=f"at least {MIN_ROWS}"):
        load_series(path)


def test_load_constant_series(tmp_path):
    frame = _series()
    frame["value"] = 3.14
    path = tmp_path / "flat.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(SeriesError, match="no variation"):
        load_series(path)


def test_load_sorts_by_t(tmp_path):
    frame = _series()
    frame = frame.iloc[::-1].reset_index(drop=True)
    path = tmp_path / "shuffled.csv"
    frame.to_csv(path, index=False)
    loaded = load_series(path)
    assert loaded["t"].is_monotonic_increasing


# --------------------------------------------------------------------------- #
# Windows
# --------------------------------------------------------------------------- #
def test_make_windows_shapes():
    values = np.arange(50, dtype=float)
    x, y = make_windows(values, window=10, start=0, stop=50)
    assert x.shape == (40, 10)
    assert y.shape == (40,)
    assert (x[0] == np.arange(10)).all()
    assert y[0] == 10


def test_make_windows_targets_within_segment():
    values = np.arange(100, dtype=float)
    _, y = make_windows(values, window=5, start=40, stop=60)
    assert y.min() >= 40 and y.max() < 60


def test_make_windows_rejects_empty_segment():
    with pytest.raises(SeriesError, match="no windows"):
        make_windows(np.arange(10.0), window=5, start=0, stop=3)


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def test_forecaster_seeded_identical():
    torch.manual_seed(1)
    first = LSTMForecaster(hidden=8)
    torch.manual_seed(1)
    second = LSTMForecaster(hidden=8)
    for a, b in zip(first.parameters(), second.parameters()):
        assert torch.equal(a, b)


def test_forecaster_output_shape():
    model = LSTMForecaster(hidden=8)
    out = model(torch.zeros(4, 20, 1))
    assert out.shape == (4,)


def test_forecaster_rejects_bad_config():
    with pytest.raises(SeriesError, match=">= 1"):
        LSTMForecaster(hidden=0)


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
def test_train_valid_metrics(trained):
    assert trained.test_rmse > 0 and trained.test_mae > 0
    assert trained.baseline_rmse > 0
    assert trained.test_mae <= trained.test_rmse * 1.5
    assert -1.0 <= trained.correlation <= 1.0
    assert trained.rows == 1200
    assert trained.train_rows == 960 and trained.test_rows == 240
    assert trained.train_rows + trained.test_rows == trained.rows


def test_train_history_has_entry_per_epoch(trained):
    assert len(trained.history) == 2
    assert {"loss", "val_loss"} <= set(trained.history[0])
    assert np.isfinite(trained.history[0]["loss"])


def test_train_is_deterministic(sample):
    first = train_model(sample, window=20, epochs=2, hidden=16, seed=7)
    second = train_model(sample, window=20, epochs=2, hidden=16, seed=7)
    assert first.test_rmse == second.test_rmse
    assert [h["loss"] for h in first.history] == \
        [h["loss"] for h in second.history]


def test_seed_changes_training(sample):
    first = train_model(sample, window=20, epochs=2, hidden=16, seed=1)
    second = train_model(sample, window=20, epochs=2, hidden=16, seed=2)
    assert [h["loss"] for h in first.history] != \
        [h["loss"] for h in second.history]


def test_persistence_baseline_is_computable(trained):
    # baseline predictions are the last in-window values, so RMSE is finite
    assert np.isfinite(trained.baseline_rmse)
    assert np.isfinite(trained.baseline_mae)


def test_test_predictions_length(trained):
    # every test point gets a target (context may straddle the split)
    assert len(trained.test_targets) == trained.test_rows
    assert len(trained.test_predictions) == len(trained.test_targets)


def test_result_to_dict(trained):
    payload = trained.to_dict()
    json.dumps(payload)
    assert payload["window"] == 20
    assert payload["epochs"] == 2
    assert payload["test_rmse"] > 0
    assert -1 <= payload["correlation"] <= 1


# --------------------------------------------------------------------------- #
# Configuration validation
# --------------------------------------------------------------------------- #
def test_train_rejects_bad_window(sample):
    with pytest.raises(SeriesError, match="window must be"):
        train_model(sample, window=3)
    with pytest.raises(SeriesError, match="window must be"):
        train_model(sample, window=2.5)  # type: ignore[arg-type]


def test_train_rejects_window_larger_than_split(sample):
    with pytest.raises(SeriesError, match="training windows"):
        train_model(sample, window=1000)


def test_train_rejects_bad_hyperparams(sample):
    with pytest.raises(SeriesError, match="epochs"):
        train_model(sample, epochs=0)
    with pytest.raises(SeriesError, match="lr must be"):
        train_model(sample, lr=0.0)
    with pytest.raises(SeriesError, match="batch_size"):
        train_model(sample, batch_size=0)
    with pytest.raises(SeriesError, match="test_fraction"):
        train_model(sample, test_fraction=0.9)


def test_train_rejects_missing_value_column():
    with pytest.raises(SeriesError, match="'value' column"):
        train_model(pd.DataFrame({"t": range(80),
                                  "v": np.zeros(80)}))


def test_train_rejects_short_series():
    frame = _series(50)
    with pytest.raises(SeriesError, match="at least 60"):
        train_model(frame)


def test_train_rejects_non_finite_values():
    frame = _series(80)
    frame.loc[5, "value"] = np.nan
    with pytest.raises(SeriesError, match="non-finite"):
        train_model(frame)


# --------------------------------------------------------------------------- #
# Forecasting
# --------------------------------------------------------------------------- #
def test_forecast_returns_float(trained, sample):
    tail = sample["value"].to_numpy(dtype=float)[-trained.window:]
    value = trained.forecast(tail)
    assert isinstance(value, float)
    assert np.isfinite(value)
    assert abs(value) <= abs(sample["value"]).max() + 1.0


def test_forecast_rejects_wrong_length(trained):
    with pytest.raises(SeriesError, match="recent values"):
        trained.forecast(np.zeros(5))


def test_forecast_rejects_nan(trained):
    bad = np.zeros(trained.window)
    bad[2] = np.nan
    with pytest.raises(SeriesError, match="finite"):
        trained.forecast(bad)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections(trained):
    text = render_report(trained)
    assert "TIME SERIES PREDICTOR" in text
    assert "Learning curve" in text
    assert "Hold-out next-step forecast:" in text
    assert "Persistence" in text
    assert "correlation" in text
    assert "actual" in text and "predicted" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Next-step forecast after t=" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(SeriesError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_file_training_and_forecast(capsys):
    assert main(["--file", str(DEMO_CSV), "--epochs", "3",
                 "--window", "20", "--forecast"]) == 0
    out = capsys.readouterr().out
    assert "Next-step forecast after t=" in out
    assert "Done." in out


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--epochs", "2",
                 "--window", "20", "--json", str(payload_path),
                 "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["window"] == 20
    assert payload["test_rmse"] > 0


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


# --------------------------------------------------------------------------- #
# Windowing and result contract
# --------------------------------------------------------------------------- #
def test_make_windows_target_is_the_value_after_the_window():
    values = np.arange(10, dtype=np.float32)
    xs, ys = make_windows(values, window=3, start=3, stop=6)
    assert len(xs) == len(ys) == 3
    assert list(ys) == [3.0, 4.0, 5.0]
    assert list(xs[0]) == [0.0, 1.0, 2.0]


def test_make_windows_rejects_window_larger_than_series():
    with pytest.raises(SeriesError):
        make_windows(np.arange(3, dtype=np.float32), window=5, start=0, stop=3)


def test_result_to_dict_reports_split(trained):
    payload = trained.to_dict()
    assert payload["train_rows"] + payload["test_rows"] == payload["rows"]


def test_result_to_dict_has_error_metrics(trained):
    payload = trained.to_dict()
    for key in ("test_rmse", "test_mae", "baseline_rmse", "baseline_mae"):
        assert key in payload


def test_metrics_are_non_negative(trained):
    assert trained.test_rmse >= 0.0
    assert trained.test_mae >= 0.0
    assert trained.baseline_rmse >= 0.0


def test_history_losses_are_finite(trained):
    assert all(np.isfinite(entry["loss"]) for entry in trained.history)


def test_forecast_is_close_to_the_last_value(trained, sample):
    values = sample["value"].to_numpy(dtype=np.float32)[-trained.window:]
    prediction = trained.forecast(values)
    assert np.isfinite(prediction)
    assert abs(prediction - float(values[-1])) < 5.0


def test_render_report_is_ascii(trained):
    render_report(trained).encode("ascii")
