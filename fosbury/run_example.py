#!/usr/bin/env python
"""Standalone example: run the full Fosbury pipeline in stub mode.

Usage:
    cd fosbury/
    pip install -e ".[dev]"
    python run_example.py

No API keys required — STUB_MODE is forced to True here.
Results land in ./data/sqlite/fosbury.db and ./data/parquet/.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Make sure the package is importable even without a proper install.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fosbury.config.settings import Settings
from fosbury.core.logging import configure_logging
from fosbury.core.pipeline import Pipeline
from fosbury.registry import build_pipeline_stages


def main() -> None:
    settings = Settings(
        _env_file=Path(__file__).parent / ".env",
        sqlite_path=Path("data/sqlite/fosbury.db"),
        parquet_dir=Path("data/parquet"),
    )

    configure_logging(settings.log_level)
    settings.ensure_storage_dirs()

    print("=" * 60)
    mode = "stub mode" if settings.stub_mode else "live mode"
    print(f"  Project Fosbury — PJM Energy-Grid ETL ({mode})")
    print("=" * 60)
    print()

    stages = build_pipeline_stages(settings)
    results = Pipeline(settings).run(stages)

    print()
    print(f"{'Source':<25} {'Status':<8} {'Rows':>6}  {'Elapsed':>8}")
    print("-" * 55)
    for r in results:
        status = "✓ ok" if r.success else "✗ FAIL"
        print(f"{r.source_key:<25} {status:<8} {r.rows_loaded:>6}  {r.elapsed_s:>7.2f}s")
        if not r.success:
            print(f"   └─ {r.error}")

    print()
    print("─" * 55)
    print("SQLite database:", settings.sqlite_path)
    print("Parquet directory:", settings.parquet_dir)
    print()

    # Quick SQL preview
    if settings.sqlite_path.exists():
        conn = sqlite3.connect(settings.sqlite_path)
        print("── LMP sample (3 rows) ──────────────────────────────────")
        try:
            for row in conn.execute(
                "SELECT timestamp_utc, pnode_name, lmp_total, lmp_congestion "
                "FROM lmp ORDER BY timestamp_utc LIMIT 3"
            ):
                print(f"  {row[0]}  {row[1]:<20}  total={row[2]:>8}  cong={row[3]:>8}")
        except sqlite3.OperationalError as e:
            print(f"  (no lmp table yet: {e})")

        print()
        print("── Binding constraints ─────────────────────────────────")
        try:
            for row in conn.execute(
                "SELECT timestamp_utc, constraint_name, shadow_price, pct_loading "
                "FROM constraints ORDER BY shadow_price DESC LIMIT 3"
            ):
                print(f"  {row[0]}  {row[1][:30]:<30}  shadow=${row[2]:>7}  load={row[3]}%")
        except sqlite3.OperationalError as e:
            print(f"  (no constraints table yet: {e})")

        conn.close()

    print()
    failed = [r for r in results if not r.success]
    if failed:
        print(f"WARNING: {len(failed)} stage(s) failed.")
        sys.exit(1)
    else:
        print("All stages completed successfully.")


if __name__ == "__main__":
    main()
