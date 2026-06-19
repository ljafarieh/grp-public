"""Unit tests for the Pipeline orchestrator.

All external I/O is replaced with simple in-memory stubs that satisfy the
Extractor / Transformer / Loader protocols.
"""

from __future__ import annotations

from fosbury.config.settings import Settings
from fosbury.core.exceptions import ExtractionError, LoadError, TransformationError
from fosbury.core.models import LmpDataset, StageResult
from fosbury.core.pipeline import Pipeline, PipelineStage


# ---------------------------------------------------------------------------
# Stub implementations (satisfy Extractor / Transformer / Loader protocols)
# ---------------------------------------------------------------------------


class _OkExtractor:
    source_key = "stub_ok"

    def extract(self) -> dict:
        return {"items": []}


class _FailExtractor:
    source_key = "stub_fail"

    def extract(self) -> dict:
        raise ExtractionError("network down")


class _OkTransformer:
    def transform(self, raw: dict) -> LmpDataset:
        from fosbury.core.models import LmpRecord
        from decimal import Decimal
        from datetime import datetime

        return LmpDataset(
            source="stub",
            records=[
                LmpRecord(
                    timestamp_utc=datetime(2026, 6, 18, 0, 0),
                    pnode_id=1,
                    pnode_name="HUB",
                    lmp_total=Decimal("30"),
                    lmp_congestion=Decimal("0"),
                    lmp_marginal_loss=Decimal("0"),
                    lmp_energy=Decimal("30"),
                )
            ],
        )


class _FailTransformer:
    def transform(self, raw: object) -> object:
        raise TransformationError("bad schema")


class _CountingLoader:
    def __init__(self) -> None:
        self.calls = 0

    def load(self, data: object) -> int:
        self.calls += 1
        return 1


class _FailLoader:
    def load(self, data: object) -> int:
        raise LoadError("disk full")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def make_settings() -> Settings:
    return Settings(stub_mode=True, log_level="DEBUG")


class TestPipeline:
    def test_successful_run(self) -> None:
        loader = _CountingLoader()
        stage = PipelineStage(
            source_key="stub_ok",
            extractor=_OkExtractor(),
            transformer=_OkTransformer(),
            loaders=[loader],
        )
        results = Pipeline(make_settings()).run([stage])
        assert len(results) == 1
        assert results[0].success
        assert results[0].rows_loaded == 1
        assert loader.calls == 1

    def test_extract_failure_captured(self) -> None:
        stage = PipelineStage(
            source_key="stub_fail",
            extractor=_FailExtractor(),
            transformer=_OkTransformer(),
            loaders=[_CountingLoader()],
        )
        results = Pipeline(make_settings()).run([stage])
        assert not results[0].success
        assert "ExtractionError" in (results[0].error or "")

    def test_transform_failure_captured(self) -> None:
        stage = PipelineStage(
            source_key="stub_ok",
            extractor=_OkExtractor(),
            transformer=_FailTransformer(),
            loaders=[_CountingLoader()],
        )
        results = Pipeline(make_settings()).run([stage])
        assert not results[0].success
        assert "TransformationError" in (results[0].error or "")

    def test_load_failure_captured(self) -> None:
        stage = PipelineStage(
            source_key="stub_ok",
            extractor=_OkExtractor(),
            transformer=_OkTransformer(),
            loaders=[_FailLoader()],
        )
        results = Pipeline(make_settings()).run([stage])
        assert not results[0].success
        assert "LoadError" in (results[0].error or "")

    def test_failed_stage_does_not_block_subsequent(self) -> None:
        """A failure in stage 1 must not prevent stage 2 from running."""
        good_loader = _CountingLoader()
        stages = [
            PipelineStage(
                source_key="fails",
                extractor=_FailExtractor(),
                transformer=_OkTransformer(),
                loaders=[],
            ),
            PipelineStage(
                source_key="succeeds",
                extractor=_OkExtractor(),
                transformer=_OkTransformer(),
                loaders=[good_loader],
            ),
        ]
        results = Pipeline(make_settings()).run(stages)
        assert len(results) == 2
        assert not results[0].success
        assert results[1].success
        assert good_loader.calls == 1

    def test_multiple_loaders_all_called(self) -> None:
        loaders = [_CountingLoader(), _CountingLoader(), _CountingLoader()]
        stage = PipelineStage(
            source_key="stub_ok",
            extractor=_OkExtractor(),
            transformer=_OkTransformer(),
            loaders=loaders,
        )
        Pipeline(make_settings()).run([stage])
        assert all(ldr.calls == 1 for ldr in loaders)

    def test_elapsed_time_recorded(self) -> None:
        stage = PipelineStage(
            source_key="stub_ok",
            extractor=_OkExtractor(),
            transformer=_OkTransformer(),
            loaders=[_CountingLoader()],
        )
        results = Pipeline(make_settings()).run([stage])
        assert results[0].elapsed_s >= 0
