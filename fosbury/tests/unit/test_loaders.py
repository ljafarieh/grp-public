"""Unit tests for SQLite and Parquet loaders."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fosbury.core.models import (
    ConstraintDataset,
    ConstraintRecord,
    DemandDataset,
    DemandRecord,
    LmpDataset,
    LmpRecord,
)
from fosbury.loaders.parquet_loader import ParquetLoader
from fosbury.loaders.sqlite_loader import SqliteLoader


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def lmp_dataset() -> LmpDataset:
    return LmpDataset(
        source="test",
        records=[
            LmpRecord(
                timestamp_utc=datetime(2026, 6, 18, 0, 0),
                pnode_id=1,
                pnode_name="HUB A",
                lmp_total=Decimal("30.50"),
                lmp_congestion=Decimal("-1.00"),
                lmp_marginal_loss=Decimal("0.50"),
                lmp_energy=Decimal("31.00"),
            ),
            LmpRecord(
                timestamp_utc=datetime(2026, 6, 18, 0, 5),
                pnode_id=2,
                pnode_name="HUB B",
                lmp_total=Decimal("28.00"),
                lmp_congestion=Decimal("0.00"),
                lmp_marginal_loss=Decimal("0.00"),
                lmp_energy=Decimal("28.00"),
            ),
        ],
    )


@pytest.fixture()
def constraint_dataset() -> ConstraintDataset:
    return ConstraintDataset(
        source="test",
        records=[
            ConstraintRecord(
                timestamp_utc=datetime(2026, 6, 18, 0, 0),
                constraint_name="LINE-A 500",
                contingency="N-1 LINE-A",
                shadow_price=Decimal("45.75"),
                mw_flow=Decimal("1820.5"),
                mw_limit=Decimal("2000.0"),
                pct_loading=Decimal("91.025"),
            )
        ],
    )


@pytest.fixture()
def demand_dataset() -> DemandDataset:
    return DemandDataset(
        source="test",
        records=[
            DemandRecord(
                timestamp_utc=datetime(2026, 6, 18, 0, 0),
                respondent="PJM",
                respondent_name="PJM Interconnection",
                value_mwh=Decimal("112500"),
                type_name="Demand",
            )
        ],
    )


# ---------------------------------------------------------------------------
# SQLite loader
# ---------------------------------------------------------------------------


class TestSqliteLoader:
    def test_load_lmp(self, tmp_path: Path, lmp_dataset: LmpDataset) -> None:
        loader = SqliteLoader(tmp_path / "test.db")
        rows = loader.load(lmp_dataset)
        assert rows == 2

    def test_load_constraints(self, tmp_path: Path, constraint_dataset: ConstraintDataset) -> None:
        loader = SqliteLoader(tmp_path / "test.db")
        rows = loader.load(constraint_dataset)
        assert rows == 1

    def test_load_demand(self, tmp_path: Path, demand_dataset: DemandDataset) -> None:
        loader = SqliteLoader(tmp_path / "test.db")
        rows = loader.load(demand_dataset)
        assert rows == 1

    def test_idempotent_upsert(self, tmp_path: Path, lmp_dataset: LmpDataset) -> None:
        """Loading the same dataset twice must not duplicate rows."""
        import sqlite3

        db = tmp_path / "test.db"
        loader = SqliteLoader(db)
        loader.load(lmp_dataset)
        loader.load(lmp_dataset)

        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM lmp").fetchone()[0]
        conn.close()
        assert count == 2  # not 4

    def test_decimal_precision_preserved(self, tmp_path: Path, lmp_dataset: LmpDataset) -> None:
        """Decimal values must round-trip as strings without floating-point drift."""
        import sqlite3

        db = tmp_path / "test.db"
        SqliteLoader(db).load(lmp_dataset)

        conn = sqlite3.connect(db)
        row = conn.execute("SELECT lmp_total FROM lmp WHERE pnode_id=1").fetchone()
        conn.close()
        assert row[0] == "30.50"


# ---------------------------------------------------------------------------
# Parquet loader
# ---------------------------------------------------------------------------


class TestParquetLoader:
    def test_load_lmp(self, tmp_path: Path, lmp_dataset: LmpDataset) -> None:
        loader = ParquetLoader(tmp_path)
        rows = loader.load(lmp_dataset)
        assert rows == 2

    def test_creates_date_partition(self, tmp_path: Path, lmp_dataset: LmpDataset) -> None:
        ParquetLoader(tmp_path).load(lmp_dataset)
        partitions = list((tmp_path / "lmp").glob("date=*"))
        assert len(partitions) == 1
        assert (partitions[0] / "lmp.parquet").exists()

    def test_load_constraints(self, tmp_path: Path, constraint_dataset: ConstraintDataset) -> None:
        rows = ParquetLoader(tmp_path).load(constraint_dataset)
        assert rows == 1

    def test_load_demand(self, tmp_path: Path, demand_dataset: DemandDataset) -> None:
        rows = ParquetLoader(tmp_path).load(demand_dataset)
        assert rows == 1

    def test_parquet_readable_with_pandas(self, tmp_path: Path, lmp_dataset: LmpDataset) -> None:
        import pandas as pd

        ParquetLoader(tmp_path).load(lmp_dataset)
        files = list((tmp_path / "lmp").rglob("*.parquet"))
        df = pd.read_parquet(files[0])
        assert "lmp_total" in df.columns
        assert len(df) == 2
