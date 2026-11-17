"""Stock market analysis from a local OHLCV CSV - fully offline.

Provides price loading/validation, technical indicators (SMA, EMA, RSI,
MACD), risk/return statistics (volatility, Sharpe, max drawdown), a
cross-ticker correlation matrix, and a comparison report.

Sample data is bundled and deterministic; no market data is ever fetched
from the network. Past performance of synthetic data proves nothing about
real markets - this is an analytics exercise, not investment advice.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

LOG = logging.getLogger("stock.analyzer")

REQUIRED_COLUMNS = ("date", "ticker", "open", "high", "low", "close", "volume")
PRICE_COLUMNS = ("open", "high", "low", "close")
TRADING_DAYS = 252


class StockError(RuntimeError):
    """Raised for missing files, bad schemas, and inconsistent bars."""


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def load_prices(path: str | Path) -> pd.DataFrame:
    """Load an OHLCV CSV, validate bar consistency, return a sorted frame."""
    source = Path(path)
    if not source.is_file():
        raise StockError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise StockError(f"could not parse {source.name}: {exc}") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise StockError(
            f"missing column(s): {', '.join(missing)} "
            f"(required: {', '.join(REQUIRED_COLUMNS)})"
        )
    if frame.empty:
        raise StockError(f"no rows in {source.name}")

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if frame["date"].isna().any():
        raise StockError("unparseable date value(s)")

    for column in (*PRICE_COLUMNS, "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise StockError(f"column {column!r} contains non-numeric values")
    if (frame[list(PRICE_COLUMNS)] <= 0).any().any():
        raise StockError("prices must be positive")
    if (frame["volume"] < 0).any():
        raise StockError("volume must be non-negative")

    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise StockError("high is below open/close/low in some bars")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise StockError("low is above open/close/high in some bars")

    if frame.duplicated(subset=["date", "ticker"]).any():
        raise StockError("duplicate (date, ticker) rows")

    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    if (frame["ticker"] == "").any():
        raise StockError("empty ticker symbol")
    frame = frame.sort_values(["ticker", "date"]).reset_index(drop=True)
    LOG.info("loaded %d bars for %d ticker(s) from %s",
             len(frame), frame["ticker"].nunique(), source.name)
    return frame


# --------------------------------------------------------------------------- #
# Indicator primitives (pure Series -> Series functions)
# --------------------------------------------------------------------------- #
def daily_returns(closes: pd.Series) -> pd.Series:
    """Simple percentage change of a close series (first row dropped)."""
    if len(closes) < 2:
        raise StockError("need at least 2 closes to compute returns")
    return closes.pct_change().dropna()


def sma(closes: pd.Series, window: int) -> pd.Series:
    if window < 1:
        raise StockError("window must be >= 1")
    return closes.rolling(window, min_periods=window).mean()


def ema(closes: pd.Series, span: int) -> pd.Series:
    if span < 1:
        raise StockError("span must be >= 1")
    return closes.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(closes: pd.Series, period: int = 14) -> float:
    """Wilder's Relative Strength Index (last value, 0-100)."""
    if period < 1:
        raise StockError("period must be >= 1")
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    # zero loss means no down-moves: RSI is 100 (50 only if fully flat)
    safe_loss = loss.replace(0, math.nan)
    rs = gain / safe_loss
    value = (100 - 100 / (1 + rs)).iloc[-1]
    if pd.isna(value):
        return 100.0 if gain.iloc[-1] > 0 else 50.0
    return float(value)


