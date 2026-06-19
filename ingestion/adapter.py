"""
Data-source adapter for OHLCV ingestion.

All price/volume fetching goes through the DataSourceAdapter interface.
To swap data sources (yfinance → stooq, Alpaca, Polygon, etc.), implement
a new subclass and change the factory at the bottom. No other file changes.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)


class DataSourceAdapter(ABC):
    """Abstract interface every data-source adapter must implement."""

    @abstractmethod
    def fetch_ohlcv(
        self,
        ticker: str,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """
        Return a DataFrame indexed by date with columns:
            open, high, low, close, volume, adj_close
        All values are floats; volume is an integer stored as float for
        consistency. Missing sessions should be absent rows, not NaNs.
        Raises DataSourceError on unrecoverable fetch failure.
        """

    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of the underlying data source."""


class DataSourceError(RuntimeError):
    """Raised when a data source fails and the caller should handle it."""


# ---------------------------------------------------------------------------
# yfinance adapter (default)
# ---------------------------------------------------------------------------

class YFinanceAdapter(DataSourceAdapter):
    """
    Wraps yfinance. yfinance is an unofficial Yahoo Finance client —
    it can break without notice when Yahoo changes its internal API.
    Isolating it here means a breakage only requires updating this class.
    """

    def __init__(self) -> None:
        try:
            import yfinance as yf  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "yfinance is not installed. Run: pip install yfinance"
            ) from exc

    def source_name(self) -> str:
        return "yfinance (Yahoo Finance, unofficial)"

    def fetch_ohlcv(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        import yfinance as yf

        logger.debug("yfinance fetch: %s  %s → %s", ticker, start, end)

        raw = yf.download(
            ticker,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=True,   # prices adjusted for splits/dividends
            progress=False,
            threads=False,
        )

        if raw.empty:
            raise DataSourceError(
                f"yfinance returned no data for {ticker} ({start} → {end}). "
                "Ticker may be delisted, mistyped, or Yahoo is blocking requests."
            )

        # yfinance column names vary slightly by version; normalise defensively
        raw.columns = [c[0].lower() if isinstance(c, tuple) else c.lower()
                       for c in raw.columns]

        # After auto_adjust, Yahoo drops the separate 'adj close' column and
        # folds the adjustment into 'close'. Keep an explicit adj_close column
        # so downstream code always has a consistent schema.
        if "adj close" in raw.columns:
            raw = raw.rename(columns={"adj close": "adj_close"})
        else:
            raw["adj_close"] = raw["close"]

        raw.index = pd.to_datetime(raw.index).date  # bare date objects
        raw.index.name = "date"

        return raw[["open", "high", "low", "close", "volume", "adj_close"]].copy()


# ---------------------------------------------------------------------------
# Factory — change this one line to swap the active adapter
# ---------------------------------------------------------------------------

def get_adapter() -> DataSourceAdapter:
    """Return the configured data-source adapter."""
    return YFinanceAdapter()
