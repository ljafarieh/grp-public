"""PJM Regional Transmission Expansion Plan (RTEP) — state infrastructure report scraper.

Live targets (no auth required — fully public):
    State reports: https://www.pjm.com/-/media/DotCom/library/reports-notices/state-specific-reports/2025/<state>.pdf
    Full report:   https://www.pjm.com/-/media/DotCom/library/reports-notices/2025-rtep/2025-rtep-report.pdf

These are annual reports published in June covering the prior calendar year.
PJM publishes state-specific breakdowns for each of its 13 member states.

What we extract
---------------
1. Large Load Adjustments table — discrete MW of new large load (data centers) added to
   PJM's official load forecast by zone.  A rising number means utilities *must* build
   more transmission and generation to serve these loads — directly bullish for grid
   infrastructure names ($PPL, $AEP, $FE, $D) and a confirmation signal for AI/HPC
   companies with approved interconnections.

2. Capacity auction clearing prices — when an auction clears at the price cap it signals
   the market is capacity-constrained.  Scarcity is bullish for generators (nuclear,
   gas peakers) and bearish for large loads paying elevated capacity charges.

3. Load growth rate — the % range in the executive summary section.  A high growth
   rate (> 3% annually) in a specific transmission zone is a forward-looking signal
   for new transmission project approvals.

Arbitrage focus
---------------
- Virginia / DOMINION zone: ~7 GW of large-load additions already in the 2026 forecast,
  growing to ~22 GW by 2045.  Directly validates the Verrus / PUR-2026-00011 queue thesis.
- Pennsylvania / PPL zone: tariff reform outcome (M-2025-3054271) affects who pays for
  the transmission upgrades needed to serve this load.
- Both 2026/27 and 2027/28 capacity auctions cleared at price cap — confirms scarcity.
"""

from __future__ import annotations

import hashlib
import io
import re
from typing import Any

import structlog

from fosbury.config.settings import Settings
from fosbury.extractors.base import BaseHttpExtractor

log = structlog.get_logger()

_BASE = "https://www.pjm.com/-/media/DotCom/library/reports-notices"

# State-specific reports: highest signal-to-noise, ~2 MB each, 31 pages
_STATE_REPORTS: list[dict[str, Any]] = [
    {
        "state": "VA",
        "entity": "Dominion Energy",
        "url": f"{_BASE}/state-specific-reports/2025/virginia.pdf",
        "zones": ["DOMINION", "APS"],
    },
    {
        "state": "PA",
        "entity": "PPL Corporation",
        "url": f"{_BASE}/state-specific-reports/2025/pennsylvania.pdf",
        "zones": ["PPL", "PECO", "PENELEC", "METED"],
    },
    {
        "state": "OH",
        "entity": "American Electric Power",
        "url": f"{_BASE}/state-specific-reports/2025/ohio.pdf",
        "zones": ["AEP", "DAYTON", "OHIO_ED"],
    },
    {
        "state": "NJ",
        "entity": "PSEG",
        "url": f"{_BASE}/state-specific-reports/2025/new-jersey.pdf",
        "zones": ["PSEG", "JCP&L", "RECO"],
    },
    {
        "state": "MD",
        "entity": "Pepco / BGE",
        "url": f"{_BASE}/state-specific-reports/2025/maryland-dc.pdf",
        "zones": ["PEPCO", "BGE", "SMECO"],
    },
]

# Regex patterns for the large load adjustments table
_LARGE_LOAD_PATTERN = re.compile(
    r"Large Load Adjustments.*?(\d[\d,]+)\s+(\d[\d,]+)\s+(\d[\d,]+)",
    re.DOTALL | re.IGNORECASE,
)

# Capacity auction price cap indicator — both recent auctions cleared at cap
_PRICE_CAP_PATTERN = re.compile(
    r"cleared at.*?\$([\d,]+\.?\d*)\s*price cap",
    re.IGNORECASE,
)

_LOAD_GROWTH_PATTERN = re.compile(
    r"(?:summer|winter) peak.*?(\d+\.\d+)%.*?(\d+\.\d+)%",
    re.IGNORECASE | re.DOTALL,
)

