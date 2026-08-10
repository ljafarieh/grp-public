"""Plugin registry — zero-touch extensibility for new data sources.

How to add a new source
───────────────────────
1. Create ``src/fosbury/extractors/my_source.py`` with a class that inherits
   from :class:`~fosbury.extractors.base.BaseHttpExtractor` and sets
   ``source_key = "my_source"``.
2. Create ``src/fosbury/transformers/my_source.py`` with a transformer that
   inherits from :class:`~fosbury.transformers.base.BaseTransformer`.
3. Add a fixture at ``tests/fixtures/my_source.json``.
4. Register the stage at the bottom of *this file* — one call to
   :func:`register_stage`.

That's it.  The orchestrator (:class:`~fosbury.core.pipeline.Pipeline`) picks
it up automatically; no other files change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import structlog

from fosbury.config.settings import Settings
from fosbury.core.exceptions import RegistryError
from fosbury.core.pipeline import PipelineStage

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Internal registry storage
# ---------------------------------------------------------------------------


@dataclass
class _StageFactory:
    """Holds the callables that build one complete ETL stage."""

    source_key: str
    factory: Callable[[Settings], PipelineStage]
    description: str = ""


_REGISTRY: dict[str, _StageFactory] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register_stage(
    source_key: str,
    factory: Callable[[Settings], PipelineStage],
    description: str = "",
) -> None:
    """Register a stage factory under *source_key*.

    Args:
        source_key: Unique identifier (e.g. ``"pjm_lmp"``).  Duplicate keys
            raise :class:`~fosbury.core.exceptions.RegistryError`.
        factory: Callable ``(Settings) -> PipelineStage``.  Will be called by
            :func:`build_pipeline_stages` at runtime.
        description: Human-readable description shown in ``--help`` output.

    Raises:
        RegistryError: If *source_key* is already registered.
    """
    if source_key in _REGISTRY:
        raise RegistryError(
            f"Stage '{source_key}' is already registered.  "
            "Each source_key must be unique."
        )
    _REGISTRY[source_key] = _StageFactory(
        source_key=source_key, factory=factory, description=description
    )
    log.debug("registry.registered", source_key=source_key)


def list_registered() -> list[str]:
    """Return all currently registered source keys."""
    return sorted(_REGISTRY.keys())


def build_pipeline_stages(
    settings: Settings,
    sources: list[str] | None = None,
) -> list[PipelineStage]:
    """Instantiate :class:`~fosbury.core.pipeline.PipelineStage` objects.

    Args:
        settings: Injected runtime configuration, passed to each factory.
        sources: If given, only these source keys are built.  If ``None``,
            all registered sources are built.

    Returns:
        Ordered list of stages ready to pass to :meth:`Pipeline.run`.

    Raises:
        RegistryError: If a requested source key is not registered.
    """
    keys = sources if sources is not None else list_registered()

    stages: list[PipelineStage] = []
    for key in keys:
        if key not in _REGISTRY:
            raise RegistryError(
                f"Unknown source key '{key}'.  "
                f"Registered sources: {list_registered()}"
            )
        stage = _REGISTRY[key].factory(settings)
        stages.append(stage)
        log.debug("registry.stage_built", source_key=key)

    return stages


# ---------------------------------------------------------------------------
# Built-in stage registrations
# ---------------------------------------------------------------------------
# Import here (bottom of file) to avoid circular imports; the extractors /
# transformers / loaders import from core but not from registry.


def _build_pjm_lmp(settings: Settings) -> PipelineStage:
    from fosbury.extractors.pjm_lmp import PjmLmpExtractor
    from fosbury.loaders.parquet_loader import ParquetLoader
    from fosbury.loaders.sqlite_loader import SqliteLoader
    from fosbury.transformers.lmp import LmpTransformer

    settings.ensure_storage_dirs()
    return PipelineStage(
        source_key="pjm_lmp",
        extractor=PjmLmpExtractor(settings),
        transformer=LmpTransformer(),
        loaders=[
            SqliteLoader(settings.sqlite_path),
            ParquetLoader(settings.parquet_dir),
        ],
    )


def _build_pjm_constraints(settings: Settings) -> PipelineStage:
    from fosbury.extractors.pjm_constraints import PjmConstraintsExtractor
    from fosbury.loaders.parquet_loader import ParquetLoader
    from fosbury.loaders.sqlite_loader import SqliteLoader
    from fosbury.transformers.constraints import ConstraintsTransformer

    settings.ensure_storage_dirs()
    return PipelineStage(
        source_key="pjm_constraints",
        extractor=PjmConstraintsExtractor(settings),
        transformer=ConstraintsTransformer(),
        loaders=[
            SqliteLoader(settings.sqlite_path),
            ParquetLoader(settings.parquet_dir),
        ],
    )


def _build_eia_demand(settings: Settings) -> PipelineStage:
    from fosbury.extractors.eia_demand import EiaDemandExtractor
    from fosbury.loaders.parquet_loader import ParquetLoader
    from fosbury.loaders.sqlite_loader import SqliteLoader
    from fosbury.transformers.eia_demand import EiaDemandTransformer

    settings.ensure_storage_dirs()
    return PipelineStage(
        source_key="eia_demand",
        extractor=EiaDemandExtractor(settings),
        transformer=EiaDemandTransformer(),
        loaders=[
            SqliteLoader(settings.sqlite_path),
            ParquetLoader(settings.parquet_dir),
        ],
    )


# pjm_lmp and pjm_constraints require a PJM Data Miner subscription key.
# Re-enable by uncommenting these two lines and setting PJM_API_KEY in .env.
# register_stage("pjm_lmp", _build_pjm_lmp, "PJM 5-min ex-post LMP by pricing node")
# register_stage("pjm_constraints", _build_pjm_constraints, "PJM binding transmission constraints")
register_stage("eia_demand", _build_eia_demand, "EIA hourly PJM-region electricity demand")


# ---------------------------------------------------------------------------
# GRP regulatory scraper stages
# ---------------------------------------------------------------------------


def _build_va_scc(settings: Settings) -> PipelineStage:
    from fosbury.extractors.va_scc import VirginiaSCCScraper
    from fosbury.loaders.grid_event_loader import GridEventLoader
    from fosbury.transformers.regulatory import RegulatoryTransformer

    settings.ensure_storage_dirs()
    return PipelineStage(
        source_key="va_scc",
        extractor=VirginiaSCCScraper(settings),
        transformer=RegulatoryTransformer("va_scc"),
        loaders=[GridEventLoader(settings.sqlite_path)],
    )


def _build_ohio_puco(settings: Settings) -> PipelineStage:
    from fosbury.extractors.ohio_puco import OhioPUCOScraper
    from fosbury.loaders.grid_event_loader import GridEventLoader
    from fosbury.transformers.regulatory import RegulatoryTransformer

    settings.ensure_storage_dirs()
    return PipelineStage(
        source_key="ohio_puco",
        extractor=OhioPUCOScraper(settings),
        transformer=RegulatoryTransformer("ohio_puco"),
        loaders=[GridEventLoader(settings.sqlite_path)],
    )


def _build_pa_puc(settings: Settings) -> PipelineStage:
    from fosbury.extractors.pa_puc import PaPUCScraper
    from fosbury.loaders.grid_event_loader import GridEventLoader
    from fosbury.transformers.regulatory import RegulatoryTransformer

    settings.ensure_storage_dirs()
    return PipelineStage(
        source_key="pa_puc",
        extractor=PaPUCScraper(settings),
        transformer=RegulatoryTransformer("pa_puc"),
        loaders=[GridEventLoader(settings.sqlite_path)],
    )


def _build_ferc(settings: Settings) -> PipelineStage:
    from fosbury.extractors.ferc import FERCScraper
    from fosbury.loaders.grid_event_loader import GridEventLoader
    from fosbury.transformers.regulatory import RegulatoryTransformer

    settings.ensure_storage_dirs()
    return PipelineStage(
        source_key="ferc",
        extractor=FERCScraper(settings),
        transformer=RegulatoryTransformer("ferc"),
        loaders=[GridEventLoader(settings.sqlite_path)],
    )


register_stage("va_scc", _build_va_scc, "Virginia SCC daily docket — Dominion Energy transmission delays")
register_stage("ohio_puco", _build_ohio_puco, "Ohio PUCO — AEP data center load impact studies")
register_stage("pa_puc", _build_pa_puc, "PA PUC — Constellation/Talen nuclear co-location protests")
register_stage("ferc", _build_ferc, "FERC eLibrary — Section 205/206 co-location filings")


# ---------------------------------------------------------------------------
# AI/HPC company NTP / ISA queue miner
# ---------------------------------------------------------------------------


def _build_ntp_queue_miner(settings: Settings) -> PipelineStage:
    from fosbury.extractors.ntp_queue_miner import NTPQueueMiner
    from fosbury.loaders.grid_event_loader import GridEventLoader
    from fosbury.transformers.regulatory import RegulatoryTransformer

    settings.ensure_storage_dirs()
    return PipelineStage(
        source_key="ntp_queue_miner",
        extractor=NTPQueueMiner(settings),
        transformer=RegulatoryTransformer("ntp_queue_miner"),
        loaders=[GridEventLoader(settings.sqlite_path)],
    )


register_stage(
    "ntp_queue_miner",
    _build_ntp_queue_miner,
    "PJM queue NTP/ISA transitions + FERC dockets for CORZ, IREN, Keel",
)


# ---------------------------------------------------------------------------
# PJM RTEP state infrastructure reports
# ---------------------------------------------------------------------------


def _build_pjm_rtep(settings: Settings) -> PipelineStage:
    from fosbury.extractors.pjm_rtep import PjmRtepScraper
    from fosbury.loaders.grid_event_loader import GridEventLoader
    from fosbury.transformers.regulatory import RegulatoryTransformer

    settings.ensure_storage_dirs()
    return PipelineStage(
        source_key="pjm_rtep",
        extractor=PjmRtepScraper(settings),
        transformer=RegulatoryTransformer("pjm_rtep"),
        loaders=[GridEventLoader(settings.sqlite_path)],
    )


register_stage(
    "pjm_rtep",
    _build_pjm_rtep,
    "PJM RTEP state reports — large load MW forecast + capacity auction scarcity signals",
)
