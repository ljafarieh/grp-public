"""
Rolling correlations and lead-lag analysis across the universe.

Multiple-comparisons guardrails are enforced explicitly:
  - We report how many pairs were tested.
  - Lead-lag p-values are Bonferroni-corrected for the number of pairs.
  - Anything that doesn't survive correction is labeled "candidate only."
  - Correlation ≠ causation is stated in every lead-lag output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

BENCHMARK_ROLES = {"benchmark"}


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def build_returns_matrix(
    cached_data: dict[str, pd.DataFrame],
    universe_meta: dict,
    min_periods: int = 60,
) -> pd.DataFrame:
    """
    Build a date-indexed DataFrame of daily log returns for all tickers.
    Columns are ticker symbols. Rows with fewer than min_periods non-NaN
    values are not dropped — callers handle minimum windows.
    """
    series = {}
    for ticker, df in cached_data.items():
        df = df.sort_index().copy()
        df.index = pd.to_datetime(df.index)
        log_ret = np.log(df["adj_close"] / df["adj_close"].shift(1))
        series[ticker] = log_ret

    returns = pd.DataFrame(series).sort_index()
    return returns


# ---------------------------------------------------------------------------
# Rolling correlations
# ---------------------------------------------------------------------------

@dataclass
class CorrelationShift:
    ticker_a: str
    ticker_b: str
    role_a: str
    role_b: str
    corr_recent: float       # last 30 days
    corr_prior: float        # 31-60 days ago
    shift: float             # recent - prior
    n_pairs_tested: int      # for multiple-comparisons disclosure


def rolling_correlation_shifts(
    returns: pd.DataFrame,
    universe_meta: dict,
    recent_window: int = 30,
    prior_window: int = 30,
    shift_threshold: float = 0.20,
) -> list[CorrelationShift]:
    """
    For every pair of tickers, compute correlation over the last recent_window
    days vs the prior_window days. Return pairs where |shift| >= threshold,
    sorted by |shift| descending.
    """
    tickers = [t for t in returns.columns if t in universe_meta]
    if len(tickers) < 2:
        return []

    recent = returns[tickers].iloc[-recent_window:].dropna(how="all")
    prior = returns[tickers].iloc[-(recent_window + prior_window):-recent_window].dropna(how="all")

    results = []
    n_pairs = 0

    for i, ta in enumerate(tickers):
        for tb in tickers[i + 1:]:
            n_pairs += 1
            ra = recent[ta].dropna()
            rb = recent[tb].dropna()
            pa = prior[ta].dropna()
            pb = prior[tb].dropna()

            # Align on common dates
            r_common = ra.index.intersection(rb.index)
            p_common = pa.index.intersection(pb.index)

            if len(r_common) < 10 or len(p_common) < 10:
                continue

            corr_r = float(np.corrcoef(ra.loc[r_common], rb.loc[r_common])[0, 1])
            corr_p = float(np.corrcoef(pa.loc[p_common], pb.loc[p_common])[0, 1])

            if np.isnan(corr_r) or np.isnan(corr_p):
                continue

            shift = corr_r - corr_p
            if abs(shift) >= shift_threshold:
                results.append(CorrelationShift(
                    ticker_a=ta,
                    ticker_b=tb,
                    role_a=universe_meta.get(ta, {}).get("thesis_role", "unknown"),
                    role_b=universe_meta.get(tb, {}).get("thesis_role", "unknown"),
                    corr_recent=round(corr_r, 3),
                    corr_prior=round(corr_p, 3),
                    shift=round(shift, 3),
                    n_pairs_tested=n_pairs,
                ))

    # Back-fill n_pairs_tested with the final count
    for r in results:
        r.n_pairs_tested = n_pairs

    results.sort(key=lambda x: abs(x.shift), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Lead-lag
# ---------------------------------------------------------------------------

@dataclass
class LeadLagResult:
    leader: str
    follower: str
    role_leader: str
    role_follower: str
    lag_days: int
    raw_correlation: float
    raw_pvalue: float
    corrected_pvalue: float          # Bonferroni
    n_tests: int
    survives_correction: bool        # corrected_pvalue < 0.05
    n_obs: int


def lead_lag_analysis(
    returns: pd.DataFrame,
    universe_meta: dict,
    lag_days: int = 1,
    alpha: float = 0.05,
) -> list[LeadLagResult]:
    """
    Test whether ticker A's return on day T predicts ticker B's return on
    day T+lag. Reports raw and Bonferroni-corrected p-values.

    Only tests cross-role pairs (same-role lead-lag is less interesting and
    inflates the comparison count without adding thesis insight).
    """
    # Build sector-level daily returns (equal-weight average per role)
    roles = {}
    for ticker, meta in universe_meta.items():
        role = meta.get("thesis_role", "unknown")
        if role in BENCHMARK_ROLES:
            continue
        if ticker not in returns.columns:
            continue
        roles.setdefault(role, []).append(ticker)

    role_returns = {}
    for role, tickers in roles.items():
        available = [t for t in tickers if t in returns.columns]
        if available:
            role_returns[role] = returns[available].mean(axis=1)

    # Also include benchmarks as individual series
    for ticker, meta in universe_meta.items():
        if meta.get("thesis_role") in BENCHMARK_ROLES and ticker in returns.columns:
            role_returns[ticker] = returns[ticker]

    role_names = list(role_returns.keys())
    n_tests = len(role_names) * (len(role_names) - 1)  # ordered pairs

    raw_results = []
    for leader in role_names:
        for follower in role_names:
            if leader == follower:
                continue

            x = role_returns[leader].shift(lag_days)
            y = role_returns[follower]
            combined = pd.concat([x, y], axis=1).dropna()
            combined.columns = ["x", "y"]

            if len(combined) < 30:
                continue

            r, p = stats.pearsonr(combined["x"], combined["y"])
            raw_results.append((leader, follower, float(r), float(p), len(combined)))

    results = []
    for leader, follower, r, p, n in raw_results:
        corrected_p = min(p * n_tests, 1.0)  # Bonferroni
        role_l = universe_meta.get(leader, {}).get("thesis_role", leader)
        role_f = universe_meta.get(follower, {}).get("thesis_role", follower)
        results.append(LeadLagResult(
            leader=leader,
            follower=follower,
            role_leader=role_l if role_l != leader else leader,
            role_follower=role_f if role_f != follower else follower,
            lag_days=lag_days,
            raw_correlation=round(r, 3),
            raw_pvalue=round(p, 4),
            corrected_pvalue=round(corrected_p, 4),
            n_tests=n_tests,
            survives_correction=corrected_p < alpha,
            n_obs=n,
        ))

    # Sort: surviving correction first, then by |raw_correlation|
    results.sort(key=lambda x: (not x.survives_correction, -abs(x.raw_correlation)))
    return results
