"""GRP alert engine — research signal dispatch via Discord webhook.

This module:
1. Reads un-alerted :class:`~fosbury.core.models.GridEvent` records from SQLite.
2. Looks up the ``entity_target`` in the equity correlation matrix.
3. Formats a structured research alert and POSTs it to Discord.
4. Marks the event as alerted so it is never sent twice.

All output is framed as **informational research** derived from publicly
available regulatory filings.  Nothing here constitutes financial advice or
a trade recommendation.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import httpx
import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Equity correlation matrix
# Maps entity_target names → ticker research context
# Source: GRP document Part III
# ---------------------------------------------------------------------------

TICKER_CORRELATION: dict[str, dict[str, str]] = {
    "Dominion Energy": {
        "ticker": "D",
        "layer": "Regulated Utility",
        "research_context": (
            "Transmission delay signals slower rate-base capital deployment "
            "relative to guidance. Monitor quarterly capex vs. approved rate-base additions."
        ),
    },
    "American Electric Power": {
        "ticker": "AEP",
        "layer": "Regulated Utility",
        "research_context": (
            "Data center load shortfall vs. consensus growth assumptions. "
            "Track uncommitted MW vs. system impact study totals."
        ),
    },
    "Constellation Energy": {
        "ticker": "CEG",
        "layer": "Merchant Generation / IPP",
        "research_context": (
            "Nuclear co-location regulatory friction. Regulatory block or restudy "
            "removes premium priced in for direct AI monetization."
        ),
    },
    "Vistra Corp": {
        "ticker": "VST",
        "layer": "Merchant Generation / IPP",
        "research_context": (
            "Merchant margin pressure from PJM capacity auction rule revisions "
            "or nodal congestion changes not yet in consensus quarterly models."
        ),
    },
    "Talen Energy": {
        "ticker": "TLN",
        "layer": "Merchant Generation / IPP",
        "research_context": (
            "FERC Section 206 co-location compliance uncertainty at Susquehanna. "
            "Net injection restriction or restudy order delays direct AI revenue."
        ),
    },
    "NRG Energy": {
        "ticker": "NRG",
        "layer": "Merchant Generation / IPP",
        "research_context": (
            "Capacity auction clearance shifts and regional gas pipeline "
            "constraints affecting dispatch margins."
        ),
    },
    "FirstEnergy": {
        "ticker": "FE",
        "layer": "Regulated Utility",
        "research_context": (
            "Transmission expansion delays in OH/PA/WV routing corridors "
            "affecting load growth timelines."
        ),
    },
    "Exelon": {
        "ticker": "EXC",
        "layer": "Regulated Utility",
        "research_context": (
            "Ratepayer pushback on transmission capex in IL/MD/PA "
            "forcing rollbacks of approved capital programs."
        ),
    },
    "PPL Corporation": {
        "ticker": "PPL",
        "layer": "Regulated Utility",
        "research_context": (
            "Regional PJM capacity shortfalls and grid stability alerts "
            "affecting mid-atlantic load growth projections."
        ),
    },
    "Quanta Services": {
        "ticker": "PWR",
        "layer": "EPC Contractor",
        "research_context": (
            "Labor availability or raw material shortage signals "
            "that shift project milestone timelines and margin guidance."
        ),
    },
    "GE Vernova": {
        "ticker": "GEV",
        "layer": "Grid Hardware",
        "research_context": (
            "Equipment delivery pushbacks in PJM interconnection queue "
            "are a leading indicator of deferred project revenue."
        ),
    },
    "Eaton Corporation": {
        "ticker": "ETN",
        "layer": "Grid Hardware",
        "research_context": (
            "Transformer procurement delays surface 12-18 months before "
            "they show up in public earnings commentary."
        ),
    },
}


# ---------------------------------------------------------------------------
# Discord dispatch
# ---------------------------------------------------------------------------


def _format_discord_message(event: dict, correlation: dict) -> str:
    """Build the Discord message body for one research alert."""
    ts = event.get("scraped_at", datetime.utcnow().isoformat())
    delta = event.get("metric_delta", 0)
    delta_str = f"{delta} calendar days" if delta else "not yet quantified"
    keywords = ", ".join(event.get("keywords_matched", [])[:5]) or "see excerpt"

    return (
        f"**GRP RESEARCH SIGNAL DETECTED**\n\n"
        f"**Grid Region:** {event.get('iso_region')} "
        f"({event.get('state_jurisdiction')})\n"
        f"**Entity:** {event.get('entity_target')}\n"
        f"**Signal Category:** {event.get('data_type')}\n"
        f"**Delay Metric:** {delta_str}\n"
        f"**Keywords Matched:** {keywords}\n\n"
        f"**Equity Context:** {correlation['ticker']} ({correlation['layer']})\n"
        f"**Research Note:** {correlation['research_context']}\n\n"
        f"**Filing Excerpt:**\n> {event.get('raw_text_blob', '')[:300]}...\n\n"
        f"**Source:** {event.get('source_url', 'N/A')}\n"
        f"*Scraped: {ts} UTC — informational research only*"
    )


def dispatch_alert(event: dict, webhook_url: str) -> bool:
    """POST one research alert to Discord.

    Args:
        event: Raw event dict (keys match GridEvent fields).
        webhook_url: Full Discord webhook URL.

    Returns:
        True if the POST succeeded (2xx response), False otherwise.
    """
    correlation = TICKER_CORRELATION.get(event.get("entity_target", ""))
    if not correlation:
        log.debug("alert_engine.no_correlation", entity=event.get("entity_target"))
        return False

    message = _format_discord_message(event, correlation)
    try:
        resp = httpx.post(webhook_url, json={"content": message}, timeout=10)
        resp.raise_for_status()
        log.info(
            "alert_engine.sent",
            event_id=event.get("event_id"),
            ticker=correlation["ticker"],
        )
        return True
    except httpx.HTTPError as exc:
        log.error("alert_engine.send_failed", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Database sweep — mark alerted events
# ---------------------------------------------------------------------------


def process_pending_alerts(db_path: Path, webhook_url: str) -> int:
    """Find un-alerted GridEvents in SQLite, dispatch each, mark as sent.

    Args:
        db_path: Path to the fosbury SQLite database.
        webhook_url: Discord webhook URL.

    Returns:
        Number of alerts successfully dispatched.
    """
    if not db_path.exists():
        log.warning("alert_engine.no_db", path=str(db_path))
        return 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            "SELECT * FROM grid_events WHERE alert_sent = 0 ORDER BY scraped_at"
        ).fetchall()
    except sqlite3.OperationalError:
        log.warning("alert_engine.no_grid_events_table")
        conn.close()
        return 0

    sent = 0
    for row in rows:
        event = dict(row)
        # keywords_matched is stored as comma-separated string
        raw_kw = event.get("keywords_matched", "")
        event["keywords_matched"] = [k.strip() for k in raw_kw.split(",") if k.strip()]

        if dispatch_alert(event, webhook_url):
            conn.execute(
                "UPDATE grid_events SET alert_sent = 1 WHERE event_id = ?",
                (event["event_id"],),
            )
            conn.commit()
            sent += 1

    conn.close()
    log.info("alert_engine.sweep_done", dispatched=sent, pending=len(rows))
    return sent
