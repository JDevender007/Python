"""Tests for the Digit Recognizer project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from digits import (  # noqa: E402
    CLASSES,
    DEMO_CSV,
    MIN_PER_CLASS,
    MIN_ROWS,
    PIXELS,
    DigitError,
    DigitNet,
    ascii_digit,
    build_model,
    load_digits_data,
    render_report,
    run_demo,
    to_tensor,
    train_model,
)
from main import main, parse_pixels  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(label: int, fill: int = 0) -> dict:
    row = {p: fill for p in PIXELS}
    row["label"] = label
    return row


def _grid(n: int = 120) -> pd.DataFrame:
    """n valid rows cycling through all 10 classes with varying pixels."""
    rows = []
    for i in range(n):
        label = i % 10
        row = _row(label, fill=0)
        # a few non-zero pixels that depend on i so no column is constant
        row["pixel_0"] = i % 17
        row["pixel_9"] = (i * 3) % 17
        row["pixel_63"] = (i * 7) % 17
        rows.append(row)
    return pd.DataFrame(rows)


def _csv(tmp_path: Path, frame: pd.DataFrame,
         name: str = "digits.csv") -> Path:
    path = tmp_path / name
    frame.to_csv(path, index=False)
    return path


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_digits_data(DEMO_CSV)


@pytest.fixture(scope="module")
def trained(sample):
    # 2 epochs keeps the suite fast; the demo covers full training
    return train_model(sample, epochs=2, hidden=(32,))


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 1797
    assert list(sample.columns) == list(PIXELS) + ["label"]
    assert set(sample["label"]) == set(CLASSES)
    counts = sample["label"].value_counts()
    assert counts.min() >= MIN_PER_CLASS
    for column in PIXELS:
        assert sample[column].between(0, 16).all()


def test_load_missing_file(tmp_path):
    with pytest.raises(DigitError, match="not found"):
        load_digits_data(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("pixel_0,label\n5,1\n", encoding="utf-8")
    with pytest.raises(DigitError, match="missing column"):
        load_digits_data(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(PIXELS + ("label",)) + "\n",
                    encoding="utf-8")
    with pytest.raises(DigitError, match="no rows"):
        load_digits_data(path)


def test_load_non_numeric_pixel(tmp_path):
    frame = _grid()
    frame["pixel_3"] = frame["pixel_3"].astype(object)
    frame.loc[0, "pixel_3"] = "bright"
    with pytest.raises(DigitError, match="'pixel_3' contains non-numeric"):
        load_digits_data(_csv(tmp_path, frame))


def test_load_pixel_out_of_range(tmp_path):
    frame = _grid()
    frame.loc[0, "pixel_5"] = 20
    with pytest.raises(DigitError, match="'pixel_5' outside"):
        load_digits_data(_csv(tmp_path, frame))


def test_load_negative_pixel(tmp_path):
    frame = _grid()
    frame.loc[0, "pixel_7"] = -1
    with pytest.raises(DigitError, match="'pixel_7' outside"):
        load_digits_data(_csv(tmp_path, frame))


def test_load_label_out_of_range(tmp_path):
    frame = _grid()
    frame.loc[0, "label"] = 12
    with pytest.raises(DigitError, match="label must be 0..9"):
        load_digits_data(_csv(tmp_path, frame))


def test_load_fractional_label(tmp_path):
    frame = _grid()
    frame["label"] = frame["label"].astype(float)
    frame.loc[0, "label"] = 3.5
    with pytest.raises(DigitError, match="whole numbers"):
        load_digits_data(_csv(tmp_path, frame))


def test_load_too_few_rows(tmp_path):
    with pytest.raises(DigitError, match=f"at least {MIN_ROWS}"):
        load_digits_data(_csv(tmp_path, _grid(50)))


def test_load_sparse_class(tmp_path):
    frame = _grid(200)
    frame = frame[frame["label"] != 7]  # drop class 7 entirely
    with pytest.raises(DigitError, match="too few samples.*7"):
        load_digits_data(_csv(tmp_path, frame))


# --------------------------------------------------------------------------- #
# Model and tensors
# --------------------------------------------------------------------------- #
def test_build_model_is_seeded():
    first = build_model(hidden=(16,), seed=5)
    second = build_model(hidden=(16,), seed=5)
    for a, b in zip(first.parameters(), second.parameters()):
        assert torch.equal(a, b)


def test_model_output_shape():
    model = build_model(hidden=(32,), seed=1)
    out = model(torch.zeros(6, 64))
    assert out.shape == (6, 10)


def test_model_rejects_bad_hidden():
    with pytest.raises(DigitError, match="hidden"):
        DigitNet(hidden=())


def test_to_tensor_scales_pixels(sample):
    x, y = to_tensor(sample.head(8))
    assert x.shape == (8, 64)
    assert y.dtype == torch.long
    assert float(x.max()) <= 1.0 + 1e-6
    assert float(x.min()) >= 0.0


# --------------------------------------------------------------------------- #
# Training and evaluation
# --------------------------------------------------------------------------- #
def test_train_valid_metrics(trained):
    assert 0.0 <= trained.test_accuracy <= 1.0
    assert 0.0 <= trained.train_accuracy <= 1.0
    assert len(trained.history) == 2
    assert trained.train_rows + trained.test_rows == trained.rows


def test_confusion_counts_test_rows(trained):
    assert int(trained.confusion.values.sum()) == trained.test_rows
    assert list(trained.confusion.index) == [str(c) for c in CLASSES]
    assert list(trained.confusion.columns) == [str(c) for c in CLASSES]


def test_per_class_metrics_consistent(trained):
    assert len(trained.per_class) == 10
    assert trained.per_class["support"].sum() == trained.test_rows
    assert trained.per_class["recall"].between(0, 1).all()
    assert trained.per_class["precision"].between(0, 1).all()


def test_misclassified_matches_accuracy(trained):
    errors = len(trained.misclassified)
    expected = round((1 - trained.test_accuracy) * trained.test_rows)
    assert errors == expected


def test_training_is_deterministic(sample):
    first = train_model(sample, epochs=2, hidden=(32,), seed=9)
    second = train_model(sample, epochs=2, hidden=(32,), seed=9)
    assert first.test_accuracy == second.test_accuracy
    assert first.misclassified == second.misclassified


def test_seed_changes_training(sample):
    first = train_model(sample, epochs=2, hidden=(32,), seed=1)
    second = train_model(sample, epochs=2, hidden=(32,), seed=2)
    assert first.history != second.history


def test_more_epochs_improve_or_hold(sample):
    quick = train_model(sample, epochs=1, hidden=(32,), seed=3)
    longer = train_model(sample, epochs=6, hidden=(32,), seed=3)
    assert longer.test_accuracy >= quick.test_accuracy - 0.05


def test_train_rejects_bad_hyperparams(sample):
    with pytest.raises(DigitError, match="epochs"):
        train_model(sample, epochs=0)
    with pytest.raises(DigitError, match="lr must be"):
        train_model(sample, lr=0.0)
    with pytest.raises(DigitError, match="batch_size"):
        train_model(sample, batch_size=0)
    with pytest.raises(DigitError, match="test_fraction"):
        train_model(sample, test_fraction=0.9)


def test_result_to_dict(trained):
    payload = trained.to_dict()
    json.dumps(payload)
    assert payload["epochs"] == 2
    assert 0 <= payload["test_accuracy"] <= 1
    assert set(payload["per_class_recall"]) == {str(c) for c in CLASSES}
    total = sum(sum(row.values())
                for row in payload["confusion_matrix"].values())
    assert total == trained.test_rows


# --------------------------------------------------------------------------- #
# Prediction and ASCII rendering
# --------------------------------------------------------------------------- #
def test_predict_single_image(trained, sample):
    row = sample.iloc[0]
    label, confidence = trained.predict(row[list(PIXELS)].to_numpy(float))
    assert label in CLASSES
    assert 0.0 < confidence <= 1.0


def test_predict_rejects_wrong_length(trained):
    with pytest.raises(DigitError, match="64 pixel values"):
        trained.predict(np.zeros(10))


def test_predict_rejects_out_of_range(trained):
    with pytest.raises(DigitError, match="0..16"):
        trained.predict(np.full(64, 99.0))


def test_predict_rejects_nan(trained):
    bad = np.zeros(64)
    bad[3] = np.nan
    with pytest.raises(DigitError, match="finite"):
        trained.predict(bad)


def test_ascii_digit_shape():
    art = ascii_digit(np.arange(64, dtype=float))
    lines = art.splitlines()
    assert len(lines) == 8 and all(len(line) == 8 for line in lines)


def test_ascii_digit_rejects_wrong_size():
    with pytest.raises(DigitError, match="64 pixel values"):
        ascii_digit(np.zeros(5))


def test_parse_pixels():
    values = parse_pixels(",".join(str(i % 17) for i in range(64)))
    assert len(values) == 64
    assert values[0] == 0 and values[16] == 16


def test_parse_pixels_wrong_count():
    with pytest.raises(DigitError, match="expected 64"):
        parse_pixels("1,2,3")


def test_parse_pixels_not_a_number():
    with pytest.raises(DigitError, match="not a number for pixel_"):
        parse_pixels(",".join(["5"] * 63 + ["loud"]))


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections(trained):
    text = render_report(trained, _grid())
    assert "DIGIT RECOGNIZER" in text
    assert "Confusion matrix" in text
    assert "Per-class metrics:" in text
    assert "Hold-out accuracy" in text
    for label in CLASSES:
        assert f"class {label}:" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Sample digit classified as" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(DigitError, match="bundled sample"):
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
    assert "Hold-out accuracy" in out and "Done." in out


def test_cli_predict_path(capsys):
    pixels = ",".join("8" for _ in range(64))
    assert main(["--file", str(DEMO_CSV), "--epochs", "2",
                 "--predict", pixels, "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Prediction: digit " in out and "confidence" in out


def test_cli_predict_bad_count(capsys):
    assert main(["--predict", "1,2,3", "--quiet"]) == 2
    assert "expected 64" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "metrics.json"
    assert main(["--file", str(DEMO_CSV), "--epochs", "2",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["epochs"] == 2
    assert set(payload["per_class_recall"]) == {str(c) for c in CLASSES}


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
# Tensors and CLI parsing details
# --------------------------------------------------------------------------- #
def test_to_tensor_shapes(sample):
    import torch

    x, y = to_tensor(sample)
    assert tuple(x.shape) == (len(sample), 64)
    assert tuple(y.shape) == (len(sample),)
    assert x.dtype == torch.float32 and y.dtype == torch.long


def test_to_tensor_scales_into_unit_interval(sample):
    x, _ = to_tensor(sample)
    assert float(x.min()) >= 0.0 and float(x.max()) <= 1.0


def test_to_tensor_labels_cover_every_class(sample):
    _, y = to_tensor(sample)
    assert set(y.tolist()) == set(CLASSES)


def test_parse_pixels_returns_floats():
    text = ",".join(str(i % 17) for i in range(64))
    values = parse_pixels(text)
    assert len(values) == 64
    assert all(isinstance(v, float) for v in values)
