"""Statistical visualization: descriptive stats, inference, and charts - offline.

Loads a CSV measurement table, computes descriptive statistics (mean, median,
std, quartiles, IQR, z-scores, outlier fences, skewness), a two-sample
t-test with confidence intervals, Pearson correlation with a least-squares
regression, and renders six statistical plots (histogram + normal curve,
box plot, Q-Q plot, bar chart with 95% CI error bars, scatter + regression,
correlation heatmap) using the headless Agg backend. Fully offline.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import matplotlib
matplotlib.use("Agg")  # headless: must precede pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

LOG = logging.getLogger("stats")

REQUIRED_COLUMNS = ("subject_id", "group", "score", "age", "improved")
NUMERIC_COLUMNS = ("score", "age")
OUTLIER_SIGMA = 1.5  # IQR rule: fence = Q1 - 1.5*IQR / Q3 + 1.5*IQR


class StatsError(RuntimeError):
    """Raised for missing files, bad schemas, and invalid statistical input."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_measurements(path: str | Path) -> pd.DataFrame:
    """Load the measurements CSV, validate it, and return a cleaned frame."""
    source = Path(path)
    if not source.is_file():
        raise StatsError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise StatsError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise StatsError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise StatsError(f"no rows in {source.name}")

    frame = frame.copy()
    for column in ("subject_id", "group"):
        values = frame[column].astype(str).str.strip()
        if values.eq("").any() or values.str.lower().eq("nan").any():
            raise StatsError(f"empty {column!r} value(s)")
        frame[column] = values
    if frame["subject_id"].duplicated().any():
        raise StatsError("duplicate subject_id value(s)")

    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise StatsError(f"column {column!r} contains non-numeric values")

    if not frame["age"].between(0, 120).all():
        raise StatsError("age outside 0..120")

    improved = frame["improved"].astype(str).str.strip().str.lower()
    if not improved.isin(["yes", "no"]).all():
        raise StatsError("improved must be 'yes' or 'no'")
    frame["improved"] = improved

    if frame["group"].nunique() < 2:
        raise StatsError("need at least two groups to compare")
    for _, subset in frame.groupby("group"):
        if len(subset) < 3:
            raise StatsError("every group needs at least 3 rows")

    frame = frame.sort_values(["group", "subject_id"]).reset_index(drop=True)
    LOG.info("loaded %d rows (%d groups) from %s",
             len(frame), frame["group"].nunique(), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Descriptive statistics
# --------------------------------------------------------------------------- #
def describe(values: Any) -> dict[str, float]:
    """Descriptive stats for a 1-D sample (ddof=1 standard deviation)."""
    data = np.asarray(list(values), dtype=float)
    if data.size < 2:
        raise StatsError("need at least 2 values to describe")
    if not np.isfinite(data).all():
        raise StatsError("sample contains non-finite values")

    mean = float(data.mean())
    std = float(data.std(ddof=1))
    q1, median, q3 = (float(v) for v in np.percentile(data, [25, 50, 75]))
    iqr = q3 - q1
    return {
        "n": int(data.size),
        "mean": mean,
        "median": median,
        "std": std,
        "variance": std ** 2,
        "min": float(data.min()),
        "max": float(data.max()),
        "range": float(data.max() - data.min()),
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "sem": std / math.sqrt(data.size),
        "skewness": _skewness(data, std),
    }


def _skewness(data: np.ndarray, std: float) -> float:
    """Fisher-Pearson standardized moment coefficient (population form)."""
    if std == 0 or data.size < 3:
        return 0.0
    z = (data - data.mean()) / std
    return float((z ** 3).mean())


def outlier_bounds(values: Any, sigma: float = OUTLIER_SIGMA) -> tuple[float, float]:
    """Tukey fence: [Q1 - sigma*IQR, Q3 + sigma*IQR]."""
    stats = describe(values)
    return stats["q1"] - sigma * stats["iqr"], stats["q3"] + sigma * stats["iqr"]


def find_outliers(values: Any, sigma: float = OUTLIER_SIGMA) -> list[float]:
    """Values outside the Tukey fences (sorted)."""
    low, high = outlier_bounds(values, sigma)
    data = sorted(float(v) for v in values)
    return [v for v in data if v < low or v > high]


def z_scores(values: Any) -> list[float]:
    """Sample z-scores using mean and ddof=1 standard deviation."""
    stats = describe(values)
    if stats["std"] == 0:
        raise StatsError("standard deviation is zero; z-scores undefined")
    return [(float(v) - stats["mean"]) / stats["std"] for v in values]


# --------------------------------------------------------------------------- #
# Inference
# --------------------------------------------------------------------------- #
# two-sided 95% t critical values by df (rows); normal approximation above 60
_T_975 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
    7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
    13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101,
    19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064,
    25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def t_critical(df: int, confidence: float = 0.95) -> float:
    """Two-sided t critical value (table lookup, normal approx for df > 60)."""
    if confidence != 0.95:
        raise StatsError("only 95% confidence is supported")
    if df < 1:
        raise StatsError("degrees of freedom must be >= 1")
    if df in _T_975:
        return _T_975[df]
    if df <= 40:
        return 2.021  # df 31..40
    if df <= 60:
        return 2.000  # df 41..60
    return 1.960      # normal approximation


def confidence_interval(values: Any, confidence: float = 0.95) -> tuple[float, float]:
    """95% t-interval for the mean of a sample."""
    stats = describe(values)
    margin = t_critical(stats["n"] - 1, confidence) * stats["sem"]
    return stats["mean"] - margin, stats["mean"] + margin


def welch_t_test(a: Any, b: Any) -> dict[str, float]:
    """Welch's unequal-variance two-sample t-test (two-sided).

    Returns t statistic, approximate Welch-Satterthwaite degrees of freedom,
    and a p-value from the regularized incomplete beta function.
    """
    x, y = np.asarray(list(a), dtype=float), np.asarray(list(b), dtype=float)
    if x.size < 2 or y.size < 2:
        raise StatsError("each sample needs at least 2 rows")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise StatsError("sample contains non-finite values")

    mean_diff = float(x.mean() - y.mean())
    va, vb = float(x.var(ddof=1)), float(y.var(ddof=1))
    se2 = va / x.size + vb / y.size
    if se2 == 0:
        raise StatsError("both samples are constant; t is undefined")
    t_stat = mean_diff / math.sqrt(se2)

    # Welch-Satterthwaite degrees of freedom
    df = se2 ** 2 / ((va / x.size) ** 2 / (x.size - 1)
                     + (vb / y.size) ** 2 / (y.size - 1))
    p_value = 2 * _student_t_sf(abs(t_stat), df)
    return {"t": t_stat, "df": df, "p_value": p_value, "mean_diff": mean_diff}


def _student_t_sf(t: float, df: float) -> float:
    """Survival function P(T > t) for Student's t via incomplete beta."""
    x = df / (df + t * t)
    return 0.5 * _regularized_beta(x, df / 2.0, 0.5)


def _regularized_beta(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta I_x(a, b) (continued fraction, Lentz)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    log_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - log_beta) / a

    # modified Lentz's method
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            numerator = 1.0
        elif i % 2 == 0:
            numerator = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            numerator = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + numerator * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + numerator / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    result = front * (f - 1.0)
    return min(max(result, 0.0), 1.0)


def correlation(x: Any, y: Any) -> dict[str, float]:
    """Pearson correlation with a least-squares fit: r, r^2, slope, intercept."""
    xs, ys = np.asarray(list(x), dtype=float), np.asarray(list(y), dtype=float)
    if xs.size != ys.size or xs.size < 2:
        raise StatsError("x and y must be the same length (>= 2)")
    if not (np.isfinite(xs).all() and np.isfinite(ys).all()):
        raise StatsError("input contains non-finite values")
    if xs.std() == 0 or ys.std() == 0:
        raise StatsError("cannot correlate a constant vector")

    slope, intercept = np.polyfit(xs, ys, 1)
    r = float(np.corrcoef(xs, ys)[0, 1])
    return {"r": r, "r2": r ** 2, "slope": float(slope),
            "intercept": float(intercept)}


# --------------------------------------------------------------------------- #
# Chart functions (uniform signature: data -> matplotlib Figure)
# --------------------------------------------------------------------------- #
def _figure(figsize: tuple[float, float] = (8, 4.5)) -> tuple[Any, Any]:
    figure, axis = plt.subplots(figsize=figsize)
    return figure, axis


def chart_histogram(values: Any, bins: int = 20):
    """Histogram with fitted normal curve and mean line."""
    data = np.asarray(list(values), dtype=float)
    stats = describe(data)
    figure, axis = _figure()
    axis.hist(data, bins=bins, density=True, color="#4C72B0",
              edgecolor="white", alpha=0.75, label="sample")
    xs = np.linspace(data.min(), data.max(), 200)
    if stats["std"] > 0:
        normal = (np.exp(-0.5 * ((xs - stats["mean"]) / stats["std"]) ** 2)
                  / (stats["std"] * math.sqrt(2 * math.pi)))
        axis.plot(xs, normal, "r-", linewidth=2, label="normal fit")
    axis.axvline(stats["mean"], color="black", linestyle="--",
                 label=f"mean {stats['mean']:.2f}")
    axis.axvline(stats["median"], color="green", linestyle=":",
                 label=f"median {stats['median']:.2f}")
    axis.set_title("Distribution with normal fit")
    axis.set_xlabel("Value")
    axis.set_ylabel("Density")
    axis.legend()
    axis.grid(alpha=0.3)
    return figure


def chart_box(groups: dict[str, Any]):
    """Box plots per group with Tukey outlier fences."""
    names = sorted(groups)
    samples = [np.asarray(list(groups[name]), dtype=float) for name in names]
    figure, axis = _figure()
    axis.boxplot(samples, tick_labels=names, patch_artist=True,
                 showmeans=True)
    for i, data in enumerate(samples, start=1):
        low, high = outlier_bounds(data)
        axis.hlines([low, high], i - 0.35, i + 0.35,
                    colors="red", linestyles="dashed", linewidth=1.2)
    axis.set_title("Group distributions (dashed = Tukey fences)")
    axis.set_ylabel("Score")
    axis.grid(axis="y", alpha=0.3)
    return figure


def chart_qq(values: Any):
    """Normal Q-Q plot: sorted sample vs theoretical normal quantiles."""
    data = np.sort(np.asarray(list(values), dtype=float))
    n = data.size
    # Blom plotting positions, clipped away from 0/1
    probs = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
    theoretical = _norm_ppf(probs)
    stats = describe(data)
    figure, axis = _figure((7, 5.5))
    axis.scatter(theoretical, data, color="#C44E52", alpha=0.8)
    if stats["std"] > 0:
        xs = np.linspace(theoretical.min(), theoretical.max(), 50)
        axis.plot(xs, stats["mean"] + stats["std"] * xs, "k--",
                  label="normal reference")
    axis.set_title("Normal Q-Q plot")
    axis.set_xlabel("Theoretical quantile")
    axis.set_ylabel("Sample quantile")
    axis.legend()
    axis.grid(alpha=0.3)
    return figure


def _norm_ppf(probs: np.ndarray) -> np.ndarray:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01,
         2.445134137142996e+00, 3.754408661907416e+00]
    p_low, p_high = 0.02425, 1 - 0.02425
    probs = np.asarray(probs, dtype=float)
    result = np.empty_like(probs)

    low = probs < p_low
    if low.any():
        q = np.sqrt(-2 * np.log(probs[low]))
        result[low] = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) \
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    high = probs > p_high
    if high.any():
        q = np.sqrt(-2 * np.log(1 - probs[high]))
        result[high] = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) \
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    mid = ~(low | high)
    if mid.any():
        q = probs[mid] - 0.5
        r = q * q
        result[mid] = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q \
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    return result


