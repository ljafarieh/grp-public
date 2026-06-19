"""Domain exceptions for the Fosbury ETL framework."""

from __future__ import annotations


class FosburyError(Exception):
    """Base class for all Fosbury errors."""


class ExtractionError(FosburyError):
    """Raised when an extractor cannot retrieve source data."""


class TransformationError(FosburyError):
    """Raised when a transformer rejects or cannot parse the raw payload."""


class LoadError(FosburyError):
    """Raised when a loader cannot write to its storage backend."""


class RegistryError(FosburyError):
    """Raised on plugin registry misuse (duplicate key, missing key, etc.)."""


class ConfigurationError(FosburyError):
    """Raised on invalid or missing configuration."""
