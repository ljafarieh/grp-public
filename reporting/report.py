"""
Markdown report writer. Assembles all pipeline outputs into a dated
research document at reports/YYYY-MM-DD.md.

Every section carries explicit epistemic framing: observations and
hypotheses with confidence levels, never recommendations.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from analysis.attribution import AttributedMove
from analysis.correlations import CorrelationShift, LeadLagResult
from analysis.lookahead import LookaheadAuditReport
from analysis.multiple_testing import MultipleTestingAudit
from analysis.oos import OOSReport
from analysis.rotation import RotationSignal
from analysis.scorecard import ScorecardResult

PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"

DISCLAIMER = """\
> **NOT FINANCIAL ADVICE.** This document is a research and observation record.
> Every item below is an observation or a testable hypothesis with a stated
> confidence level — not a buy, sell, or hold recommendation. Inclusion of any
> ticker is a research choice, not an endorsement. Confidence levels (LOW /
> MEDIUM / HIGH) reflect the strength of available evidence, not certainty.
"""


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _header(as_of: date, generated_at: datetime) -> str:
    return f"""\
# AI-Compute Buildout Research Report

**Date:** {as_of}
**Generated:** {generated_at.strftime("%Y-%m-%d %H:%M UTC")}
**Thesis lens:** Aschenbrenner (June 2024) *Situational Awareness* — treated as a
testable hypothesis, not received wisdom.

---

{DISCLAIMER}

