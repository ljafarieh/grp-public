"""Structural protocols that define the ETL contract.

These are *pure* Protocol classes — no implementation, no imports from concrete
modules.  Any object satisfying the structural interface is accepted by the
pipeline, including third-party objects that have never heard of Fosbury.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")
U = TypeVar("U")


@runtime_checkable
class Extractor(Protocol):
    """Pull raw data from an external source and return it as a plain Python object.

    Concrete implementations should be registered via :func:`fosbury.registry.register`.
    """

    #: Short identifier used in logs and the plugin registry.
    source_key: str

    def extract(self) -> Any:
        """Fetch raw data from the source.

        Returns:
            Raw payload — type is source-specific but must be accepted by the
            paired :class:`Transformer`.

        Raises:
            ExtractionError: on unrecoverable fetch failure.
        """
        ...


@runtime_checkable
class Transformer(Protocol):
    """Convert raw extractor output into a validated, typed dataset."""

    def transform(self, raw: Any) -> Any:
        """Transform *raw* into a clean payload.

        Args:
            raw: Output of :meth:`Extractor.extract`.

        Returns:
            Clean, validated data ready for loading.

        Raises:
            TransformationError: on schema violations or unrecoverable data issues.
        """
        ...


@runtime_checkable
class Loader(Protocol):
    """Persist a clean dataset to a storage backend."""

    def load(self, data: Any) -> int:
        """Write *data* to the storage backend.

        Args:
            data: Clean payload from :meth:`Transformer.transform`.

        Returns:
            Number of rows written.

        Raises:
            LoadError: on storage failure.
        """
        ...
