"""
Daily OHLCV ingestion: fetches data for the configured universe and stores
it in the local parquet cache. Re-runs are incremental — only missing dates
are fetched, making repeated runs fast and deterministic.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from ingestion.adapter import DataSourceAdapter, DataSourceError, get_adapter

logger = logging.getLogger(__name__)

# Path anchors (resolved relative to the project root, not this file)
PROJECT_ROOT = Path(__file__).parent.parent
UNIVERSE_PATH = PROJECT_ROOT / "config" / "universe.yaml"
CACHE_DIR = PROJECT_ROOT / "cache"


# ---------------------------------------------------------------------------
# Universe loading
# ---------------------------------------------------------------------------

def load_universe(path: Path = UNIVERSE_PATH) -> dict:
    """
    Load the ticker universe from YAML. Returns a dict keyed by ticker symbol
    with metadata sub-dicts (name, sector, thesis_role, notes).
    """
    with open(path) as fh:
        data = yaml.safe_load(fh)
    return data.get("tickers", {})


# ---------------------------------------------------------------------------
# Parquet cache helpers
# ---------------------------------------------------------------------------

def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker.upper()}.parquet"


def load_cached(ticker: str) -> Optional[pd.DataFrame]:
    """Return cached DataFrame for ticker, or None if no cache exists."""
    p = _cache_path(ticker)
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df.index = pd.to_datetime(df.index).date
    return df


def save_cache(ticker: str, df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_cache_path(ticker))


def merge_and_save(ticker: str, new_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge new_df with any existing cache for ticker, deduplicate by date,
    sort chronologically, and persist. Returns the merged DataFrame.
    """
    existing = load_cached(ticker)
    if existing is not None:
        combined = pd.concat([existing, new_df])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined.sort_index(inplace=True)
    else:
        combined = new_df.sort_index()
    save_cache(ticker, combined)
    return combined


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------

def find_missing_dates(
    ticker: str,
    start: date,
    end: date,
) -> tuple[date, date] | None:
    """
    Determine the date range to fetch for ticker.
    - If no cache: fetch full (start, end).
    - If cache exists but doesn't cover through end: fetch (cache_end+1, end).
    - If cache already covers through end: return None (nothing to fetch).

    We never try to fetch today's data — markets may still be open and
    yfinance returns nothing for an incomplete session.
    """
    # Cap end at yesterday so we only fetch settled closes
    latest_fetchable = date.today() - timedelta(days=1)
    end = min(end, latest_fetchable)

    cached = load_cached(ticker)
    if cached is None or cached.empty:
        return start, end

    cache_end = max(cached.index)
    if cache_end >= end:
        return None  # already up to date

    fetch_start = cache_end + timedelta(days=1)
    if fetch_start > end:
        return None

    return fetch_start, end


# ---------------------------------------------------------------------------
# Core ingestion
# ---------------------------------------------------------------------------

def ingest_ticker(
    ticker: str,
    start: date,
    end: date,
    adapter: DataSourceAdapter,
) -> tuple[pd.DataFrame, str]:
    """
    Fetch OHLCV for one ticker, merge with cache, persist.
    Returns (full_dataframe, status_string).
    """
    missing = find_missing_dates(ticker, start, end)

    if missing is None:
        df = load_cached(ticker)
        return df, "cache_hit"

    fetch_start, fetch_end = missing
    try:
        new_data = adapter.fetch_ohlcv(ticker, fetch_start, fetch_end)
    except DataSourceError as exc:
        logger.warning("Failed to fetch %s: %s", ticker, exc)
        existing = load_cached(ticker)
        if existing is not None:
            return existing, f"fetch_error_used_cache ({exc})"
        raise

    df = merge_and_save(ticker, new_data)
    rows_added = len(new_data)
    return df, f"fetched {rows_added} new rows ({fetch_start} → {fetch_end})"


def run_ingestion(
    history_days: int = 365,
    end_date: Optional[date] = None,
    universe_path: Path = UNIVERSE_PATH,
) -> dict[str, dict]:
    """
    Main ingestion entry point. Fetches/updates OHLCV for all tickers in the
    universe. Returns a results dict keyed by ticker with status and stats.
    """
    universe = load_universe(universe_path)
    adapter = get_adapter()

    end = end_date or date.today()
    start = end - timedelta(days=history_days)

    logger.info(
        "Ingestion start | source: %s | tickers: %d | window: %s → %s",
        adapter.source_name(),
        len(universe),
        start,
        end,
    )

    results = {}
    for ticker, meta in universe.items():
        try:
            df, status = ingest_ticker(ticker, start, end, adapter)
            date_index = [d for d in df.index]
            results[ticker] = {
                "status": status,
                "rows": len(df),
                "date_start": min(date_index) if date_index else None,
                "date_end": max(date_index) if date_index else None,
                "thesis_role": meta.get("thesis_role", "unknown"),
                "sector": meta.get("sector", "unknown"),
                "error": None,
            }
            logger.info("  %-8s  %s", ticker, status)
        except DataSourceError as exc:
            results[ticker] = {
                "status": "error",
                "rows": 0,
                "date_start": None,
                "date_end": None,
                "thesis_role": meta.get("thesis_role", "unknown"),
                "sector": meta.get("sector", "unknown"),
                "error": str(exc),
            }
            logger.error("  %-8s  ERROR: %s", ticker, exc)

    return results


# ---------------------------------------------------------------------------
# Gap analysis (called after ingestion for sanity check)
# ---------------------------------------------------------------------------

def detect_gaps(df: pd.DataFrame, ticker: str) -> list[str]:
    """
    Identify multi-day gaps in trading data (excluding weekends).
    A gap > 4 calendar days between consecutive rows is flagged.
    Returns a list of human-readable gap descriptions.
    """
    if df is None or len(df) < 2:
        return []
    dates = sorted(df.index)
    gaps = []
    for i in range(1, len(dates)):
        delta = (dates[i] - dates[i - 1]).days
        # Markets close weekends (2 days) + possible holiday (1 day) = 4 days max
        if delta > 4:
            gaps.append(f"{dates[i-1]} → {dates[i]} ({delta} calendar days)")
    return gaps
