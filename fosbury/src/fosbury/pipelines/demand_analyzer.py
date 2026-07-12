"""Demand trend and outlier analysis for GRP arbitrage signals.

Reads the demand table from SQLite and produces:
  - Hourly rolling baselines (7-day rolling mean + std dev per hour-of-day)
  - Z-score anomaly detection (flags rows where demand > 2.0 sigma above baseline)
  - Week-over-week % change per respondent
  - Peak demand records per respondent
  - A ranked signal table: respondent → ticker → signal_strength

The output is purely informational research.  Nothing here constitutes
financial advice or a trading recommendation.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ZSCORE_THRESHOLD = 2.0   # flag rows this many std devs above the rolling mean
MIN_ROWS_FOR_BASELINE = 24  # need at least 24 hrs of history to compute a baseline


@dataclass
class DemandSignal:
    """A single detected anomaly or trend signal."""

    respondent: str
    company_name: str
    ticker: str
    signal_type: str          # "SPIKE", "SUSTAINED_GROWTH", "NEW_PEAK", "WOW_SURGE"
    timestamp_utc: str
    value_mwh: float
    baseline_mwh: float
    zscore: float
    pct_above_baseline: float
    notes: str = ""

    @property
    def signal_strength(self) -> float:
        """Higher = stronger signal. Used for ranking."""
        return round(self.zscore * (self.pct_above_baseline / 100), 2)


@dataclass
class AnalysisReport:
    """Full output from one analysis run."""

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    signals: list[DemandSignal] = field(default_factory=list)
    summary: dict[str, object] = field(default_factory=dict)

    @property
    def traded_signals(self) -> list[DemandSignal]:
        """Signals for respondents with a known stock ticker."""
        return [s for s in self.signals if s.ticker]

    def ranked(self) -> list[DemandSignal]:
        return sorted(self.signals, key=lambda s: s.signal_strength, reverse=True)


def analyze(db_path: Path) -> AnalysisReport:
    """Run full trend + outlier analysis on the demand table.

    Args:
        db_path: Path to the fosbury SQLite database.

    Returns:
        :class:`AnalysisReport` with all detected signals.
    """
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """
        SELECT timestamp_utc, respondent, respondent_name,
               company_name, ticker, CAST(value_mwh AS REAL) AS value_mwh
        FROM demand
        ORDER BY respondent, timestamp_utc
        """,
        conn,
        parse_dates=["timestamp_utc"],
    )
    conn.close()

    if df.empty:
        return AnalysisReport(summary={"error": "No demand data in database."})

    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["hour_of_day"] = df["timestamp_utc"].dt.hour
    df["date"] = df["timestamp_utc"].dt.date

    report = AnalysisReport()
    signals: list[DemandSignal] = []

    for respondent, grp in df.groupby("respondent"):
        grp = grp.sort_values("timestamp_utc").copy()
        company_name = grp["company_name"].iloc[0] or ""
        ticker = grp["ticker"].iloc[0] or ""

        if len(grp) < MIN_ROWS_FOR_BASELINE:
            continue

        # ── Rolling baseline: 7-day rolling mean + std per hour-of-day ──────
        grp["rolling_mean"] = (
            grp["value_mwh"]
            .rolling(window=min(168, len(grp)), min_periods=MIN_ROWS_FOR_BASELINE)
            .mean()
        )
        grp["rolling_std"] = (
            grp["value_mwh"]
            .rolling(window=min(168, len(grp)), min_periods=MIN_ROWS_FOR_BASELINE)
            .std()
        )
        grp["zscore"] = (grp["value_mwh"] - grp["rolling_mean"]) / grp["rolling_std"].replace(0, float("nan"))

        # ── Spike detection ──────────────────────────────────────────────────
        spikes = grp[grp["zscore"] > ZSCORE_THRESHOLD].copy()
        for _, row in spikes.iterrows():
            pct_above = ((row["value_mwh"] - row["rolling_mean"]) / row["rolling_mean"]) * 100
            signals.append(DemandSignal(
                respondent=respondent,
                company_name=company_name,
                ticker=ticker,
                signal_type="SPIKE",
                timestamp_utc=str(row["timestamp_utc"]),
                value_mwh=round(row["value_mwh"], 1),
                baseline_mwh=round(row["rolling_mean"], 1),
                zscore=round(row["zscore"], 2),
                pct_above_baseline=round(pct_above, 1),
                notes=f"Demand {pct_above:.1f}% above 7-day rolling mean",
            ))

        # ── New peak detection ───────────────────────────────────────────────
        peak_row = grp.loc[grp["value_mwh"].idxmax()]
        # Only flag as NEW_PEAK if it's in the latest 25% of the time window
        cutoff_idx = int(len(grp) * 0.75)
        if grp.index.get_loc(peak_row.name) >= cutoff_idx:
            baseline = grp["rolling_mean"].iloc[cutoff_idx]
            if pd.notna(baseline) and baseline > 0:
                pct_above = ((peak_row["value_mwh"] - baseline) / baseline) * 100
                signals.append(DemandSignal(
                    respondent=respondent,
                    company_name=company_name,
                    ticker=ticker,
                    signal_type="NEW_PEAK",
                    timestamp_utc=str(peak_row["timestamp_utc"]),
                    value_mwh=round(peak_row["value_mwh"], 1),
                    baseline_mwh=round(baseline, 1),
                    zscore=round(peak_row["zscore"] if pd.notna(peak_row["zscore"]) else 0, 2),
                    pct_above_baseline=round(pct_above, 1),
                    notes="All-time high in current dataset window",
                ))

        # ── Week-over-week trend ─────────────────────────────────────────────
        daily = grp.groupby("date")["value_mwh"].mean().reset_index()
        daily.columns = ["date", "avg_mwh"]
        if len(daily) >= 14:
            last_7 = daily.tail(7)["avg_mwh"].mean()
            prev_7 = daily.iloc[-14:-7]["avg_mwh"].mean()
            if prev_7 > 0:
                wow_pct = ((last_7 - prev_7) / prev_7) * 100
                if wow_pct > 5.0:  # only flag meaningful growth
                    latest = grp.tail(1).iloc[0]
                    signals.append(DemandSignal(
                        respondent=respondent,
                        company_name=company_name,
                        ticker=ticker,
                        signal_type="WOW_SURGE",
                        timestamp_utc=str(latest["timestamp_utc"]),
                        value_mwh=round(last_7, 1),
                        baseline_mwh=round(prev_7, 1),
                        zscore=0.0,
                        pct_above_baseline=round(wow_pct, 1),
                        notes=f"Last-7-day avg {wow_pct:.1f}% above prior-7-day avg",
                    ))

        # ── Sustained growth (linear trend slope) ────────────────────────────
        if len(daily) >= 7:
            daily["day_num"] = range(len(daily))
            slope = _linear_slope(daily["day_num"].values, daily["avg_mwh"].values)
            slope_pct = (slope / daily["avg_mwh"].mean()) * 100
            if slope_pct > 1.0:  # > 1% per day growth trend
                signals.append(DemandSignal(
                    respondent=respondent,
                    company_name=company_name,
                    ticker=ticker,
                    signal_type="SUSTAINED_GROWTH",
                    timestamp_utc=str(daily["date"].iloc[-1]),
                    value_mwh=round(daily["avg_mwh"].iloc[-1], 1),
                    baseline_mwh=round(daily["avg_mwh"].iloc[0], 1),
                    zscore=0.0,
                    pct_above_baseline=round(slope_pct, 2),
                    notes=f"Linear trend: +{slope:.0f} MWh/day ({slope_pct:.2f}%/day growth)",
                ))

    report.signals = signals
    report.summary = {
        "respondents_analyzed": df["respondent"].nunique(),
        "total_rows": len(df),
        "date_range": f"{df['timestamp_utc'].min().date()} → {df['timestamp_utc'].max().date()}",
        "signals_found": len(signals),
        "traded_signals": len([s for s in signals if s.ticker]),
    }
    return report


def _linear_slope(x, y) -> float:
    """Least-squares slope of y ~ x."""
    import numpy as np
    if len(x) < 2:
        return 0.0
    coeffs = np.polyfit(x, y, 1)
    return float(coeffs[0])


def report_to_df(report: AnalysisReport) -> pd.DataFrame:
    """Convert :class:`AnalysisReport` signals to a flat DataFrame for export."""
    if not report.signals:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            "signal_type": s.signal_type,
            "signal_strength": s.signal_strength,
            "respondent": s.respondent,
            "company_name": s.company_name,
            "ticker": s.ticker,
            "timestamp_utc": s.timestamp_utc,
            "value_mwh": s.value_mwh,
            "baseline_mwh": s.baseline_mwh,
            "zscore": s.zscore,
            "pct_above_baseline": s.pct_above_baseline,
            "notes": s.notes,
        }
        for s in report.ranked()
    ])