---
"""


def _section_notable_moves(
    attributed: list[AttributedMove],
    as_of: date,
    zscore_threshold: float,
    vol_window: int,
) -> str:
    lines = [
        f"## Notable Moves — {as_of}",
        "",
        f"Detection method: daily return z-score ≥ {zscore_threshold} vs trailing "
        f"{vol_window}-day realized volatility. Volume spike: today > 2× 20-day average. "
        "Moves are flagged relative to each ticker's own baseline — a volatile name "
        "is not flagged for every normal-sized day.",
        "",
    ]

    if not attributed:
        lines += [
            "_No moves exceeded the detection threshold today._",
            "",
            "> **Observation:** The universe was quiet on this date. "
            "This is a valid and informative result — not a failure of the tool.",
            "",
        ]
        return "\n".join(lines)

    for am in attributed:
        s = am.signal
        direction = "▲" if s.daily_return_pct > 0 else "▼"
        flags = []
        if s.price_flagged:
            flags.append(f"price z={s.zscore:+.1f}")
        if s.volume_flagged:
            flags.append(f"volume {s.volume_ratio:.1f}× avg")

        lines += [
            f"### {s.ticker} &nbsp; {direction} {abs(s.daily_return_pct):.2f}%",
            "",
            f"| Field | Value |",
            f"|---|---|",
            f"| Close | ${s.close:.2f} (prev ${s.prev_close:.2f}) |",
            f"| Return | {s.daily_return_pct:+.2f}% |",
            f"| Z-score | {s.zscore:+.2f} |",
            f"| Trailing vol (ann.) | {s.trailing_vol_annualized:.0f}% |",
            f"| Flags | {', '.join(flags)} |",
        ]
        if am.sector_return_pct is not None:
            lines.append(f"| Sector peers avg | {am.sector_return_pct:+.1f}% |")
        lines += ["", f"**Summary:** {am.summary}", ""]

        if am.explanations:
            lines.append("**Candidate explanations (ranked by evidence):**")
            lines.append("")
            for ex in am.explanations:
                lines.append(
                    f"{ex.rank}. **[{ex.confidence.upper()} confidence]** {ex.hypothesis}  "
                )
                lines.append(f"   *Evidence:* {ex.evidence}")
                lines.append("")

        lines.append("---")
        lines.append("")

    n = len(attributed)
    expected_false = round(n * 0.05, 1)
    lines += [
        f"> **Multiple-comparisons note:** {n} signal(s) from universe scan. "
        f"At a 2σ threshold, ~{expected_false} false positive(s) expected by chance. "
        "All findings are candidates until independently corroborated.",
        "",
    ]
    return "\n".join(lines)


def _section_correlations(
    shifts: list[CorrelationShift],
    lead_lag: list[LeadLagResult],
) -> str:
    lines = [
        "## Correlation Shifts",
        "",
        "Rolling 30-day correlation vs prior 30-day correlation. "
        "A shift ≥ 0.20 is flagged. **Correlation ≠ causation.** "
        "With many pairs tested, some shifts are expected by chance.",
        "",
    ]

    if not shifts:
        lines += ["_No correlation shifts ≥ 0.20 detected._", ""]
    else:
        n_pairs = shifts[0].n_pairs_tested
        lines += [
            f"_{n_pairs} pairs tested. Showing largest shifts (≥ 0.20):_",
            "",
            "| Pair | Roles | Prior corr | Recent corr | Shift |",
            "|---|---|---:|---:|---:|",
        ]
        for s in shifts[:12]:
            direction = "↑" if s.shift > 0 else "↓"
            lines.append(
                f"| {s.ticker_a}/{s.ticker_b} | {s.role_a} / {s.role_b} "
                f"| {s.corr_prior:+.3f} | {s.corr_recent:+.3f} | {direction} {abs(s.shift):.3f} |"
            )
        lines += [""]

    lines += [
        "## Lead-Lag Analysis (1-day)",
        "",
        "Tests whether sector A's return on day T predicts sector B's return on day T+1. "
        "Bonferroni correction applied. **Correlation ≠ causation.**",
        "",
    ]

    surviving = [r for r in lead_lag if r.survives_correction]
    candidates = [r for r in lead_lag if not r.survives_correction]
    n_tests = lead_lag[0].n_tests if lead_lag else 0

    lines += [
        f"_{n_tests} ordered pairs tested. "
        f"Bonferroni threshold: p < {0.05/n_tests:.4f}_",
        "",
    ]

    if surviving:
        lines += [
            "**Statistically significant after correction:**",
            "",
            "| Leader | Follower | r | p (raw) | p (corrected) | n obs |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for r in surviving[:8]:
            lines.append(
                f"| {r.leader} | {r.follower} | {r.raw_correlation:+.3f} "
                f"| {r.raw_pvalue:.4f} | {r.corrected_pvalue:.4f} | {r.n_obs} |"
            )
        lines += [""]
    else:
        lines += [
            "> **Observation:** No lead-lag relationships survive Bonferroni correction. "
            "This is the expected result for daily equity returns and is itself informative — "
            "the universe is not exhibiting exploitable day-ahead predictability.",
            "",
        ]

    if candidates:
        top = sorted(candidates, key=lambda x: -abs(x.raw_correlation))[:5]
        lines += [
            "**Top uncorrected candidates** *(do not treat as findings — candidate only):*",
            "",
            "| Leader | Follower | r | p (raw) |",
            "|---|---|---:|---:|",
        ]
        for r in top:
            lines.append(
                f"| {r.leader} | {r.follower} | {r.raw_correlation:+.3f} | {r.raw_pvalue:.4f} |"
            )
        lines += [""]

    return "\n".join(lines)


def _section_scorecard(scorecard: list[ScorecardResult]) -> str:
    lines = [
        "## Thesis Scorecard",
        "",
        "Equal-weight basket total returns per thesis role vs benchmarks. "
        "**This is a hypothesis scorecard, not a strategy backtest.** "
        "Past returns do not predict future returns.",
        "",
    ]

    for sc in scorecard:
        bench = sc.benchmark_returns
        bench_str = " &nbsp;|&nbsp; ".join(
            f"**{t}:** {v:+.1f}%" for t, v in sorted(bench.items())
        )
        lines += [
            f"### Window: {sc.window}",
            "",
            f"Benchmarks: {bench_str}",
            "",
            "| Role | Total return | Ann. return | vs SPY | Best ticker | Worst ticker | Tickers |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
        spy_ret = bench.get("SPY", 0.0)
        for b in sc.basket_returns:
            vs_spy = b.total_return_pct - spy_ret
            vs_str = f"{vs_spy:+.1f}%"
            ticker_str = ", ".join(b.tickers)
            lines.append(
                f"| {b.role} | {b.total_return_pct:+.1f}% | {b.annualized_return_pct:+.1f}% "
                f"| {vs_str} | {b.best_ticker} {b.best_ticker_return_pct:+.1f}% "
                f"| {b.worst_ticker} {b.worst_ticker_return_pct:+.1f}% | {ticker_str} |"
            )
        lines += [""]

    return "\n".join(lines)


def _section_rotation(signals: list[RotationSignal]) -> str:
    lines = [
        "## Sector Rotation",
        "",
        "Return rank per thesis role: last 30 days vs prior 30 days. "
        "A large rank shift is a descriptive observation — not a prediction.",
        "",
    ]

    if not signals:
        lines += ["_Insufficient data for rotation analysis._", ""]
        return "\n".join(lines)

    n = signals[0].n_roles
    lines += [
        f"| Role | Prior 30d return | Recent 30d return | Prior rank | Recent rank | Shift |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for s in signals:
        flag = " ◀" if s.flagged else ""
        lines.append(
            f"| {s.role}{flag} | {s.prior_return_pct:+.1f}% | {s.recent_return_pct:+.1f}% "
            f"| {s.prior_rank}/{n} | {s.recent_rank}/{n} | {s.rank_shift:+d} |"
        )
    lines += [""]

    flagged = [s for s in signals if s.flagged]
    if flagged:
        lines += ["**Flagged rotations** *(rank shifted > half the field — LOW confidence, descriptive only):*", ""]
        for s in flagged:
            direction = "up" if s.rank_shift > 0 else "down"
            lines.append(
                f"- **{s.role}** moved {direction} {abs(s.rank_shift)} rank(s): "
                f"{s.prior_return_pct:+.1f}% (prior 30d) → {s.recent_return_pct:+.1f}% (recent 30d)"
            )
        lines += [""]
    else:
        lines += ["> Sector return ordering is stable — no large rank shifts.", ""]

    return "\n".join(lines)


def _section_noise_summary(
    attributed: list[AttributedMove],
    lead_lag: list[LeadLagResult],
    shifts: list[CorrelationShift],
    signals: list[RotationSignal],
) -> str:
    lines = [
        "## Noise and Uncertainty Summary",
        "",
        "This section explicitly catalogs what is uncertain, weak, or likely noise. "
        "An honest tool surfaces its own limits.",
        "",
    ]

    uncertain = []
    solid = []

    # Move attribution quality
    no_cause = [am for am in attributed if am.explanations and am.explanations[0].source == "none"]
    low_conf = [am for am in attributed
                if am.explanations and am.explanations[0].confidence == "low"
                and am.explanations[0].source != "none"]
    if no_cause:
        tickers = ", ".join(am.signal.ticker for am in no_cause)
        uncertain.append(
            f"**{tickers}** flagged move(s) with no identifiable cause — "
            "likely noise or driven by information not in this dataset."
        )
    if low_conf:
        tickers = ", ".join(am.signal.ticker for am in low_conf)
        uncertain.append(
            f"**{tickers}** flagged move(s) attributed with LOW confidence only — "
            "treat explanations as hypotheses requiring corroboration."
        )
    if attributed and not no_cause and not low_conf:
        solid.append("All flagged moves have at least MEDIUM-confidence candidate explanations.")

    # Lead-lag
    surviving_ll = [r for r in lead_lag if r.survives_correction]
    if not surviving_ll:
        uncertain.append(
            "No lead-lag relationships survive multiple-testing correction — "
            "absence of predictable day-ahead structure is the finding."
        )
    else:
        solid.append(
            f"{len(surviving_ll)} lead-lag relationship(s) survive Bonferroni correction "
            "— flag for out-of-sample validation in Phase 4."
        )

    # Correlation shifts
    if shifts:
        n_pairs = shifts[0].n_pairs_tested
        expected_spurious = round(n_pairs * 0.05)
        uncertain.append(
            f"{len(shifts)} correlation shift(s) flagged from {n_pairs} pairs tested. "
            f"~{expected_spurious} spurious shifts expected by chance at this threshold. "
            "Treat all as candidates until the pattern persists across independent windows."
        )

    # Rotation
    flagged_rot = [s for s in signals if s.flagged]
    if flagged_rot:
        roles = ", ".join(s.role for s in flagged_rot)
        uncertain.append(
            f"Rotation flag(s) for **{roles}** are descriptive only — "
            "a rank shift in a 30-day window does not predict the next 30-day window."
        )

    if not attributed:
        uncertain.append("No moves flagged today — universe was quiet. No signal to interpret.")

    lines.append("### What is uncertain or likely noise")
    lines.append("")
    if uncertain:
        for item in uncertain:
            lines.append(f"- {item}")
    else:
        lines.append("- Nothing flagged as uncertain — unusually clean session.")
    lines += [""]

    lines.append("### What has stronger support")
    lines.append("")
    if solid:
        for item in solid:
            lines.append(f"- {item}")
    else:
        lines.append("- No findings with strong support today.")
    lines += [""]

    return "\n".join(lines)


def _section_lookahead(audit: LookaheadAuditReport) -> str:
    lines = [
        "## Lookahead Bias Audit",
        "",
        "Verifies that rolling calculations only use data available before the "
        "evaluation date. A violation would mean the pipeline is cheating — "
        "using future prices to explain past moves.",
        "",
        f"**Result: {'PASS' if audit.passed else 'FAIL'}** — "
        f"{audit.n_passed} check(s) passed, {audit.n_failed} failed.",
        "",
    ]

    failures = [c for c in audit.checks if not c.passed]
    if failures:
        lines += ["**Failures:**", ""]
        for c in failures:
            lines.append(f"- `{c.name}`: {c.detail}")
        lines += [""]
    else:
        lines += [
            "> All rolling windows confirmed to use only prior data. "
            "No lookahead violations detected.",
            "",
        ]

    return "\n".join(lines)


def _section_oos(report: OOSReport) -> str:
    split = report.split
    lines = [
        "## Out-of-Sample Validation",
        "",
        "Rolling split: in-sample = all data before the last 4 months; "
        "out-of-sample = most recent 4 months. "
        "Patterns are re-tested on the holdout period. "
        "**OOS_CONFIRMED = weak supporting evidence only** — the holdout window is short.",
        "",
        f"| | Date range | Trading days |",
        f"|---|---|---:|",
        f"| In-sample | {split.is_start} → {split.is_end} | {split.is_trading_days} |",
        f"| Out-of-sample | {split.oos_start} → {split.oos_end} | {split.oos_trading_days} |",
        "",
    ]

    verdict_emoji = {
        "OOS_CONFIRMED": "✓",
        "OOS_WEAK": "~",
        "OOS_FAILED": "✗",
        "INSUFFICIENT_DATA": "?",
    }

    for f in report.findings:
        icon = verdict_emoji.get(f.verdict, "?")
        lines += [
            f"### {icon} {f.test_name} — {f.verdict}",
            "",
            f"**In-sample:** {f.is_result}",
            "",
            f"**Out-of-sample:** {f.oos_result}",
            "",
        ]
        if f.detail:
            for line in f.detail.split("\n"):
                lines.append(f"  {line}" if line.strip() else "")
        lines += [""]

    return "\n".join(lines)


def _section_multiple_testing(audit: MultipleTestingAudit) -> str:
    lines = [
        "## Multiple-Testing Audit",
        "",
        f"**Total tests run this session: {audit.total_tests}**  ",
        f"Raw findings (before correction): {audit.total_raw_findings}  ",
        f"Findings surviving Bonferroni correction: {audit.total_bonferroni_findings}",
        "",
        "This section discloses every statistical test the pipeline ran and the "
        "expected false-positive count at the threshold used. "
        "It exists so findings cannot be mistaken for more significant than they are.",
        "",
        "| Test family | Tests | α per test | Raw findings | Bonferroni | BH | Expected FP |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for f in audit.families:
        lines.append(
            f"| {f.name} | {f.n_tests} | {f.alpha_per_test:.4f} | "
            f"{f.n_findings_raw} | {f.n_findings_bonferroni} | {f.n_findings_bh} | "
            f"~{f.expected_false_positives} |"
        )

    lines += [""]
    for f in audit.families:
        if f.notes:
            lines += [f"**{f.name}:** {f.notes}", ""]

    return "\n".join(lines)


def _footer(as_of: date) -> str:
    return f"""\
