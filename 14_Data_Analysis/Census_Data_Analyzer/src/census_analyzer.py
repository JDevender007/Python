"""Census data analysis: loading, validation, and demographic reporting — offline.

Reads a CSV of regional census indicators, validates it, and produces a
CensusReport with population and household totals, population/household
weighted indicator means, state-level aggregation, urban/rural splits,
indicator correlations, income rankings, and an inequality ratio (income
IQR). Local file analysis only - no network, no APIs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

LOG = logging.getLogger("census.analyzer")

REQUIRED_COLUMNS = ("region_id", "region_name", "state", "population",
                    "households", "median_household_income", "poverty_rate",
                    "unemployment_rate", "bachelor_degree_pct", "median_age",
                    "urban_population_pct")
RATE_COLUMNS = ("poverty_rate", "unemployment_rate", "bachelor_degree_pct",
                "urban_population_pct")
CORR_COLUMNS = ("median_household_income", "poverty_rate",
                "bachelor_degree_pct", "unemployment_rate",
                "median_age", "urban_population_pct")
INCOME_MIN, INCOME_MAX = 10_000, 500_000


class CensusError(RuntimeError):
    """Raised for missing files, bad schemas, and out-of-range values."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_census(path: str | Path) -> pd.DataFrame:
    """Load a census CSV, validate it, and return a cleaned DataFrame."""
    source = Path(path)
    if not source.is_file():
        raise CensusError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise CensusError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise CensusError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise CensusError(f"no rows in {source.name}")

    frame = frame.copy()
    for column in ("region_id", "region_name", "state"):
        values = frame[column].astype(str).str.strip()
        if values.eq("").any() or values.str.lower().eq("nan").any():
            raise CensusError(f"empty {column!r} value(s)")
        frame[column] = values
    if frame["region_id"].duplicated().any():
        raise CensusError("duplicate region_id value(s)")

    for column in ("population", "households"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise CensusError(f"column {column!r} contains non-numeric values")
        if (frame[column] < 1).any() or (frame[column] % 1 != 0).any():
            raise CensusError(f"column {column!r} must be positive whole numbers")
        frame[column] = frame[column].astype(int)
    if (frame["households"] > frame["population"]).any():
        raise CensusError("households cannot exceed population")

    frame["median_household_income"] = pd.to_numeric(
        frame["median_household_income"], errors="coerce")
    if frame["median_household_income"].isna().any():
        raise CensusError("column 'median_household_income' contains non-numeric values")
    if not frame["median_household_income"].between(INCOME_MIN, INCOME_MAX).all():
        raise CensusError(f"median_household_income outside {INCOME_MIN}..{INCOME_MAX}")

    for column in RATE_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise CensusError(f"column {column!r} contains non-numeric values")
        if not frame[column].between(0, 1).all():
            raise CensusError(f"column {column!r} must be a fraction in 0..1")

    frame["median_age"] = pd.to_numeric(frame["median_age"], errors="coerce")
    if frame["median_age"].isna().any():
        raise CensusError("column 'median_age' contains non-numeric values")
    if not frame["median_age"].between(18, 100).all():
        raise CensusError("median_age outside 18..100")

    frame = frame.sort_values("state").reset_index(drop=True)
    LOG.info("loaded %d regions from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Report model
# --------------------------------------------------------------------------- #
@dataclass
class CensusReport:
    """Aggregated view over a validated census DataFrame."""

    frame: pd.DataFrame
    regions: int = 0
    states: int = 0
    population_total: int = 0
    households_total: int = 0
    indicators: dict[str, float] = field(default_factory=dict)
    poverty_population: int = 0
    by_state: pd.DataFrame = field(default_factory=pd.DataFrame)
    urban_split: dict[str, dict[str, float]] = field(default_factory=dict)
    correlations: pd.DataFrame = field(default_factory=pd.DataFrame)
    top_income: pd.DataFrame = field(default_factory=pd.DataFrame)
    top_poverty: pd.DataFrame = field(default_factory=pd.DataFrame)
    income_iqr_ratio: float = 0.0

    @property
    def avg_household_size(self) -> float:
        return round(self.population_total / self.households_total, 2) \
            if self.households_total else 0.0

    @property
    def poverty_share_pct(self) -> float:
        return round(self.poverty_population / self.population_total * 100, 2) \
            if self.population_total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "regions": self.regions,
            "states": self.states,
            "population_total": self.population_total,
            "households_total": self.households_total,
            "avg_household_size": self.avg_household_size,
            "poverty_population": self.poverty_population,
            "poverty_share_pct": self.poverty_share_pct,
            "indicators": {k: round(v, 4) for k, v in self.indicators.items()},
            "by_state": [
                {"state": str(idx), **{str(k): (round(float(v), 4)
                                                if isinstance(v, float) else int(v))
                                       for k, v in row.items()}}
                for idx, row in self.by_state.iterrows()
            ],
            "urban_split": {k: {kk: round(vv, 4) for kk, vv in v.items()}
                            for k, v in self.urban_split.items()},
            "correlation": {
                a: {b: round(float(v), 4) for b, v in row.items()}
                for a, row in self.correlations.to_dict("index").items()
            },
            "top_income": [
                {"region": str(idx), "region_id": str(row["region_id"]),
                 "income": int(row["median_household_income"]),
                 "state": str(row["state"])}
                for idx, row in self.top_income.iterrows()
            ],
            "top_poverty": [
                {"region": str(idx), "region_id": str(row["region_id"]),
                 "poverty_rate": round(float(row["poverty_rate"]), 4),
                 "state": str(row["state"])}
                for idx, row in self.top_poverty.iterrows()
            ],
            "income_iqr_ratio": round(self.income_iqr_ratio, 3),
        }


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def weighted_mean(frame: pd.DataFrame, value: str, weight: str) -> float:
    """Weighted mean of `value` by `weight` (both validated columns)."""
    for column in (value, weight):
        if column not in frame.columns:
            raise CensusError(f"unknown column {column!r}")
    if frame.empty:
        raise CensusError("no rows to average")
    total_weight = float(frame[weight].sum())
    if total_weight <= 0:
        raise CensusError(f"total weight for {weight!r} must be positive")
    return float((frame[value] * frame[weight]).sum() / total_weight)


def analyze(frame: pd.DataFrame, top: int = 5) -> CensusReport:
    """Aggregate a validated frame into a CensusReport."""
    if top < 1:
        raise CensusError("top must be >= 1")

    report = CensusReport(frame=frame)
    report.regions = len(frame)
    report.states = int(frame["state"].nunique())
    report.population_total = int(frame["population"].sum())
    report.households_total = int(frame["households"].sum())
    report.poverty_population = int(
        (frame["poverty_rate"] * frame["population"]).sum().round())

    # weighted (correct for populations) vs unweighted (naive) averages
    report.indicators = {
        "median_income_weighted": weighted_mean(
            frame, "median_household_income", "households"),
        "median_income_unweighted": float(frame["median_household_income"].mean()),
        "poverty_rate_weighted": weighted_mean(frame, "poverty_rate", "population"),
        "poverty_rate_unweighted": float(frame["poverty_rate"].mean()),
        "bachelor_pct_weighted": weighted_mean(
            frame, "bachelor_degree_pct", "population"),
        "unemployment_weighted": weighted_mean(
            frame, "unemployment_rate", "population"),
        "urban_pct_weighted": weighted_mean(
            frame, "urban_population_pct", "population"),
        "median_age_unweighted": float(frame["median_age"].mean()),
    }

    # state-level aggregation (population/household weighted)
    report.by_state = frame.groupby("state").apply(
        lambda g: pd.Series({
            "regions": len(g),
            "population": int(g["population"].sum()),
            "households": int(g["households"].sum()),
            "median_income": weighted_mean(g, "median_household_income", "households"),
            "poverty_rate": weighted_mean(g, "poverty_rate", "population"),
            "urban_pct": weighted_mean(g, "urban_population_pct", "population"),
        }),
        include_groups=False,
    ).sort_values("population", ascending=False)

    # urban vs rural regions (urban majority population)
    urban_mask = frame["urban_population_pct"] >= 0.5
    for label, mask in (("urban", urban_mask), ("rural", ~urban_mask)):
        subset = frame[mask]
        report.urban_split[label] = {
            "regions": float(len(subset)),
            "population": float(subset["population"].sum()),
            "median_income": (weighted_mean(subset, "median_household_income", "households")
                              if len(subset) else 0.0),
            "poverty_rate": (weighted_mean(subset, "poverty_rate", "population")
                             if len(subset) else 0.0),
        }

    report.correlations = frame[list(CORR_COLUMNS)].corr().round(4)

    report.top_income = (frame.sort_values("median_household_income", ascending=False)
                         .head(top).set_index("region_name"))
    report.top_poverty = (frame.sort_values("poverty_rate", ascending=False)
                          .head(top).set_index("region_name"))
    q1, q3 = frame["median_household_income"].quantile([0.25, 0.75])
    report.income_iqr_ratio = float(q3 / q1) if q1 > 0 else 0.0

    LOG.info("analysed %d regions across %d states", report.regions, report.states)
    return report


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_report(report: CensusReport) -> str:
    """Human-readable census report used by the CLI and demo."""
    ind = report.indicators
    lines = [
        "CENSUS ANALYSIS",
        "=" * 70,
        f"Regions    : {report.regions} across {report.states} states",
        f"Population : {report.population_total:,}   "
        f"households {report.households_total:,}   "
        f"avg size {report.avg_household_size}",
        f"Income     : weighted ${ind['median_income_weighted']:,.0f}   "
        f"unweighted ${ind['median_income_unweighted']:,.0f}   "
        f"(IQR ratio {report.income_iqr_ratio:.2f})",
        f"Poverty    : weighted {ind['poverty_rate_weighted'] * 100:.1f}%   "
        f"unweighted {ind['poverty_rate_unweighted'] * 100:.1f}%   "
        f"people in poverty ~{report.poverty_population:,} "
        f"({report.poverty_share_pct}%)",
        f"Other      : bachelor {ind['bachelor_pct_weighted'] * 100:.1f}%   "
        f"unemployment {ind['unemployment_weighted'] * 100:.1f}%   "
        f"urban {ind['urban_pct_weighted'] * 100:.1f}%   "
        f"median age {ind['median_age_unweighted']:.1f}",
        "",
        "By state (weighted):",
        f"  {'state':<12}{'regions':>8}{'population':>13}{'income':>10}"
        f"{'poverty':>9}{'urban':>8}",
    ]
    for state, row in report.by_state.iterrows():
        lines.append(
            f"  {str(state):<12}{int(row['regions']):>8}{int(row['population']):>13,}"
            f"{row['median_income']:>10,.0f}{row['poverty_rate'] * 100:>8.1f}%"
            f"{row['urban_pct'] * 100:>7.1f}%"
        )

    lines += ["", "Urban vs rural regions:"]
    for label, stats in report.urban_split.items():
        lines.append(f"  {label:<6} {int(stats['regions']):>3} regions  "
                     f"pop {int(stats['population']):>11,}  "
                     f"income ${stats['median_income']:>9,.0f}  "
                     f"poverty {stats['poverty_rate'] * 100:4.1f}%")

    lines += ["", "Indicator correlation:"]
    names = list(report.correlations.columns)
    short = [n.replace("_pct", "").replace("median_household_income", "income")
             .replace("poverty_rate", "poverty").replace("unemployment_rate", "unemp")
             .replace("median_age", "age").replace("urban_population_pct", "urban")
             .replace("bachelor_degree_pct", "bach") for n in names]
    lines.append("        " + "".join(f"{s:>8}" for s in short))
    for name, row in report.correlations.iterrows():
        label = short[names.index(name)]
        lines.append(f"  {label:<6}" + "".join(f"{row[c]:>8.3f}" for c in names))

    lines += ["", "Highest incomes:"]
    for idx, row in report.top_income.iterrows():
        lines.append(f"  {str(idx):<28} ${int(row['median_household_income']):>8,}  "
                     f"({row['state']})")
    lines += ["", "Highest poverty:"]
    for idx, row in report.top_poverty.iterrows():
        lines.append(f"  {str(idx):<28} {float(row['poverty_rate']) * 100:>6.1f}%  "
                     f"({row['state']})")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "census_sample.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Analyse the bundled sample census data — fully offline."""
    print("=" * 70)
    print(" CENSUS DATA ANALYZER - offline demo")
    print(" Bundled synthetic indicators; no network, no APIs.")
    print("=" * 70)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise CensusError(f"bundled sample not found: {source}")

    frame = load_census(source)
    print(f"\nLoaded {len(frame)} regions across "
          f"{frame['state'].nunique()} states from {source.name}")

    report = analyze(frame, top=5)
    print()
    print(render_report(report))

    # --- cross-checks the demo asserts ---------------------------------- #
    assert report.population_total == int(frame["population"].sum()), \
        "population total mismatch"
    assert report.households_total == int(frame["households"].sum())
    assert int(report.by_state["population"].sum()) == report.population_total, \
        "state populations must partition the total"
    assert report.by_state["regions"].sum() == report.regions
    assert sum(v["regions"] for v in report.urban_split.values()) == report.regions, \
        "urban + rural must cover every region"
    assert report.poverty_population <= report.population_total, \
        "poverty headcount cannot exceed population"
    # weighted mean must sit inside the observed range
    low, high = frame["median_household_income"].min(), frame["median_household_income"].max()
    assert low <= report.indicators["median_income_weighted"] <= high, \
        "weighted income outside observed range"
    corr = report.correlations
    assert ((corr.values >= -1.0001) & (corr.values <= 1.0001)).all()
    assert abs(float(corr.values.diagonal().min()) - 1.0) < 1e-6
    assert ((corr.values - corr.values.T) ** 2).max() < 1e-6, "corr not symmetric"
    assert report.income_iqr_ratio >= 1.0, "Q3/Q1 must be >= 1"
    print(f"\nCross-checks OK: state populations partition "
          f"{report.population_total:,} people "
          f"(poverty ~{report.poverty_population:,}, "
          f"weighted income ${report.indicators['median_income_weighted']:,.0f})")

    # weighted vs unweighted tells the story of aggregation
    delta = report.indicators["median_income_weighted"] - \
        report.indicators["median_income_unweighted"]
    print(f"Weighted vs unweighted income: {delta:+,.0f} "
          f"(households weigh rich/poor regions correctly)")
    print("\nDemo completed successfully.")
    return 0
