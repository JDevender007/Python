"""Tests for the Neural Network From Scratch project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mlp import (  # noqa: E402
    DEMO_CSV,
    MIN_ROWS,
    MLP,
    MLPError,
    REQUIRED_COLUMNS,
    gradient_check,
    load_data,
    relu,
    render_report,
    run_demo,
    sigmoid,
    tanh,
    train_model,
)
from main import main, parse_layers  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _csv(tmp_path: Path, rows: list[list], name: str = "dataset.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS)).to_csv(
        path, index=False)
    return path


def _grid(n: int = 60) -> list[list]:
    """n valid rows, both labels, features varying."""
    rows = []
    for i in range(n):
        rows.append([round(-2.0 + 4.0 * i / n, 4),
                     round(float(i % 7) - 3.0, 4),
                     i % 2])
    return rows


def _tiny_frame(n: int = 60) -> pd.DataFrame:
    return pd.DataFrame(_grid(n), columns=list(REQUIRED_COLUMNS))


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_data(DEMO_CSV)


@pytest.fixture(scope="module")
def trained(sample):
    # short training keeps the suite fast; the demo covers full convergence
    return train_model(sample, hidden=(8,), lr=0.2, epochs=80)


# --------------------------------------------------------------------------- #
# Activations
# --------------------------------------------------------------------------- #
def test_sigmoid_bounds_and_midpoint():
    z = np.array([-50.0, -1.0, 0.0, 1.0, 50.0])
    s = sigmoid(z)
    assert ((s >= 0) & (s <= 1)).all()
    assert s[2] == pytest.approx(0.5)
    assert s[3] > 0.5 > s[1]
    assert not np.isnan(s).any()  # overflow-free at the extremes


def test_relu_and_tanh():
    z = np.array([-2.0, -0.5, 0.0, 0.5, 2.0])
    assert (relu(z) == [0, 0, 0, 0.5, 2.0]).all()
    assert tanh(0.0) == 0.0
    assert abs(tanh(10.0)) < 1.0


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 600
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    counts = sample["label"].value_counts()
    assert counts[0] == 300 and counts[1] == 300


def test_load_missing_file(tmp_path):
    with pytest.raises(MLPError, match="not found"):
        load_data(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("x1,label\n0.5,1\n", encoding="utf-8")
    with pytest.raises(MLPError, match="missing column"):
        load_data(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(MLPError, match="no rows"):
        load_data(path)


def test_load_non_numeric_feature(tmp_path):
    rows = _grid()
    rows[0][1] = "curved"
    with pytest.raises(MLPError, match="'x2' contains non-numeric"):
        load_data(_csv(tmp_path, rows))


def test_load_infinite_feature(tmp_path):
    rows = _grid()
    rows[0][0] = float("inf")
    with pytest.raises(MLPError, match="finite"):
        load_data(_csv(tmp_path, rows))


def test_load_non_binary_label(tmp_path):
    rows = _grid()
    rows[0][2] = 2
    with pytest.raises(MLPError, match="binary 0/1"):
        load_data(_csv(tmp_path, rows))


def test_load_too_few_rows(tmp_path):
    with pytest.raises(MLPError, match=f"at least {MIN_ROWS}"):
        load_data(_csv(tmp_path, _grid(20)))


def test_load_missing_class(tmp_path):
    rows = _grid()
    for row in rows:
        row[2] = 1
    # the binary 0/1 check fires before the per-class count check
    with pytest.raises(MLPError, match="binary 0/1"):
        load_data(_csv(tmp_path, rows))


# --------------------------------------------------------------------------- #
# Configuration validation
# --------------------------------------------------------------------------- #
def test_config_rejects_bad_sizes():
    with pytest.raises(MLPError, match="at least 2 entries"):
        MLP([2])
    with pytest.raises(MLPError, match="positive integers"):
        MLP([2, -4, 1])
    with pytest.raises(MLPError, match="output layer"):
        MLP([2, 8, 2])


def test_config_rejects_bad_hyperparameters():
    with pytest.raises(MLPError, match="hidden_activation"):
        MLP([2, 4, 1], hidden_activation="swish")
    with pytest.raises(MLPError, match="lr must be"):
        MLP([2, 4, 1], lr=0.0)
    with pytest.raises(MLPError, match="epochs"):
        MLP([2, 4, 1], epochs=0)
    with pytest.raises(MLPError, match="batch_size"):
        MLP([2, 4, 1], batch_size=0)


def test_parse_layers():
    assert parse_layers("16,16") == (16, 16)
    assert parse_layers("32, 8, 4") == (32, 8, 4)
    with pytest.raises(MLPError, match="comma-separated"):
        parse_layers("abc")
    with pytest.raises(MLPError, match="positive"):
        parse_layers("16,0")


# --------------------------------------------------------------------------- #
# Forward pass and gradient checking
# --------------------------------------------------------------------------- #
def test_forward_output_shape_and_bounds():
    model = MLP([2, 6, 1], epochs=1, seed=1)
    rng = np.random.default_rng(0)
    x = rng.normal(size=(7, 2))
    # an unfitted model must refuse to predict, not return raw input
    with pytest.raises(MLPError, match="fit"):
        model.predict_proba(x)
    model.fit(x[:4], np.array([0.0, 1.0, 0.0, 1.0]))
    probs = model.predict_proba(x)
    assert probs.shape == (7,)
    assert ((probs >= 0) & (probs <= 1)).all()


def test_gradients_match_numerical_differentiation():
    # the whole point of "from scratch": prove the hand-derived backprop
    error = gradient_check(hidden=(4,), samples=3, seed=5)
    assert error < 1e-6


def test_gradients_match_numerical_wider_network():
    error = gradient_check(hidden=(6, 5), samples=4, seed=9)
    assert error < 1e-6


def test_gradients_reject_mismatched_batch():
    model = MLP([2, 4, 1], epochs=1, seed=1)
    with pytest.raises(MLPError, match="same number of rows"):
        model.gradients(np.zeros((5, 2)), np.zeros(4))


# --------------------------------------------------------------------------- #
# Training behaviour
# --------------------------------------------------------------------------- #
def test_fit_rejects_wrong_feature_count(trained):
    with pytest.raises(MLPError, match="expected 2 features"):
        trained.model.fit(np.zeros((10, 3)), np.zeros(10))


def test_fit_rejects_non_binary_targets(trained):
    with pytest.raises(MLPError, match="binary 0/1"):
        trained.model.fit(np.zeros((10, 2)), np.full(10, 2.0))


def test_fit_rejects_non_finite_input(trained):
    bad = np.zeros((10, 2))
    bad[0, 0] = np.nan
    with pytest.raises(MLPError, match="non-finite"):
        trained.model.fit(bad, np.zeros(10))


def test_training_reduces_loss(sample):
    result = train_model(sample, hidden=(8,), lr=0.2, epochs=80)
    first, last = result.history[0], result.history[-1]
    assert last["loss"] < first["loss"] * 0.5
    assert last["loss"] < 0.5


def test_training_beats_baseline(sample):
    result = train_model(sample, hidden=(8,), lr=0.2, epochs=80)
    assert result.test_accuracy > result.baseline_accuracy + 0.3
    assert result.baseline_accuracy == pytest.approx(0.5)


def test_training_is_deterministic(sample):
    first = train_model(sample, hidden=(8,), lr=0.2, epochs=40, seed=7)
    second = train_model(sample, hidden=(8,), lr=0.2, epochs=40, seed=7)
    assert first.test_accuracy == second.test_accuracy
    assert [h["loss"] for h in first.history] == \
        [h["loss"] for h in second.history]


def test_seed_changes_training(sample):
    first = train_model(sample, hidden=(8,), lr=0.2, epochs=40, seed=1)
    second = train_model(sample, hidden=(8,), lr=0.2, epochs=40, seed=2)
    assert [h["loss"] for h in first.history] != \
        [h["loss"] for h in second.history]


def test_split_sizes_add_up(sample):
    result = train_model(sample, epochs=5)
    assert result.train_rows + result.test_rows == result.rows == 600
    assert result.test_rows == 150  # 25% of each class


def test_history_has_entry_per_epoch(sample):
    result = train_model(sample, hidden=(4,), epochs=25)
    assert len(result.history) == 25
    assert {"loss", "accuracy", "val_loss", "val_accuracy"} <= \
        set(result.history[0])


def test_train_model_rejects_bad_test_fraction(sample):
    with pytest.raises(MLPError, match="test_fraction"):
        train_model(sample, test_fraction=0.9)


def test_result_to_dict(trained):
    payload = trained.to_dict()
    json.dumps(payload)
    assert payload["params"]["sizes"] == [2, 8, 1]
    assert payload["epochs"] == 80
    assert 0 <= payload["test_accuracy"] <= 1
    assert payload["final_loss"] <= payload["initial_loss"]


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections(trained):
    text = render_report(trained)
    assert "NEURAL NETWORK FROM SCRATCH" in text
    assert "Architecture : 2 -> 8 -> 1" in text
    assert "Learning curve" in text
    assert "Hold-out results:" in text
    assert "Majority baseline" in text
    assert "Lift over baseline" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "gradient check" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(MLPError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_file_training(capsys):
    assert main(["--file", str(DEMO_CSV), "--epochs", "60",
                 "--layers", "8"]) == 0
    out = capsys.readouterr().out
    assert "Hold-out results:" in out and "Done." in out


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--epochs", "40",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["params"]["sizes"] == [2, 16, 16, 1]
    assert payload["test_accuracy"] >= 0.8


def test_cli_bad_layers(capsys):
    assert main(["--file", str(DEMO_CSV), "--layers", "abc"]) == 2
    assert "comma-separated" in capsys.readouterr().err


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