_HEADERS = {
    "Accept": "application/pdf,*/*",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


class PjmRtepScraper(BaseHttpExtractor):
    """Scrape PJM RTEP state infrastructure reports for large-load and capacity signals."""

    source_key = "pjm_rtep"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    def _live_extract(self) -> list[dict[str, Any]]:
        try:
            import pdfplumber
        except ImportError:
            log.warning("pjm_rtep.pdfplumber_missing")
            return []

        events: list[dict[str, Any]] = []

        for report in _STATE_REPORTS:
            log.info("pjm_rtep.fetching", state=report["state"], url=report["url"])
            try:
                resp = self._client.get(report["url"], timeout=60, headers=_HEADERS)
                resp.raise_for_status()
                if not resp.content.startswith(b"%PDF"):
                    log.warning("pjm_rtep.not_pdf", state=report["state"])
                    continue
            except Exception as exc:
                log.warning("pjm_rtep.fetch_failed", state=report["state"], error=str(exc))
                continue

            try:
                with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                    full_text = " ".join(p.extract_text() or "" for p in pdf.pages)
                    page_texts = [p.extract_text() or "" for p in pdf.pages]
            except Exception as exc:
                log.warning("pjm_rtep.parse_failed", state=report["state"], error=str(exc))
                continue

            signals = _extract_signals(full_text, page_texts, report)

            for sig in signals:
                event_id = hashlib.sha256(
                    f"rtep:{report['state']}:{sig['data_type']}:{sig['raw_text_blob'][:120]}".encode()
                ).hexdigest()[:24]

                events.append({
                    "event_id": event_id,
                    "iso_region": "PJM",
                    "state_jurisdiction": report["state"],
                    "entity_target": report["entity"],
                    "data_type": sig["data_type"],
                    "raw_text_blob": sig["raw_text_blob"],
                    "metric_delta": sig["metric_delta"],
                    "keywords_matched": sig["keywords_matched"],
                    "source_url": report["url"],
                })
                log.info(
                    "pjm_rtep.signal",
                    state=report["state"],
                    type=sig["data_type"],
                    metric=sig["metric_delta"],
                )

        log.info("pjm_rtep.done", total_events=len(events))
        return events


# ---------------------------------------------------------------------------
# Signal extraction helpers
# ---------------------------------------------------------------------------


def _extract_signals(
    full_text: str,
    page_texts: list[str],
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    signals = []

    # 1. Large Load Adjustments — find the page with the table
    large_load_page = _find_large_load_page(page_texts)
    if large_load_page:
        sig = _parse_large_load(large_load_page, report)
        if sig:
            signals.append(sig)

    # 2. Capacity auction price cap — scarcity signal
    price_caps = _PRICE_CAP_PATTERN.findall(full_text)
    if price_caps:
        prices = [float(p.replace(",", "")) for p in price_caps]
        max_price = max(prices)
        signals.append({
            "data_type": "CAPACITY_SCARCITY",
            "raw_text_blob": (
                f"PJM {report['state']} state report: capacity auction(s) cleared at price cap. "
                f"Prices found: {', '.join(f'${p}/MW-day' for p in prices)}. "
                f"Price-cap clearing confirms capacity scarcity in {report['state']} transmission zone. "
                f"Bullish for generation owners; bearish for large loads (data centers) paying elevated capacity charges. "
                f"Source: PJM 2025 {report['state']} State Infrastructure Report."
            ),
            "metric_delta": int(max_price),
            "keywords_matched": ["capacity auction", "price cap", "scarcity", report["state"].lower()],
        })

    # 3. Load growth rate from executive summary
    growth_match = _LOAD_GROWTH_PATTERN.search(full_text[:3000])
    if growth_match:
        low_pct = float(growth_match.group(1))
        high_pct = float(growth_match.group(2))
        if high_pct >= 2.0:  # only flag meaningful growth
            signals.append({
                "data_type": "LOAD_GROWTH_FORECAST",
                "raw_text_blob": (
                    f"PJM {report['state']} state report: peak load projected to grow "
                    f"{low_pct:.1f}%–{high_pct:.1f}% annually. "
                    f"High growth rate signals new transmission investment requirements in {report['state']}. "
                    f"Relevant to {report['entity']} capex outlook and large-load tariff proceedings. "
                    f"Source: PJM 2025 {report['state']} State Infrastructure Report."
                ),
                "metric_delta": int(high_pct * 10),
                "keywords_matched": ["load growth", "peak load forecast", report["state"].lower()],
            })

    return signals


def _find_large_load_page(page_texts: list[str]) -> str | None:
    """Return the text of the page containing the Large Load Adjustments table."""
    for text in page_texts:
        if "large load adjustment" in text.lower() and any(
            zone in text for zone in ["DOMINION", "PPL", "AEP", "PSEG", "PEPCO", "BGE"]
        ):
            return text
    return None


def _parse_large_load(page_text: str, report: dict[str, Any]) -> dict[str, Any] | None:
    """Extract MW values for the primary zone from the large load adjustments table."""
    primary_zone = report["zones"][0]

    # Find the row for this zone — grab up to 10 consecutive numbers on that line
    zone_row = re.search(
        rf"(?:^|\n)\s*{re.escape(primary_zone)}\s+([\d,\s]+)",
        page_text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not zone_row:
        return None

    row_numbers = [
        int(n.replace(",", ""))
        for n in re.findall(r"\d[\d,]*", zone_row.group(1))
        if 10 <= int(n.replace(",", "")) <= 99_999
    ]

    if not row_numbers:
        return None

    current_mw = row_numbers[0]   # near-term (first year in forecast, usually current year)
    horizon_mw = row_numbers[-1]  # furthest year

    idx = page_text.lower().find("large load")
    snippet = page_text[max(0, idx):idx + 800].strip() if idx >= 0 else page_text[:800]

    return {
        "data_type": "LARGE_LOAD_FORECAST",
        "raw_text_blob": (
            f"PJM {report['state']} RTEP Large Load Adjustments — {primary_zone} zone: "
            f"{current_mw:,} MW in near-term forecast, growing to {horizon_mw:,} MW at horizon. "
            f"Discrete data-center/large-load requests officially incorporated into PJM load forecast, "
            f"requiring corresponding transmission and generation investment. "
            f"Raw excerpt: {snippet[:600]}"
        ),
        "metric_delta": current_mw,
        "keywords_matched": [
            "large load adjustment", "pjm load forecast", "data center load",
            primary_zone.lower(), report["state"].lower(),
        ],
    }
