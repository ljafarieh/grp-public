"""Integration test: full stub pipeline run end-to-end.

Runs all registered sources against fixture JSON (no network, no live
credentials) and verifies that data lands in SQLite and Parquet.

Note: pjm_lmp and pjm_constraints are disabled in the registry until a
PJM subscription key is available. Only eia_demand and GRP regulatory
sources are active.

Marked ``integration`` so you can skip in fast unit-only CI:
    pytest -m "not integration"
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from fosbury.config.settings import Settings
from fosbury.core.pipeline import Pipeline
from fosbury.registry import build_pipeline_stages


@pytest.mark.integration
class TestStubPipelineEndToEnd:
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
        self.tmp_path = tmp_path

    def test_all_active_stages_succeed(self) -> None:
        # All currently registered sources (pjm_lmp/constraints disabled)
        stages = build_pipeline_stages(self.settings)
        results = Pipeline(self.settings).run(stages)
        for r in results:
            assert r.success, f"Stage {r.source_key} failed: {r.error}"

    def test_demand_rows_in_sqlite(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=["eia_demand"])
        Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        rows = conn.execute("SELECT COUNT(*) FROM demand").fetchone()[0]
        conn.close()
        assert rows == 3

    def test_parquet_files_created_for_demand(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=["eia_demand"])
        Pipeline(self.settings).run(stages)

        files = list((self.settings.parquet_dir / "demand").rglob("*.parquet"))
        assert files, "No Parquet files found for demand table"

    def test_parquet_demand_readable(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=["eia_demand"])
        Pipeline(self.settings).run(stages)

        files = list((self.settings.parquet_dir / "demand").rglob("*.parquet"))
        df = pd.read_parquet(files[0])
        assert "value_mwh" in df.columns
        assert len(df) > 0

    def test_idempotent_rerun_demand(self) -> None:
        """Running twice must not double the row count."""
        for _ in range(2):
            stages = build_pipeline_stages(self.settings, sources=["eia_demand"])
            Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        rows = conn.execute("SELECT COUNT(*) FROM demand").fetchone()[0]
        conn.close()
        assert rows == 3

    def test_selective_source_run(self) -> None:
        """Running one source must not create tables for others."""
        stages = build_pipeline_stages(self.settings, sources=["eia_demand"])
        Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "demand" in tables
        assert "lmp" not in tables
