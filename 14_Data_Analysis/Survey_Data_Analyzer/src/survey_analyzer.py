"""Survey response analysis: loading, validation, and reporting — offline.

Reads a CSV of survey responses, validates it, and produces a SurveyReport
with response counts, Likert distributions, top/bottom-box analysis, NPS,
group comparisons (department / gender / remote), and a satisfaction
cross-tabulation. Local file analysis only — no network, no APIs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

LOG = logging.getLogger("survey.analyzer")

REQUIRED_COLUMNS = ("response_id", "date", "department", "gender", "age",
                    "tenure_years", "satisfaction", "recommend_score", "remote")
GROUP_COLUMNS = ("department", "gender", "remote")
LIKERT_MIN, LIKERT_MAX = 1, 5
NPS_MIN, NPS_MAX = 1, 10
AGE_MIN, AGE_MAX = 16, 120

SAT_BUCKETS = {"Low (1-2)": (1, 2), "Mid (3)": (3, 3), "High (4-5)": (4, 5)}


class SurveyError(RuntimeError):
    """Raised for missing files, bad schemas, and out-of-range values."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_survey(path: str | Path) -> pd.DataFrame:
    """Load a survey CSV, validate it, and return a cleaned DataFrame."""
    source = Path(path)
    if not source.is_file():
        raise SurveyError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise SurveyError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SurveyError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise SurveyError(f"no rows in {source.name}")

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if frame["date"].isna().any():
        raise SurveyError("unparseable date value(s)")

    ids = frame["response_id"].astype(str).str.strip()
    if ids.eq("").any() or ids.str.lower().eq("nan").any():
        raise SurveyError("empty response_id value(s)")
    if frame["response_id"].duplicated().any():
        raise SurveyError("duplicate response_id value(s)")

    for column in ("department", "gender", "remote"):
        values = frame[column].astype(str).str.strip()
        if values.eq("").any() or values.str.lower().eq("nan").any():
            raise SurveyError(f"empty {column!r} value(s)")
        frame[column] = values

    for column, low, high in (("age", AGE_MIN, AGE_MAX),
                              ("tenure_years", 0, AGE_MAX),
                              ("satisfaction", LIKERT_MIN, LIKERT_MAX),
                              ("recommend_score", NPS_MIN, NPS_MAX)):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise SurveyError(f"column {column!r} contains non-numeric values")
        if not frame[column].between(low, high).all():
            raise SurveyError(f"column {column!r} outside {low}..{high}")

    for column in ("age", "satisfaction", "recommend_score"):
        if (frame[column] % 1 != 0).any():
            raise SurveyError(f"column {column!r} must be whole numbers")
    frame["age"] = frame["age"].astype(int)
    frame["satisfaction"] = frame["satisfaction"].astype(int)
    frame["recommend_score"] = frame["recommend_score"].astype(int)

    frame = frame.sort_values("date").reset_index(drop=True)
    LOG.info("loaded %d responses from %s", len(frame), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Report model
# --------------------------------------------------------------------------- #
@dataclass
class SurveyReport:
    """Aggregated view over a validated survey DataFrame."""

    frame: pd.DataFrame
    n_responses: int = 0
    date_min: str = ""
    date_max: str = ""
    satisfaction: dict[str, float] = field(default_factory=dict)
    satisfaction_dist: dict[int, int] = field(default_factory=dict)
    recommend: dict[str, float] = field(default_factory=dict)
    age: dict[str, float] = field(default_factory=dict)
    by_group: dict[str, pd.DataFrame] = field(default_factory=dict)
    crosstab: pd.DataFrame = field(default_factory=pd.DataFrame)
    remote_split: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_responses": self.n_responses,
            "date_range": [self.date_min, self.date_max],
            "satisfaction": {k: round(v, 4) for k, v in self.satisfaction.items()},
            "satisfaction_dist": {str(k): v for k, v in self.satisfaction_dist.items()},
            "recommend": {k: round(v, 4) for k, v in self.recommend.items()},
            "age": {k: round(v, 4) for k, v in self.age.items()},
            "by_department": _records(self.by_group["department"]),
            "by_gender": _records(self.by_group["gender"]),
            "crosstab_pct": _records(self.crosstab),
            "remote_split": {k: {kk: round(vv, 4) for kk, vv in v.items()}
                             for k, v in self.remote_split.items()},
        }


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    for idx, row in frame.iterrows():
        record = {"name": str(idx)}
        for key, value in row.items():
            record[str(key)] = round(float(value), 2) if isinstance(value, float) \
                else int(value)
        records.append(record)
    return records


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def nps_scores(values: pd.Series) -> dict[str, float]:
    """Net Promoter Score: %promoters(9-10) - %detractors(1-6), on 1-10."""
    total = len(values)
    if total == 0:
        raise SurveyError("no responses for NPS")
    promoters = int((values >= 9).sum())
    detractors = int((values <= 6).sum())
    passives = total - promoters - detractors
    return {
        "nps": round((promoters - detractors) / total * 100, 1),
        "promoter_pct": round(promoters / total * 100, 1),
        "passive_pct": round(passives / total * 100, 1),
        "detractor_pct": round(detractors / total * 100, 1),
    }


