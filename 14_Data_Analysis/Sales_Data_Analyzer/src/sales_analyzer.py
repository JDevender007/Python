"""Sales data analysis: loading, validation, and period/segment reporting.

Reads a CSV of orders, validates it, and produces a SalesReport with
totals, per-period revenue and growth, segment breakdowns (region,
category, product), and a moving-average trend. Everything is local
file analysis - no network, no APIs.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

LOG = logging.getLogger("sales.analyzer")

REQUIRED_COLUMNS = ("order_id", "date", "region", "category",
                    "product", "quantity", "unit_price", "revenue")
SEGMENT_COLUMNS = ("region", "category", "product")
PERIODS = ("D", "W", "M", "Q", "Y")
# user-facing alias -> pandas resample code (ME/QE/YE are the modern names)
PERIOD_CODES = {"D": "D", "W": "W", "M": "ME", "Q": "QE", "Y": "YE"}


class SalesError(RuntimeError):
    """Raised for missing files, bad schemas, and bad values."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_sales(path: str | Path) -> pd.DataFrame:
    """Load a sales CSV, validate it, and return a cleaned DataFrame."""
    source = Path(path)
    if not source.is_file():
        raise SalesError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:  # pandas raises assorted parser errors
        raise SalesError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SalesError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise SalesError(f"no rows in {source.name}")

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if frame["date"].isna().any():
        bad = int(frame["date"].isna().sum())
        raise SalesError(f"{bad} row(s) have an unparseable date")

    for column in ("quantity", "unit_price", "revenue"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise SalesError(f"column {column!r} contains non-numeric values")
        if (frame[column] < 0).any():
            raise SalesError(f"column {column!r} contains negative values")

    if (frame["quantity"] == 0).any():
        raise SalesError("column 'quantity' contains zeros")

    # recompute revenue so the report never trusts a stale CSV column
    frame["revenue"] = (frame["quantity"] * frame["unit_price"]).round(2)
    frame = frame.sort_values("date").reset_index(drop=True)
    LOG.info("loaded %d rows from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Report model
# --------------------------------------------------------------------------- #
@dataclass
class SalesReport:
    """Aggregated view over a validated sales DataFrame."""

    frame: pd.DataFrame
    period: str = "M"
    total_revenue: float = 0.0
    total_orders: int = 0
    total_units: int = 0
    date_min: str = ""
    date_max: str = ""
    by_period: pd.DataFrame = field(default_factory=pd.DataFrame)
    by_segment: dict[str, pd.DataFrame] = field(default_factory=dict)
    growth_pct: list[tuple[str, float]] = field(default_factory=list)
    moving_average: pd.Series = field(default_factory=pd.Series)

    @property
    def avg_order_value(self) -> float:
        return round(self.total_revenue / self.total_orders, 2) if self.total_orders else 0.0

    @property
    def avg_daily_revenue(self) -> float:
        days = max(1, (self.frame["date"].max() - self.frame["date"].min()).days + 1)
        return round(self.total_revenue / days, 2)

    def top_products(self, n: int = 5) -> pd.DataFrame:
        return self.by_segment["product"].head(n)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_revenue": round(self.total_revenue, 2),
            "total_orders": self.total_orders,
            "total_units": self.total_units,
            "avg_order_value": self.avg_order_value,
            "avg_daily_revenue": self.avg_daily_revenue,
            "date_range": [self.date_min, self.date_max],
            "period": self.period,
            "by_period": [
                {"period": str(idx), "revenue": round(float(row["revenue"]), 2),
                 "orders": int(row["orders"])}
                for idx, row in self.by_period.iterrows()
            ],
            "growth_pct": [{"period": p, "growth_pct": round(g, 2)}
                           for p, g in self.growth_pct],
            "by_region": _frame_records(self.by_segment["region"]),
            "by_category": _frame_records(self.by_segment["category"]),
            "top_products": _frame_records(self.top_products()),
        }


def _frame_records(frame: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    subset = frame if limit is None else frame.head(limit)
    records = []
    for idx, row in subset.iterrows():
        record = {"name": str(idx)}
        for key, value in row.items():
            record[str(key)] = round(float(value), 2) if isinstance(value, float) else int(value)
        records.append(record)
    return records


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def analyze(frame: pd.DataFrame, period: str = "M",
            segments: tuple[str, ...] = SEGMENT_COLUMNS,
            window: int = 3) -> SalesReport:
    """Aggregate a validated frame into a SalesReport."""
    if period not in PERIODS:
        raise SalesError(f"unknown period {period!r} (choose {', '.join(PERIODS)})")
    for segment in segments:
        if segment not in frame.columns:
            raise SalesError(f"unknown segment {segment!r}")

    report = SalesReport(frame=frame, period=period)
    report.total_revenue = float(frame["revenue"].sum())
    report.total_orders = int(len(frame))
    report.total_units = int(frame["quantity"].sum())
    report.date_min = str(frame["date"].min().date())
    report.date_max = str(frame["date"].max().date())

    # per-period revenue/orders (pandas 2.3 resample emits an internal
    # NumPy-timedelta DeprecationWarning we can't control)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=".*'generic' unit for NumPy timedelta is deprecated.*",
            category=DeprecationWarning,
        )
        grouped = frame.set_index("date").resample(PERIOD_CODES[period])["revenue"].agg(
            ["sum", "count"]
        )
    grouped.columns = ["revenue", "orders"]
    report.by_period = grouped

    # period-over-period growth (%)
    previous: float | None = None
    for idx, row in grouped.iterrows():
        current = float(row["revenue"])
        if previous is not None and previous > 0:
            report.growth_pct.append(
                (str(idx.date()), (current - previous) / previous * 100.0)
            )
        previous = current

    # segment breakdowns: revenue, orders, units
    for segment in segments:
        table = frame.groupby(segment).agg(
            revenue=("revenue", "sum"),
            orders=("order_id", "count"),
            units=("quantity", "sum"),
        ).sort_values("revenue", ascending=False)
        table["revenue"] = table["revenue"].round(2)
        report.by_segment[segment] = table

    # simple moving average of period revenue (trend smoothing)
    if len(grouped) >= 2:
        report.moving_average = grouped["revenue"].rolling(
            min(window, len(grouped)), min_periods=1
        ).mean().round(2)

    LOG.info("analysed %d orders, revenue %.2f", report.total_orders,
             report.total_revenue)
    return report


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_report(report: SalesReport, top: int = 5) -> str:
    """Human-readable report used by the CLI and demo."""
    lines = [
        "SALES ANALYSIS",
        "=" * 64,
        f"Period      : {report.date_min} .. {report.date_max} (bucketed {report.period})",
        f"Orders      : {report.total_orders:,}   Units: {report.total_units:,}",
        f"Revenue     : ${report.total_revenue:,.2f}",
        f"Avg order   : ${report.avg_order_value:,.2f}   "
        f"Avg day: ${report.avg_daily_revenue:,.2f}",
        "",
        "Revenue by period:",
    ]
    peak = report.by_period["revenue"].max() if len(report.by_period) else 0.0
    for idx, row in report.by_period.iterrows():
        bar = "#" * max(1, round(float(row["revenue"]) / peak * 24)) if peak else ""
        lines.append(f"  {str(idx.date()):<12} ${float(row['revenue']):>10,.2f}  {bar}")

    if report.growth_pct:
        last = report.growth_pct[-1]
        total_growth = sum(g for _, g in report.growth_pct)
        lines += [
            "",
            f"Growth      : last period {last[1]:+.1f}%   "
            f"cumulative {total_growth:+.1f}% across {len(report.growth_pct)} transitions",
        ]

    for segment in ("region", "category"):
        lines += ["", f"By {segment}:"]
        table = report.by_segment[segment]
        for name, row in table.iterrows():
            share = float(row["revenue"]) / report.total_revenue * 100 if report.total_revenue else 0
            lines.append(f"  {str(name):<14} ${float(row['revenue']):>10,.2f}  "
                         f"{share:5.1f}%  ({int(row['orders'])} orders)")

    lines += ["", f"Top {top} products:"]
    for name, row in report.top_products(top).iterrows():
        lines.append(f"  {str(name):<20} ${float(row['revenue']):>10,.2f}  "
                     f"{int(row['orders'])} orders")

    if len(report.moving_average):
        lines += ["", "Trend (moving avg of period revenue):"]
        for idx, value in report.moving_average.items():
            lines.append(f"  {str(idx.date()):<12} ${float(value):>10,.2f}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "sales_sample.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Analyse the bundled sample CSV and print the full report."""
    print("=" * 64)
    print(" SALES DATA ANALYZER - offline demo")
    print(" Local CSV only; no network, no APIs.")
    print("=" * 64)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise SalesError(f"bundled sample not found: {source}")

    frame = load_sales(source)
    print(f"\nLoaded {len(frame):,} orders from {source.name}")

    report = analyze(frame, period="M")
    print()
    print(render_report(report, top=5))

    # cross-checks the demo asserts
    recomputed = float((frame["quantity"] * frame["unit_price"]).sum())
    assert abs(recomputed - report.total_revenue) < 0.01, "revenue mismatch"
    assert report.total_orders == len(frame)
    segment_sum = float(report.by_segment["region"]["revenue"].sum())
    assert abs(segment_sum - report.total_revenue) < 0.01, "region split mismatch"
    print(f"\nCross-checks OK: regions sum to ${segment_sum:,.2f}")

    # quarterly view for a coarser cut
    quarterly = analyze(frame, period="Q")
    print(f"Quarterly buckets: {len(quarterly.by_period)} "
          f"(peak ${quarterly.by_period['revenue'].max():,.2f})")

    print("\nDemo completed successfully.")
    return 0
