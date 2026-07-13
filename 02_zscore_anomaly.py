"""
Snippet 02 — Detecting demand anomalies with rolling Z-score
-------------------------------------------------------------
Once you have historical demand data, you can flag statistically
unusual readings. The intuition: if a utility's demand is 3 standard
deviations above its 7-day rolling average, something unusual is
happening — a heatwave, a large new load connecting, or a data center
cluster coming online.

GRP uses this to surface demand spikes that might precede a utility's
public announcement about load growth. When the physical signal shows
up in the data before the press release, that's the edge.

This snippet works on a CSV produced by snippet 01, or any DataFrame
with [timestamp_utc, respondent, value_mwh] columns.

Requirements:
    pip install pandas
"""

import pandas as pd

ZSCORE_THRESHOLD  = 2.0   # flag anything more than 2σ above the rolling mean
WINDOW_HOURS      = 168   # 7 days of hourly data as the baseline window
MIN_ROWS_BASELINE = 24    # need at least 24 hours before computing stats


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a demand DataFrame, return rows that are statistical outliers.

    Adds columns: rolling_mean, rolling_std, zscore, signal_type
    """
    df = df.sort_values("timestamp_utc").copy()
    df["rolling_mean"] = (
        df["value_mwh"]
        .rolling(window=WINDOW_HOURS, min_periods=MIN_ROWS_BASELINE)
        .mean()
    )
    df["rolling_std"] = (
        df["value_mwh"]
        .rolling(window=WINDOW_HOURS, min_periods=MIN_ROWS_BASELINE)
        .std()
    )

    # Z-score: how many standard deviations above the rolling mean?
    df["zscore"] = (df["value_mwh"] - df["rolling_mean"]) / df["rolling_std"].replace(0, float("nan"))

    # Classify signal type
    df["signal_type"] = None
    df.loc[df["zscore"] >= ZSCORE_THRESHOLD, "signal_type"] = "SPIKE"

    # Week-over-week surge: last 7-day avg vs prior 7-day avg
    df["avg_last7"]  = df["value_mwh"].rolling(168).mean()
    df["avg_prior7"] = df["value_mwh"].rolling(168).mean().shift(168)
    df.loc[
        (df["avg_last7"] / df["avg_prior7"] - 1) > 0.05,
        "signal_type"
    ] = "WOW_SURGE"

    return df[df["signal_type"].notna()].copy()


def summarize(signals: pd.DataFrame) -> None:
    if signals.empty:
        print("No anomalies detected.")
        return

    print(f"\n{'BA':<6} {'Ticker':<6} {'Timestamp':<22} {'MWh':>8} {'Baseline':>8} {'Z':>6} {'Type'}")
    print("-" * 70)
    for _, row in signals.sort_values("zscore", ascending=False).head(20).iterrows():
        print(
            f"{row['respondent']:<6} "
            f"{row.get('ticker', ''):<6} "
            f"{str(row['timestamp_utc'])[:19]:<22} "
            f"{row['value_mwh']:>8,.0f} "
            f"{row['rolling_mean']:>8,.0f} "
            f"{row['zscore']:>6.2f} "
            f"{row['signal_type']}"
        )


if __name__ == "__main__":
    # Generate synthetic demand data to demo the detector
    import numpy as np

    rng = pd.date_range("2026-01-01", periods=24 * 30, freq="h", tz="UTC")
    base = 15_000 + 2_000 * np.sin(2 * np.pi * rng.hour / 24)  # daily cycle
    noise = np.random.normal(0, 300, len(rng))

    values = base + noise
    # Inject a fake spike on day 20
    spike_idx = 24 * 20 + 14
    values[spike_idx] = 23_000

    df = pd.DataFrame({
        "timestamp_utc": rng,
        "respondent":    "AEP",
        "ticker":        "AEP",
        "value_mwh":     values,
    })

    signals = detect_anomalies(df)
    print(f"Detected {len(signals)} anomaly hours from {len(df)} total observations.")
    summarize(signals)
