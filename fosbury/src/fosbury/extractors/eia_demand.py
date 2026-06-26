"""EIA Open Data API v2 — hourly electricity demand extractor.

Live endpoint:
    GET https://api.eia.gov/v2/electricity/rto/region-data/data/
    Documentation: https://www.eia.gov/opendata/browser/electricity/rto/region-data

**API key required**: Free registration at https://www.eia.gov/opendata/
Set ``EIA_API_KEY`` in your ``.env``.  Without it, stub_mode=True still works.

We filter to the PJM respondent (``respondent=PJM``) and the ``D`` (Demand)
series so the dataset aligns with the LMP and constraints data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from fosbury.config.settings import Settings
from fosbury.core.exceptions import ConfigurationError
from fosbury.extractors.base import BaseHttpExtractor

log = structlog.get_logger()

_BASE_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"


class EiaDemandExtractor(BaseHttpExtractor):
    """Extract hourly PJM-region demand from the EIA v2 API.

    Args:
        settings: Injected runtime configuration.
        lookback_days: Days of history to pull.
    """

    source_key = "eia_demand"

    def __init__(self, settings: Settings, lookback_days: int | None = None) -> None:
        super().__init__(settings)
        self._lookback_days = lookback_days or settings.lookback_days

    def _live_extract(self) -> Any:
        if not self._settings.eia_api_key:
            raise ConfigurationError(
                "EIA_API_KEY is not set.  Register for a free key at "
                "https://www.eia.gov/opendata/ and add it to your .env file.  "
                "Alternatively, run with STUB_MODE=true."
            )

        end_dt = datetime.now(tz=timezone.utc)
        start_dt = end_dt - timedelta(days=self._lookback_days)

        # Pull demand for PJM aggregate + key utility-level BAs with traded parents
        respondents = [
            "PJM",   # PJM Interconnection aggregate
            "DOM",   # Dominion Energy Virginia (D)
            "AEP",   # American Electric Power (AEP)
            "FE",    # FirstEnergy (FE)
            "DUK",   # Duke Energy (DUK)
            "CPLE",  # Duke Energy Progress East (DUK)
            "EXC",   # Exelon (EXC) — feeds ComEd/PECO/BGE
            "PPL",   # PPL Corporation (PPL)
            "PSEG",  # PSEG (PEG)
        ]

        params: dict[str, Any] = {
            "api_key": self._settings.eia_api_key,
            "frequency": "hourly",
            "data[0]": "value",
            "facets[type][]": "D",            # Demand only
            "start": start_dt.strftime("%Y-%m-%dT%H"),
            "end": end_dt.strftime("%Y-%m-%dT%H"),
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": 0,
            "length": 5000,
        }
        # Add each respondent as a separate facet parameter
        for i, code in enumerate(respondents):
            params[f"facets[respondent][{i}]"] = code

        log.info("eia_demand.fetch", start=params["start"], end=params["end"], respondents=respondents)
        return self._get_json(_BASE_URL, params=params)
