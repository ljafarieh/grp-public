"""
Move attribution: for each flagged MoveSignal, assembles candidate explanations
ranked by evidence weight.

Evidence sources (in descending reliability order):
  1. Same-day / recent news headlines for the ticker
  2. Sector/peer co-movement — if the whole sector moved, the individual
     move is less informative (shared macro driver, not company-specific)
  3. Earnings proximity — yfinance calendar (approximate; can be wrong)

Epistemic guardrails enforced here:
  - Every explanation is a hypothesis, never a fact.
  - Confidence is low/medium/high with a stated reason.
  - When no explanation is found we say so explicitly: "no identifiable cause;
    move is likely noise or driven by information not in this dataset."
  - Sector co-movement is computed against peers, not the broad market, to
    avoid false attribution (everything moves with SPY slightly).
  - We do NOT manufacture a narrative for every wiggle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from analysis.moves import MoveSignal
from ingestion.news import get_headlines

logger = logging.getLogger(__name__)


@dataclass
class CandidateExplanation:
    rank: int
    hypothesis: str
    evidence: str
    confidence: str   # "low" | "medium" | "high"
    source: str       # "news" | "sector_comove" | "earnings" | "none"


@dataclass
class AttributedMove:
    signal: MoveSignal
    sector_return_pct: Optional[float]       # avg return of same-role peers that day
    sector_zscore: Optional[float]           # how much of signal move is sector-wide
    explanations: list[CandidateExplanation] = field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# Sector co-movement helper
# ---------------------------------------------------------------------------

def _sector_return(
    ticker: str,
    signal_date: date,
    thesis_role: str,
    universe_meta: dict,
    cached_data: dict[str, pd.DataFrame],
) -> tuple[Optional[float], Optional[float]]:
    """
    Compute the average return of same-role peers (excluding ticker itself)
    on signal_date. Returns (avg_peer_return_pct, peer_count).
    """
    peers = [
        t for t, m in universe_meta.items()
        if m.get("thesis_role") == thesis_role and t != ticker
        and m.get("thesis_role") != "benchmark"
    ]
    if not peers:
        return None, None

    peer_returns = []
    ts = pd.Timestamp(signal_date)
    for peer in peers:
        df = cached_data.get(peer)
        if df is None:
            continue
        df = df.copy()
        df.index = pd.to_datetime(df.index)
        if ts not in df.index:
            continue
        prev_ts = df.index[df.index < ts]
        if prev_ts.empty:
            continue
        prev_close = float(df.loc[prev_ts[-1], "adj_close"])
        today_close = float(df.loc[ts, "adj_close"])
        if prev_close > 0:
            peer_returns.append((today_close / prev_close - 1) * 100)

    if not peer_returns:
        return None, None

    return round(float(np.mean(peer_returns)), 2), len(peer_returns)


# ---------------------------------------------------------------------------
# Earnings proximity helper
# ---------------------------------------------------------------------------

def _earnings_proximity(ticker: str, signal_date: date) -> Optional[str]:
    """
    Check if signal_date is within ±2 trading days of a known earnings date.
    Uses yfinance calendar (approximate; treat as low-confidence).
    Returns a description string if near earnings, else None.
    """
    try:
        import yfinance as yf
        cal = yf.Ticker(ticker).calendar
        if cal is None or cal.empty:
            return None
        # calendar is a DataFrame with columns like 'Earnings Date'
        if "Earnings Date" in cal.columns:
            for ed in cal["Earnings Date"].dropna():
                ed_date = pd.Timestamp(ed).date()
                delta = abs((signal_date - ed_date).days)
                if delta <= 3:
                    return f"earnings reported/expected around {ed_date} (Δ{delta}d)"
        # Some versions return index-based format
        if "Earnings Date" in cal.index:
            ed_raw = cal.loc["Earnings Date"]
            if hasattr(ed_raw, "__iter__"):
                for ed in ed_raw:
                    try:
                        ed_date = pd.Timestamp(ed).date()
                        delta = abs((signal_date - ed_date).days)
                        if delta <= 3:
                            return f"earnings reported/expected around {ed_date} (Δ{delta}d)"
                    except Exception:
                        pass
    except Exception as exc:
        logger.debug("Earnings lookup failed for %s: %s", ticker, exc)
    return None


# ---------------------------------------------------------------------------
# Core attribution
# ---------------------------------------------------------------------------

def attribute_move(
    signal: MoveSignal,
    universe_meta: dict,
    cached_data: dict[str, pd.DataFrame],
    news_lookback_days: int = 3,
) -> AttributedMove:
    """
    Build an AttributedMove for one MoveSignal.
    """
    meta = universe_meta.get(signal.ticker, {})
    thesis_role = meta.get("thesis_role", "unknown")

    # --- sector co-movement ---
    sector_avg, peer_count = _sector_return(
        signal.ticker, signal.signal_date, thesis_role, universe_meta, cached_data
    )

    attributed = AttributedMove(
        signal=signal,
        sector_return_pct=sector_avg,
        sector_zscore=None,
    )

    explanations: list[CandidateExplanation] = []
    rank = 1

    # --- 1. News headlines ---
    headlines = get_headlines(signal.ticker, signal.signal_date, news_lookback_days)
    if headlines:
        # Weight: more headlines = higher confidence that news drove the move
        conf = "medium" if len(headlines) >= 2 else "low"
        titles = "; ".join(h["title"] for h in headlines[:3])
        explanations.append(CandidateExplanation(
            rank=rank,
            hypothesis=f"Move coincides with recent news coverage of {signal.ticker}.",
            evidence=(f"{len(headlines)} headline(s) in last {news_lookback_days}d: \"{titles[:200]}...\"" if len(titles) > 200 else f"{len(headlines)} headline(s): \"{titles}\""),
            confidence=conf,
            source="news",
        ))
        rank += 1

    # --- 2. Sector / peer co-movement ---
    if sector_avg is not None:
        same_direction = (signal.daily_return_pct > 0) == (sector_avg > 0)
        sector_explains_fraction = abs(sector_avg) / max(abs(signal.daily_return_pct), 0.01)

        if same_direction and sector_explains_fraction > 0.5:
            conf = "medium" if sector_explains_fraction > 0.7 else "low"
            explanations.append(CandidateExplanation(
                rank=rank,
                hypothesis=(
                    f"Move is largely explained by {thesis_role} sector co-movement "
                    f"({peer_count} peer(s) averaged {sector_avg:+.1f}% on the same day)."
                ),
                evidence=(
                    f"Sector avg: {sector_avg:+.1f}% vs ticker: {signal.daily_return_pct:+.1f}%. "
                    f"Sector accounts for ~{sector_explains_fraction*100:.0f}% of the move. "
                    "Residual may reflect company-specific news or noise."
                ),
                confidence=conf,
                source="sector_comove",
            ))
            rank += 1
        elif same_direction:
            explanations.append(CandidateExplanation(
                rank=rank,
                hypothesis=(
                    f"Partial sector tailwind: {thesis_role} peers also moved "
                    f"{sector_avg:+.1f}% on average, but {signal.ticker}'s move "
                    "is larger — suggesting an additional company-specific driver."
                ),
                evidence=f"Sector avg: {sector_avg:+.1f}%, ticker: {signal.daily_return_pct:+.1f}%.",
                confidence="low",
                source="sector_comove",
            ))
            rank += 1
        else:
            # ticker moved against its sector — more interesting
            explanations.append(CandidateExplanation(
                rank=rank,
                hypothesis=(
                    f"{signal.ticker} moved {signal.daily_return_pct:+.1f}% against "
                    f"its {thesis_role} peers (avg {sector_avg:+.1f}%), suggesting "
                    "a company-specific driver rather than a macro/sector move."
                ),
                evidence=f"Counter-sector move: peers {sector_avg:+.1f}%, ticker {signal.daily_return_pct:+.1f}%.",
                confidence="medium",
                source="sector_comove",
            ))
            rank += 1

    # --- 3. Earnings proximity ---
    earnings_note = _earnings_proximity(signal.ticker, signal.signal_date)
    if earnings_note:
        explanations.append(CandidateExplanation(
            rank=rank,
            hypothesis=f"Move may be earnings-driven: {earnings_note}.",
            evidence="Earnings date from yfinance calendar (approximate; verify independently).",
            confidence="low",
            source="earnings",
        ))
        rank += 1

    # --- 4. Explicit no-explanation case ---
    if not explanations:
        attributed.summary = (
            f"{signal.ticker} moved {signal.daily_return_pct:+.2f}% "
            f"(z={signal.zscore:+.1f}) with no identifiable cause in this dataset. "
            "Likely noise or driven by information not captured here. "
            "Confidence: low."
        )
        explanations.append(CandidateExplanation(
            rank=1,
            hypothesis="No identifiable cause found.",
            evidence=(
                "No relevant news headlines in the lookback window; "
                "no sector co-movement pattern; no earnings proximity. "
                "Move is a candidate for noise."
            ),
            confidence="low",
            source="none",
        ))
    else:
        direction = "up" if signal.daily_return_pct > 0 else "down"
        top = explanations[0]
        attributed.summary = (
            f"{signal.ticker} moved {signal.daily_return_pct:+.2f}% ({direction}) "
            f"on {signal.signal_date}, z={signal.zscore:+.1f} vs trailing "
            f"{signal.trailing_vol_annualized:.0f}% annualized vol. "
            f"Top candidate: {top.hypothesis} [confidence: {top.confidence}]"
        )

    attributed.explanations = explanations
    return attributed


def attribute_universe(
    signals: list[MoveSignal],
    universe_meta: dict,
    cached_data: dict[str, pd.DataFrame],
    news_lookback_days: int = 3,
) -> list[AttributedMove]:
    """Run attribution for every signal. Returns list in same order."""
    return [
        attribute_move(s, universe_meta, cached_data, news_lookback_days)
        for s in signals
    ]
