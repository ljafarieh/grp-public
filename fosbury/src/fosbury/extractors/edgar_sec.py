"""SEC EDGAR filing scraper — CORZ, IREN, KEEL grid/interconnection signals.

Live target (no auth required — fully public):
    Company submissions: https://data.sec.gov/submissions/CIK{cik}.json
    Filing documents:    https://www.sec.gov/Archives/edgar/data/{cik}/{accno}/{doc}

EDGAR is the SEC's public filing database. All 8-K, 10-Q, and 10-K filings are
publicly available with no API key. Rate limit: 10 requests/second per SEC fair
use policy (we stay well under with a User-Agent header).

What we extract
---------------
Public AI/HPC infrastructure companies (former Bitcoin miners) must disclose
material grid and interconnection developments in SEC filings. This extractor
watches for:

- New PJM interconnection agreements or NTP issuances (8-K item 1.01/8.01)
- Changes to MW capacity or site status (10-Q operational updates)
- Power purchase agreements or utility contracts (8-K)
- Site acquisitions or disposals affecting grid position (8-K item 2.01)

Targets
-------
- Core Scientific (CORZ) — CIK 0001839341
- IREN Limited (IREN)    — CIK 0001878848
- Keel Infrastructure    — CIK 0001812477  (formerly Bitfarms)

Key finding from KEEL 10-Q (filed 2026-08-10):
    KEEL confirmed established PJM grid interconnections in Pennsylvania
    (Sharon, Panther Creek, Scrubgrass sites). As of June 29, 2026 they
    ceased Bitcoin mining at all three PA sites — transition to AI/HPC
    hosting is now the primary business.  Substation infrastructure already
    built with $40M letter of credit to utility.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import structlog
from bs4 import BeautifulSoup

from fosbury.config.settings import Settings
from fosbury.extractors.base import BaseHttpExtractor
from fosbury.pipelines.pdf_parser import ALL_KEYWORDS

log = structlog.get_logger()

_SUBMISSIONS_BASE = "https://data.sec.gov/submissions"
_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# SEC fair-use requires a descriptive User-Agent
_HEADERS = {
    "User-Agent": "Project Fosbury research pipeline ljafarieh@gmail.com",
    "Accept-Encoding": "gzip, deflate",
}

_TARGETS = [
    {
        "ticker": "CORZ",
        "entity": "Core Scientific",
        "cik": "1839341",
        "cik_padded": "0001839341",
    },
    {
        "ticker": "IREN",
        "entity": "IREN Limited",
        "cik": "1878848",
        "cik_padded": "0001878848",
    },
    {
        "ticker": "KEEL",
        "entity": "Keel Infrastructure",
        "cik": "1812477",
        "cik_padded": "0001812477",
    },
]

# Form types worth scanning
_TARGET_FORMS = {"8-K", "10-Q", "10-K"}

# Keywords that indicate a grid/interconnection signal in filing text
_GRID_KEYWORDS = [
    "interconnect", "PJM", "notice to proceed", "NTP", "ISA executed",
    "power purchase agreement", "megawatt", "MW capacity", "substation",
    "transmission", "grid connection", "utility agreement", "colocation",
    "co-location", "hyperscaler", "data center contract",
    "Sharon", "Panther Creek", "Scrubgrass", "Mercer County",
]

# Only flag filings from last 90 days to avoid re-processing old history
_LOOKBACK_DAYS = 90


class EdgarSecScraper(BaseHttpExtractor):
    """Scrape SEC EDGAR for grid/interconnection disclosures from AI/HPC companies."""

    source_key = "edgar_sec"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    def _live_extract(self) -> list[dict[str, Any]]:
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=_LOOKBACK_DAYS)).isoformat()

        events: list[dict[str, Any]] = []

        for target in _TARGETS:
            log.info("edgar_sec.checking", ticker=target["ticker"])
            try:
                filings = self._get_recent_filings(target, cutoff)
            except Exception as exc:
                log.warning("edgar_sec.submissions_failed",
                            ticker=target["ticker"], error=str(exc))
                continue

            log.debug("edgar_sec.filings_found",
                      ticker=target["ticker"], count=len(filings))

            for filing in filings[:6]:  # cap per company to stay under rate limit
                try:
                    text = self._fetch_filing_text(target["cik"], filing)
                    if not text:
                        continue
                except Exception as exc:
                    log.warning("edgar_sec.fetch_failed",
                                ticker=target["ticker"],
                                accno=filing["accno"], error=str(exc))
                    continue

                matched = _scan_keywords(text)
                if len(matched) < 2:
                    log.debug("edgar_sec.no_signal",
                              ticker=target["ticker"], keywords=matched)
                    continue

                excerpt = _build_excerpt(text, matched)
                event_id = hashlib.sha256(
                    f"edgar:{filing['accno']}:{target['ticker']}".encode()
                ).hexdigest()[:24]

                events.append({
                    "event_id": event_id,
                    "iso_region": "PJM",
                    "state_jurisdiction": "FEDERAL",
                    "entity_target": target["entity"],
                    "data_type": _classify_form(filing["form"], matched),
                    "raw_text_blob": excerpt,
                    "metric_delta": _extract_mw(text),
                    "keywords_matched": matched,
                    "source_url": filing["url"],
                })
                log.info("edgar_sec.signal",
                         ticker=target["ticker"],
                         form=filing["form"],
                         date=filing["date"],
                         keywords=matched[:4])

                time.sleep(0.15)  # SEC rate limit courtesy pause

        log.info("edgar_sec.done", total_events=len(events))
        return events

    def _get_recent_filings(
        self, target: dict[str, Any], cutoff: str
    ) -> list[dict[str, Any]]:
        r = self._client.get(
            f"{_SUBMISSIONS_BASE}/CIK{target['cik_padded']}.json",
            headers=_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        recent = data.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accnos = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])

        filings = []
        for form, date, accno, doc in zip(forms, dates, accnos, docs):
            if form not in _TARGET_FORMS:
                continue
            if date < cutoff:
                continue
            clean_accno = accno.replace("-", "")
            url = f"{_ARCHIVES_BASE}/{target['cik']}/{clean_accno}/{doc}"
            filings.append({
                "form": form,
                "date": date,
                "accno": accno,
                "url": url,
            })

        return filings

    def _fetch_filing_text(
        self, cik: str, filing: dict[str, Any]
    ) -> str:
        r = self._client.get(
            filing["url"],
            headers=_HEADERS,
            timeout=30,
            follow_redirects=True,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(separator=" ", strip=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scan_keywords(text: str) -> list[str]:
    lower = text.lower()
    return [kw for kw in _GRID_KEYWORDS if kw.lower() in lower]


def _build_excerpt(text: str, keywords: list[str]) -> str:
    """Return a ~1000-char excerpt centred on the first keyword hit."""
    lower = text.lower()
    idx = next(
        (lower.find(kw.lower()) for kw in keywords if lower.find(kw.lower()) >= 0),
        0,
    )
    start = max(0, idx - 200)
    return text[start: start + 1000].strip()


def _extract_mw(text: str) -> int:
    """Pull the largest MW number mentioned in the filing."""
    import re
    matches = re.findall(r"(\d[\d,]*)\s*(?:MW|megawatt)", text, re.IGNORECASE)
    if not matches:
        return 0
    values = [int(m.replace(",", "")) for m in matches if int(m.replace(",", "")) < 100_000]
    return max(values) if values else 0


def _classify_form(form: str, keywords: list[str]) -> str:
    lower_kws = {k.lower() for k in keywords}
    if "notice to proceed" in lower_kws or "ntp" in lower_kws:
        return "QUEUE_MILESTONE"
    if "power purchase agreement" in lower_kws or "hyperscaler" in lower_kws:
        return "QUEUE_MILESTONE"
    if "isa executed" in lower_kws or "interconnect" in lower_kws:
        return "QUEUE_MILESTONE"
    if form == "8-K":
        return "REGULATORY_PROTEST"
    return "LARGE_LOAD_FORECAST"