def chart_means(groups: dict[str, Any]):
    """Group means with 95% t-interval error bars."""
    names = sorted(groups)
    samples = [np.asarray(list(groups[name]), dtype=float) for name in names]
    means = [describe(data)["mean"] for data in samples]
    lows, highs = [], []
    for data, mean in zip(samples, means):
        low, high = confidence_interval(data)
        lows.append(mean - low)
        highs.append(high - mean)

    figure, axis = _figure((7, 4.5))
    axis.bar(names, means, color=["#55A868", "#C44E52", "#4C72B0", "#8172B2"][:len(names)],
             capsize=6, yerr=[lows, highs], error_kw={"linewidth": 1.4})
    axis.set_title("Group means with 95% confidence intervals")
    axis.set_ylabel("Score")
    axis.grid(axis="y", alpha=0.3)
    for i, mean in enumerate(means):
        axis.text(i, mean, f" {mean:.2f}", va="bottom", ha="center")
    return figure


def chart_regression(x: Any, y: Any):
    """Scatter with least-squares line and r^2 annotation."""
    xs, ys = np.asarray(list(x), dtype=float), np.asarray(list(y), dtype=float)
    fit = correlation(xs, ys)
    figure, axis = _figure()
    axis.scatter(xs, ys, color="#4C72B0", alpha=0.75, edgecolor="white")
    line = np.linspace(xs.min(), xs.max(), 50)
    axis.plot(line, fit["slope"] * line + fit["intercept"], "r-", linewidth=2,
              label=f"y = {fit['slope']:.2f}x + {fit['intercept']:.2f}")
    axis.set_title(f"Regression (r = {fit['r']:.3f}, r^2 = {fit['r2']:.3f})")
    axis.set_xlabel("X")
    axis.set_ylabel("Y")
    axis.legend()
    axis.grid(alpha=0.3)
    return figure


