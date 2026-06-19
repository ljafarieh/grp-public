"""
Multiple-testing audit: catalogs every statistical test the pipeline runs,
the threshold used, the expected false-positive count, and the number of
findings that survive Bonferroni and Benjamini-Hochberg correction.

This is appended to the markdown report as a methodology transparency section.
It exists to prevent the pipeline from deceiving its user by surfacing
spurious patterns without disclosing how many tests generated them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy import stats as scipy_stats


@dataclass
class TestFamily:
    """One family of related hypothesis tests."""
    name: str
    description: str
    n_tests: int
    alpha_per_test: float          # threshold used per individual test
    n_findings_raw: int            # findings before correction
    n_findings_bonferroni: int     # findings surviving Bonferroni
    n_findings_bh: int             # findings surviving Benjamini-Hochberg
    expected_false_positives: float
    raw_pvalues: list[float] = field(default_factory=list)
    notes: str = ""


@dataclass
class MultipleTestingAudit:
    families: list[TestFamily] = field(default_factory=list)

    @property
    def total_tests(self) -> int:
        return sum(f.n_tests for f in self.families)

    @property
    def total_raw_findings(self) -> int:
        return sum(f.n_findings_raw for f in self.families)

    @property
    def total_bonferroni_findings(self) -> int:
        return sum(f.n_findings_bonferroni for f in self.families)


def _benjamini_hochberg(pvalues: list[float], alpha: float = 0.05) -> list[bool]:
    """Return a boolean mask of which p-values survive BH correction."""
    n = len(pvalues)
    if n == 0:
        return []
    indexed = sorted(enumerate(pvalues), key=lambda x: x[1])
    rejected = [False] * n
    for rank, (i, p) in enumerate(indexed, start=1):
        if p <= (rank / n) * alpha:
            rejected[i] = True
        else:
            # BH stops at first non-rejection in the sorted order
            break
    return rejected


def build_multiple_testing_audit(
    correlation_shifts,
    lead_lag_results,
    n_move_tickers: int,
    zscore_threshold: float = 2.0,
) -> MultipleTestingAudit:
    """
    Build the full multiple-testing audit from pipeline outputs.
    """
    audit = MultipleTestingAudit()

    # --- Move detection ---
    # Each ticker is tested for a notable move. The z-score threshold of 2.0
    # corresponds to ~4.6% false positive rate per test (two-tailed normal).
    alpha_move = 2 * (1 - scipy_stats.norm.cdf(zscore_threshold))
    expected_fp_moves = round(n_move_tickers * alpha_move, 1)
    audit.families.append(TestFamily(
        name="Move detection",
        description=f"Daily return z-score vs trailing vol, threshold={zscore_threshold}σ (two-tailed)",
        n_tests=n_move_tickers,
        alpha_per_test=round(alpha_move, 4),
        n_findings_raw=0,   # populated by caller if desired; 0 = no adjustment
        n_findings_bonferroni=0,
        n_findings_bh=0,
        expected_false_positives=expected_fp_moves,
        notes=(
            f"At {zscore_threshold}σ, each ticker has ~{alpha_move*100:.1f}% chance of a false flag "
            f"on any given day. Expected false positives across {n_move_tickers} tickers: "
            f"~{expected_fp_moves}."
        ),
    ))

    # --- Correlation shifts ---
    if correlation_shifts:
        n_corr = correlation_shifts[0].n_pairs_tested
        n_flagged = len(correlation_shifts)
        # No formal p-value for correlation shifts — we use a magnitude threshold.
        # Rough false-positive estimate: assume null shifts are ~N(0, 1/sqrt(n))
        # and our threshold of 0.20 corresponds to some rejection probability.
        # With ~30 observations per window, SE ≈ 1/sqrt(30) ≈ 0.18, so 0.20 is ~1σ → ~32% fp rate
        expected_fp_corr = round(n_corr * 0.32, 0)
        audit.families.append(TestFamily(
            name="Correlation shifts",
            description="Rolling 30d vs prior 30d correlation shift, threshold=0.20",
            n_tests=n_corr,
            alpha_per_test=0.32,  # approximate
            n_findings_raw=n_flagged,
            n_findings_bonferroni=0,  # no formal correction applied (magnitude-based)
            n_findings_bh=0,
            expected_false_positives=expected_fp_corr,
            notes=(
                f"Magnitude threshold of 0.20 on 30-day windows (~30 obs) has a high false-positive "
                f"rate (~32% per pair). {n_flagged} shift(s) flagged from {n_corr} pairs; "
                f"~{int(expected_fp_corr)} expected by chance. "
                "Treat all correlation shifts as hypotheses requiring persistence over multiple windows."
            ),
        ))

    # --- Lead-lag ---
    if lead_lag_results:
        n_ll = lead_lag_results[0].n_tests
        pvals = [r.raw_pvalue for r in lead_lag_results]
        n_raw = sum(1 for p in pvals if p < 0.05)
        n_bonf = sum(1 for r in lead_lag_results if r.survives_correction)
        bh_mask = _benjamini_hochberg(pvals, alpha=0.05)
        n_bh = sum(bh_mask)
        expected_fp_ll = round(n_ll * 0.05, 1)

        audit.families.append(TestFamily(
            name="Lead-lag (1-day)",
            description="Pearson correlation of lagged sector returns, α=0.05",
            n_tests=n_ll,
            alpha_per_test=0.05,
            n_findings_raw=n_raw,
            n_findings_bonferroni=n_bonf,
            n_findings_bh=n_bh,
            expected_false_positives=expected_fp_ll,
            raw_pvalues=pvals,
            notes=(
                f"{n_ll} ordered pairs tested. Uncorrected findings at p<0.05: {n_raw}. "
                f"After Bonferroni: {n_bonf}. After Benjamini-Hochberg: {n_bh}. "
                f"Expected false positives (uncorrected): ~{expected_fp_ll}. "
                "Use Bonferroni or BH-corrected counts for any claim of significance."
            ),
        ))

    return audit
