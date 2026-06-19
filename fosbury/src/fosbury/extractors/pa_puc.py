"""Pennsylvania Public Utility Commission (PaPUC) — docket scraper.

Live target:
    https://www.dms.puc.pa.gov/dms_public/

The PA PUC document management system lists filings by docket number.
This extractor searches for Constellation Energy and Talen Energy cases
related to nuclear co-location tariff challenges.

No credentials required — PA PUC DMS is a public state agency system.

Arbitrage focus (per GRP document):
    PAPUC or FERC filings flagging a formal protest against the
    co-location tariff eliminate the "immediate AI monetization" premium
    priced into Constellation Energy (CEG) stock.
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

_SEARCH_URL = "https://www.dms.puc.pa.gov/dms_public/home"

_TARGET_ENTITIES = {
    "constellation": "Constellation Energy",
    "talen": "Talen Energy",
    "ppl": "PPL Corporation",
    "met-ed": "FirstEnergy",
    "penelec": "FirstEnergy",
    "west penn": "FirstEnergy",
}


class PaPUCScraper(BaseHttpExtractor):
    """Scrape PA PUC filings for nuclear co-location and grid constraint signals.

    Args:
        settings: Injected runtime configuration.
    """

    source_key = "pa_puc"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    def _live_extract(self) -> list[dict[str, Any]]:
        log.info("pa_puc.fetch", url=_SEARCH_URL)

        try:
            resp = self._client.get(_SEARCH_URL)
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            log.warning("pa_puc.fetch_failed", error=str(exc))
            return []

        soup = BeautifulSoup(html, "html.parser")
        events: list[dict[str, Any]] = []

        for link in soup.find_all("a", href=True):
            href: str = link["href"]
            link_text = link.get_text(strip=True).lower()

            if not href.lower().endswith(".pdf"):
                continue

            matched_entity = next(
                (full for key, full in _TARGET_ENTITIES.items() if key in link_text or key in href.lower()),
                None,
            )
            if not matched_entity:
                continue

            pdf_url = href if href.startswith("http") else f"https://www.dms.puc.pa.gov{href}"
            log.debug("pa_puc.downloading_pdf", url=pdf_url)

            try:
                resp = self._client.get(pdf_url)
                resp.raise_for_status()
                result = scan_pdf(resp.content)
            except Exception as exc:
                log.warning("pa_puc.pdf_failed", url=pdf_url, error=str(exc))
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
                    "state_jurisdiction": "PA",
                    "entity_target": matched_entity,
                    "data_type": "REGULATORY_PROTEST",
                    "raw_text_blob": result.excerpt(1500),
                    "metric_delta": result.metric_delta,
                    "keywords_matched": result.keywords_matched,
                    "source_url": pdf_url,
                }
            )
            log.info("pa_puc.signal_found", entity=matched_entity, keywords=result.keywords_matched[:3])

        log.info("pa_puc.done", events=len(events))
        return events
