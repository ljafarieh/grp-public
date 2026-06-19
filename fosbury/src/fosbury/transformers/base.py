"""Abstract base transformer — shared validation helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import structlog

from fosbury.core.exceptions import TransformationError

log = structlog.get_logger()


class BaseTransformer(ABC):
    """Provides helper methods for safe field extraction with informative errors.

    Subclasses implement :meth:`transform` and use :meth:`_require` /
    :meth:`_coerce` to validate individual fields without writing repetitive
    try/except blocks.
    """

    @abstractmethod
    def transform(self, raw: Any) -> Any:
        """Convert *raw* extractor output to a clean dataset."""

    # ------------------------------------------------------------------
    # Protected helpers
    # ------------------------------------------------------------------

    def _require(self, row: dict[str, Any], key: str, row_index: int) -> Any:
        """Return ``row[key]`` or raise :class:`TransformationError`."""
        try:
            val = row[key]
        except KeyError as exc:
            raise TransformationError(
                f"Missing required field '{key}' in row {row_index}: {list(row.keys())}"
            ) from exc
        if val is None:
            raise TransformationError(
                f"Required field '{key}' is null in row {row_index}"
            )
        return val

    def _warn_skip(self, row_index: int, reason: str) -> None:
        log.warning("transformer.row_skipped", row=row_index, reason=reason)
