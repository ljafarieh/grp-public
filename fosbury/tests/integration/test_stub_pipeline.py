"""Integration test: full stub pipeline run end-to-end.

Runs all three registered sources against fixture JSON (no network, no live
credentials) and verifies that data lands in both SQLite and Parquet.

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

    def test_all_stages_succeed(self) -> None:
        stages = build_pipeline_stages(self.settings)
        results = Pipeline(self.settings).run(stages)

        assert len(results) == 3
        for r in results:
            assert r.success, f"Stage {r.source_key} failed: {r.error}"

    def test_lmp_rows_in_sqlite(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=["pjm_lmp"])
        Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        rows = conn.execute("SELECT COUNT(*) FROM lmp").fetchone()[0]
        conn.close()
        assert rows == 3  # matches fixture row count

    def test_constraints_rows_in_sqlite(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=["pjm_constraints"])
        Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        rows = conn.execute("SELECT COUNT(*) FROM constraints").fetchone()[0]
        conn.close()
        assert rows == 2

    def test_demand_rows_in_sqlite(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=["eia_demand"])
        Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        rows = conn.execute("SELECT COUNT(*) FROM demand").fetchone()[0]
        conn.close()
        assert rows == 3

    def test_parquet_files_created(self) -> None:
        stages = build_pipeline_stages(self.settings)
        Pipeline(self.settings).run(stages)

        parquet_root = self.settings.parquet_dir
        for table in ("lmp", "constraints", "demand"):
            files = list((parquet_root / table).rglob("*.parquet"))
            assert files, f"No Parquet files found for table '{table}'"

    def test_parquet_lmp_readable(self) -> None:
        stages = build_pipeline_stages(self.settings, sources=["pjm_lmp"])
        Pipeline(self.settings).run(stages)

        files = list((self.settings.parquet_dir / "lmp").rglob("*.parquet"))
        df = pd.read_parquet(files[0])
        assert set(df.columns) >= {"timestamp_utc", "pnode_id", "lmp_total", "lmp_congestion"}
        assert len(df) == 3

    def test_selective_source_run(self) -> None:
        """Running a single source must not create tables for others."""
        stages = build_pipeline_stages(self.settings, sources=["pjm_lmp"])
        Pipeline(self.settings).run(stages)

        conn = sqlite3.connect(self.settings.sqlite_path)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "lmp" in tables
        assert "constraints" not in tables
        assert "demand" not in tables

    def test_idempotent_rerun(self) -> None:
        """Running twice must not double the row count."""
        stages_1 = build_pipeline_stages(self.settings, sources=["pjm_lmp"])
        stages_2 = build_pipeline_stages(self.settings, sources=["pjm_lmp"])
        Pipeline(self.settings).run(stages_1)
        Pipeline(self.settings).run(stages_2)

        conn = sqlite3.connect(self.settings.sqlite_path)
        rows = conn.execute("SELECT COUNT(*) FROM lmp").fetchone()[0]
        conn.close()
        assert rows == 3
