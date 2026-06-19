"""SQLite loader — writes clean datasets to a local SQLite database.

Design notes
────────────
- Uses Python's stdlib ``sqlite3``; no extra ORM dependency.
- Tables are created on first use (``CREATE TABLE IF NOT EXISTS``).
- Records are upserted by primary key so the pipeline is idempotent: re-running
  with the same date window doesn't duplicate rows.
- All writes happen inside a single transaction; failure rolls back cleanly.
- Decimal values are stored as TEXT to preserve precision (SQLite has no DECIMAL
  type; REAL would silently lose precision on large numbers).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Union

import structlog

from fosbury.core.exceptions import LoadError
from fosbury.core.models import ConstraintDataset, DemandDataset, LmpDataset
from fosbury.core.retry import io_retry

log = structlog.get_logger()

Dataset = Union[LmpDataset, ConstraintDataset, DemandDataset]

# ---------------------------------------------------------------------------
# DDL — table schemas
# ---------------------------------------------------------------------------

_DDL: dict[str, str] = {
    "lmp": """
        CREATE TABLE IF NOT EXISTS lmp (
            timestamp_utc   TEXT NOT NULL,
            pnode_id        INTEGER NOT NULL,
            pnode_name      TEXT NOT NULL,
            lmp_total       TEXT NOT NULL,
            lmp_congestion  TEXT NOT NULL,
            lmp_marginal_loss TEXT NOT NULL,
            lmp_energy      TEXT NOT NULL,
            voltage_level   TEXT,
            loaded_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            PRIMARY KEY (timestamp_utc, pnode_id)
        )
    """,
    "constraints": """
        CREATE TABLE IF NOT EXISTS constraints (
            timestamp_utc   TEXT NOT NULL,
            constraint_name TEXT NOT NULL,
            contingency     TEXT,
            shadow_price    TEXT NOT NULL,
            mw_flow         TEXT NOT NULL,
            mw_limit        TEXT NOT NULL,
            pct_loading     TEXT,
            loaded_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            PRIMARY KEY (timestamp_utc, constraint_name, contingency)
        )
    """,
    "demand": """
        CREATE TABLE IF NOT EXISTS demand (
            timestamp_utc   TEXT NOT NULL,
            respondent      TEXT NOT NULL,
            respondent_name TEXT,
            value_mwh       TEXT NOT NULL,
            type_name       TEXT,
            loaded_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            PRIMARY KEY (timestamp_utc, respondent)
        )
    """,
}


class SqliteLoader:
    """Load a dataset into a SQLite database.

    Args:
        db_path: Path to the ``.db`` file (created if absent).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, data: Any) -> int:
        """Upsert *data* into the appropriate SQLite table.

        Args:
            data: One of :class:`LmpDataset`, :class:`ConstraintDataset`,
                  or :class:`DemandDataset`.

        Returns:
            Number of rows written/updated.

        Raises:
            LoadError: On any SQLite error.
        """
        if isinstance(data, LmpDataset):
            return self._load_lmp(data)
        if isinstance(data, ConstraintDataset):
            return self._load_constraints(data)
        if isinstance(data, DemandDataset):
            return self._load_demand(data)
        raise LoadError(f"SqliteLoader does not support dataset type {type(data).__name__}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_tables(self, conn: sqlite3.Connection, *table_names: str) -> None:
        for name in table_names:
            conn.execute(_DDL[name])

    @io_retry(max_attempts=3, wait_seconds=0.5)
    def _load_lmp(self, dataset: LmpDataset) -> int:
        rows = [
            (
                r.timestamp_utc.isoformat(),
                r.pnode_id,
                r.pnode_name,
                str(r.lmp_total),
                str(r.lmp_congestion),
                str(r.lmp_marginal_loss),
                str(r.lmp_energy),
                r.voltage_level,
            )
            for r in dataset.records
        ]
        sql = """
            INSERT OR REPLACE INTO lmp
                (timestamp_utc, pnode_id, pnode_name, lmp_total, lmp_congestion,
                 lmp_marginal_loss, lmp_energy, voltage_level)
            VALUES (?,?,?,?,?,?,?,?)
        """
        return self._bulk_write("lmp", rows, sql)

    @io_retry(max_attempts=3, wait_seconds=0.5)
    def _load_constraints(self, dataset: ConstraintDataset) -> int:
        rows = [
            (
                r.timestamp_utc.isoformat(),
                r.constraint_name,
                r.contingency,
                str(r.shadow_price),
                str(r.mw_flow),
                str(r.mw_limit),
                str(r.pct_loading) if r.pct_loading is not None else None,
            )
            for r in dataset.records
        ]
        sql = """
            INSERT OR REPLACE INTO constraints
                (timestamp_utc, constraint_name, contingency, shadow_price,
                 mw_flow, mw_limit, pct_loading)
            VALUES (?,?,?,?,?,?,?)
        """
        return self._bulk_write("constraints", rows, sql)

    @io_retry(max_attempts=3, wait_seconds=0.5)
    def _load_demand(self, dataset: DemandDataset) -> int:
        rows = [
            (
                r.timestamp_utc.isoformat(),
                r.respondent,
                r.respondent_name,
                str(r.value_mwh),
                r.type_name,
            )
            for r in dataset.records
        ]
        sql = """
            INSERT OR REPLACE INTO demand
                (timestamp_utc, respondent, respondent_name, value_mwh, type_name)
            VALUES (?,?,?,?,?)
        """
        return self._bulk_write("demand", rows, sql)

    def _bulk_write(self, table: str, rows: list[tuple[Any, ...]], sql: str) -> int:
        try:
            with self._connect() as conn:
                self._ensure_tables(conn, table)
                conn.executemany(sql, rows)
                log.debug("sqlite_loader.wrote", table=table, rows=len(rows))
                return len(rows)
        except sqlite3.Error as exc:
            raise LoadError(f"SQLite write failed for table '{table}': {exc}") from exc
