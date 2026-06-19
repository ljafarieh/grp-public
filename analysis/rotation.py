"""
Sector rotation detection: compares each thesis-role basket's return rank
over the last 30 days vs the prior 30 days.

A role jumping from bottom-half to top-half (or vice versa) is flagged as
a rotation candidate. This is descriptive, not predictive — rank shifts are
observations, not signals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

BENCHMARK_ROLES = {"benchmark"}


@dataclass
class RotationSignal:
    role: str
    tickers: list[str]
    recent_return_pct: float     # last 30 days
    prior_return_pct: float      # 31-60 days ago
    recent_rank: int             # 1 = best among thesis roles
    prior_rank: int
    rank_shift: int              # prior_rank - recent_rank (positive = moved up)
    n_roles: int
    flagged: bool                # rank shifted by more than half the field


def detect_rotation(
    cached_data: dict[str, pd.DataFrame],
    universe_meta: dict,
    recent_days: int = 30,
    prior_days: int = 30,
    as_of: Optional[date] = None,
) -> list[RotationSignal]:
    """
    Compute 30d return for each thesis-role basket in two consecutive windows
    and rank them. Flag roles where rank shifted by > n_roles/2.
    """
    as_of_ts = pd.Timestamp(as_of or date.today() - timedelta(days=1))

    # Build adj_close per ticker
    price: dict[str, pd.Series] = {}
    for ticker, df in cached_data.items():
        s = df["adj_close"].copy()
        s.index = pd.to_datetime(s.index)
        s = s[s.index <= as_of_ts].sort_index()
        price[ticker] = s

    # Group by role (exclude benchmarks)
    role_tickers: dict[str, list[str]] = {}
    for ticker, meta in universe_meta.items():
        role = meta.get("thesis_role", "unknown")
        if role in BENCHMARK_ROLES:
            continue
        if ticker in price and len(price[ticker]) >= 2:
            role_tickers.setdefault(role, []).append(ticker)

    def window_return(series: pd.Series, end_ts: pd.Timestamp, n_days: int) -> Optional[float]:
        start_ts = end_ts - pd.Timedelta(days=n_days)
        window = series[(series.index > start_ts) & (series.index <= end_ts)]
        if len(window) < 2:
            return None
        return float((window.iloc[-1] / window.iloc[0] - 1) * 100)

    recent_end = as_of_ts
    prior_end = as_of_ts - pd.Timedelta(days=recent_days)

    role_recent: dict[str, float] = {}
    role_prior: dict[str, float] = {}
    role_ticker_map: dict[str, list[str]] = {}

    for role, tickers in role_tickers.items():
        r_vals, p_vals = [], []
        for t in tickers:
            r = window_return(price[t], recent_end, recent_days)
            p = window_return(price[t], prior_end, prior_days)
            if r is not None:
                r_vals.append(r)
            if p is not None:
                p_vals.append(p)

        if r_vals and p_vals:
            role_recent[role] = float(np.mean(r_vals))
            role_prior[role] = float(np.mean(p_vals))
            role_ticker_map[role] = tickers

    if len(role_recent) < 2:
        return []

    # Rank: rank 1 = highest return
    roles_sorted_recent = sorted(role_recent, key=role_recent.get, reverse=True)
    roles_sorted_prior = sorted(role_prior, key=role_prior.get, reverse=True)

    recent_rank = {r: i + 1 for i, r in enumerate(roles_sorted_recent)}
    prior_rank = {r: i + 1 for i, r in enumerate(roles_sorted_prior)}
    n_roles = len(role_recent)

    signals = []
    for role in role_recent:
        rr = recent_rank[role]
        pr = prior_rank[role]
        shift = pr - rr   # positive = moved up in rank
        flagged = abs(shift) > n_roles / 2

        signals.append(RotationSignal(
            role=role,
            tickers=role_ticker_map.get(role, []),
            recent_return_pct=round(role_recent[role], 2),
            prior_return_pct=round(role_prior[role], 2),
            recent_rank=rr,
            prior_rank=pr,
            rank_shift=shift,
            n_roles=n_roles,
            flagged=flagged,
        ))

    # Sort by |rank_shift| descending
    signals.sort(key=lambda s: abs(s.rank_shift), reverse=True)
    return signals
