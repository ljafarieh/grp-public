"""PJM Data Miner 2 — Locational Marginal Price extractor.

Live endpoint (no auth required for recent 5-minute intervals):
    GET https://api.pjm.com/api/v1/five_min_expost_lmps
    query params: startRow=1, rowCount=N, datetime_beginning_ept=<ISO date>

PJM's public API is documented at:
    https://dataminer2.pjm.com/feed/five_min_expost_lmps/definition

**API key**: Public LMP endpoints work without a key.  If PJM enforces a
subscription key in future, set ``PJM_API_KEY`` in your ``.env`` and this
extractor will attach it automatically.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import structlog

from fosbury.config.settings import Settings
from fosbury.core.exceptions import ConfigurationError
from fosbury.extractors.base import BaseHttpExtractor

log = structlog.get_logger()

_BASE_URL = "https://api.pjm.com/api/v1"


class PjmLmpExtractor(BaseHttpExtractor):
    """Extract 5-minute ex-post LMP data from PJM Data Miner 2.

    Args:
        settings: Injected runtime configuration.
        lookback_days: Number of days of history to pull (overrides settings).
    """

    source_key = "pjm_lmp"

    def __init__(self, settings: Settings, lookback_days: int | None = None) -> None:
        super().__init__(settings)
        self._lookback_days = lookback_days or settings.lookback_days

    def _live_extract(self) -> Any:
        if not self._settings.pjm_api_key:
            raise ConfigurationError(
                "PJM_API_KEY is not set. Register for a free key at "
                "https://www.pjm.com/markets-and-operations/etools/data-miner-2 "
                "and add it to your .env file. Alternatively, run with STUB_MODE=true."
            )
        start_date = (date.today() - timedelta(days=self._lookback_days)).isoformat()
        params: dict[str, Any] = {
            "startRow": 1,
            "rowCount": 10_000,
            "datetime_beginning_ept": start_date,
            "api_key": self._settings.pjm_api_key,
        }
        log.info("pjm_lmp.fetch", start_date=start_date)
        return self._get_json(f"{_BASE_URL}/five_min_expost_lmps", params=params)
