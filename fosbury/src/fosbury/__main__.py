"""Entry-point for ``python -m fosbury`` and the ``fosbury`` CLI script."""

from __future__ import annotations

import sys

import click

from fosbury.config.settings import Settings
from fosbury.core.logging import configure_logging
from fosbury.core.pipeline import Pipeline
from fosbury.registry import build_pipeline_stages


@click.command()
@click.option("--source", "-s", multiple=True, help="Source keys to run (default: all registered).")
@click.option("--stub", is_flag=True, default=None, help="Force stub mode regardless of .env.")
@click.option("--log-level", default=None, help="Override LOG_LEVEL from .env.")
def main(source: tuple[str, ...], stub: bool | None, log_level: str | None) -> None:
    """Run the Fosbury ETL pipeline."""
    settings = Settings()
    if stub is not None:
        settings = settings.model_copy(update={"stub_mode": stub})
    if log_level is not None:
        settings = settings.model_copy(update={"log_level": log_level.upper()})

    configure_logging(settings.log_level)

    import structlog

    log = structlog.get_logger()
    log.info("fosbury.start", version="0.1.0", stub_mode=settings.stub_mode)

    stages = build_pipeline_stages(settings, sources=list(source) or None)
    pipeline = Pipeline(settings=settings)

    results = pipeline.run(stages)

    total_rows = sum(r.rows_loaded for r in results)
    log.info("fosbury.done", total_rows=total_rows, sources=len(results))

    for r in results:
        status = "ok" if r.success else "FAILED"
        click.echo(f"  [{status}] {r.source_key}: {r.rows_loaded} rows  ({r.elapsed_s:.1f}s)")

    failed = [r for r in results if not r.success]
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
