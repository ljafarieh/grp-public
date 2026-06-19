"""Abstract base extractor — shared HTTP client, retry, stub logic.

Concrete extractors inherit from :class:`BaseHttpExtractor` and implement
:meth:`_live_extract` (real network call) and optionally override
:meth:`_fixture_path` to point at a different fixture file.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx
import structlog

from fosbury.config.settings import Settings
from fosbury.core.exceptions import ExtractionError
from fosbury.core.retry import http_retry

log = structlog.get_logger()

# Fixtures live next to the tests directory for easy discovery.
_FIXTURE_ROOT = Path(__file__).parents[3] / "tests" / "fixtures"


class BaseHttpExtractor(ABC):
    """Base class for HTTP-backed extractors.

    Subclasses declare ``source_key`` and implement ``_live_extract``.
    When ``settings.stub_mode`` is ``True`` the fixture file is loaded
    instead, so the full pipeline runs without live credentials.

    Args:
        settings: Injected runtime configuration.
    """

    source_key: str  # must be set by subclass

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.Client(
            timeout=settings.http_timeout_seconds,
            headers={"Accept": "application/json", "User-Agent": "Fosbury-ETL/0.1"},
            follow_redirects=True,
        )

    # ------------------------------------------------------------------
    # Public interface (satisfies Extractor protocol)
    # ------------------------------------------------------------------

    def extract(self) -> Any:
        """Return raw payload, from fixture or live API depending on config."""
        if self._settings.stub_mode:
            return self._load_fixture()
        return self._live_extract_with_retry()

    # ------------------------------------------------------------------
    # Subclass interface
    # ------------------------------------------------------------------

    @abstractmethod
    def _live_extract(self) -> Any:
        """Fetch live data from the external API.

        Must raise :class:`~fosbury.core.exceptions.ExtractionError` on failure.
        """

    def _fixture_path(self) -> Path:
        """Return path to the JSON fixture for this source.

        Override in a subclass to use a non-default path.
        """
        return _FIXTURE_ROOT / f"{self.source_key}.json"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_fixture(self) -> Any:
        path = self._fixture_path()
        if not path.exists():
            raise ExtractionError(
                f"Stub mode active but fixture missing: {path}. "
                "Run `fosbury --stub` only after placing a fixture file."
            )
        log.debug("extractor.fixture_loaded", source=self.source_key, path=str(path))
        return json.loads(path.read_text())

    def _live_extract_with_retry(self) -> Any:
        @http_retry(
            max_attempts=self._settings.http_retry_max,
            wait_seconds=self._settings.http_retry_wait_seconds,
        )
        def _inner() -> Any:
            return self._live_extract()

        return _inner()

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """Perform a GET request and return parsed JSON.

        Args:
            url: Full URL to request.
            params: Optional query parameters.

        Returns:
            Parsed JSON (dict or list).

        Raises:
            ExtractionError: On HTTP error or JSON decode failure.
        """
        try:
            resp = self._client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise ExtractionError(
                f"HTTP {exc.response.status_code} from {url}: {exc.response.text[:200]}"
            ) from exc
        except httpx.RequestError as exc:
            raise ExtractionError(f"Network error fetching {url}: {exc}") from exc
        except ValueError as exc:
            raise ExtractionError(f"JSON decode error from {url}: {exc}") from exc

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
