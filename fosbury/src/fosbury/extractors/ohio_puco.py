"""Ohio Public Utilities Commission (PUCO) — docket scraper.

Live target:
    https://dis.puc.state.oh.us/CaseRecord/SearchCases.aspx

The PUCO case management system lists utility filings.  This extractor
queries for recent American Electric Power (AEP) cases and scans for
signals that data center take-or-pay tariff changes are reducing the
committed load pipeline.

No credentials required — PUCO is a public state agency system.

Arbitrage focus (per GRP document):
    PUCO filings around AEP's data center tariff show that uncommitted
    speculative demand has dropped from 30,000 MW to ~5,700 MW.  Scraping
    this before quarterly calls provides an earlier view of AEP's load
    growth assumptions vs. reality.
"""

from __future__ import annotations

import hashlib
from typing import Any

import structlog
from bs4 import BeautifulSoup

from fosbury.config.settings import Settings
from fosbury.extractors.base import BaseHttpExtractor
from fosbury.pipelines.pdf_parser import scan_pdf, scan_text

log = structlog.get_logger()

_SEARCH_URL = "https://dis.puc.state.oh.us/CaseRecord/SearchCases.aspx"
_TARGET_ENTITIES = ["american electric power", "aep", "ohio power", "duke energy ohio"]


class OhioPUCOScraper(BaseHttpExtractor):
    """Scrape Ohio PUCO for AEP data-center load and tariff filings.

    Args:
        settings: Injected runtime configuration.
    """

    source_key = "ohio_puco"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    def _live_extract(self) -> list[dict[str, Any]]:
        log.info("ohio_puco.fetch", url=_SEARCH_URL)

        # PUCO search uses a GET form; query for AEP large-load cases
        params = {
            "CaseType": "EL",           # Electric
            "Company": "American Electric Power",
            "DateFrom": "",
            "DateTo": "",
        }

        try:
            resp = self._client.get(_SEARCH_URL, params=params)
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            log.warning("ohio_puco.fetch_failed", error=str(exc))
            return []

        soup = BeautifulSoup(html, "html.parser")
        events: list[dict[str, Any]] = []

        # Parse case links and PDF attachments
        for link in soup.find_all("a", href=True):
            href: str = link["href"]
            link_text = link.get_text(strip=True).lower()

            if not href.lower().endswith(".pdf"):
                continue
            if not any(ent in link_text or "aep" in href.lower() for ent in _TARGET_ENTITIES):
                continue

            pdf_url = href if href.startswith("http") else f"https://dis.puc.state.oh.us{href}"
            log.debug("ohio_puco.downloading_pdf", url=pdf_url)

            try:
                resp = self._client.get(pdf_url)
                resp.raise_for_status()
                result = scan_pdf(resp.content)
            except Exception as exc:
                log.warning("ohio_puco.pdf_failed", url=pdf_url, error=str(exc))
                continue

            if not result.has_signal:
                continue

            event_id = hashlib.sha256(
                f"{pdf_url}:{result.full_text[:200]}".encode()
            ).hexdigest()[:24]

            events.append(
                {
                    "event_id": event_id,
                    "iso_region": "PJM",
                    "state_jurisdiction": "OH",
                    "entity_target": "American Electric Power",
                    "data_type": "QUEUE_MILESTONE",
                    "raw_text_blob": result.excerpt(1500),
                    "metric_delta": result.metric_delta,
                    "keywords_matched": result.keywords_matched,
                    "source_url": pdf_url,
                }
            )
            log.info("ohio_puco.signal_found", keywords=result.keywords_matched[:3])

        log.info("ohio_puco.done", events=len(events))
        return events