def chart_correlation(frame: pd.DataFrame, columns: list[str] | None = None):
    """Correlation heatmap of numeric columns."""
    numeric = frame.select_dtypes(include="number")
    if columns is not None:
        missing = [c for c in columns if c not in numeric.columns]
        if missing:
            raise StatsError(f"column(s) not numeric: {', '.join(missing)}")
        numeric = numeric[columns]
    if numeric.shape[1] < 2:
        raise StatsError("need at least two numeric columns to correlate")
    matrix = numeric.corr()
    figure, axis = plt.subplots(figsize=(6.5, 5.5))
    image = axis.imshow(matrix.values, cmap="coolwarm", vmin=-1, vmax=1)
    labels = [c.replace("_", " ") for c in matrix.columns]
    axis.set_xticks(range(len(labels)))
    axis.set_xticklabels(labels, rotation=40, ha="right")
    axis.set_yticks(range(len(labels)))
    axis.set_yticklabels(labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            axis.text(j, i, f"{matrix.values[i, j]:.2f}",
                      ha="center", va="center", fontsize=9)
    axis.set_title("Correlation matrix")
    figure.colorbar(image, ax=axis, label="Pearson r")
    figure.tight_layout()
    return figure


# name -> (function, description)
CHART_TYPES: dict[str, tuple[Callable[..., Any], str]] = {
    "histogram": (chart_histogram, "distribution with normal fit"),
    "box": (chart_box, "group box plots with Tukey fences"),
    "qq": (chart_qq, "normal Q-Q plot"),
    "means": (chart_means, "group means with 95% CI error bars"),
    "regression": (chart_regression, "scatter with least-squares line"),
    "correlation": (chart_correlation, "correlation heatmap of numeric columns"),
}


def render_chart(name: str, frame: pd.DataFrame, out_path: str | Path) -> Path:
    """Render one statistical chart from the measurements frame to a PNG."""
    if name not in CHART_TYPES:
        available = ", ".join(sorted(CHART_TYPES))
        raise StatsError(f"unknown chart {name!r} (available: {available})")
    function = CHART_TYPES[name][0]
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    groups = {g: subset["score"].tolist() for g, subset in frame.groupby("group")}
    if name == "histogram":
        figure = function(frame["score"])
    elif name == "box":
        figure = function(groups)
    elif name == "qq":
        figure = function(frame["score"])
    elif name == "means":
        figure = function(groups)
    elif name == "regression":
        figure = function(frame["age"], frame["score"])
    else:  # correlation
        figure = function(frame)

    try:
        figure.tight_layout()
        figure.savefig(target, dpi=100)
    finally:
        plt.close(figure)
    if not target.is_file() or target.stat().st_size == 0:
        raise StatsError(f"failed to write {target}")
    LOG.info("rendered %s -> %s (%d bytes)", name, target, target.stat().st_size)
    return target


# --------------------------------------------------------------------------- #
# Report model
# --------------------------------------------------------------------------- #
@dataclass
class StatsReport:
    """Descriptive + inferential summary over a validated frame."""

    frame: pd.DataFrame
    overall: dict[str, float] = field(default_factory=dict)
    by_group: dict[str, dict[str, float]] = field(default_factory=dict)
    comparison: dict[str, float] = field(default_factory=dict)
    age_fit: dict[str, float] = field(default_factory=dict)
    outliers: dict[str, list[float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.overall.get("n", 0),
            "overall": {k: round(v, 4) for k, v in self.overall.items()},
            "by_group": {g: {k: round(v, 4) for k, v in stats.items()}
                         for g, stats in self.by_group.items()},
            "comparison": {k: (round(v, 6) if isinstance(v, (int, float))
                               else v)
                           for k, v in self.comparison.items()},
            "age_fit": {k: round(v, 4) for k, v in self.age_fit.items()},
            "outliers": {g: values for g, values in self.outliers.items()},
        }


def analyze(frame: pd.DataFrame) -> StatsReport:
    """Compute descriptive statistics, t-test, and correlations."""
    report = StatsReport(frame=frame)
    report.overall = describe(frame["score"])

    for group, subset in frame.groupby("group"):
        report.by_group[group] = describe(subset["score"])
        report.outliers[group] = find_outliers(subset["score"])

    names = sorted(report.by_group)
    report.comparison = welch_t_test(
        frame.loc[frame["group"] == names[0], "score"],
        frame.loc[frame["group"] == names[1], "score"],
    )
    report.comparison["group_a"], report.comparison["group_b"] = names[0], names[1]
    report.age_fit = correlation(frame["age"], frame["score"])
    LOG.info("analysed %d rows; %s vs %s p=%.4f",
             len(frame), names[0], names[1], report.comparison["p_value"])
    return report


def render_report(report: StatsReport) -> str:
    """Human-readable statistical report used by the CLI and demo."""
    overall = report.overall
    names = sorted(report.by_group)
    lines = [
        "STATISTICAL SUMMARY",
        "=" * 68,
        f"Sample     : {overall['n']} observations   "
        f"mean {overall['mean']:.2f}  median {overall['median']:.2f}",
        f"Spread     : std {overall['std']:.2f}  variance {overall['variance']:.2f}  "
        f"range {overall['range']:.2f}",
        f"Quartiles  : Q1 {overall['q1']:.2f}  Q3 {overall['q3']:.2f}  "
        f"IQR {overall['iqr']:.2f}  skew {overall['skewness']:+.3f}",
        "",
        "By group:",
        f"  {'group':<14}{'n':>4}{'mean':>9}{'std':>9}{'median':>9}"
        f"{'CI low':>9}{'CI high':>10}{'outliers':>10}",
    ]
    for name in names:
        stats = report.by_group[name]
        low, high = confidence_interval(
            report.frame.loc[report.frame["group"] == name, "score"])
        lines.append(
            f"  {name:<14}{stats['n']:>4}{stats['mean']:>9.2f}"
            f"{stats['std']:>9.2f}{stats['median']:>9.2f}"
            f"{low:>9.2f}{high:>10.2f}{len(report.outliers[name]):>10}"
        )

    cmp_ = report.comparison
    verdict = "significant" if cmp_["p_value"] < 0.05 else "not significant"
    lines += [
        "",
        f"Welch t-test: {cmp_['group_a']} vs {cmp_['group_b']}",
        f"  t = {cmp_['t']:+.3f}   df = {cmp_['df']:.1f}   "
        f"p = {cmp_['p_value']:.4f}   mean diff = {cmp_['mean_diff']:+.2f}",
        f"  difference is {verdict} at the 5% level "
        f"({'reject' if cmp_['p_value'] < 0.05 else 'retain'} H0)",
        "",
        f"Age vs score: r = {report.age_fit['r']:+.3f}  "
        f"r^2 = {report.age_fit['r2']:.3f}  "
        f"slope = {report.age_fit['slope']:+.3f}",
        f"  {report.age_fit['r2'] * 100:.1f}% of score variance is explained by age",
    ]
    if report.outliers:
        lines += ["", "Tukey outliers (1.5 x IQR):"]
        for name in names:
            values = report.outliers[name]
            shown = ", ".join(f"{v:.2f}" for v in values[:5])
            suffix = " ..." if len(values) > 5 else ""
            lines.append(f"  {name:<14}{len(values)} found  {shown}{suffix}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "measurements.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "output"


def run_demo(out_dir: Path | None = None, quiet: bool = False) -> int:
    """Analyse the bundled sample and render all six charts - fully offline."""
    if not quiet:
        print("=" * 68)
        print(" STATISTICAL VISUALIZER - offline demo")
        print(" Bundled sample measurements; Agg backend; local PNGs.")
        print("=" * 68)

    if not DEMO_CSV.is_file():
        raise StatsError(f"bundled sample not found: {DEMO_CSV}")
    frame = load_measurements(DEMO_CSV)
    target_dir = out_dir or DEFAULT_OUTPUT

    report = analyze(frame)
    if not quiet:
        print(f"\nLoaded {len(frame)} rows across "
              f"{frame['group'].nunique()} groups from {DEMO_CSV.name}\n")
        print(render_report(report))

    written = {}
    for name in CHART_TYPES:
        written[name] = render_chart(name, frame, target_dir / f"{name}.png")

    # --- cross-checks the demo asserts ----------------------------------- #
    assert report.overall["n"] == len(frame), "overall n mismatch"
    total = sum(s["n"] for s in report.by_group.values())
    assert total == len(frame), "group counts must partition the sample"
    for name, stats in report.by_group.items():
        subset = frame.loc[frame["group"] == name, "score"]
        assert abs(stats["mean"] - float(subset.mean())) < 1e-9, f"mean {name}"
        assert stats["min"] <= stats["q1"] <= stats["median"] \
            <= stats["q3"] <= stats["max"], f"quartile order {name}"
    p = report.comparison["p_value"]
    assert 0.0 <= p <= 1.0, "p-value out of bounds"
    assert report.comparison["group_a"] in report.by_group
    assert abs(report.age_fit["r"]) <= 1.0, "r out of bounds"
    assert 0.0 <= report.age_fit["r2"] <= 1.0, "r2 out of bounds"
    for path in written.values():
        assert path.is_file() and path.stat().st_size > 1000, path.name
    assert plt.get_fignums() == [], "figures must be closed"

    if not quiet:
        print(f"\nCross-checks OK: group counts partition {report.overall['n']} rows, "
              f"quartiles ordered, p={p:.4f} in [0,1], "
              f"{len(written)} charts rendered, figures closed")
        print("Demo completed successfully.")
    return 0
