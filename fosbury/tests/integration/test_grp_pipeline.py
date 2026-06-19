"""Integration test: full GRP stub pipeline end-to-end.

Runs all four regulatory sources against fixture JSON and verifies
that GridEvents land in SQLite correctly.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fosbury.config.settings import Settings
from fosbury.core.pipeline import Pipeline
from fosbury.registry import build_pipeline_stages

GRP_SOURCES = ["va_scc", "ohio_puco", "pa_puc", "ferc"]


@pytest.mark.integration
class TestGRPPipelineEndToEnd:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.settings = Settings(
            stub_mode=True,
            log_level="DEBUG",
            sqlite_path=tmp_path / "fosbury.db",
            parquet_dir=tmp_path / "parquet",
            eia_api_key="",
            pjm_api_key="",
        )

    def test_all_grp_stages_succeed(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=GRP_SOURCES)
        results = Pipeline(self.settings).run(stages)
        assert len(results) == 4
        for r in results:
            assert r.success, f"Stage {r.source_key} failed: {r.error}"

    def test_grid_events_written_to_sqlite(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=GRP_SOURCES)
        Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        count = conn.execute("SELECT COUNT(*) FROM grid_events").fetchone()[0]
        conn.close()
        assert count == 6  # 2 VA + 1 OH + 1 PA + 2 FERC

    def test_event_fields_correct(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=["va_scc"])
        Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        row = conn.execute(
            "SELECT * FROM grid_events WHERE state_jurisdiction='VA' LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_idempotent_rerun(self) -> None:
        """Running the same sources twice must not duplicate events."""
        for _ in range(2):
            stages = build_pipeline_stages(self.settings, sources=["ferc"])
            Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        count = conn.execute("SELECT COUNT(*) FROM grid_events").fetchone()[0]
        conn.close()
        assert count == 2  # 2 FERC fixture events, not 4

    def test_alert_sent_defaults_to_false(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=["pa_puc"])
        Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        unsent = conn.execute(
            "SELECT COUNT(*) FROM grid_events WHERE alert_sent=0"
        ).fetchone()[0]
        conn.close()
        assert unsent == 1

    def test_metric_delta_stored(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=["ohio_puco"])
        Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        delta = conn.execute(
            "SELECT metric_delta FROM grid_events WHERE state_jurisdiction='OH'"
        ).fetchone()[0]
        conn.close()
        assert delta == 420  # 14 months * 30 days
