"""Retry helpers built on ``tenacity``.

All I/O boundaries (HTTP, SQLite, file I/O) should be wrapped with
:func:`http_retry` or :func:`io_retry` so transient failures are handled
uniformly without scattered try/except blocks.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

import structlog
import tenacity

from fosbury.core.exceptions import ExtractionError, LoadError

log = structlog.get_logger()

F = TypeVar("F", bound=Callable[..., Any])


def _before_sleep(retry_state: tenacity.RetryCallState) -> None:
    log.warning(
        "fosbury.retry",
        attempt=retry_state.attempt_number,
        wait_s=round(retry_state.next_action.sleep, 2) if retry_state.next_action else None,  # type: ignore[union-attr]
        exc=str(retry_state.outcome.exception()) if retry_state.outcome else None,
    )


def http_retry(max_attempts: int = 3, wait_seconds: float = 2.0) -> Callable[[F], F]:
    """Decorator: retry on ``httpx`` transport errors and 5xx responses.

    Args:
        max_attempts: Maximum number of total attempts (including first).
        wait_seconds: Base wait between retries (exponential, jittered).

    Returns:
        Decorator that wraps the function with retry logic.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import httpx

            retryer = tenacity.Retrying(
                retry=tenacity.retry_if_exception_type(
                    (httpx.TransportError, httpx.TimeoutException, ExtractionError)
                ),
                stop=tenacity.stop_after_attempt(max_attempts),
                wait=tenacity.wait_exponential(multiplier=wait_seconds, min=wait_seconds, max=60)
                + tenacity.wait_random(0, 1),
                before_sleep=_before_sleep,
                reraise=True,
            )
            return retryer(fn, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def io_retry(max_attempts: int = 3, wait_seconds: float = 1.0) -> Callable[[F], F]:
    """Decorator: retry on I/O errors (file, SQLite, Parquet write failures).

    Args:
        max_attempts: Maximum number of total attempts.
        wait_seconds: Base wait between retries.

    Returns:
        Decorator that wraps the function with retry logic.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            retryer = tenacity.Retrying(
                retry=tenacity.retry_if_exception_type((OSError, LoadError)),
                stop=tenacity.stop_after_attempt(max_attempts),
                wait=tenacity.wait_exponential(multiplier=wait_seconds, min=wait_seconds, max=30),
                before_sleep=_before_sleep,
                reraise=True,
            )
            return retryer(fn, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
