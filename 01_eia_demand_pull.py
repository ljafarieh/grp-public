"""
Snippet 01 — Pulling live electricity demand from the EIA Open Data API
------------------------------------------------------------------------
The U.S. Energy Information Administration publishes hourly electricity
demand for every balancing authority (BA) in the country. A balancing
authority is roughly a utility's control area — so this data tells you,
in near-real-time, how much power AEP, Dominion, PPL, Duke, etc. are
actually delivering to their customers.

This is Layer 1 of GRP: the raw physical demand signal.

Requirements:
    pip install httpx pandas

EIA API key (free): https://www.eia.gov/opendata/
"""

import httpx
import pandas as pd
from datetime import datetime, timedelta, timezone

EIA_API_KEY = "YOUR_KEY_HERE"  # get one free at eia.gov/opendata

# Balancing authority codes → publicly traded utility tickers
# This is a small sample. The full registry covers 70+ BAs.
BA_REGISTRY = {
    "AEP":  "AEP",   # American Electric Power
    "DOM":  "D",     # Dominion Energy
    "PPL":  "PPL",   # PPL Corporation
    "DUK":  "DUK",   # Duke Energy
    "FE":   "FE",    # FirstEnergy
    "PSEG": "PEG",   # PSEG
    "EXC":  "EXC",   # Exelon (ComEd, BGE, Pepco)
}


def pull_demand(ba_code: str, days_back: int = 7) -> pd.DataFrame:
    """
    Pull hourly demand (MWh) for a balancing authority over the last N days.

    Returns a DataFrame with columns: [timestamp_utc, respondent, value_mwh]
    """
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)

    resp = httpx.get(
        "https://api.eia.gov/v2/electricity/rto/region-data/data/",
        params={
            "api_key":         EIA_API_KEY,
            "frequency":       "hourly",
            "data[0]":         "value",
            "facets[respondent][]": ba_code,
            "facets[type][]":  "D",   # D = demand
            "start":           start.strftime("%Y-%m-%dT%H"),
            "end":             end.strftime("%Y-%m-%dT%H"),
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length":          500,
        },
        timeout=15,
    )
    resp.raise_for_status()

    rows = resp.json().get("response", {}).get("data", [])
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["timestamp_utc"] = pd.to_datetime(df["period"], utc=True)
    df["value_mwh"]     = pd.to_numeric(df["value"], errors="coerce")
    df["respondent"]    = ba_code
    df["ticker"]        = BA_REGISTRY.get(ba_code, "")

    return df[["timestamp_utc", "respondent", "ticker", "value_mwh"]].dropna()


if __name__ == "__main__":
    for ba in ["AEP", "DOM", "PPL"]:
        df = pull_demand(ba, days_back=3)
        if df.empty:
            print(f"{ba}: no data")
            continue
        latest = df.iloc[0]
        print(
            f"{ba} ({BA_REGISTRY[ba]}) | "
            f"latest: {latest['timestamp_utc']} | "
            f"{latest['value_mwh']:,.0f} MWh"
        )
