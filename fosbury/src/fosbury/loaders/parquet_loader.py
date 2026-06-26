"""Parquet loader — writes clean datasets to partitioned Parquet files.

Design notes
────────────
- Uses ``pandas`` + ``pyarrow`` engine for columnar efficiency.
- Files are partitioned by date: ``<parquet_dir>/<table>/date=YYYY-MM-DD/<table>.parquet``
  This makes downstream DuckDB / Polars queries trivially fast for date ranges.
- Each run overwrites the partition for the dates it covers, keeping the store
  idempotent (safe to re-run with the same date window).
- Decimal columns are converted to float64 for wide Parquet compatibility; the
  SQLite loader retains Decimal strings for precision when needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import pandas as pd
import structlog

from fosbury.core.exceptions import LoadError
from fosbury.core.models import ConstraintDataset, DemandDataset, LmpDataset
from fosbury.core.retry import io_retry

log = structlog.get_logger()

Dataset = Union[LmpDataset, ConstraintDataset, DemandDataset]


class ParquetLoader:
    """Load a dataset into date-partitioned Parquet files.

    Args:
        parquet_dir: Root directory for Parquet output.
    """

    def __init__(self, parquet_dir: Path) -> None:
        self._root = parquet_dir
        parquet_dir.mkdir(parents=True, exist_ok=True)

    def load(self, data: Any) -> int:
        """Write *data* to the appropriate Parquet partition.

        Args:
            data: One of :class:`LmpDataset`, :class:`ConstraintDataset`,
                  or :class:`DemandDataset`.

        Returns:
            Total number of rows written across all partitions.

        Raises:
            LoadError: On any I/O or serialisation error.
        """
        if isinstance(data, LmpDataset):
            return self._write(self._to_lmp_df(data), table="lmp")
        if isinstance(data, ConstraintDataset):
            return self._write(self._to_constraints_df(data), table="constraints")
        if isinstance(data, DemandDataset):
            return self._write(self._to_demand_df(data), table="demand")
        raise LoadError(f"ParquetLoader does not support dataset type {type(data).__name__}")

    # ------------------------------------------------------------------
    # Private helpers — DataFrame builders
    # ------------------------------------------------------------------

    @staticmethod
    def _to_lmp_df(dataset: LmpDataset) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "timestamp_utc": r.timestamp_utc,
                    "pnode_id": r.pnode_id,
                    "pnode_name": r.pnode_name,
                    "lmp_total": float(r.lmp_total),
                    "lmp_congestion": float(r.lmp_congestion),
                    "lmp_marginal_loss": float(r.lmp_marginal_loss),
                    "lmp_energy": float(r.lmp_energy),
                    "voltage_level": r.voltage_level,
                }
                for r in dataset.records
            ]
        )

    @staticmethod
    def _to_constraints_df(dataset: ConstraintDataset) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "timestamp_utc": r.timestamp_utc,
                    "constraint_name": r.constraint_name,
                    "contingency": r.contingency,
                    "shadow_price": float(r.shadow_price),
                    "mw_flow": float(r.mw_flow),
                    "mw_limit": float(r.mw_limit),
                    "pct_loading": float(r.pct_loading) if r.pct_loading is not None else None,
                }
                for r in dataset.records
            ]
        )

    @staticmethod
    def _to_demand_df(dataset: DemandDataset) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "timestamp_utc": r.timestamp_utc,
                    "respondent": r.respondent,
                    "respondent_name": r.respondent_name,
                    "value_mwh": float(r.value_mwh),
                    "type_name": r.type_name,
                    "ticker": r.ticker,
                    "company_name": r.company_name,
                }
                for r in dataset.records
            ]
        )

    @io_retry(max_attempts=3, wait_seconds=0.5)
    def _write(self, df: pd.DataFrame, table: str) -> int:
        """Write *df* to date-partitioned Parquet files under *table/*.

        Each unique date in the dataframe gets its own directory partition.
        """
        if df.empty:
            log.warning("parquet_loader.empty_df", table=table)
            return 0

        if "timestamp_utc" not in df.columns:
            raise LoadError(f"DataFrame for table '{table}' has no 'timestamp_utc' column")

        # Normalise timestamps
        df = df.copy()
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        df["_date"] = df["timestamp_utc"].dt.date

        total = 0
        for date_val, partition_df in df.groupby("_date"):
            out_dir = self._root / table / f"date={date_val}"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{table}.parquet"
            partition_df.drop(columns=["_date"]).to_parquet(
                out_path,
                engine="pyarrow",
                index=False,
                compression="snappy",
            )
            total += len(partition_df)
            log.debug("parquet_loader.wrote", table=table, date=str(date_val), rows=len(partition_df))

        return total
