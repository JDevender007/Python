"""Tests for the Stock Market Analyzer project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from stock_analyzer import (  # noqa: E402
    DEMO_CSV,
    REQUIRED_COLUMNS,
    MarketReport,
    StockError,
    TickerStats,
    analyze_market,
    analyze_ticker,
    correlation_matrix,
    daily_returns,
    ema,
    load_prices,
    macd,
    max_drawdown,
    render_report,
    rsi,
    run_demo,
    sma,
)


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _bars(ticker: str = "TEST", n: int = 80, start: float = 100.0,
          drift: float = 0.001) -> list[dict]:
    """Deterministic synthetic bars with a gentle upward drift."""
    import datetime as dt
    import math

    rows = []
    price = start
    first_day = dt.date(2024, 1, 1)
    for i in range(n):
        day = first_day + dt.timedelta(days=i)
        open_ = price
        close = price * (1 + drift + 0.004 * math.sin(i))
        high = max(open_, close) * 1.01
        low = min(open_, close) * 0.99
        rows.append({
            "date": day.isoformat(), "ticker": ticker,
            "open": round(open_, 2), "high": round(high, 2),
            "low": round(low, 2), "close": round(close, 2),
            "volume": 1_000_000 + i * 1000,
        })
        price = close
    return rows


def _csv(tmp_path: Path, rows: list[dict], name: str = "stocks.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_prices(DEMO_CSV)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 1512
    assert set(sample["ticker"]) == {"ALPHA", "BETA", "GAMMA"}
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    for _, group in sample.groupby("ticker"):
        assert group["date"].is_monotonic_increasing  # sorted per ticker
    assert not sample.duplicated(subset=["date", "ticker"]).any()


def test_load_missing_file(tmp_path):
    with pytest.raises(StockError, match="not found"):
        load_prices(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("date,ticker,close\n2024-01-01,X,10\n", encoding="utf-8")
    with pytest.raises(StockError, match="missing column"):
        load_prices(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(StockError, match="no rows"):
        load_prices(path)


def test_load_bad_date(tmp_path):
    path = _csv(tmp_path, [dict(_bars(n=1)[0], date="yesterday")])
    with pytest.raises(StockError, match="unparseable date"):
        load_prices(path)


def test_load_non_numeric(tmp_path):
    path = _csv(tmp_path, [dict(_bars(n=1)[0], close="high")])
    with pytest.raises(StockError, match="non-numeric"):
        load_prices(path)


def test_load_non_positive_price(tmp_path):
    path = _csv(tmp_path, [dict(_bars(n=1)[0], close=0.0, low=0.0)])
    with pytest.raises(StockError, match="positive"):
        load_prices(path)


def test_load_negative_volume(tmp_path):
    path = _csv(tmp_path, [dict(_bars(n=1)[0], volume=-5)])
    with pytest.raises(StockError, match="volume"):
        load_prices(path)


def test_load_high_below_close(tmp_path):
    row = _bars(n=1)[0]
    row["high"] = row["close"] - 5  # violates high >= close
    with pytest.raises(StockError, match="high is below"):
        load_prices(_csv(tmp_path, [row]))


def test_load_low_above_open(tmp_path):
    row = _bars(n=1)[0]
    row["low"] = row["open"] + 5    # violates low <= open
    row["high"] = row["low"] + 1    # keep high consistent so only low breaks
    with pytest.raises(StockError, match="low is above"):
        load_prices(_csv(tmp_path, [row]))


def test_load_duplicate_rows(tmp_path):
    rows = _bars(n=2) + [_bars(n=2)[1]]
    with pytest.raises(StockError, match="duplicate"):
        load_prices(_csv(tmp_path, rows))


def test_load_normalizes_ticker_case(tmp_path):
    rows = _bars(ticker="  abc ", n=35)
    frame = load_prices(_csv(tmp_path, rows))
    assert set(frame["ticker"]) == {"ABC"}


def test_load_sorts_by_ticker_then_date(tmp_path):
    rows = _bars(ticker="ZZZ", n=35) + _bars(ticker="AAA", n=35)
    frame = load_prices(_csv(tmp_path, rows))
    assert list(dict.fromkeys(frame["ticker"])) == ["AAA", "ZZZ"]


# --------------------------------------------------------------------------- #
# Indicators
# --------------------------------------------------------------------------- #
def test_daily_returns():
    closes = pd.Series([100.0, 110.0, 99.0])
    returns = daily_returns(closes)
    assert len(returns) == 2
    assert returns.iloc[0] == pytest.approx(0.10)
    assert returns.iloc[1] == pytest.approx(-0.10)


def test_daily_returns_needs_two_points():
    with pytest.raises(StockError, match="at least 2"):
        daily_returns(pd.Series([100.0]))


def test_sma_window():
    closes = pd.Series(range(1, 11), dtype=float)
    values = sma(closes, 3)
    assert pd.isna(values.iloc[1])          # min_periods=window
    assert values.iloc[2] == pytest.approx(2.0)
    assert values.iloc[-1] == pytest.approx(9.0)
    with pytest.raises(StockError, match="window"):
        sma(closes, 0)


def test_ema_tracks_series():
    flat = pd.Series([50.0] * 40)
    assert ema(flat, 5).iloc[-1] == pytest.approx(50.0)

    trending = pd.Series([float(i) for i in range(1, 40)])
    values = ema(trending, 5)
    # an EMA lags a rising trend but stays close to the last price
    assert values.iloc[-1] < trending.iloc[-1]
    assert values.iloc[-1] > trending.iloc[-1] * 0.9
    with pytest.raises(StockError, match="span"):
        ema(trending, 0)


def test_rsi_bounds_and_direction():
    rising = pd.Series([100 * (1.01 ** i) for i in range(60)])
    falling = pd.Series([100 * (0.99 ** i) for i in range(60)])
    mixed = pd.Series([100 + (5 if i % 2 else -5) for i in range(60)], dtype=float)
    assert rsi(rising) > 90
    assert rsi(falling) < 10
    assert 0 <= rsi(mixed) <= 100
    with pytest.raises(StockError, match="period"):
        rsi(rising, period=0)


def test_macd_shapes():
    closes = pd.Series([100 + i + (i % 7) for i in range(80)], dtype=float)
    line, signal, hist = macd(closes)
    assert len(line) == len(signal) == len(hist) == 80
    last = len(line) - 1
    assert hist.iloc[last] == pytest.approx(line.iloc[last] - signal.iloc[last])


def test_max_drawdown_known_series():
    closes = pd.Series(
        [100.0, 120.0, 60.0, 90.0],
        index=pd.to_datetime(["2024-01-01", "2024-01-02",
                              "2024-01-03", "2024-01-04"]),
    )
    pct, peak, trough = max_drawdown(closes)
    assert pct == pytest.approx(50.0)
    assert peak == "2024-01-02"
    assert trough == "2024-01-03"


def test_max_drawdown_no_loss():
    pct, _, _ = max_drawdown(pd.Series([10.0, 20.0, 30.0]))
    assert pct == pytest.approx(0.0)


def test_max_drawdown_empty():
    with pytest.raises(StockError, match="empty"):
        max_drawdown(pd.Series(dtype=float))


# --------------------------------------------------------------------------- #
# Per-ticker analysis
# --------------------------------------------------------------------------- #
def test_analyze_ticker_stats(tmp_path):
    frame = load_prices(_csv(tmp_path, _bars(n=80)))
    stats = analyze_ticker(frame, "TEST")
    assert isinstance(stats, TickerStats)
    assert stats.bars == 80
    assert stats.total_return_pct > 0        # gentle drift upward
    assert stats.volatility_pct > 0
    assert 0 <= stats.max_drawdown_pct < 100
    assert 0 <= stats.rsi_14 <= 100
    assert stats.sma_20 > 0 and stats.sma_50 > 0
    assert stats.start <= stats.end


def test_analyze_ticker_unknown(tmp_path, sample):
    with pytest.raises(StockError, match="unknown ticker"):
        analyze_ticker(sample, "NOPE")


def test_analyze_ticker_needs_30_bars(tmp_path):
    frame = load_prices(_csv(tmp_path, _bars(n=20)))
    with pytest.raises(StockError, match="at least 30"):
        analyze_ticker(frame, "TEST")


def test_analyze_ticker_total_return_matches_closes(tmp_path):
    rows = _bars(n=80)
    frame = load_prices(_csv(tmp_path, rows))
    stats = analyze_ticker(frame, "TEST")
    expected = (rows[-1]["close"] / rows[0]["close"] - 1) * 100
    assert stats.total_return_pct == pytest.approx(expected, abs=0.05)


# --------------------------------------------------------------------------- #
# Market-level analysis
# --------------------------------------------------------------------------- #
def test_analyze_market_all_tickers(sample):
    report = analyze_market(sample)
    assert set(report.tickers) == {"ALPHA", "BETA", "GAMMA"}
    assert len(report.summary) == 3
    assert report.best_ticker in report.tickers
    best = max(report.tickers.values(), key=lambda s: s.total_return_pct)
    assert report.tickers[report.best_ticker] is best


def test_correlation_matrix(sample):
    corr = correlation_matrix(sample)
    assert list(corr.columns) == ["ALPHA", "BETA", "GAMMA"]
    assert ((corr.values - corr.values.T) ** 2).max() < 1e-6
    assert abs(float(corr.values.diagonal().min()) - 1.0) < 1e-6
    assert ((corr.values >= -1.0001) & (corr.values <= 1.0001)).all()


def test_correlation_needs_two_tickers(tmp_path):
    frame = load_prices(_csv(tmp_path, _bars(n=40)))
    with pytest.raises(StockError, match="at least 2"):
        correlation_matrix(frame)


def test_market_report_to_dict(sample):
    payload = analyze_market(sample).to_dict()
    assert set(payload["tickers"]) == {"ALPHA", "BETA", "GAMMA"}
    assert payload["best_ticker"] in payload["tickers"]
    assert "correlation" in payload
    json.dumps(payload)  # serializable
    first = next(iter(payload["tickers"].values()))
    assert "sharpe" in first and "max_drawdown_pct" in first


# --------------------------------------------------------------------------- #
# Rendering and demo
# --------------------------------------------------------------------------- #
def test_render_report_sections(sample):
    text = render_report(analyze_market(sample))
    assert "MARKET ANALYSIS" in text
    assert "Return correlation:" in text
    assert "Per-ticker detail:" in text
    assert "Best performer:" in text
    assert "ALPHA" in text and "GAMMA" in text


def test_render_single_ticker_without_correlation(tmp_path):
    frame = load_prices(_csv(tmp_path, _bars(n=60)))
    report = MarketReport(tickers={"TEST": analyze_ticker(frame, "TEST")})
    text = render_report(report)
    assert "Return correlation" not in text
    assert "TEST" in text


def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "RSI sanity" in out
    assert "not investment advice" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_sample(tmp_path):
    with pytest.raises(StockError, match="bundled sample"):
        run_demo(csv_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def test_cli_file_analysis(capsys):
    assert main(["--file", str(DEMO_CSV)]) == 0
    out = capsys.readouterr().out
    assert "MARKET ANALYSIS" in out and "Done." in out


def test_cli_single_ticker(capsys):
    assert main(["--file", str(DEMO_CSV), "--ticker", "alpha"]) == 0
    out = capsys.readouterr().out
    detail = out.split("Per-ticker detail:")[1]
    assert "ALPHA" in detail
    assert "BETA" not in detail and "GAMMA" not in detail
    assert "Return correlation" not in out  # needs >= 2 tickers


def test_cli_json_output(tmp_path, capsys):
    out_file = tmp_path / "report.json"
    assert main(["--file", str(DEMO_CSV), "--json", str(out_file)]) == 0
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert set(payload["tickers"]) == {"ALPHA", "BETA", "GAMMA"}


def test_cli_chart_output(tmp_path, capsys):
    chart = tmp_path / "prices.png"
    assert main(["--file", str(DEMO_CSV), "--chart", str(chart), "--quiet"]) == 0
    assert chart.is_file() and chart.stat().st_size > 1000


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_bad_ticker(capsys):
    assert main(["--file", str(DEMO_CSV), "--ticker", "NOPE"]) == 2
    assert "unknown ticker" in capsys.readouterr().err


def test_cli_bad_window(capsys):
    assert main(["--file", str(DEMO_CSV), "--window", "0"]) == 2
    assert "--window" in capsys.readouterr().err


def test_cli_requires_source(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_project_has_sample_data():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent.name == "data"
