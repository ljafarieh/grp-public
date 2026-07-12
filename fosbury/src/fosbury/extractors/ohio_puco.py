"""Ohio Public Utilities Commission (PUCO) — docket scraper.

Live target:
    https://dis.puc.state.oh.us/CaseRecord/SearchCases.aspx

Uses Playwright to handle the ASP.NET form-based search and collect
PDF filings related to AEP Ohio data-center interconnection cases.

No credentials required — PUCO case search is fully public.

Arbitrage focus:
    AEP Ohio interconnection queue milestones and load study updates
    signal data-center energisation timelines ahead of earnings calls.
"""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from fosbury.config.settings import Settings
from fosbury.extractors.base import BaseHttpExtractor
from fosbury.pipelines.pdf_parser import scan_pdf

log = structlog.get_logger()

_SEARCH_URL = "https://dis.puc.state.oh.us/CaseRecord/SearchCases.aspx"

_TARGET_SEARCHES = [
    ("AEP Ohio", "American Electric Power"),
    ("data center", "American Electric Power"),
    ("interconnection", "American Electric Power"),
]


class OhioPUCOScraper(BaseHttpExtractor):
    """Scrape Ohio PUCO case filings using a headless browser."""

    source_key = "ohio_puco"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    def _live_extract(self) -> list[dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            log.warning("ohio_puco.playwright_missing")
            return []

        events: list[dict[str, Any]] = []
        seen: set[str] = set()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ))
            page = context.new_page()

            for search_term, entity_name in _TARGET_SEARCHES:
                log.info("ohio_puco.search", term=search_term)
                try:
                    page.goto(_SEARCH_URL, wait_until="domcontentloaded", timeout=20000)

                    # Fill ASP.NET search form — try common field names
                    for selector in [
                        "input[id*='Company']", "input[id*='company']",
                        "input[name*='Company']", "input[id*='Search']",
                        "input[type='text']",
                    ]:
                        try:
                            page.fill(selector, search_term, timeout=3000)
                            break
                        except Exception:
                            continue

                    # Submit — try button click or Enter
                    for btn_selector in [
                        "input[type='submit']", "input[value*='Search' i]",
                        "button[type='submit']", "input[id*='Search']",
                    ]:
                        try:
                            page.click(btn_selector, timeout=3000)
                            break
                        except Exception:
                            continue
                    else:
                        page.keyboard.press("Enter")

                    page.wait_for_load_state("networkidle", timeout=15000)

                    # Collect PDF links from results
                    pdf_links = page.eval_on_selector_all(
                        "a[href$='.pdf'], a[href*='.pdf'], a[href*='GetDocument']",
                        "els => els.map(e => ({href: e.href, text: e.textContent.trim()}))"
                    )
                    log.debug("ohio_puco.links_found", count=len(pdf_links))

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
                            log.warning("ohio_puco.pdf_failed", url=pdf_url, error=str(exc))
                            continue

                        if not result.has_signal:
                            continue

                        event_id = hashlib.sha256(
                            f"{pdf_url}:{result.full_text[:200]}".encode()
                        ).hexdigest()[:24]

                        events.append({
                            "event_id": event_id,
                            "iso_region": "PJM",
                            "state_jurisdiction": "OH",
                            "entity_target": entity_name,
                            "data_type": _classify(result.keywords_matched),
                            "raw_text_blob": result.excerpt(1500),
                            "metric_delta": result.metric_delta,
                            "keywords_matched": result.keywords_matched,
                            "source_url": pdf_url,
                        })
                        log.info("ohio_puco.signal_found", entity=entity_name,
                                 keywords=result.keywords_matched[:3])

                except PWTimeout:
                    log.warning("ohio_puco.timeout", term=search_term)
                except Exception as exc:
                    log.warning("ohio_puco.search_failed", term=search_term, error=str(exc))

            browser.close()

        log.info("ohio_puco.done", events=len(events))
        return events


def _classify(keywords: list[str]) -> str:
    protest_kws = {"protest", "intervention", "ratepayer", "objection"}
    equipment_kws = {"transformer", "switchgear", "supply chain", "equipment"}
    lower_kws = {k.lower() for k in keywords}
    if lower_kws & protest_kws:
        return "REGULATORY_PROTEST"
    if lower_kws & equipment_kws:
        return "EQUIPMENT_DELAY"
    return "QUEUE_MILESTONE"
