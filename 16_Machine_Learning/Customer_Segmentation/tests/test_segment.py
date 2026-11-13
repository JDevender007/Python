"""Tests for the Customer Segmentation project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from segment import (  # noqa: E402
    DEFAULT_K_RANGE,
    DEMO_CSV,
    FEATURES,
    REQUIRED_COLUMNS,
    SegmentError,
    load_customers,
    render_report,
    run_demo,
    segment,
    sweep_k,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    row = {
        "customer_id": "C001", "freq_per_month": 5.0,
        "avg_spend": 40.0, "tenure_months": 12.0,
    }
    row.update(overrides)
    return row


def _csv(tmp_path: Path, rows: list[dict], name: str = "customers.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _grid(n: int = 30) -> list[dict]:
    """n valid rows with variation in every feature."""
    return [_row(
        customer_id=f"C{i + 1:04d}",
        freq_per_month=1.0 + i % 10,
        avg_spend=10.0 + i * 3.5,
        tenure_months=1.0 + i % 40,
    ) for i in range(n)]


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_customers(DEMO_CSV)


@pytest.fixture(scope="module")
def clustered(sample):
    return segment(sample)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 360
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert not sample["customer_id"].duplicated().any()
    for column in FEATURES:
        assert pd.api.types.is_numeric_dtype(sample[column])


def test_load_missing_file(tmp_path):
    with pytest.raises(SegmentError, match="not found"):
        load_customers(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("customer_id,avg_spend\nC1,40\n", encoding="utf-8")
    with pytest.raises(SegmentError, match="missing column"):
        load_customers(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(SegmentError, match="no rows"):
        load_customers(path)


def test_load_empty_customer_id(tmp_path):
    rows = _grid()
    rows[0]["customer_id"] = ""
    with pytest.raises(SegmentError, match="empty customer_id"):
        load_customers(_csv(tmp_path, rows))


def test_load_duplicate_customer_id(tmp_path):
    rows = _grid()
    rows[1]["customer_id"] = rows[0]["customer_id"]
    with pytest.raises(SegmentError, match="duplicate customer_id"):
        load_customers(_csv(tmp_path, rows))


def test_load_non_numeric_spend(tmp_path):
    rows = _grid()
    rows[0]["avg_spend"] = "lots"
    with pytest.raises(SegmentError, match="'avg_spend' contains non-numeric"):
        load_customers(_csv(tmp_path, rows))


def test_load_nan_frequency(tmp_path):
    rows = _grid()
    rows[0]["freq_per_month"] = None
    with pytest.raises(SegmentError,
                       match="'freq_per_month' contains non-numeric"):
        load_customers(_csv(tmp_path, rows))


def test_load_zero_frequency(tmp_path):
    rows = _grid()
    rows[0]["freq_per_month"] = 0
    with pytest.raises(SegmentError, match="freq_per_month.*outside"):
        load_customers(_csv(tmp_path, rows))


def test_load_negative_spend(tmp_path):
    rows = _grid()
    rows[0]["avg_spend"] = -5
    with pytest.raises(SegmentError, match="avg_spend.*outside"):
        load_customers(_csv(tmp_path, rows))


def test_load_too_few_customers(tmp_path):
    with pytest.raises(SegmentError, match="at least 10"):
        load_customers(_csv(tmp_path, _grid(5)))


def test_load_constant_feature_rejected(tmp_path):
    rows = _grid()
    for row in rows:
        row["tenure_months"] = 12.0
    with pytest.raises(SegmentError, match="no variation.*tenure"):
        load_customers(_csv(tmp_path, rows))


def test_load_sorted_by_id(tmp_path):
    rows = _grid()
    rows[0]["customer_id"] = "Z999"
    frame = load_customers(_csv(tmp_path, rows))
    ids = list(frame["customer_id"])
    assert ids == sorted(ids)


# --------------------------------------------------------------------------- #
# Silhouette sweep and k selection
# --------------------------------------------------------------------------- #
def test_sweep_covers_default_range(sample):
    scores = sweep_k(sample)
    assert set(scores) == set(DEFAULT_K_RANGE)
    for k, score in scores.items():
        assert 0.0 < score <= 1.0, k


def test_sweep_rejects_empty_range(sample):
    with pytest.raises(SegmentError, match="empty"):
        sweep_k(sample, k_range=range(0))


def test_sweep_rejects_k_too_large(sample):
    with pytest.raises(SegmentError, match="k must be in"):
        sweep_k(sample, k_range=range(2, len(sample) + 5))


def test_sweep_is_deterministic(sample):
    first = sweep_k(sample)
    second = sweep_k(sample)
    assert first == second


def test_segment_picks_best_silhouette_k(sample, clustered):
    scores = sweep_k(sample)
    assert clustered.k == max(scores, key=scores.get)
    assert clustered.silhouette == pytest.approx(scores[clustered.k])


def test_segment_forced_k(sample, clustered):
    forced = segment(sample, k=4)
    assert forced.k == 4
    assert forced.silhouette > 0.0
    assert len(set(forced.labels)) == 4


def test_segment_rejects_bad_k(sample):
    with pytest.raises(SegmentError, match="k must be in"):
        segment(sample, k=1)
    with pytest.raises(SegmentError, match="k must be in"):
        segment(sample, k=len(sample) + 3)


def test_segment_labels_partition(sample, clustered):
    assert len(clustered.labels) == len(sample)
    assert set(clustered.labels) == set(range(clustered.k))


def test_segment_is_deterministic(sample, clustered):
    again = segment(sample, k=clustered.k)
    assert (again.labels == clustered.labels).all()
    assert again.silhouette == clustered.silhouette


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #
def test_profiles_partition_the_sample(sample, clustered):
    assert int(clustered.profiles["size"].sum()) == len(sample)
    assert clustered.profiles["share_pct"].sum() == pytest.approx(100.0)
    assert len(clustered.profiles) == clustered.k


def test_profiles_ranks_are_one_to_k(clustered):
    assert list(clustered.profiles["rank"]) == list(
        range(1, clustered.k + 1))


def test_profiles_sorted_by_value_desc(clustered):
    values = list(clustered.profiles["value_index"])
    assert values == sorted(values, reverse=True)


def test_profiles_value_index_math(clustered, sample):
    work = sample.copy()
    work["cluster"] = clustered.labels
    expected = (work["freq_per_month"] * work["avg_spend"]).mean()
    # overall mean value must sit between min and max cluster values
    values = list(clustered.profiles["value_index"])
    assert min(values) <= expected <= max(values)
    # rank-1 cluster must be worth at least 2x the last-ranked one
    assert values[0] > 2 * values[-1]


def test_profiles_cluster_means_match_labels(clustered, sample):
    work = sample.copy()
    work["cluster"] = clustered.labels
    for _, row in clustered.profiles.iterrows():
        subset = work[work["cluster"] == row["cluster"]]
        assert len(subset) == int(row["size"])
        assert subset["avg_spend"].mean() == pytest.approx(row["avg_spend"])
        assert subset["tenure_months"].mean() == pytest.approx(
            row["tenure_months"])


def test_result_to_dict(clustered):
    payload = clustered.to_dict()
    json.dumps(payload)
    assert payload["k"] == clustered.k
    assert 0 < payload["silhouette"] <= 1
    assert len(payload["clusters"]) == clustered.k
    assert sum(c["size"] for c in payload["clusters"]) == 360
    assert set(payload["sweep"]) == {str(k) for k in DEFAULT_K_RANGE}


# --------------------------------------------------------------------------- #
# Assign
# --------------------------------------------------------------------------- #
def test_assign_reproduces_training_labels(sample, clustered):
    reassigned = cluster_assign_helper(clustered, sample)
    assert (reassigned == clustered.labels).all()


def cluster_assign_helper(clustered, frame):
    return clustered.assign(frame)


def test_assign_handles_new_customers(clustered):
    new = pd.DataFrame([
        _row(customer_id="N1", freq_per_month=14.0, avg_spend=135.0,
             tenure_months=50.0),
        _row(customer_id="N2", freq_per_month=1.0, avg_spend=15.0,
             tenure_months=2.0),
    ])
    labels = clustered.assign(new)
    assert len(labels) == 2
    # high-value newcomer lands in the rank-1 cluster
    rank1 = int(clustered.profiles.iloc[0]["cluster"])
    rank_last = int(clustered.profiles.iloc[-1]["cluster"])
    assert labels[0] == rank1
    assert labels[1] == rank_last


def test_assign_missing_feature(clustered):
    with pytest.raises(SegmentError, match="missing feature"):
        clustered.assign(pd.DataFrame([{"avg_spend": 50.0}]))


def test_assign_non_numeric_values(clustered):
    bad = pd.DataFrame([{f: "x" for f in FEATURES}])
    with pytest.raises(SegmentError, match="non-numeric"):
        clustered.assign(bad)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections(clustered, sample):
    text = render_report(clustered, sample)
    assert "CUSTOMER SEGMENTATION" in text
    assert "k sweep" in text
    assert "<-- best" in text
    assert "Cluster profiles" in text
    assert "Interpretation:" in text
    assert "rank 1" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "Cluster profiles" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(SegmentError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_file_auto_k(capsys):
    assert main(["--file", str(DEMO_CSV)]) == 0
    out = capsys.readouterr().out
    assert "Chosen k" in out and "Done." in out


def test_cli_file_forced_k(tmp_path, capsys):
    payload_path = tmp_path / "segments.json"
    assert main(["--file", str(DEMO_CSV), "--k", "4",
                 "--json", str(payload_path)]) == 0
    out = capsys.readouterr().out
    assert "Chosen k    : 4" in out
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["k"] == 4
    assert len(payload["clusters"]) == 4


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "segments.json"
    assert main(["--file", str(DEMO_CSV), "--json", str(payload_path),
                 "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["k"] >= 2
    assert sum(c["size"] for c in payload["clusters"]) == 360


def test_cli_bad_k(capsys):
    assert main(["--file", str(DEMO_CSV), "--k", "1"]) == 2
    assert "k must be in" in capsys.readouterr().err


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
