"""Interactive dashboard builder: plotly figure + self-contained offline HTML.

Loads a bundled monthly segment-performance CSV, computes KPIs, and builds
an interactive 2x2 dashboard (trend with range slider and metric switcher,
grouped bars, donut share, scatter with trend line). The saved HTML embeds
plotly.js inline, so it opens in any browser fully offline - no CDN, no
network, no server.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

LOG = logging.getLogger("dashboard")

REQUIRED_COLUMNS = ("month", "segment", "revenue", "cost", "orders")
METRICS = ("revenue", "cost", "orders")


class DashboardError(RuntimeError):
    """Raised for missing files, bad schemas, and unknown options."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_data(path: str | Path) -> pd.DataFrame:
    """Load the monthly segment CSV, validate it, return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise DashboardError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise DashboardError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise DashboardError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise DashboardError(f"no rows in {source.name}")

    frame = frame.copy()
    frame["month"] = frame["month"].astype(str).str.strip()
    if not frame["month"].str.match(r"\d{4}-\d{2}$").all():
        raise DashboardError("month values must look like YYYY-MM")

    frame["segment"] = frame["segment"].astype(str).str.strip()
    if frame["segment"].eq("").any() or frame["segment"].str.lower().eq("nan").any():
        raise DashboardError("empty segment value(s)")

    for column in ("revenue", "cost", "orders"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise DashboardError(f"column {column!r} contains non-numeric values")
        if (frame[column] < 0).any():
            raise DashboardError(f"column {column!r} must be non-negative")
        if column == "orders" and (frame[column] % 1 != 0).any():
            raise DashboardError("column 'orders' must be whole numbers")

    if frame.duplicated(subset=["month", "segment"]).any():
        raise DashboardError("duplicate (month, segment) rows")

    frame = frame.sort_values(["segment", "month"]).reset_index(drop=True)
    LOG.info("loaded %d rows from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# KPIs
# --------------------------------------------------------------------------- #
def compute_kpis(frame: pd.DataFrame) -> dict[str, Any]:
    """Headline metrics over a validated frame."""
    total_revenue = float(frame["revenue"].sum())
    total_cost = float(frame["cost"].sum())
    total_orders = int(frame["orders"].sum())
    margin = total_revenue - total_cost

    monthly = frame.groupby("month")["revenue"].sum()
    first, last = float(monthly.iloc[0]), float(monthly.iloc[-1])
    growth = (last - first) / first * 100 if first else 0.0

    by_segment = frame.groupby("segment")["revenue"].sum()
    return {
        "rows": int(len(frame)),
        "segments": int(frame["segment"].nunique()),
        "months": int(frame["month"].nunique()),
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "margin": round(margin, 2),
        "margin_pct": round(margin / total_revenue * 100, 2) if total_revenue else 0.0,
        "total_orders": total_orders,
        "aov": round(total_revenue / total_orders, 2) if total_orders else 0.0,
        "revenue_growth_pct": round(growth, 2),
        "best_segment": str(by_segment.idxmax()),
        "best_month": str(monthly.idxmax()),
    }


def render_kpis(kpis: dict[str, Any]) -> str:
    """Aligned text block of KPIs for the CLI."""
    lines = [
        "DASHBOARD KPIs",
        "=" * 56,
        f"  {'Total revenue':<26} ${kpis['total_revenue']:>13,.0f}",
        f"  {'Total cost':<26} ${kpis['total_cost']:>13,.0f}",
        f"  {'Margin':<26} ${kpis['margin']:>13,.0f}  ({kpis['margin_pct']}%)",
        f"  {'Orders':<26} {kpis['total_orders']:>13,}",
        f"  {'Avg order value':<26} ${kpis['aov']:>13,.2f}",
        f"  {'Revenue growth (first->last month)':<26} "
        f"{kpis['revenue_growth_pct']:>+12.1f}%",
        f"  {'Best segment':<26} {kpis['best_segment']:>13}",
        f"  {'Best month':<26} {kpis['best_month']:>13}",
        f"  {'Coverage':<26} {kpis['rows']} rows, "
        f"{kpis['segments']} segs x {kpis['months']} months",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Figure construction
# --------------------------------------------------------------------------- #
def _kpi_header(kpis: dict[str, Any]) -> str:
    return (
        f"<b>Segment Performance Dashboard</b><br>"
        f"revenue ${kpis['total_revenue']:,.0f} - margin {kpis['margin_pct']}% - "
        f"growth {kpis['revenue_growth_pct']:+.1f}%<br>"
        f"orders {kpis['total_orders']:,} - AOV ${kpis['aov']:,.0f} - "
        f"best: {kpis['best_segment']} / {kpis['best_month']}"
    )


def build_dashboard(frame: pd.DataFrame) -> go.Figure:
    """Build the interactive 2x2 dashboard figure (metric switcher included)."""
    kpis = compute_kpis(frame)
    segments = sorted(frame["segment"].unique())
    months = sorted(frame["month"].unique())

    figure = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Monthly trend (drag to zoom, slide to range)",
                        "Revenue vs cost by segment",
                        "Revenue share by segment",
                        "Revenue vs orders"),
        specs=[[{"type": "xy"}, {"type": "xy"}],
               [{"type": "domain"}, {"type": "xy"}]],
    )

    # --- line: 4 segments x 3 metrics (12 traces, metric switcher) -------- #
    pivot_table = frame.pivot_table(index="month", columns="segment",
                                    values=list(METRICS), aggfunc="sum")
    colors = {"revenue": "#636EFA", "cost": "#EF553B", "orders": "#00CC96"}
    line_trace_slots: dict[str, list[int]] = {m: [] for m in METRICS}
    for metric in METRICS:
        for segment in segments:
            values = pivot_table[(metric, segment)].reindex(months)
            default_metric = metric == "revenue"
            figure.add_trace(
                go.Scatter(
                    x=months, y=values, mode="lines+markers", name=segment,
                    legendgroup=segment, showlegend=default_metric,
                    visible=default_metric,
                    line={"width": 2.2, "color": colors[metric]},
                    hovertemplate="%{x}<br>%{y:,.0f}<extra>" + segment + "</extra>",
                ),
                row=1, col=1,
            )
            line_trace_slots[metric].append(len(figure.data) - 1)

    # --- bar: grouped revenue vs cost ------------------------------------- #
    summary = frame.groupby("segment")[["revenue", "cost"]].sum().reindex(segments)
    figure.add_trace(go.Bar(x=segments, y=summary["revenue"], name="Revenue",
                            marker_color="#636EFA"), row=1, col=2)
    figure.add_trace(go.Bar(x=segments, y=summary["cost"], name="Cost",
                            marker_color="#EF553B"), row=1, col=2)

    # --- donut: revenue share --------------------------------------------- #
    share = frame.groupby("segment")["revenue"].sum().reindex(segments)
    figure.add_trace(go.Pie(labels=segments, values=share, hole=0.45,
                            showlegend=False,
                            textinfo="label+percent",
                            hovertemplate="%{label}: $%{value:,.0f}<extra></extra>"),
                     row=2, col=1)

    # --- scatter: revenue vs orders with least-squares trend --------------- #
    x = frame["orders"].astype(float).values
    y = frame["revenue"].astype(float).values
    slope, intercept = np.polyfit(x, y, 1)
    labels = [f"{seg} {mon}" for seg, mon in
              zip(frame["segment"], frame["month"])]
    figure.add_trace(go.Scatter(x=x, y=y, mode="markers", name="observations",
                                marker={"size": 9, "opacity": 0.65,
                                        "color": "#AB63FA"},
                                text=labels,
                                hovertemplate="%{text}<br>orders %{x:,.0f}"
                                              "<br>revenue $%{y:,.0f}"
                                              "<extra></extra>"),
                     row=2, col=2)
    figure.add_trace(go.Scatter(x=[float(x.min()), float(x.max())],
                                y=[slope * float(x.min()) + intercept,
                                   slope * float(x.max()) + intercept],
                                mode="lines", name="trend",
                                line={"color": "black", "dash": "dash"},
                                showlegend=False),
                     row=2, col=2)

    # --- metric switcher (updates the 12 line traces) --------------------- #
    total_traces = len(figure.data)
    line_slots = line_trace_slots["revenue"] + line_trace_slots["cost"] \
        + line_trace_slots["orders"]
    buttons = []
    for metric in METRICS:
        visible = [False] * total_traces
        for slot in line_trace_slots[metric]:
            visible[slot] = True
        for slot in range(total_traces):
            if slot not in line_slots:
                visible[slot] = True
        buttons.append(dict(label=metric.capitalize(), method="update",
                            args=[{"visible": visible}]))

    figure.update_layout(
        title={"text": _kpi_header(kpis), "x": 0.0, "y": 0.995,
               "xanchor": "left", "yanchor": "top"},
        updatemenus=[dict(buttons=buttons, direction="down", showactive=True,
                          x=1.0, xanchor="right", y=0.995, yanchor="top")],
        legend_title="Segment",
        template="plotly_white",
        height=760,
    )
    figure.update_xaxes(title_text="Month", row=1, col=1)
    figure.update_yaxes(title_text="Value", row=1, col=1)
    figure.update_xaxes(rangeslider_visible=True, row=1, col=1)
    figure.update_yaxes(title_text="USD", row=2, col=2)
    figure.update_xaxes(title_text="Orders", row=2, col=2)
    return figure


def figure_to_html(figure: go.Figure) -> str:
    """Self-contained HTML (plotly.js embedded inline, no CDN)."""
    return figure.to_html(full_html=True, include_plotlyjs=True)


def save_dashboard(frame: pd.DataFrame, out_path: str | Path,
                   figure: go.Figure | None = None) -> Path:
    """Build the dashboard and write a self-contained HTML file."""
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure = figure if figure is not None else build_dashboard(frame)
    html = figure_to_html(figure)
    target.write_text(html, encoding="utf-8")
    if not target.is_file() or target.stat().st_size < 100_000:
        raise DashboardError(f"failed to write a complete dashboard to {target}")
    LOG.info("wrote dashboard -> %s (%d bytes)", target, target.stat().st_size)
    return target


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "dashboard_sample.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "output"


def run_demo(out_dir: Path | None = None, quiet: bool = False,
             note: str | None = None) -> int:
    """Build the bundled dashboard - fully offline, self-contained HTML."""
    if not quiet:
        print("=" * 60)
        print(" INTERACTIVE DASHBOARD - offline demo")
        print(" Bundled data; plotly.js embedded inline; no CDN, no server.")
        print("=" * 60)

    if not DEMO_CSV.is_file():
        raise DashboardError(f"bundled sample not found: {DEMO_CSV}")
    frame = load_data(DEMO_CSV)
    target = (out_dir or DEFAULT_OUTPUT) / "dashboard.html"

    kpis = compute_kpis(frame)
    if not quiet:
        print(f"\nLoaded {len(frame)} rows from {DEMO_CSV.name}\n")
        print(render_kpis(kpis))

    figure = build_dashboard(frame)
    path = save_dashboard(frame, target, figure=figure)
    html = path.read_text(encoding="utf-8")

    # --- cross-checks the demo asserts ------------------------------------ #
    assert kpis["total_revenue"] == float(frame["revenue"].sum()), "revenue KPI"
    assert kpis["margin"] == round(
        float(frame["revenue"].sum() - frame["cost"].sum()), 2), "margin KPI"
    expected_orders = int(frame["orders"].sum())
    assert kpis["total_orders"] == expected_orders, "orders KPI"
    monthly = frame.groupby("month")["revenue"].sum()
    expected_growth = (float(monthly.iloc[-1]) - float(monthly.iloc[0])) \
        / float(monthly.iloc[0]) * 100
    assert abs(kpis["revenue_growth_pct"] - expected_growth) < 0.01, "growth KPI"

    assert len(figure.data) == 17, "12 lines + bar x2 + pie + scatter x2"
    assert figure.layout.updatemenus and \
        len(figure.layout.updatemenus[0].buttons) == 3, "metric switcher"
    visible_default = sum(1 for t in figure.data if t.visible is not False)
    assert visible_default == 9, "4 revenue lines + bar x2 + pie + scatter x2"

    # document-level checks: the page must not load any remote resource
    # (a stray src="https://..." string inside plotly.js's mapbox dead code
    # is harmless - it never executes without mapbox traces)
    assert "<script src=" not in html, "must not load external scripts"
    assert not re.search(r"<link[^>]*href=[\"']https?://", html), \
        "must not load external stylesheets"
    assert not re.search(r"<(?:img|iframe)[^>]*src=[\"']https?://", html), \
        "must not embed remote images/iframes"
    assert "plotly" in html.lower(), "plotly.js missing"
    assert path.stat().st_size > 1_000_000, "embedded plotly.js should exceed 1 MB"
    for segment in frame["segment"].unique():
        assert segment in html, f"{segment} missing from dashboard"

    if not quiet:
        try:
            shown = path.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            shown = path
        print(f"\nWrote {shown} ({path.stat().st_size:,} bytes, self-contained)")
        if note:
            print(note)
        print(f"Cross-checks OK: KPIs match the frame, {len(figure.data)} traces, "
              f"3-button metric switcher, self-contained HTML (no remote resources)")
        print("\nDemo completed successfully.")
    return 0
