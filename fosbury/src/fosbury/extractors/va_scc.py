"""Virginia State Corporation Commission (SCC) — docket scraper.

Live target:
    https://scc.virginia.gov/pages/Daily-Docket-Filings

The SCC posts a daily list of new case filings.  This extractor:
1. Fetches the daily docket HTML page.
2. Finds all PDF links associated with energy-related cases.
3. Downloads each PDF and runs the shared :func:`~fosbury.pipelines.pdf_parser.scan_pdf`.
4. Returns a list of raw event dicts for any document that matches keywords.

No credentials required — the SCC docket is fully public.

Arbitrage focus (per GRP document):
    Dominion Energy transmission delay dockets → scraped VA SCC entries
    tracking line transmission delays signal slower capital deployment
    rates → near-term earnings guidance risk.
"""

from __future__ import annotations

import hashlib
from typing import Any

import structlog
from bs4 import BeautifulSoup

from fosbury.config.settings import Settings
from fosbury.extractors.base import BaseHttpExtractor
from fosbury.pipelines.pdf_parser import scan_pdf

log = structlog.get_logger()

_DOCKET_URL = "https://scc.virginia.gov/docketing/search"

# Companies we care about — any docket mentioning these gets downloaded
_TARGET_ENTITIES = [
    "dominion energy",
    "appalachian power",
    "american electric power",
    "north anna",
    "surry",
]


class VirginiaSCCScraper(BaseHttpExtractor):
    """Scrape VA SCC daily docket filings for energy-related delay signals.

    Args:
        settings: Injected runtime configuration.
    """

    source_key = "va_scc"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    def _live_extract(self) -> list[dict[str, Any]]:
        log.info("va_scc.fetch_docket", url=_DOCKET_URL)
        html = self._get_text(_DOCKET_URL)
        soup = BeautifulSoup(html, "html.parser")

        events: list[dict[str, Any]] = []
        for link in soup.find_all("a", href=True):
            link_text = link.get_text(strip=True).lower()
            href: str = link["href"]

            # Only process PDFs that mention a target entity
            if not href.lower().endswith(".pdf"):
                continue
            if not any(ent in link_text for ent in _TARGET_ENTITIES):
                continue

            pdf_url = href if href.startswith("http") else f"https://scc.virginia.gov{href}"
            log.debug("va_scc.downloading_pdf", url=pdf_url)

            try:
                resp = self._client.get(pdf_url)
                resp.raise_for_status()
                result = scan_pdf(resp.content)
            except Exception as exc:
                log.warning("va_scc.pdf_failed", url=pdf_url, error=str(exc))
                continue

            if not result.has_signal:
                continue

            entity = next(
                (e.title() for e in _TARGET_ENTITIES if e in link_text),
                "Unknown",
            )
            # Canonicalise "Dominion Energy Virginia" → "Dominion Energy"
            if "dominion" in entity.lower():
                entity = "Dominion Energy"

            event_id = hashlib.sha256(
                f"{pdf_url}:{result.full_text[:200]}".encode()
            ).hexdigest()[:24]

            events.append(
                {
                    "event_id": event_id,
                    "iso_region": "PJM",
                    "state_jurisdiction": "VA",
                    "entity_target": entity,
                    "data_type": _classify(result.keywords_matched),
                    "raw_text_blob": result.excerpt(1500),
                    "metric_delta": result.metric_delta,
                    "keywords_matched": result.keywords_matched,
                    "source_url": pdf_url,
                }
            )
            log.info("va_scc.signal_found", entity=entity, keywords=result.keywords_matched[:3])

        log.info("va_scc.done", events=len(events))
        return events

    def _get_text(self, url: str) -> str:
        """Fetch URL and return response text."""
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.text


def _classify(keywords: list[str]) -> str:
    """Map keyword hits to the GRP data_type taxonomy."""
    protest_kws = {"protest", "intervention", "show cause", "ratepayer", "objection"}
    equipment_kws = {"transformer", "switchgear", "supply chain", "procurement", "cooling"}

    lower_kws = {k.lower() for k in keywords}
    if lower_kws & protest_kws:
        return "REGULATORY_PROTEST"
    if lower_kws & equipment_kws:
        return "EQUIPMENT_DELAY"
    return "QUEUE_MILESTONE"
