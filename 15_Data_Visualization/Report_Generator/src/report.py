"""Report generator: data-driven HTML and Markdown reports - offline.

Loads a CSV of monthly channel performance, computes summary statistics,
renders charts with matplotlib (Agg), embeds them as base64 data URIs, and
assembles a self-contained HTML report plus a Markdown version. Fully
offline: local files only, no CDN, no network, no API keys.
"""

from __future__ import annotations

import base64
import html
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")  # headless: must precede pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

LOG = logging.getLogger("report")

REQUIRED_COLUMNS = ("month", "channel", "revenue", "cost", "orders")


class ReportError(RuntimeError):
    """Raised for missing files, bad schemas, and assembly failures."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_data(path: str | Path) -> pd.DataFrame:
    """Load the channel-performance CSV, validate it, return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise ReportError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise ReportError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ReportError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise ReportError(f"no rows in {source.name}")

    frame = frame.copy()
    frame["month"] = frame["month"].astype(str).str.strip()
    if not frame["month"].str.match(r"\d{4}-\d{2}$").all():
        raise ReportError("month values must look like YYYY-MM")

    frame["channel"] = frame["channel"].astype(str).str.strip()
    if frame["channel"].eq("").any() or frame["channel"].str.lower().eq("nan").any():
        raise ReportError("empty channel value(s)")

    for column in ("revenue", "cost", "orders"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise ReportError(f"column {column!r} contains non-numeric values")
        if (frame[column] < 0).any():
            raise ReportError(f"column {column!r} must be non-negative")
        if column == "orders" and (frame[column] % 1 != 0).any():
            raise ReportError("column 'orders' must be whole numbers")

    if frame.duplicated(subset=["month", "channel"]).any():
        raise ReportError("duplicate (month, channel) rows")
    if frame["channel"].nunique() < 2:
        raise ReportError("need at least two channels")
    if frame["month"].nunique() < 2:
        raise ReportError("need at least two months")

    frame = frame.sort_values(["month", "channel"]).reset_index(drop=True)
    LOG.info("loaded %d rows from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Summary model
# --------------------------------------------------------------------------- #
@dataclass
class ReportSummary:
    """Aggregated numbers driving both report formats."""

    frame: pd.DataFrame
    totals: dict[str, float] = field(default_factory=dict)
    by_channel: pd.DataFrame = field(default_factory=pd.DataFrame)
    monthly: pd.DataFrame = field(default_factory=pd.DataFrame)
    best_month: str = ""
    worst_month: str = ""
    best_channel: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "totals": {k: round(v, 2) for k, v in self.totals.items()},
            "by_channel": [
                {"channel": str(idx), **{str(k): round(float(v), 2)
                                         for k, v in row.items()}}
                for idx, row in self.by_channel.iterrows()
            ],
            "monthly": [
                {"month": str(idx), **{str(k): round(float(v), 2)
                                       for k, v in row.items()}}
                for idx, row in self.monthly.iterrows()
            ],
            "best_month": self.best_month,
            "worst_month": self.worst_month,
            "best_channel": self.best_channel,
            "notes": list(self.notes),
        }


def summarize(frame: pd.DataFrame) -> ReportSummary:
    """Compute totals, per-channel and per-month aggregates, and insights."""
    summary = ReportSummary(frame=frame)
    revenue = float(frame["revenue"].sum())
    cost = float(frame["cost"].sum())
    orders = int(frame["orders"].sum())
    margin = revenue - cost
    summary.totals = {
        "revenue": revenue,
        "cost": cost,
        "margin": margin,
        "margin_pct": margin / revenue * 100 if revenue else 0.0,
        "orders": float(orders),
        "aov": revenue / orders if orders else 0.0,
        "months": float(frame["month"].nunique()),
        "channels": float(frame["channel"].nunique()),
        "rows": float(len(frame)),
    }

    by_channel = frame.groupby("channel").agg(
        revenue=("revenue", "sum"),
        cost=("cost", "sum"),
        orders=("orders", "sum"),
    )
    by_channel["margin"] = by_channel["revenue"] - by_channel["cost"]
    by_channel["share_pct"] = by_channel["revenue"] / revenue * 100
    by_channel["margin_pct"] = np.where(
        by_channel["revenue"] > 0,
        by_channel["margin"] / by_channel["revenue"] * 100, 0.0)
    summary.by_channel = by_channel.sort_values("revenue", ascending=False)

    monthly = frame.groupby("month").agg(
        revenue=("revenue", "sum"),
        cost=("cost", "sum"),
        orders=("orders", "sum"),
    )
    monthly["margin"] = monthly["revenue"] - monthly["cost"]
    monthly["growth_pct"] = monthly["revenue"].pct_change() * 100
    summary.monthly = monthly

    summary.best_month = str(monthly["revenue"].idxmax())
    summary.worst_month = str(monthly["revenue"].idxmin())
    summary.best_channel = str(summary.by_channel.index[0])

    # --- insights (plain-language notes) ---------------------------------- #
    growth = float(monthly["growth_pct"].iloc[-1]) if len(monthly) > 1 else 0.0
    if growth >= 0:
        summary.notes.append(
            f"Revenue grew {growth:+.1f}% from {monthly.index[-2]} to "
            f"{monthly.index[-1]}.")
    else:
        summary.notes.append(
            f"Revenue fell {growth:+.1f}% from {monthly.index[-2]} to "
            f"{monthly.index[-1]} - investigate the dip.")
    top_share = float(summary.by_channel["share_pct"].iloc[0])
    summary.notes.append(
        f"{summary.best_channel} leads with {top_share:.1f}% of total revenue.")
    total_first = float(monthly["revenue"].iloc[0])
    total_last = float(monthly["revenue"].iloc[-1])
    overall = (total_last - total_first) / total_first * 100 if total_first else 0.0
    summary.notes.append(
        f"First-to-last month revenue change: {overall:+.1f}% "
        f"(${total_first:,.0f} -> ${total_last:,.0f}).")
    lowest_margin = summary.by_channel["margin_pct"].min()
    worst_margin_channel = str(summary.by_channel["margin_pct"].idxmin())
    summary.notes.append(
        f"Thinnest margin: {worst_margin_channel} at {lowest_margin:.1f}%.")
    return summary


# --------------------------------------------------------------------------- #
# Charts (base64 PNG data URIs)
# --------------------------------------------------------------------------- #
def _to_data_uri(figure) -> str:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=90, bbox_inches="tight")
    plt.close(figure)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def chart_monthly_trend(summary: ReportSummary) -> str:
    figure, axis = plt.subplots(figsize=(7.5, 3.5))
    monthly = summary.monthly
    axis.plot(monthly.index, monthly["revenue"], marker="o", linewidth=2,
              color="#4C72B0", label="Revenue")
    axis.plot(monthly.index, monthly["cost"], marker="s", linewidth=2,
              color="#C44E52", label="Cost")
    axis.fill_between(monthly.index, monthly["cost"], monthly["revenue"],
                      alpha=0.15, color="#55A868", label="Margin")
    axis.set_title("Monthly revenue vs cost")
    axis.set_ylabel("USD")
    axis.grid(alpha=0.3)
    axis.legend()
    figure.autofmt_xdate(rotation=45)
    return _to_data_uri(figure)


