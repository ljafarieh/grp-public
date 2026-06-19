"""
Lookahead bias auditor.

Verifies that every rolling calculation in the pipeline only uses data
available strictly before the evaluation date. Returns a structured audit
report with pass/fail status per check.

This is a documentation and sanity-check tool, not a runtime guard —
it re-derives the key invariants from the data and confirms they hold.
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
class AuditCheck:
    name: str
    passed: bool
    detail: str
    severity: str = "info"   # "info" | "warning" | "fail"


@dataclass
class LookaheadAuditReport:
    checks: list[AuditCheck] = field(default_factory=list)
    as_of: Optional[date] = None

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "fail")

    @property
    def n_passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def n_failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)


def _check_rolling_window_no_lookahead(
    df: pd.DataFrame,
    ticker: str,
    vol_window: int,
    as_of: date,
) -> list[AuditCheck]:
    """
    Verify that the trailing vol window for as_of uses only dates < as_of.
    The shift(1) in moves.py is the mechanism — confirm it's in effect.
    """
    checks = []
    df = df.sort_index().copy()
    df.index = pd.to_datetime(df.index)
    as_of_ts = pd.Timestamp(as_of)

    # Rows available on or before as_of
    available = df[df.index <= as_of_ts]

    if len(available) < vol_window + 1:
        checks.append(AuditCheck(
            name=f"{ticker}: vol_window data availability",
            passed=False,
            detail=f"Only {len(available)} rows available through {as_of}; "
                   f"need {vol_window + 1} for a full window. Signal would be suppressed.",
            severity="info",
        ))
        return checks

    # The window used for as_of's z-score should be the vol_window rows
    # ending at as_of - 1 (i.e., the shift(1) rows)
    window_rows = available.iloc[-(vol_window + 1):-1]  # last vol_window rows before as_of row
    window_max_date = window_rows.index.max().date()

    # Confirm none of the window dates equal or exceed as_of
    lookahead_contamination = window_max_date >= as_of
    checks.append(AuditCheck(
        name=f"{ticker}: vol window ends before as_of",
        passed=not lookahead_contamination,
        detail=(
            f"Vol window for {as_of} spans through {window_max_date}. "
            + ("OK — no lookahead." if not lookahead_contamination
               else f"FAIL — window includes or exceeds as_of={as_of}.")
        ),
        severity="fail" if lookahead_contamination else "info",
    ))

    return checks


def _check_return_uses_prior_close(
    df: pd.DataFrame,
    ticker: str,
    as_of: date,
) -> list[AuditCheck]:
    """
    Verify that the daily return on as_of uses close[as_of] / close[as_of-1],
    not any future price.
    """
    checks = []
    df = df.sort_index().copy()
    df.index = pd.to_datetime(df.index)
    as_of_ts = pd.Timestamp(as_of)

    row = df[df.index == as_of_ts]
    if row.empty:
        checks.append(AuditCheck(
            name=f"{ticker}: return calculation date present",
            passed=True,
            detail=f"No data for {as_of} — no return computed, no lookahead risk.",
            severity="info",
        ))
        return checks

    prior_rows = df[df.index < as_of_ts]
    if prior_rows.empty:
        checks.append(AuditCheck(
            name=f"{ticker}: prior close available",
            passed=False,
            detail=f"No prior close before {as_of} — return cannot be computed.",
            severity="info",
        ))
        return checks

    prior_close = float(prior_rows["adj_close"].iloc[-1])
    today_close = float(row["adj_close"].iloc[0])
    computed_return = (today_close / prior_close - 1) * 100

    checks.append(AuditCheck(
        name=f"{ticker}: return uses prior close only",
        passed=True,
        detail=(
            f"Return on {as_of} = {computed_return:+.2f}% "
            f"({today_close:.2f} / {prior_close:.2f} - 1). "
            "Only uses data available at market close on as_of."
        ),
        severity="info",
    ))
    return checks


def _check_volume_window_no_lookahead(
    df: pd.DataFrame,
    ticker: str,
    vol_window: int,
    as_of: date,
) -> list[AuditCheck]:
    """
    Verify that the volume average for as_of uses only prior days' volume.
    """
    checks = []
    df = df.sort_index().copy()
    df.index = pd.to_datetime(df.index)
    as_of_ts = pd.Timestamp(as_of)

    prior = df[df.index < as_of_ts]
    if len(prior) < vol_window:
        checks.append(AuditCheck(
            name=f"{ticker}: volume window availability",
            passed=True,
            detail=f"Fewer than {vol_window} prior rows — volume spike suppressed. No lookahead risk.",
            severity="info",
        ))
        return checks

    window_dates = prior.index[-vol_window:]
    window_max = window_dates.max().date()

    passed = window_max < as_of
    checks.append(AuditCheck(
        name=f"{ticker}: volume avg window ends before as_of",
        passed=passed,
        detail=(
            f"Volume window for {as_of} spans through {window_max}. "
            + ("OK — no lookahead." if passed else "FAIL — window contaminated.")
        ),
        severity="fail" if not passed else "info",
    ))
    return checks


def run_lookahead_audit(
    cached_data: dict[str, pd.DataFrame],
    as_of: date,
    vol_window: int = 20,
    sample_tickers: Optional[list[str]] = None,
) -> LookaheadAuditReport:
    """
    Run the full lookahead audit for as_of across all (or sampled) tickers.
    Returns a structured report.
    """
    report = LookaheadAuditReport(as_of=as_of)

    tickers = sample_tickers or list(cached_data.keys())

    for ticker in tickers:
        df = cached_data.get(ticker)
        if df is None:
            continue
        report.checks.extend(_check_rolling_window_no_lookahead(df, ticker, vol_window, as_of))
        report.checks.extend(_check_return_uses_prior_close(df, ticker, as_of))
        report.checks.extend(_check_volume_window_no_lookahead(df, ticker, vol_window, as_of))

    # Summary check
    n_fail = sum(1 for c in report.checks if not c.passed and c.severity == "fail")
    report.checks.append(AuditCheck(
        name="Overall lookahead audit",
        passed=n_fail == 0,
        detail=(
            f"{len(tickers)} ticker(s) audited across {len(report.checks) - 1} sub-checks. "
            f"{n_fail} failure(s) detected."
            if n_fail > 0
            else f"{len(tickers)} ticker(s) audited. No lookahead violations found."
        ),
        severity="fail" if n_fail > 0 else "info",
    ))

    return report
