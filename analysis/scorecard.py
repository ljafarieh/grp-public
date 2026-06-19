"""
Thesis scorecard: tracks equal-weight baskets per thesis role vs benchmarks
over multiple time windows.

Explicitly framed as a hypothesis scorecard, not a backtest of a strategy.
No lookahead bias: all returns use adj_close prices only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

BENCHMARK_ROLES = {"benchmark"}
WINDOWS = {
    "30d": 30,
    "90d": 90,
    "1yr": 365,
}


@dataclass
class BasketReturn:
    role: str
    tickers: list[str]
    window: str
    total_return_pct: float
    annualized_return_pct: float
    trading_days: int
    best_ticker: str
    best_ticker_return_pct: float
    worst_ticker: str
    worst_ticker_return_pct: float


@dataclass
class ScorecardResult:
    window: str
    basket_returns: list[BasketReturn]        # thesis roles
    benchmark_returns: dict[str, float]       # ticker → total return pct
    as_of: date


# ---------------------------------------------------------------------------
# Core calculations
# ---------------------------------------------------------------------------

def _total_return(price_series: pd.Series, n_days: int) -> Optional[float]:
    """
    Compute total return over the last n_days of trading data.
    Returns None if insufficient data.
    """
    s = price_series.dropna()
    if len(s) < 2:
        return None

    # Find the slice covering approximately n_days calendar days
    end_date = s.index[-1]
    start_cutoff = end_date - pd.Timedelta(days=n_days)
    window_data = s[s.index >= start_cutoff]

    if len(window_data) < 2:
        return None

    return float((window_data.iloc[-1] / window_data.iloc[0] - 1) * 100)


def _annualize(total_return_pct: float, trading_days: int) -> float:
    """Convert total return over trading_days to annualized, compounded."""
    if trading_days <= 0:
        return 0.0
    r = total_return_pct / 100
    return float(((1 + r) ** (252 / trading_days) - 1) * 100)


def build_scorecard(
    cached_data: dict[str, pd.DataFrame],
    universe_meta: dict,
    as_of: Optional[date] = None,
) -> list[ScorecardResult]:
    """
    Build a scorecard for each time window. Returns one ScorecardResult per window.
    """
    as_of = as_of or date.today() - timedelta(days=1)

    # Build adj_close series per ticker, indexed by datetime
    price_series: dict[str, pd.Series] = {}
    for ticker, df in cached_data.items():
        s = df["adj_close"].copy()
        s.index = pd.to_datetime(s.index)
        s = s[s.index <= pd.Timestamp(as_of)]
        price_series[ticker] = s.sort_index()

    # Group tickers by role
    role_tickers: dict[str, list[str]] = {}
    benchmark_tickers: list[str] = []
    for ticker, meta in universe_meta.items():
        role = meta.get("thesis_role", "unknown")
        if role in BENCHMARK_ROLES:
            benchmark_tickers.append(ticker)
        else:
            role_tickers.setdefault(role, []).append(ticker)

    results = []
    for window_label, n_days in WINDOWS.items():
        basket_returns = []

        for role, tickers in sorted(role_tickers.items()):
            available = [t for t in tickers if t in price_series and len(price_series[t]) >= 2]
            if not available:
                continue

            # Equal-weight basket: average the individual total returns
            # (simpler and more transparent than a price-weighted index)
            ticker_returns = {}
            for t in available:
                r = _total_return(price_series[t], n_days)
                if r is not None:
                    ticker_returns[t] = r

            if not ticker_returns:
                continue

            avg_return = float(np.mean(list(ticker_returns.values())))
            best_t = max(ticker_returns, key=ticker_returns.get)
            worst_t = min(ticker_returns, key=ticker_returns.get)

            # Approximate trading days in window
            end_date = price_series[available[0]].index[-1]
            start_cutoff = end_date - pd.Timedelta(days=n_days)
            trading_days = int(len(price_series[available[0]][price_series[available[0]].index >= start_cutoff]))

            basket_returns.append(BasketReturn(
                role=role,
                tickers=available,
                window=window_label,
                total_return_pct=round(avg_return, 2),
                annualized_return_pct=round(_annualize(avg_return, max(trading_days, 1)), 1),
                trading_days=trading_days,
                best_ticker=best_t,
                best_ticker_return_pct=round(ticker_returns[best_t], 2),
                worst_ticker=worst_t,
                worst_ticker_return_pct=round(ticker_returns[worst_t], 2),
            ))

        # Sort: best total return first
        basket_returns.sort(key=lambda b: b.total_return_pct, reverse=True)

        # Benchmark returns
        bench_returns = {}
        for t in benchmark_tickers:
            if t in price_series:
                r = _total_return(price_series[t], n_days)
                if r is not None:
                    bench_returns[t] = round(r, 2)

        results.append(ScorecardResult(
            window=window_label,
            basket_returns=basket_returns,
            benchmark_returns=bench_returns,
            as_of=as_of,
        ))

    return results
