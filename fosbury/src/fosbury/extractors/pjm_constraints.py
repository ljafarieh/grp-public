"""PJM Data Miner 2 — binding transmission constraints extractor.

Live endpoint:
    GET https://api.pjm.com/api/v1/binding_constraints
    Documented at: https://dataminer2.pjm.com/feed/binding_constraints/definition

This endpoint is public (no subscription key required).  It returns the set of
transmission constraints that were binding in real-time during the requested
period, along with shadow prices ($/MWh) that directly represent the cost of
congestion on each constrained flowgate.
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


class PjmConstraintsExtractor(BaseHttpExtractor):
    """Extract binding transmission constraints from PJM Data Miner 2.

    Args:
        settings: Injected runtime configuration.
        lookback_days: Number of days of history to pull.
    """

    source_key = "pjm_constraints"

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
            "rowCount": 5_000,
            "datetime_beginning_ept": start_date,
            "api_key": self._settings.pjm_api_key,
        }
        log.info("pjm_constraints.fetch", start_date=start_date)
        return self._get_json(f"{_BASE_URL}/binding_constraints", params=params)
