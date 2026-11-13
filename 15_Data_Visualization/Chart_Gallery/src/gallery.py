"""Chart Gallery: ten chart types rendered offline with matplotlib.

Loads a bundled monthly revenue dataset and renders every registered chart
type (line, area, grouped bar, stacked bar, ranked bar, histogram, scatter,
pie, box, heatmap) to a PNG file using the headless Agg backend. Fully
offline - no network, no GUI display required.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

import matplotlib
matplotlib.use("Agg")  # headless: must precede pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

LOG = logging.getLogger("gallery")

REQUIRED_COLUMNS = ("month", "region", "revenue", "cost", "orders")


class GalleryError(RuntimeError):
    """Raised for missing files, bad schemas, and unknown chart names."""


# --------------------------------------------------------------------------- #
# Loading and sample data
# --------------------------------------------------------------------------- #
def load_sample(path: str | Path) -> pd.DataFrame:
    """Load the monthly revenue CSV, validate it, return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise GalleryError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise GalleryError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise GalleryError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise GalleryError(f"no rows in {source.name}")

    frame = frame.copy()
    frame["month"] = frame["month"].astype(str).str.strip()
    if not frame["month"].str.match(r"\d{4}-\d{2}$").all():
        raise GalleryError("month values must look like YYYY-MM")

    frame["region"] = frame["region"].astype(str).str.strip()
    if frame["region"].eq("").any() or frame["region"].str.lower().eq("nan").any():
        raise GalleryError("empty region value(s)")

    for column in ("revenue", "cost", "orders"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise GalleryError(f"column {column!r} contains non-numeric values")
        if (frame[column] < 0).any():
            raise GalleryError(f"column {column!r} must be non-negative")
        if column == "orders" and (frame[column] % 1 != 0).any():
            raise GalleryError("column 'orders' must be whole numbers")

    if frame.duplicated(subset=["month", "region"]).any():
        raise GalleryError("duplicate (month, region) rows")

    frame["month"] = frame["month"].str.zfill(7)
    frame = frame.sort_values(["region", "month"]).reset_index(drop=True)
    LOG.info("loaded %d rows from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Data helpers
# --------------------------------------------------------------------------- #
def pivot(frame: pd.DataFrame, column: str = "revenue") -> pd.DataFrame:
    """Region x month matrix of `column` (sorted by month)."""
    table = frame.pivot_table(index="region", columns="month",
                              values=column, aggfunc="sum")
    return table.reindex(sorted(table.columns), axis=1)


def summary_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-region totals: revenue, cost, orders, margin, avg order value."""
    table = frame.groupby("region").agg(
        revenue=("revenue", "sum"),
        cost=("cost", "sum"),
        orders=("orders", "sum"),
    )
    table["margin"] = table["revenue"] - table["cost"]
    table["margin_pct"] = (table["margin"] / table["revenue"] * 100).round(1)
    table["aov"] = (table["revenue"] / table["orders"]).round(1)
    return table.sort_values("revenue", ascending=False)


# --------------------------------------------------------------------------- #
# Chart functions (uniform signature: frame -> matplotlib Figure)
# --------------------------------------------------------------------------- #
def _figure() -> tuple[Any, Any]:
    figure, axis = plt.subplots(figsize=(8, 4.5))
    return figure, axis


def chart_line(frame: pd.DataFrame):
    """Multi-series revenue trend over months."""
    figure, axis = _figure()
    table = pivot(frame)
    for region, row in table.iterrows():
        axis.plot(table.columns, row.values, marker="o", linewidth=2, label=region)
    axis.set_title("Revenue trend by region")
    axis.set_ylabel("Revenue (USD)")
    axis.set_xlabel("Month")
    axis.grid(alpha=0.3)
    axis.legend()
    figure.autofmt_xdate(rotation=45)
    return figure


def chart_area(frame: pd.DataFrame):
    """Stacked revenue area over months."""
    figure, axis = _figure()
    table = pivot(frame)
    axis.stackplot(table.columns, table.values, labels=table.index, alpha=0.85)
    axis.set_title("Stacked revenue by region")
    axis.set_ylabel("Revenue (USD)")
    axis.set_xlabel("Month")
    axis.legend(loc="upper left")
    axis.grid(alpha=0.3)
    figure.autofmt_xdate(rotation=45)
    return figure


def chart_bar(frame: pd.DataFrame):
    """Grouped bars: revenue vs cost per region."""
    figure, axis = _figure()
    summary = summary_table(frame)
    positions = np.arange(len(summary))
    width = 0.38
    axis.bar(positions - width / 2, summary["revenue"], width, label="Revenue")
    axis.bar(positions + width / 2, summary["cost"], width, label="Cost")
    axis.set_xticks(positions)
    axis.set_xticklabels(summary.index)
    axis.set_title("Revenue vs cost by region")
    axis.set_ylabel("USD")
    axis.legend()
    axis.grid(axis="y", alpha=0.3)
    return figure


def chart_stacked_bar(frame: pd.DataFrame):
    """Monthly revenue with regions stacked."""
    figure, axis = _figure()
    table = pivot(frame)
    months = list(table.columns)
    bottom = np.zeros(len(months))
    for region, row in table.iterrows():
        axis.bar(months, row.values, bottom=bottom, label=region)
        bottom = bottom + row.values
    axis.set_title("Monthly revenue (stacked regions)")
    axis.set_ylabel("Revenue (USD)")
    axis.set_xlabel("Month")
    axis.legend()
    axis.grid(axis="y", alpha=0.3)
    figure.autofmt_xdate(rotation=45)
    return figure


def chart_ranked_bar(frame: pd.DataFrame):
    """Horizontal bars ranking regions by revenue."""
    figure, axis = plt.subplots(figsize=(8, 4))
    summary = summary_table(frame)
    axis.barh(summary.index[::-1], summary["revenue"][::-1], color="#4C72B0")
    axis.set_title("Revenue ranking")
    axis.set_xlabel("Revenue (USD)")
    for i, value in enumerate(summary["revenue"][::-1]):
        axis.text(value, i, f" {int(value):,}", va="center")
    axis.grid(axis="x", alpha=0.3)
    return figure


def chart_histogram(frame: pd.DataFrame):
    """Distribution of monthly revenue values."""
    figure, axis = _figure()
    values = frame["revenue"].astype(float)
    axis.hist(values, bins=10, color="#55A868", edgecolor="white")
    axis.axvline(values.mean(), color="black", linestyle="--",
                 label=f"mean {values.mean():,.0f}")
    axis.set_title("Distribution of regional monthly revenue")
    axis.set_xlabel("Revenue (USD)")
    axis.set_ylabel("Frequency")
    axis.legend()
    axis.grid(axis="y", alpha=0.3)
    return figure


def chart_scatter(frame: pd.DataFrame):
    """Revenue vs orders with a least-squares trend line."""
    figure, axis = _figure()
    x = frame["orders"].astype(float).values
    y = frame["revenue"].astype(float).values
    axis.scatter(x, y, alpha=0.75, color="#C44E52", edgecolor="white")
    slope, intercept = np.polyfit(x, y, 1)
    order_line = np.linspace(x.min(), x.max(), 50)
    axis.plot(order_line, slope * order_line + intercept, "k--",
              label=f"trend y={slope:.1f}x+{intercept:.0f}")
    axis.set_title("Revenue vs orders")
    axis.set_xlabel("Orders")
    axis.set_ylabel("Revenue (USD)")
    axis.legend()
    axis.grid(alpha=0.3)
    return figure


def chart_pie(frame: pd.DataFrame):
    """Revenue share by region (donut)."""
    figure, axis = plt.subplots(figsize=(6.5, 6.5))
    summary = summary_table(frame)
    axis.pie(summary["revenue"], labels=summary.index, autopct="%1.1f%%",
             startangle=90, wedgeprops={"width": 0.42})
    axis.set_title("Revenue share by region")
    return figure


def chart_box(frame: pd.DataFrame):
    """Revenue spread per region."""
    figure, axis = _figure()
    groups = [group["revenue"].values for _, group in frame.groupby("region")]
    labels = list(frame.groupby("region").groups)
    axis.boxplot(groups, tick_labels=labels, patch_artist=True)
    axis.set_title("Revenue spread by region")
    axis.set_ylabel("Revenue (USD)")
    axis.grid(axis="y", alpha=0.3)
    return figure


def chart_heatmap(frame: pd.DataFrame):
    """Region x month revenue heatmap."""
    figure, axis = plt.subplots(figsize=(9, 4))
    table = pivot(frame)
    image = axis.imshow(table.values, aspect="auto", cmap="viridis")
    axis.set_xticks(range(len(table.columns)))
    axis.set_xticklabels(table.columns, rotation=45, ha="right")
    axis.set_yticks(range(len(table.index)))
    axis.set_yticklabels(table.index)
    axis.set_title("Revenue heatmap (region x month)")
    figure.colorbar(image, ax=axis, label="Revenue (USD)")
    return figure


# name -> (function, one-line description)
CHART_TYPES: dict[str, tuple[Callable[[pd.DataFrame], Any], str]] = {
    "line": (chart_line, "multi-series revenue trend over months"),
    "area": (chart_area, "stacked revenue area over months"),
    "bar": (chart_bar, "grouped revenue vs cost by region"),
    "stacked_bar": (chart_stacked_bar, "monthly revenue with stacked regions"),
    "ranked_bar": (chart_ranked_bar, "horizontal revenue ranking by region"),
    "histogram": (chart_histogram, "distribution of monthly revenue values"),
    "scatter": (chart_scatter, "revenue vs orders with trend line"),
    "pie": (chart_pie, "revenue share by region (donut)"),
    "box": (chart_box, "revenue spread by region"),
    "heatmap": (chart_heatmap, "region x month revenue heatmap"),
}


def list_charts() -> list[tuple[str, str]]:
    """Registered chart names and descriptions, in display order."""
    return [(name, description) for name, (_, description) in CHART_TYPES.items()]


def render_chart(name: str, frame: pd.DataFrame, out_path: str | Path) -> Path:
    """Render one chart type to a PNG file and close the figure."""
    if name not in CHART_TYPES:
        available = ", ".join(sorted(CHART_TYPES))
        raise GalleryError(f"unknown chart {name!r} (available: {available})")
    function, _ = CHART_TYPES[name]
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure = function(frame)
    try:
        figure.tight_layout()
        figure.savefig(target, dpi=100)
    finally:
        plt.close(figure)  # never leak figures across renders
    if not target.is_file() or target.stat().st_size == 0:
        raise GalleryError(f"failed to write {target}")
    LOG.info("rendered %s -> %s (%d bytes)", name, target, target.stat().st_size)
    return target


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "gallery_sample.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "output"


def run_demo(out_dir: Path | None = None, quiet: bool = False) -> int:
    """Render every registered chart from the bundled sample — fully offline."""
    if not quiet:
        print("=" * 62)
        print(" CHART GALLERY - offline demo")
        print(" Bundled sample data, headless Agg backend, local PNGs.")
        print("=" * 62)

    if not DEMO_CSV.is_file():
        raise GalleryError(f"bundled sample not found: {DEMO_CSV}")
    frame = load_sample(DEMO_CSV)
    target_dir = out_dir or DEFAULT_OUTPUT

    if not quiet:
        print(f"\nLoaded {len(frame)} rows "
              f"({frame['region'].nunique()} regions x "
              f"{frame['month'].nunique()} months) from {DEMO_CSV.name}")
        print(f"Rendering {len(CHART_TYPES)} charts to {target_dir}/\n")

    written: dict[str, str] = {}
    for name in CHART_TYPES:
        path = render_chart(name, frame, target_dir / f"{name}.png")
        written[name] = str(path)
        if not quiet:
            size = path.stat().st_size
            print(f"  {name:<12} {path.name:<18} {size:>7,} bytes")

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(written) == len(CHART_TYPES) == 10, "expected exactly 10 charts"
    for name, file_name in written.items():
        assert Path(file_name).is_file(), f"{name} not written"
        assert Path(file_name).stat().st_size > 1000, f"{name} suspiciously small"
    assert plt.get_fignums() == [], "figures must be closed after rendering"

    # summary math matches the raw frame
    summary = summary_table(frame)
    assert int(summary["revenue"].sum()) == int(frame["revenue"].sum())
    assert int(summary["orders"].sum()) == int(frame["orders"].sum())
    table = pivot(frame)
    assert float(table.values.sum()) == float(frame["revenue"].sum())
    assert abs(float(frame.loc[frame['region'] == 'East', 'revenue'].sum())
               - summary.loc['East', 'revenue']) < 0.01

    if not quiet:
        print(f"\nCross-checks OK: {len(written)} charts rendered, "
              f"figures closed, pivot/summary totals match "
              f"(revenue {int(frame['revenue'].sum()):,})")
        print("\nDemo completed successfully.")
    return 0
