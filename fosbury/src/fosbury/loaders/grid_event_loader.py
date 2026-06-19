"""SQLite loader for :class:`~fosbury.core.models.GridEventDataset`.

The ``grid_events`` table uses ``event_id`` (SHA-256 hash) as the primary
key so re-runs with overlapping date windows never produce duplicate rows.
``keywords_matched`` is stored as a comma-separated string for simplicity;
the alert engine re-splits it on read.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import structlog

from fosbury.core.exceptions import LoadError
from fosbury.core.models import GridEventDataset
from fosbury.core.retry import io_retry

log = structlog.get_logger()

_DDL = """
    CREATE TABLE IF NOT EXISTS grid_events (
        event_id            TEXT PRIMARY KEY,
        iso_region          TEXT NOT NULL,
        state_jurisdiction  TEXT NOT NULL,
        entity_target       TEXT NOT NULL,
        data_type           TEXT NOT NULL,
        raw_text_blob       TEXT,
        metric_delta        INTEGER DEFAULT 0,
        keywords_matched    TEXT,
        source_url          TEXT,
        scraped_at          TEXT NOT NULL,
        alert_sent          INTEGER NOT NULL DEFAULT 0,
        loaded_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )
"""


class GridEventLoader:
    """Upsert a :class:`GridEventDataset` into the ``grid_events`` SQLite table.

    Args:
        db_path: Path to the fosbury SQLite database file.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, data: Any) -> int:
        """Write *data* to ``grid_events``.

        Args:
            data: A :class:`~fosbury.core.models.GridEventDataset` instance.

        Returns:
            Number of rows written.

        Raises:
            LoadError: On any SQLite error.
        """
        if not isinstance(data, GridEventDataset):
            raise LoadError(
                f"GridEventLoader expects GridEventDataset, got {type(data).__name__}"
            )
        return self._write(data)

    @io_retry(max_attempts=3, wait_seconds=0.5)
    def _write(self, dataset: GridEventDataset) -> int:
        rows = [
            (
                rec.event_id,
                rec.iso_region,
                rec.state_jurisdiction,
                rec.entity_target,
                rec.data_type,
                rec.raw_text_blob,
                rec.metric_delta,
                ",".join(rec.keywords_matched),
                rec.source_url,
                rec.scraped_at.isoformat(),
                int(rec.alert_sent),
            )
            for rec in dataset.records
        ]

        sql = """
            INSERT OR IGNORE INTO grid_events
                (event_id, iso_region, state_jurisdiction, entity_target,
                 data_type, raw_text_blob, metric_delta, keywords_matched,
                 source_url, scraped_at, alert_sent)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """

        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(_DDL)
                conn.executemany(sql, rows)
                log.debug("grid_event_loader.wrote", rows=len(rows))
                return len(rows)
        except sqlite3.Error as exc:
            raise LoadError(f"SQLite write failed for grid_events: {exc}") from exc
