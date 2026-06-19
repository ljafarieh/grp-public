"""Pipeline orchestrator.

The orchestrator knows *nothing* about individual data sources.  It receives a
list of :class:`PipelineStage` objects (each bundling one extractor, one
transformer, and one or more loaders) and runs them in sequence, collecting
:class:`~fosbury.core.models.StageResult` objects.

Adding a new data source = creating a new extractor + transformer (+ optional
loader override) and registering them in ``fosbury/registry.py``.  No changes
to this file are ever needed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import structlog

from fosbury.config.settings import Settings
from fosbury.core.exceptions import ExtractionError, LoadError, TransformationError
from fosbury.core.models import StageResult
from fosbury.core.protocols import Extractor, Loader, Transformer

log = structlog.get_logger()


@dataclass
class PipelineStage:
    """One logical ETL unit: a paired extractor → transformer → loader(s).

    Args:
        source_key: Unique string identifier for this stage (e.g. ``"pjm_lmp"``).
        extractor: Object satisfying :class:`~fosbury.core.protocols.Extractor`.
        transformer: Object satisfying :class:`~fosbury.core.protocols.Transformer`.
        loaders: One or more objects satisfying :class:`~fosbury.core.protocols.Loader`.
            All loaders receive the same transformed payload.
    """

    source_key: str
    extractor: Extractor
    transformer: Transformer
    loaders: list[Loader] = field(default_factory=list)


class Pipeline:
    """Orchestrates a sequence of :class:`PipelineStage` objects.

    Args:
        settings: Runtime configuration.  Used for logging and future
            global options (e.g. dry-run mode).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(self, stages: list[PipelineStage]) -> list[StageResult]:
        """Execute every stage and return a result summary for each.

        Failures in one stage are caught and recorded; subsequent stages still
        run.  The caller decides whether to treat partial failure as fatal.

        Args:
            stages: Ordered list of stages to execute.

        Returns:
            One :class:`~fosbury.core.models.StageResult` per stage.
        """
        results: list[StageResult] = []
        for stage in stages:
            result = self._run_stage(stage)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_stage(self, stage: PipelineStage) -> StageResult:
        bound_log = log.bind(source_key=stage.source_key)
        bound_log.info("stage.start")
        t0 = time.perf_counter()

        try:
            raw = stage.extractor.extract()
            bound_log.debug("stage.extracted")
        except ExtractionError as exc:
            elapsed = time.perf_counter() - t0
            bound_log.error("stage.extract_failed", error=str(exc))
            return StageResult(
                source_key=stage.source_key,
                success=False,
                elapsed_s=elapsed,
                error=f"ExtractionError: {exc}",
            )

        try:
            clean = stage.transformer.transform(raw)
            bound_log.debug("stage.transformed", rows=getattr(clean, "row_count", "?"))
        except TransformationError as exc:
            elapsed = time.perf_counter() - t0
            bound_log.error("stage.transform_failed", error=str(exc))
            return StageResult(
                source_key=stage.source_key,
                success=False,
                elapsed_s=elapsed,
                error=f"TransformationError: {exc}",
            )

        total_rows = 0
        for loader in stage.loaders:
            try:
                rows = loader.load(clean)
                total_rows = max(total_rows, rows)
                bound_log.debug("stage.loaded", loader=type(loader).__name__, rows=rows)
            except LoadError as exc:
                elapsed = time.perf_counter() - t0
                bound_log.error("stage.load_failed", loader=type(loader).__name__, error=str(exc))
                return StageResult(
                    source_key=stage.source_key,
                    success=False,
                    elapsed_s=elapsed,
                    error=f"LoadError ({type(loader).__name__}): {exc}",
                )

        elapsed = time.perf_counter() - t0
        bound_log.info("stage.done", rows=total_rows, elapsed_s=round(elapsed, 2))
        return StageResult(
            source_key=stage.source_key,
            success=True,
            rows_loaded=total_rows,
            elapsed_s=elapsed,
        )
