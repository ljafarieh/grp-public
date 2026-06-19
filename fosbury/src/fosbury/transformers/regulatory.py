"""Universal transformer for all regulatory scrapers.

Every regulatory extractor (VA SCC, Ohio PUCO, PA PUC, FERC) returns a
``list[dict]`` of raw events.  This transformer validates each dict into
a typed :class:`~fosbury.core.models.GridEvent` pydantic model, applies
deduplication by ``event_id``, and packages everything into a
:class:`~fosbury.core.models.GridEventDataset`.

A single transformer handles all four scrapers because the raw event
format is identical — the scrapers already normalise to the GRP universal
schema before returning.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import structlog

from fosbury.core.exceptions import TransformationError
from fosbury.core.models import GridEvent, GridEventDataset
from fosbury.transformers.base import BaseTransformer

log = structlog.get_logger()


class RegulatoryTransformer(BaseTransformer):
    """Validate raw regulatory event dicts into a :class:`GridEventDataset`.

    Args:
        source: Source key string used to label the dataset (e.g. ``"va_scc"``).
    """

    def __init__(self, source: str) -> None:
        self._source = source

    def transform(self, raw: Any) -> GridEventDataset:
        """Parse and validate a list of raw event dicts.

        Args:
            raw: ``list[dict]`` returned by any regulatory extractor.

        Returns:
            Validated :class:`GridEventDataset`.

        Raises:
            TransformationError: If *raw* is not a list or all rows fail validation.
        """
        if not isinstance(raw, list):
            raise TransformationError(
                f"RegulatoryTransformer expected list, got {type(raw).__name__}"
            )

        records: list[GridEvent] = []
        seen_ids: set[str] = set()
        skipped = 0

        for i, row in enumerate(raw):
            if not isinstance(row, dict):
                self._warn_skip(i, "row is not a dict")
                skipped += 1
                continue

            # Auto-generate event_id if missing
            if not row.get("event_id"):
                blob = f"{row.get('source_url', '')}:{row.get('raw_text_blob', '')[:200]}"
                row["event_id"] = hashlib.sha256(blob.encode()).hexdigest()[:24]

            if row["event_id"] in seen_ids:
                skipped += 1
                continue
            seen_ids.add(row["event_id"])

            # Ensure scraped_at is set
            if not row.get("scraped_at"):
                row["scraped_at"] = datetime.now(timezone.utc)

            # keywords_matched may be a list or absent
            if "keywords_matched" not in row:
                row["keywords_matched"] = []

            try:
                records.append(GridEvent(**row))
            except Exception as exc:
                self._warn_skip(i, str(exc))
                skipped += 1
                continue

        log.info(
            "regulatory_transformer.done",
            source=self._source,
            total_input=len(raw),
            parsed=len(records),
            skipped=skipped,
        )

        if not records and raw:
            raise TransformationError(
                f"RegulatoryTransformer ({self._source}) produced zero valid records "
                f"from {len(raw)} input rows."
            )

        return GridEventDataset(source=self._source, records=records)
