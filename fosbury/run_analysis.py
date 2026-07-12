"""GRP Demand Analysis Runner.

Reads the local SQLite demand table, detects anomalies and trends,
and prints a ranked signal report.  Optionally exports to CSV.

Usage:
    python run_analysis.py                 # print report to terminal
    python run_analysis.py --csv           # also export signals to CSV
    python run_analysis.py --all           # include non-traded respondents

This is informational research only — not financial advice.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Make sure the src layout is on the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fosbury.config.settings import Settings
from fosbury.core.logging import configure_logging
from fosbury.pipelines.demand_analyzer import AnalysisReport, analyze, report_to_df

_ENV = Path(__file__).parent / ".env"
_DIVIDER = "=" * 62


def main() -> None:
    parser = argparse.ArgumentParser(description="GRP demand trend & outlier analysis")
    parser.add_argument("--csv", action="store_true", help="Export signals to demand_signals.csv")
    parser.add_argument("--all", dest="all_respondents", action="store_true",
                        help="Include non-traded ISOs (PJM aggregate etc.)")
    args = parser.parse_args()

    settings = Settings(_env_file=_ENV)
    configure_logging(settings.log_level)

    print(f"\n{_DIVIDER}")
    print("  Grid Realization Pipeline — Demand Analysis")
    print(_DIVIDER)

    report: AnalysisReport = analyze(settings.sqlite_path)

    if "error" in report.summary:
        print(f"\n  ERROR: {report.summary['error']}")
        print("  Run 'python run_example.py' first to populate demand data.\n")
        return

    # ── Summary header ────────────────────────────────────────────────────
    s = report.summary
    print(f"\n  Date range : {s['date_range']}")
    print(f"  Respondents: {s['respondents_analyzed']}  |  Rows: {s['total_rows']}")
    print(f"  Signals    : {s['signals_found']} total  ({s['traded_signals']} for traded equities)\n")

    # Filter to traded-only unless --all
    signals = report.ranked() if args.all_respondents else report.traded_signals
    if not signals:
        signals = report.ranked()  # fall back to all if no traded signals

    if not signals:
        print("  No anomalies detected in current data window.")
        print("  Tip: run 'python run_example.py' to pull fresh data, then re-run.\n")
        return

    # ── Signal table ──────────────────────────────────────────────────────
    _SIGNAL_ICONS = {
        "SPIKE": "⚡",
        "NEW_PEAK": "🔺",
        "WOW_SURGE": "📈",
        "SUSTAINED_GROWTH": "📊",
    }

    print(f"  {'#':>3}  {'TYPE':<18} {'TICKER':<7} {'MWh':>9} {'vs BASE':>9} {'Z':>6}  COMPANY")
    print(f"  {'-'*3}  {'-'*18} {'-'*6} {'-'*9} {'-'*9} {'-'*6}  {'-'*26}")

    for i, sig in enumerate(signals[:20], 1):
        icon = _SIGNAL_ICONS.get(sig.signal_type, "  ")
        ticker_str = sig.ticker if sig.ticker else "—"
        zscore_str = f"{sig.zscore:+.2f}" if sig.zscore != 0 else "  n/a"
        print(
            f"  {i:>3}  {icon} {sig.signal_type:<16} {ticker_str:<7} "
            f"{sig.value_mwh:>9,.0f} {sig.pct_above_baseline:>+8.1f}% {zscore_str:>6}  "
            f"{sig.company_name}"
        )

    # ── Detailed breakdown ────────────────────────────────────────────────
    print(f"\n── Top Signal Detail {'─'*42}")
    for sig in signals[:5]:
        ticker_label = f"[{sig.ticker}]" if sig.ticker else "[non-traded]"
        print(f"\n  {sig.signal_type}  {sig.company_name} {ticker_label}")
        print(f"  Time     : {sig.timestamp_utc}")
        print(f"  Demand   : {sig.value_mwh:,.0f} MWh  (baseline {sig.baseline_mwh:,.0f} MWh)")
        print(f"  Δ vs base: {sig.pct_above_baseline:+.1f}%"
              + (f"  |  Z-score: {sig.zscore:+.2f}σ" if sig.zscore else ""))
        print(f"  Signal   : {sig.notes}")

    # ── Research context ──────────────────────────────────────────────────
    print(f"\n── Research Context {'─'*43}")
    print("""
  How to interpret these signals (informational only):

  SPIKE / NEW_PEAK  — A sudden jump in grid demand above the rolling
    baseline can precede official load-growth disclosures.  Large
    sustained spikes in Dominion (D), Duke (DUK), or FirstEnergy (FE)
    territories often track data-center energisation events that are
    not yet in analyst models.

  WOW_SURGE / SUSTAINED_GROWTH  — A week-over-week trend inflection
    that runs ahead of quarterly earnings guidance revisions.  Utilities
    with AI-hyperscaler interconnection queues (Dominion, AEP, Exelon)
    show load growth faster than rate cases or analyst estimates imply.

  Cross-reference against GRP regulatory events (run_grp.py) to see
  whether any QUEUE_MILESTONE or EQUIPMENT_DELAY filings coincide with
  these demand anomalies — divergence between physical grid data and
  financial models is the core informational edge this tool surfaces.

  ⚠  This is informational research only.  Not financial advice.
""")

    # ── CSV export ────────────────────────────────────────────────────────
    if args.csv:
        df = report_to_df(report)
        out = Path("demand_signals.csv")
        df.to_csv(out, index=False)
        print(f"  Exported {len(df)} signals → {out}\n")


if __name__ == "__main__":
    main()
