#!/usr/bin/env python
"""Grid Realization Pipeline (GRP) — full regulatory intelligence run.

Runs all four regulatory scrapers (VA SCC, Ohio PUCO, PA PUC, FERC),
writes events to SQLite, and optionally dispatches Discord research alerts.

Usage:
    cd fosbury/
    source .venv/bin/activate
    python run_grp.py                   # stub mode (default)
    python run_grp.py --live            # live scrape (no PJM key needed)
    python run_grp.py --alerts          # also fire Discord alerts
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from fosbury.config.settings import Settings
from fosbury.core.logging import configure_logging
from fosbury.core.pipeline import Pipeline
from fosbury.pipelines.alert_engine import process_pending_alerts
from fosbury.registry import build_pipeline_stages

GRP_SOURCES = ["va_scc", "ohio_puco", "pa_puc", "ferc"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid Realization Pipeline")
    parser.add_argument("--live", action="store_true", help="Run live scrapers (default: stub)")
    parser.add_argument("--alerts", action="store_true", help="Dispatch Discord research alerts")
    args = parser.parse_args()

    settings = Settings(
        _env_file=Path(__file__).parent / ".env",
        stub_mode=not args.live,
        sqlite_path=Path("data/sqlite/fosbury.db"),
        parquet_dir=Path("data/parquet"),
    )

    configure_logging(settings.log_level)
    settings.ensure_storage_dirs()

    mode = "LIVE" if not settings.stub_mode else "STUB"
    print("=" * 62)
    print(f"  Grid Realization Pipeline (GRP) — {mode} MODE")
    print("=" * 62)
    print()

    stages = build_pipeline_stages(settings, sources=GRP_SOURCES)
    results = Pipeline(settings).run(stages)

    print()
    print(f"{'Source':<18} {'Status':<8} {'Events':>7}  {'Elapsed':>8}")
    print("-" * 50)
    total_events = 0
    for r in results:
        status = "✓ ok" if r.success else "✗ FAIL"
        print(f"{r.source_key:<18} {status:<8} {r.rows_loaded:>7}  {r.elapsed_s:>7.2f}s")
        if not r.success:
            print(f"   └─ {r.error}")
        total_events += r.rows_loaded

    print()
    print(f"Total new events written: {total_events}")
    print(f"Database: {settings.sqlite_path}")
    print()

    # Show grid_events summary from SQLite
    if settings.sqlite_path.exists():
        _print_event_summary(settings.sqlite_path)

    # Discord alerts
    if args.alerts:
        if not settings.discord_webhook_url:
            print("WARNING: --alerts flag set but DISCORD_WEBHOOK_URL is not configured in .env")
        else:
            sent = process_pending_alerts(settings.sqlite_path, settings.discord_webhook_url)
            print(f"Discord alerts dispatched: {sent}")

    failed = [r for r in results if not r.success]
    if failed:
        sys.exit(1)


def _print_event_summary(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    print("── Grid Events Summary ─────────────────────────────────")
    try:
        rows = conn.execute(
            """
            SELECT entity_target, data_type, metric_delta, state_jurisdiction,
                   substr(raw_text_blob, 1, 90) as excerpt
            FROM grid_events
            ORDER BY scraped_at DESC
            LIMIT 10
            """
        ).fetchall()
        for row in rows:
            entity, dtype, delta, state, excerpt = row
            delta_str = f"{delta}d" if delta else "—"
            print(f"  [{state}] {entity:<28} {dtype:<22} Δ={delta_str}")
            print(f"      └─ {excerpt}...")
            print()
    except sqlite3.OperationalError:
        print("  (no grid_events table yet)")
    conn.close()


if __name__ == "__main__":
    main()
