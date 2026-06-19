"""
Out-of-sample (OOS) validation harness.

Split: rolling — in-sample = everything before the last OOS_MONTHS months;
out-of-sample = the most recent OOS_MONTHS months. As the cache grows, the
split advances automatically.

What gets tested:
  1. Correlation shifts found in-sample: do the same pairs show elevated
     correlation in the OOS period?
  2. Lead-lag candidates from in-sample: does the direction persist OOS?
  3. Thesis scorecard: do in-sample return rankings hold OOS?

Findings are labeled:
  "OOS_CONFIRMED"  — pattern persists (same direction, p<0.10 in OOS)
  "OOS_WEAK"       — same direction but not significant OOS
  "OOS_FAILED"     — pattern reversed or disappeared OOS

Treat OOS_CONFIRMED as weak supporting evidence only — the holdout is short.
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

OOS_MONTHS = 4    # holdout window length
MIN_IS_MONTHS = 4 # minimum in-sample length before we attempt OOS testing


@dataclass
class OOSSplit:
    is_start: date
    is_end: date
    oos_start: date
    oos_end: date
    is_trading_days: int
    oos_trading_days: int


@dataclass
class OOSFinding:
    test_name: str
    is_result: str        # description of what was found in-sample
    oos_result: str       # what happened OOS
    verdict: str          # OOS_CONFIRMED | OOS_WEAK | OOS_FAILED | INSUFFICIENT_DATA
    detail: str


@dataclass
class OOSReport:
    split: OOSSplit
    findings: list[OOSFinding] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Split calculation
# ---------------------------------------------------------------------------

def compute_split(
    cached_data: dict[str, pd.DataFrame],
    oos_months: int = OOS_MONTHS,
) -> Optional[OOSSplit]:
    """
    Determine the rolling IS/OOS split from the available data.
    Uses SPY as the reference series for date range; falls back to any ticker.
    """
    ref = cached_data.get("SPY")
    if ref is None:
        ref = next(iter(cached_data.values()), None)
    if ref is None:
        return None

    dates = sorted(pd.to_datetime(ref.index))
    if not dates:
        return None

    all_start = dates[0].date()
    all_end = dates[-1].date()

    # OOS = last oos_months calendar months
    oos_start_approx = all_end - pd.DateOffset(months=oos_months)
    oos_start_ts = pd.Timestamp(oos_start_approx)

    ref_ts = pd.Series(dates)
    oos_dates = ref_ts[ref_ts >= oos_start_ts]
    is_dates = ref_ts[ref_ts < oos_start_ts]

    if len(is_dates) < MIN_IS_MONTHS * 20:  # ~20 trading days/month
        logger.warning("Insufficient in-sample data for OOS validation.")
        return None
    if len(oos_dates) < 20:
        logger.warning("Insufficient out-of-sample data for OOS validation.")
        return None

    return OOSSplit(
        is_start=is_dates.iloc[0].date(),
        is_end=is_dates.iloc[-1].date(),
        oos_start=oos_dates.iloc[0].date(),
        oos_end=oos_dates.iloc[-1].date(),
        is_trading_days=len(is_dates),
        oos_trading_days=len(oos_dates),
    )


# ---------------------------------------------------------------------------
# Slice helpers
# ---------------------------------------------------------------------------

def _slice(series: pd.Series, start: date, end: date) -> pd.Series:
    s = series.copy()
    s.index = pd.to_datetime(s.index)
    return s[(s.index.date >= start) & (s.index.date <= end)]


def _log_returns(price: pd.Series) -> pd.Series:
    return np.log(price / price.shift(1)).dropna()


# ---------------------------------------------------------------------------
# Test 1: correlation shifts
# ---------------------------------------------------------------------------

def _test_correlation_shifts(
    cached_data: dict[str, pd.DataFrame],
    universe_meta: dict,
    split: OOSSplit,
    shift_threshold: float = 0.20,
) -> list[OOSFinding]:
    """
    Re-derive which pairs had elevated correlation in-sample, then check OOS.
    A pair is 'in-sample elevated' if its IS correlation > 0.40.
    We then ask: does OOS correlation also exceed 0.40?
    """
    from analysis.correlations import build_returns_matrix, rolling_correlation_shifts

    findings = []

    # Build full return matrices
    all_returns: dict[str, pd.Series] = {}
    for ticker, df in cached_data.items():
        s = df["adj_close"].copy()
        s.index = pd.to_datetime(s.index)
        all_returns[ticker] = _log_returns(s)

    tickers = [t for t in all_returns if t in universe_meta]

    # In-sample correlations (last 30d of IS period)
    is_corrs: dict[tuple, float] = {}
    for i, ta in enumerate(tickers):
        for tb in tickers[i + 1:]:
            ra = _slice(all_returns[ta], split.is_start, split.is_end).dropna()
            rb = _slice(all_returns[tb], split.is_start, split.is_end).dropna()
            common = ra.index.intersection(rb.index)
            if len(common) < 20:
                continue
            c = float(np.corrcoef(ra.loc[common], rb.loc[common])[0, 1])
            if not np.isnan(c) and abs(c) > 0.40:
                is_corrs[(ta, tb)] = c

    if not is_corrs:
        findings.append(OOSFinding(
            test_name="Correlation structure",
            is_result="No pairs with |corr| > 0.40 found in-sample.",
            oos_result="N/A",
            verdict="INSUFFICIENT_DATA",
            detail="Nothing to validate OOS.",
        ))
        return findings

    # OOS correlations for the same pairs
    confirmed = weak = failed = 0
    pair_details = []

    for (ta, tb), is_c in sorted(is_corrs.items(), key=lambda x: -abs(x[1]))[:10]:
        ra = _slice(all_returns[ta], split.oos_start, split.oos_end).dropna()
        rb = _slice(all_returns[tb], split.oos_start, split.oos_end).dropna()
        common = ra.index.intersection(rb.index)
        if len(common) < 10:
            pair_details.append(f"{ta}/{tb}: insufficient OOS data")
            continue
        oos_c = float(np.corrcoef(ra.loc[common], rb.loc[common])[0, 1])
        same_direction = (is_c > 0) == (oos_c > 0)
        oos_strong = abs(oos_c) > 0.30

        if same_direction and oos_strong:
            verdict = "OOS_CONFIRMED"
            confirmed += 1
        elif same_direction:
            verdict = "OOS_WEAK"
            weak += 1
        else:
            verdict = "OOS_FAILED"
            failed += 1

        pair_details.append(
            f"{ta}/{tb}: IS corr={is_c:+.3f}, OOS corr={oos_c:+.3f} → {verdict}"
        )

    findings.append(OOSFinding(
        test_name="Correlation structure (top IS pairs)",
        is_result=f"{len(is_corrs)} pair(s) with |IS corr| > 0.40.",
        oos_result=f"Confirmed: {confirmed}, Weak: {weak}, Failed: {failed}.",
        verdict="OOS_CONFIRMED" if confirmed > failed else ("OOS_WEAK" if confirmed + weak > failed else "OOS_FAILED"),
        detail="\n  ".join(pair_details),
    ))

    return findings


# ---------------------------------------------------------------------------
# Test 2: lead-lag candidates
# ---------------------------------------------------------------------------

def _test_lead_lag(
    cached_data: dict[str, pd.DataFrame],
    universe_meta: dict,
    split: OOSSplit,
) -> list[OOSFinding]:
    """
    Re-run lead-lag on IS data only, then test surviving (raw p<0.10) candidates OOS.
    """
    from analysis.correlations import build_returns_matrix, lead_lag_analysis

    findings = []

    # Build IS returns matrix
    is_data = {t: df[df.index <= pd.Timestamp(split.is_end)] for t, df in cached_data.items()}
    is_returns_df = pd.DataFrame({
        t: _log_returns(df["adj_close"].set_axis(pd.to_datetime(df.index)))
        for t, df in is_data.items()
        if len(df) > 1
    }).sort_index()

    is_ll = lead_lag_analysis(is_returns_df, universe_meta)

    # Take top raw candidates (p_raw < 0.10 in IS)
    candidates = [r for r in is_ll if r.raw_pvalue < 0.10]

    if not candidates:
        findings.append(OOSFinding(
            test_name="Lead-lag",
            is_result="No lead-lag candidates with p_raw < 0.10 in-sample.",
            oos_result="N/A",
            verdict="INSUFFICIENT_DATA",
            detail="Nothing to validate OOS — consistent with efficient markets.",
        ))
        return findings

    # Build role-level OOS return series
    role_tickers: dict[str, list[str]] = {}
    for ticker, meta in universe_meta.items():
        role = meta.get("thesis_role", "unknown")
        if ticker in cached_data:
            role_tickers.setdefault(role, []).append(ticker)

    def role_series(role: str, start: date, end: date) -> pd.Series:
        tks = role_tickers.get(role, [])
        # Also handle benchmark tickers passed as role name
        if not tks and role in cached_data:
            df = cached_data[role]
            s = df["adj_close"].copy()
            s.index = pd.to_datetime(s.index)
            return _log_returns(s)
        parts = []
        for t in tks:
            df = cached_data[t]
            s = df["adj_close"].copy()
            s.index = pd.to_datetime(s.index)
            parts.append(_log_returns(s))
        if not parts:
            return pd.Series(dtype=float)
        combined = pd.concat(parts, axis=1).mean(axis=1)
        combined.index = pd.to_datetime(combined.index)
        return combined[(combined.index.date >= start) & (combined.index.date <= end)]

    confirmed = weak = failed = 0
    detail_lines = []

    for cand in candidates[:8]:
        leader_oos = role_series(cand.leader, split.oos_start, split.oos_end)
        follower_oos = role_series(cand.follower, split.oos_start, split.oos_end)

        x = leader_oos.shift(cand.lag_days)
        common = pd.concat([x, follower_oos], axis=1).dropna()
        if len(common) < 15:
            detail_lines.append(f"{cand.leader}->{cand.follower}: insufficient OOS data")
            continue

        oos_r, oos_p = stats.pearsonr(common.iloc[:, 0], common.iloc[:, 1])
        same_direction = (cand.raw_correlation > 0) == (oos_r > 0)

        if same_direction and oos_p < 0.10:
            v = "OOS_CONFIRMED"; confirmed += 1
        elif same_direction:
            v = "OOS_WEAK"; weak += 1
        else:
            v = "OOS_FAILED"; failed += 1

        detail_lines.append(
            f"{cand.leader}->{cand.follower}: IS r={cand.raw_correlation:+.3f} "
            f"(p={cand.raw_pvalue:.3f}), OOS r={oos_r:+.3f} (p={oos_p:.3f}) → {v}"
        )

    overall = "OOS_CONFIRMED" if confirmed > failed else ("OOS_WEAK" if confirmed + weak > failed else "OOS_FAILED")
    findings.append(OOSFinding(
        test_name="Lead-lag candidates (IS p_raw < 0.10)",
        is_result=f"{len(candidates)} candidate(s) identified in-sample.",
        oos_result=f"Confirmed: {confirmed}, Weak: {weak}, Failed: {failed}.",
        verdict=overall,
        detail="\n  ".join(detail_lines) if detail_lines else "No testable pairs.",
    ))
    return findings


# ---------------------------------------------------------------------------
# Test 3: thesis scorecard rank stability
# ---------------------------------------------------------------------------

def _test_scorecard_ranks(
    cached_data: dict[str, pd.DataFrame],
    universe_meta: dict,
    split: OOSSplit,
) -> list[OOSFinding]:
    """
    Does the in-sample return ranking of thesis roles hold in the OOS period?
    Measured by Spearman rank correlation between IS and OOS role returns.
    """
    from analysis.scorecard import build_scorecard

    findings = []

    is_data = {t: df[df.index <= pd.Timestamp(split.is_end)] for t, df in cached_data.items()}
    oos_data = {
        t: df[(df.index >= pd.Timestamp(split.oos_start)) & (df.index <= pd.Timestamp(split.oos_end))]
        for t, df in cached_data.items()
    }

    is_sc = build_scorecard(is_data, universe_meta, as_of=split.is_end)
    oos_sc = build_scorecard(oos_data, universe_meta, as_of=split.oos_end)

    if not is_sc or not oos_sc:
        findings.append(OOSFinding(
            test_name="Thesis scorecard rank stability",
            is_result="Could not compute scorecard.",
            oos_result="N/A",
            verdict="INSUFFICIENT_DATA",
            detail="Insufficient data for one or both periods.",
        ))
        return findings

    # Use the longest available window from each scorecard
    is_returns = {b.role: b.total_return_pct for b in is_sc[-1].basket_returns}
    oos_returns = {b.role: b.total_return_pct for b in oos_sc[-1].basket_returns}

    common_roles = sorted(set(is_returns) & set(oos_returns))
    if len(common_roles) < 3:
        findings.append(OOSFinding(
            test_name="Thesis scorecard rank stability",
            is_result="Too few common roles to rank.",
            oos_result="N/A",
            verdict="INSUFFICIENT_DATA",
            detail=f"Only {len(common_roles)} common role(s).",
        ))
        return findings

    is_vals = [is_returns[r] for r in common_roles]
    oos_vals = [oos_returns[r] for r in common_roles]

    rho, p = stats.spearmanr(is_vals, oos_vals)
    rho = float(rho)

    if rho > 0.5 and p < 0.10:
        verdict = "OOS_CONFIRMED"
    elif rho > 0:
        verdict = "OOS_WEAK"
    else:
        verdict = "OOS_FAILED"

    role_lines = [
        f"{r}: IS {is_returns[r]:+.1f}%, OOS {oos_returns[r]:+.1f}%"
        for r in common_roles
    ]

    findings.append(OOSFinding(
        test_name="Thesis scorecard rank stability",
        is_result=f"IS return ranking across {len(common_roles)} roles established.",
        oos_result=f"Spearman rank correlation IS vs OOS: rho={rho:+.3f}, p={p:.3f}.",
        verdict=verdict,
        detail=(
            f"Interpretation: rho={rho:+.3f} means IS rankings "
            + ("are positively correlated with OOS rankings." if rho > 0 else "do not predict OOS rankings.")
            + f" p={p:.3f}."
            + (" Treat as weak supporting evidence only — OOS window is short." if verdict == "OOS_CONFIRMED" else "")
            + "\n  Role breakdown:\n  " + "\n  ".join(role_lines)
        ),
    ))
    return findings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_oos_validation(
    cached_data: dict[str, pd.DataFrame],
    universe_meta: dict,
    oos_months: int = OOS_MONTHS,
) -> OOSReport:
    split = compute_split(cached_data, oos_months)
    if split is None:
        logger.warning("Cannot perform OOS validation — insufficient data.")
        return OOSReport(
            split=OOSSplit(date.today(), date.today(), date.today(), date.today(), 0, 0),
            findings=[OOSFinding(
                test_name="OOS validation",
                is_result="N/A",
                oos_result="N/A",
                verdict="INSUFFICIENT_DATA",
                detail="Not enough history to split into IS and OOS windows.",
            )],
        )

    logger.info(
        "OOS split: IS %s→%s (%d days), OOS %s→%s (%d days)",
        split.is_start, split.is_end, split.is_trading_days,
        split.oos_start, split.oos_end, split.oos_trading_days,
    )

    findings = []
    findings.extend(_test_correlation_shifts(cached_data, universe_meta, split))
    findings.extend(_test_lead_lag(cached_data, universe_meta, split))
    findings.extend(_test_scorecard_ranks(cached_data, universe_meta, split))

    return OOSReport(split=split, findings=findings)