---

*Report generated by the AI-Compute Buildout Research Pipeline.*
*Data source: Yahoo Finance via yfinance (unofficial). Prices are adjusted for splits and dividends.*
*This document is for research purposes only. It is not financial advice.*
*Thesis source: L. Aschenbrenner, "Situational Awareness: The Decade Ahead" (June 2024),*
*treated as a testable hypothesis — not investment guidance.*
"""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def write_report(
    as_of: date,
    attributed: list[AttributedMove],
    shifts: list[CorrelationShift],
    lead_lag: list[LeadLagResult],
    scorecard: list[ScorecardResult],
    rotation: list[RotationSignal],
    zscore_threshold: float = 2.0,
    vol_window: int = 20,
    lookahead_audit: Optional[LookaheadAuditReport] = None,
    oos_report: Optional[OOSReport] = None,
    mt_audit: Optional[MultipleTestingAudit] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Assemble and write the full markdown report. Returns the path written to.
    Validation sections (Phase 4) are included when provided.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = output_path or REPORTS_DIR / f"{as_of.isoformat()}.md"

    generated_at = datetime.now(timezone.utc)

    sections = [
        _header(as_of, generated_at),
        _section_notable_moves(attributed, as_of, zscore_threshold, vol_window),
        _section_correlations(shifts, lead_lag),
        _section_scorecard(scorecard),
        _section_rotation(rotation),
        _section_noise_summary(attributed, lead_lag, shifts, rotation),
    ]

    if lookahead_audit is not None:
        sections.append(_section_lookahead(lookahead_audit))
    if oos_report is not None:
        sections.append(_section_oos(oos_report))
    if mt_audit is not None:
        sections.append(_section_multiple_testing(mt_audit))

    sections.append(_footer(as_of))

    content = "\n".join(sections)
    output_path.write_text(content, encoding="utf-8")
    return output_path
