"""Transform raw PJM binding-constraints JSON into a :class:`ConstraintDataset`.

PJM Data Miner 2 returns ``{"items": [...]}`` for the ``binding_constraints``
feed.  Each item describes one constraint interval with shadow price and flow.

The ``pct_loading`` field is computed here as ``mw_flow / mw_limit * 100`` when
both fields are present and non-zero, giving operators a quick severity gauge.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

from fosbury.core.exceptions import TransformationError
from fosbury.core.models import ConstraintDataset, ConstraintRecord
from fosbury.transformers.base import BaseTransformer

log = structlog.get_logger()


class ConstraintsTransformer(BaseTransformer):
    """Transform raw PJM constraints response into a :class:`ConstraintDataset`."""

    def transform(self, raw: Any) -> ConstraintDataset:
        """Parse the PJM Data Miner 2 ``binding_constraints`` response.

        Args:
            raw: Parsed JSON from the PJM API.

        Returns:
            Validated :class:`ConstraintDataset`.

        Raises:
            TransformationError: If the structure is unrecognisable.
        """
        if not isinstance(raw, dict):
            raise TransformationError(f"Expected dict, got {type(raw).__name__}")

        items = raw.get("items")
        if not isinstance(items, list):
            raise TransformationError(f"Expected 'items' list; keys: {list(raw.keys())}")

        records: list[ConstraintRecord] = []
        skipped = 0

        for i, row in enumerate(items):
            if not isinstance(row, dict):
                self._warn_skip(i, "row is not a dict")
                skipped += 1
                continue

            shadow = row.get("shadow_price")
            if shadow is None:
                self._warn_skip(i, "null shadow_price")
                skipped += 1
                continue

            try:
                mw_flow = Decimal(str(row.get("mw_flow", 0)))
                mw_limit = Decimal(str(row.get("mw_limit", 0)))
                pct = (mw_flow / mw_limit * 100) if mw_limit else None

                record = ConstraintRecord(
                    timestamp_utc=self._require(row, "datetime_beginning_utc", i),
                    constraint_name=str(self._require(row, "constraint_name", i)),
                    contingency=str(row.get("contingency", "")),
                    shadow_price=shadow,
                    mw_flow=mw_flow,
                    mw_limit=mw_limit,
                    pct_loading=pct,
                )
            except (TransformationError, ValueError, TypeError) as exc:
                self._warn_skip(i, str(exc))
                skipped += 1
                continue

            records.append(record)

        log.info(
            "constraints_transformer.done",
            total_input=len(items),
            parsed=len(records),
            skipped=skipped,
        )

        if not records:
            raise TransformationError(
                "Constraints transformer produced zero records — check raw payload."
            )

        return ConstraintDataset(source="pjm_constraints", records=records)
