"""Pennsylvania Public Utility Commission (PaPUC) — docket scraper.

Live target:
    https://www.puc.pa.gov/filing-resources/online-filings/

The PA PUC document management system (DMS) has an unreliable hostname.
This extractor uses the main PUC filing search page via Playwright, then
collects PDFs related to Constellation Energy and Talen Energy co-location
and nuclear restart filings.

No credentials required — PA PUC filings are fully public.

Arbitrage focus:
    Constellation (CEG) and Talen (TLN) nuclear co-location protest
    filings at PA PUC track direct regulatory risk to AI data center
    power purchase agreement revenues.
"""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from fosbury.config.settings import Settings
from fosbury.extractors.base import BaseHttpExtractor
from fosbury.pipelines.pdf_parser import scan_pdf

log = structlog.get_logger()

# Primary search portal — more stable than the DMS subdomain
_SEARCH_URL = "https://www.puc.pa.gov/filing-resources/online-filings/e-filing-search/"

_TARGET_SEARCHES = [
    ("Constellation", "Constellation Energy"),
    ("Talen Energy", "Talen Energy"),
    ("nuclear co-location", "Constellation Energy"),
    ("PPL Electric", "PPL Corporation"),
]

_FALLBACK_URLS = [
    "https://efiling.puc.pa.gov/dockets/search",
    "https://www.puc.pa.gov/general/docSearch/default.aspx",
]


class PaPUCScraper(BaseHttpExtractor):
    """Scrape PA PUC docket filings using a headless browser."""

    source_key = "pa_puc"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    def _live_extract(self) -> list[dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            log.warning("pa_puc.playwright_missing")
            return []

        events: list[dict[str, Any]] = []
        seen: set[str] = set()

        # Try primary URL, fall back if it fails
        search_urls = [_SEARCH_URL] + _FALLBACK_URLS

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ))
            page = context.new_page()

            # Find a working search URL
            working_url = None
            for url in search_urls:
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    if resp and resp.status < 400:
                        working_url = url
                        log.info("pa_puc.using_url", url=url)
                        break
                except Exception:
                    continue

            if not working_url:
                log.warning("pa_puc.no_working_url")
                browser.close()
                return []

            for search_term, entity_name in _TARGET_SEARCHES:
                log.info("pa_puc.search", term=search_term)
                try:
                    page.goto(working_url, wait_until="domcontentloaded", timeout=15000)

                    # Fill search box
                    for selector in [
                        "input[type='search']", "input[type='text']",
                        "input[id*='search' i]", "input[name*='search' i]",
                        "input[id*='company' i]", "input[placeholder*='search' i]",
                    ]:
                        try:
                            page.fill(selector, search_term, timeout=3000)
                            break
                        except Exception:
                            continue

                    page.keyboard.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=15000)

                    # Collect PDF links
                    pdf_links = page.eval_on_selector_all(
                        "a[href$='.pdf'], a[href*='.pdf'], a[href*='document' i]",
                        "els => els.map(e => ({href: e.href, text: e.textContent.trim()}))"
                    )
                    log.debug("pa_puc.links_found", count=len(pdf_links))

                    for link in pdf_links[:10]:
                        pdf_url = link.get("href", "")
                        if not pdf_url or pdf_url in seen:
                            continue
                        seen.add(pdf_url)

                        try:
                            resp = self._client.get(pdf_url, timeout=15)
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

                        events.append({
                            "event_id": event_id,
                            "iso_region": "PJM",
                            "state_jurisdiction": "PA",
                            "entity_target": entity_name,
                            "data_type": _classify(result.keywords_matched),
                            "raw_text_blob": result.excerpt(1500),
                            "metric_delta": result.metric_delta,
                            "keywords_matched": result.keywords_matched,
                            "source_url": pdf_url,
                        })
                        log.info("pa_puc.signal_found", entity=entity_name,
                                 keywords=result.keywords_matched[:3])

                except PWTimeout:
                    log.warning("pa_puc.timeout", term=search_term)
                except Exception as exc:
                    log.warning("pa_puc.search_failed", term=search_term, error=str(exc))

            browser.close()

        log.info("pa_puc.done", events=len(events))
        return events


def _classify(keywords: list[str]) -> str:
    protest_kws = {"protest", "intervention", "ratepayer", "objection", "show cause"}
    equipment_kws = {"transformer", "switchgear", "supply chain", "equipment", "cooling"}
    lower_kws = {k.lower() for k in keywords}
    if lower_kws & protest_kws:
        return "REGULATORY_PROTEST"
    if lower_kws & equipment_kws:
        return "EQUIPMENT_DELAY"
    return "QUEUE_MILESTONE"
