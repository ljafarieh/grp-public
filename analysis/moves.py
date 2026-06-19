"""
Move detection: flags daily price/volume moves that are notable relative to
each ticker's own recent volatility.

Approach:
  - Daily return z-score vs trailing N-day realized volatility. A large-cap
    with normally-low vol and a small-cap with high vol are judged against
    their own baselines, so neither gets flagged every day or never.
  - Volume spike: today's volume vs trailing N-day average.

Both thresholds are config-driven (analysis.vol_window,
analysis.move_zscore_threshold, analysis.volume_spike_multiplier).

No lookahead bias: all calculations at date T use only data through T-1
for the rolling window, then compare against day T's actual value.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MoveSignal:
    ticker: str
    signal_date: date
    daily_return_pct: float          # e.g. +4.23
    zscore: float                    # return / trailing vol (annualized units cancel)
    trailing_vol_annualized: float   # realized vol used as baseline
    volume_ratio: float              # today / 20d avg volume; NaN if volume missing
    price_flagged: bool              # |zscore| >= threshold
    volume_flagged: bool             # volume_ratio >= multiplier
    close: float
    prev_close: float
    tags: list[str] = field(default_factory=list)  # populated by attribution


def detect_moves(
    df: pd.DataFrame,
    ticker: str,
    as_of: Optional[date] = None,
    vol_window: int = 20,
    zscore_threshold: float = 2.0,
    volume_multiplier: float = 2.0,
) -> list[MoveSignal]:
    """
    Scan df for notable moves. If as_of is given, only returns the signal
    for that single date (used in daily pipeline). If None, returns signals
    for every date in df (used for historical scan).

    as_of is the date we're evaluating. The rolling window covers the
    vol_window trading days *before* as_of, enforcing no lookahead bias.
    """
    if df is None or len(df) < vol_window + 1:
        logger.debug("%s: insufficient data for move detection (%d rows)", ticker, len(df) if df is not None else 0)
        return []

    df = df.sort_index().copy()
    df.index = pd.to_datetime(df.index)

    # Daily log returns
    df["log_ret"] = np.log(df["adj_close"] / df["adj_close"].shift(1))

    # Trailing realized vol (annualized): std of log returns over window,
    # computed using only data up to T-1 (shift ensures no lookahead).
    # min_periods=vol_window ensures we don't emit signals on sparse early data.
    df["trail_vol"] = (
        df["log_ret"].shift(1)
        .rolling(window=vol_window, min_periods=vol_window)
        .std()
        * np.sqrt(252)
    )

    # Daily vol in same units as log_ret (un-annualize for z-score)
    df["daily_vol"] = df["trail_vol"] / np.sqrt(252)

    # Z-score: today's return / trailing daily vol
    df["zscore"] = df["log_ret"] / df["daily_vol"]

    # Trailing volume average (again shift(1) → no lookahead)
    df["vol_avg"] = (
        df["volume"].shift(1)
        .rolling(window=vol_window, min_periods=vol_window)
        .mean()
    )
    df["vol_ratio"] = df["volume"] / df["vol_avg"]

    # Restrict to as_of if specified
    if as_of is not None:
        target = pd.Timestamp(as_of)
        df = df[df.index == target]
        if df.empty:
            logger.debug("%s: no data for as_of=%s", ticker, as_of)
            return []

    signals = []
    for ts, row in df.iterrows():
        if pd.isna(row["zscore"]) or pd.isna(row["trail_vol"]):
            continue

        price_flagged = abs(row["zscore"]) >= zscore_threshold
        vol_ratio = row["vol_ratio"] if not pd.isna(row["vol_ratio"]) else float("nan")
        volume_flagged = (not np.isnan(vol_ratio)) and (vol_ratio >= volume_multiplier)

        if not (price_flagged or volume_flagged):
            continue

        prev_close_val = row["adj_close"] / np.exp(row["log_ret"])

        signals.append(
            MoveSignal(
                ticker=ticker,
                signal_date=ts.date(),
                daily_return_pct=round(np.expm1(row["log_ret"]) * 100, 2),
                zscore=round(float(row["zscore"]), 2),
                trailing_vol_annualized=round(float(row["trail_vol"]) * 100, 1),
                volume_ratio=round(float(vol_ratio), 2) if not np.isnan(vol_ratio) else float("nan"),
                price_flagged=price_flagged,
                volume_flagged=volume_flagged,
                close=round(float(row["adj_close"]), 2),
                prev_close=round(float(prev_close_val), 2),
            )
        )

    return signals


def detect_moves_universe(
    cached_data: dict[str, pd.DataFrame],
    as_of: Optional[date] = None,
    vol_window: int = 20,
    zscore_threshold: float = 2.0,
    volume_multiplier: float = 2.0,
) -> list[MoveSignal]:
    """
    Run detect_moves across all tickers in cached_data.
    Returns a flat list of MoveSignals, sorted by |zscore| descending.
    """
    all_signals = []
    for ticker, df in cached_data.items():
        sigs = detect_moves(
            df, ticker, as_of,
            vol_window, zscore_threshold, volume_multiplier,
        )
        all_signals.extend(sigs)

    all_signals.sort(key=lambda s: abs(s.zscore), reverse=True)
    return all_signals
