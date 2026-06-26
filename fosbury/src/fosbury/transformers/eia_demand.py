"""Transform raw EIA v2 API demand JSON into a :class:`DemandDataset`.

The EIA v2 API wraps results under ``response.data``.  Each record has:
  - ``period``: ISO-8601 datetime string (UTC implied for EIA hourly data)
  - ``respondent``: balancing-authority code (e.g. "PJM")
  - ``respondent-name``: human-readable name
  - ``type-name``: series description (e.g. "Demand")
  - ``value``: MWh figure
  - ``value-units``: should be "megawatthours"
"""

from __future__ import annotations

from typing import Any

import structlog

from fosbury.core.exceptions import TransformationError
from fosbury.core.models import DemandDataset, DemandRecord
from fosbury.pipelines.ba_registry import lookup_ba
from fosbury.transformers.base import BaseTransformer

log = structlog.get_logger()


class EiaDemandTransformer(BaseTransformer):
    """Transform raw EIA demand API response into a :class:`DemandDataset`."""

    def transform(self, raw: Any) -> DemandDataset:
        """Parse the EIA v2 electricity/rto/region-data response.

        Args:
            raw: Parsed JSON from the EIA API.

        Returns:
            Validated :class:`DemandDataset`.

        Raises:
            TransformationError: On unrecognisable structure.
        """
        if not isinstance(raw, dict):
            raise TransformationError(f"Expected dict, got {type(raw).__name__}")

        # EIA v2 nests data under response.data
        response_block = raw.get("response", raw)
        items = response_block.get("data")
        if not isinstance(items, list):
            raise TransformationError(
                f"Expected 'response.data' list; top-level keys: {list(raw.keys())}"
            )

        records: list[DemandRecord] = []
        skipped = 0

        for i, row in enumerate(items):
            if not isinstance(row, dict):
                self._warn_skip(i, "row is not a dict")
                skipped += 1
                continue

            value = row.get("value")
            if value is None:
                self._warn_skip(i, "null value")
                skipped += 1
                continue

            try:
                respondent = str(self._require(row, "respondent", i))
                ba_info = lookup_ba(respondent)
                record = DemandRecord(
                    timestamp_utc=self._require(row, "period", i),
                    respondent=respondent,
                    respondent_name=str(row.get("respondent-name", "")),
                    value_mwh=value,
                    type_name=str(row.get("type-name", "")),
                    ticker=ba_info.ticker,
                    company_name=ba_info.company_name,
                )
            except (TransformationError, ValueError, TypeError) as exc:
                self._warn_skip(i, str(exc))
                skipped += 1
                continue

            records.append(record)

        log.info(
            "eia_demand_transformer.done",
            total_input=len(items),
            parsed=len(records),
            skipped=skipped,
        )

        if not records:
            raise TransformationError("EIA demand transformer produced zero records.")

        return DemandDataset(source="eia_demand", records=records)