def macd(closes: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line, and histogram."""
    fast = ema(closes, 12)
    slow = ema(closes, 26)
    line = fast - slow
    signal = line.ewm(span=9, adjust=False).mean()
    return line, signal, line - signal


def max_drawdown(closes: pd.Series) -> tuple[float, str, str]:
    """Largest peak-to-trough decline as a positive percentage."""
    if closes.empty:
        raise StockError("empty close series")
    running_max = closes.cummax()
    drawdown = (closes - running_max) / running_max
    trough_idx = drawdown.idxmin()
    peak_idx = closes.loc[:trough_idx].idxmax()
    pct = float(-drawdown.min()) * 100.0
    peak_date = pd.Timestamp(peak_idx).date()
    trough_date = pd.Timestamp(trough_idx).date()
    return pct, str(peak_date), str(trough_date)


# --------------------------------------------------------------------------- #
# Report model
# --------------------------------------------------------------------------- #
@dataclass
class TickerStats:
    """Risk/return statistics and latest indicator values for one ticker."""

    ticker: str
    bars: int
    start: str
    end: str
    last_close: float
    total_return_pct: float
    cagr_pct: float
    volatility_pct: float          # annualized
    sharpe: float                  # rf = 0
    max_drawdown_pct: float
    drawdown_peak: str
    drawdown_trough: str
    best_day_pct: float
    worst_day_pct: float
    sma_20: float
    sma_50: float
    above_sma_20: bool
    rsi_14: float
    macd_hist: float

    def to_dict(self) -> dict[str, Any]:
        return {k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in self.__dict__.items()}


@dataclass
class MarketReport:
    """Full analysis over one or more tickers."""

    tickers: dict[str, TickerStats] = field(default_factory=dict)
    correlation: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def best_ticker(self) -> str:
        return max(self.tickers, key=lambda t: self.tickers[t].total_return_pct)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tickers": {t: s.to_dict() for t, s in self.tickers.items()},
            "best_ticker": self.best_ticker,
            "correlation": {
                a: {b: round(float(v), 4) for b, v in row.items()}
                for a, row in self.correlation.to_dict("index").items()
            },
        }


def analyze_ticker(frame: pd.DataFrame, ticker: str,
                   sma_window: int = 20) -> TickerStats:
    """Compute statistics and indicators for one ticker's bars."""
    subset = frame[frame["ticker"] == ticker.upper()]
    if subset.empty:
        available = ", ".join(sorted(frame["ticker"].unique()))
        raise StockError(f"unknown ticker {ticker!r} (available: {available})")
    subset = subset.sort_values("date")
    # keep dates as the index so drawdown peak/trough report real dates
    closes = subset["close"].copy()
    closes.index = pd.DatetimeIndex(subset["date"].values)
    if len(closes) < 30:
        raise StockError(f"{ticker}: need at least 30 bars, got {len(closes)}")

    returns = daily_returns(closes)
    total_return = float(closes.iloc[-1] / closes.iloc[0] - 1.0)
    years = max((subset["date"].iloc[-1] - subset["date"].iloc[0]).days / 365.25, 1 / 365.25)
    cagr = float((1 + total_return) ** (1 / years) - 1) if total_return > -1 else -1.0

    vol = float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS))
    mean_daily = float(returns.mean())
    sharpe = (mean_daily / returns.std(ddof=1) * math.sqrt(TRADING_DAYS)
              if returns.std(ddof=1) > 0 else 0.0)

    drawdown_pct, peak, trough = max_drawdown(closes)
    sma_20_series = sma(closes, min(sma_window, len(closes)))
    sma_50_series = sma(closes, min(50, len(closes)))

    stats = TickerStats(
        ticker=ticker.upper(),
        bars=len(subset),
        start=str(subset["date"].iloc[0].date()),
        end=str(subset["date"].iloc[-1].date()),
        last_close=round(float(closes.iloc[-1]), 2),
        total_return_pct=round(total_return * 100, 2),
        cagr_pct=round(cagr * 100, 2),
        volatility_pct=round(vol * 100, 2),
        sharpe=round(float(sharpe), 2),
        max_drawdown_pct=round(drawdown_pct, 2),
        drawdown_peak=peak,
        drawdown_trough=trough,
        best_day_pct=round(float(returns.max() * 100), 2),
        worst_day_pct=round(float(returns.min() * 100), 2),
        sma_20=round(float(sma_20_series.dropna().iloc[-1]), 2),
        sma_50=round(float(sma_50_series.dropna().iloc[-1]), 2),
        above_sma_20=bool(closes.iloc[-1] >= sma_20_series.dropna().iloc[-1]),
        rsi_14=round(rsi(closes), 1),
        macd_hist=round(float(macd(closes)[2].dropna().iloc[-1]), 4),
    )
    return stats