def chart_channel_share(summary: ReportSummary) -> str:
    figure, axis = plt.subplots(figsize=(5.5, 4.5))
    by_channel = summary.by_channel
    axis.pie(by_channel["revenue"], labels=by_channel.index,
             autopct="%1.1f%%", startangle=90,
             wedgeprops={"width": 0.42})
    axis.set_title("Revenue share by channel")
    return _to_data_uri(figure)


def chart_margin_by_channel(summary: ReportSummary) -> str:
    figure, axis = plt.subplots(figsize=(7.5, 3.5))
    by_channel = summary.by_channel
    axis.bar(by_channel.index, by_channel["margin_pct"],
             color=["#55A868" if v >= by_channel["margin_pct"].median()
                    else "#CCB974" for v in by_channel["margin_pct"]])
    axis.set_title("Margin % by channel")
    axis.set_ylabel("Margin %")
    axis.grid(axis="y", alpha=0.3)
    for i, value in enumerate(by_channel["margin_pct"]):
        axis.text(i, value, f" {value:.1f}%", ha="center", va="bottom")
    return _to_data_uri(figure)


def chart_monthly_growth(summary: ReportSummary) -> str:
    figure, axis = plt.subplots(figsize=(7.5, 3.2))
    monthly = summary.monthly
    growth = monthly["growth_pct"].fillna(0.0)
    colors = ["#55A868" if v >= 0 else "#C44E52" for v in growth]
    axis.bar(monthly.index, growth, color=colors)
    axis.axhline(0, color="black", linewidth=0.8)
    axis.set_title("Month-over-month revenue growth")
    axis.set_ylabel("Growth %")
    axis.grid(axis="y", alpha=0.3)
    figure.autofmt_xdate(rotation=45)
    return _to_data_uri(figure)


