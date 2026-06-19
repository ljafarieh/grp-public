"""Unit tests for retry decorators."""

from __future__ import annotations

import pytest

from fosbury.core.exceptions import ExtractionError
from fosbury.core.retry import http_retry, io_retry


class TestHttpRetry:
    def test_succeeds_on_first_attempt(self) -> None:
        calls = []

        @http_retry(max_attempts=3, wait_seconds=0.01)
        def fn() -> str:
            calls.append(1)
            return "ok"

        assert fn() == "ok"
        assert len(calls) == 1

    def test_retries_on_extraction_error(self) -> None:
        calls = []

        @http_retry(max_attempts=3, wait_seconds=0.01)
        def fn() -> str:
            calls.append(1)
            if len(calls) < 3:
                raise ExtractionError("transient")
            return "ok"

        assert fn() == "ok"
        assert len(calls) == 3

    def test_reraises_after_max_attempts(self) -> None:
        @http_retry(max_attempts=2, wait_seconds=0.01)
        def fn() -> None:
            raise ExtractionError("always fails")

        with pytest.raises(ExtractionError):
            fn()


class TestIoRetry:
    def test_succeeds_without_retry(self) -> None:
        @io_retry(max_attempts=3, wait_seconds=0.01)
        def fn() -> int:
            return 42

        assert fn() == 42

    def test_retries_on_os_error(self) -> None:
        calls = []

        @io_retry(max_attempts=3, wait_seconds=0.01)
        def fn() -> str:
            calls.append(1)
            if len(calls) < 2:
                raise OSError("busy")
            return "written"

        assert fn() == "written"
        assert len(calls) == 2
