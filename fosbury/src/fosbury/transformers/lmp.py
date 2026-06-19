"""Transform raw PJM Data Miner LMP JSON into a validated :class:`LmpDataset`.

PJM Data Miner 2 returns a top-level dict with an ``"items"`` list.  Each item
contains the pricing node info and four LMP components.  This transformer:

  1. Validates required fields are present and non-null.
  2. Skips rows with null prices (PJM occasionally returns null for placeholder
     intervals that haven't been settled yet).
  3. Builds typed :class:`~fosbury.core.models.LmpRecord` objects via pydantic,
     which catches type errors (e.g. non-numeric price) at construction time.
"""

from __future__ import annotations

from typing import Any

import structlog

from fosbury.core.exceptions import TransformationError
from fosbury.core.models import LmpDataset, LmpRecord
from fosbury.transformers.base import BaseTransformer

log = structlog.get_logger()


class LmpTransformer(BaseTransformer):
    """Transform raw PJM LMP API response into a :class:`LmpDataset`."""

    def transform(self, raw: Any) -> LmpDataset:
        """Parse the PJM Data Miner 2 ``five_min_expost_lmps`` response.

        Args:
            raw: Parsed JSON from the PJM API (dict with ``"items"`` list).

        Returns:
            Validated :class:`LmpDataset`.

        Raises:
            TransformationError: If the top-level structure is unrecognisable.
        """
        if not isinstance(raw, dict):
            raise TransformationError(f"Expected dict at top level, got {type(raw).__name__}")

        items = raw.get("items")
        if not isinstance(items, list):
            raise TransformationError(
                f"Expected 'items' list in PJM response; keys present: {list(raw.keys())}"
            )

        records: list[LmpRecord] = []
        skipped = 0

        for i, row in enumerate(items):
            if not isinstance(row, dict):
                self._warn_skip(i, "row is not a dict")
                skipped += 1
                continue

            # Skip rows with null prices — unsettled intervals
            lmp_val = row.get("total_lmp_rt")
            if lmp_val is None:
                self._warn_skip(i, "null total_lmp_rt")
                skipped += 1
                continue

            try:
                record = LmpRecord(
                    timestamp_utc=self._require(row, "datetime_beginning_utc", i),
                    pnode_id=int(self._require(row, "pnode_id", i)),
                    pnode_name=str(self._require(row, "pnode_name", i)),
                    lmp_total=lmp_val,
                    lmp_congestion=row.get("congestion_price_rt", 0),
                    lmp_marginal_loss=row.get("marginal_loss_price_rt", 0),
                    lmp_energy=row.get("system_energy_price_rt", 0),
                    voltage_level=row.get("voltage"),
                )
            except (TransformationError, ValueError, TypeError) as exc:
                self._warn_skip(i, str(exc))
                skipped += 1
                continue

            records.append(record)

        log.info(
            "lmp_transformer.done",
            total_input=len(items),
            parsed=len(records),
            skipped=skipped,
        )

        if not records:
            raise TransformationError("LMP transformer produced zero records — check raw payload.")

        return LmpDataset(source="pjm_lmp", records=records)
