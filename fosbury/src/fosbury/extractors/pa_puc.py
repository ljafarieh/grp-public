"""Pennsylvania Public Utility Commission (PaPUC) — docket scraper.

Live targets:
    Document search: https://www.puc.pa.gov/search/document-search/
    eFiling portal:  https://efiling.puc.pa.gov/  (login required to file)
    Direct dockets:  https://www.puc.pa.gov/docket/<docket-no>
    Direct PDFs:     https://www.puc.pa.gov/pcdocs/<id>.pdf

The old e-filing search URL (/filing-resources/online-filings/e-filing-search/)
was removed when PA PUC restructured their site.  This extractor now uses:
  1. Direct PDF scans of known high-signal dockets (no auth required)
  2. Playwright-driven document search as a fallback for keyword queries

Key docket being monitored:
    M-2025-3054271 — En Banc Hearing on Interconnection and Tariffs for
    Large Load Customers (data centers).  Testimony filed by Amazon, Google,
    PPL Electric, FirstEnergy, PECO, Duquesne Light, and others.

Arbitrage focus:
    PPL Electric take-or-pay tariff proceedings and nuclear co-location
    protests (Constellation/Talen) that affect AI data center power costs.
"""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from fosbury.config.settings import Settings
from fosbury.extractors.base import BaseHttpExtractor
from fosbury.pipelines.pdf_parser import scan_pdf

log = structlog.get_logger()

# Working document search (replaces the removed e-filing search page)
_SEARCH_URL = "https://www.puc.pa.gov/search/document-search/"

_FALLBACK_URLS = [
    "https://efiling.puc.pa.gov/",
]

_TARGET_SEARCHES = [
    ("Constellation", "Constellation Energy"),
    ("Talen Energy", "Talen Energy"),
    ("nuclear co-location", "Constellation Energy"),
    # PPL bull-case watchlist
    ("PPL Electric", "PPL Corporation"),
    ("large load tariff PPL", "PPL Corporation"),
    ("data center interconnection Pennsylvania", "PPL Corporation"),
]

# ---------------------------------------------------------------------------
# Direct PDF targets — known high-signal documents, scraped every run.
# These bypass the search UI entirely and are always available publicly.
# Docket M-2025-3054271: En Banc Hearing on Interconnection and Tariffs
# for Large Load Customers (data centers). Filed 2025.
# ---------------------------------------------------------------------------
_DIRECT_PDF_TARGETS: list[dict] = [
    {
        "url": "https://www.puc.pa.gov/pcdocs/1875751.pdf",
        "entity": "PPL Corporation",
        "description": "PPL Electric en banc testimony — large load interconnection & tariffs",
    },
    {
        "url": "https://www.puc.pa.gov/pcdocs/1875773.pdf",
        "entity": "Amazon Data Services",
        "description": "Amazon en banc testimony — large load interconnection & tariffs",
    },
    {
        "url": "https://www.puc.pa.gov/pcdocs/1875806.pdf",
        "entity": "Google LLC",
        "description": "Google en banc testimony — large load interconnection & tariffs",
    },
    {
        "url": "https://www.puc.pa.gov/pcdocs/1875805.pdf",
        "entity": "FirstEnergy Pennsylvania",
        "description": "FirstEnergy en banc testimony — large load interconnection & tariffs",
    },
    {
        "url": "https://www.puc.pa.gov/pcdocs/1875750.pdf",
        "entity": "Data Center Coalition",
        "description": "Data Center Coalition en banc testimony — large load interconnection",
    },
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

        # -- Direct PDF scan (always runs, no browser needed) ----------------
        for target in _DIRECT_PDF_TARGETS:
            pdf_url = target["url"]
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            try:
                resp = self._client.get(
                    pdf_url, timeout=20,
                    headers={"Accept": "application/pdf,*/*", "User-Agent": "Mozilla/5.0"},
                )
                resp.raise_for_status()
                result = scan_pdf(resp.content)
            except Exception as exc:
                log.warning("pa_puc.direct_pdf_failed", url=pdf_url, error=str(exc))
                continue

            if not result.has_signal:
                log.debug("pa_puc.direct_pdf_no_signal", url=pdf_url,
                          keywords=result.keywords_matched)
                continue

            event_id = hashlib.sha256(
                f"{pdf_url}:{result.full_text[:200]}".encode()
            ).hexdigest()[:24]

            events.append({
                "event_id": event_id,
                "iso_region": "PJM",
                "state_jurisdiction": "PA",
                "entity_target": target["entity"],
                "data_type": _classify(result.keywords_matched),
                "raw_text_blob": result.excerpt(1500),
                "metric_delta": result.metric_delta,
                "keywords_matched": result.keywords_matched,
                "source_url": pdf_url,
            })
            log.info("pa_puc.direct_signal", entity=target["entity"],
                     keywords=result.keywords_matched[:4])

        # -- Browser-driven keyword search -----------------------------------
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
    tariff_kws = {
        "take-or-pay", "take or pay", "large load tariff", "large-load tariff",
        "data center tariff", "hyperscale tariff", "load commitment",
        "bankable demand", "queue deposit", "withdrawal penalty",
    }
    protest_kws = {"protest", "intervention", "ratepayer", "objection", "show cause"}
    equipment_kws = {"transformer", "switchgear", "supply chain", "equipment", "cooling"}
    lower_kws = {k.lower() for k in keywords}
    # PPL bull-case threat: PA take-or-pay tariff proceedings are highest priority
    if lower_kws & tariff_kws:
        return "PPL_TARIFF_THREAT"
    if lower_kws & protest_kws:
        return "REGULATORY_PROTEST"
    if lower_kws & equipment_kws:
        return "EQUIPMENT_DELAY"
    return "QUEUE_MILESTONE"