def correlation_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Close-to-close return correlation across all tickers."""
    wide = frame.pivot_table(index="date", columns="ticker", values="close")
    if wide.shape[1] < 2:
        raise StockError("need at least 2 tickers for correlation")
    returns = wide.pct_change().dropna(how="all")
    corr = returns.corr()
    return corr.round(4)


def analyze_market(frame: pd.DataFrame, sma_window: int = 20) -> MarketReport:
    """Analyse every ticker in the frame into a MarketReport."""
    report = MarketReport()
    for ticker in sorted(frame["ticker"].unique()):
        report.tickers[ticker] = analyze_ticker(frame, ticker, sma_window=sma_window)

    report.summary = pd.DataFrame([s.to_dict() for s in report.tickers.values()])
    report.summary = report.summary.set_index("ticker")[
        ["last_close", "total_return_pct", "cagr_pct", "volatility_pct",
         "sharpe", "max_drawdown_pct", "rsi_14"]
    ]
    if frame["ticker"].nunique() >= 2:
        report.correlation = correlation_matrix(frame)
    LOG.info("analysed %d ticker(s)", len(report.tickers))
    return report


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_report(report: MarketReport) -> str:
    """Human-readable market report used by the CLI and demo."""
    lines = [
        "MARKET ANALYSIS (synthetic data - not investment advice)",
        "=" * 72,
        f"{'Ticker':<8}{'Last':>9}{'Return':>10}{'CAGR':>9}{'Vol':>9}"
        f"{'Sharpe':>8}{'MaxDD':>9}{'RSI':>7}",
        "-" * 72,
    ]
    for ticker, stats in sorted(report.tickers.items()):
        lines.append(
            f"{ticker:<8}{stats.last_close:>9.2f}{stats.total_return_pct:>9.2f}%"
            f"{stats.cagr_pct:>8.2f}%{stats.volatility_pct:>8.2f}%"
            f"{stats.sharpe:>8.2f}{stats.max_drawdown_pct:>8.2f}%{stats.rsi_14:>7.1f}"
        )

    lines += ["", "Per-ticker detail:"]
    for ticker, stats in sorted(report.tickers.items()):
        trend = "above" if stats.above_sma_20 else "below"
        lines += [
            f"  {ticker}: {stats.bars} bars ({stats.start} .. {stats.end})",
            f"      {trend} SMA{20} (price {stats.last_close:.2f} vs "
            f"{stats.sma_20:.2f}); SMA50={stats.sma_50:.2f}; "
            f"MACD hist={stats.macd_hist:+.3f}",
            f"      best day {stats.best_day_pct:+.2f}%, "
            f"worst day {stats.worst_day_pct:+.2f}%; "
            f"drawdown {stats.max_drawdown_pct:.2f}% "
            f"({stats.drawdown_peak} -> {stats.drawdown_trough})",
        ]

    if not report.correlation.empty:
        lines += ["", "Return correlation:"]
        tickers = list(report.correlation.columns)
        lines.append("        " + "".join(f"{t:>9}" for t in tickers))
        for a, row in report.correlation.iterrows():
            lines.append(f"  {a:<6}" + "".join(f"{row[b]:>9.3f}" for b in tickers))

    best = report.best_ticker
    lines += ["", f"Best performer: {best} "
                  f"({report.tickers[best].total_return_pct:+.2f}%)"]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_CSV = Path(__file__).resolve().parent.parent / "data" / "stocks_sample.csv"


def run_demo(csv_path: Path | None = None) -> int:
    """Analyse the bundled sample market data - fully offline."""
    print("=" * 72)
    print(" STOCK MARKET ANALYZER - offline demo")
    print(" Bundled synthetic OHLCV data; no network, no market feeds.")
    print("=" * 72)

    source = csv_path or DEMO_CSV
    if not source.is_file():
        raise StockError(f"bundled sample not found: {source}")

    frame = load_prices(source)
    print(f"\nLoaded {len(frame):,} bars for "
          f"{frame['ticker'].nunique()} tickers from {source.name}")

    report = analyze_market(frame)
    print()
    print(render_report(report))

    # --- cross-checks the demo asserts -----------------------------------
    for ticker, stats in report.tickers.items():
        closes = (frame[frame["ticker"] == ticker].sort_values("date")["close"]
                  .reset_index(drop=True))
        compounded = float(closes.iloc[-1] / closes.iloc[0] - 1.0) * 100
        assert abs(compounded - stats.total_return_pct) < 0.05, ticker
        assert 0 <= stats.max_drawdown_pct < 100, ticker
        assert 0 <= stats.rsi_14 <= 100, ticker
        assert stats.volatility_pct > 0, ticker

    corr = report.correlation
    assert (corr.index == corr.columns).all(), "correlation labels mismatch"
    assert ((corr.values - corr.values.T) ** 2).max() < 1e-6, "corr not symmetric"
    assert abs(float(corr.values.diagonal().min()) - 1.0) < 1e-6, "diag != 1"
    print(f"\nCross-checks OK: returns, drawdowns, RSI bounds, "
          f"correlation symmetry (best={report.best_ticker})")

    # RSI sanity: an always-rising series should pin RSI near 100
    rising = pd.Series([100 * (1.01 ** i) for i in range(60)])
    assert rsi(rising) > 90, "RSI should be high on a monotonically rising series"
    print(f"RSI sanity: monotonically rising series -> {rsi(rising):.1f}")

    print("\nDemo completed successfully.")
    return 0