def analyze(frame: pd.DataFrame, group: str = "department") -> SurveyReport:
    """Aggregate a validated frame into a SurveyReport."""
    if group not in GROUP_COLUMNS:
        raise SurveyError(f"unknown group {group!r} (choose {', '.join(GROUP_COLUMNS)})")

    report = SurveyReport(frame=frame)
    report.n_responses = len(frame)
    report.date_min = str(frame["date"].min().date())
    report.date_max = str(frame["date"].max().date())

    # --- satisfaction ---------------------------------------------------- #
    sat = frame["satisfaction"]
    dist = sat.value_counts().sort_index()
    report.satisfaction_dist = {int(k): int(v) for k, v in dist.items()}
    top_box = float((sat >= 4).mean() * 100)
    bottom_box = float((sat <= 2).mean() * 100)
    report.satisfaction = {
        "mean": float(sat.mean()),
        "median": float(sat.median()),
        "std": float(sat.std(ddof=1)) if len(sat) > 1 else 0.0,
        "top_box_pct": top_box,       # 4-5
        "bottom_box_pct": bottom_box,  # 1-2
        "net_top_box_pct": top_box - bottom_box,
    }

    # --- recommendation (NPS) ------------------------------------------- #
    report.recommend = nps_scores(frame["recommend_score"])
    report.recommend["mean"] = float(frame["recommend_score"].mean())

    # --- demographics ---------------------------------------------------- #
    report.age = {
        "mean": float(frame["age"].mean()),
        "median": float(frame["age"].median()),
        "min": int(frame["age"].min()),
        "max": int(frame["age"].max()),
        "mean_tenure_years": float(frame["tenure_years"].mean()),
    }

    # --- group comparisons ---------------------------------------------- #
    for column in GROUP_COLUMNS:
        table = frame.groupby(column).agg(
            responses=("response_id", "count"),
            mean_satisfaction=("satisfaction", "mean"),
            mean_recommend=("recommend_score", "mean"),
            top_box_pct=("satisfaction", lambda s: float((s >= 4).mean() * 100)),
        ).sort_values("responses", ascending=False)
        table["mean_satisfaction"] = table["mean_satisfaction"].round(2)
        table["mean_recommend"] = table["mean_recommend"].round(2)
        table["top_box_pct"] = table["top_box_pct"].round(1)
        report.by_group[column] = table

    # --- satisfaction bucket x group crosstab (row %) -------------------- #
    bucket = pd.Series(
        [f"{name}" for value in frame["satisfaction"]
         for name, (lo, hi) in SAT_BUCKETS.items() if lo <= value <= hi],
        index=frame.index, name="satisfaction_bucket",
    )
    counts = pd.crosstab(bucket, frame[group])
    pct = counts.div(counts.sum(axis=1), axis=0) * 100
    # logical Low -> Mid -> High order; drop buckets with no responses
    report.crosstab = pct.reindex(index=list(SAT_BUCKETS)).dropna(how="all").round(2)

    # --- remote split ----------------------------------------------------- #
    for value, subset in frame.groupby("remote"):
        report.remote_split[str(value)] = {
            "responses": int(len(subset)),
            "mean_satisfaction": round(float(subset["satisfaction"].mean()), 2),
            "mean_recommend": round(float(subset["recommend_score"].mean()), 2),
        }

    LOG.info("analysed %d responses grouped by %s", report.n_responses, group)
    return report


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_report(report: SurveyReport, group: str = "department") -> str:
    """Human-readable survey report used by the CLI and demo."""
    sat = report.satisfaction
    rec = report.recommend
    lines = [
        "SURVEY ANALYSIS",
        "=" * 68,
        f"Responses   : {report.n_responses:,}   "
        f"({report.date_min} .. {report.date_max})",
        f"Satisfaction: mean {sat['mean']:.2f}  median {sat['median']:.0f}  "
        f"std {sat['std']:.2f}",
        f"Top box 4-5 : {sat['top_box_pct']:.1f}%   "
        f"bottom box 1-2: {sat['bottom_box_pct']:.1f}%   "
        f"net: {sat['net_top_box_pct']:+.1f} pts",
        f"NPS         : {rec['nps']:+.0f}  "
        f"(promoters {rec['promoter_pct']:.0f}% / "
        f"passives {rec['passive_pct']:.0f}% / "
        f"detractors {rec['detractor_pct']:.0f}%)",
        f"Age         : mean {report.age['mean']:.1f}  "
        f"range {report.age['min']}..{report.age['max']}  "
        f"tenure {report.age['mean_tenure_years']:.1f} yr",
        "",
        "Satisfaction distribution:",
    ]
    for score in range(LIKERT_MIN, LIKERT_MAX + 1):
        count = report.satisfaction_dist.get(score, 0)
        share = count / report.n_responses * 100
        bar = "#" * max(1, round(share / 2)) if count else ""
        lines.append(f"  {score}  {count:>4} ({share:5.1f}%)  {bar}")

    lines += ["", f"By {group}:"]
    table = report.by_group[group]
    lines.append(f"  {group:<16}{'resp':>6}{'mean sat':>10}{'mean rec':>10}{'top box':>9}")
    for name, row in table.iterrows():
        lines.append(f"  {str(name):<16}{int(row['responses']):>6}"
                     f"{row['mean_satisfaction']:>10.2f}"
                     f"{row['mean_recommend']:>10.2f}"
                     f"{row['top_box_pct']:>8.1f}%")

    lines += ["", f"Satisfaction bucket share by {group} (%):"]
    header = f"  {'bucket':<12}" + "".join(f"{str(c):>12}" for c in report.crosstab.columns)
    lines.append(header)
    for name, row in report.crosstab.iterrows():
        cells = "".join(f"{row[c]:>11.1f}%" for c in report.crosstab.columns)
        lines.append(f"  {str(name):<12}{cells}")

    lines += ["", "Remote split:"]
    for value, stats in sorted(report.remote_split.items()):
        lines.append(f"  {value:<6} n={stats['responses']:<4} "
                     f"sat {stats['mean_satisfaction']:.2f}  "
                     f"rec {stats['mean_recommend']:.2f}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "survey_sample.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Analyse the bundled sample survey — fully offline."""
    print("=" * 68)
    print(" SURVEY DATA ANALYZER - offline demo")
    print(" Bundled sample responses; no network, no APIs.")
    print("=" * 68)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise SurveyError(f"bundled sample not found: {source}")

    frame = load_survey(source)
    print(f"\nLoaded {len(frame):,} responses from {source.name}")

    report = analyze(frame, group="department")
    print()
    print(render_report(report, group="department"))

    # --- cross-checks the demo asserts ---------------------------------- #
    assert sum(report.satisfaction_dist.values()) == report.n_responses, \
        "likert distribution must sum to n"
    total_pct = sum(v / report.n_responses * 100 for v in
                    report.satisfaction_dist.values())
    assert abs(total_pct - 100) < 1e-6, "distribution shares must sum to 100%"
    assert -100 <= report.recommend["nps"] <= 100, "NPS out of bounds"

    # weighted group means must reproduce the overall mean
    table = report.by_group["department"]
    weighted = float((table["mean_satisfaction"] * table["responses"]).sum()
                     / table["responses"].sum())
    assert abs(weighted - report.satisfaction["mean"]) < 0.02, \
        "department-weighted mean != overall mean"

    # each crosstab row sums to 100%
    row_sums = report.crosstab.sum(axis=1)
    assert ((row_sums - 100).abs() < 0.1).all(), "crosstab rows must sum to 100%"
    print(f"\nCross-checks OK: distribution sums to {total_pct:.0f}%, "
          f"weighted means match (NPS {report.recommend['nps']:+.0f})")

    # a different grouping proves the cross-tab follows the --group option
    by_gender = analyze(frame, group="gender")
    assert set(by_gender.crosstab.columns) == set(frame["gender"].unique()), \
        "gender crosstab must cover every gender value"
    print(f"Grouped by gender instead: {len(by_gender.by_group['gender'])} groups, "
          f"mean sat {by_gender.satisfaction['mean']:.2f}")

    print("\nDemo completed successfully.")
    return 0