CHARTS = {
    "trend": (chart_monthly_trend, "Monthly revenue vs cost"),
    "share": (chart_channel_share, "Revenue share by channel"),
    "margin": (chart_margin_by_channel, "Margin % by channel"),
    "growth": (chart_monthly_growth, "Month-over-month growth"),
}


# --------------------------------------------------------------------------- #
# Report assembly
# --------------------------------------------------------------------------- #
def _money(value: float) -> str:
    return f"${value:,.0f}"


def render_markdown(summary: ReportSummary, title: str) -> str:
    """Markdown report with a stats table, channel table, and insights."""
    totals = summary.totals
    lines = [
        f"# {title}",
        "",
        f"_{int(totals['rows'])} rows - {int(totals['months'])} months - "
        f"{int(totals['channels'])} channels_",
        "",
        "## Key metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Revenue | {_money(totals['revenue'])} |",
        f"| Cost | {_money(totals['cost'])} |",
        f"| Margin | {_money(totals['margin'])} ({totals['margin_pct']:.1f}%) |",
        f"| Orders | {int(totals['orders']):,} |",
        f"| Avg order value | ${totals['aov']:.2f} |",
        f"| Best month | {summary.best_month} |",
        f"| Best channel | {summary.best_channel} |",
        "",
        "## By channel",
        "",
        "| Channel | Revenue | Share | Margin % | Orders |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for channel, row in summary.by_channel.iterrows():
        lines.append(
            f"| {channel} | {_money(row['revenue'])} | {row['share_pct']:.1f}% "
            f"| {row['margin_pct']:.1f}% | {int(row['orders']):,} |")

    lines += ["", "## Monthly totals", "",
              "| Month | Revenue | Growth |", "| --- | ---: | ---: |"]
    for month, row in summary.monthly.iterrows():
        growth = row["growth_pct"]
        growth_text = "-" if pd.isna(growth) else f"{growth:+.1f}%"
        lines.append(f"| {month} | {_money(row['revenue'])} | {growth_text} |")

    lines += ["", "## Insights", ""]
    lines += [f"- {note}" for note in summary.notes]
    lines.append("")
    return "\n".join(lines)


def render_html(summary: ReportSummary, title: str) -> str:
    """Self-contained HTML report with base64-embedded chart images."""
    totals = summary.totals
    esc = html.escape

    metric_cards = "".join(
        f'<div class="card"><div class="label">{label}</div>'
        f'<div class="value">{value}</div></div>'
        for label, value in (
            ("Revenue", _money(totals["revenue"])),
            ("Cost", _money(totals["cost"])),
            ("Margin", f'{_money(totals["margin"])} ({totals["margin_pct"]:.1f}%)'),
            ("Orders", f'{int(totals["orders"]):,}'),
            ("AOV", f'${totals["aov"]:.2f}'),
            ("Best month", summary.best_month),
        ))

    channel_rows = "".join(
        f"<tr><td>{esc(str(channel))}</td>"
        f"<td class='num'>{_money(row['revenue'])}</td>"
        f"<td class='num'>{row['share_pct']:.1f}%</td>"
        f"<td class='num'>{row['margin_pct']:.1f}%</td>"
        f"<td class='num'>{int(row['orders']):,}</td></tr>"
        for channel, row in summary.by_channel.iterrows())

    month_rows = ""
    for month, row in summary.monthly.iterrows():
        growth = row["growth_pct"]
        growth_class = "up" if (not pd.isna(growth) and growth >= 0) else "down"
        growth_text = "-" if pd.isna(growth) else f"{growth:+.1f}%"
        month_rows += (
            f"<tr><td>{esc(str(month))}</td>"
            f"<td class='num'>{_money(row['revenue'])}</td>"
            f"<td class='num {growth_class}'>{growth_text}</td></tr>")

    insight_items = "".join(f"<li>{esc(note)}</li>" for note in summary.notes)
    figure_blocks = "".join(
        f'<figure><img src="{chart_fn(summary)}" alt="{esc(caption)}">'
        f"<figcaption>{esc(caption)}</figcaption></figure>"
        for chart_fn, caption in CHARTS.values())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
  :root {{ --ink:#1f2937; --muted:#6b7280; --line:#e5e7eb; --accent:#4C72B0; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; color: var(--ink);
         margin: 0; padding: 2rem; background: #f9fafb; }}
  header {{ border-bottom: 3px solid var(--accent); padding-bottom: .75rem;
            margin-bottom: 1.5rem; }}
  h1 {{ margin: 0 0 .25rem; font-size: 1.7rem; }}
  .sub {{ color: var(--muted); font-size: .9rem; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 1.5rem; }}
  .card {{ background: white; border: 1px solid var(--line); border-radius: 8px;
           padding: .8rem 1.1rem; min-width: 150px; }}
  .card .label {{ font-size: .75rem; text-transform: uppercase;
                  letter-spacing: .05em; color: var(--muted); }}
  .card .value {{ font-size: 1.25rem; font-weight: 600; margin-top: .2rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
           gap: 1rem; margin-bottom: 1.5rem; }}
  figure {{ background: white; border: 1px solid var(--line); border-radius: 8px;
            margin: 0; padding: .75rem; }}
  figure img {{ width: 100%; height: auto; display: block; }}
  figcaption {{ font-size: .8rem; color: var(--muted); text-align: center;
                margin-top: .4rem; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           border: 1px solid var(--line); border-radius: 8px;
           overflow: hidden; margin-bottom: 1.5rem; }}
  th, td {{ padding: .55rem .8rem; border-bottom: 1px solid var(--line);
            font-size: .9rem; }}
  th {{ background: #f3f4f6; text-align: left; font-weight: 600; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr:last-child td {{ border-bottom: none; }}
  .up {{ color: #059669; }} .down {{ color: #dc2626; }}
  h2 {{ font-size: 1.1rem; margin: 1.75rem 0 .75rem; }}
  ul {{ background: white; border: 1px solid var(--line); border-radius: 8px;
        padding: 1rem 1rem 1rem 2.2rem; margin: 0; }}
  li {{ margin: .35rem 0; font-size: .92rem; }}
  footer {{ margin-top: 2rem; font-size: .8rem; color: var(--muted);
            border-top: 1px solid var(--line); padding-top: .75rem; }}
</style>
</head>
<body>
<header>
  <h1>{esc(title)}</h1>
  <div class="sub">{int(totals['rows'])} rows &middot;
    {int(totals['months'])} months &middot;
    {int(totals['channels'])} channels &middot;
    generated fully offline</div>
</header>
<section class="cards">{metric_cards}</section>
<section class="grid">{figure_blocks}</section>
<h2>By channel</h2>
<table>
  <thead><tr><th>Channel</th><th class="num">Revenue</th>
    <th class="num">Share</th><th class="num">Margin %</th>
    <th class="num">Orders</th></tr></thead>
  <tbody>{channel_rows}</tbody>
</table>
<h2>Monthly totals</h2>
<table>
  <thead><tr><th>Month</th><th class="num">Revenue</th>
    <th class="num">Growth</th></tr></thead>
  <tbody>{month_rows}</tbody>
</table>
<h2>Insights</h2>
<ul>{insight_items}</ul>
<footer>Report Generator &middot; Devender J &middot;
  https://github.com/JDevender007 &middot; charts embedded as base64 PNGs
  (no CDN, no network)</footer>
</body>
</html>
"""


def build_report(frame: pd.DataFrame, title: str) -> tuple[str, str]:
    """Return (html, markdown) reports for a validated frame."""
    summary = summarize(frame)
    return render_html(summary, title), render_markdown(summary, title)


def save_report(frame: pd.DataFrame, out_dir: str | Path,
                title: str) -> dict[str, Path]:
    """Write report.html and report.md into out_dir; return their paths."""
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    document, markdown = build_report(frame, title)

    html_path = target_dir / "report.html"
    md_path = target_dir / "report.md"
    html_path.write_text(document, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")

    if html_path.stat().st_size < 50_000:
        raise ReportError(f"HTML report too small: {html_path}")
    if md_path.stat().st_size == 0:
        raise ReportError(f"Markdown report empty: {md_path}")
    LOG.info("wrote %s (%d bytes) and %s (%d bytes)",
             html_path, html_path.stat().st_size,
             md_path, md_path.stat().st_size)
    return {"html": html_path, "markdown": md_path}


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "report_sample.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "output"
DEMO_TITLE = "Channel Performance Report - 2025"


def run_demo(out_dir: Path | None = None, quiet: bool = False) -> int:
    """Generate HTML + Markdown reports from the bundled sample - offline."""
    if not quiet:
        print("=" * 64)
        print(" REPORT GENERATOR - offline demo")
        print(" Bundled sample data; base64 charts; no CDN, no network.")
        print("=" * 64)

    if not DEMO_CSV.is_file():
        raise ReportError(f"bundled sample not found: {DEMO_CSV}")
    frame = load_data(DEMO_CSV)
    summary = summarize(frame)

    if not quiet:
        print(f"\nLoaded {len(frame)} rows from {DEMO_CSV.name}")
        print(f"Revenue {_money(summary.totals['revenue'])}  "
              f"margin {summary.totals['margin_pct']:.1f}%  "
              f"orders {int(summary.totals['orders']):,}")
        print("\nInsights:")
        for note in summary.notes:
            print(f"  - {note}")

    paths = save_report(frame, out_dir or DEFAULT_OUTPUT, DEMO_TITLE)
    html_path, md_path = paths["html"], paths["markdown"]
    document = html_path.read_text(encoding="utf-8")
    markdown = md_path.read_text(encoding="utf-8")

    # --- cross-checks the demo asserts ------------------------------------ #
    assert summary.totals["revenue"] == float(frame["revenue"].sum()), "revenue"
    assert summary.totals["orders"] == float(frame["orders"].sum()), "orders"
    assert summary.by_channel["revenue"].sum() == float(frame["revenue"].sum()), \
        "channel shares must partition total revenue"
    assert abs(summary.by_channel["share_pct"].sum() - 100) < 1e-6, "shares"
    assert int(summary.monthly["revenue"].sum()) == int(frame["revenue"].sum()), \
        "monthly totals must partition total revenue"

    # HTML: self-contained (base64 PNGs, no external resources)
    assert document.startswith("<!DOCTYPE html>"), "missing doctype"
    assert document.count("data:image/png;base64,") == len(CHARTS), \
        "every chart must be an embedded base64 PNG"
    assert "<script" not in document, "no scripts in a static report"
    assert not any(token in document for token in ('src="http', 'href="http',
                                                   'url(http', "cdn.plot")), \
        "no external resource references (footer URL is plain text)"
    for channel in summary.by_channel.index:
        assert channel in document, f"{channel} missing from HTML"
        assert channel in markdown, f"{channel} missing from Markdown"

    # Markdown: tables and insights present
    assert markdown.startswith("# "), "missing H1"
    assert "| Channel | Revenue |" in markdown, "channel table missing"
    assert "## Insights" in markdown
    assert all(note in markdown for note in summary.notes)

    # numbers appear in both formats
    assert _money(summary.totals["revenue"]) in document
    assert _money(summary.totals["revenue"]) in markdown

    if not quiet:
        print(f"\nWrote {html_path} ({html_path.stat().st_size:,} bytes)")
        print(f"Wrote {md_path} ({md_path.stat().st_size:,} bytes)")
        print(f"Cross-checks OK: totals partition {len(frame)} rows, "
              f"{len(CHARTS)} base64 charts embedded, no external references")
        print("Demo completed successfully.")
    return 0
