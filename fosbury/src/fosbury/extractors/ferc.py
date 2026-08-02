"""FERC eLibrary — federal regulatory filing scraper.

Live target:
    https://elibrary.ferc.gov/eLibrary/search

FERC (Federal Energy Regulatory Commission) publishes all docket filings
in its public eLibrary.  This extractor queries for FPA Section 205/206
filings and "Show Cause" orders related to nuclear co-location and
behind-the-meter arrangements inside PJM.

No credentials required — FERC eLibrary is a fully public federal system.

Arbitrage focus (per GRP document):
    FERC FPA Section 206 "Show Cause" filings regarding Talen Energy's
    Cumulus Data co-location arrangement and net injection restrictions
    directly threaten revenue from direct AI data center contracts.
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

_SEARCH_BASE = "https://elibrary.ferc.gov/eLibrary/search"

# eLibrary is an Angular SPA — search results are injected by JS.
# We use Playwright to drive the search, then parse the rendered HTML.
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_TARGET_QUERIES = [
    "co-location nuclear behind-the-meter",
    "net injection restriction PJM",
    "Section 206 show cause nuclear",
]

_ENTITY_MAP = {
    "constellation": "Constellation Energy",
    "talen": "Talen Energy",
    "vistra": "Vistra Corp",
    "nrg": "NRG Energy",
    "dominion": "Dominion Energy",
    "aep": "American Electric Power",
}


class FERCScraper(BaseHttpExtractor):
    """Scrape FERC eLibrary for Section 205/206 filings with grid signal keywords.

    Args:
        settings: Injected runtime configuration.
    """

    source_key = "ferc"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    def _live_extract(self) -> list[dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.warning("ferc.playwright_missing")
            return []

        events: list[dict[str, Any]] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(user_agent=_BROWSER_UA)
            page = context.new_page()

            for query in _TARGET_QUERIES:
                log.info("ferc.search", query=query)
                try:
                    page.goto(_SEARCH_BASE, wait_until="domcontentloaded", timeout=20000)
                    for sel in [
                        "input[type='search']", "input[placeholder*='search' i]",
                        "input[id*='search' i]", "input[name*='query' i]",
                    ]:
                        try:
                            page.fill(sel, query, timeout=3000)
                            break
                        except Exception:
                            continue
                    page.keyboard.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=15000)
                    html = page.content()
                except Exception as exc:
                    log.warning("ferc.search_failed", query=query, error=str(exc))
                    continue

                soup = BeautifulSoup(html, "html.parser")
                for link in soup.find_all("a", href=True):
                    href: str = link["href"]
                    link_text = link.get_text(strip=True).lower()

                    if not href.lower().endswith(".pdf"):
                        continue

                    matched_entity = next(
                        (full for key, full in _ENTITY_MAP.items()
                         if key in link_text or key in href.lower()),
                        None,
                    )

                    pdf_url = (
                        href if href.startswith("http")
                        else f"https://elibrary.ferc.gov{href}"
                    )
                    log.debug("ferc.downloading_pdf", url=pdf_url)

                    try:
                        resp = self._client.get(pdf_url)
                        resp.raise_for_status()
                        result = scan_pdf(resp.content)
                    except Exception as exc:
                        log.warning("ferc.pdf_failed", url=pdf_url, error=str(exc))
                        continue

                    if not result.has_signal:
                        continue

                    event_id = hashlib.sha256(
                        f"{pdf_url}:{result.full_text[:200]}".encode()
                    ).hexdigest()[:24]

                    if any(e["event_id"] == event_id for e in events):
                        continue

                    events.append({
                        "event_id": event_id,
                        "iso_region": "PJM",
                        "state_jurisdiction": "FEDERAL",
                        "entity_target": matched_entity or "Unknown",
                        "data_type": "REGULATORY_PROTEST",
                        "raw_text_blob": result.excerpt(1500),
                        "metric_delta": result.metric_delta,
                        "keywords_matched": result.keywords_matched,
                        "source_url": pdf_url,
                    })
                    log.info("ferc.signal_found", entity=matched_entity,
                             keywords=result.keywords_matched[:3])

            browser.close()

        log.info("ferc.done", events=len(events))
        return events
