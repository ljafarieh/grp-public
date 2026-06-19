"""
Entry point: python run_pipeline.py [--date YYYY-MM-DD] [--skip-ingest]

Phases:
  0 — ingest OHLCV for the universe
  1 — detect notable moves, fetch news, attribute moves
  2 — rolling correlations, lead-lag, thesis scorecard, sector rotation
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

from ingestion.ingest import load_cached, load_universe, run_ingestion
from ingestion.news import ingest_news
from analysis.moves import detect_moves_universe
from analysis.attribution import attribute_universe
from analysis.correlations import build_returns_matrix, rolling_correlation_shifts, lead_lag_analysis
from analysis.scorecard import build_scorecard
from analysis.rotation import detect_rotation
from analysis.lookahead import run_lookahead_audit
from analysis.oos import run_oos_validation
from analysis.multiple_testing import build_multiple_testing_audit
from reporting.report import write_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
UNIVERSE_PATH = PROJECT_ROOT / "config" / "universe.yaml"

DISCLAIMER = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOT FINANCIAL ADVICE. This tool is a research and observation
instrument. All outputs are observations or testable hypotheses
with stated confidence levels — not buy/sell recommendations.
Inclusion of any ticker is a research choice, not an endorsement.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def load_analysis_config() -> dict:
    with open(UNIVERSE_PATH) as fh:
        raw = yaml.safe_load(fh)
    return raw.get("analysis", {})


# ---------------------------------------------------------------------------
# Phase 0 printer
# ---------------------------------------------------------------------------

def print_ingestion_summary(results: dict) -> None:
    print("\n=== INGESTION SUMMARY ===\n")
    print(f"{'TICKER':<8}  {'ROLE':<25}  {'ROWS':>5}  {'DATE RANGE':<25}  STATUS")
    print("-" * 90)
    by_role: dict[str, list[str]] = {}
    for ticker, r in results.items():
        by_role.setdefault(r["thesis_role"], []).append(ticker)
    total_rows = 0
    for role in sorted(by_role):
        for ticker in sorted(by_role[role]):
            r = results[ticker]
            total_rows += r["rows"]
            date_range = f"{r['date_start']} → {r['date_end']}" if r["date_start"] else "no data"
            status_short = "ERROR" if r["error"] else ("cache_hit" if "cache" in r["status"] else "updated")
            print(f"{ticker:<8}  {role:<25}  {r['rows']:>5}  {date_range:<25}  {status_short}")
    print("-" * 90)
    print(f"{'TOTAL':<8}  {'':25}  {total_rows:>5}")


# ---------------------------------------------------------------------------
# Phase 1 printer
# ---------------------------------------------------------------------------

def print_move_report(attributed_moves, as_of: date, cfg: dict) -> None:
    zscore_threshold = cfg.get("move_zscore_threshold", 2.0)
    vol_window = cfg.get("vol_window", 20)

    print(f"\n=== NOTABLE MOVES  {as_of}  (|z| >= {zscore_threshold}, vol_window={vol_window}d) ===")
    print("All observations are hypotheses. Confidence levels are stated explicitly.")
    print("A move with no identifiable cause is reported as such -- not narrativized.\n")

    if not attributed_moves:
        print("  No moves exceeded the detection threshold. Universe was quiet.")
        return

    for am in attributed_moves:
        s = am.signal
        direction = "^" if s.daily_return_pct > 0 else "v"
        flags = []
        if s.price_flagged:
            flags.append(f"price z={s.zscore:+.1f}")
        if s.volume_flagged:
            flags.append(f"vol {s.volume_ratio:.1f}x avg")

        print(f"{'─'*70}")
        print(f"  {s.ticker:<6}  {direction} {abs(s.daily_return_pct):.2f}%  |  {', '.join(flags)}")
        print(f"  Close: ${s.close:.2f}  (prev ${s.prev_close:.2f})  |  Trailing vol: {s.trailing_vol_annualized:.0f}% ann.")
        if am.sector_return_pct is not None:
            print(f"  Sector peers avg: {am.sector_return_pct:+.1f}% on same day")
        print(f"\n  {am.summary}\n")
        if am.explanations:
            print("  Candidate explanations (ranked by evidence weight):")
            for ex in am.explanations:
                print(f"    [{ex.rank}] [{ex.confidence.upper()}] {ex.hypothesis}")
                print(f"        Evidence: {ex.evidence}")
        print()

    n_tested = len(attributed_moves)
    expected_false = round(n_tested * 0.05, 1)
    print(f"{'─'*70}")
    print(
        f"  MULTIPLE-COMPARISONS NOTE: {n_tested} flag(s) from universe scan. "
        f"At 2sigma threshold, ~{expected_false} false positives expected by chance. "
        "Treat all as candidates until corroborated."
    )


# ---------------------------------------------------------------------------
# Phase 2 printers
# ---------------------------------------------------------------------------

def print_correlation_report(shifts, lead_lag_results) -> None:
    print("\n=== CORRELATION SHIFTS (recent 30d vs prior 30d) ===")
    print("Pairs where |correlation shift| >= 0.20. More pairs tested = more expected noise.\n")

    if not shifts:
        print("  No significant correlation shifts detected.")
    else:
        n_pairs = shifts[0].n_pairs_tested
        print(f"  {n_pairs} pairs tested. Showing shifts >= 0.20:\n")
        print(f"  {'PAIR':<18}  {'ROLES':<40}  {'PRIOR':>6}  {'RECENT':>6}  {'SHIFT':>6}")
        print(f"  {'-'*18}  {'-'*40}  {'-'*6}  {'-'*6}  {'-'*6}")
        for s in shifts[:15]:
            pair = f"{s.ticker_a}/{s.ticker_b}"
            roles = f"{s.role_a} / {s.role_b}"[:40]
            direction = "+" if s.shift > 0 else ""
            print(f"  {pair:<18}  {roles:<40}  {s.corr_prior:>+.3f}  {s.corr_recent:>+.3f}  {direction}{s.shift:.3f}")

    print(f"\n=== LEAD-LAG (1-day, sector baskets vs benchmarks) ===")
    print("Correlation =/= causation. Bonferroni correction applied for multiple tests.")
    print("'Candidate only' = does not survive correction at p<0.05.\n")

    surviving = [r for r in lead_lag_results if r.survives_correction]
    candidates = [r for r in lead_lag_results if not r.survives_correction]

    n_tests = lead_lag_results[0].n_tests if lead_lag_results else 0
    print(f"  {n_tests} ordered pairs tested. Bonferroni threshold: p < {0.05/n_tests:.4f}\n")

    if surviving:
        print("  Statistically significant after correction:")
        for r in surviving[:10]:
            print(f"    {r.leader} -> {r.follower}  |  r={r.raw_correlation:+.3f}  "
                  f"p_raw={r.raw_pvalue:.4f}  p_corrected={r.corrected_pvalue:.4f}  n={r.n_obs}")
    else:
        print("  No lead-lag relationships survive Bonferroni correction.")
        print("  This is the expected result for daily equity returns — absence of signal is informative.")

    if candidates:
        top_candidates = sorted(candidates, key=lambda x: -abs(x.raw_correlation))[:5]
        print(f"\n  Top uncorrected candidates (treat as noise until out-of-sample validation):")
        for r in top_candidates:
            print(f"    {r.leader} -> {r.follower}  |  r={r.raw_correlation:+.3f}  "
                  f"p_raw={r.raw_pvalue:.4f}  (does NOT survive correction)")


def print_scorecard(scorecard_results, universe_meta: dict) -> None:
    print("\n=== THESIS SCORECARD ===")
    print("Equal-weight basket returns per thesis role vs benchmarks.")
    print("This is a hypothesis scorecard, not a strategy backtest.\n")

    for sc in scorecard_results:
        print(f"  --- Window: {sc.window} (as of {sc.as_of}) ---")

        bench = sc.benchmark_returns
        bench_str = "  ".join(f"{t}: {v:+.1f}%" for t, v in sorted(bench.items()))
        print(f"  Benchmarks: {bench_str}\n")

        print(f"  {'ROLE':<28}  {'TOTAL RTN':>9}  {'ANN RTN':>8}  {'BEST':>6}  {'WORST':>6}  TICKERS")
        print(f"  {'-'*28}  {'-'*9}  {'-'*8}  {'-'*6}  {'-'*6}  {'-'*30}")

        for b in sc.basket_returns:
            vs_spy = b.total_return_pct - bench.get("SPY", 0)
            vs_str = f"({vs_spy:+.1f}% vs SPY)"
            ticker_str = ", ".join(b.tickers)
            print(
                f"  {b.role:<28}  {b.total_return_pct:>+8.1f}%  {b.annualized_return_pct:>+7.1f}%  "
                f"{b.best_ticker_return_pct:>+5.1f}%  {b.worst_ticker_return_pct:>+5.1f}%  "
                f"{ticker_str}  {vs_str}"
            )
        print()


def print_rotation_report(signals) -> None:
    print("=== SECTOR ROTATION ===")
    print("Return rank per thesis role: last 30d vs prior 30d.")
    print("A large rank shift is an observation, not a prediction.\n")

    if not signals:
        print("  Insufficient data for rotation analysis.")
        return

    n = signals[0].n_roles
    print(f"  {'ROLE':<28}  {'PRIOR 30d RTN':>13}  {'RECENT 30d RTN':>14}  "
          f"{'PRIOR RANK':>10}  {'RECENT RANK':>11}  {'SHIFT':>5}  FLAG")
    print(f"  {'-'*28}  {'-'*13}  {'-'*14}  {'-'*10}  {'-'*11}  {'-'*5}  {'-'*4}")
    for s in signals:
        flag = "<<" if s.flagged else ""
        print(
            f"  {s.role:<28}  {s.prior_return_pct:>+12.1f}%  {s.recent_return_pct:>+13.1f}%  "
            f"  {s.prior_rank:>4}/{n}       {s.recent_rank:>4}/{n}  {s.rank_shift:>+5}  {flag}"
        )

    flagged = [s for s in signals if s.flagged]
    if flagged:
        print(f"\n  Flagged rotations (rank shifted > {n//2} positions):")
        for s in flagged:
            direction = "UP" if s.rank_shift > 0 else "DOWN"
            print(f"    {s.role}: moved {direction} {abs(s.rank_shift)} rank(s)  "
                  f"({s.prior_return_pct:+.1f}% prior -> {s.recent_return_pct:+.1f}% recent)  "
                  f"[confidence: low — descriptive only]")
    else:
        print("\n  No large rank shifts detected. Sector return ordering is stable.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="AI-compute research pipeline")
    parser.add_argument("--date", type=str, default=None,
                        help="Analysis date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--skip-ingest", action="store_true",
                        help="Skip OHLCV + news ingestion, use cache only")
    parser.add_argument("--report", action="store_true",
                        help="Write a dated markdown report to reports/YYYY-MM-DD.md")
    parser.add_argument("--validate", action="store_true",
                        help="Run Phase 4 validation (lookahead audit, OOS, multiple-testing)")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.date) if args.date else date.today() - timedelta(days=1)

    print(DISCLAIMER)
    print(f"Pipeline run  |  analysis date: {as_of}\n")

    cfg = load_analysis_config()
    universe = load_universe()

    # --- Phase 0: OHLCV ingestion ---
    if not args.skip_ingest:
        logger.info("Phase 0: ingesting OHLCV...")
        ingest_results = run_ingestion(history_days=365)
        print_ingestion_summary(ingest_results)
    else:
        logger.info("Phase 0: skipped (--skip-ingest)")

    # --- Phase 1a: news ---
    news_source = cfg.get("news_source", "yfinance")
    news_lookback = cfg.get("news_lookback_days", 3)
    max_headlines = cfg.get("max_headlines_per_ticker", 10)

    if not args.skip_ingest:
        logger.info("Phase 1a: ingesting news (source=%s)...", news_source)
        news_counts = ingest_news(
            list(universe.keys()),
            source=news_source,
            lookback_days=news_lookback,
            max_items=max_headlines,
            sleep_between=0.4,
        )
        logger.info("News: %d new headline(s) stored", sum(news_counts.values()))

    # --- Load price cache ---
    logger.info("Loading cached price data...")
    cached_data: dict[str, pd.DataFrame] = {}
    for ticker in universe:
        df = load_cached(ticker)
        if df is not None:
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            cached_data[ticker] = df

    # --- Phase 1b/c: move detection + attribution ---
    vol_window = cfg.get("vol_window", 20)
    zscore_threshold = cfg.get("move_zscore_threshold", 2.0)
    vol_multiplier = cfg.get("volume_spike_multiplier", 2.0)

    logger.info("Phase 1b: detecting moves for %s...", as_of)
    signals = detect_moves_universe(
        cached_data, as_of=as_of,
        vol_window=vol_window,
        zscore_threshold=zscore_threshold,
        volume_multiplier=vol_multiplier,
    )
    logger.info("%d move signal(s) detected", len(signals))

    logger.info("Phase 1c: attributing moves...")
    attributed = attribute_universe(signals, universe, cached_data, news_lookback)
    print_move_report(attributed, as_of, cfg)

    # --- Phase 2a: correlations + lead-lag ---
    logger.info("Phase 2a: computing correlations and lead-lag...")
    returns = build_returns_matrix(cached_data, universe)
    shifts = rolling_correlation_shifts(returns, universe)
    lead_lag = lead_lag_analysis(returns, universe)
    print_correlation_report(shifts, lead_lag)

    # --- Phase 2b: thesis scorecard ---
    logger.info("Phase 2b: building thesis scorecard...")
    scorecard = build_scorecard(cached_data, universe, as_of=as_of)
    print_scorecard(scorecard, universe)

    # --- Phase 2c: sector rotation ---
    logger.info("Phase 2c: detecting sector rotation...")
    rotation = detect_rotation(cached_data, universe, as_of=as_of)
    print_rotation_report(rotation)

    # --- Phase 4: validation harness ---
    lookahead_audit = oos_report = mt_audit = None

    if args.validate:
        logger.info("Phase 4a: running lookahead audit...")
        lookahead_audit = run_lookahead_audit(cached_data, as_of=as_of, vol_window=vol_window)
        status = "PASS" if lookahead_audit.passed else "FAIL"
        print(f"\n=== LOOKAHEAD AUDIT: {status} ===")
        print(f"  {lookahead_audit.n_passed} checks passed, {lookahead_audit.n_failed} failed.")
        failures = [c for c in lookahead_audit.checks if not c.passed]
        if failures:
            for c in failures:
                print(f"  FAIL: {c.name} — {c.detail}")
        else:
            print("  No lookahead violations detected.")

        logger.info("Phase 4b: running out-of-sample validation...")
        oos_report = run_oos_validation(cached_data, universe)
        print(f"\n=== OUT-OF-SAMPLE VALIDATION ===")
        print(f"  IS: {oos_report.split.is_start} → {oos_report.split.is_end} "
              f"({oos_report.split.is_trading_days} days)")
        print(f"  OOS: {oos_report.split.oos_start} → {oos_report.split.oos_end} "
              f"({oos_report.split.oos_trading_days} days)")
        for f in oos_report.findings:
            print(f"  {f.verdict:<22}  {f.test_name}")
            print(f"    IS:  {f.is_result}")
            print(f"    OOS: {f.oos_result}")

        logger.info("Phase 4c: building multiple-testing audit...")
        mt_audit = build_multiple_testing_audit(
            correlation_shifts=shifts,
            lead_lag_results=lead_lag,
            n_move_tickers=len(universe),
            zscore_threshold=zscore_threshold,
        )
        print(f"\n=== MULTIPLE-TESTING AUDIT ===")
        print(f"  Total tests: {mt_audit.total_tests} | "
              f"Raw findings: {mt_audit.total_raw_findings} | "
              f"Bonferroni survivors: {mt_audit.total_bonferroni_findings}")
        for f in mt_audit.families:
            print(f"  {f.name}: {f.n_tests} tests, ~{f.expected_false_positives} expected FP")

    # --- Phase 3: markdown report ---
    if args.report:
        report_path = write_report(
            as_of=as_of,
            attributed=attributed,
            shifts=shifts,
            lead_lag=lead_lag,
            scorecard=scorecard,
            rotation=rotation,
            zscore_threshold=zscore_threshold,
            vol_window=vol_window,
            lookahead_audit=lookahead_audit,
            oos_report=oos_report,
            mt_audit=mt_audit,
        )
        print(f"\nReport written to: {report_path}")

    print(f"\nRun complete.")
    print("  --skip-ingest   re-run analysis on cached data only")
    print("  --report        write dated markdown to reports/")
    print("  --validate      run Phase 4 lookahead + OOS + multiple-testing audit\n")


if __name__ == "__main__":
    main()
