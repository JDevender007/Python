"""Customer segmentation with k-means — clustering and profiling, offline.

Loads a customer CSV (frequency, spend, tenure), standardises the
features, sweeps k with silhouette scores to pick a cluster count, fits
KMeans, and renders per-cluster value profiles. Local files only - no
network, no dataset downloads, no model artifacts fetched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

LOG = logging.getLogger("segment")

FEATURES = ("freq_per_month", "avg_spend", "tenure_months")
REQUIRED_COLUMNS = ("customer_id",) + FEATURES
RANGES = {
    "freq_per_month": (1, 500),
    "avg_spend": (1.0, 10_000.0),
    "tenure_months": (1, 600),
}
DEFAULT_K_RANGE = range(2, 9)
RANDOM_STATE = 42


class SegmentError(RuntimeError):
    """Raised for missing files, bad schemas, and clustering failures."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_customers(path: str | Path) -> pd.DataFrame:
    """Load the customer CSV, validate it, and return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise SegmentError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise SegmentError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SegmentError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise SegmentError(f"no rows in {source.name}")

    frame = frame.copy()
    frame["customer_id"] = frame["customer_id"].astype(str).str.strip()
    if frame["customer_id"].eq("").any() or \
            frame["customer_id"].str.lower().eq("nan").any():
        raise SegmentError("empty customer_id value(s)")
    if frame["customer_id"].duplicated().any():
        raise SegmentError("duplicate customer_id value(s)")

    for column in FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise SegmentError(f"column {column!r} contains non-numeric values")
        if not np.isfinite(frame[column]).all():
            raise SegmentError(f"column {column!r} must be finite")
        low, high = RANGES[column]
        if not frame[column].between(low, high).all():
            raise SegmentError(f"column {column!r} outside {low:g}..{high:g}")

    if len(frame) < 10:
        raise SegmentError("need at least 10 customers to cluster")
    if frame[list(FEATURES)].nunique().min() < 2:
        constant = frame[list(FEATURES)].nunique()
        flat = constant[constant < 2].index.tolist()
        raise SegmentError(
            f"feature(s) with no variation: {', '.join(flat)}")

    frame = frame.sort_values("customer_id").reset_index(drop=True)
    LOG.info("loaded %d customers from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Clustering
# --------------------------------------------------------------------------- #
@dataclass
class SegmentationResult:
    """Fitted k-means model, chosen k, and per-cluster profiles."""

    k: int
    labels: np.ndarray
    silhouette: float
    scores: dict[int, float] = field(default_factory=dict)
    scaler: Any = None
    model: Any = None
    profiles: pd.DataFrame = field(default_factory=pd.DataFrame)

    def assign(self, customers: pd.DataFrame) -> np.ndarray:
        """Cluster new customers with the fitted scaler + model."""
        missing = [f for f in FEATURES if f not in customers.columns]
        if missing:
            raise SegmentError(f"missing feature(s): {', '.join(missing)}")
        values = customers[list(FEATURES)].apply(
            pd.to_numeric, errors="coerce")
        if values.isna().any().any():
            raise SegmentError("features contain non-numeric values")
        scaled = self.scaler.transform(values)
        return self.model.predict(scaled)

    def to_dict(self) -> dict[str, Any]:
        return {
            "k": self.k,
            "silhouette": round(self.silhouette, 4),
            "sweep": {str(k): round(score, 4)
                      for k, score in sorted(self.scores.items())},
            "clusters": [
                {
                    "cluster": int(row["cluster"]),
                    "rank": int(row["rank"]),
                    "size": int(row["size"]),
                    "share_pct": round(float(row["share_pct"]), 2),
                    **{f: round(float(row[f]), 3) for f in FEATURES},
                    "value_index": round(float(row["value_index"]), 1),
                }
                for _, row in self.profiles.iterrows()
            ],
        }


def sweep_k(frame: pd.DataFrame,
            k_range: range = DEFAULT_K_RANGE) -> dict[int, float]:
    """Silhouette score for each k (features standardised first)."""
    k_values = list(k_range)
    if not k_values:
        raise SegmentError("k_range is empty")
    n = len(frame)
    for k in k_values:
        if k < 2 or k >= n:
            raise SegmentError(f"k must be in 2..{n - 1}, got {k}")

    scaled = StandardScaler().fit_transform(frame[list(FEATURES)])
    scores: dict[int, float] = {}
    for k in k_values:
        model = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
        labels = model.fit_predict(scaled)
        scores[k] = float(silhouette_score(scaled, labels))
    LOG.info("swept k=%s", sorted(scores))
    return scores


def segment(frame: pd.DataFrame, k: int | None = None) -> SegmentationResult:
    """Cluster customers; if k is None pick the best silhouette in 2..8."""
    if k is not None and not 2 <= k < len(frame):
        raise SegmentError(f"k must be in 2..{len(frame) - 1}, got {k}")

    # fit the scaler on a DataFrame so feature names survive for assign()
    scaler = StandardScaler()
    scaled = scaler.fit_transform(frame[list(FEATURES)])

    scores = sweep_k(frame)
    if k is None:
        k = max(scores, key=scores.get)
    elif k not in scores:
        probe = KMeans(n_clusters=k, n_init=10,
                       random_state=RANDOM_STATE).fit_predict(scaled)
        scores[k] = float(silhouette_score(scaled, probe))

    model = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE)
    labels = model.fit_predict(scaled)
    silhouette = float(silhouette_score(scaled, labels))

    profiles = _build_profiles(frame, labels)
    result = SegmentationResult(
        k=k, labels=labels, silhouette=silhouette, scores=scores,
        scaler=scaler, model=model, profiles=profiles)
    LOG.info("segmented %d customers into %d clusters (silhouette %.3f)",
             len(frame), k, silhouette)
    return result


def _build_profiles(frame: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Per-cluster size, mean features, and a ranked value index."""
    work = frame.copy()
    work["cluster"] = labels
    # value index = how much revenue the average member generates monthly
    work["_value"] = work["freq_per_month"] * work["avg_spend"]

    profiles = work.groupby("cluster").agg(
        size=("customer_id", "count"),
        freq_per_month=("freq_per_month", "mean"),
        avg_spend=("avg_spend", "mean"),
        tenure_months=("tenure_months", "mean"),
        value_index=("_value", "mean"),
    )
    profiles["share_pct"] = profiles["size"] / len(work) * 100
    # rank clusters by value: 1 = most valuable
    profiles["rank"] = profiles["value_index"].rank(
        ascending=False, method="first").astype(int)
    profiles = profiles.sort_values("rank").reset_index()
    return profiles


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(result: SegmentationResult, frame: pd.DataFrame) -> str:
    """Human-readable segmentation report used by the CLI and demo."""
    lines = [
        "CUSTOMER SEGMENTATION (k-means)",
        "=" * 70,
        f"Customers   : {len(frame)}   features: {', '.join(FEATURES)}",
        f"Chosen k    : {result.k}  "
        f"(silhouette {result.silhouette:.3f})",
        "",
        "k sweep (standardised features):",
    ]
    for k, score in sorted(result.scores.items()):
        marker = "  <-- best" if k == result.k else ""
        bar = "#" * max(1, round(score * 60))
        lines.append(f"  k={k}  {score:.3f}  {bar}{marker}")

    lines += [
        "",
        "Cluster profiles (rank 1 = highest value):",
        f"  {'rank':<5}{'cluster':>8}{'size':>7}{'share':>8}"
        f"{'freq/mo':>9}{'spend':>9}{'tenure':>8}{'value/mo':>10}",
        "  " + "-" * 64,
    ]
    for _, row in result.profiles.iterrows():
        lines.append(
            f"  {int(row['rank']):<5}{int(row['cluster']):>8}"
            f"{int(row['size']):>7}{row['share_pct']:>7.1f}%"
            f"{row['freq_per_month']:>9.1f}{row['avg_spend']:>9.1f}"
            f"{row['tenure_months']:>8.1f}{row['value_index']:>10.1f}"
        )

    top = result.profiles.iloc[0]
    bottom = result.profiles.iloc[-1]
    lines += [
        "",
        f"Interpretation: cluster {int(top['cluster'])} (rank 1) spends "
        f"${top['avg_spend']:.1f} x {top['freq_per_month']:.1f}/mo "
        f"= ${top['value_index']:.0f} value/mo per customer, while "
        f"cluster {int(bottom['cluster'])} is worth "
        f"${bottom['value_index']:.0f}.",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "customers.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Cluster the bundled customer sample — fully offline."""
    print("=" * 70)
    print(" CUSTOMER SEGMENTATION - offline demo")
    print(" Bundled sample; scikit-learn k-means; no network.")
    print("=" * 70)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise SegmentError(f"bundled sample not found: {source}")

    frame = load_customers(source)
    print(f"\nLoaded {len(frame)} customers from {source.name}")

    result = segment(frame)
    print()
    print(render_report(result, frame))

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(result.labels) == len(frame), "one label per customer"
    assert set(result.labels) == set(range(result.k)), "labels must be 0..k-1"
    assert 0.0 < result.silhouette <= 1.0, "silhouette out of range"
    assert result.silhouette > 0.25, "clusters are barely separated"
    assert result.k == max(result.scores, key=result.scores.get), \
        "chosen k must win the silhouette sweep"
    assert int(result.profiles["size"].sum()) == len(frame), \
        "cluster sizes must partition the sample"
    assert abs(float(result.profiles["share_pct"].sum()) - 100) < 1e-6, \
        "shares must sum to 100%"
    assert list(result.profiles["rank"]) == list(range(1, result.k + 1)), \
        "ranks must be 1..k"

    # deterministic re-run gives identical clustering
    again = segment(frame)
    assert again.k == result.k and again.silhouette == result.silhouette, \
        "clustering is not deterministic"
    assert (again.labels == result.labels).all(), "labels changed between runs"

    # assigning the same customers reproduces their labels
    reassigned = result.assign(frame)
    assert (reassigned == result.labels).all(), "assign() disagrees with fit"

    # the data really is separable: profiles must differ in value
    values = list(result.profiles["value_index"])
    assert max(values) > 2 * min(values), "profiles look homogeneous"

    print(f"\nCross-checks OK: {result.k} clusters partition {len(frame)} "
          f"customers, silhouette {result.silhouette:.3f}, deterministic "
          f"re-run, assign() reproduces labels")
    print("\nDemo completed successfully.")
    return 0
